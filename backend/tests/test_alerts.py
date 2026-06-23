import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.bootstrap import build_company_os
from app.core.enums import PermissionLevel, RiskLevel
from app.core.models import Incident
from app.observability.alerts import (
    AlertConfigurationError,
    AlertDispatcher,
    AlertSettings,
)
from app.services.company import CompanyApplicationService


class AlertTests(unittest.TestCase):
    def test_alert_status_is_disabled_by_default_without_secret_exposure(self):
        dispatcher = AlertDispatcher(AlertSettings())

        status = dispatcher.status()

        self.assertFalse(status["enabled"])
        self.assertFalse(status["configured"])
        self.assertIsNone(status["endpoint_host"])

    def test_enabled_webhook_sends_sanitized_incident_payload(self):
        deliveries = []

        def transport(url, payload, timeout):
            deliveries.append((url, payload, timeout))
            return 202

        dispatcher = AlertDispatcher(
            AlertSettings(
                enabled=True,
                webhook_url="https://alerts.example/hooks/secret-token",
                timeout_seconds=3,
            ),
            transport=transport,
        )
        incident = Incident(
            title="Queue failed",
            description="Failed delivery needs review.",
            source_type="schedule",
            source_id="schedule_1",
            risk_level=RiskLevel.MEDIUM,
            actor_id="human_root",
        )

        result = dispatcher.send_incident(incident)
        status = dispatcher.status()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.http_status, 202)
        self.assertEqual(status["endpoint_host"], "alerts.example")
        self.assertEqual(deliveries[0][0], "https://alerts.example/hooks/secret-token")
        self.assertEqual(deliveries[0][1]["event_type"], "incident.opened")
        self.assertEqual(deliveries[0][1]["incident"]["incident_id"], incident.incident_id)
        self.assertNotIn("webhook_url", deliveries[0][1])
        self.assertEqual(deliveries[0][2], 3)

    def test_external_http_webhook_is_rejected(self):
        with self.assertRaises(AlertConfigurationError):
            AlertDispatcher(
                AlertSettings(
                    enabled=True,
                    webhook_url="http://alerts.example/hook",
                )
            )

    def test_service_alerts_opened_incidents_and_audits_delivery(self):
        deliveries = []

        def transport(_url, payload, _timeout):
            deliveries.append(payload)
            return 200

        service = CompanyApplicationService(
            build_company_os(),
            alerts=AlertDispatcher(
                AlertSettings(enabled=True, webhook_url="https://alerts.example/hook"),
                transport=transport,
            ),
        )

        response = service.request_action_approval(
            action="forbidden_root_change",
            actor_id="ceo_agent_v1",
            permission_level=PermissionLevel.L5_ROOT,
            reason="This must alert Human Root.",
        )

        audit = service.list_audit_logs()

        self.assertEqual(response["incident"]["status"], "open")
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0]["incident"]["incident_id"], response["incident"]["incident_id"])
        alert_events = [event for event in audit if event["event_type"] == "alert_delivery_sent"]
        self.assertEqual(len(alert_events), 1)
        self.assertEqual(alert_events[0]["output_ref"], "webhook")
        self.assertIsNone(alert_events[0]["error"])

    def test_service_records_alert_delivery_failure_without_blocking_incident(self):
        def transport(_url, _payload, _timeout):
            return 500

        service = CompanyApplicationService(
            build_company_os(),
            alerts=AlertDispatcher(
                AlertSettings(enabled=True, webhook_url="https://alerts.example/hook"),
                transport=transport,
            ),
        )

        response = service.request_action_approval(
            action="forbidden_root_change",
            actor_id="ceo_agent_v1",
            permission_level=PermissionLevel.L5_ROOT,
            reason="Alert transport failure should not hide the incident.",
        )

        audit = service.list_audit_logs()

        self.assertEqual(response["incident"]["status"], "open")
        alert_events = [event for event in audit if event["event_type"] == "alert_delivery_failed"]
        self.assertEqual(len(alert_events), 1)
        self.assertIn("HTTP 500", alert_events[0]["error"])


if __name__ == "__main__":
    unittest.main()
