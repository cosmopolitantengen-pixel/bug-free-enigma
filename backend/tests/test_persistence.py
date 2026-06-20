import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.bootstrap import build_company_os
from app.core.enums import TaskStatus
from app.main import create_app
from app.persistence.sqlite_store import SQLiteStateStore
from app.services.company import CompanyApplicationService


class PersistenceTests(unittest.TestCase):
    def test_sqlite_schema_migration_ledger_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "schema.db")
            store = SQLiteStateStore(db_path)
            reloaded = SQLiteStateStore(db_path)

            self.assertEqual(store.schema_version(), 5)
            self.assertEqual(reloaded.schema_version(), 5)
            self.assertEqual(len(reloaded.list_schema_migrations()), 5)
            self.assertEqual(reloaded.list_schema_migrations()[0]["migration_id"], "0001_initial_local_state")
            self.assertEqual(reloaded.list_schema_migrations()[0]["version"], 1)
            self.assertEqual(reloaded.list_schema_migrations()[1]["migration_id"], "0002_audit_append_only_guards")
            self.assertEqual(reloaded.list_schema_migrations()[1]["version"], 2)
            self.assertEqual(
                reloaded.list_schema_migrations()[2]["migration_id"],
                "0003_backup_restore_execution_ledger",
            )
            self.assertEqual(reloaded.list_schema_migrations()[2]["version"], 3)
            self.assertEqual(
                reloaded.list_schema_migrations()[3]["migration_id"],
                "0004_scheduler_event_bus",
            )
            self.assertEqual(reloaded.list_schema_migrations()[3]["version"], 4)
            self.assertEqual(
                reloaded.list_schema_migrations()[4]["migration_id"],
                "0005_agent_skill_catalogs",
            )
            self.assertEqual(reloaded.list_schema_migrations()[4]["version"], 5)

            with closing(sqlite3.connect(db_path)) as connection:
                user_version = connection.execute("PRAGMA user_version").fetchone()[0]
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                trigger_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                    ).fetchall()
                }

            self.assertEqual(user_version, 5)
            self.assertIn("schema_migrations", table_names)
            self.assertIn("audit_logs", table_names)
            self.assertIn("workflow_runs", table_names)
            self.assertIn("backup_restore_executions", table_names)
            self.assertIn("domain_events", table_names)
            self.assertIn("scheduled_jobs", table_names)
            self.assertIn("scheduled_executions", table_names)
            self.assertIn("agents", table_names)
            self.assertIn("skills", table_names)
            self.assertIn("audit_logs_no_update", trigger_names)
            self.assertIn("audit_logs_no_delete", trigger_names)
            self.assertIn("domain_events_no_update", trigger_names)
            self.assertIn("domain_events_no_delete", trigger_names)

    def test_registered_agent_and_skill_catalogs_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "catalogs.db")
            first = TestClient(create_app(sqlite_path=db_path))
            skill = first.post(
                "/skills",
                json={
                    "skill_id": "training_outline_skill_v1",
                    "name": "Training Outline Skill",
                    "type": "knowledge",
                    "description": "Prepare internal training outlines.",
                    "input_schema": {"topic": "string"},
                    "output_schema": {"outline": "array"},
                    "allowed_agents": ["document_agent_v1"],
                    "risk_level": "low",
                    "requires_approval": False,
                    "enabled": False,
                },
            )
            agent = first.post(
                "/agents",
                json={
                    "agent_id": "training_agent_v1",
                    "name": "Training Agent",
                    "department": "Knowledge",
                    "role": "Prepare internal training material.",
                    "permissions": ["L0_READ", "L1_DRAFT"],
                    "allowed_skills": ["training_outline_skill_v1"],
                    "allowed_tools": ["knowledge_base_tool"],
                    "reports_to": "ceo_agent_v1",
                    "risk_level": "low",
                    "enabled": False,
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            skills = {item["skill_id"]: item for item in second.get("/skills").json()}
            agents = {item["agent_id"]: item for item in second.get("/agents").json()}
            audit_types = [item["event_type"] for item in second.get("/audit-logs").json()]

            self.assertEqual(skill.status_code, 200)
            self.assertEqual(agent.status_code, 200)
            self.assertFalse(skills["training_outline_skill_v1"]["enabled"])
            self.assertFalse(agents["training_agent_v1"]["enabled"])
            self.assertIn("training_agent_v1", skills["training_outline_skill_v1"]["allowed_agents"])
            self.assertIn("training_outline_skill_v1", agents["training_agent_v1"]["allowed_skills"])
            self.assertIn("skill_registered", audit_types)
            self.assertIn("agent_registered", audit_types)

    def test_sqlite_audit_logs_are_append_only_at_database_layer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "audit_guard.db")
            service = CompanyApplicationService(
                company_os=build_company_os(),
                persistence=SQLiteStateStore(db_path),
            )

            task = service.create_task("Guarded audit", "Create an audit record.")
            service.run_task(task["task_id"])
            event_id = service.list_audit_logs()[0]["event_id"]

            with closing(sqlite3.connect(db_path)) as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE audit_logs SET payload_json = ? WHERE event_id = ?",
                        ("{}", event_id),
                    )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("DELETE FROM audit_logs WHERE event_id = ?", (event_id,))

                row_count = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]

            self.assertGreaterEqual(row_count, 7)

    def test_scheduler_events_jobs_and_executions_persist_with_append_only_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "scheduler.db")
            first = TestClient(create_app(sqlite_path=db_path))
            schedule = first.post(
                "/schedules",
                json={
                    "name": "Persistent schedule",
                    "action": "create_task",
                    "payload": {
                        "title": "Persistent scheduled task",
                        "description": "Created through a durable scheduler.",
                    },
                    "next_run_at": "2031-01-01T00:00:00+00:00",
                },
            ).json()
            tick = first.post(
                "/scheduler/tick",
                json={"now": "2031-01-01T00:00:00+00:00"},
            )

            second = TestClient(create_app(sqlite_path=db_path))
            jobs = second.get("/schedules").json()
            executions = second.get("/scheduler/executions").json()
            events = second.get("/events").json()
            tasks = second.get("/tasks").json()

            self.assertEqual(tick.status_code, 200)
            self.assertEqual(jobs[0]["schedule_id"], schedule["schedule_id"])
            self.assertEqual(jobs[0]["status"], "completed")
            self.assertEqual(len(executions), 1)
            self.assertEqual(executions[0]["status"], "completed")
            self.assertEqual(len(events), 2)
            self.assertEqual(len(tasks), 1)

            event_id = events[0]["event_id"]
            with closing(sqlite3.connect(db_path)) as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE domain_events SET payload_json = ? WHERE event_id = ?",
                        ("{}", event_id),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("DELETE FROM domain_events WHERE event_id = ?", (event_id,))

    def test_service_reloads_tasks_audit_memory_and_knowledge_from_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "company_os.db")
            store = SQLiteStateStore(db_path)
            service = CompanyApplicationService(company_os=build_company_os(), persistence=store)

            task = service.create_task("Persistent task", "Verify local SQLite persistence.")
            service.run_task(task["task_id"])

            reloaded = CompanyApplicationService(
                company_os=build_company_os(),
                persistence=SQLiteStateStore(db_path),
            )

            self.assertEqual(len(reloaded.list_tasks()), 1)
            self.assertEqual(reloaded.list_tasks()[0]["status"], TaskStatus.COMPLETED.value)
            self.assertGreaterEqual(len(reloaded.list_audit_logs()), 7)
            self.assertEqual(len(reloaded.list_memory()), 1)
            self.assertEqual(len(reloaded.list_knowledge()), 1)
            self.assertEqual(len(reloaded.list_evaluations()), 3)
            self.assertGreaterEqual(len(reloaded.list_tools()), 5)
            self.assertEqual(len(reloaded.list_workflow_runs()), 1)
            self.assertEqual(len(reloaded.list_workflow_steps()), 7)
            self.assertEqual(len(reloaded.list_model_usage()), 1)
            self.assertEqual(len(reloaded.list_cost_logs()), 1)
            self.assertEqual(len(reloaded.list_incidents()), 0)

    def test_task_planning_workflow_traces_memory_and_evaluation_persist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "task_planning.db")
            first = TestClient(create_app(sqlite_path=db_path))
            planned = first.post(
                "/workflows/run",
                json={
                    "workflow_id": "task_planning_v1",
                    "title": "Persistent plan",
                    "description": "Retain planning controls across restart.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            tasks = second.get("/tasks").json()
            runs = second.get("/workflow-runs").json()
            steps = second.get(f"/workflow-runs/{runs[0]['run_id']}/steps").json()
            memory = second.get("/memory").json()
            evaluations = second.get("/evaluations").json()

            self.assertEqual(planned.status_code, 200)
            self.assertEqual(tasks[0]["status"], "planned")
            self.assertEqual(runs[0]["workflow_id"], "task_planning_v1")
            self.assertEqual(runs[0]["status"], "completed")
            self.assertEqual(len(steps), 3)
            self.assertEqual(memory[0]["memory_type"], "plan")
            self.assertEqual(evaluations[0]["subject_id"], "task_planning_v1")

    def test_incidents_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "incidents.db")
            first = TestClient(create_app(sqlite_path=db_path))
            first.post(
                "/approvals/request",
                json={
                    "action": "disable_risk_system",
                    "actor_id": "ceo_agent_v1",
                    "permission_level": "L5_ROOT",
                    "reason": "Persist blocked incident.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            incidents = second.get("/incidents")
            dashboard = second.get("/dashboard/summary")

            self.assertEqual(incidents.status_code, 200)
            self.assertEqual(len(incidents.json()), 1)
            self.assertEqual(incidents.json()[0]["status"], "open")
            self.assertEqual(dashboard.json()["open_incident_count"], 1)

    def test_backups_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "backups.db")
            first = TestClient(create_app(sqlite_path=db_path))
            task = first.post("/tasks", json={"title": "Snapshot task", "description": "Persist backup snapshot."})
            created = first.post(
                "/backups",
                json={"actor_id": "human_root", "reason": "Persist backup."},
            )

            second = TestClient(create_app(sqlite_path=db_path))
            backups = second.get("/backups")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(created.status_code, 200)
            self.assertEqual(backups.status_code, 200)
            self.assertEqual(len(backups.json()), 1)
            self.assertEqual(backups.json()[0]["backup_id"], created.json()["backup_id"])
            self.assertEqual(backups.json()[0]["snapshot"]["tasks"][0]["task_id"], task.json()["task_id"])
            self.assertEqual(backups.json()[0]["backup_checksum"], created.json()["backup_checksum"])
            self.assertEqual(dashboard.json()["backup_count"], 1)
            self.assertEqual(audit_logs.json()[-1]["event_type"], "backup_created")

    def test_backup_verification_detects_snapshot_tampering_after_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "backup_integrity.db")
            first = TestClient(create_app(sqlite_path=db_path))
            first.post("/tasks", json={"title": "Integrity task", "description": "Back up and verify."})
            backup = first.post(
                "/backups",
                json={"actor_id": "human_root", "reason": "Integrity checkpoint."},
            ).json()
            tampered_payload = dict(backup)
            tampered_payload["snapshot"] = dict(tampered_payload["snapshot"])
            tampered_payload["snapshot"]["tasks"] = []

            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "UPDATE backups SET payload_json = ? WHERE backup_id = ?",
                    (json.dumps(tampered_payload, ensure_ascii=False, sort_keys=True), backup["backup_id"]),
                )
                connection.commit()

            second = TestClient(create_app(sqlite_path=db_path))
            verified = second.post(
                f"/backups/{backup['backup_id']}/verify",
                json={"actor_id": "human_root"},
            )
            restore_request = second.post(
                f"/backups/{backup['backup_id']}/restore-request",
                json={"actor_id": "human_root", "reason": "Try restoring tampered backup."},
            )
            audit_logs = second.get("/audit-logs")
            incidents = second.get("/incidents")

            self.assertEqual(verified.status_code, 200)
            self.assertFalse(verified.json()["verified"])
            self.assertEqual(verified.json()["status"], "checksum_mismatch")
            self.assertNotEqual(verified.json()["expected_checksum"], verified.json()["actual_checksum"])
            self.assertEqual(restore_request.status_code, 200)
            self.assertEqual(restore_request.json()["result"], "blocked")
            self.assertEqual(restore_request.json()["verification"]["status"], "checksum_mismatch")
            self.assertIsNone(restore_request.json()["approval"])
            self.assertEqual(len(incidents.json()), 1)
            self.assertEqual(audit_logs.json()[-1]["event_type"], "backup_restore_request_blocked")
            self.assertEqual(audit_logs.json()[-1]["result"], "checksum_mismatch")

    def test_approved_backup_restore_replaces_business_state_and_preserves_control_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "restore.db")
            client = TestClient(create_app(sqlite_path=db_path))
            original_task = client.post(
                "/tasks",
                json={"title": "Snapshot task", "description": "Keep this task after restore."},
            ).json()
            backup = client.post(
                "/backups",
                json={"actor_id": "human_root", "reason": "Restore target."},
            ).json()
            later_schedule = client.post(
                "/schedules",
                json={
                    "name": "Post-backup schedule",
                    "action": "create_task",
                    "payload": {"title": "Later", "description": "Remove schedule on restore."},
                    "next_run_at": "2032-01-01T00:00:00+00:00",
                },
            ).json()
            later_skill = client.post(
                "/skills",
                json={
                    "skill_id": "post_backup_skill_v1",
                    "name": "Post Backup Skill",
                    "type": "test",
                    "description": "This catalog entry must be removed by restore.",
                    "allowed_agents": ["document_agent_v1"],
                    "risk_level": "low",
                    "requires_approval": False,
                    "enabled": False,
                },
            ).json()
            later_agent = client.post(
                "/agents",
                json={
                    "agent_id": "post_backup_agent_v1",
                    "name": "Post Backup Agent",
                    "department": "Test",
                    "role": "This catalog entry must be removed by restore.",
                    "permissions": ["L0_READ"],
                    "allowed_skills": [later_skill["skill_id"]],
                    "reports_to": "ceo_agent_v1",
                    "risk_level": "low",
                    "enabled": False,
                },
            ).json()
            later_task = client.post(
                "/tasks",
                json={"title": "Later task", "description": "Remove this task during restore."},
            ).json()
            client.post(f"/tasks/{later_task['task_id']}/run")
            audit_count_before_restore = len(client.get("/audit-logs").json())

            requested = client.post(
                f"/backups/{backup['backup_id']}/restore-request",
                json={"actor_id": "human_root", "reason": "Return to the verified checkpoint."},
            ).json()
            approval_id = requested["approval"]["approval_id"]
            approved = client.post(
                f"/approvals/{approval_id}/approve",
                json={"decided_by": "human_root", "note": "Approved for controlled restore."},
            )
            restored = client.post(
                f"/backups/{backup['backup_id']}/restore",
                json={
                    "approval_id": approval_id,
                    "actor_id": "human_root",
                    "reason": "Apply the approved checkpoint.",
                },
            )

            self.assertEqual(approved.status_code, 200)
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()["result"], "restored")
            self.assertEqual(restored.json()["restored_counts"]["tasks"], 1)
            self.assertEqual(restored.json()["restored_counts"]["memory"], 0)
            self.assertEqual(restored.json()["restored_counts"]["agents"], 17)
            self.assertEqual(restored.json()["restored_counts"]["skills"], 18)
            self.assertEqual(restored.json()["verification"]["status"], "verified")
            self.assertIn(later_task["task_id"], [
                task["task_id"]
                for task in restored.json()["safety_backup"]["snapshot"]["tasks"]
            ])
            self.assertIn(later_schedule["schedule_id"], [
                job["schedule_id"]
                for job in restored.json()["safety_backup"]["snapshot"]["scheduled_jobs"]
            ])
            self.assertIn(later_agent["agent_id"], [
                agent["agent_id"]
                for agent in restored.json()["safety_backup"]["snapshot"]["agents"]
            ])
            self.assertIn(later_skill["skill_id"], [
                skill["skill_id"]
                for skill in restored.json()["safety_backup"]["snapshot"]["skills"]
            ])

            reloaded = TestClient(create_app(sqlite_path=db_path))
            tasks = reloaded.get("/tasks").json()
            approvals = reloaded.get("/approvals").json()
            audit_logs = reloaded.get("/audit-logs").json()
            backups = reloaded.get("/backups").json()

            self.assertEqual([task["task_id"] for task in tasks], [original_task["task_id"]])
            self.assertEqual(reloaded.get("/memory").json(), [])
            self.assertEqual(reloaded.get("/knowledge").json(), [])
            self.assertEqual(reloaded.get("/schedules").json(), [])
            self.assertNotIn(later_agent["agent_id"], [
                agent["agent_id"] for agent in reloaded.get("/agents").json()
            ])
            self.assertNotIn(later_skill["skill_id"], [
                skill["skill_id"] for skill in reloaded.get("/skills").json()
            ])
            self.assertEqual(len(backups), 2)
            self.assertIn(approval_id, [approval["approval_id"] for approval in approvals])
            self.assertGreater(len(audit_logs), audit_count_before_restore)
            self.assertEqual(audit_logs[-1]["event_type"], "backup_restored")
            self.assertEqual(audit_logs[-1]["input_ref"], approval_id)

            with closing(sqlite3.connect(db_path)) as connection:
                restore_ledger = connection.execute(
                    "SELECT approval_id, backup_id, safety_backup_id "
                    "FROM backup_restore_executions"
                ).fetchall()
            self.assertEqual(len(restore_ledger), 1)
            self.assertEqual(restore_ledger[0][0], approval_id)
            self.assertEqual(restore_ledger[0][1], backup["backup_id"])
            self.assertEqual(
                restore_ledger[0][2],
                restored.json()["safety_backup"]["backup_id"],
            )

            replay = reloaded.post(
                f"/backups/{backup['backup_id']}/restore",
                json={
                    "approval_id": approval_id,
                    "actor_id": "human_root",
                    "reason": "Do not allow approval replay.",
                },
            )
            self.assertEqual(replay.status_code, 400)
            self.assertIn("already been used", replay.json()["detail"])

    def test_backup_restore_rechecks_integrity_after_approval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "restore_recheck.db")
            client = TestClient(create_app(sqlite_path=db_path))
            client.post("/tasks", json={"title": "Protected", "description": "Remain live."})
            backup = client.post(
                "/backups",
                json={"actor_id": "human_root", "reason": "Integrity target."},
            ).json()
            requested = client.post(
                f"/backups/{backup['backup_id']}/restore-request",
                json={"actor_id": "human_root", "reason": "Request before tampering."},
            ).json()
            approval_id = requested["approval"]["approval_id"]
            client.post(
                f"/approvals/{approval_id}/approve",
                json={"decided_by": "human_root", "note": "Approved before recheck."},
            )

            tampered_payload = dict(backup)
            tampered_payload["snapshot"] = dict(tampered_payload["snapshot"])
            tampered_payload["snapshot"]["tasks"] = []
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "UPDATE backups SET payload_json = ? WHERE backup_id = ?",
                    (json.dumps(tampered_payload, ensure_ascii=False, sort_keys=True), backup["backup_id"]),
                )
                connection.commit()

            reloaded = TestClient(create_app(sqlite_path=db_path))
            blocked = reloaded.post(
                f"/backups/{backup['backup_id']}/restore",
                json={
                    "approval_id": approval_id,
                    "actor_id": "human_root",
                    "reason": "Execution must recheck integrity.",
                },
            )

            self.assertEqual(blocked.status_code, 200)
            self.assertEqual(blocked.json()["result"], "blocked")
            self.assertEqual(blocked.json()["verification"]["status"], "checksum_mismatch")
            self.assertIsNone(blocked.json()["safety_backup"])
            self.assertEqual(len(reloaded.get("/tasks").json()), 1)
            self.assertEqual(reloaded.get("/audit-logs").json()[-1]["event_type"], "backup_restore_execution_blocked")
            self.assertEqual(len(reloaded.get("/incidents").json()), 1)

    def test_agent_communication_persists_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "communication.db")
            first = TestClient(create_app(sqlite_path=db_path))
            message = first.post(
                "/agent-messages",
                json={
                    "from_agent": "ceo_agent_v1",
                    "to_agent": "document_agent_v1",
                    "message_type": "handoff",
                    "content": "Persist this internal handoff.",
                    "requires_response": True,
                },
            )
            meeting = first.post(
                "/agent-meetings",
                json={
                    "title": "Persistent coordination",
                    "organizer_agent": "ceo_agent_v1",
                    "participant_agents": ["ceo_agent_v1", "document_agent_v1"],
                    "agenda": "Persist this coordination record.",
                    "minutes": "Both agents aligned.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            messages = second.get("/agent-messages")
            meetings = second.get("/agent-meetings")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(message.status_code, 200)
            self.assertEqual(meeting.status_code, 200)
            self.assertEqual(len(messages.json()), 1)
            self.assertEqual(messages.json()[0]["message_id"], message.json()["message_id"])
            self.assertEqual(len(meetings.json()), 1)
            self.assertEqual(meetings.json()[0]["meeting_id"], meeting.json()["meeting_id"])
            self.assertEqual(dashboard.json()["agent_message_count"], 1)
            self.assertEqual(dashboard.json()["agent_meeting_count"], 1)
            self.assertIn("agent_message_sent", [event["event_type"] for event in audit_logs.json()])
            self.assertIn("agent_meeting_recorded", [event["event_type"] for event in audit_logs.json()])

    def test_task_handoffs_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "task_handoffs.db")
            first = TestClient(create_app(sqlite_path=db_path))
            task = first.post(
                "/tasks",
                json={"title": "Persistent handoff task", "description": "Persist handoff history."},
            )
            handoff = first.post(
                f"/tasks/{task.json()['task_id']}/handoff",
                json={
                    "from_agent": "project_manager_agent_v1",
                    "to_agent": "document_agent_v1",
                    "reason": "Persist this ownership transfer.",
                    "instructions": "Carry the task into document drafting.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            handoffs = second.get("/task-handoffs")
            messages = second.get("/agent-messages")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(handoff.status_code, 200)
            self.assertEqual(len(handoffs.json()), 1)
            self.assertEqual(handoffs.json()[0]["handoff_id"], handoff.json()["handoff"]["handoff_id"])
            self.assertEqual(len(messages.json()), 1)
            self.assertEqual(messages.json()[0]["message_type"], "handoff")
            self.assertEqual(dashboard.json()["task_handoff_count"], 1)
            self.assertEqual(dashboard.json()["agent_message_count"], 1)
            self.assertEqual(audit_logs.json()[-1]["event_type"], "task_handoff_recorded")

    def test_agent_broadcasts_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "agent_broadcasts.db")
            first = TestClient(create_app(sqlite_path=db_path))
            created = first.post(
                "/agent-broadcasts",
                json={
                    "from_agent": "ceo_agent_v1",
                    "audience_agents": ["project_manager_agent_v1", "document_agent_v1"],
                    "event_type": "workflow_update",
                    "title": "Persistent broadcast",
                    "content": "Persist this internal event.",
                    "priority": "high",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            broadcasts = second.get("/agent-broadcasts")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(created.status_code, 200)
            self.assertEqual(len(broadcasts.json()), 1)
            self.assertEqual(broadcasts.json()[0]["broadcast_id"], created.json()["broadcast_id"])
            self.assertEqual(broadcasts.json()[0]["event_type"], "workflow_update")
            self.assertEqual(dashboard.json()["agent_broadcast_count"], 1)
            self.assertEqual(audit_logs.json()[-1]["event_type"], "agent_broadcast_sent")

    def test_agent_conflicts_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "agent_conflicts.db")
            first = TestClient(create_app(sqlite_path=db_path))
            opened = first.post(
                "/agent-conflicts",
                json={
                    "raised_by_agent": "risk_agent_v1",
                    "opposing_agents": ["document_agent_v1"],
                    "issue": "Risk review should happen before drafting proceeds.",
                    "positions": {
                        "risk_agent_v1": "Pause and complete risk review.",
                        "document_agent_v1": "Draft first, review before completion.",
                    },
                    "priority_area": "safety",
                },
            )
            first.post(
                f"/agent-conflicts/{opened.json()['conflict_id']}/resolve",
                json={
                    "resolved_by": "human_root",
                    "selected_position_agent": "risk_agent_v1",
                    "resolution": "Risk review must happen first.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            conflicts = second.get("/agent-conflicts")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(opened.status_code, 200)
            self.assertEqual(len(conflicts.json()), 1)
            self.assertEqual(conflicts.json()[0]["conflict_id"], opened.json()["conflict_id"])
            self.assertEqual(conflicts.json()[0]["status"], "resolved")
            self.assertEqual(conflicts.json()[0]["resolved_by"], "human_root")
            self.assertEqual(dashboard.json()["agent_conflict_count"], 1)
            self.assertEqual(dashboard.json()["open_agent_conflict_count"], 0)
            self.assertEqual(audit_logs.json()[-1]["event_type"], "agent_conflict_resolved")

    def test_task_reviews_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "task_reviews.db")
            first = TestClient(create_app(sqlite_path=db_path))
            task = first.post(
                "/tasks",
                json={"title": "Persistent review task", "description": "Persist review learning."},
            )
            created = first.post(
                "/task-reviews",
                json={
                    "task_id": task.json()["task_id"],
                    "reviewer_agent": "quality_agent_v1",
                    "outcome": "reviewed",
                    "summary": "Persist this retrospective.",
                    "what_went_well": "Clear audit trail.",
                    "what_went_wrong": "Follow-up action was manual.",
                    "lessons": ["Persist review lessons"],
                    "follow_up_actions": ["Add checklist"],
                    "quality_score": 0.91,
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            reviews = second.get("/task-reviews")
            memory = second.get("/memory")
            knowledge = second.get("/knowledge")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(created.status_code, 200)
            self.assertEqual(len(reviews.json()), 1)
            self.assertEqual(reviews.json()[0]["review_id"], created.json()["review"]["review_id"])
            self.assertEqual(reviews.json()[0]["quality_score"], 0.91)
            self.assertEqual(memory.json()[-1]["memory_type"], "review")
            self.assertIn("Review lessons", knowledge.json()[-1]["title"])
            self.assertEqual(dashboard.json()["task_review_count"], 1)
            self.assertEqual(dashboard.json()["average_review_score"], 0.91)
            self.assertEqual(audit_logs.json()[-1]["event_type"], "task_review_recorded")

    def test_improvement_proposals_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "improvement_proposals.db")
            first = TestClient(create_app(sqlite_path=db_path))
            task = first.post(
                "/tasks",
                json={"title": "Persistent improvement task", "description": "Persist improvement proposal."},
            )
            review = first.post(
                "/task-reviews",
                json={
                    "task_id": task.json()["task_id"],
                    "reviewer_agent": "quality_agent_v1",
                    "outcome": "reviewed",
                    "summary": "Persist improvement source review.",
                    "lessons": ["Persist improvement proposal"],
                    "follow_up_actions": ["Reload proposal after restart"],
                    "quality_score": 0.88,
                },
            )
            proposal = first.post(
                f"/task-reviews/{review.json()['review']['review_id']}/improvements",
                json={
                    "proposed_by_agent": "ceo_agent_v1",
                    "target_type": "workflow",
                    "title": "Persistent improvement",
                    "description": "Persist this review-driven improvement.",
                    "risk_level": "medium",
                },
            )
            first.post(f"/improvement-proposals/{proposal.json()['proposal_id']}/sandbox")

            second = TestClient(create_app(sqlite_path=db_path))
            proposals = second.get("/improvement-proposals")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(proposal.status_code, 200)
            self.assertEqual(len(proposals.json()), 1)
            self.assertEqual(proposals.json()[0]["proposal_id"], proposal.json()["proposal_id"])
            self.assertEqual(proposals.json()[0]["status"], "pending_approval")
            self.assertEqual(proposals.json()[0]["sandbox_status"], "passed")
            self.assertEqual(dashboard.json()["improvement_proposal_count"], 1)
            self.assertIn("improvement_proposal_sandboxed", [event["event_type"] for event in audit_logs.json()])

    def test_strategic_goals_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "strategic_goals.db")
            first = TestClient(create_app(sqlite_path=db_path))
            goal = first.post(
                "/goals",
                json={
                    "title": "Persistent strategic goal",
                    "description": "Persist operating goal and links.",
                    "owner_agent": "ceo_agent_v1",
                    "target_metric": "modules",
                    "target_value": 2,
                    "current_value": 1,
                },
            )
            task = first.post(
                "/tasks",
                json={"title": "Persistent goal task", "description": "Persist linked task."},
            )
            first.post(f"/goals/{goal.json()['goal_id']}/tasks/{task.json()['task_id']}", json={})
            first.post(
                f"/goals/{goal.json()['goal_id']}/progress",
                json={"current_value": 2, "note": "Complete persisted goal."},
            )

            second = TestClient(create_app(sqlite_path=db_path))
            goals = second.get("/goals")
            dashboard = second.get("/dashboard/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(goal.status_code, 200)
            self.assertEqual(len(goals.json()), 1)
            self.assertEqual(goals.json()[0]["goal_id"], goal.json()["goal_id"])
            self.assertEqual(goals.json()[0]["status"], "completed")
            self.assertEqual(goals.json()[0]["linked_task_ids"], [task.json()["task_id"]])
            self.assertEqual(dashboard.json()["strategic_goal_count"], 1)
            self.assertEqual(dashboard.json()["average_goal_progress"], 1.0)
            self.assertIn("strategic_goal_created", [event["event_type"] for event in audit_logs.json()])
            self.assertEqual(audit_logs.json()[-1]["event_type"], "strategic_goal_progress_updated")

    def test_budget_policy_persists_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "budget_policy.db")
            first = TestClient(create_app(sqlite_path=db_path))
            first.post(
                "/budget/policy",
                json={
                    "actor_id": "human_root",
                    "name": "Persistent Budget",
                    "max_tokens_per_call": 77,
                    "max_total_tokens": 7700,
                    "max_estimated_cost": 3.25,
                    "cost_per_token": 0.000002,
                    "currency": "eur",
                    "enabled": True,
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            budget = second.get("/budget/summary")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(budget.status_code, 200)
            self.assertEqual(budget.json()["policy_name"], "Persistent Budget")
            self.assertEqual(budget.json()["max_tokens_per_call"], 77)
            self.assertEqual(budget.json()["max_total_tokens"], 7700)
            self.assertEqual(budget.json()["currency"], "EUR")
            self.assertEqual(audit_logs.json()[-1]["event_type"], "budget_policy_updated")

    def test_tool_runs_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "tool_runs.db")
            first = TestClient(create_app(sqlite_path=db_path))
            created = first.post(
                "/tools/runs/request",
                json={
                    "tool_id": "task_manager_tool",
                    "actor_id": "ceo_agent_v1",
                    "input": {"operation": "inspect"},
                    "reason": "Persist a tool run.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            runs = second.get("/tools/runs")
            tools = second.get("/tools")

            self.assertEqual(created.status_code, 200)
            self.assertEqual(runs.status_code, 200)
            self.assertEqual(len(runs.json()), 1)
            self.assertEqual(runs.json()[0]["status"], "completed")
            self.assertIn("task_count", json.loads(runs.json()[0]["result"]))
            self.assertGreaterEqual(len(tools.json()), 5)

    def test_github_absorptions_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "github_absorptions.db")
            first = TestClient(create_app(sqlite_path=db_path))
            analyzed = first.post(
                "/github/absorptions/analyze",
                json={
                    "repo_url": "https://github.com/example/safe-docs",
                    "requested_by_agent": "ceo_agent_v1",
                    "license_name": "MIT",
                    "maintenance_signal": "active",
                    "readme": "# Safe Docs\n\nA documentation helper with tests.",
                },
            )
            first.post(
                f"/approvals/{analyzed.json()['approval_id']}/approve",
                json={"status": "approved", "decided_by": "human_root", "note": "approved"},
            )
            first.post(f"/github/absorptions/{analyzed.json()['proposal_id']}/sandbox")
            first.post(f"/github/absorptions/{analyzed.json()['proposal_id']}/register")

            second = TestClient(create_app(sqlite_path=db_path))
            absorptions = second.get("/github/absorptions")
            knowledge = second.get("/knowledge")
            dashboard = second.get("/dashboard/summary")

            self.assertEqual(analyzed.status_code, 200)
            self.assertEqual(absorptions.status_code, 200)
            self.assertEqual(len(absorptions.json()), 1)
            self.assertEqual(absorptions.json()[0]["status"], "registered")
            self.assertEqual(absorptions.json()[0]["sandbox_status"], "passed")
            self.assertEqual(len(knowledge.json()), 1)
            self.assertEqual(dashboard.json()["github_absorption_count"], 1)

    def test_fastapi_app_reloads_state_from_same_sqlite_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "company_os_api.db")
            first_client = TestClient(create_app(sqlite_path=db_path))

            created = first_client.post(
                "/tasks",
                json={"title": "Persistent API task", "description": "Persist through app recreation."},
            )
            task_id = created.json()["task_id"]
            first_client.post(f"/tasks/{task_id}/run")

            second_client = TestClient(create_app(sqlite_path=db_path))
            tasks = second_client.get("/tasks")
            audit_logs = second_client.get("/audit-logs")
            evaluations = second_client.get("/evaluations")
            workflow_runs = second_client.get("/workflow-runs")
            model_usage = second_client.get("/model-usage")
            cost_logs = second_client.get("/cost-logs")

            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(len(tasks.json()), 1)
            self.assertEqual(tasks.json()[0]["task_id"], task_id)
            self.assertEqual(tasks.json()[0]["status"], "completed")
            self.assertGreaterEqual(len(audit_logs.json()), 7)
            self.assertEqual(len(evaluations.json()), 3)
            self.assertEqual(len(workflow_runs.json()), 1)
            self.assertEqual(workflow_runs.json()[0]["status"], "completed")
            self.assertEqual(len(model_usage.json()), 1)
            self.assertEqual(len(cost_logs.json()), 1)

    def test_model_usage_persists_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "model_usage.db")
            first = TestClient(create_app(sqlite_path=db_path))
            created = first.post(
                "/models/generate",
                json={
                    "prompt": "Create a model usage record.",
                    "actor_id": "document_agent_v1",
                    "purpose": "persistence_test",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            usage = second.get("/model-usage")
            cost_logs = second.get("/cost-logs")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(created.status_code, 200)
            self.assertEqual(len(usage.json()), 1)
            self.assertEqual(usage.json()[0]["purpose"], "persistence_test")
            self.assertEqual(len(cost_logs.json()), 1)
            self.assertEqual(cost_logs.json()[0]["result"], "recorded")
            self.assertEqual(audit_logs.json()[-1]["event_type"], "model_called")

    def test_approval_requests_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "approvals.db")
            first = TestClient(create_app(sqlite_path=db_path))
            created = first.post(
                "/approvals/request",
                json={
                    "action": "prepare_external_content",
                    "actor_id": "ceo_agent_v1",
                    "permission_level": "L3_EXTERNAL_PREPARE",
                    "reason": "Prepare draft content for external review.",
                },
            )

            second = TestClient(create_app(sqlite_path=db_path))
            approvals = second.get("/approvals")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(created.status_code, 200)
            self.assertEqual(created.json()["approval"]["status"], "pending")
            self.assertEqual(len(approvals.json()), 1)
            self.assertEqual(approvals.json()[0]["status"], "pending")
            self.assertEqual(audit_logs.json()[-1]["event_type"], "action_requested")

    def test_approval_decisions_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "approval_decisions.db")
            first = TestClient(create_app(sqlite_path=db_path))
            created = first.post(
                "/approvals/request",
                json={
                    "action": "prepare_external_content",
                    "actor_id": "ceo_agent_v1",
                    "permission_level": "L3_EXTERNAL_PREPARE",
                    "reason": "Prepare draft content for external review.",
                },
            )
            approval_id = created.json()["approval"]["approval_id"]
            first.post(
                f"/approvals/{approval_id}/reject",
                json={"note": "Rejected by Human Root."},
            )

            second = TestClient(create_app(sqlite_path=db_path))
            approvals = second.get("/approvals")
            audit_logs = second.get("/audit-logs")

            self.assertEqual(approvals.json()[0]["status"], "rejected")
            self.assertEqual(audit_logs.json()[-1]["event_type"], "approval_decided")
            self.assertEqual(audit_logs.json()[-1]["approval_status"], "rejected")

    def test_skill_and_agent_proposals_persist_through_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "proposals.db")
            first = TestClient(create_app(sqlite_path=db_path))
            skill = first.post(
                "/skills/missing",
                json={
                    "capability": "Quiz Generator",
                    "requested_by_agent": "document_agent_v1",
                    "risk_level": "medium",
                },
            ).json()
            agent = first.post(
                "/agents/missing",
                json={
                    "role": "Training",
                    "department": "Knowledge",
                    "repeated_reason": "Training tasks appear repeatedly.",
                },
            ).json()
            first.post(f"/skills/proposals/{skill['proposal_id']}/sandbox")
            first.post(f"/agents/proposals/{agent['proposal_id']}/sandbox")

            second = TestClient(create_app(sqlite_path=db_path))
            skills = second.get("/skills/proposals").json()
            agents = second.get("/agents/proposals").json()
            audit_logs = second.get("/audit-logs").json()

            self.assertEqual(skills[0]["proposal_id"], skill["proposal_id"])
            self.assertEqual(skills[0]["status"], "pending_approval")
            self.assertEqual(skills[0]["sandbox_status"], "passed")
            self.assertEqual(agents[0]["proposal_id"], agent["proposal_id"])
            self.assertEqual(agents[0]["status"], "pending_approval")
            self.assertEqual(agents[0]["sandbox_status"], "passed")
            self.assertIn("skill_proposal_sandboxed", [event["event_type"] for event in audit_logs])
            self.assertIn("agent_proposal_sandboxed", [event["event_type"] for event in audit_logs])


if __name__ == "__main__":
    unittest.main()
