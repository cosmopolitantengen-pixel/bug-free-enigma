import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.main import create_app


class RunbookApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_runbook_catalog_is_available(self):
        response = self.client.get("/runbooks")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(payload), 5)
        self.assertIn("scheduler_failure_response", [item["runbook_id"] for item in payload])
        self.assertTrue(all(item["immediate_actions"] for item in payload))
        self.assertTrue(all(item["verification_steps"] for item in payload))

    def test_blocked_root_policy_update_includes_safety_runbook(self):
        blocked = self.client.post(
            "/budget/policy",
            json={
                "actor_id": "ceo_agent_v1",
                "name": "Unauthorized policy",
                "max_tokens_per_call": 1,
                "max_total_tokens": 10,
                "max_estimated_cost": 1,
                "cost_per_token": 0.000001,
                "currency": "USD",
                "enabled": True,
            },
        )
        incidents = self.client.get("/incidents").json()
        incident = incidents[-1]
        runbook = self.client.get(f"/incidents/{incident['incident_id']}/runbook")

        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(incident["source_type"], "budget_policy")
        self.assertEqual(incident["runbook_id"], "safety_control_response")
        self.assertEqual(incident["runbook"]["owner_agent"], "risk_agent_v1")
        self.assertEqual(runbook.status_code, 200)
        self.assertEqual(runbook.json()["runbook_id"], "safety_control_response")

    def test_scheduler_failure_incident_uses_scheduler_runbook(self):
        task = self.client.post(
            "/tasks",
            json={"title": "Budget-blocked scheduled run", "description": "Trigger a scheduler incident."},
        ).json()
        schedule = self.client.post(
            "/schedules",
            json={
                "name": "Run blocked task",
                "action": "run_task",
                "payload": {"task_id": task["task_id"]},
                "next_run_at": "2030-03-01T00:00:00+00:00",
            },
        ).json()
        self.client.post(
            "/budget/policy",
            json={
                "actor_id": "human_root",
                "name": "Blocking policy",
                "max_tokens_per_call": 1,
                "max_total_tokens": 10,
                "max_estimated_cost": 1,
                "cost_per_token": 0.000001,
                "currency": "USD",
                "enabled": True,
            },
        )
        tick = self.client.post("/scheduler/tick", json={"now": "2030-03-01T00:00:00+00:00"})
        incidents = self.client.get("/incidents").json()
        incident = [item for item in incidents if item["source_id"] == schedule["schedule_id"]][0]

        self.assertEqual(tick.status_code, 200)
        self.assertEqual(tick.json()["executions"][0]["status"], "failed")
        self.assertEqual(incident["runbook_id"], "scheduler_failure_response")
        self.assertIn("Pause the affected schedule", incident["runbook"]["immediate_actions"][0])

    def test_unknown_incident_runbook_returns_404(self):
        response = self.client.get("/incidents/incident_missing/runbook")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
