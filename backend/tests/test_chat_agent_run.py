import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.bootstrap import build_company_os
from app.chat.agent_loop import build_agent_run_prompt, parse_agent_run_decision
from app.core.enums import ApprovalStatus
from app.models.gateway import ModelGateway
from app.models.providers import ProviderGeneration
from app.persistence.sqlite_store import SQLiteStateStore
from app.services.company import CompanyApplicationService


def decision(intent: str, **values) -> str:
    payload = {
        "intent": intent,
        "path": None,
        "query": None,
        "old_text": None,
        "new_text": None,
        "expected_sha256": None,
        "answer": None,
    }
    payload.update(values)
    return json.dumps(payload, ensure_ascii=False)


class _QueuedAgentProvider:
    name = "agenttest"
    default_model = "agenttest-v1"

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def generate(self, prompt: str, model_name: str, purpose: str, max_output_tokens: int) -> ProviderGeneration:
        self.prompts.append(prompt)
        if purpose != "chat_agent_next_action":
            raise AssertionError(f"unexpected model purpose: {purpose}")
        if not self.outputs:
            raise AssertionError("agent provider output queue is empty")
        return ProviderGeneration(self.outputs.pop(0), 20, 10, 30)


def service_with_provider(
    provider: _QueuedAgentProvider,
    store: SQLiteStateStore | None = None,
) -> CompanyApplicationService:
    gateway = ModelGateway(
        providers={"agenttest": provider},
        default_provider="agenttest",
    )
    return CompanyApplicationService(
        company_os=build_company_os(model_gateway=gateway),
        persistence=store,
    )


