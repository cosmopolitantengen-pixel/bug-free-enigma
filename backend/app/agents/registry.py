from __future__ import annotations

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
            allowed_skills={"task_planning_skill_v1", "summary_skill_v1"},
            allowed_tools={"task_manager_tool", "database_read_tool", "filesystem_read_tool"},
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
            allowed_tools={"task_manager_tool", "filesystem_read_tool"},
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
            allowed_skills={"document_writer_skill_v1", "summary_skill_v1"},
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
            allowed_skills={"quality_check_skill_v1"},
            allowed_tools={"audit_read_tool", "database_read_tool", "filesystem_read_tool"},
            reports_to="project_manager_agent_v1",
            risk_level=RiskLevel.LOW,
        ),
    ]
