from __future__ import annotations

from app.core.enums import PermissionLevel, RiskLevel
from app.core.models import ActionRequest, RiskAssessment


FORBIDDEN_ACTIONS = {
    "phishing",
    "credential_theft",
    "steal_token",
    "steal_cookie",
    "captcha_bypass",
    "platform_risk_bypass",
    "attack_system",
    "malicious_computer_control",
    "malicious_bulk_register",
    "malicious_mass_message",
    "ad_click_fraud",
    "money_laundering",
    "automatic_transfer",
    "illegal_scraping",
    "delete_audit_log",
    "modify_audit_log",
    "disable_risk_system",
    "modify_root_permissions",
}

HIGH_RISK_ACTIONS = {
    "execute_payment",
    "execute_refund",
    "change_password",
    "export_private_data",
    "control_local_computer",
    "execute_code",
    "publish_external_content",
    "restore_backup",
    "send_external_message",
}

MEDIUM_RISK_ACTIONS = {
    "prepare_external_message",
    "prepare_external_content",
    "call_external_api",
    "generate_contract_draft",
    "generate_quote",
    "read_customer_data",
}


class RiskEngine:
    def assess(self, request: ActionRequest) -> RiskAssessment:
        reasons: list[str] = []

        if request.action in FORBIDDEN_ACTIONS:
            reasons.append("action is forbidden by safety policy")
            return RiskAssessment(request, RiskLevel.FORBIDDEN, tuple(reasons), True, True)

        if request.action in HIGH_RISK_ACTIONS or request.permission_level == PermissionLevel.L4_HIGH_RISK:
            reasons.append("action is high risk and requires Root approval")
            return RiskAssessment(request, RiskLevel.HIGH, tuple(reasons), True, False)

        if request.action in MEDIUM_RISK_ACTIONS or request.permission_level == PermissionLevel.L3_EXTERNAL_PREPARE:
            reasons.append("action is medium risk and requires approval")
            return RiskAssessment(request, RiskLevel.MEDIUM, tuple(reasons), True, False)

        reasons.append("action is low risk")
        return RiskAssessment(request, RiskLevel.LOW, tuple(reasons), False, False)
