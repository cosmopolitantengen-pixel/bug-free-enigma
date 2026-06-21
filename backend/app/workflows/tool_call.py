from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.audit.log import AuditLog
from app.core.enums import (
    ApprovalStatus,
    RiskLevel,
    TaskStatus,
    ToolRunStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import AuditEvent, EvaluationRecord, Incident, Task, WorkflowStep, WorkflowStepDefinition, utc_now
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class ToolCallResult:
    task: Task
    output: str
    outcome: str
    approval_required: bool
    blocked: bool
    tool: dict[str, Any] | None = None
    tool_run: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    incident: Incident | None = None


class ToolCallWorkflow:
    workflow_id = "tool_call_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict] | None = None
        self._tool_requester: Callable[[str, str, dict, str, str], dict[str, Any]] | None = None
        self._tool_completer: Callable[[str, str, str | None], dict[str, Any]] | None = None
        self._tool_denier: Callable[[str, str], dict[str, Any]] | None = None
        self._tool_getter: Callable[[str], dict[str, Any]] | None = None

    def set_skill_executor(self, executor: Callable[[str, str, dict, str, str], dict]) -> None:
        self._skill_executor = executor

    def set_tool_requester(
        self,
        requester: Callable[[str, str, dict, str, str], dict[str, Any]],
    ) -> None:
        self._tool_requester = requester

    def set_tool_completer(
        self,
        completer: Callable[[str, str, str | None], dict[str, Any]],
    ) -> None:
        self._tool_completer = completer

    def set_tool_denier(self, denier: Callable[[str, str], dict[str, Any]]) -> None:
        self._tool_denier = denier

    def set_tool_getter(self, getter: Callable[[str], dict[str, Any]]) -> None:
        self._tool_getter = getter

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Tool Call input must be an object")
        tool_id = str(payload.get("tool_id", "")).strip()
        actor_id = str(payload.get("actor_id", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        tool_input = payload.get("tool_input", payload.get("input", {}))
        if not tool_id:
            raise ValueError("Tool Call tool_id is required")
        if not actor_id:
            raise ValueError("Tool Call actor_id is required")
        if not reason:
            raise ValueError("Tool Call reason is required")
        if not isinstance(tool_input, dict):
            raise ValueError("Tool Call tool_input must be an object")
        return {
            "tool_id": tool_id,
            "actor_id": actor_id,
            "reason": reason,
            "tool_input": tool_input,
        }

    def run(self, task: Task, payload: dict[str, Any]) -> ToolCallResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("Tool Call requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("Tool Call Workflow is disabled")
        self._ensure_runtime()
        data = self.validate_input(payload)
        tool = self._tool_getter(data["tool_id"])
        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.WAITING_TOOL)
        prepare_step, risk_step, audit_step = definition.steps

        try:
            self._skill_executor(
                prepare_step.skill_id,
                prepare_step.actor_id,
                {
                    "action": "call_tool",
                    "reason": data["reason"],
                    "target": data["tool_id"],
                },
                f"{definition.name}: {prepare_step.step_name}",
                task.task_id,
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._control_block(task, run.run_id, prepare_step, str(exc))
        self._record_step(
            run.run_id,
            task,
            prepare_step,
            WorkflowStepStatus.COMPLETED,
            "Tool call request prepared",
        )

        try:
            risk = self._skill_executor(
                risk_step.skill_id,
                risk_step.actor_id,
                {"action": tool["action"]},
                f"{definition.name}: {risk_step.step_name}",
                task.task_id,
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._control_block(task, run.run_id, risk_step, str(exc))
        risk_level = RiskLevel(risk.get("risk_level", RiskLevel.LOW.value))
        if risk.get("blocked", False):
            return self._control_block(
                task,
                run.run_id,
                risk_step,
                "risk Skill blocked Tool call",
                RiskLevel.FORBIDDEN,
            )
        self._record_step(
            run.run_id,
            task,
            risk_step,
            WorkflowStepStatus.COMPLETED,
            f"Tool risk reviewed: {risk_level.value}",
            risk_level,
        )

        try:
            requested = self._tool_requester(
                data["tool_id"],
                data["actor_id"],
                data["tool_input"],
                data["reason"],
                task.task_id,
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._control_block(task, run.run_id, risk_step, str(exc), risk_level)
        tool_run = requested["run"]
        task.risk_level = RiskLevel(tool_run["risk_level"])
        if tool_run["status"] == ToolRunStatus.WAITING_APPROVAL.value:
            return self._wait_for_approval(task, run.run_id, risk_step, requested, risk)
        return self._audit_and_finish(task, run.run_id, risk_step, audit_step, requested, risk)

    def resume_after_decision(
        self,
        task: Task,
        approval: dict[str, Any],
        tool_run: dict[str, Any],
    ) -> ToolCallResult:
        if task.status != TaskStatus.NEEDS_APPROVAL:
            raise ValueError("task is not waiting for Tool Call approval")
        run = self.traces.latest_run_for_task(task.task_id, self.workflow_id)
        if run is None or run.status != WorkflowRunStatus.WAITING_APPROVAL:
            raise ValueError("task has no waiting Tool Call Workflow run")
        if not task.approval_id or approval.get("approval_id") != task.approval_id:
            raise ValueError("Tool Call approval does not match task")
        if tool_run.get("approval_id") != task.approval_id or tool_run.get("task_id") != task.task_id:
            raise ValueError("Tool Run does not match waiting Tool Call task")
        status = ApprovalStatus(approval["status"])
        definition = self.workflows.get(self.workflow_id)
        risk_step, audit_step = definition.steps[1], definition.steps[2]
        if status in {ApprovalStatus.PENDING, ApprovalStatus.NEED_MORE_INFO}:
            raise ValueError("Tool Call approval has no final decision")
        if status == ApprovalStatus.REJECTED:
            denied = self._tool_denier(tool_run["run_id"], "Human Root rejected Tool execution.")
            return self._audit_rejection(task, run.run_id, audit_step, denied, approval)
        if status != ApprovalStatus.APPROVED:
            denied = self._tool_denier(tool_run["run_id"], f"Tool approval is {status.value}.")
            return self._audit_and_finish(
                task,
                run.run_id,
                risk_step,
                audit_step,
                denied,
                {"risk_level": tool_run["risk_level"], "blocked": True},
                approval,
            )

        task.transition(TaskStatus.APPROVED)
        task.transition(TaskStatus.EXECUTING)
        try:
            completed = self._tool_completer(
                tool_run["run_id"],
                "human_root",
                "Resume approved Tool Call Workflow.",
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._control_block(task, run.run_id, risk_step, str(exc), task.risk_level)
        return self._audit_and_finish(
            task,
            run.run_id,
            risk_step,
            audit_step,
            completed,
            {"risk_level": tool_run["risk_level"], "blocked": False},
            approval,
        )

    def _wait_for_approval(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        requested: dict[str, Any],
        risk: dict[str, Any],
    ) -> ToolCallResult:
        tool_run = requested["run"]
        approval = requested["approval"]
        task.approval_id = tool_run["approval_id"]
        task.result = "Tool Call requires Human Root approval."
        task.transition(TaskStatus.NEEDS_APPROVAL)
        self._record_step(
            run_id,
            task,
            step,
            WorkflowStepStatus.WAITING_APPROVAL,
            f"Tool Run waiting for approval: {tool_run['run_id']}",
            task.risk_level,
            ApprovalStatus.PENDING,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.WAITING_APPROVAL, task.result)
        self.audit.append(
            AuditEvent(
                event_type="tool_call_workflow_waiting_approval",
                actor_id=tool_run["actor_id"],
                action=tool_run["action"],
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.PENDING,
                result="waiting_approval",
                input_ref=tool_run["run_id"],
                output_ref=task.approval_id,
            )
        )
        return ToolCallResult(
            task,
            task.result,
            "waiting_approval",
            True,
            False,
            tool=requested["tool"],
            tool_run=tool_run,
            approval=approval,
            risk=risk,
        )

    def _audit_rejection(
        self,
        task: Task,
        run_id: str,
        audit_step: WorkflowStepDefinition,
        denied: dict[str, Any],
        approval: dict[str, Any],
    ) -> ToolCallResult:
        try:
            self._execute_audit_skill(task, audit_step, denied["run"], ApprovalStatus.REJECTED)
        except (KeyError, PermissionError, ValueError) as exc:
            return self._control_block(task, run_id, audit_step, str(exc), task.risk_level)
        self._record_step(
            run_id,
            task,
            audit_step,
            WorkflowStepStatus.COMPLETED,
            "Tool rejection audited",
            task.risk_level,
            ApprovalStatus.REJECTED,
        )
        output = "Human Root rejected Tool execution."
        task.result = output
        task.transition(TaskStatus.CANCELLED)
        self.traces.complete_run(run_id, WorkflowRunStatus.COMPLETED, output)
        self._evaluate(task, "tool_call_rejected_enforced", 1.0, output)
        self._audit_completion(task, denied["run"], ApprovalStatus.REJECTED, "rejected")
        return ToolCallResult(
            task,
            output,
            "rejected",
            False,
            False,
            tool=denied["tool"],
            tool_run=denied["run"],
            approval=approval,
        )

    def _audit_and_finish(
        self,
        task: Task,
        run_id: str,
        risk_step: WorkflowStepDefinition,
        audit_step: WorkflowStepDefinition,
        tool_result: dict[str, Any],
        risk: dict[str, Any],
        approval: dict[str, Any] | None = None,
    ) -> ToolCallResult:
        tool_run = tool_result["run"]
        approval = approval or tool_result.get("approval")
        approval_status = ApprovalStatus(approval["status"]) if approval else ApprovalStatus.NOT_REQUIRED
        tool_status = ToolRunStatus(tool_run["status"])
        if tool_status == ToolRunStatus.BLOCKED:
            self._record_step(
                run_id,
                task,
                risk_step,
                WorkflowStepStatus.BLOCKED,
                tool_run.get("error") or "Tool Run blocked",
                RiskLevel(tool_run["risk_level"]),
                approval_status,
                tool_run.get("error"),
            )
        try:
            self._execute_audit_skill(task, audit_step, tool_run, approval_status)
        except (KeyError, PermissionError, ValueError) as exc:
            return self._control_block(task, run_id, audit_step, str(exc), task.risk_level)
        self._record_step(
            run_id,
            task,
            audit_step,
            WorkflowStepStatus.COMPLETED,
            f"Tool Run audited: {tool_status.value}",
            RiskLevel(tool_run["risk_level"]),
            approval_status,
        )

        task.risk_level = RiskLevel(tool_run["risk_level"])
        if tool_status == ToolRunStatus.COMPLETED:
            outcome = "completed"
            output = f"Tool Call completed: {tool_run['run_id']}"
            task.transition(TaskStatus.COMPLETED)
            workflow_status = WorkflowRunStatus.COMPLETED
            score = 1.0
            incident = None
        elif tool_status == ToolRunStatus.FAILED:
            outcome = "failed"
            output = tool_run.get("error") or "Tool execution failed"
            task.transition(TaskStatus.FAILED)
            workflow_status = WorkflowRunStatus.FAILED
            score = 0.0
            incident = None
        else:
            outcome = "blocked"
            output = tool_run.get("error") or "Tool execution was blocked"
            task.transition(TaskStatus.BLOCKED)
            workflow_status = WorkflowRunStatus.BLOCKED
            score = 0.0
            incident = self.incidents.report(
                Incident(
                    title="Tool Call Workflow blocked",
                    description=output,
                    source_type="workflow",
                    source_id=run_id,
                    risk_level=task.risk_level,
                    task_id=task.task_id,
                    actor_id=tool_run["actor_id"],
                    recommendation="Review Tool enablement, Agent authorization, approval state, risk policy, and Tool Run evidence.",
                )
            )
        task.result = output
        self.traces.complete_run(run_id, workflow_status, output)
        self._evaluate(task, f"tool_call_{outcome}", score, output)
        self._audit_completion(task, tool_run, approval_status, outcome, incident)
        return ToolCallResult(
            task,
            output,
            outcome,
            False,
            outcome == "blocked",
            tool=tool_result["tool"],
            tool_run=tool_run,
            approval=approval,
            risk=risk,
            incident=incident,
        )

    def _execute_audit_skill(
        self,
        task: Task,
        step: WorkflowStepDefinition,
        tool_run: dict[str, Any],
        approval_status: ApprovalStatus,
    ) -> None:
        self._skill_executor(
            step.skill_id,
            step.actor_id,
            {
                "event": {
                    "event_type": "tool_call_workflow_result",
                    "task_id": task.task_id,
                    "tool_run_id": tool_run["run_id"],
                    "tool_id": tool_run["tool_id"],
                    "status": tool_run["status"],
                    "approval_status": approval_status.value,
                    "error": tool_run.get("error"),
                }
            },
            f"{self.workflows.get(self.workflow_id).name}: {step.step_name}",
            task.task_id,
        )

    def _control_block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
    ) -> ToolCallResult:
        task.result = reason
        task.risk_level = risk_level
        task.transition(TaskStatus.BLOCKED)
        self._record_step(
            run_id,
            task,
            step,
            WorkflowStepStatus.BLOCKED,
            reason,
            risk_level,
            ApprovalStatus.BLOCKED,
            reason,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Tool Call Workflow control blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=risk_level,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review Workflow Skill controls and Tool Runtime configuration before retrying.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="tool_call_workflow_blocked",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=risk_level,
                approval_status=ApprovalStatus.BLOCKED,
                result=reason,
                output_ref=incident.incident_id,
                error=reason,
            )
        )
        return ToolCallResult(task, reason, "blocked", False, True, incident=incident)

    def _record_step(
        self,
        run_id: str,
        task: Task,
        step: WorkflowStepDefinition,
        status: WorkflowStepStatus,
        result: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED,
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

    def _evaluate(self, task: Task, metric: str, score: float, notes: str) -> None:
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=score,
                metric=metric,
                notes=notes,
                risk_level=task.risk_level,
            )
        )

    def _audit_completion(
        self,
        task: Task,
        tool_run: dict[str, Any],
        approval_status: ApprovalStatus,
        outcome: str,
        incident: Incident | None = None,
    ) -> None:
        self.audit.append(
            AuditEvent(
                event_type="tool_call_workflow_completed",
                actor_id="workflow_engine",
                action="complete_tool_call_workflow",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=approval_status,
                result=outcome,
                input_ref=tool_run["run_id"],
                output_ref=incident.incident_id if incident else tool_run.get("result"),
                error=tool_run.get("error"),
            )
        )

    def _ensure_runtime(self) -> None:
        if any(
            dependency is None
            for dependency in (
                self._skill_executor,
                self._tool_requester,
                self._tool_completer,
                self._tool_denier,
                self._tool_getter,
            )
        ):
            raise RuntimeError("Tool Call Workflow runtime is not configured")
