from __future__ import annotations

from dataclasses import dataclass

from app.core.models import Incident
from app.services.serializers import to_plain


@dataclass(frozen=True)
class Runbook:
    runbook_id: str
    title: str
    description: str
    owner_agent: str
    severity: str
    applies_to_sources: tuple[str, ...]
    triggers: tuple[str, ...]
    immediate_actions: tuple[str, ...]
    verification_steps: tuple[str, ...]
    escalation_policy: str


class RunbookCatalog:
    def __init__(self, runbooks: tuple[Runbook, ...] | None = None) -> None:
        self._runbooks = runbooks or DEFAULT_RUNBOOKS
        self._by_id = {runbook.runbook_id: runbook for runbook in self._runbooks}

    def list(self) -> list[dict]:
        return [to_plain(runbook) for runbook in self._runbooks]

    def get(self, runbook_id: str) -> dict:
        return to_plain(self._by_id[runbook_id])

    def match_incident(self, incident: Incident) -> dict:
        source = incident.source_type
        title = incident.title.lower()
        description = incident.description.lower()
        if source == "schedule":
            return self.get("scheduler_failure_response")
        if source == "backup":
            return self.get("backup_integrity_response")
        if source == "model_usage":
            if "budget" in title or "budget" in description or "blocked" in title:
                return self.get("budget_guard_response")
            return self.get("provider_failure_response")
        if source in SAFETY_CONTROL_SOURCES:
            return self.get("safety_control_response")
        return self.get("general_incident_triage")


SAFETY_CONTROL_SOURCES = {
    "approval",
    "tool_run",
    "skill_run",
    "task",
    "budget_policy",
    "agent_conflict",
    "agent_broadcast",
    "task_handoff",
}


DEFAULT_RUNBOOKS = (
    Runbook(
        runbook_id="general_incident_triage",
        title="General Incident Triage",
        description="Default response for operational incidents that do not map to a specialized runbook.",
        owner_agent="risk_agent_v1",
        severity="medium",
        applies_to_sources=("incident",),
        triggers=("An Incident is open and no specialized source mapping applies.",),
        immediate_actions=(
            "Acknowledge the Incident so other operators know it is being handled.",
            "Read the Incident description, source ID, Audit records, and related task context.",
            "Decide whether the affected work should stay paused, be retried, or be cancelled.",
        ),
        verification_steps=(
            "Confirm the source object still exists and its current state matches the Incident.",
            "Check recent Audit and Domain Event records for repeated failures.",
            "Resolve only after the operator decision and evidence are recorded.",
        ),
        escalation_policy="Escalate to Human Root when the source is unclear, repeated, or high risk.",
    ),
    Runbook(
        runbook_id="safety_control_response",
        title="Safety Control Response",
        description="Response for permission, approval, Skill, Tool, Workflow, and Agent communication blocks.",
        owner_agent="risk_agent_v1",
        severity="high",
        applies_to_sources=tuple(sorted(SAFETY_CONTROL_SOURCES)),
        triggers=("A protected action was blocked by Permission, Risk, Approval, or runtime revalidation.",),
        immediate_actions=(
            "Keep the blocked action paused; do not bypass Permission or Approval checks.",
            "Inspect the actor, requested action, permission level, risk reasons, and approval status.",
            "If the request is valid, adjust policy through Human Root approval or ask the actor to retry with narrower scope.",
        ),
        verification_steps=(
            "Confirm a matching Audit record exists for the blocked action.",
            "Confirm no Tool, Skill, or Workflow result was completed after the block.",
            "Resolve after policy, actor permissions, or task input have been corrected or the action is rejected.",
        ),
        escalation_policy="Human Root must decide high or forbidden-risk actions before retry.",
    ),
    Runbook(
        runbook_id="scheduler_failure_response",
        title="Scheduler Failure Response",
        description="Response for failed scheduled jobs, Redis/RQ queue problems, and repeated schedule execution failures.",
        owner_agent="workflow_agent_v1",
        severity="high",
        applies_to_sources=("schedule",),
        triggers=("A ScheduledExecution failed or scheduler queue health reports degraded/failed.",),
        immediate_actions=(
            "Pause the affected schedule when repeated failures could create duplicate work.",
            "Inspect schedule payload, target task state, execution history, queue health, and worker logs.",
            "Fix the payload, target task, budget policy, or worker configuration before resuming.",
        ),
        verification_steps=(
            "Confirm the failed execution has a clear error and corresponding Domain Event.",
            "Run a controlled scheduler tick or queue health check after the fix.",
            "Resume only when the next execution can complete without duplicating unsafe work.",
        ),
        escalation_policy="Escalate to Human Root if the schedule mutates important state or fails twice in a row.",
    ),
    Runbook(
        runbook_id="provider_failure_response",
        title="Provider Failure Response",
        description="Response for model or embedding provider failures.",
        owner_agent="tech_agent_v1",
        severity="medium",
        applies_to_sources=("model_usage",),
        triggers=("A model generation or embedding request failed after budget approval.",),
        immediate_actions=(
            "Check provider configuration, credentials, endpoint health, allowed model, and timeout settings.",
            "Keep fallback lexical search or local provider behavior enabled where available.",
            "Avoid retry loops until the provider error is understood.",
        ),
        verification_steps=(
            "Confirm provider status endpoint reports the intended provider and model.",
            "Run a small controlled request after configuration changes.",
            "Confirm model usage, cost logs, and Audit records match the retry outcome.",
        ),
        escalation_policy="Escalate if credentials may be invalid, leaked, or shared across environments.",
    ),
    Runbook(
        runbook_id="budget_guard_response",
        title="Budget Guard Response",
        description="Response for model calls blocked by token or cost policy.",
        owner_agent="finance_agent_v1",
        severity="medium",
        applies_to_sources=("model_usage", "budget_policy"),
        triggers=("A model or embedding request was blocked by active BudgetPolicy limits.",),
        immediate_actions=(
            "Review prompt size, purpose, actor, and remaining budget before changing limits.",
            "Prefer reducing scope or splitting work before increasing budget.",
            "Only Human Root may update budget policy.",
        ),
        verification_steps=(
            "Confirm a blocked CostLog exists and no ModelUsage record was written for the rejected call.",
            "Confirm the active BudgetPolicy matches the intended deployment limits.",
            "Resolve after the request is narrowed, cancelled, or explicitly re-budgeted.",
        ),
        escalation_policy="Escalate to Human Root for any budget increase or repeated over-budget pattern.",
    ),
    Runbook(
        runbook_id="backup_integrity_response",
        title="Backup Integrity Response",
        description="Response for failed backup verification or blocked restore attempts.",
        owner_agent="audit_agent_v1",
        severity="critical",
        applies_to_sources=("backup",),
        triggers=("A backup checksum verification fails or restore is blocked by integrity checks.",),
        immediate_actions=(
            "Do not restore the affected backup.",
            "Create or identify a verified checkpoint before any further restore attempt.",
            "Inspect storage, checksum history, and Audit records for tampering or corruption indicators.",
        ),
        verification_steps=(
            "Confirm a separate backup verifies successfully before continuing operations.",
            "Confirm the failed restore request remains blocked or rejected.",
            "Resolve only after a verified recovery path exists.",
        ),
        escalation_policy="Human Root must approve any restore path after an integrity failure.",
    ),
)
