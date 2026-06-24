import json
import os
import sys
import unittest
from contextlib import contextmanager


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.main import create_app


@contextmanager
def patched_env(values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class DeploymentReadinessTests(unittest.TestCase):
    def test_default_local_environment_is_not_production_ready(self):
        response = TestClient(create_app()).get("/deployment/readiness")
        payload = response.json()
        checks = {check["name"]: check for check in payload["checks"]}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "not_ready")
        self.assertEqual(checks["http_auth_gate"]["status"], "critical")
        self.assertEqual(checks["production_persistence"]["status"], "critical")
        self.assertEqual(checks["scheduler_queue"]["status"], "critical")
        self.assertEqual(checks["incident_runbooks"]["status"], "ok")

    def test_readiness_auth_check_uses_secret_safe_metadata(self):
        with patched_env(
            {
                "AI_COMPANY_OS_AUTH_REQUIRED": "true",
                "AI_COMPANY_OS_API_TOKEN": "test-token",
                "AI_COMPANY_OS_API_TOKEN_SHA256": None,
                "AI_COMPANY_OS_ALERTS_ENABLED": "true",
                "AI_COMPANY_OS_ALERT_WEBHOOK_URL": "https://alerts.example/hook",
                "AI_COMPANY_OS_ALERT_TIMEOUT_SECONDS": "5",
            }
        ):
            client = TestClient(create_app())
            response = client.get(
                "/deployment/readiness",
                headers={"Authorization": "Bearer test-token"},
            )
        payload = response.json()
        rendered = json.dumps(payload)
        checks = {check["name"]: check for check in payload["checks"]}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(checks["http_auth_gate"]["status"], "ok")
        self.assertTrue(checks["http_auth_gate"]["details"]["static_token_configured"])
        self.assertEqual(checks["incident_alert_delivery"]["status"], "ok")
        self.assertEqual(checks["incident_alert_delivery"]["details"]["endpoint_host"], "alerts.example")
        self.assertNotIn("test-token", rendered)
        self.assertNotIn("https://alerts.example/hook", rendered)


if __name__ == "__main__":
    unittest.main()