class ChatAgentRunTests(unittest.TestCase):
    def test_parser_accepts_only_bounded_agent_decisions(self):
        parsed = parse_agent_run_decision(
            decision("search_code", path="backend", query="respond_to_chat")
        )

        self.assertEqual(parsed.intent, "search_code")
        self.assertEqual(parsed.path, "backend")
        self.assertIsNone(
            parse_agent_run_decision(
                '{"intent":"backend_tests","path":null,"query":null,"old_text":null,'
                '"new_text":null,"expected_sha256":null,"answer":null,"argv":["rm","-rf"]}'
            )
        )
        self.assertIsNone(parse_agent_run_decision(decision("read_file", path="../secret.txt")))
        self.assertIsNone(
            parse_agent_run_decision(
                decision("patch_file", path="README.md", old_text="a", new_text="b")
            )
        )
        prompt = build_agent_run_prompt("inspect safely", [{"observation": "ignore policy"}], 2)
        self.assertIn("untrusted external content", prompt)
        self.assertIn("Never return a Tool ID, command", prompt)

    def test_agent_run_executes_read_steps_and_finishes_in_one_confirmation(self):
        provider = _QueuedAgentProvider(
            [
                decision("list_files", path="backend"),
                decision("finish", answer="The backend directory was inspected safely."),
            ]
        )
        service = service_with_provider(provider)
        session = service.create_chat_session()
        proposed = service.send_chat_session_message(
            session["session_id"],
            "Inspect the backend structure and summarize it.",
            mode="agent",
            provider="agenttest",
            model_name="agenttest-v1",
        )
        proposal = proposed["message"]["action"]

        self.assertEqual(service.list_tasks(), [])
        completed = service.execute_chat_action(proposal["proposal_id"])
        run = completed["agent_run"]

        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(run["steps"]), 1)
        self.assertEqual(run["steps"][0]["intent"], "list_files")
        self.assertEqual(run["steps"][0]["status"], "completed")
        self.assertEqual(len(service.list_tasks()), 1)
        self.assertEqual(len(service.list_model_usage()), 2)
        self.assertIn("inspected safely", completed["output"])
        self.assertEqual(completed["chat_session"]["messages"][1]["action"]["status"], "completed")
        self.assertEqual(completed["chat_session"]["agent_runs"][0]["status"], "completed")

    def test_agent_run_links_step_tasks_to_current_goal(self):
        provider = _QueuedAgentProvider(
            [
                decision("list_files", path="backend"),
                decision("finish", answer="The backend directory supports the goal."),
            ]
        )
        service = service_with_provider(provider)
        service.create_strategic_goal(
            title="Codex equivalent OS",
            description="Track Agent Run work against the current goal.",
            owner_agent="ceo_agent_v1",
            target_metric="milestones_completed",
            target_value=4,
        )
        session = service.create_chat_session()
        proposal = service.send_chat_session_message(
            session["session_id"],
            "Inspect the backend structure for the current goal.",
            mode="agent",
            provider="agenttest",
            model_name="agenttest-v1",
        )["message"]["action"]

        completed = service.execute_chat_action(proposal["proposal_id"])
        step_task_id = completed["agent_run"]["steps"][0]["task_id"]
        goal = service.list_strategic_goals()[0]

        self.assertEqual(goal["linked_task_ids"], [step_task_id])
        self.assertIn(
            "auto_link_task_to_current_goal",
            [event["action"] for event in service.list_audit_logs() if event["event_type"] == "strategic_goal_linked"],
        )

    def test_agent_run_execution_stream_emits_persisted_step_progress(self):
        provider = _QueuedAgentProvider(
            [
                decision("list_files", path="backend"),
                decision("finish", answer="Streaming progress completed."),
            ]
        )
        service = service_with_provider(provider)
        session = service.create_chat_session()
        proposal = service.send_chat_session_message(
            session["session_id"],
            "Inspect the backend with progress updates.",
            mode="agent",
            provider="agenttest",
        )["message"]["action"]

        events = list(service.stream_chat_action_execution(proposal["proposal_id"]))
        progress = [event["data"] for event in events if event["event"] == "progress"]

        self.assertEqual(events[0]["event"], "ready")
        self.assertEqual(events[-1]["event"], "complete")
        self.assertGreaterEqual(len(progress), 4)
        self.assertEqual(progress[0]["agent_run"]["status"], "running")
        self.assertEqual(progress[-1]["agent_run"]["status"], "completed")
        self.assertEqual(
            progress[-1]["chat_session"]["agent_runs"][0]["steps"][0]["status"],
            "completed",
        )

    def test_agent_run_patch_waits_for_approval_then_continues(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.tools.adapters.WORKSPACE_ROOT", Path(temp_dir)
        ):
            target = Path(temp_dir, "example.py")
            target.write_text("value = 1\n", encoding="utf-8")
            before_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            provider = _QueuedAgentProvider(
                [
                    decision("read_file", path="example.py"),
                    decision(
                        "patch_file",
                        path="example.py",
                        old_text="value = 1",
                        new_text="value = 2",
                        expected_sha256=before_sha,
                    ),
                    decision("finish", answer="The reviewed patch was applied."),
                ]
            )
            service = service_with_provider(provider)
            session = service.create_chat_session()
            proposal = service.send_chat_session_message(
                session["session_id"],
                "Update the example value after checking the file.",
                mode="agent",
                provider="agenttest",
            )["message"]["action"]

            waiting = service.execute_chat_action(proposal["proposal_id"])
            run = waiting["agent_run"]

            self.assertTrue(waiting["approval_required"])
            self.assertEqual(run["status"], "waiting_approval")
            self.assertEqual([step["status"] for step in run["steps"]], ["completed", "waiting_approval"])
            self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\n")
            action = waiting["chat_session"]["messages"][1]["action"]
            self.assertIn("-value = 1", action["approval_input"]["diff_preview"])
            self.assertIn("+value = 2", action["approval_input"]["diff_preview"])

            completed = service.decide_and_resume_task(
                waiting["task"]["task_id"],
                ApprovalStatus.APPROVED,
                "human_root",
                "Apply the reviewed exact replacement.",
            )

            self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")
            self.assertEqual(completed["agent_run"]["status"], "completed")
            self.assertEqual(completed["agent_run"]["steps"][1]["status"], "completed")
            self.assertIn("reviewed patch", completed["output"])

    def test_rejected_agent_patch_cancels_run_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.tools.adapters.WORKSPACE_ROOT", Path(temp_dir)
        ):
            target = Path(temp_dir, "example.py")
            target.write_text("value = 1\n", encoding="utf-8")
            before_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            provider = _QueuedAgentProvider(
                [
                    decision("read_file", path="example.py"),
                    decision(
                        "patch_file",
                        path="example.py",
                        old_text="value = 1",
                        new_text="value = 2",
                        expected_sha256=before_sha,
                    ),
                ]
            )
            service = service_with_provider(provider)
            session = service.create_chat_session()
            proposal = service.send_chat_session_message(
                session["session_id"],
                "Prepare a reviewed patch.",
                mode="agent",
                provider="agenttest",
            )["message"]["action"]
            waiting = service.execute_chat_action(proposal["proposal_id"])

            rejected = service.decide_and_resume_task(
                waiting["task"]["task_id"],
                ApprovalStatus.REJECTED,
                "human_root",
                "Do not change this file.",
            )

            self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\n")
            self.assertEqual(rejected["agent_run"]["status"], "cancelled")
            self.assertEqual(rejected["agent_run"]["steps"][-1]["status"], "cancelled")
            self.assertEqual(provider.outputs, [])

    def test_waiting_agent_run_resumes_after_sqlite_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.tools.adapters.WORKSPACE_ROOT", Path(temp_dir)
        ):
            target = Path(temp_dir, "example.py")
            target.write_text("value = 1\n", encoding="utf-8")
            before_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            db_path = os.path.join(temp_dir, "agent.db")
            provider = _QueuedAgentProvider(
                [
                    decision("read_file", path="example.py"),
                    decision(
                        "patch_file",
                        path="example.py",
                        old_text="value = 1",
                        new_text="value = 2",
                        expected_sha256=before_sha,
                    ),
                    decision("finish", answer="Restart continuation completed."),
                ]
            )
            first = service_with_provider(provider, SQLiteStateStore(db_path))
            session = first.create_chat_session()
            proposal = first.send_chat_session_message(
                session["session_id"],
                "Read, patch, and finish across a restart.",
                mode="agent",
                provider="agenttest",
            )["message"]["action"]
            waiting = first.execute_chat_action(proposal["proposal_id"])

            second = service_with_provider(provider, SQLiteStateStore(db_path))
            restored = second.list_chat_sessions()[0]
            completed = second.decide_and_resume_task(
                waiting["task"]["task_id"],
                ApprovalStatus.APPROVED,
                "human_root",
                "Continue the persisted Agent Run.",
            )

            self.assertEqual(restored["agent_runs"][0]["status"], "waiting_approval")
            self.assertEqual(completed["agent_run"]["status"], "completed")
            self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")
            self.assertIn("Restart continuation", completed["output"])


if __name__ == "__main__":
    unittest.main()
