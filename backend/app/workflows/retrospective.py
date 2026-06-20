from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.audit.log import AuditLog
from app.core.enums import ApprovalStatus, RiskLevel, TaskStatus, WorkflowRunStatus, WorkflowStepStatus
from app.core.models import AuditEvent, EvaluationRecord, Incident, KnowledgeDoc, Task, TaskReview, WorkflowStep, utc_now
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.knowledge_base.store import KnowledgeBase
from app.reviews.store import ReviewStore
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class RetrospectiveResult:
    task: Task
    output: str
    blocked: bool
    review: TaskReview | None = None
    knowledge: KnowledgeDoc | None = None
    incident: Incident | None = None


class RetrospectiveWorkflow:
    workflow_id = "retrospective_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        reviews: ReviewStore,
        knowledge: KnowledgeBase,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.reviews = reviews
        self.knowledge = knowledge
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict] | None = None

    def set_skill_executor(self, executor: Callable[[str, str, dict, str, str], dict]) -> None:
        self._skill_executor = executor

    def validate_input(self, payload: dict[str, Any], fallback_summary: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("retrospective input must be an object")
        summary = str(payload.get("summary", fallback_summary)).strip()
        if not summary:
            raise ValueError("retrospective summary is required")
        quality_score = payload.get("quality_score", 1.0)
        if isinstance(quality_score, bool) or not isinstance(quality_score, (int, float)):
            raise ValueError("retrospective quality_score must be a number")
        quality_score = float(quality_score)
        if quality_score < 0 or quality_score > 1:
            raise ValueError("retrospective quality_score must be between 0 and 1")
        lessons = self._text_list(payload.get("lessons", []), "lessons")
        follow_ups = self._text_list(payload.get("follow_up_actions", []), "follow_up_actions")
        try:
            risk_level = RiskLevel(payload.get("risk_level", RiskLevel.LOW.value))
        except ValueError as exc:
            raise ValueError("retrospective risk_level is invalid") from exc
        return {
            "source_task_id": payload.get("source_task_id"),
            "outcome": str(payload.get("outcome", "reviewed")).strip() or "reviewed",
            "summary": summary,
            "what_went_well": str(payload.get("what_went_well", "")).strip(),
            "what_went_wrong": str(payload.get("what_went_wrong", "")).strip(),
            "lessons": lessons,
            "follow_up_actions": follow_ups,
            "quality_score": quality_score,
            "risk_level": risk_level,
        }

    def run(self, task: Task, payload: dict[str, Any]) -> RetrospectiveResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("retrospective requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("retrospective workflow is disabled")
        if self._skill_executor is None:
            raise RuntimeError("retrospective Skill runtime is not configured")
        data = self.validate_input(payload, task.description)
        source_task_id = data["source_task_id"] or task.task_id
        review_content = self._review_content(data)
        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.IN_PROGRESS)

        for step in definition.steps:
            if step.skill_id == "quality_check_skill_v1":
                skill_input = {"content": review_content}
            elif step.skill_id == "memory_write_skill_v1":
                skill_input = {"task_id": source_task_id, "content": review_content}
            elif step.skill_id == "audit_logging_skill_v1":
                skill_input = {
                    "event": {
                        "event_type": "retrospective_recorded",
                        "source_task_id": source_task_id,
                        "outcome": data["outcome"],
                        "quality_score": data["quality_score"],
                    }
                }
            else:
                return self._block(task, run.run_id, step, "unsupported Skill mapping")
            try:
                output = self._skill_executor(
                    step.skill_id,
                    step.actor_id,
                    skill_input,
                    f"{definition.name}: {step.step_name}",
                    task.task_id,
                )
            except (PermissionError, ValueError) as exc:
                return self._block(task, run.run_id, step, str(exc))
            if step.skill_id == "quality_check_skill_v1" and not output.get("passed", False):
                reason = "; ".join(output.get("issues", [])) or "retrospective quality check failed"
                task.result = reason
                task.transition(TaskStatus.FAILED)
                self._step(run.run_id, task, step, WorkflowStepStatus.FAILED, reason, reason)
                self.traces.complete_run(run.run_id, WorkflowRunStatus.FAILED, reason)
                self._evaluate(task, 0.0, reason, data["risk_level"])
                return RetrospectiveResult(task, reason, False)
            self._step(run.run_id, task, step, WorkflowStepStatus.COMPLETED, "completed")

        review = self.reviews.record(
            TaskReview(
                task_id=source_task_id,
                reviewer_agent="quality_agent_v1",
                outcome=data["outcome"],
                summary=data["summary"],
                what_went_well=data["what_went_well"],
                what_went_wrong=data["what_went_wrong"],
                lessons=data["lessons"],
                follow_up_actions=data["follow_up_actions"],
                quality_score=data["quality_score"],
                risk_level=data["risk_level"],
            )
        )
        knowledge = self.knowledge.write(
            KnowledgeDoc(
                title=f"Retrospective: {task.title}",
                content=review_content,
                source_task_id=source_task_id,
            )
        )
        output = f"Retrospective recorded: {review.review_id}"
        task.result = output
        task.risk_level = data["risk_level"]
        task.transition(TaskStatus.REVIEWED)
        self.traces.complete_run(run.run_id, WorkflowRunStatus.COMPLETED, output)
        self._evaluate(task, data["quality_score"], output, data["risk_level"])
        self.audit.append(
            AuditEvent(
                event_type="retrospective_workflow_completed",
                actor_id="quality_agent_v1",
                action="record_retrospective",
                task_id=source_task_id,
                risk_level=data["risk_level"],
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=data["outcome"],
                input_ref=task.task_id,
                output_ref=review.review_id,
            )
        )
        return RetrospectiveResult(task, output, False, review, knowledge)

    def _block(self, task: Task, run_id: str, step: Any, reason: str) -> RetrospectiveResult:
        task.result = reason
        task.risk_level = RiskLevel.MEDIUM
        task.transition(TaskStatus.BLOCKED)
        self._step(run_id, task, step, WorkflowStepStatus.BLOCKED, reason, reason, RiskLevel.MEDIUM)
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Retrospective Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review retrospective input and required Skill availability before retrying.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="retrospective_workflow_blocked",
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
        return RetrospectiveResult(task, reason, True, incident=incident)

    def _step(
        self,
        run_id: str,
        task: Task,
        step: Any,
        status: WorkflowStepStatus,
        result: str,
        error: str | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
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
                approval_status=ApprovalStatus.BLOCKED if status == WorkflowStepStatus.BLOCKED else ApprovalStatus.NOT_REQUIRED,
                result=result,
                error=error,
                completed_at=utc_now(),
            )
        )

    def _evaluate(self, task: Task, score: float, notes: str, risk_level: RiskLevel) -> None:
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=score,
                metric="retrospective_quality",
                notes=notes,
                risk_level=risk_level,
            )
        )

    def _review_content(self, data: dict[str, Any]) -> str:
        return (
            f"Outcome: {data['outcome']}\n"
            f"Summary: {data['summary']}\n"
            f"What went well: {data['what_went_well'] or 'n/a'}\n"
            f"What went wrong: {data['what_went_wrong'] or 'n/a'}\n"
            f"Lessons: {', '.join(data['lessons']) or 'none'}\n"
            f"Follow-up actions: {', '.join(data['follow_up_actions']) or 'none'}\n"
            f"Quality score: {data['quality_score']}"
        )

    def _text_list(self, value: Any, field_name: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"retrospective {field_name} must be an array")
        return [str(item).strip() for item in value if str(item).strip()]
