from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.enums import RiskLevel
from app.core.models import AuditEvent, CostLog, Incident, ModelUsageRecord, ToolRun, WorkflowRun, WorkflowStep
from app.services.serializers import to_plain


StructuredLog = dict[str, Any]


def build_structured_logs(
    audit_events: list[AuditEvent],
    workflow_runs: list[WorkflowRun],
    workflow_steps: list[WorkflowStep],
    tool_runs: list[ToolRun],
    model_usage: list[ModelUsageRecord],
    cost_logs: list[CostLog],
    incidents: list[Incident],
) -> list[StructuredLog]:
    logs: list[StructuredLog] = []
    logs.extend(_audit_log(event) for event in audit_events)
    logs.extend(_workflow_run_log(run) for run in workflow_runs)
    logs.extend(_workflow_step_log(step) for step in workflow_steps)
    logs.extend(_tool_run_log(run) for run in tool_runs)
    logs.extend(_model_usage_log(record) for record in model_usage)
    logs.extend(_cost_log(record) for record in cost_logs)
    logs.extend(_incident_log(incident) for incident in incidents)
    return sorted(logs, key=lambda log: (log["timestamp"], log["source_id"]))


def _audit_log(event: AuditEvent) -> StructuredLog:
    payload = to_plain(event)
    return _log(
        timestamp=event.created_at,
        level=_level_for_risk(event.risk_level),
        category="audit",
        event_type=event.event_type,
        source_id=event.event_id,
        actor_id=event.actor_id,
        task_id=event.task_id,
        action=event.action,
        risk_level=event.risk_level,
        approval_status=event.approval_status,
        status=event.approval_status.value,
        result=event.result,
        message=f"{event.actor_id} {event.action}: {event.result}",
        payload=payload,
    )


def _workflow_run_log(run: WorkflowRun) -> StructuredLog:
    payload = to_plain(run)
    timestamp = run.completed_at or run.started_at
    return _log(
        timestamp=timestamp,
        level=_level_for_status(run.status.value),
        category="workflow",
        event_type="workflow_run",
        source_id=run.run_id,
        actor_id=None,
        task_id=run.task_id,
        action=run.workflow_id,
        risk_level=None,
        approval_status=None,
        status=run.status.value,
        result=run.result,
        message=f"{run.workflow_id} {run.status.value}",
        payload=payload,
    )


def _workflow_step_log(step: WorkflowStep) -> StructuredLog:
    payload = to_plain(step)
    timestamp = step.completed_at or step.created_at
    return _log(
        timestamp=timestamp,
        level=_level_for_status(step.status.value, step.risk_level),
        category="workflow_step",
        event_type="workflow_step",
        source_id=step.step_id,
        actor_id=step.actor_id,
        task_id=step.task_id,
        action=step.action,
        risk_level=step.risk_level,
        approval_status=step.approval_status,
        status=step.status.value,
        result=step.result,
        message=f"{step.step_name} by {step.actor_id}: {step.result}",
        payload=payload,
    )


def _tool_run_log(run: ToolRun) -> StructuredLog:
    payload = to_plain(run)
    timestamp = run.completed_at or run.created_at
    return _log(
        timestamp=timestamp,
        level=_level_for_status(run.status.value, run.risk_level),
        category="tool",
        event_type="tool_run",
        source_id=run.run_id,
        actor_id=run.actor_id,
        task_id=run.task_id,
        action=run.action,
        risk_level=run.risk_level,
        approval_status=None,
        status=run.status.value,
        result=run.error or run.result,
        message=f"{run.tool_id} {run.status.value}",
        payload=payload,
    )


def _model_usage_log(record: ModelUsageRecord) -> StructuredLog:
    payload = to_plain(record)
    return _log(
        timestamp=record.created_at,
        level="info",
        category="model",
        event_type="model_usage",
        source_id=record.record_id,
        actor_id=record.actor_id,
        task_id=record.task_id,
        action=record.purpose,
        risk_level=None,
        approval_status=None,
        status="recorded",
        result=f"{record.total_tokens} tokens / {record.estimated_cost:.9f}",
        message=f"{record.model_name} used for {record.purpose}",
        payload=payload,
    )


def _cost_log(record: CostLog) -> StructuredLog:
    payload = to_plain(record)
    return _log(
        timestamp=record.created_at,
        level="warning" if record.result == "blocked" else "info",
        category="cost",
        event_type="cost_log",
        source_id=record.record_id,
        actor_id=record.actor_id,
        task_id=record.task_id,
        action=record.source_type,
        risk_level=None,
        approval_status=None,
        status=record.result,
        result=f"{record.tokens} tokens / {record.amount:.6f} {record.currency}",
        message=record.reason,
        payload=payload,
    )


def _incident_log(incident: Incident) -> StructuredLog:
    payload = to_plain(incident)
    timestamp = incident.resolved_at or incident.acknowledged_at or incident.created_at
    return _log(
        timestamp=timestamp,
        level="error" if incident.status.value != "resolved" else "info",
        category="incident",
        event_type="incident",
        source_id=incident.incident_id,
        actor_id=incident.actor_id,
        task_id=incident.task_id,
        action=incident.source_type,
        risk_level=incident.risk_level,
        approval_status=None,
        status=incident.status.value,
        result=incident.description,
        message=f"{incident.title}: {incident.description}",
        payload=payload,
    )


def _log(
    *,
    timestamp: datetime,
    level: str,
    category: str,
    event_type: str,
    source_id: str,
    actor_id: str | None,
    task_id: str | None,
    action: str,
    risk_level: RiskLevel | None,
    approval_status: Any,
    status: str | None,
    result: str | None,
    message: str,
    payload: dict[str, Any],
) -> StructuredLog:
    return {
        "timestamp": timestamp.isoformat(),
        "level": level,
        "category": category,
        "event_type": event_type,
        "source_id": source_id,
        "actor_id": actor_id,
        "task_id": task_id,
        "action": action,
        "risk_level": risk_level.value if risk_level else None,
        "approval_status": approval_status.value if approval_status else None,
        "status": status,
        "result": result,
        "message": message,
        "payload": payload,
    }


def _level_for_risk(risk_level: RiskLevel) -> str:
    if risk_level == RiskLevel.FORBIDDEN:
        return "critical"
    if risk_level == RiskLevel.HIGH:
        return "error"
    if risk_level == RiskLevel.MEDIUM:
        return "warning"
    return "info"


def _level_for_status(status: str, risk_level: RiskLevel | None = None) -> str:
    if status in {"blocked", "failed"}:
        return "error"
    if status in {"waiting_approval", "pending"}:
        return "warning"
    if risk_level is not None:
        return _level_for_risk(risk_level)
    return "info"
