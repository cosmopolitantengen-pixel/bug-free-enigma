from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import ActionDecision, PermissionLevel
from app.core.models import ActionRequest, Agent


ROOT_ONLY_ACTIONS = {
    "delete_audit_log",
    "modify_audit_log",
    "disable_risk_system",
    "modify_root_permissions",
    "execute_payment",
    "execute_refund",
    "change_password",
    "export_all_private_data",
}


PERMISSION_ORDER = {
    PermissionLevel.L0_READ: 0,
    PermissionLevel.L1_DRAFT: 1,
    PermissionLevel.L2_INTERNAL_WRITE: 2,
    PermissionLevel.L3_EXTERNAL_PREPARE: 3,
    PermissionLevel.L4_HIGH_RISK: 4,
    PermissionLevel.L5_ROOT: 5,
}


@dataclass(frozen=True)
class PermissionResult:
    decision: ActionDecision
    reason: str


class PermissionEngine:
    def evaluate(self, agent: Agent, request: ActionRequest) -> PermissionResult:
        if not agent.enabled:
            return PermissionResult(ActionDecision.BLOCK, "agent is disabled")

        if request.action in ROOT_ONLY_ACTIONS:
            return PermissionResult(ActionDecision.BLOCK, "action is Human Root only")

        if request.action in agent.forbidden:
            return PermissionResult(ActionDecision.BLOCK, "action is forbidden for this agent")

        agent_max_level = max(PERMISSION_ORDER[level] for level in agent.permissions)
        requested_level = PERMISSION_ORDER[request.permission_level]
        if requested_level > agent_max_level:
            return PermissionResult(ActionDecision.BLOCK, "permission level exceeds agent boundary")

        if request.permission_level in {
            PermissionLevel.L3_EXTERNAL_PREPARE,
            PermissionLevel.L4_HIGH_RISK,
        }:
            return PermissionResult(ActionDecision.REQUIRE_APPROVAL, "action requires approval")

        return PermissionResult(ActionDecision.ALLOW, "permission allowed")
