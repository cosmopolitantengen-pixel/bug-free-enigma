from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.enums import (
    ApprovalStatus,
    PermissionLevel,
    RiskLevel,
    IncidentStatus,
    GoalStatus,
    ScheduleAction,
    ScheduleExecutionStatus,
    ScheduleStatus,
    TaskStatus,
    ToolRunStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class User:
    email: str
    password_hash: str
    role: str = "human_root"
    user_id: str = field(default_factory=lambda: new_id("user"))
    enabled: bool = True
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class Agent:
    agent_id: str
    name: str
    department: str
    role: str
    permissions: set[PermissionLevel]
    forbidden: set[str]
    allowed_skills: set[str]
    allowed_tools: set[str]
    reports_to: str
    risk_level: RiskLevel
    version: str = "1.0.0"
    enabled: bool = True


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    type: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    allowed_agents: set[str]
    risk_level: RiskLevel
    requires_approval: bool
    version: str = "1.0.0"
    enabled: bool = True


@dataclass(frozen=True)
class Tool:
    tool_id: str
    name: str
    type: str
    description: str
    action: str
    permission_level: PermissionLevel
    risk_level: RiskLevel
    requires_approval: bool
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    version: str = "1.0.0"
    enabled: bool = True


@dataclass
class Task:
    title: str
    description: str
    user_id: str = "human_root"
    task_id: str = field(default_factory=lambda: new_id("task"))
    status: TaskStatus = TaskStatus.CREATED
    result: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    approval_id: str | None = None
    history: list[TaskStatus] = field(default_factory=lambda: [TaskStatus.CREATED])

    def transition(self, status: TaskStatus) -> None:
        self.status = status
        self.history.append(status)


@dataclass
class StrategicGoal:
    title: str
    description: str
    owner_agent: str
    target_metric: str
    target_value: float
    current_value: float = 0.0
    status: GoalStatus = GoalStatus.ACTIVE
    linked_task_ids: list[str] = field(default_factory=list)
    linked_review_ids: list[str] = field(default_factory=list)
    linked_improvement_ids: list[str] = field(default_factory=list)
    goal_id: str = field(default_factory=lambda: new_id("goal"))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def progress_ratio(self) -> float:
        if self.target_value <= 0:
            return 0.0
        return min(max(self.current_value / self.target_value, 0.0), 1.0)


@dataclass(frozen=True)
class ActionRequest:
    action: str
    actor_id: str
    task_id: str | None
    permission_level: PermissionLevel
    reason: str
    target: str | None = None
    reversible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskAssessment:
    request: ActionRequest
    level: RiskLevel
    reasons: tuple[str, ...]
    requires_approval: bool
    blocked: bool


@dataclass
class ApprovalRequest:
    request: ActionRequest
    risk: RiskAssessment
    possible_benefit: str
    possible_loss: str
    recommendation: str
    approval_id: str = field(default_factory=lambda: new_id("approval"))
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor_id: str
    action: str
    task_id: str | None
    risk_level: RiskLevel
    approval_status: ApprovalStatus
    result: str
    input_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None
    model_name: str | None = None
    version: str = "1.0.0"
    event_id: str = field(default_factory=lambda: new_id("audit"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class MemoryRecord:
    task_id: str
    content: str
    memory_type: str = "task"
    record_id: str = field(default_factory=lambda: new_id("memory"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class KnowledgeDoc:
    title: str
    content: str
    source_task_id: str | None = None
    doc_id: str = field(default_factory=lambda: new_id("knowledge"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class EvaluationRecord:
    subject_type: str
    subject_id: str
    task_id: str | None
    score: float
    metric: str
    notes: str
    risk_level: RiskLevel = RiskLevel.LOW
    record_id: str = field(default_factory=lambda: new_id("evaluation"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class TaskReview:
    task_id: str
    reviewer_agent: str
    outcome: str
    summary: str
    what_went_well: str
    what_went_wrong: str
    lessons: list[str]
    follow_up_actions: list[str]
    quality_score: float
    risk_level: RiskLevel = RiskLevel.LOW
    review_id: str = field(default_factory=lambda: new_id("task_review"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ToolRun:
    tool_id: str
    actor_id: str
    action: str
    input: dict[str, Any]
    reason: str
    task_id: str | None = None
    status: ToolRunStatus = ToolRunStatus.REQUESTED
    result: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    approval_id: str | None = None
    error: str | None = None
    run_id: str = field(default_factory=lambda: new_id("tool_run"))
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None


@dataclass
class WorkflowRun:
    workflow_id: str
    task_id: str
    status: WorkflowRunStatus = WorkflowRunStatus.RUNNING
    result: str | None = None
    run_id: str = field(default_factory=lambda: new_id("workflow_run"))
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None


@dataclass
class WorkflowStep:
    run_id: str
    task_id: str
    sequence: int
    step_name: str
    actor_id: str
    action: str
    status: WorkflowStepStatus
    risk_level: RiskLevel
    approval_status: ApprovalStatus
    result: str
    error: str | None = None
    step_id: str = field(default_factory=lambda: new_id("workflow_step"))
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None


@dataclass(frozen=True)
class ModelUsageRecord:
    model_name: str
    provider: str
    actor_id: str
    task_id: str | None
    purpose: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    input_ref: str
    output_ref: str
    record_id: str = field(default_factory=lambda: new_id("model_usage"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class BudgetPolicy:
    name: str = "Default Model Budget"
    max_tokens_per_call: int = 2_000
    max_total_tokens: int = 100_000
    max_estimated_cost: float = 10.0
    cost_per_token: float = 0.000001
    currency: str = "USD"
    enabled: bool = True
    policy_id: str = field(default_factory=lambda: new_id("budget_policy"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class BudgetCheck:
    allowed: bool
    reason: str
    estimated_tokens: int
    estimated_cost: float
    policy_id: str


@dataclass(frozen=True)
class CostLog:
    source_type: str
    source_id: str
    actor_id: str
    task_id: str | None
    tokens: int
    amount: float
    currency: str
    result: str
    reason: str
    record_id: str = field(default_factory=lambda: new_id("cost_log"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class Incident:
    title: str
    description: str
    source_type: str
    source_id: str
    risk_level: RiskLevel
    status: IncidentStatus = IncidentStatus.OPEN
    task_id: str | None = None
    actor_id: str | None = None
    recommendation: str = "Review the blocked action and decide whether policy, permissions, or task input should change."
    incident_id: str = field(default_factory=lambda: new_id("incident"))
    created_at: datetime = field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None


@dataclass(frozen=True)
class BackupRecord:
    reason: str
    actor_id: str
    snapshot: dict[str, Any]
    rollback_plan: str
    backup_checksum: str | None = None
    backup_id: str = field(default_factory=lambda: new_id("backup"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    source_type: str
    source_id: str
    actor_id: str
    payload: dict[str, Any]
    task_id: str | None = None
    event_id: str = field(default_factory=lambda: new_id("event"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ScheduledJob:
    name: str
    action: ScheduleAction
    payload: dict[str, Any]
    created_by: str
    next_run_at: datetime
    interval_seconds: int | None = None
    max_runs: int | None = None
    schedule_id: str = field(default_factory=lambda: new_id("schedule"))
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    run_count: int = 0
    failure_count: int = 0
    last_run_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ScheduledExecution:
    schedule_id: str
    action: ScheduleAction
    status: ScheduleExecutionStatus
    actor_id: str
    output_ref: str | None = None
    error: str | None = None
    execution_id: str = field(default_factory=lambda: new_id("schedule_run"))
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AgentMessage:
    from_agent: str
    to_agent: str
    message_type: str
    content: str
    priority: str = "medium"
    requires_response: bool = False
    task_id: str | None = None
    message_id: str = field(default_factory=lambda: new_id("agent_message"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AgentMeeting:
    title: str
    organizer_agent: str
    participant_agents: list[str]
    agenda: str
    meeting_type: str = "group"
    task_id: str | None = None
    minutes: str | None = None
    meeting_id: str = field(default_factory=lambda: new_id("agent_meeting"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class TaskHandoff:
    task_id: str
    from_agent: str
    to_agent: str
    reason: str
    task_status: TaskStatus
    instructions: str | None = None
    message_id: str | None = None
    handoff_id: str = field(default_factory=lambda: new_id("task_handoff"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AgentBroadcast:
    from_agent: str
    audience_agents: list[str]
    event_type: str
    title: str
    content: str
    priority: str = "medium"
    task_id: str | None = None
    broadcast_id: str = field(default_factory=lambda: new_id("agent_broadcast"))
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class AgentConflict:
    raised_by_agent: str
    opposing_agents: list[str]
    issue: str
    positions: dict[str, str]
    priority_area: str = "safety"
    task_id: str | None = None
    status: str = "open"
    resolution: str | None = None
    resolved_by: str | None = None
    selected_position_agent: str | None = None
    conflict_id: str = field(default_factory=lambda: new_id("agent_conflict"))
    created_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None
