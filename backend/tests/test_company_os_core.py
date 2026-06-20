import json
import os
import sys
import unittest
from dataclasses import replace


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.agents.registry import AgentRegistry
from app.bootstrap import build_company_os
from app.core.enums import ActionDecision, ApprovalStatus, PermissionLevel, RiskLevel, TaskStatus
from app.core.models import ActionRequest, Agent, AuditEvent, BudgetPolicy, RiskAssessment, Task, WorkflowDefinition, WorkflowStepDefinition
from app.workflows.registry import WorkflowRegistry


class CompanyOSCoreTests(unittest.TestCase):
    def test_default_bootstrap_registers_foundation(self):
        company_os = build_company_os()

        self.assertEqual(len(company_os.agents.list()), 17)
        self.assertEqual(len(company_os.skills.list()), 18)
        self.assertGreaterEqual(len(company_os.tools.list()), 5)
        self.assertEqual(company_os.agents.get("ceo_agent_v1").reports_to, "human_root")

        agent_ids = {agent.agent_id for agent in company_os.agents.list()}
        skill_ids = {skill.skill_id for skill in company_os.skills.list()}
        tool_ids = {tool.tool_id for tool in company_os.tools.list()}
        for agent in company_os.agents.list():
            self.assertTrue(agent.allowed_skills <= skill_ids)
            self.assertTrue(agent.allowed_tools <= tool_ids)
            self.assertTrue(agent.reports_to == "human_root" or agent.reports_to in agent_ids)
            self.assertNotIn(PermissionLevel.L5_ROOT, agent.permissions)
            for skill_id in agent.allowed_skills:
                self.assertIn(agent.agent_id, company_os.skills.get(skill_id).allowed_agents)
        for skill in company_os.skills.list():
            self.assertTrue(skill.allowed_agents <= agent_ids)
            for agent_id in skill.allowed_agents:
                self.assertIn(skill.skill_id, company_os.agents.get(agent_id).allowed_skills)

    def test_v1_workflow_catalog_is_complete_and_validated(self):
        company_os = build_company_os()
        workflows = company_os.workflows.list()

        self.assertEqual(len(workflows), 10)
        self.assertEqual(
            {workflow.workflow_id for workflow in workflows},
            {
                "document_generation_v1",
                "task_planning_v1",
                "agent_collaboration_v1",
                "skill_missing_v1",
                "agent_missing_v1",
                "approval_v1",
                "quality_check_v1",
                "retrospective_v1",
                "github_project_analysis_v1",
                "tool_call_v1",
            },
        )
        registry = WorkflowRegistry(company_os.agents, company_os.skills)
        with self.assertRaises(ValueError):
            registry.register(
                WorkflowDefinition(
                    workflow_id="invalid_sequence_v1",
                    name="Invalid Sequence",
                    description="Must fail validation.",
                    entrypoint="none",
                    steps=(
                        WorkflowStepDefinition(
                            sequence=2,
                            step_name="bad_step",
                            actor_id="ceo_agent_v1",
                            action="plan_task",
                            permission_level=PermissionLevel.L1_DRAFT,
                            skill_id="task_planning_skill_v1",
                        ),
                    ),
                )
            )

    def test_task_planning_workflow_blocks_disabled_skill_and_reports_incident(self):
        company_os = build_company_os()
        skill = company_os.skills.get("task_planning_skill_v1")
        company_os.skills.restore(replace(skill, enabled=False))
        task = Task(title="Blocked planning", description="Disabled Skills must stop execution.")

        result = company_os.task_planning_workflow.run(task)

        self.assertTrue(result.blocked)
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertEqual(company_os.traces.list_runs()[-1].status.value, "blocked")
        self.assertEqual(company_os.traces.list_steps()[-1].status.value, "blocked")
        self.assertEqual(company_os.incidents.list()[-1].source_type, "workflow")

    def test_agents_cannot_register_root_permissions(self):
        registry = AgentRegistry()

        with self.assertRaises(ValueError):
            registry.register(
                Agent(
                    agent_id="bad_root_agent",
                    name="Bad Root Agent",
                    department="Unsafe",
                    role="Should not be allowed.",
                    permissions={PermissionLevel.L5_ROOT},
                    forbidden=set(),
                    allowed_skills=set(),
                    allowed_tools=set(),
                    reports_to="human_root",
                    risk_level=RiskLevel.HIGH,
                )
            )

    def test_permission_blocks_root_only_actions(self):
        company_os = build_company_os()
        agent = company_os.agents.get("ceo_agent_v1")
        request = ActionRequest(
            action="delete_audit_log",
            actor_id=agent.agent_id,
            task_id="task_test",
            permission_level=PermissionLevel.L5_ROOT,
            reason="Attempt to delete audit log.",
        )

        result = company_os.permissions.evaluate(agent, request)

        self.assertEqual(result.decision, ActionDecision.BLOCK)
        self.assertIn("Human Root", result.reason)

    def test_risk_blocks_forbidden_actions(self):
        company_os = build_company_os()
        request = ActionRequest(
            action="captcha_bypass",
            actor_id="ceo_agent_v1",
            task_id="task_test",
            permission_level=PermissionLevel.L4_HIGH_RISK,
            reason="Forbidden request.",
        )

        risk = company_os.risks.assess(request)

        self.assertEqual(risk.level, RiskLevel.FORBIDDEN)
        self.assertTrue(risk.blocked)
        self.assertTrue(risk.requires_approval)

    def test_high_risk_action_requires_approval(self):
        company_os = build_company_os()
        request = ActionRequest(
            action="execute_code",
            actor_id="tech_agent_v1",
            task_id="task_test",
            permission_level=PermissionLevel.L4_HIGH_RISK,
            reason="Run generated code.",
        )

        risk = company_os.risks.assess(request)
        approval = company_os.approvals.request_approval(
            request,
            risk,
            possible_benefit="Verify code behavior.",
            possible_loss="Unsafe execution.",
        )

        self.assertEqual(risk.level, RiskLevel.HIGH)
        self.assertEqual(approval.status, ApprovalStatus.PENDING)

    def test_forbidden_approval_is_auto_blocked(self):
        company_os = build_company_os()
        request = ActionRequest(
            action="disable_risk_system",
            actor_id="ceo_agent_v1",
            task_id="task_test",
            permission_level=PermissionLevel.L5_ROOT,
            reason="Forbidden request.",
        )

        risk = company_os.risks.assess(request)
        approval = company_os.approvals.request_approval(
            request,
            risk,
            possible_benefit="None.",
            possible_loss="System safety disabled.",
        )

        self.assertEqual(approval.status, ApprovalStatus.BLOCKED)
        self.assertEqual(approval.decided_by, "risk_system")

    def test_audit_log_is_append_only(self):
        company_os = build_company_os()
        event = AuditEvent(
            event_type="test",
            actor_id="tester",
            action="append",
            task_id="task_test",
            risk_level=RiskLevel.LOW,
            approval_status=ApprovalStatus.NOT_REQUIRED,
            result="ok",
        )

        company_os.audit.append(event)

        self.assertEqual(len(company_os.audit.list()), 1)
        with self.assertRaises(PermissionError):
            company_os.audit.delete(event.event_id)
        with self.assertRaises(PermissionError):
            company_os.audit.clear()

    def test_document_workflow_completes_and_writes_memory_knowledge_audit(self):
        company_os = build_company_os()
        task = Task(title="Internal operating note", description="Create a safe internal operating note.")

        result = company_os.document_workflow.run(task)

        self.assertFalse(result.blocked)
        self.assertFalse(result.approval_required)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertIn(TaskStatus.PLANNED, task.history)
        self.assertIn(TaskStatus.QUALITY_CHECKING, task.history)
        self.assertEqual(len(company_os.memory.list()), 1)
        self.assertEqual(len(company_os.knowledge.list()), 1)
        self.assertEqual(len(company_os.traces.list_runs()), 1)
        self.assertEqual(company_os.traces.list_runs()[0].status.value, "completed")
        self.assertEqual(len(company_os.traces.list_steps()), 7)
        self.assertEqual(company_os.traces.list_steps()[0].step_name, "task_created")
        self.assertEqual(len(company_os.models.list_usage()), 1)
        self.assertEqual(company_os.models.list_usage()[0].purpose, "document_generation")
        self.assertEqual(len(company_os.budget.list_cost_logs()), 1)
        self.assertEqual(company_os.budget.list_cost_logs()[0].result, "recorded")
        self.assertGreater(company_os.models.list_usage()[0].estimated_cost, 0)
        self.assertGreaterEqual(len(company_os.audit.list()), 7)

    def test_document_workflow_blocks_when_model_call_exceeds_budget(self):
        company_os = build_company_os(budget_policy=BudgetPolicy(max_tokens_per_call=1))
        task = Task(title="Budget test", description="This should exceed the tiny token limit.")

        result = company_os.document_workflow.run(task)

        self.assertTrue(result.blocked)
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertEqual(len(company_os.models.list_usage()), 0)
        self.assertEqual(len(company_os.budget.list_cost_logs()), 1)
        self.assertEqual(company_os.budget.list_cost_logs()[0].result, "blocked")
        self.assertEqual(company_os.traces.list_runs()[0].status.value, "blocked")
        self.assertGreaterEqual(len(company_os.incidents.list()), 1)
        self.assertEqual(company_os.incidents.list()[0].status.value, "open")

    def test_document_workflow_stops_when_runtime_skill_is_disabled(self):
        from dataclasses import replace
        from app.services.company import CompanyApplicationService

        company_os = build_company_os()
        quality_skill = company_os.skills.get("quality_check_skill_v1")
        company_os.skills.restore(replace(quality_skill, enabled=False))
        service = CompanyApplicationService(company_os=company_os)
        task = service.create_task("Blocked quality run", "The Workflow must not bypass a disabled Skill.")

        result = service.run_task(task["task_id"])
        skill_runs = service.list_skill_runs()

        self.assertTrue(result["blocked"])
        self.assertEqual(result["task"]["status"], "blocked")
        self.assertEqual(len(skill_runs), 5)
        self.assertEqual(skill_runs[-1]["skill_id"], "quality_check_skill_v1")
        self.assertEqual(skill_runs[-1]["status"], "blocked")
        self.assertIn("skill is disabled", skill_runs[-1]["error"])
        self.assertEqual(service.list_workflow_runs()[-1]["status"], "failed")

    def test_quality_workflow_blocks_when_quality_skill_is_disabled(self):
        from dataclasses import replace
        from app.services.company import CompanyApplicationService

        company_os = build_company_os()
        skill = company_os.skills.get("quality_check_skill_v1")
        company_os.skills.restore(replace(skill, enabled=False))
        service = CompanyApplicationService(company_os=company_os)

        result = service.run_registered_workflow(
            "quality_check_v1",
            "Blocked quality workflow",
            "This content would pass, but its required Skill is disabled.",
        )

        self.assertTrue(result["blocked"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["incident"]["source_type"], "workflow")
        self.assertEqual(result["task"]["status"], "blocked")
        self.assertEqual(service.list_skill_runs()[0]["status"], "blocked")
        self.assertEqual(service.list_workflow_runs()[0]["status"], "blocked")
        self.assertEqual(service.list_workflow_steps()[0]["status"], "blocked")
        self.assertGreaterEqual(len(service.list_incidents()), 2)

    def test_retrospective_workflow_blocks_before_review_when_memory_skill_is_disabled(self):
        from dataclasses import replace
        from app.services.company import CompanyApplicationService

        company_os = build_company_os()
        skill = company_os.skills.get("memory_write_skill_v1")
        company_os.skills.restore(replace(skill, enabled=False))
        service = CompanyApplicationService(company_os=company_os)

        result = service.run_registered_workflow(
            "retrospective_v1",
            "Blocked retrospective",
            "This retrospective has enough detail to pass quality before memory is blocked.",
            input={"lessons": ["Do not bypass disabled Skills"], "quality_score": 0.8},
        )

        self.assertTrue(result["blocked"])
        self.assertEqual(result["task"]["status"], "blocked")
        self.assertIsNone(result["review"])
        self.assertIsNone(result["knowledge"])
        self.assertEqual(len(service.list_task_reviews()), 0)
        self.assertEqual(len(service.list_knowledge()), 0)
        self.assertEqual([run["status"] for run in service.list_skill_runs()], ["completed", "blocked"])
        self.assertEqual(service.list_workflow_runs()[0]["status"], "blocked")

    def test_document_workflow_resumes_after_approval(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        original_assess = service.company_os.risks.assess

        def require_document_approval(request):
            if request.action == "create_internal_document":
                return RiskAssessment(request, RiskLevel.MEDIUM, ("approval forced for test",), True, False)
            return original_assess(request)

        service.company_os.risks.assess = require_document_approval
        task = service.create_task("Approval document", "Force the workflow through approval.")
        requested = service.run_task(task["task_id"])
        runs = service.list_workflow_runs()

        self.assertEqual(requested["task"]["status"], "needs_approval")
        self.assertTrue(requested["approval_required"])
        self.assertEqual(runs[-1]["status"], "waiting_approval")
        with self.assertRaises(ValueError):
            service.resume_task(task["task_id"])

        service.decide_approval(requested["task"]["approval_id"], ApprovalStatus.APPROVED, "human_root", "approved")
        resumed = service.resume_task(task["task_id"])

        self.assertEqual(resumed["task"]["status"], "completed")
        self.assertEqual(service.list_workflow_runs()[-1]["status"], "completed")
        self.assertEqual(len(service.list_memory()), 1)
        self.assertEqual(len(service.list_knowledge()), 1)
        self.assertEqual(service.list_audit_logs()[-1]["event_type"], "task_completed")

    def test_model_gateway_records_deterministic_usage(self):
        company_os = build_company_os()

        response = company_os.models.generate(
            prompt="Create an internal summary.",
            actor_id="document_agent_v1",
            purpose="unit_test",
            task_id="task_test",
        )

        self.assertIn("unit_test", response.output)
        self.assertEqual(len(company_os.models.list_usage()), 1)
        self.assertEqual(company_os.models.list_usage()[0].total_tokens, response.usage.total_tokens)

    def test_missing_skill_and_agent_generate_disabled_proposals(self):
        company_os = build_company_os()

        skill = company_os.gaps.missing_skill(
            capability="Course Outline",
            requested_by_agent="document_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        )
        agent = company_os.gaps.missing_agent(
            role="Training",
            department="Knowledge",
            repeated_reason="Training content appears repeatedly.",
        )

        self.assertTrue(skill.requires_approval)
        self.assertFalse(skill.enabled_by_default)
        self.assertFalse(agent.enabled_by_default)
        self.assertEqual(agent.risk_level, RiskLevel.MEDIUM)

    def test_tool_run_request_completes_low_risk_allowed_tool(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        service.create_task("Tool inspected task", "Make task state visible to the task manager tool.")

        result = service.request_tool_run(
            tool_id="task_manager_tool",
            actor_id="ceo_agent_v1",
            input={"operation": "inspect"},
            reason="Inspect internal task state.",
        )

        self.assertEqual(result["run"]["status"], "completed")
        self.assertEqual(result["permission_decision"], "allow")
        self.assertIsNone(result["approval"])
        tool_result = json.loads(result["run"]["result"])
        self.assertEqual(tool_result["task_count"], 1)
        self.assertEqual(tool_result["status_counts"]["created"], 1)
        self.assertEqual(service.list_audit_logs()[-1]["event_type"], "tool_run_requested")

    def test_internal_tool_adapters_execute_safe_system_queries(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        service.request_tool_run(
            tool_id="knowledge_base_tool",
            actor_id="document_agent_v1",
            input={"operation": "write", "title": "Adapter Note", "content": "Tool adapters can write internal knowledge."},
            reason="Write low-risk internal knowledge.",
        )
        database = service.request_tool_run(
            tool_id="database_read_tool",
            actor_id="risk_agent_v1",
            input={"operation": "summary"},
            reason="Read aggregate database state.",
        )
        audit = service.request_tool_run(
            tool_id="audit_read_tool",
            actor_id="quality_agent_v1",
            input={"limit": 2},
            reason="Read recent audit entries.",
        )

        self.assertEqual(len(service.list_knowledge()), 1)
        self.assertEqual(database["run"]["status"], "completed")
        self.assertEqual(json.loads(database["run"]["result"])["tables"]["knowledge_docs"], 1)
        self.assertEqual(audit["run"]["status"], "completed")
        self.assertEqual(len(json.loads(audit["run"]["result"])["events"]), 2)

    def test_filesystem_read_tool_stays_inside_safe_workspace_paths(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())

        listed = service.request_tool_run(
            tool_id="filesystem_read_tool",
            actor_id="document_agent_v1",
            input={"operation": "list", "path": ".", "limit": 10},
            reason="List safe workspace files for context.",
        )
        readme = service.request_tool_run(
            tool_id="filesystem_read_tool",
            actor_id="document_agent_v1",
            input={"operation": "read", "path": "README.md"},
            reason="Read a small text file.",
        )
        safety_doc = service.request_tool_run(
            tool_id="filesystem_read_tool",
            actor_id="document_agent_v1",
            input={"operation": "read", "path": "docs/SAFETY.md"},
            reason="Read safety doc as external content.",
        )
        searched = service.request_tool_run(
            tool_id="filesystem_read_tool",
            actor_id="document_agent_v1",
            input={"operation": "search", "path": "docs", "query": "Tool", "limit": 5},
            reason="Search safe project docs.",
        )
        escaped = service.request_tool_run(
            tool_id="filesystem_read_tool",
            actor_id="document_agent_v1",
            input={"operation": "list", "path": ".."},
            reason="Attempt to leave workspace.",
        )
        hidden = service.request_tool_run(
            tool_id="filesystem_read_tool",
            actor_id="document_agent_v1",
            input={"operation": "list", "path": ".git"},
            reason="Attempt to read sensitive metadata.",
        )

        self.assertEqual(listed["run"]["status"], "completed")
        self.assertIn("README.md", [entry["name"] for entry in json.loads(listed["run"]["result"])["entries"]])
        self.assertEqual(readme["run"]["status"], "completed")
        self.assertIn("AI Company OS", json.loads(readme["run"]["result"])["content"])
        self.assertFalse(json.loads(readme["run"]["result"])["external_content_inspection"]["trusted"])
        safety_result = json.loads(safety_doc["run"]["result"])
        self.assertEqual(safety_result["external_content_inspection"]["risk_level"], "high")
        self.assertTrue(safety_result["external_content_inspection"]["instruction_risk"])
        self.assertEqual(searched["run"]["status"], "completed")
        search_result = json.loads(searched["run"]["result"])
        self.assertGreaterEqual(len(search_result["matches"]), 1)
        self.assertFalse(search_result["external_content_inspection"]["trusted"])
        self.assertIn("flagged_files", search_result["external_content_inspection"])
        self.assertEqual(escaped["run"]["status"], "failed")
        self.assertIn("inside the workspace", escaped["run"]["error"])
        self.assertEqual(hidden["run"]["status"], "failed")
        self.assertIn("sensitive", hidden["run"]["error"])

    def test_tool_adapter_reports_invalid_input_as_failed_run(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())

        result = service.request_tool_run(
            tool_id="task_manager_tool",
            actor_id="ceo_agent_v1",
            input={"operation": "get"},
            reason="Invalid adapter input should fail cleanly.",
        )

        self.assertEqual(result["run"]["status"], "failed")
        self.assertIn("task_id is required", result["run"]["error"])

    def test_tool_run_blocks_disallowed_agent_tool_pair(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())

        result = service.request_tool_run(
            tool_id="knowledge_base_tool",
            actor_id="risk_agent_v1",
            input={"operation": "write"},
            reason="Risk agent should not write knowledge.",
        )

        self.assertEqual(result["run"]["status"], "blocked")
        self.assertIn("not allowed", result["run"]["error"])

    def test_approved_tool_run_can_be_completed_after_human_decision(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        service.register_tool(
            tool_id="approved_content_prepare_tool",
            name="Approved Content Prepare Tool",
            type="internal",
            description="Prepare medium-risk internal content after approval.",
            action="prepare_external_content",
            permission_level=PermissionLevel.L3_EXTERNAL_PREPARE,
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            input_schema={"topic": "string"},
            output_schema={"message": "string"},
            version="1.0.0",
            enabled=True,
        )
        service.register_agent(
            agent_id="approval_test_agent",
            name="Approval Test Agent",
            department="QA",
            role="Exercise approval-gated tool runs.",
            permissions=[PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT, PermissionLevel.L2_INTERNAL_WRITE, PermissionLevel.L3_EXTERNAL_PREPARE],
            forbidden=[],
            allowed_skills=[],
            allowed_tools=["approved_content_prepare_tool"],
            reports_to="human_root",
            risk_level=RiskLevel.LOW,
            version="1.0.0",
            enabled=True,
        )

        requested = service.request_tool_run(
            tool_id="approved_content_prepare_tool",
            actor_id="approval_test_agent",
            input={"topic": "launch note"},
            reason="Needs approval before preparing external content.",
        )

        self.assertEqual(requested["run"]["status"], "waiting_approval")
        with self.assertRaises(ValueError):
            service.complete_tool_run(requested["run"]["run_id"], "human_root", "too early")

        service.decide_approval(requested["approval"]["approval_id"], ApprovalStatus.APPROVED, "human_root", "approved")
        completed = service.complete_tool_run(requested["run"]["run_id"], "human_root", "complete after approval")

        self.assertEqual(completed["run"]["status"], "completed")
        self.assertIn("Simulated Approved Content Prepare Tool execution", json.loads(completed["run"]["result"])["message"])
        self.assertEqual(service.list_audit_logs()[-1]["event_type"], "tool_run_completed")

    def test_low_risk_skill_run_executes_validated_adapter_and_evaluates(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        result = service.request_skill_run(
            "task_planning_skill_v1",
            "ceo_agent_v1",
            {"goal": "Ship a controlled Skill Runtime."},
            "Create a safe execution plan.",
        )

        self.assertEqual(result["run"]["status"], "completed")
        self.assertIn("Assign authorized Agents", json.loads(result["run"]["result"])["plan"])
        self.assertEqual(service.list_evaluations()[-1]["subject_type"], "skill")

    def test_skill_run_invalid_input_fails_without_losing_run_record(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        result = service.request_skill_run(
            "summary_skill_v1",
            "ceo_agent_v1",
            {},
            "Reject malformed input cleanly.",
        )

        self.assertEqual(result["run"]["status"], "failed")
        self.assertIn("missing required skill input: content", result["run"]["error"])
        self.assertEqual(len(service.list_skill_runs()), 1)

    def test_skill_run_blocks_asymmetric_or_missing_agent_authorization(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        result = service.request_skill_run(
            "summary_skill_v1",
            "risk_agent_v1",
            {"content": "The Risk Agent is not authorized to summarize this text."},
            "Exercise the two-sided authorization boundary.",
        )

        self.assertEqual(result["run"]["status"], "blocked")
        self.assertIn("not authorized", result["run"]["error"])
        self.assertEqual(result["incident"]["source_type"], "skill_run")

    def test_approval_gated_skill_executes_only_after_human_decision(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        requested = service.request_skill_run(
            "code_generation_skill_v1",
            "tech_agent_v1",
            {"requirements": "Return a greeting.", "language": "Python"},
            "Generate a draft after approval.",
        )

        self.assertEqual(requested["run"]["status"], "waiting_approval")
        with self.assertRaises(ValueError):
            service.complete_skill_run(requested["run"]["run_id"])
        service.decide_approval(requested["approval"]["approval_id"], ApprovalStatus.APPROVED, "human_root", "approved")
        completed = service.complete_skill_run(requested["run"]["run_id"], "human_root", "execute")

        self.assertEqual(completed["run"]["status"], "completed")
        self.assertIn("Draft Python implementation", json.loads(completed["run"]["result"])["source"])

    def test_all_registered_v1_skills_have_executable_runtime_adapters(self):
        from app.services.company import CompanyApplicationService

        service = CompanyApplicationService(company_os=build_company_os())
        cases = {
            "task_planning_skill_v1": ("ceo_agent_v1", {"goal": "Plan work"}),
            "document_writer_skill_v1": ("document_agent_v1", {"topic": "Note", "materials": []}),
            "summary_skill_v1": ("ceo_agent_v1", {"content": "Summarize this internal text."}),
            "risk_check_skill_v1": ("risk_agent_v1", {"action": "read_internal_state"}),
            "quality_check_skill_v1": ("quality_agent_v1", {"content": "A sufficiently detailed quality sample."}),
            "rewrite_skill_v1": ("document_agent_v1", {"content": "Draft", "instructions": "Clarify"}),
            "data_cleanup_skill_v1": ("data_agent_v1", {"records": [{"name": " A "}], "rules": {}}),
            "spreadsheet_generation_skill_v1": ("data_agent_v1", {"records": [], "columns": ["name"]}),
            "code_generation_skill_v1": ("tech_agent_v1", {"requirements": "Draft code", "language": "Python"}),
            "code_review_skill_v1": ("tech_agent_v1", {"source": "print('ok')", "context": "unit"}),
            "github_project_analysis_skill_v1": ("tech_agent_v1", {"repository": "owner/repo", "metadata": {}}),
            "approval_request_skill_v1": ("ceo_agent_v1", {"action": "prepare", "reason": "test", "target": "draft"}),
            "audit_logging_skill_v1": ("audit_agent_v1", {"event": {"type": "test"}}),
            "memory_write_skill_v1": ("memory_agent_v1", {"task_id": "task_adapter_test", "content": "Retain this."}),
            "knowledge_search_skill_v1": ("memory_agent_v1", {"query": "nothing"}),
            "skill_search_skill_v1": ("skill_manager_agent_v1", {"query": "planning"}),
            "skill_composition_skill_v1": ("skill_manager_agent_v1", {"skill_ids": ["summary_skill_v1"], "goal": "Compose"}),
            "temporary_skill_creation_skill_v1": ("skill_factory_agent_v1", {"capability": "Test helper", "constraints": []}),
        }

        self.assertEqual(set(cases), {skill.skill_id for skill in service.company_os.skills.list()})
        for skill_id, (actor_id, payload) in cases.items():
            requested = service.request_skill_run(skill_id, actor_id, payload, "Verify runtime adapter coverage.")
            if requested["run"]["status"] == "waiting_approval":
                service.decide_approval(requested["approval"]["approval_id"], ApprovalStatus.APPROVED, "human_root", "adapter test")
                requested = service.complete_skill_run(requested["run"]["run_id"])
            self.assertEqual(requested["run"]["status"], "completed", skill_id)


if __name__ == "__main__":
    unittest.main()
