from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.enums import PermissionLevel, ProposalStatus, RiskLevel, SandboxStatus
from app.core.models import new_id, utc_now
from app.safety.external_content import inspect_external_content


@dataclass
class SkillProposal:
    name: str
    description: str
    requested_by_agent: str
    risk_level: RiskLevel
    requires_approval: bool
    proposal_id: str = field(default_factory=lambda: new_id("skill_proposal"))
    enabled_by_default: bool = False
    status: ProposalStatus = ProposalStatus.PROPOSED
    approval_id: str | None = None
    sandbox_status: SandboxStatus = SandboxStatus.NOT_RUN
    sandbox_notes: str | None = None
    sandboxed_at: datetime | None = None


@dataclass
class AgentProposal:
    name: str
    department: str
    role: str
    proposed_permissions: set[PermissionLevel]
    proposed_skills: set[str]
    risk_level: RiskLevel
    proposal_id: str = field(default_factory=lambda: new_id("agent_proposal"))
    enabled_by_default: bool = False
    status: ProposalStatus = ProposalStatus.PROPOSED
    approval_id: str | None = None
    sandbox_status: SandboxStatus = SandboxStatus.NOT_RUN
    sandbox_notes: str | None = None
    sandboxed_at: datetime | None = None


@dataclass
class ImprovementProposal:
    source_review_id: str
    task_id: str
    proposed_by_agent: str
    target_type: str
    title: str
    description: str
    rationale: str
    lessons: list[str]
    follow_up_actions: list[str]
    risk_level: RiskLevel
    requires_approval: bool
    proposal_id: str = field(default_factory=lambda: new_id("improvement_proposal"))
    enabled_by_default: bool = False
    status: ProposalStatus = ProposalStatus.PROPOSED
    approval_id: str | None = None
    sandbox_status: SandboxStatus = SandboxStatus.NOT_RUN
    sandbox_notes: str | None = None
    sandboxed_at: datetime | None = None


@dataclass
class GitHubAbsorption:
    repo_url: str
    requested_by_agent: str
    summary: str
    readme_excerpt: str
    license_name: str
    maintenance_signal: str
    external_content_findings: list[str]
    security_findings: list[str]
    recommended_capabilities: list[str]
    risk_level: RiskLevel
    requires_approval: bool = True
    proposal_id: str = field(default_factory=lambda: new_id("github_absorption"))
    status: ProposalStatus = ProposalStatus.PROPOSED
    approval_id: str | None = None
    sandbox_status: SandboxStatus = SandboxStatus.NOT_RUN
    sandbox_notes: str | None = None
    sandboxed_at: datetime | None = None
    registered_doc_id: str | None = None


class CapabilityGapDetector:
    def missing_skill(self, capability: str, requested_by_agent: str, risk_level: RiskLevel) -> SkillProposal:
        return SkillProposal(
            name=f"{capability} Skill",
            description=f"Proposed controlled Skill for capability: {capability}",
            requested_by_agent=requested_by_agent,
            risk_level=risk_level,
            requires_approval=risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.FORBIDDEN},
        )

    def missing_agent(self, role: str, department: str, repeated_reason: str) -> AgentProposal:
        return AgentProposal(
            name=f"{role} Agent",
            department=department,
            role=f"Proposed Agent for repeated need: {repeated_reason}",
            proposed_permissions={PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT},
            proposed_skills=set(),
            risk_level=RiskLevel.MEDIUM,
        )

    def review_improvement(
        self,
        source_review_id: str,
        task_id: str,
        proposed_by_agent: str,
        target_type: str,
        title: str,
        description: str,
        rationale: str,
        lessons: list[str],
        follow_up_actions: list[str],
        risk_level: RiskLevel,
    ) -> ImprovementProposal:
        return ImprovementProposal(
            source_review_id=source_review_id,
            task_id=task_id,
            proposed_by_agent=proposed_by_agent,
            target_type=target_type,
            title=title,
            description=description,
            rationale=rationale,
            lessons=lessons,
            follow_up_actions=follow_up_actions,
            risk_level=risk_level,
            requires_approval=True,
        )

    def github_absorption(
        self,
        repo_url: str,
        requested_by_agent: str,
        readme: str,
        license_name: str,
        maintenance_signal: str,
    ) -> GitHubAbsorption:
        clean_url = repo_url.strip()
        clean_readme = readme.strip()
        inspection = inspect_external_content(clean_readme, clean_url, "github_readme")
        security_findings = _github_security_findings(clean_readme)
        license_risk = _license_risk(license_name)
        risk_level = max(
            [inspection.risk_level, license_risk] + ([RiskLevel.HIGH] if security_findings else []),
            key=_risk_rank,
        )
        return GitHubAbsorption(
            repo_url=clean_url,
            requested_by_agent=requested_by_agent,
            summary=_summarize_readme(clean_readme),
            readme_excerpt=clean_readme[:1200],
            license_name=license_name.strip() or "unknown",
            maintenance_signal=maintenance_signal.strip() or "unknown",
            external_content_findings=inspection.findings,
            security_findings=security_findings,
            recommended_capabilities=_recommended_capabilities(clean_readme),
            risk_level=risk_level,
        )


