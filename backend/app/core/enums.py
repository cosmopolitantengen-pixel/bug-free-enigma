from __future__ import annotations

from enum import Enum


class PermissionLevel(str, Enum):
    L0_READ = "L0_READ"
    L1_DRAFT = "L1_DRAFT"
    L2_INTERNAL_WRITE = "L2_INTERNAL_WRITE"
    L3_EXTERNAL_PREPARE = "L3_EXTERNAL_PREPARE"
    L4_HIGH_RISK = "L4_HIGH_RISK"
    L5_ROOT = "L5_ROOT"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FORBIDDEN = "forbidden"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    NEED_MORE_INFO = "need_more_info"
    BLOCKED = "blocked"


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_SKILL = "waiting_skill"
    WAITING_AGENT = "waiting_agent"
    WAITING_TOOL = "waiting_tool"
    NEEDS_REVIEW = "needs_review"
    NEEDS_APPROVAL = "needs_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    QUALITY_CHECKING = "quality_checking"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    BLOCKED = "blocked"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    ROLLBACK = "rollback"
    ESCALATED = "escalated"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    AT_RISK = "at_risk"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ActionDecision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    REGISTERED = "registered"


class SandboxStatus(str, Enum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"


class ToolRunStatus(str, Enum):
    REQUESTED = "requested"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class WorkflowRunStatus(str, Enum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class WorkflowStepStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    FAILED = "failed"


class IncidentStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
