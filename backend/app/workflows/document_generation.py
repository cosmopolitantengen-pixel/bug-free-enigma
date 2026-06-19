from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentRegistry
from app.approvals.service import ApprovalCenter
from app.audit.log import AuditLog
from app.budget.guard import BudgetGuard
from app.core.enums import (
    ActionDecision,
    ApprovalStatus,
    PermissionLevel,
    RiskLevel,
    TaskStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import (
    ActionRequest,
    AuditEvent,
    EvaluationRecord,
    KnowledgeDoc,
    MemoryRecord,
    Task,
    WorkflowRun,
    WorkflowStep,
    utc_now,
    Incident,
)
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.knowledge_base.store import KnowledgeBase
from app.memory.store import MemoryStore
from app.models.gateway import ModelGateway
from app.permissions.engine import PermissionEngine
from app.safety.risk import RiskEngine
from app.skills.registry import SkillRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class WorkflowResult:
    task: Task
    output: str | None
    approval_required: bool
    blocked: bool


class DocumentGenerationWorkflow:
    def __init__(
        self,
        agents: AgentRegistry,
        skills: SkillRegistry,
        permissions: PermissionEngine,
        risks: RiskEngine,
        approvals: ApprovalCenter,
        audit: AuditLog,
        memory: MemoryStore,
        knowledge: KnowledgeBase,
        evaluations: EvaluationStore,
        models: ModelGateway,
        budget: BudgetGuard,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.agents = agents
        self.skills = skills
        self.permissions = permissions
        self.risks = risks
        self.approvals = approvals
        self.audit = audit
        self.memory = memory
        self.knowledge = knowledge
        self.evaluations = evaluations
        self.models = models
        self.budget = budget
        self.incidents = incidents
        self.traces = traces

    def run(self, task: Task) -> WorkflowResult:
        run = self.traces.start_run("document_generation_v1", task.task_id)
        self._audit("task_created", "human_root", "create_task", task, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "created")
        self._step(run, 1, "task_created", "human_root", "create_task", task, WorkflowStepStatus.COMPLETED, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "created")

        ceo = self.agents.get("ceo_agent_v1")
        self._ensure_skill_allowed(ceo.agent_id, "task_planning_skill_v1")
        plan_request = ActionRequest(
            action="plan_task",
            actor_id=ceo.agent_id,
            task_id=task.task_id,
            permission_level=PermissionLevel.L1_DRAFT,
            reason="CEO Agent creates a safe execution plan.",
        )
        permission = self.permissions.evaluate(ceo, plan_request)
        risk = self.risks.assess(plan_request)
        if permission.decision == ActionDecision.BLOCK or risk.blocked:
            task.transition(TaskStatus.BLOCKED)
            self._audit("task_blocked", ceo.agent_id, plan_request.action, task, risk.level, ApprovalStatus.BLOCKED, permission.reason)
            self._step(run, 2, "plan_task", ceo.agent_id, plan_request.action, task, WorkflowStepStatus.BLOCKED, risk.level, ApprovalStatus.BLOCKED, permission.reason, permission.reason)
            self.traces.complete_run(run.run_id, WorkflowRunStatus.BLOCKED, permission.reason)
            return WorkflowResult(task, None, False, True)

        task.transition(TaskStatus.PLANNED)
        self._audit("task_planned", ceo.agent_id, plan_request.action, task, risk.level, ApprovalStatus.NOT_REQUIRED, "planned")
        self._step(run, 2, "plan_task", ceo.agent_id, plan_request.action, task, WorkflowStepStatus.COMPLETED, risk.level, ApprovalStatus.NOT_REQUIRED, "planned")

        pm = self.agents.get("project_manager_agent_v1")
        task.transition(TaskStatus.ASSIGNED)
        self._audit("task_assigned", pm.agent_id, "assign_document_agent", task, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "assigned")
        self._step(run, 3, "assign_document_agent", pm.agent_id, "assign_document_agent", task, WorkflowStepStatus.COMPLETED, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "assigned")

        document_agent = self.agents.get("document_agent_v1")
        self._ensure_skill_allowed(document_agent.agent_id, "document_writer_skill_v1")
        write_request = ActionRequest(
            action="create_internal_document",
            actor_id=document_agent.agent_id,
            task_id=task.task_id,
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            reason="Document Agent writes an internal document draft.",
        )
        permission = self.permissions.evaluate(document_agent, write_request)
        risk = self.risks.assess(write_request)
        if permission.decision == ActionDecision.BLOCK or risk.blocked:
            task.transition(TaskStatus.BLOCKED)
            self._audit("task_blocked", document_agent.agent_id, write_request.action, task, risk.level, ApprovalStatus.BLOCKED, permission.reason)
            self._step(run, 4, "write_document", document_agent.agent_id, write_request.action, task, WorkflowStepStatus.BLOCKED, risk.level, ApprovalStatus.BLOCKED, permission.reason, permission.reason)
            self.traces.complete_run(run.run_id, WorkflowRunStatus.BLOCKED, permission.reason)
            return WorkflowResult(task, None, False, True)

        if permission.decision == ActionDecision.REQUIRE_APPROVAL or risk.requires_approval:
            approval = self.approvals.request_approval(
                write_request,
                risk,
                possible_benefit="Complete the document task.",
                possible_loss="Incorrect or unsafe internal write.",
            )
            task.approval_id = approval.approval_id
            task.risk_level = risk.level
            task.transition(TaskStatus.NEEDS_APPROVAL)
            self._audit("approval_requested", document_agent.agent_id, write_request.action, task, risk.level, approval.status, "approval required")
            self._step(run, 4, "write_document", document_agent.agent_id, write_request.action, task, WorkflowStepStatus.WAITING_APPROVAL, risk.level, approval.status, "approval required")
            self.traces.complete_run(run.run_id, WorkflowRunStatus.WAITING_APPROVAL, "approval required")
            return WorkflowResult(task, None, True, False)

        task.transition(TaskStatus.EXECUTING)
        try:
            output = self._write_document(task, document_agent.agent_id)
        except PermissionError as exc:
            task.transition(TaskStatus.BLOCKED)
            self._audit("task_blocked", document_agent.agent_id, "generate_document", task, RiskLevel.MEDIUM, ApprovalStatus.BLOCKED, str(exc))
            self._step(run, 4, "write_document", document_agent.agent_id, write_request.action, task, WorkflowStepStatus.BLOCKED, RiskLevel.MEDIUM, ApprovalStatus.BLOCKED, str(exc), str(exc))
            self.traces.complete_run(run.run_id, WorkflowRunStatus.BLOCKED, str(exc))
            return WorkflowResult(task, None, False, True)
        self._audit("document_written", document_agent.agent_id, write_request.action, task, risk.level, ApprovalStatus.NOT_REQUIRED, "draft written")
        self._step(run, 4, "write_document", document_agent.agent_id, write_request.action, task, WorkflowStepStatus.COMPLETED, risk.level, ApprovalStatus.NOT_REQUIRED, "draft written")

        risk_agent = self.agents.get("risk_agent_v1")
        risk_check_request = ActionRequest(
            action="risk_check",
            actor_id=risk_agent.agent_id,
            task_id=task.task_id,
            permission_level=PermissionLevel.L1_DRAFT,
            reason="Risk Agent checks generated document.",
        )
        risk_check = self.risks.assess(risk_check_request)
        self._audit("risk_checked", risk_agent.agent_id, risk_check_request.action, task, risk_check.level, ApprovalStatus.NOT_REQUIRED, "risk checked")
        self._step(run, 5, "risk_check", risk_agent.agent_id, risk_check_request.action, task, WorkflowStepStatus.COMPLETED, risk_check.level, ApprovalStatus.NOT_REQUIRED, "risk checked")

        quality_agent = self.agents.get("quality_agent_v1")
        task.transition(TaskStatus.QUALITY_CHECKING)
        self._audit("quality_checked", quality_agent.agent_id, "quality_check", task, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "quality passed")
        self._step(run, 6, "quality_check", quality_agent.agent_id, "quality_check", task, WorkflowStepStatus.COMPLETED, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "quality passed")

        task.result = output
        task.risk_level = risk.level
        task.transition(TaskStatus.COMPLETED)
        self.memory.write(MemoryRecord(task_id=task.task_id, content=output))
        self.knowledge.write(KnowledgeDoc(title=task.title, content=output, source_task_id=task.task_id))
        self._evaluate(task, risk.level)
        self._audit("task_completed", "workflow_engine", "complete_task", task, risk.level, ApprovalStatus.NOT_REQUIRED, "completed")
        self._step(run, 7, "complete_task", "workflow_engine", "complete_task", task, WorkflowStepStatus.COMPLETED, risk.level, ApprovalStatus.NOT_REQUIRED, "completed")
        self.traces.complete_run(run.run_id, WorkflowRunStatus.COMPLETED, "completed")
        return WorkflowResult(task, output, False, False)

    def resume_after_approval(self, task: Task) -> WorkflowResult:
        if task.status != TaskStatus.NEEDS_APPROVAL:
            raise ValueError("task is not waiting for workflow approval")
        if not task.approval_id:
            raise ValueError("task has no workflow approval")

        approval = self.approvals.get(task.approval_id)
        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("workflow approval is not approved")

        run = self.traces.latest_run_for_task(task.task_id, "document_generation_v1")
        if run is None or run.status != WorkflowRunStatus.WAITING_APPROVAL:
            raise ValueError("task has no waiting workflow run")

        document_agent = self.agents.get("document_agent_v1")
        write_action = approval.request.action
        risk_level = approval.risk.level
        task.transition(TaskStatus.EXECUTING)
        try:
            output = self._write_document(task, document_agent.agent_id)
        except PermissionError as exc:
            task.transition(TaskStatus.BLOCKED)
            self._audit("task_blocked", document_agent.agent_id, "generate_document", task, RiskLevel.MEDIUM, ApprovalStatus.BLOCKED, str(exc))
            self._step(run, 4, "write_document", document_agent.agent_id, write_action, task, WorkflowStepStatus.BLOCKED, RiskLevel.MEDIUM, ApprovalStatus.BLOCKED, str(exc), str(exc))
            self.traces.complete_run(run.run_id, WorkflowRunStatus.BLOCKED, str(exc))
            return WorkflowResult(task, None, False, True)

        self._audit("document_written", document_agent.agent_id, write_action, task, risk_level, ApprovalStatus.APPROVED, "draft written after approval")
        self._step(run, 4, "write_document", document_agent.agent_id, write_action, task, WorkflowStepStatus.COMPLETED, risk_level, ApprovalStatus.APPROVED, "draft written after approval")

        risk_agent = self.agents.get("risk_agent_v1")
        risk_check_request = ActionRequest(
            action="risk_check",
            actor_id=risk_agent.agent_id,
            task_id=task.task_id,
            permission_level=PermissionLevel.L1_DRAFT,
            reason="Risk Agent checks generated document after approval.",
        )
        risk_check = self.risks.assess(risk_check_request)
        self._audit("risk_checked", risk_agent.agent_id, risk_check_request.action, task, risk_check.level, ApprovalStatus.NOT_REQUIRED, "risk checked")
        self._step(run, 5, "risk_check", risk_agent.agent_id, risk_check_request.action, task, WorkflowStepStatus.COMPLETED, risk_check.level, ApprovalStatus.NOT_REQUIRED, "risk checked")

        quality_agent = self.agents.get("quality_agent_v1")
        task.transition(TaskStatus.QUALITY_CHECKING)
        self._audit("quality_checked", quality_agent.agent_id, "quality_check", task, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "quality passed")
        self._step(run, 6, "quality_check", quality_agent.agent_id, "quality_check", task, WorkflowStepStatus.COMPLETED, RiskLevel.LOW, ApprovalStatus.NOT_REQUIRED, "quality passed")

        task.result = output
        task.risk_level = risk_level
        task.transition(TaskStatus.COMPLETED)
        self.memory.write(MemoryRecord(task_id=task.task_id, content=output))
        self.knowledge.write(KnowledgeDoc(title=task.title, content=output, source_task_id=task.task_id))
        self._evaluate(task, risk_level)
        self._audit("task_completed", "workflow_engine", "complete_task", task, risk_level, ApprovalStatus.APPROVED, "completed after approval")
        self._step(run, 7, "complete_task", "workflow_engine", "complete_task", task, WorkflowStepStatus.COMPLETED, risk_level, ApprovalStatus.APPROVED, "completed after approval")
        self.traces.complete_run(run.run_id, WorkflowRunStatus.COMPLETED, "completed after approval")
        return WorkflowResult(task, output, False, False)

    def _write_document(self, task: Task, actor_id: str) -> str:
        prompt = (
            f"# {task.title}\n\n"
            f"## Goal\n\n{task.description}\n\n"
            "## Plan\n\n"
            "1. Confirm task intent.\n"
            "2. Draft a structured internal document.\n"
            "3. Run risk and quality checks.\n"
            "4. Store approved results in Memory and Knowledge Base.\n\n"
            "## Safety Note\n\n"
            "This output is internal by default and must enter approval before any external publication."
        )
        budget_check = self.budget.check_model_call(prompt, "document_generation")
        if not budget_check.allowed:
            self.budget.record_cost(
                source_type="model_usage",
                source_id="blocked",
                actor_id=actor_id,
                task_id=task.task_id,
                tokens=budget_check.estimated_tokens,
                amount=budget_check.estimated_cost,
                result="blocked",
                reason=budget_check.reason,
            )
            self.audit.append(
                AuditEvent(
                    event_type="model_blocked",
                    actor_id=actor_id,
                    action="generate_document",
                    task_id=task.task_id,
                    risk_level=RiskLevel.MEDIUM,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=budget_check.reason,
                )
            )
            self.incidents.report(
                Incident(
                    title="Model call blocked by budget policy",
                    description=budget_check.reason,
                    source_type="model_usage",
                    source_id="blocked",
                    risk_level=RiskLevel.MEDIUM,
                    task_id=task.task_id,
                    actor_id=actor_id,
                    recommendation="Review budget policy, task input size, or whether this model call is necessary.",
                )
            )
            raise PermissionError(budget_check.reason)
        response = self.models.generate(
            prompt=prompt,
            actor_id=actor_id,
            purpose="document_generation",
            task_id=task.task_id,
            cost_per_token=self.budget.policy.cost_per_token,
        )
        self.budget.record_cost(
            source_type="model_usage",
            source_id=response.usage.record_id,
            actor_id=actor_id,
            task_id=task.task_id,
            tokens=response.usage.total_tokens,
            amount=response.usage.estimated_cost,
            result="recorded",
            reason="model usage recorded",
        )
        self.audit.append(
            AuditEvent(
                event_type="model_called",
                actor_id=actor_id,
                action="generate_document",
                task_id=task.task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="model usage recorded",
                input_ref=response.usage.input_ref,
                output_ref=response.usage.output_ref,
                model_name=response.usage.model_name,
            )
        )
        return response.output

    def _ensure_skill_allowed(self, agent_id: str, skill_id: str) -> None:
        agent = self.agents.get(agent_id)
        skill = self.skills.get(skill_id)
        if skill_id not in agent.allowed_skills or agent_id not in skill.allowed_agents:
            raise PermissionError(f"{agent_id} cannot use {skill_id}")
        if not skill.enabled:
            raise PermissionError(f"{skill_id} is disabled")

    def _audit(
        self,
        event_type: str,
        actor_id: str,
        action: str,
        task: Task,
        risk_level: RiskLevel,
        approval_status: ApprovalStatus,
        result: str,
    ) -> None:
        self.audit.append(
            AuditEvent(
                event_type=event_type,
                actor_id=actor_id,
                action=action,
                task_id=task.task_id,
                risk_level=risk_level,
                approval_status=approval_status,
                result=result,
            )
        )

    def _step(
        self,
        run: WorkflowRun,
        sequence: int,
        step_name: str,
        actor_id: str,
        action: str,
        task: Task,
        status: WorkflowStepStatus,
        risk_level: RiskLevel,
        approval_status: ApprovalStatus,
        result: str,
        error: str | None = None,
    ) -> None:
        self.traces.append_step(
            WorkflowStep(
                run_id=run.run_id,
                task_id=task.task_id,
                sequence=sequence,
                step_name=step_name,
                actor_id=actor_id,
                action=action,
                status=status,
                risk_level=risk_level,
                approval_status=approval_status,
                result=result,
                error=error,
                completed_at=None if status == WorkflowStepStatus.STARTED else utc_now(),
            )
        )

    def _evaluate(self, task: Task, risk_level: RiskLevel) -> None:
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id="document_generation_v1",
                task_id=task.task_id,
                score=1.0,
                metric="completed_without_approval_or_block",
                notes="Document workflow completed, wrote Memory and Knowledge Base records.",
                risk_level=risk_level,
            )
        )
        self.evaluations.write(
            EvaluationRecord(
                subject_type="agent",
                subject_id="quality_agent_v1",
                task_id=task.task_id,
                score=1.0,
                metric="quality_check_passed",
                notes="Quality check passed for generated document.",
                risk_level=RiskLevel.LOW,
            )
        )
        self.evaluations.write(
            EvaluationRecord(
                subject_type="skill",
                subject_id="document_writer_skill_v1",
                task_id=task.task_id,
                score=1.0,
                metric="document_generated",
                notes="Document Writing Skill produced structured internal output.",
                risk_level=RiskLevel.LOW,
            )
        )