class ProposalSandbox:
    def test_skill(self, proposal: SkillProposal, known_agent_ids: set[str]) -> SkillProposal:
        if proposal.risk_level == RiskLevel.FORBIDDEN:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Forbidden-risk Skills cannot pass sandbox."
        elif proposal.requested_by_agent not in known_agent_ids:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Requested Agent does not exist in the registry."
        else:
            proposal.sandbox_status = SandboxStatus.PASSED
            proposal.sandbox_notes = "Deterministic sandbox passed: schema, Agent reference, and risk boundary are acceptable."
        proposal.sandboxed_at = utc_now()
        return proposal

    def test_agent(self, proposal: AgentProposal) -> AgentProposal:
        if proposal.risk_level == RiskLevel.FORBIDDEN:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Forbidden-risk Agents cannot pass sandbox."
        elif PermissionLevel.L5_ROOT in proposal.proposed_permissions:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Proposed Agent requests Root permissions."
        else:
            proposal.sandbox_status = SandboxStatus.PASSED
            proposal.sandbox_notes = "Deterministic sandbox passed: permission boundary and risk level are acceptable."
        proposal.sandboxed_at = utc_now()
        return proposal

    def test_improvement(self, proposal: ImprovementProposal) -> ImprovementProposal:
        if proposal.risk_level == RiskLevel.FORBIDDEN:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Forbidden-risk improvements cannot pass sandbox."
        elif proposal.target_type not in {"skill", "agent", "workflow", "policy", "dashboard", "memory", "knowledge"}:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Improvement target type is not recognized."
        elif not proposal.lessons and not proposal.follow_up_actions:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Improvement must be grounded in at least one lesson or follow-up action."
        else:
            proposal.sandbox_status = SandboxStatus.PASSED
            proposal.sandbox_notes = "Deterministic sandbox passed: review linkage, target type, and risk boundary are acceptable."
        proposal.sandboxed_at = utc_now()
        return proposal

    def test_github_absorption(self, proposal: GitHubAbsorption, known_agent_ids: set[str]) -> GitHubAbsorption:
        if proposal.requested_by_agent not in known_agent_ids:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Requested Agent does not exist in the registry."
        elif not proposal.repo_url.startswith(("https://github.com/", "https://www.github.com/")):
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Only GitHub repository URLs are accepted for the first absorber."
        elif proposal.risk_level == RiskLevel.FORBIDDEN:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Forbidden-risk repositories cannot pass sandbox."
        elif _license_risk(proposal.license_name) == RiskLevel.HIGH:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Repository license is unknown or not compatible enough for absorption."
        elif proposal.security_findings:
            proposal.sandbox_status = SandboxStatus.FAILED
            proposal.sandbox_notes = "Security-sensitive repository signals require manual analysis outside automatic absorption."
        else:
            proposal.sandbox_status = SandboxStatus.PASSED
            proposal.sandbox_notes = "Deterministic sandbox passed: URL, license, security signals, and external-content boundary are acceptable."
        proposal.sandboxed_at = utc_now()
        return proposal


def _risk_rank(level: RiskLevel) -> int:
    return {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.FORBIDDEN: 3,
    }[level]


def _license_risk(license_name: str) -> RiskLevel:
    normalized = license_name.strip().lower()
    if not normalized or normalized in {"unknown", "none", "proprietary"}:
        return RiskLevel.HIGH
    if any(item in normalized for item in {"gpl", "agpl", "lgpl", "sspl"}):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _github_security_findings(readme: str) -> list[str]:
    lowered = readme.lower()
    checks = {
        "execute arbitrary code": "mentions arbitrary code execution",
        "disable antivirus": "mentions disabling security software",
        "bypass captcha": "mentions captcha bypass",
        "credential": "mentions credential handling",
        "steal token": "mentions token theft",
        "scrape": "mentions scraping behavior",
    }
    return [finding for needle, finding in checks.items() if needle in lowered]


def _recommended_capabilities(readme: str) -> list[str]:
    lowered = readme.lower()
    capabilities = []
    if "test" in lowered:
        capabilities.append("testing")
    if "document" in lowered or "docs" in lowered:
        capabilities.append("documentation")
    if "api" in lowered:
        capabilities.append("api-integration")
    if "database" in lowered or "sql" in lowered:
        capabilities.append("database")
    if "github" in lowered:
        capabilities.append("github-workflow")
    return capabilities or ["knowledge-reference"]


def _summarize_readme(readme: str) -> str:
    first_line = next((line.strip() for line in readme.splitlines() if line.strip()), "")
    return first_line[:240] or "No README summary available."
