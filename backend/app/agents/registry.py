from __future__ import annotations

from dataclasses import replace

from app.core.enums import PermissionLevel, RiskLevel
from app.core.models import Agent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> Agent:
        if agent.agent_id in self._agents:
            raise ValueError(f"agent already registered: {agent.agent_id}")
        if PermissionLevel.L5_ROOT in agent.permissions:
            raise ValueError("Agents cannot receive L5_ROOT permission")
        self._agents[agent.agent_id] = agent
        return agent

    def restore(self, agent: Agent) -> Agent:
        if PermissionLevel.L5_ROOT in agent.permissions:
            raise ValueError("Agents cannot receive L5_ROOT permission")
        self._agents[agent.agent_id] = agent
        return agent

    def grant_skill(self, agent_id: str, skill_id: str) -> Agent:
        agent = self.get(agent_id)
        updated = replace(agent, allowed_skills=agent.allowed_skills | {skill_id})
        self._agents[agent_id] = updated
        return updated

    def get(self, agent_id: str) -> Agent:
        return self._agents[agent_id]

    def list(self) -> list[Agent]:
        return list(self._agents.values())


def default_agents() -> list[Agent]:
    common_forbidden = {
        "execute_payment",
        "execute_refund",
        "delete_audit_log",
        "modify_audit_log",
        "disable_risk_system",
        "modify_root_permissions",
    }
    internal_permissions = {
        PermissionLevel.L0_READ,
        PermissionLevel.L1_DRAFT,
        PermissionLevel.L2_INTERNAL_WRITE,
    }
    review_permissions = {PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT}
    return [
        Agent(
            agent_id="ceo_agent_v1",
            name="AI CEO",
            department="Executive",
            role="Plan tasks, coordinate agents, and summarize outcomes.",
            permissions={
                PermissionLevel.L0_READ,
                PermissionLevel.L1_DRAFT,
                PermissionLevel.L2_INTERNAL_WRITE,
                PermissionLevel.L3_EXTERNAL_PREPARE,
            },
            forbidden=common_forbidden,
            allowed_skills={"task_planning_skill_v1", "summary_skill_v1", "approval_request_skill_v1"},
            allowed_tools={"task_manager_tool", "database_read_tool", "filesystem_read_tool", "git_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="project_manager_agent_v1",
            name="Project Manager Agent",
            department="Project",
            role="Break work into steps and assign execution.",
            permissions={PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT, PermissionLevel.L2_INTERNAL_WRITE},
            forbidden=common_forbidden,
            allowed_skills={"task_planning_skill_v1", "summary_skill_v1"},
            allowed_tools={"task_manager_tool", "filesystem_read_tool", "git_read_tool"},
            reports_to="ceo_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        ),
        Agent(
            agent_id="document_agent_v1",
            name="Document Agent",
            department="Document",
            role="Create structured internal documents.",
            permissions={PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT, PermissionLevel.L2_INTERNAL_WRITE},
            forbidden=common_forbidden,
            allowed_skills={"document_writer_skill_v1", "summary_skill_v1", "rewrite_skill_v1"},
            allowed_tools={"knowledge_base_tool", "filesystem_read_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.LOW,
        ),
        Agent(
            agent_id="risk_agent_v1",
            name="Risk Agent",
            department="Safety",
            role="Assess risk and block forbidden actions.",
            permissions={PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT, PermissionLevel.L2_INTERNAL_WRITE},
            forbidden=common_forbidden,
            allowed_skills={"risk_check_skill_v1"},
            allowed_tools={"audit_read_tool", "database_read_tool", "filesystem_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="quality_agent_v1",
            name="Quality Check Agent",
            department="Quality",
            role="Check output quality before completion.",
            permissions={PermissionLevel.L0_READ, PermissionLevel.L1_DRAFT, PermissionLevel.L2_INTERNAL_WRITE},
            forbidden=common_forbidden,
            allowed_skills={"quality_check_skill_v1", "code_review_skill_v1"},
            allowed_tools={"audit_read_tool", "database_read_tool", "filesystem_read_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.LOW,
        ),
        Agent(
            agent_id="product_agent_v1",
            name="Product Agent",
            department="Product",
            role="Translate goals into product requirements and internal specifications.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"task_planning_skill_v1", "document_writer_skill_v1", "rewrite_skill_v1"},
            allowed_tools={"task_manager_tool", "knowledge_base_tool", "filesystem_read_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        ),
        Agent(
            agent_id="tech_agent_v1",
            name="Tech Agent",
            department="Engineering",
            role="Design implementation plans, generate draft code, and review technical changes.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"code_generation_skill_v1", "code_review_skill_v1", "github_project_analysis_skill_v1"},
            allowed_tools={"task_manager_tool", "filesystem_read_tool", "git_read_tool", "code_execution_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="data_agent_v1",
            name="Data Agent",
            department="Data",
            role="Clean internal datasets and prepare structured tables and summaries.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"data_cleanup_skill_v1", "spreadsheet_generation_skill_v1", "summary_skill_v1"},
            allowed_tools={"database_read_tool", "filesystem_read_tool", "knowledge_base_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        ),
        Agent(
            agent_id="legal_compliance_agent_v1",
            name="Legal and Compliance Agent",
            department="Compliance",
            role="Review internal drafts for policy, privacy, and compliance concerns.",
            permissions=review_permissions,
            forbidden=common_forbidden,
            allowed_skills={"risk_check_skill_v1", "document_writer_skill_v1", "knowledge_search_skill_v1"},
            allowed_tools={"knowledge_base_tool", "audit_read_tool", "filesystem_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="finance_assistant_agent_v1",
            name="Finance Assistant Agent",
            department="Finance",
            role="Prepare internal financial summaries without moving money or changing accounts.",
            permissions=review_permissions,
            forbidden=common_forbidden,
            allowed_skills={"data_cleanup_skill_v1", "spreadsheet_generation_skill_v1", "risk_check_skill_v1"},
            allowed_tools={"database_read_tool", "filesystem_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="memory_agent_v1",
            name="Memory Agent",
            department="Knowledge",
            role="Turn completed work and reviews into scoped, reusable internal memory.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"memory_write_skill_v1", "summary_skill_v1", "knowledge_search_skill_v1"},
            allowed_tools={"knowledge_base_tool", "database_read_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.LOW,
        ),
        Agent(
            agent_id="skill_manager_agent_v1",
            name="Skill Manager Agent",
            department="Capability",
            role="Search, compare, and compose registered Skills before proposing new capability.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"skill_search_skill_v1", "skill_composition_skill_v1", "temporary_skill_creation_skill_v1", "github_project_analysis_skill_v1"},
            allowed_tools={"database_read_tool", "audit_read_tool"},
            reports_to="ceo_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        ),
        Agent(
            agent_id="workflow_agent_v1",
            name="Workflow Agent",
            department="Operations",
            role="Coordinate registered workflow steps and surface approval or capability gaps.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"task_planning_skill_v1", "approval_request_skill_v1", "quality_check_skill_v1", "audit_logging_skill_v1"},
            allowed_tools={"task_manager_tool", "audit_read_tool", "database_read_tool"},
            reports_to="ceo_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        ),
        Agent(
            agent_id="audit_agent_v1",
            name="Audit Agent",
            department="Audit",
            role="Inspect append-only operational records and report control gaps.",
            permissions=review_permissions,
            forbidden=common_forbidden,
            allowed_skills={"audit_logging_skill_v1", "risk_check_skill_v1", "summary_skill_v1"},
            allowed_tools={"audit_read_tool", "database_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="capability_gap_detector_agent_v1",
            name="Capability Gap Detector Agent",
            department="Capability",
            role="Detect repeated capability and role gaps without changing runtime authority.",
            permissions=review_permissions,
            forbidden=common_forbidden,
            allowed_skills={"skill_search_skill_v1", "knowledge_search_skill_v1", "summary_skill_v1"},
            allowed_tools={"database_read_tool", "audit_read_tool"},
            reports_to="ceo_agent_v1",
            risk_level=RiskLevel.MEDIUM,
        ),
        Agent(
            agent_id="agent_factory_agent_v1",
            name="Agent Factory Agent",
            department="Capability",
            role="Prepare disabled Agent proposals for sandbox, risk, and Human Root review.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"task_planning_skill_v1", "approval_request_skill_v1", "risk_check_skill_v1"},
            allowed_tools={"database_read_tool", "audit_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="skill_factory_agent_v1",
            name="Skill Factory Agent",
            department="Capability",
            role="Prepare constrained Skill proposals and temporary low-risk capability definitions.",
            permissions=internal_permissions,
            forbidden=common_forbidden,
            allowed_skills={"skill_search_skill_v1", "skill_composition_skill_v1", "temporary_skill_creation_skill_v1", "approval_request_skill_v1"},
            allowed_tools={"database_read_tool", "audit_read_tool"},
            reports_to="human_root",
            risk_level=RiskLevel.HIGH,
        ),
        Agent(
            agent_id="workspace_agent_v1",
            name="Workspace Agent",
            department="Engineering",
            role="Inspect and modify the active workspace through approval-gated development tools.",
            permissions={
                PermissionLevel.L0_READ,
                PermissionLevel.L1_DRAFT,
                PermissionLevel.L2_INTERNAL_WRITE,
                PermissionLevel.L4_HIGH_RISK,
            },
            forbidden=common_forbidden,
            allowed_skills=set(),
            allowed_tools={
                "filesystem_read_tool",
                "workspace_patch_tool",
                "workspace_command_tool",
                "git_read_tool",
            },
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.HIGH,
        ),
    ]
