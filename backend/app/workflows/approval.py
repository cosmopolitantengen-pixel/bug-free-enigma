from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.agents.registry import AgentRegistry
from app.approvals.service import ApprovalCenter
from app.audit.log import AuditLog
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
    Incident,
    Task,
    WorkflowStep,
    WorkflowStepDefinition,
    utc_now,
)
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.permissions.engine import PermissionEngine
from app.safety.risk import RiskEngine
from app.services.serializers import to_plain
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class ApprovalWorkflowResult:
    task: Task
    output: str
    outcome: str
    approval_required: bool
    blocked: bool
    approval: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    incident: dict[str, Any] | None = None


class ApprovalWorkflow:
    workflow_id = "approval_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        agents: AgentRegistry,
        permissions: PermissionEngine,
        risks: RiskEngine,
        approvals: ApprovalCenter,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.agents = agents
        self.permissions = permissions
        self.risks = risks
        self.approvals = approvals
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict[str, Any]] | None = None
        self._approval_requester: Callable[..., dict[str, Any]] | None = None

    def set_skill_executor(
        self,
        executor: Callable[[str, str, dict, str, str], dict[str, Any]],
    ) -> None:
        self._skill_executor = executor

    def set_approval_requester(self, requester: Callable[..., dict[str, Any]]) -> None:
        self._approval_requester = requester

    def validate_input(self, payload: dict[str, Any], fallback_reason: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("approval input must be an object")
        action = str(payload.get("action", "")).strip()
        actor_id = str(payload.get("actor_id", "ceo_agent_v1")).strip()
        reason = str(payload.get("reason", fallback_reason)).strip()
        target = str(payload.get("target", "")).strip() or None
        if not action:
            raise ValueError("approval action is required")
        if not actor_id:
            raise ValueError("approval actor_id is required")
        self.agents.get(actor_id)
        if not reason:
            raise ValueError("approval reason is required")
        try:
            permission_level = PermissionLevel(
                payload.get("permission_level", PermissionLevel.L1_DRAFT.value)
            )
        except ValueError as exc:
            raise ValueError("approval permission_level is invalid") from exc
        reversible = payload.get("reversible", True)
        if not isinstance(reversible, bool):
            raise ValueError("approval reversible must be a boolean")
        return {
            "action": action,
            "actor_id": actor_id,
            "permission_level": permission_level,
            "reason": reason,
            "target": target,
            "possible_benefit": str(
                payload.get("possible_benefit", "Complete the requested action.")
            ).strip(),
            "possible_loss": str(
                payload.get("possible_loss", "Unsafe or unauthorized action.")
            ).strip(),
            "reversible": reversible,
        }

    def run(self, task: Task, payload: dict[str, Any]) -> ApprovalWorkflowResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("approval workflow requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("approval workflow is disabled")
        if self._skill_executor is None or self._approval_requester is None:
            raise RuntimeError("approval Workflow runtime is not configured")
        data = self.validate_input(payload, task.description)
        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.IN_PROGRESS)
        prepare_step, risk_step, audit_step = definition.steps

        for step in (prepare_step, risk_step):
            control_error = self._check_step_control(task, step)
            if control_error:
                return self._control_block(task, run.run_id, step, control_error)
            skill_input = (
                {
                    "action": data["action"],
                    "reason": data["reason"],
                    "target": data["target"] or "unspecified",
                }
                if step is prepare_step
                else {"action": data["action"]}
            )
            try:
                output = self._execute_step(task, step, skill_input, definition.name)
            except (PermissionError, ValueError) as exc:
                return self._control_block(task, run.run_id, step, str(exc))
            result = (
                "approval request prepared"
                if step is prepare_step
                else f"risk reviewed at {output.get('risk_level', RiskLevel.LOW.value)}"
            )
            self._record_step(run.run_id, task, step, WorkflowStepStatus.COMPLETED, result)
            self._audit_step(task, step, result, None)

        requested = self._approval_requester(
            action=data["action"],
            actor_id=data["actor_id"],
            permission_level=data["permission_level"],
            reason=data["reason"],
            task_id=task.task_id,
            target=data["target"],
            possible_benefit=data["possible_benefit"],
            possible_loss=data["possible_loss"],
            reversible=data["reversible"],
        )
        approval = requested["approval"]
        if requested["result"] == "approval_required":
            task.result = "Action is waiting for Human Root approval."
            task.risk_level = RiskLevel(requested["risk"]["level"])
            task.approval_id = approval["approval_id"]
            task.transition(TaskStatus.NEEDS_APPROVAL)
            self._record_step(
                run.run_id,
                task,
                audit_step,
                WorkflowStepStatus.WAITING_APPROVAL,
                f"waiting for decision: {approval['approval_id']}",
                approval_status=ApprovalStatus.PENDING,
            )
            self.traces.complete_run(
                run.run_id,
                WorkflowRunStatus.WAITING_APPROVAL,
                task.result,
            )
            self.audit.append(
                AuditEvent(
                    event_type="approval_workflow_waiting_decision",
                    actor_id=data["actor_id"],
                    action=data["action"],
                    task_id=task.task_id,
                    risk_level=task.risk_level,
                    approval_status=ApprovalStatus.PENDING,
                    result="waiting_approval",
                    output_ref=approval["approval_id"],
                )
            )
            return ApprovalWorkflowResult(
                task,
                task.result,
                "waiting_approval",
                True,
                False,
                approval,
                requested["risk"],
            )
        return self._audit_and_finish(
            task,
            run.run_id,
            audit_step,
            requested["result"],
            approval,
            requested["risk"],
            requested["incident"],
        )

    def resume_after_decision(self, task: Task) -> ApprovalWorkflowResult:
        if task.status != TaskStatus.NEEDS_APPROVAL:
            raise ValueError("task is not waiting for Approval Workflow decision")
        if not task.approval_id:
            raise ValueError("task has no Approval Workflow approval")
        approval = self.approvals.get(task.approval_id)
        if approval.status in {ApprovalStatus.PENDING, ApprovalStatus.NEED_MORE_INFO}:
            raise ValueError("approval decision is not final")
        run = self.traces.latest_run_for_task(task.task_id, self.workflow_id)
        if run is None or run.status != WorkflowRunStatus.WAITING_APPROVAL:
            raise ValueError("task has no waiting Approval Workflow run")
        audit_step = self.workflows.get(self.workflow_id).steps[2]
        result = (
            "approved"
            if approval.status in {ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED}
            else "rejected"
            if approval.status == ApprovalStatus.REJECTED
            else "blocked"
        )
        return self._audit_and_finish(
            task,
            run.run_id,
            audit_step,
            result,
            to_plain(approval),
            to_plain(approval.risk),
            None,
        )

    def _audit_and_finish(
        self,
        task: Task,
        run_id: str,
        audit_step: WorkflowStepDefinition,
        result: str,
        approval: dict[str, Any] | None,
        risk: dict[str, Any],
        incident: dict[str, Any] | None,
    ) -> ApprovalWorkflowResult:
        control_error = self._check_step_control(task, audit_step)
        if control_error:
            return self._control_block(task, run_id, audit_step, control_error)
        approval_status = (
            ApprovalStatus(approval["status"])
            if approval
            else ApprovalStatus.NOT_REQUIRED
        )
        decision_risk = RiskLevel(risk["level"])
        task.risk_level = decision_risk
        try:
            self._execute_step(
                task,
                audit_step,
                {
                    "event": {
                        "event_type": "approval_workflow_decision",
                        "task_id": task.task_id,
                        "approval_id": approval.get("approval_id") if approval else None,
                        "decision": approval_status.value,
                        "result": result,
                    }
                },
                self.workflows.get(self.workflow_id).name,
            )
        except (PermissionError, ValueError) as exc:
            return self._control_block(task, run_id, audit_step, str(exc))
        self._record_step(
            run_id,
            task,
            audit_step,
            WorkflowStepStatus.COMPLETED,
            f"decision audited: {approval_status.value}",
            risk_level=decision_risk,
            approval_status=approval_status,
        )
        self._audit_step(
            task,
            audit_step,
            f"decision audited: {approval_status.value}",
            approval.get("approval_id") if approval else None,
            approval_status,
        )

        blocked = result == "blocked"
        if result == "approved":
            task.transition(TaskStatus.APPROVED)
            task.transition(TaskStatus.COMPLETED)
            output = "Human Root approved the controlled action."
        elif result == "rejected":
            task.transition(TaskStatus.CANCELLED)
            output = "Human Root rejected the controlled action."
        elif blocked:
            task.transition(TaskStatus.BLOCKED)
            output = "The controlled action was blocked by policy."
        else:
            task.transition(TaskStatus.COMPLETED)
            output = "The action was allowed without Human Root approval."
        task.result = output
        run_status = WorkflowRunStatus.BLOCKED if blocked else WorkflowRunStatus.COMPLETED
        self.traces.complete_run(run_id, run_status, output)
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0,
                metric=f"approval_workflow_{result}",
                notes=output,
                risk_level=task.risk_level,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="approval_workflow_completed",
                actor_id="audit_agent_v1",
                action="complete_approval_workflow",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=approval_status,
                result=result,
                output_ref=approval.get("approval_id") if approval else run_id,
            )
        )
        return ApprovalWorkflowResult(
            task,
            output,
            result,
            False,
            blocked,
            approval,
            risk,
            incident,
        )

    def _execute_step(
        self,
        task: Task,
        step: WorkflowStepDefinition,
        skill_input: dict[str, Any],
        workflow_name: str,
    ) -> dict[str, Any]:
        return self._skill_executor(
            step.skill_id,
            step.actor_id,
            skill_input,
            f"{workflow_name}: {step.step_name}",
            task.task_id,
        )

    def _check_step_control(self, task: Task, step: WorkflowStepDefinition) -> str | None:
        agent = self.agents.get(step.actor_id)
        request = ActionRequest(
            action=step.action,
            actor_id=step.actor_id,
            task_id=task.task_id,
            permission_level=step.permission_level,
            reason=f"Approval Workflow: {step.step_name}",
            target=self.workflow_id,
        )
        permission = self.permissions.evaluate(agent, request)
        risk = self.risks.assess(request)
        if permission.decision == ActionDecision.BLOCK:
            return permission.reason
        if risk.blocked:
            return "; ".join(risk.reasons)
        if permission.decision == ActionDecision.REQUIRE_APPROVAL or risk.requires_approval:
            return "Approval Workflow control step unexpectedly requires its own approval"
        return None

    def _control_block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
    ) -> ApprovalWorkflowResult:
        task.result = reason
        task.risk_level = RiskLevel.MEDIUM
        task.transition(TaskStatus.BLOCKED)
        self._record_step(
            run_id,
            task,
            step,
            WorkflowStepStatus.BLOCKED,
            reason,
            reason,
            RiskLevel.MEDIUM,
            ApprovalStatus.BLOCKED,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Approval Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review approval input, Agent permissions, Skill state, and audit controls.",
            )
        )
        incident_payload = to_plain(incident)
        self.audit.append(
            AuditEvent(
                event_type="approval_workflow_blocked",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.BLOCKED,
                result=reason,
                output_ref=incident.incident_id,
                error=reason,
            )
        )
        return ApprovalWorkflowResult(
            task,
            reason,
            "control_blocked",
            False,
            True,
            incident=incident_payload,
        )

    def _record_step(
        self,
        run_id: str,
        task: Task,
        step: WorkflowStepDefinition,
        status: WorkflowStepStatus,
        result: str,
        error: str | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED,
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

    def _audit_step(
        self,
        task: Task,
        step: WorkflowStepDefinition,
        result: str,
        output_ref: str | None,
        approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED,
    ) -> None:
        self.audit.append(
            AuditEvent(
                event_type="workflow_step_recorded",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=approval_status,
                result=result,
                input_ref=self.workflow_id,
                output_ref=output_ref,
            )
        )
