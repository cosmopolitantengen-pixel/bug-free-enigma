from __future__ import annotations

from dataclasses import replace

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

    def restore(self, skill: Skill) -> Skill:
        if skill.risk_level in {RiskLevel.HIGH, RiskLevel.FORBIDDEN} and not skill.requires_approval:
            raise ValueError("high or forbidden risk skills must require approval")
        self._skills[skill.skill_id] = skill
        return skill

    def allow_agent(self, skill_id: str, agent_id: str) -> Skill:
        skill = self.get(skill_id)
        updated = replace(skill, allowed_agents=skill.allowed_agents | {agent_id})
        self._skills[skill_id] = updated
        return updated

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
            allowed_agents={
                "ceo_agent_v1",
                "project_manager_agent_v1",
                "product_agent_v1",
                "workflow_agent_v1",
                "agent_factory_agent_v1",
            },
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
            allowed_agents={"document_agent_v1", "product_agent_v1", "legal_compliance_agent_v1"},
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
            allowed_agents={
                "ceo_agent_v1",
                "project_manager_agent_v1",
                "document_agent_v1",
                "data_agent_v1",
                "memory_agent_v1",
                "audit_agent_v1",
                "capability_gap_detector_agent_v1",
            },
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
            allowed_agents={
                "risk_agent_v1",
                "legal_compliance_agent_v1",
                "finance_assistant_agent_v1",
                "audit_agent_v1",
                "agent_factory_agent_v1",
            },
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
            allowed_agents={"quality_agent_v1", "workflow_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="rewrite_skill_v1",
            name="Rewrite Skill",
            type="document",
            description="Rewrite internal text while preserving meaning and constraints.",
            input_schema={"content": "string", "instructions": "string"},
            output_schema={"rewritten_content": "string"},
            allowed_agents={"document_agent_v1", "product_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="data_cleanup_skill_v1",
            name="Data Cleanup Skill",
            type="data",
            description="Normalize and validate internal structured data without external writes.",
            input_schema={"records": "array", "rules": "object"},
            output_schema={"records": "array", "issues": "array"},
            allowed_agents={"data_agent_v1", "finance_assistant_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="spreadsheet_generation_skill_v1",
            name="Spreadsheet Generation Skill",
            type="data",
            description="Prepare an internal spreadsheet specification from validated records.",
            input_schema={"records": "array", "columns": "array"},
            output_schema={"workbook_spec": "object"},
            allowed_agents={"data_agent_v1", "finance_assistant_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="code_generation_skill_v1",
            name="Code Generation Skill",
            type="engineering",
            description="Generate draft code; execution remains a separate approval-gated Tool action.",
            input_schema={"requirements": "string", "language": "string"},
            output_schema={"source": "string", "notes": "string"},
            allowed_agents={"tech_agent_v1"},
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
        ),
        Skill(
            skill_id="code_review_skill_v1",
            name="Code Review Skill",
            type="engineering",
            description="Review code for correctness, safety, and missing tests without executing it.",
            input_schema={"source": "string", "context": "string"},
            output_schema={"findings": "array"},
            allowed_agents={"tech_agent_v1", "quality_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="github_project_analysis_skill_v1",
            name="GitHub Project Analysis Skill",
            type="engineering",
            description="Analyze supplied repository metadata as untrusted external content.",
            input_schema={"repository": "string", "metadata": "object"},
            output_schema={"analysis": "object"},
            allowed_agents={"tech_agent_v1", "skill_manager_agent_v1"},
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
        ),
        Skill(
            skill_id="approval_request_skill_v1",
            name="Approval Request Skill",
            type="control",
            description="Prepare a scoped action request for the Approval Center.",
            input_schema={"action": "string", "reason": "string", "target": "string"},
            output_schema={"approval_id": "string"},
            allowed_agents={"ceo_agent_v1", "workflow_agent_v1", "agent_factory_agent_v1", "skill_factory_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="audit_logging_skill_v1",
            name="Audit Logging Skill",
            type="control",
            description="Prepare structured append-only audit event data.",
            input_schema={"event": "object"},
            output_schema={"event_id": "string"},
            allowed_agents={"audit_agent_v1", "workflow_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="memory_write_skill_v1",
            name="Memory Write Skill",
            type="knowledge",
            description="Convert scoped task outcomes into internal memory records.",
            input_schema={"task_id": "string", "content": "string"},
            output_schema={"record_id": "string"},
            allowed_agents={"memory_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="knowledge_search_skill_v1",
            name="Knowledge Search Skill",
            type="knowledge",
            description="Search registered internal knowledge records.",
            input_schema={"query": "string"},
            output_schema={"documents": "array"},
            allowed_agents={"memory_agent_v1", "legal_compliance_agent_v1", "capability_gap_detector_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="skill_search_skill_v1",
            name="Skill Search Skill",
            type="capability",
            description="Search the Skill Registry before creating new capability.",
            input_schema={"query": "string"},
            output_schema={"skills": "array"},
            allowed_agents={"skill_manager_agent_v1", "skill_factory_agent_v1", "capability_gap_detector_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="skill_composition_skill_v1",
            name="Skill Composition Skill",
            type="capability",
            description="Design a non-executing composition of existing registered Skills.",
            input_schema={"skill_ids": "array", "goal": "string"},
            output_schema={"composition": "object"},
            allowed_agents={"skill_manager_agent_v1", "skill_factory_agent_v1"},
            risk_level=RiskLevel.LOW,
            requires_approval=False,
        ),
        Skill(
            skill_id="temporary_skill_creation_skill_v1",
            name="Temporary Skill Creation Skill",
            type="capability",
            description="Prepare a disabled low-risk temporary Skill definition for sandbox review.",
            input_schema={"capability": "string", "constraints": "array"},
            output_schema={"skill_proposal": "object"},
            allowed_agents={"skill_manager_agent_v1", "skill_factory_agent_v1"},
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
        ),
    ]
