from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ApprovalStatus, GoalStatus, PermissionLevel, RiskLevel, ScheduleAction


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class TaskCreateRequest(BaseModel):
    title: str
    description: str
    user_id: str = "human_root"


class StrategicGoalCreateRequest(BaseModel):
    title: str
    description: str
    owner_agent: str = "ceo_agent_v1"
    target_metric: str
    target_value: float = Field(gt=0)
    current_value: float = 0


class StrategicGoalProgressRequest(BaseModel):
    current_value: float
    status: GoalStatus | None = None
    note: str | None = None
    actor_id: str = "ceo_agent_v1"


class StrategicGoalLinkRequest(BaseModel):
    actor_id: str = "ceo_agent_v1"


class AgentCreateRequest(BaseModel):
    agent_id: str
    name: str
    department: str
    role: str
    permissions: list[PermissionLevel]
    forbidden: list[str] = Field(default_factory=list)
    allowed_skills: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    reports_to: str = "human_root"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    version: str = "1.0.0"
    enabled: bool = False


class SkillCreateRequest(BaseModel):
    skill_id: str
    name: str
    type: str
    description: str
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    allowed_agents: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    requires_approval: bool = True
    version: str = "1.0.0"
    enabled: bool = False


class ToolCreateRequest(BaseModel):
    tool_id: str
    name: str
    type: str
    description: str
    action: str
    permission_level: PermissionLevel
    risk_level: RiskLevel = RiskLevel.MEDIUM
    requires_approval: bool = True
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    version: str = "1.0.0"
    enabled: bool = False


class ToolRunRequest(BaseModel):
    tool_id: str
    actor_id: str
    input: dict = Field(default_factory=dict)
    reason: str
    task_id: str | None = None


class ToolRunCompleteRequest(BaseModel):
    completed_by: str = "human_root"
    note: str | None = None


class ModelGenerateRequest(BaseModel):
    prompt: str
    actor_id: str
    purpose: str = "manual_generation"
    task_id: str | None = None
    model_name: str = "deterministic_mock_v1"
    provider: str = "local"


class IncidentUpdateRequest(BaseModel):
    actor_id: str = "human_root"
    note: str | None = None


class BudgetPolicyUpdateRequest(BaseModel):
    actor_id: str = "human_root"
    name: str
    max_tokens_per_call: int = Field(gt=0)
    max_total_tokens: int = Field(gt=0)
    max_estimated_cost: float = Field(ge=0)
    cost_per_token: float = Field(ge=0)
    currency: str = "USD"
    enabled: bool = True


class BackupCreateRequest(BaseModel):
    actor_id: str = "human_root"
    reason: str


class BackupVerifyRequest(BaseModel):
    actor_id: str = "human_root"


class BackupRestoreRequest(BaseModel):
    actor_id: str = "human_root"
    reason: str


class BackupRestoreExecuteRequest(BaseModel):
    approval_id: str
    actor_id: str = "human_root"
    reason: str


class ScheduleCreateRequest(BaseModel):
    name: str
    action: ScheduleAction
    payload: dict
    created_by: str = "human_root"
    next_run_at: datetime
    interval_seconds: int | None = Field(default=None, ge=60)
    max_runs: int | None = Field(default=None, gt=0)


class ScheduleActorRequest(BaseModel):
    actor_id: str = "human_root"


class SchedulerTickRequest(BaseModel):
    actor_id: str = "human_root"
    now: datetime | None = None
    limit: int = Field(default=50, ge=1, le=100)


class AgentMessageCreateRequest(BaseModel):
    from_agent: str
    to_agent: str
    message_type: str = "direct"
    content: str
    priority: str = "medium"
    requires_response: bool = False
    task_id: str | None = None


class AgentMeetingCreateRequest(BaseModel):
    title: str
    organizer_agent: str
    participant_agents: list[str]
    agenda: str
    meeting_type: str = "group"
    task_id: str | None = None
    minutes: str | None = None


class TaskHandoffRequest(BaseModel):
    from_agent: str
    to_agent: str
    reason: str
    instructions: str | None = None


class AgentBroadcastCreateRequest(BaseModel):
    from_agent: str
    audience_agents: list[str]
    event_type: str
    title: str
    content: str
    priority: str = "medium"
    task_id: str | None = None


class AgentConflictCreateRequest(BaseModel):
    raised_by_agent: str
    opposing_agents: list[str]
    issue: str
    positions: dict[str, str]
    priority_area: str = "safety"
    task_id: str | None = None


class AgentConflictResolveRequest(BaseModel):
    resolved_by: str = "human_root"
    resolution: str
    selected_position_agent: str | None = None


class TaskReviewCreateRequest(BaseModel):
    task_id: str
    reviewer_agent: str = "quality_agent_v1"
    outcome: str = "reviewed"
    summary: str
    what_went_well: str = ""
    what_went_wrong: str = ""
    lessons: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    quality_score: float = Field(ge=0, le=1)
    risk_level: RiskLevel = RiskLevel.LOW


class ImprovementProposalCreateRequest(BaseModel):
    proposed_by_agent: str = "quality_agent_v1"
    target_type: str = "workflow"
    title: str
    description: str
    rationale: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW


class GitHubAbsorptionAnalyzeRequest(BaseModel):
    repo_url: str
    requested_by_agent: str = "ceo_agent_v1"
    readme: str
    license_name: str = "unknown"
    maintenance_signal: str = "unknown"


class ApprovalDecisionRequest(BaseModel):
    status: ApprovalStatus | None = None
    decided_by: str = "human_root"
    note: str


class ApprovalRequestCreate(BaseModel):
    action: str
    actor_id: str
    permission_level: PermissionLevel
    reason: str
    task_id: str | None = None
    target: str | None = None
    possible_benefit: str = "Complete the requested action."
    possible_loss: str = "Unsafe or unauthorized action."
    reversible: bool = True


class MemoryWriteRequest(BaseModel):
    task_id: str
    content: str
    memory_type: str = "manual"


class KnowledgeWriteRequest(BaseModel):
    title: str
    content: str
    source_task_id: str | None = None


class SkillSearchRequest(BaseModel):
    query: str


class MissingSkillRequest(BaseModel):
    capability: str
    requested_by_agent: str
    risk_level: RiskLevel = RiskLevel.MEDIUM


class MissingAgentRequest(BaseModel):
    role: str
    department: str
    repeated_reason: str


class RiskAssessRequest(BaseModel):
    action: str
    actor_id: str
    permission_level: PermissionLevel
    reason: str
    task_id: str | None = None
