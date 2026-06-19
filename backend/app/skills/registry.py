from __future__ import annotations

from app.core.enums import RiskLevel
from app.core.models import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        if skill.skill_id in self._skills:
            raise ValueError(f"skill already registered: {skill.skill_id}")
        if skill.risk_level in {RiskLevel.HIGH, RiskLevel.FORBIDDEN} and not skill.requires_approval:
            raise ValueError("high or forbidden risk skills must require approval")
        self._skills[skill.skill_id] = skill
        return skill

    def get(self, skill_id: str) -> Skill:
        return self._skills[skill_id]

    def list(self) -> list[Skill]:
        return list(self._skills.values())

    def search(self, text: str) -> list[Skill]:
        needle = text.lower()
        return [
            skill
            for skill in self._skills.values()
            if needle in skill.name.lower() or needle in skill.description.lower() or needle in skill.type.lower()
        ]


def default_skills() -> list[Skill]:
    return [
        Skill(
            skill_id="task_planning_skill_v1",
            name="Task Planning Skill",
            type="planning",
            description="Create a safe task plan and execution outline.",
            input_schema={"goal": "string"},
            output_schema={"plan": "string"},
            allowed_agents={"ceo_agent_v1", "project_manager_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="document_writer_skill_v1",
            name="Document Writing Skill",
            type="document",
            description="Generate structured internal markdown documents.",
            input_schema={"topic": "string", "materials": "array"},
            output_schema={"markdown_document": "string"},
            allowed_agents={"document_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="summary_skill_v1",
            name="Summary Skill",
            type="document",
            description="Summarize plans, decisions, and task results.",
            input_schema={"content": "string"},
            output_schema={"summary": "string"},
            allowed_agents={"ceo_agent_v1", "project_manager_agent_v1", "document_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="risk_check_skill_v1",
            name="Risk Check Skill",
            type="safety",
            description="Check risk level and forbidden action policy.",
            input_schema={"action": "string"},
            output_schema={"risk_level": "string"},
            allowed_agents={"risk_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="quality_check_skill_v1",
            name="Quality Check Skill",
            type="quality",
            description="Check whether output satisfies the requested task.",
            input_schema={"content": "string"},
            output_schema={"passed": "boolean"},
            allowed_agents={"quality_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
    ]
