import json
import os
import sys
import tempfile
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.main import create_app


class ApiRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health_and_foundation_lists(self):
        health = self.client.get("/health")
        integrity = self.client.get("/system/integrity")
        agents = self.client.get("/agents")
        skills = self.client.get("/skills")
        workflows = self.client.get("/workflows")
        tools = self.client.get("/tools")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(integrity.status_code, 200)
        self.assertEqual(integrity.json()["status"], "warning")
        self.assertIn("persistence_backend", [check["name"] for check in integrity.json()["checks"]])
        self.assertGreaterEqual(len(agents.json()), 5)
        self.assertGreaterEqual(len(skills.json()), 5)
        self.assertGreaterEqual(len(tools.json()), 5)
        self.assertEqual(workflows.json()[0]["workflow_id"], "document_generation_v1")

    def test_database_schema_reports_memory_and_sqlite_backends(self):
        memory_schema = self.client.get("/database/schema")

        self.assertEqual(memory_schema.status_code, 200)
        self.assertEqual(memory_schema.json()["backend"], "memory")
        self.assertIsNone(memory_schema.json()["schema_version"])
        self.assertEqual(memory_schema.json()["migrations"], [])

        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = os.path.join(tmpdir, "schema.db")
            sqlite_client = TestClient(create_app(sqlite_path=sqlite_path))
            sqlite_schema = sqlite_client.get("/database/schema")

            self.assertEqual(sqlite_schema.status_code, 200)
            self.assertEqual(sqlite_schema.json()["backend"], "sqlite")
            self.assertEqual(sqlite_schema.json()["schema_version"], 2)
            self.assertEqual(sqlite_schema.json()["migrations"][0]["migration_id"], "0001_initial_local_state")
            self.assertEqual(sqlite_schema.json()["migrations"][1]["migration_id"], "0002_audit_append_only_guards")

    def test_system_integrity_reports_sqlite_guards_and_backup_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = os.path.join(tmpdir, "integrity.db")
            client = TestClient(create_app(sqlite_path=sqlite_path))
            before_backup = client.get("/system/integrity")
            client.post(
                "/backups",
                json={"actor_id": "human_root", "reason": "Create integrity baseline."},
            )
            after_backup = client.get("/system/integrity")

            self.assertEqual(before_backup.status_code, 200)
            self.assertEqual(before_backup.json()["status"], "warning")
            self.assertIn("backup_integrity", [check["name"] for check in before_backup.json()["checks"]])
            self.assertEqual(after_backup.status_code, 200)
            self.assertEqual(after_backup.json()["status"], "ok")
            checks = {check["name"]: check for check in after_backup.json()["checks"]}
            self.assertEqual(checks["schema_version"]["status"], "ok")
            self.assertEqual(checks["audit_append_only_storage"]["status"], "ok")
            self.assertEqual(checks["backup_integrity"]["status"], "ok")

    def test_cors_allows_local_dashboard_requests(self):
        response = self.client.options(
            "/dashboard/summary",
            headers={
                "Origin": "file://",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")

    def test_task_run_writes_audit_memory_knowledge_and_dashboard(self):
        created = self.client.post(
            "/tasks",
            json={"title": "API task", "description": "Run the API document task."},
        )
        task_id = created.json()["task_id"]

        run = self.client.post(f"/tasks/{task_id}/run")
        audit_logs = self.client.get("/audit-logs")
        memory = self.client.get("/memory")
        knowledge = self.client.get("/knowledge")
        evaluations = self.client.get("/evaluations")
        workflow_runs = self.client.get("/workflow-runs")
        model_usage = self.client.get("/model-usage")
        cost_logs = self.client.get("/cost-logs")
        structured_logs = self.client.get("/logs/structured")
        budget = self.client.get("/budget/summary")
        dashboard = self.client.get("/dashboard/summary")
        workflow_steps = self.client.get(f"/workflow-runs/{workflow_runs.json()[0]['run_id']}/steps")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["task"]["status"], "completed")
        self.assertGreaterEqual(len(audit_logs.json()), 7)
        self.assertGreaterEqual(len(memory.json()), 1)
        self.assertGreaterEqual(len(knowledge.json()), 1)
        self.assertEqual(len(evaluations.json()), 3)
        self.assertEqual(len(workflow_runs.json()), 1)
        self.assertEqual(workflow_runs.json()[0]["status"], "completed")
        self.assertEqual(len(workflow_steps.json()), 7)
        self.assertEqual(len(model_usage.json()), 1)
        self.assertEqual(model_usage.json()[0]["purpose"], "document_generation")
        self.assertEqual(len(cost_logs.json()), 1)
        self.assertEqual(cost_logs.json()[0]["result"], "recorded")
        self.assertEqual(structured_logs.status_code, 200)
        self.assertGreaterEqual(len(structured_logs.json()), len(audit_logs.json()))
        self.assertIn("category", structured_logs.json()[-1])
        self.assertIn("level", structured_logs.json()[-1])
        self.assertIn("message", structured_logs.json()[-1])
        self.assertGreater(budget.json()["used_tokens"], 0)
        self.assertGreaterEqual(dashboard.json()["task_count"], 1)
        self.assertEqual(dashboard.json()["system_health"], "ok")
        self.assertEqual(dashboard.json()["task_status_counts"]["completed"], 1)
        self.assertGreaterEqual(dashboard.json()["memory_count"], 1)
        self.assertGreaterEqual(dashboard.json()["knowledge_count"], 1)
        self.assertGreaterEqual(dashboard.json()["audit_log_count"], 7)
        self.assertEqual(dashboard.json()["evaluation_count"], 3)
        self.assertEqual(dashboard.json()["average_evaluation_score"], 1.0)
        self.assertGreaterEqual(dashboard.json()["tool_count"], 5)
        self.assertEqual(dashboard.json()["workflow_run_count"], 1)
        self.assertEqual(dashboard.json()["workflow_step_count"], 7)
        self.assertEqual(dashboard.json()["model_usage_count"], 1)
        self.assertGreater(dashboard.json()["model_token_count"], 0)
        self.assertEqual(dashboard.json()["cost_log_count"], 1)
        self.assertGreaterEqual(dashboard.json()["structured_log_count"], len(audit_logs.json()))
        self.assertGreaterEqual(len(dashboard.json()["recent_structured_logs"]), 1)
        self.assertGreater(dashboard.json()["budget_used_tokens"], 0)
        self.assertEqual(dashboard.json()["incident_count"], 0)
        self.assertEqual(len(dashboard.json()["recent_model_usage"]), 1)
        self.assertEqual(len(dashboard.json()["recent_workflow_runs"]), 1)
        self.assertEqual(len(dashboard.json()["recent_workflow_steps"]), 7)
        self.assertEqual(len(dashboard.json()["recent_evaluations"]), 3)
        self.assertGreaterEqual(len(dashboard.json()["recent_tasks"]), 1)

    def test_structured_logs_can_filter_by_category_and_level(self):
        self.client.post(
            "/tasks",
            json={"title": "Structured log task", "description": "Run task for structured logs."},
        )
        task_id = self.client.get("/tasks").json()[0]["task_id"]
        self.client.post(f"/tasks/{task_id}/run")

        workflow_logs = self.client.get("/logs/structured?category=workflow&limit=5")
        info_logs = self.client.get("/logs/structured?level=info&limit=5")
        empty_logs = self.client.get("/logs/structured?limit=0")

        self.assertEqual(workflow_logs.status_code, 200)
        self.assertEqual(info_logs.status_code, 200)
        self.assertTrue(all(log["category"] == "workflow" for log in workflow_logs.json()))
        self.assertTrue(all(log["level"] == "info" for log in info_logs.json()))
        self.assertEqual(empty_logs.json(), [])

    def test_resume_task_route_rejects_task_not_waiting_for_approval(self):
        created = self.client.post(
            "/tasks",
            json={"title": "Resume guard", "description": "Normal completed workflow should not resume."},
        )
        run = self.client.post(f"/tasks/{created.json()['task_id']}/run")
        resumed = self.client.post(f"/tasks/{created.json()['task_id']}/resume")

        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["task"]["status"], "completed")
        self.assertEqual(resumed.status_code, 400)
        self.assertIn("not waiting", resumed.json()["detail"])

    def test_tool_run_routes_complete_or_block_with_audit(self):
        completed = self.client.post(
            "/tools/runs/request",
            json={
                "tool_id": "task_manager_tool",
                "actor_id": "ceo_agent_v1",
                "input": {"operation": "inspect"},
                "reason": "Inspect internal task state.",
            },
        )
        blocked = self.client.post(
            "/tools/runs/request",
            json={
                "tool_id": "code_execution_tool",
                "actor_id": "ceo_agent_v1",
                "input": {"language": "python", "source": "print('hello')"},
                "reason": "Disabled tool should not execute.",
            },
        )
        runs = self.client.get("/tools/runs")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["run"]["status"], "completed")
        self.assertIn("task_count", json.loads(completed.json()["run"]["result"]))
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.json()["run"]["status"], "blocked")
        self.assertEqual(len(runs.json()), 2)
        self.assertEqual(audit.json()[-1]["event_type"], "tool_run_requested")
        self.assertEqual(dashboard.json()["tool_run_count"], 2)
        self.assertIn("recent_tool_runs", dashboard.json())

    def test_filesystem_read_tool_route_returns_safe_file_result(self):
        response = self.client.post(
            "/tools/runs/request",
            json={
                "tool_id": "filesystem_read_tool",
                "actor_id": "document_agent_v1",
                "input": {"operation": "read", "path": "README.md"},
                "reason": "Read project README for context.",
            },
        )
        blocked = self.client.post(
            "/tools/runs/request",
            json={
                "tool_id": "filesystem_read_tool",
                "actor_id": "document_agent_v1",
                "input": {"operation": "read", "path": "../PROJECT_IDEA_FOR_CODEX.md"},
                "reason": "Path traversal must fail.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run"]["status"], "completed")
        self.assertIn("README.md", json.loads(response.json()["run"]["result"])["path"])
        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.json()["run"]["status"], "failed")

    def test_approval_gated_tool_run_can_complete_after_approval(self):
        tool = self.client.post(
            "/tools",
            json={
                "tool_id": "approval_route_tool",
                "name": "Approval Route Tool",
                "type": "internal",
                "description": "Medium-risk route test tool.",
                "action": "prepare_external_content",
                "permission_level": "L3_EXTERNAL_PREPARE",
                "risk_level": "medium",
                "requires_approval": True,
                "input_schema": {"topic": "string"},
                "output_schema": {"message": "string"},
                "enabled": True,
            },
        )
        agent = self.client.post(
            "/agents",
            json={
                "agent_id": "approval_route_agent",
                "name": "Approval Route Agent",
                "department": "QA",
                "role": "Exercise approval-gated tools through API.",
                "permissions": ["L0_READ", "L1_DRAFT", "L2_INTERNAL_WRITE", "L3_EXTERNAL_PREPARE"],
                "allowed_tools": ["approval_route_tool"],
                "reports_to": "human_root",
                "risk_level": "low",
                "enabled": True,
            },
        )
        requested = self.client.post(
            "/tools/runs/request",
            json={
                "tool_id": "approval_route_tool",
                "actor_id": "approval_route_agent",
                "input": {"topic": "API approval"},
                "reason": "Approval-gated API test.",
            },
        )
        early = self.client.post(
            f"/tools/runs/{requested.json()['run']['run_id']}/complete",
            json={"completed_by": "human_root", "note": "too early"},
        )
        approved = self.client.post(
            f"/approvals/{requested.json()['approval']['approval_id']}/approve",
            json={"status": "approved", "decided_by": "human_root", "note": "approved"},
        )
        completed = self.client.post(
            f"/tools/runs/{requested.json()['run']['run_id']}/complete",
            json={"completed_by": "human_root", "note": "run after approval"},
        )
        audit = self.client.get("/audit-logs")

        self.assertEqual(tool.status_code, 200)
        self.assertEqual(agent.status_code, 200)
        self.assertEqual(requested.status_code, 200)
        self.assertEqual(requested.json()["run"]["status"], "waiting_approval")
        self.assertEqual(early.status_code, 400)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["run"]["status"], "completed")
        self.assertEqual(audit.json()[-1]["event_type"], "tool_run_completed")

    def test_model_generate_route_records_usage_and_audit(self):
        response = self.client.post(
            "/models/generate",
            json={
                "prompt": "Draft a short operating summary.",
                "actor_id": "document_agent_v1",
                "purpose": "api_test",
            },
        )
        usage = self.client.get("/model-usage")
        cost_logs = self.client.get("/cost-logs")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(response.status_code, 200)
        self.assertIn("api_test", response.json()["output"])
        self.assertEqual(len(usage.json()), 1)
        self.assertEqual(usage.json()[0]["purpose"], "api_test")
        self.assertEqual(len(cost_logs.json()), 1)
        self.assertEqual(cost_logs.json()[0]["result"], "recorded")
        self.assertFalse(response.json()["blocked"])
        self.assertEqual(audit.json()[-1]["event_type"], "model_called")
        self.assertEqual(dashboard.json()["model_usage_count"], 1)
        self.assertEqual(dashboard.json()["cost_log_count"], 1)

    def test_budget_policy_update_is_audited_and_blocks_future_model_calls(self):
        updated = self.client.post(
            "/budget/policy",
            json={
                "actor_id": "human_root",
                "name": "Strict Test Budget",
                "max_tokens_per_call": 1,
                "max_total_tokens": 10,
                "max_estimated_cost": 1,
                "cost_per_token": 0.000001,
                "currency": "usd",
                "enabled": True,
            },
        )
        blocked = self.client.post(
            "/models/generate",
            json={
                "prompt": "This prompt should exceed one token.",
                "actor_id": "document_agent_v1",
                "purpose": "budget_policy_test",
            },
        )
        audit = self.client.get("/audit-logs")
        budget = self.client.get("/budget/summary")
        incidents = self.client.get("/incidents")

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["policy_name"], "Strict Test Budget")
        self.assertEqual(updated.json()["currency"], "USD")
        self.assertEqual(blocked.status_code, 200)
        self.assertTrue(blocked.json()["blocked"])
        self.assertEqual(blocked.json()["incident"]["status"], "open")
        self.assertEqual(budget.json()["max_tokens_per_call"], 1)
        self.assertEqual(len(incidents.json()), 1)
        self.assertEqual(audit.json()[-2]["event_type"], "budget_policy_updated")
        self.assertEqual(audit.json()[-1]["event_type"], "model_blocked")

    def test_non_root_budget_policy_update_is_blocked_and_incidented(self):
        response = self.client.post(
            "/budget/policy",
            json={
                "actor_id": "ceo_agent_v1",
                "name": "Unauthorized Budget",
                "max_tokens_per_call": 100,
                "max_total_tokens": 1000,
                "max_estimated_cost": 1,
                "cost_per_token": 0.000001,
                "currency": "USD",
                "enabled": True,
            },
        )
        audit = self.client.get("/audit-logs")
        incidents = self.client.get("/incidents")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(incidents.json()), 1)
        self.assertEqual(incidents.json()[0]["title"], "Budget policy update blocked")
        self.assertEqual(audit.json()[-1]["event_type"], "budget_policy_update_blocked")

    def test_blocked_action_creates_and_resolves_incident(self):
        blocked = self.client.post(
            "/approvals/request",
            json={
                "action": "disable_risk_system",
                "actor_id": "ceo_agent_v1",
                "permission_level": "L5_ROOT",
                "reason": "This must become an incident.",
            },
        )
        incidents = self.client.get("/incidents")
        incident_id = incidents.json()[0]["incident_id"]

        acknowledged = self.client.post(
            f"/incidents/{incident_id}/acknowledge",
            json={"actor_id": "human_root", "note": "Seen."},
        )
        resolved = self.client.post(
            f"/incidents/{incident_id}/resolve",
            json={"actor_id": "human_root", "note": "Policy working as intended."},
        )
        dashboard = self.client.get("/dashboard/summary")
        audit = self.client.get("/audit-logs")

        self.assertEqual(blocked.status_code, 200)
        self.assertEqual(blocked.json()["incident"]["status"], "open")
        self.assertEqual(incidents.status_code, 200)
        self.assertEqual(len(incidents.json()), 1)
        self.assertEqual(acknowledged.json()["status"], "acknowledged")
        self.assertEqual(resolved.json()["status"], "resolved")
        self.assertEqual(dashboard.json()["incident_count"], 1)
        self.assertEqual(dashboard.json()["open_incident_count"], 0)
        self.assertEqual(audit.json()[-1]["event_type"], "incident_resolved")

    def test_missing_skill_and_agent_routes_create_disabled_proposals(self):
        skill = self.client.post(
            "/skills/missing",
            json={
                "capability": "Course Outline",
                "requested_by_agent": "document_agent_v1",
                "risk_level": "medium",
            },
        )
        agent = self.client.post(
            "/agents/missing",
            json={
                "role": "Training",
                "department": "Knowledge",
                "repeated_reason": "Training tasks appear repeatedly.",
            },
        )

        self.assertEqual(skill.status_code, 200)
        self.assertEqual(agent.status_code, 200)
        self.assertTrue(skill.json()["requires_approval"])
        self.assertFalse(skill.json()["enabled_by_default"])
        self.assertFalse(agent.json()["enabled_by_default"])
        self.assertEqual(skill.json()["status"], "pending_approval")
        self.assertEqual(agent.json()["status"], "pending_approval")
        self.assertEqual(skill.json()["sandbox_status"], "not_run")
        self.assertEqual(agent.json()["sandbox_status"], "not_run")

    def test_skill_proposal_requires_approval_before_registration(self):
        proposal_response = self.client.post(
            "/skills/missing",
            json={
                "capability": "Course Outline",
                "requested_by_agent": "document_agent_v1",
                "risk_level": "medium",
            },
        )
        proposal = proposal_response.json()

        blocked_register = self.client.post(f"/skills/proposals/{proposal['proposal_id']}/register")
        self.client.post(
            f"/approvals/{proposal['approval_id']}/approve",
            json={"note": "Approve controlled Skill creation."},
        )
        still_blocked_register = self.client.post(f"/skills/proposals/{proposal['proposal_id']}/register")
        sandboxed = self.client.post(f"/skills/proposals/{proposal['proposal_id']}/sandbox")
        registered = self.client.post(f"/skills/proposals/{proposal['proposal_id']}/register")
        skills = self.client.get("/skills")
        audit = self.client.get("/audit-logs")

        self.assertEqual(blocked_register.status_code, 400)
        self.assertEqual(still_blocked_register.status_code, 400)
        self.assertEqual(sandboxed.status_code, 200)
        self.assertEqual(sandboxed.json()["sandbox_status"], "passed")
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["proposal"]["status"], "registered")
        self.assertEqual(registered.json()["proposal"]["sandbox_status"], "passed")
        self.assertEqual(registered.json()["skill"]["skill_id"], "course_outline_skill_v1")
        self.assertIn("course_outline_skill_v1", [skill["skill_id"] for skill in skills.json()])
        self.assertIn("skill_proposal_sandboxed", [event["event_type"] for event in audit.json()])

    def test_agent_proposal_requires_approval_before_registration(self):
        proposal_response = self.client.post(
            "/agents/missing",
            json={
                "role": "Training",
                "department": "Knowledge",
                "repeated_reason": "Training tasks appear repeatedly.",
            },
        )
        proposal = proposal_response.json()

        blocked_register = self.client.post(f"/agents/proposals/{proposal['proposal_id']}/register")
        self.client.post(
            f"/approvals/{proposal['approval_id']}/approve",
            json={"note": "Approve controlled Agent creation."},
        )
        still_blocked_register = self.client.post(f"/agents/proposals/{proposal['proposal_id']}/register")
        sandboxed = self.client.post(f"/agents/proposals/{proposal['proposal_id']}/sandbox")
        registered = self.client.post(f"/agents/proposals/{proposal['proposal_id']}/register")
        agents = self.client.get("/agents")
        audit = self.client.get("/audit-logs")

        self.assertEqual(blocked_register.status_code, 400)
        self.assertEqual(still_blocked_register.status_code, 400)
        self.assertEqual(sandboxed.status_code, 200)
        self.assertEqual(sandboxed.json()["sandbox_status"], "passed")
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["proposal"]["status"], "registered")
        self.assertEqual(registered.json()["proposal"]["sandbox_status"], "passed")
        self.assertEqual(registered.json()["agent"]["agent_id"], "training_agent_v1")
        self.assertIn("training_agent_v1", [agent["agent_id"] for agent in agents.json()])
        self.assertIn("agent_proposal_sandboxed", [event["event_type"] for event in audit.json()])

    def test_register_agent_rejects_root_permission(self):
        response = self.client.post(
            "/agents",
            json={
                "agent_id": "bad_root_agent_v1",
                "name": "Bad Root",
                "department": "Unsafe",
                "role": "Should fail.",
                "permissions": ["L5_ROOT"],
                "risk_level": "high",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("L5_ROOT", response.json()["detail"])

    def test_risk_assess_endpoint_blocks_forbidden_action(self):
        response = self.client.post(
            "/risks/assess",
            json={
                "action": "captcha_bypass",
                "actor_id": "ceo_agent_v1",
                "permission_level": "L4_HIGH_RISK",
                "reason": "Forbidden action check.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["level"], "forbidden")
        self.assertTrue(response.json()["blocked"])

    def test_approval_request_routes_medium_risk_to_pending_and_audit(self):
        response = self.client.post(
            "/approvals/request",
            json={
                "action": "prepare_external_message",
                "actor_id": "ceo_agent_v1",
                "permission_level": "L3_EXTERNAL_PREPARE",
                "reason": "Prepare an external status update for review.",
                "possible_benefit": "User can review the message before sending.",
                "possible_loss": "Message could be inaccurate if sent without approval.",
            },
        )
        approvals = self.client.get("/approvals")
        dashboard = self.client.get("/dashboard/summary")
        audit = self.client.get("/audit-logs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "approval_required")
        self.assertEqual(response.json()["approval"]["status"], "pending")
        self.assertEqual(response.json()["risk"]["level"], "medium")
        self.assertEqual(len(approvals.json()), 1)
        self.assertEqual(dashboard.json()["pending_approval_count"], 1)
        self.assertGreaterEqual(dashboard.json()["recent_risk_count"], 1)
        self.assertEqual(audit.json()[-1]["event_type"], "action_requested")

    def test_approval_decision_writes_audit_event(self):
        created = self.client.post(
            "/approvals/request",
            json={
                "action": "prepare_external_message",
                "actor_id": "ceo_agent_v1",
                "permission_level": "L3_EXTERNAL_PREPARE",
                "reason": "Prepare an external status update for review.",
            },
        )
        approval_id = created.json()["approval"]["approval_id"]

        decided = self.client.post(
            f"/approvals/{approval_id}/approve",
            json={"note": "Approved by Human Root."},
        )
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(decided.status_code, 200)
        self.assertEqual(decided.json()["status"], "approved")
        self.assertEqual(audit.json()[-1]["event_type"], "approval_decided")
        self.assertEqual(audit.json()[-1]["approval_status"], "approved")
        self.assertEqual(dashboard.json()["pending_approval_count"], 0)

    def test_approval_request_blocks_forbidden_action(self):
        response = self.client.post(
            "/approvals/request",
            json={
                "action": "disable_risk_system",
                "actor_id": "ceo_agent_v1",
                "permission_level": "L5_ROOT",
                "reason": "This must be blocked.",
                "possible_loss": "Safety system disabled.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "blocked")
        self.assertEqual(response.json()["approval"]["status"], "blocked")
        self.assertEqual(response.json()["risk"]["level"], "forbidden")

    def test_backup_creation_captures_state_and_audit(self):
        task = self.client.post("/tasks", json={"title": "Backup task", "description": "State to snapshot."})
        created = self.client.post(
            "/backups",
            json={"actor_id": "human_root", "reason": "Checkpoint before major change."},
        )
        backups = self.client.get("/backups")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(task.status_code, 200)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["reason"], "Checkpoint before major change.")
        self.assertEqual(created.json()["snapshot"]["tasks"][0]["task_id"], task.json()["task_id"])
        self.assertEqual(len(created.json()["backup_checksum"]), 64)
        self.assertIn("rollback_plan", created.json())
        verified = self.client.post(
            f"/backups/{created.json()['backup_id']}/verify",
            json={"actor_id": "human_root"},
        )
        audit_after_verify = self.client.get("/audit-logs")

        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["verified"])
        self.assertEqual(verified.json()["status"], "verified")
        self.assertEqual(verified.json()["expected_checksum"], created.json()["backup_checksum"])
        restore_request = self.client.post(
            f"/backups/{created.json()['backup_id']}/restore-request",
            json={"actor_id": "human_root", "reason": "Request controlled restore approval."},
        )
        audit_after_restore_request = self.client.get("/audit-logs")

        self.assertEqual(restore_request.status_code, 200)
        self.assertEqual(restore_request.json()["result"], "approval_required")
        self.assertEqual(restore_request.json()["verification"]["status"], "verified")
        self.assertEqual(restore_request.json()["approval"]["status"], "pending")
        self.assertEqual(restore_request.json()["approval"]["request"]["action"], "restore_backup")
        self.assertEqual(restore_request.json()["risk"]["level"], "high")
        self.assertEqual(backups.status_code, 200)
        self.assertEqual(len(backups.json()), 1)
        self.assertEqual(audit.json()[-1]["event_type"], "backup_created")
        self.assertEqual(audit_after_verify.json()[-1]["event_type"], "backup_verified")
        self.assertEqual(audit_after_restore_request.json()[-1]["event_type"], "action_requested")
        self.assertEqual(dashboard.json()["backup_count"], 1)
        self.assertEqual(len(dashboard.json()["recent_backups"]), 1)

    def test_agent_messages_and_meetings_are_audited_and_listed(self):
        message = self.client.post(
            "/agent-messages",
            json={
                "from_agent": "ceo_agent_v1",
                "to_agent": "document_agent_v1",
                "message_type": "handoff",
                "content": "Prepare the next internal document.",
                "priority": "high",
                "requires_response": True,
            },
        )
        meeting = self.client.post(
            "/agent-meetings",
            json={
                "title": "Document handoff sync",
                "organizer_agent": "ceo_agent_v1",
                "participant_agents": ["ceo_agent_v1", "document_agent_v1", "quality_agent_v1"],
                "agenda": "Align next document step.",
                "minutes": "Document agent owns draft; quality agent reviews.",
            },
        )
        messages = self.client.get("/agent-messages?agent_id=document_agent_v1")
        meetings = self.client.get("/agent-meetings")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(message.status_code, 200)
        self.assertEqual(message.json()["priority"], "high")
        self.assertTrue(message.json()["requires_response"])
        self.assertEqual(meeting.status_code, 200)
        self.assertEqual(len(meeting.json()["participant_agents"]), 3)
        self.assertEqual(len(messages.json()), 1)
        self.assertEqual(messages.json()[0]["message_id"], message.json()["message_id"])
        self.assertEqual(len(meetings.json()), 1)
        self.assertEqual(audit.json()[-2]["event_type"], "agent_message_sent")
        self.assertEqual(audit.json()[-1]["event_type"], "agent_meeting_recorded")
        self.assertEqual(dashboard.json()["agent_message_count"], 1)
        self.assertEqual(dashboard.json()["agent_meeting_count"], 1)
        self.assertEqual(len(dashboard.json()["recent_agent_messages"]), 1)
        self.assertEqual(len(dashboard.json()["recent_agent_meetings"]), 1)

    def test_task_handoff_records_handoff_message_and_audit(self):
        task = self.client.post(
            "/tasks",
            json={"title": "Handoff task", "description": "Needs an owner transfer."},
        )
        handoff = self.client.post(
            f"/tasks/{task.json()['task_id']}/handoff",
            json={
                "from_agent": "project_manager_agent_v1",
                "to_agent": "document_agent_v1",
                "reason": "Document Agent owns drafting.",
                "instructions": "Draft the internal note and prepare for quality review.",
            },
        )
        handoffs = self.client.get(f"/task-handoffs?task_id={task.json()['task_id']}")
        messages = self.client.get(f"/agent-messages?task_id={task.json()['task_id']}")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(task.status_code, 200)
        self.assertEqual(handoff.status_code, 200)
        self.assertEqual(handoff.json()["handoff"]["task_status"], "created")
        self.assertEqual(handoff.json()["message"]["message_type"], "handoff")
        self.assertTrue(handoff.json()["message"]["requires_response"])
        self.assertEqual(len(handoffs.json()), 1)
        self.assertEqual(handoffs.json()[0]["handoff_id"], handoff.json()["handoff"]["handoff_id"])
        self.assertEqual(len(messages.json()), 1)
        self.assertEqual(messages.json()[0]["message_id"], handoff.json()["message"]["message_id"])
        self.assertEqual(audit.json()[-1]["event_type"], "task_handoff_recorded")
        self.assertEqual(dashboard.json()["task_handoff_count"], 1)
        self.assertEqual(dashboard.json()["agent_message_count"], 1)
        self.assertEqual(len(dashboard.json()["recent_task_handoffs"]), 1)

    def test_agent_broadcasts_are_audited_and_filterable(self):
        task = self.client.post(
            "/tasks",
            json={"title": "Broadcast task", "description": "Needs a coordination event."},
        )
        broadcast = self.client.post(
            "/agent-broadcasts",
            json={
                "from_agent": "ceo_agent_v1",
                "audience_agents": ["project_manager_agent_v1", "document_agent_v1"],
                "event_type": "workflow_update",
                "title": "Workflow ready",
                "content": "Coordinate on the next task step.",
                "priority": "high",
                "task_id": task.json()["task_id"],
            },
        )
        by_agent = self.client.get("/agent-broadcasts?agent_id=document_agent_v1")
        by_task = self.client.get(f"/agent-broadcasts?task_id={task.json()['task_id']}")
        by_type = self.client.get("/agent-broadcasts?event_type=workflow_update")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(broadcast.status_code, 200)
        self.assertEqual(broadcast.json()["priority"], "high")
        self.assertEqual(len(broadcast.json()["audience_agents"]), 2)
        self.assertEqual(len(by_agent.json()), 1)
        self.assertEqual(by_agent.json()[0]["broadcast_id"], broadcast.json()["broadcast_id"])
        self.assertEqual(len(by_task.json()), 1)
        self.assertEqual(len(by_type.json()), 1)
        self.assertEqual(audit.json()[-1]["event_type"], "agent_broadcast_sent")
        self.assertEqual(dashboard.json()["agent_broadcast_count"], 1)
        self.assertEqual(len(dashboard.json()["recent_agent_broadcasts"]), 1)

    def test_agent_conflicts_can_be_opened_resolved_and_filtered(self):
        task = self.client.post(
            "/tasks",
            json={"title": "Conflict task", "description": "Needs arbitration."},
        )
        opened = self.client.post(
            "/agent-conflicts",
            json={
                "raised_by_agent": "risk_agent_v1",
                "opposing_agents": ["document_agent_v1"],
                "issue": "Risk review should happen before drafting proceeds.",
                "positions": {
                    "risk_agent_v1": "Pause and complete the risk review.",
                    "document_agent_v1": "Draft first, review before completion.",
                },
                "priority_area": "safety",
                "task_id": task.json()["task_id"],
            },
        )
        by_agent = self.client.get("/agent-conflicts?agent_id=document_agent_v1")
        by_status = self.client.get("/agent-conflicts?status=open")
        resolved = self.client.post(
            f"/agent-conflicts/{opened.json()['conflict_id']}/resolve",
            json={
                "resolved_by": "human_root",
                "selected_position_agent": "risk_agent_v1",
                "resolution": "Safety takes priority; complete risk review first.",
            },
        )
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.json()["status"], "open")
        self.assertEqual(opened.json()["priority_area"], "safety")
        self.assertEqual(len(by_agent.json()), 1)
        self.assertEqual(len(by_status.json()), 1)
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "resolved")
        self.assertEqual(resolved.json()["selected_position_agent"], "risk_agent_v1")
        self.assertEqual(audit.json()[-2]["event_type"], "agent_conflict_opened")
        self.assertEqual(audit.json()[-1]["event_type"], "agent_conflict_resolved")
        self.assertEqual(dashboard.json()["agent_conflict_count"], 1)
        self.assertEqual(dashboard.json()["open_agent_conflict_count"], 0)
        self.assertEqual(len(dashboard.json()["recent_agent_conflicts"]), 1)

    def test_task_reviews_record_memory_knowledge_audit_and_dashboard(self):
        task = self.client.post(
            "/tasks",
            json={"title": "Review task", "description": "Needs retrospective learning."},
        )
        review = self.client.post(
            "/task-reviews",
            json={
                "task_id": task.json()["task_id"],
                "reviewer_agent": "quality_agent_v1",
                "outcome": "needs_followup",
                "summary": "The workflow completed, but follow-up ownership should be clearer.",
                "what_went_well": "Audit and workflow traces were clear.",
                "what_went_wrong": "Follow-up owner was implicit.",
                "lessons": ["Assign follow-up owner", "Keep review criteria explicit"],
                "follow_up_actions": ["Add review owner field"],
                "quality_score": 0.82,
            },
        )
        reviews = self.client.get(f"/task-reviews?task_id={task.json()['task_id']}")
        memory = self.client.get("/memory")
        knowledge = self.client.get("/knowledge")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()["review"]["outcome"], "needs_followup")
        self.assertEqual(review.json()["review"]["quality_score"], 0.82)
        self.assertEqual(review.json()["memory"]["memory_type"], "review")
        self.assertIn("Assign follow-up owner", review.json()["knowledge"]["content"])
        self.assertEqual(len(reviews.json()), 1)
        self.assertEqual(memory.json()[-1]["memory_type"], "review")
        self.assertIn("Review lessons", knowledge.json()[-1]["title"])
        self.assertEqual(audit.json()[-1]["event_type"], "task_review_recorded")
        self.assertEqual(dashboard.json()["task_review_count"], 1)
        self.assertEqual(dashboard.json()["average_review_score"], 0.82)
        self.assertEqual(len(dashboard.json()["recent_task_reviews"]), 1)

    def test_review_improvement_proposal_requires_approval_sandbox_and_registers_knowledge(self):
        task = self.client.post(
            "/tasks",
            json={"title": "Improvement task", "description": "Needs a review-driven improvement."},
        )
        review = self.client.post(
            "/task-reviews",
            json={
                "task_id": task.json()["task_id"],
                "reviewer_agent": "quality_agent_v1",
                "outcome": "needs_followup",
                "summary": "Follow-up ownership was unclear.",
                "what_went_well": "The review captured lessons.",
                "what_went_wrong": "Ownership stayed implicit.",
                "lessons": ["Make review ownership explicit"],
                "follow_up_actions": ["Add owner field to review workflow"],
                "quality_score": 0.76,
            },
        )
        proposal = self.client.post(
            f"/task-reviews/{review.json()['review']['review_id']}/improvements",
            json={
                "proposed_by_agent": "ceo_agent_v1",
                "target_type": "workflow",
                "title": "Add review owner field",
                "description": "Make follow-up ownership explicit in review workflows.",
                "risk_level": "medium",
            },
        )
        blocked_register = self.client.post(
            f"/improvement-proposals/{proposal.json()['proposal_id']}/register"
        )
        sandboxed = self.client.post(
            f"/improvement-proposals/{proposal.json()['proposal_id']}/sandbox"
        )
        self.client.post(
            f"/approvals/{proposal.json()['approval_id']}/approve",
            json={"note": "Approve review-driven improvement."},
        )
        registered = self.client.post(
            f"/improvement-proposals/{proposal.json()['proposal_id']}/register"
        )
        proposals = self.client.get("/improvement-proposals")
        knowledge = self.client.get("/knowledge")
        audit = self.client.get("/audit-logs")
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(proposal.status_code, 200)
        self.assertEqual(proposal.json()["status"], "pending_approval")
        self.assertEqual(proposal.json()["target_type"], "workflow")
        self.assertEqual(blocked_register.status_code, 400)
        self.assertEqual(sandboxed.status_code, 200)
        self.assertEqual(sandboxed.json()["sandbox_status"], "passed")
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["proposal"]["status"], "registered")
        self.assertIn("Add review owner field", registered.json()["knowledge"]["title"])
        self.assertEqual(proposals.json()[0]["status"], "registered")
        self.assertIn("Make review ownership explicit", knowledge.json()[-1]["content"])
        self.assertIn("improvement_proposal_sandboxed", [event["event_type"] for event in audit.json()])
        self.assertEqual(audit.json()[-1]["event_type"], "improvement_registered_from_proposal")
        self.assertEqual(dashboard.json()["improvement_proposal_count"], 1)
        self.assertEqual(len(dashboard.json()["recent_improvement_proposals"]), 1)

    def test_github_absorption_requires_approval_sandbox_and_registers_knowledge(self):
        analyzed = self.client.post(
            "/github/absorptions/analyze",
            json={
                "repo_url": "https://github.com/example/safe-docs",
                "requested_by_agent": "ceo_agent_v1",
                "license_name": "MIT",
                "maintenance_signal": "active",
                "readme": "# Safe Docs\n\nA documentation and API workflow helper with tests.",
            },
        )
        proposal = analyzed.json()
        approved = self.client.post(
            f"/approvals/{proposal['approval_id']}/approve",
            json={"status": "approved", "decided_by": "human_root", "note": "approved"},
        )
        sandboxed = self.client.post(f"/github/absorptions/{proposal['proposal_id']}/sandbox")
        registered = self.client.post(f"/github/absorptions/{proposal['proposal_id']}/register")
        listed = self.client.get("/github/absorptions")
        knowledge = self.client.get("/knowledge")
        dashboard = self.client.get("/dashboard/summary")
        audit = self.client.get("/audit-logs")

        self.assertEqual(analyzed.status_code, 200)
        self.assertEqual(proposal["status"], "pending_approval")
        self.assertEqual(proposal["risk_level"], "low")
        self.assertIn("documentation", proposal["recommended_capabilities"])
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(sandboxed.status_code, 200)
        self.assertEqual(sandboxed.json()["sandbox_status"], "passed")
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["proposal"]["status"], "registered")
        self.assertIn("GitHub absorption analysis", registered.json()["knowledge"]["title"])
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(len(knowledge.json()), 1)
        self.assertEqual(dashboard.json()["github_absorption_count"], 1)
        self.assertIn("github_absorption_registered", [event["event_type"] for event in audit.json()])

    def test_github_absorption_sandbox_blocks_unsafe_repository_signals(self):
        analyzed = self.client.post(
            "/github/absorptions/analyze",
            json={
                "repo_url": "https://github.com/example/unsafe-tool",
                "requested_by_agent": "ceo_agent_v1",
                "license_name": "unknown",
                "maintenance_signal": "unknown",
                "readme": "# Unsafe\n\nTool can execute arbitrary code and steal token data.",
            },
        )
        sandboxed = self.client.post(f"/github/absorptions/{analyzed.json()['proposal_id']}/sandbox")

        self.assertEqual(analyzed.status_code, 200)
        self.assertEqual(analyzed.json()["risk_level"], "high")
        self.assertGreaterEqual(len(analyzed.json()["security_findings"]), 1)
        self.assertEqual(sandboxed.status_code, 200)
        self.assertEqual(sandboxed.json()["sandbox_status"], "failed")

    def test_strategic_goals_track_progress_and_link_operational_records(self):
        goal = self.client.post(
            "/goals",
            json={
                "title": "Ship closed loop modules",
                "description": "Track modules that make the operating system more complete.",
                "owner_agent": "ceo_agent_v1",
                "target_metric": "modules",
                "target_value": 4,
                "current_value": 1,
            },
        )
        task = self.client.post(
            "/tasks",
            json={"title": "Goal linked task", "description": "Work that supports a strategic goal."},
        )
        review = self.client.post(
            "/task-reviews",
            json={
                "task_id": task.json()["task_id"],
                "summary": "The task supports the strategic goal.",
                "lessons": ["Keep goal linkage visible"],
                "follow_up_actions": ["Link reviews to goals"],
                "quality_score": 0.8,
            },
        )
        improvement = self.client.post(
            f"/task-reviews/{review.json()['review']['review_id']}/improvements",
            json={
                "proposed_by_agent": "ceo_agent_v1",
                "target_type": "workflow",
                "title": "Link goals in workflow",
                "description": "Make goal linkage visible in workflow records.",
                "risk_level": "medium",
            },
        )
        linked_task = self.client.post(f"/goals/{goal.json()['goal_id']}/tasks/{task.json()['task_id']}", json={})
        linked_review = self.client.post(
            f"/goals/{goal.json()['goal_id']}/reviews/{review.json()['review']['review_id']}",
            json={},
        )
        linked_improvement = self.client.post(
            f"/goals/{goal.json()['goal_id']}/improvements/{improvement.json()['proposal_id']}",
            json={},
        )
        progress = self.client.post(
            f"/goals/{goal.json()['goal_id']}/progress",
            json={"current_value": 4, "note": "Completed target modules."},
        )
        goals = self.client.get("/goals")
        dashboard = self.client.get("/dashboard/summary")
        audit = self.client.get("/audit-logs")

        self.assertEqual(goal.status_code, 200)
        self.assertEqual(goal.json()["status"], "active")
        self.assertEqual(linked_task.json()["linked_task_ids"], [task.json()["task_id"]])
        self.assertEqual(linked_review.json()["linked_review_ids"], [review.json()["review"]["review_id"]])
        self.assertEqual(linked_improvement.json()["linked_improvement_ids"], [improvement.json()["proposal_id"]])
        self.assertEqual(progress.json()["status"], "completed")
        self.assertEqual(progress.json()["current_value"], 4)
        self.assertEqual(len(goals.json()), 1)
        self.assertEqual(dashboard.json()["strategic_goal_count"], 1)
        self.assertEqual(dashboard.json()["active_strategic_goal_count"], 0)
        self.assertEqual(dashboard.json()["average_goal_progress"], 1.0)
        self.assertEqual(len(dashboard.json()["recent_strategic_goals"]), 1)
        self.assertIn("strategic_goal_created", [event["event_type"] for event in audit.json()])
        self.assertIn("strategic_goal_linked", [event["event_type"] for event in audit.json()])
        self.assertEqual(audit.json()[-1]["event_type"], "strategic_goal_progress_updated")

    def test_dashboard_summary_has_operational_sections(self):
        dashboard = self.client.get("/dashboard/summary")

        self.assertEqual(dashboard.status_code, 200)
        payload = dashboard.json()
        self.assertIn("task_status_counts", payload)
        self.assertIn("approval_status_counts", payload)
        self.assertIn("agent_status_counts", payload)
        self.assertIn("skill_status_counts", payload)
        self.assertIn("skill_risk_counts", payload)
        self.assertIn("recent_tasks", payload)
        self.assertIn("recent_approvals", payload)
        self.assertIn("recent_risks", payload)
        self.assertIn("recent_logs", payload)
        self.assertIn("structured_log_count", payload)
        self.assertIn("recent_structured_logs", payload)
        self.assertIn("integrity_status", payload)
        self.assertIn("integrity_issue_count", payload)
        self.assertIn("integrity_checks", payload)
        self.assertIn("recent_evaluations", payload)
        self.assertIn("recent_tool_runs", payload)
        self.assertIn("recent_workflow_runs", payload)
        self.assertIn("recent_workflow_steps", payload)
        self.assertIn("tool_status_counts", payload)
        self.assertIn("tool_run_status_counts", payload)
        self.assertIn("workflow_run_status_counts", payload)
        self.assertIn("recent_model_usage", payload)
        self.assertIn("model_usage_by_model", payload)
        self.assertIn("recent_cost_logs", payload)
        self.assertIn("cost_log_result_counts", payload)
        self.assertIn("recent_incidents", payload)
        self.assertIn("incident_status_counts", payload)
        self.assertIn("budget_policy_name", payload)
        self.assertIn("budget_policy_enabled", payload)
        self.assertIn("backup_count", payload)
        self.assertIn("recent_backups", payload)
        self.assertIn("agent_message_count", payload)
        self.assertIn("agent_meeting_count", payload)
        self.assertIn("task_handoff_count", payload)
        self.assertIn("agent_broadcast_count", payload)
        self.assertIn("agent_conflict_count", payload)
        self.assertIn("open_agent_conflict_count", payload)
        self.assertIn("task_review_count", payload)
        self.assertIn("average_review_score", payload)
        self.assertIn("improvement_proposal_count", payload)
        self.assertIn("strategic_goal_count", payload)
        self.assertIn("active_strategic_goal_count", payload)
        self.assertIn("average_goal_progress", payload)
        self.assertIn("recent_agent_messages", payload)
        self.assertIn("recent_agent_meetings", payload)
        self.assertIn("recent_task_handoffs", payload)
        self.assertIn("recent_agent_broadcasts", payload)
        self.assertIn("recent_agent_conflicts", payload)
        self.assertIn("recent_task_reviews", payload)
        self.assertIn("recent_improvement_proposals", payload)
        self.assertIn("recent_strategic_goals", payload)
        self.assertEqual(payload["agent_status_counts"]["enabled"], payload["agent_count"])


if __name__ == "__main__":
    unittest.main()
