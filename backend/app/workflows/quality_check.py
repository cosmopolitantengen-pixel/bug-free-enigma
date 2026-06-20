from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.audit.log import AuditLog
from app.core.enums import ApprovalStatus, RiskLevel, TaskStatus, WorkflowRunStatus, WorkflowStepStatus
from app.core.models import AuditEvent, EvaluationRecord, Incident, Task, WorkflowStep, utc_now
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class QualityCheckResult:
    task: Task
    output: str
    approval_required: bool
    blocked: bool
    passed: bool
    incident: Incident | None = None


class QualityCheckWorkflow:
    workflow_id = "quality_check_v1"

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

    def set_skill_executor(self, executor: Callable[[str, str, dict, str, str], dict]) -> None:
        self._skill_executor = executor

    def run(self, task: Task) -> QualityCheckResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("quality check requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("quality check workflow is disabled")
        if self._skill_executor is None:
            raise RuntimeError("quality check Skill runtime is not configured")

        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.QUALITY_CHECKING)
        quality_output: dict = {}
        risk_output: dict = {}

        for step in definition.steps:
            if step.skill_id == "quality_check_skill_v1":
                skill_input = {"content": task.description}
            elif step.skill_id == "risk_check_skill_v1":
                skill_input = {"action": "review_internal_output"}
            elif step.skill_id == "audit_logging_skill_v1":
                skill_input = {
                    "event": {
                        "event_type": "quality_check_completed",
                        "task_id": task.task_id,
                        "quality_passed": quality_output.get("passed", False),
                        "risk_level": risk_output.get("risk_level", RiskLevel.LOW.value),
                    }
                }
            else:
                return self._block(task, run.run_id, step.sequence, step.step_name, step.actor_id, step.action, "unsupported Skill mapping")

            try:
                output = self._skill_executor(
                    step.skill_id,
                    step.actor_id,
                    skill_input,
                    f"{definition.name}: {step.step_name}",
                    task.task_id,
                )
            except (PermissionError, ValueError) as exc:
                return self._block(task, run.run_id, step.sequence, step.step_name, step.actor_id, step.action, str(exc))

            if step.skill_id == "quality_check_skill_v1":
                quality_output = output
                step_status = WorkflowStepStatus.COMPLETED if output.get("passed", False) else WorkflowStepStatus.FAILED
                step_result = "quality passed" if output.get("passed", False) else "quality failed"
            elif step.skill_id == "risk_check_skill_v1":
                risk_output = output
                if output.get("blocked", False):
                    return self._block(
                        task,
                        run.run_id,
                        step.sequence,
                        step.step_name,
                        step.actor_id,
                        step.action,
                        "risk Skill blocked quality review",
                        RiskLevel.FORBIDDEN,
                    )
                step_status = WorkflowStepStatus.COMPLETED
                step_result = f"risk {output.get('risk_level', RiskLevel.LOW.value)}"
            else:
                step_status = WorkflowStepStatus.COMPLETED
                step_result = "audit event prepared"
            self._step(
                run.run_id,
                task,
                step.sequence,
                step.step_name,
                step.actor_id,
                step.action,
                step_status,
                step_result,
            )

        passed = bool(quality_output.get("passed", False))
        issues = quality_output.get("issues", [])
        output = "Quality check passed." if passed else f"Quality check failed: {'; '.join(issues) or 'unspecified issue'}"
        task.result = output
        task.risk_level = RiskLevel(risk_output.get("risk_level", RiskLevel.LOW.value))
        task.transition(TaskStatus.COMPLETED if passed else TaskStatus.FAILED)
        final_status = WorkflowRunStatus.COMPLETED if passed else WorkflowRunStatus.FAILED
        self.traces.complete_run(run.run_id, final_status, output)
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0 if passed else 0.0,
                metric="quality_check_passed",
                notes=output,
                risk_level=task.risk_level,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="quality_workflow_completed",
                actor_id="workflow_engine",
                action="complete_quality_check",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="passed" if passed else "failed",
                output_ref=run.run_id,
            )
        )
        return QualityCheckResult(task, output, False, False, passed)

    def _block(
        self,
        task: Task,
        run_id: str,
        sequence: int,
        step_name: str,
        actor_id: str,
        action: str,
        reason: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
    ) -> QualityCheckResult:
        task.result = reason
        task.risk_level = risk_level
        task.transition(TaskStatus.BLOCKED)
        self._step(
            run_id,
            task,
            sequence,
            step_name,
            actor_id,
            action,
            WorkflowStepStatus.BLOCKED,
            reason,
            risk_level,
            reason,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Quality check Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=risk_level,
                task_id=task.task_id,
                actor_id=actor_id,
                recommendation="Review Skill availability, authorization, input, and risk policy before retrying.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="quality_workflow_blocked",
                actor_id=actor_id,
                action=action,
                task_id=task.task_id,
                risk_level=risk_level,
                approval_status=ApprovalStatus.BLOCKED,
                result=reason,
                output_ref=incident.incident_id,
                error=reason,
            )
        )
        return QualityCheckResult(task, reason, False, True, False, incident)

    def _step(
        self,
        run_id: str,
        task: Task,
        sequence: int,
        step_name: str,
        actor_id: str,
        action: str,
        status: WorkflowStepStatus,
        result: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        error: str | None = None,
    ) -> None:
        self.traces.append_step(
            WorkflowStep(
                run_id=run_id,
                task_id=task.task_id,
                sequence=sequence,
                step_name=step_name,
                actor_id=actor_id,
                action=action,
                status=status,
                risk_level=risk_level,
                approval_status=ApprovalStatus.BLOCKED if status == WorkflowStepStatus.BLOCKED else ApprovalStatus.NOT_REQUIRED,
                result=result,
                error=error,
                completed_at=utc_now(),
            )
        )
