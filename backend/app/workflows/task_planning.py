from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentRegistry
from app.approvals.service import ApprovalCenter
from app.audit.log import AuditLog
from app.core.enums import (
    ActionDecision,
    ApprovalStatus,
    RiskLevel,
    TaskStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import (
    ActionRequest,
    AuditEvent,
    EvaluationRecord,
    Incident,
    MemoryRecord,
    Task,
    WorkflowStep,
    WorkflowStepDefinition,
    utc_now,
)
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.memory.store import MemoryStore
from app.permissions.engine import PermissionEngine
from app.safety.risk import RiskEngine
from app.skills.registry import SkillRegistry
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class TaskPlanningResult:
    task: Task
    output: str | None
    approval_required: bool
    blocked: bool


class TaskPlanningWorkflow:
    workflow_id = "task_planning_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        agents: AgentRegistry,
        skills: SkillRegistry,
        permissions: PermissionEngine,
        risks: RiskEngine,
        approvals: ApprovalCenter,
        audit: AuditLog,
        memory: MemoryStore,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.agents = agents
        self.skills = skills
        self.permissions = permissions
        self.risks = risks
        self.approvals = approvals
        self.audit = audit
        self.memory = memory
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces

    def run(self, task: Task) -> TaskPlanningResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("task planning requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("task planning workflow is disabled")
        run = self.traces.start_run(definition.workflow_id, task.task_id)

        for step in definition.steps:
            agent = self.agents.get(step.actor_id)
            if step.skill_id is not None:
                skill = self.skills.get(step.skill_id)
                if not skill.enabled:
                    return self._block(task, run.run_id, step, "workflow Skill is disabled")
                if step.skill_id not in agent.allowed_skills or agent.agent_id not in skill.allowed_agents:
                    return self._block(task, run.run_id, step, "workflow Skill authorization changed")
            request = ActionRequest(
                action=step.action,
                actor_id=step.actor_id,
                task_id=task.task_id,
                permission_level=step.permission_level,
                reason=f"{definition.name}: {step.step_name}",
                target=definition.workflow_id,
            )
            permission = self.permissions.evaluate(agent, request)
            risk = self.risks.assess(request)
            if permission.decision == ActionDecision.BLOCK or risk.blocked:
                reason = permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons)
                return self._block(task, run.run_id, step, reason, risk.level)
            if permission.decision == ActionDecision.REQUIRE_APPROVAL or risk.requires_approval:
                approval = self.approvals.request_approval(
                    request,
                    risk,
                    possible_benefit="Produce a controlled internal task plan.",
                    possible_loss="The plan could expand scope or authority beyond the user's goal.",
                )
                task.approval_id = approval.approval_id
                task.risk_level = risk.level
                task.transition(TaskStatus.NEEDS_APPROVAL)
                self._record_step(
                    run.run_id,
                    task,
                    step,
                    WorkflowStepStatus.WAITING_APPROVAL,
                    risk.level,
                    approval.status,
                    "approval required",
                )
                self.traces.complete_run(run.run_id, WorkflowRunStatus.WAITING_APPROVAL, "approval required")
                self._audit(step, task, risk.level, approval.status, "approval required")
                return TaskPlanningResult(task, None, True, False)
            self._record_step(
                run.run_id,
                task,
                step,
                WorkflowStepStatus.COMPLETED,
                risk.level,
                ApprovalStatus.NOT_REQUIRED,
                "completed",
            )
            self._audit(step, task, risk.level, ApprovalStatus.NOT_REQUIRED, "completed")

        output = self._build_plan(task)
        task.result = output
        task.risk_level = RiskLevel.LOW
        task.transition(TaskStatus.PLANNED)
        self.memory.write(MemoryRecord(task_id=task.task_id, memory_type="plan", content=output))
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0,
                metric="task_plan_completed",
                notes="Task planning completed through permission and risk checks.",
            )
        )
        self.traces.complete_run(run.run_id, WorkflowRunStatus.COMPLETED, "plan completed")
        self.audit.append(
            AuditEvent(
                event_type="task_plan_completed",
                actor_id="workflow_engine",
                action="complete_task_plan",
                task_id=task.task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="planned",
                output_ref=run.run_id,
            )
        )
        return TaskPlanningResult(task, output, False, False)

    def _block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
    ) -> TaskPlanningResult:
        task.transition(TaskStatus.BLOCKED)
        self._record_step(
            run_id,
            task,
            step,
            WorkflowStepStatus.BLOCKED,
            risk_level,
            ApprovalStatus.BLOCKED,
            reason,
            reason,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        self._audit(step, task, risk_level, ApprovalStatus.BLOCKED, reason, reason)
        self.incidents.report(
            Incident(
                title="Task planning workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=risk_level,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review the Workflow definition, Agent permission, Skill state, and risk policy.",
            )
        )
        return TaskPlanningResult(task, None, False, True)

    def _record_step(
        self,
        run_id: str,
        task: Task,
        step: WorkflowStepDefinition,
        status: WorkflowStepStatus,
        risk_level: RiskLevel,
        approval_status: ApprovalStatus,
        result: str,
        error: str | None = None,
    ) -> None:
        self.traces.append_step(
            WorkflowStep(
                run_id=run_id,
                task_id=task.task_id,
                sequence=step.sequence,
                step_name=step.step_name,
                actor_id=step.actor_id,
                action=step.action,
                status=status,
                risk_level=risk_level,
                approval_status=approval_status,
                result=result,
                error=error,
                completed_at=None if status == WorkflowStepStatus.WAITING_APPROVAL else utc_now(),
            )
        )

    def _audit(
        self,
        step: WorkflowStepDefinition,
        task: Task,
        risk_level: RiskLevel,
        approval_status: ApprovalStatus,
        result: str,
        error: str | None = None,
    ) -> None:
        self.audit.append(
            AuditEvent(
                event_type="workflow_step_recorded",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=risk_level,
                approval_status=approval_status,
                result=result,
                input_ref=self.workflow_id,
                output_ref=step.step_name,
                error=error,
            )
        )

    def _build_plan(self, task: Task) -> str:
        return (
            f"# Task Plan: {task.title}\n\n"
            f"## Goal\n\n{task.description}\n\n"
            "## Execution Steps\n\n"
            "1. Confirm scope, constraints, and expected output with Human Root.\n"
            "2. Assign the smallest capable Agent and registered Skills.\n"
            "3. Route every Tool action through permission, risk, and approval checks.\n"
            "4. Review quality, retain useful learning, and audit the outcome.\n\n"
            "## Control Boundary\n\n"
            "External, high-risk, or irreversible actions require explicit Human Root approval."
        )
