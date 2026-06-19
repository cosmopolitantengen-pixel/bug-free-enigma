from __future__ import annotations

from app.core.enums import ApprovalStatus, RiskLevel
from app.core.models import ActionRequest, ApprovalRequest, RiskAssessment, utc_now


class ApprovalCenter:
    def __init__(self, approvals: list[ApprovalRequest] | None = None) -> None:
        self._approvals: dict[str, ApprovalRequest] = {}
        for approval in approvals or []:
            self._approvals[approval.approval_id] = approval

    def request_approval(
        self,
        request: ActionRequest,
        risk: RiskAssessment,
        possible_benefit: str,
        possible_loss: str,
    ) -> ApprovalRequest:
        recommendation = "reject" if risk.level == RiskLevel.FORBIDDEN else "review"
        approval = ApprovalRequest(
            request=request,
            risk=risk,
            possible_benefit=possible_benefit,
            possible_loss=possible_loss,
            recommendation=recommendation,
        )
        if risk.blocked:
            approval.status = ApprovalStatus.BLOCKED
            approval.decided_at = utc_now()
            approval.decided_by = "risk_system"
            approval.decision_note = "blocked by forbidden action policy"
        self._approvals[approval.approval_id] = approval
        return approval

    def decide(
        self,
        approval_id: str,
        status: ApprovalStatus,
        decided_by: str,
        note: str,
    ) -> ApprovalRequest:
        approval = self._approvals[approval_id]
        if approval.status not in {ApprovalStatus.PENDING, ApprovalStatus.NEED_MORE_INFO}:
            raise ValueError("approval has already reached a final decision")
        if status not in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.MODIFIED,
            ApprovalStatus.NEED_MORE_INFO,
            ApprovalStatus.BLOCKED,
        }:
            raise ValueError("invalid approval decision")

        approval.status = status
        approval.decided_at = utc_now()
        approval.decided_by = decided_by
        approval.decision_note = note
        return approval

    def list(self) -> list[ApprovalRequest]:
        return list(self._approvals.values())

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._approvals[approval_id]
