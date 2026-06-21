from __future__ import annotations

from app.agents.registry import AgentRegistry
from app.core.enums import PermissionLevel
from app.core.models import WorkflowDefinition, WorkflowStepDefinition
from app.skills.registry import SkillRegistry


class WorkflowRegistry:
    def __init__(self, agents: AgentRegistry, skills: SkillRegistry) -> None:
        self._agents = agents
        self._skills = skills
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        if workflow.workflow_id in self._workflows:
            raise ValueError(f"workflow already registered: {workflow.workflow_id}")
        self._validate(workflow)
        self._workflows[workflow.workflow_id] = workflow
        return workflow

    def get(self, workflow_id: str) -> WorkflowDefinition:
        return self._workflows[workflow_id]

    def list(self) -> list[WorkflowDefinition]:
        return list(self._workflows.values())

    def _validate(self, workflow: WorkflowDefinition) -> None:
        if not workflow.workflow_id.strip() or not workflow.name.strip():
            raise ValueError("workflow_id and name are required")
        if not workflow.entrypoint.strip():
            raise ValueError("workflow entrypoint is required")
        if not workflow.steps:
            raise ValueError("workflow must define at least one step")
        sequences = [step.sequence for step in workflow.steps]
        if sequences != list(range(1, len(workflow.steps) + 1)):
            raise ValueError("workflow step sequences must be unique and contiguous from 1")
        for step in workflow.steps:
            if not step.step_name.strip() or not step.action.strip():
                raise ValueError("workflow step name and action are required")
            agent = self._agents.get(step.actor_id)
            if step.permission_level not in agent.permissions:
                raise ValueError(
                    f"workflow {workflow.workflow_id} step {step.step_name} exceeds exact Agent permission"
                )
            if step.skill_id is None:
                continue
            skill = self._skills.get(step.skill_id)
            if step.skill_id not in agent.allowed_skills or agent.agent_id not in skill.allowed_agents:
                raise ValueError(
                    f"workflow {workflow.workflow_id} step {step.step_name} has unauthorized Skill assignment"
                )


def default_workflows() -> list[WorkflowDefinition]:
    step = WorkflowStepDefinition
    return [
        WorkflowDefinition(
            workflow_id="document_generation_v1",
            name="Document Generation",
            description="Plan, draft, risk-check, quality-check, and retain an internal document.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "plan_task", "ceo_agent_v1", "plan_task", PermissionLevel.L1_DRAFT, "task_planning_skill_v1"),
                step(2, "assign_document_agent", "project_manager_agent_v1", "assign_document_agent", PermissionLevel.L2_INTERNAL_WRITE, "task_planning_skill_v1"),
                step(3, "write_document", "document_agent_v1", "create_internal_document", PermissionLevel.L2_INTERNAL_WRITE, "document_writer_skill_v1"),
                step(4, "risk_check", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
                step(5, "quality_check", "quality_agent_v1", "quality_check", PermissionLevel.L1_DRAFT, "quality_check_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="task_planning_v1",
            name="Task Planning",
            description="Turn a goal into a scoped, risk-reviewed execution plan.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "understand_goal", "ceo_agent_v1", "understand_goal", PermissionLevel.L1_DRAFT, "task_planning_skill_v1"),
                step(2, "decompose_task", "project_manager_agent_v1", "decompose_task", PermissionLevel.L1_DRAFT, "task_planning_skill_v1"),
                step(3, "validate_plan_risk", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="agent_collaboration_v1",
            name="Agent Collaboration",
            description="Coordinate planning, handoff, and auditable team communication.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "coordinate_work", "workflow_agent_v1", "coordinate_work", PermissionLevel.L1_DRAFT, "task_planning_skill_v1"),
                step(2, "prepare_handoff", "project_manager_agent_v1", "prepare_handoff", PermissionLevel.L2_INTERNAL_WRITE, "task_planning_skill_v1"),
                step(3, "audit_collaboration", "audit_agent_v1", "record_collaboration", PermissionLevel.L1_DRAFT, "audit_logging_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="skill_missing_v1",
            name="Skill Missing Handling",
            description="Search, compose, sandbox, approve, and register missing capability safely.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "detect_skill_gap", "capability_gap_detector_agent_v1", "detect_skill_gap", PermissionLevel.L1_DRAFT, "skill_search_skill_v1"),
                step(2, "search_or_compose", "skill_manager_agent_v1", "compose_skill", PermissionLevel.L2_INTERNAL_WRITE, "skill_composition_skill_v1"),
                step(3, "prepare_skill_proposal", "skill_factory_agent_v1", "create_skill", PermissionLevel.L2_INTERNAL_WRITE, "temporary_skill_creation_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="agent_missing_v1",
            name="Agent Missing Handling",
            description="Detect a repeated role gap and route a constrained Agent proposal through control gates.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "detect_role_gap", "capability_gap_detector_agent_v1", "detect_role_gap", PermissionLevel.L1_DRAFT, "knowledge_search_skill_v1"),
                step(2, "prepare_agent_proposal", "agent_factory_agent_v1", "create_agent", PermissionLevel.L2_INTERNAL_WRITE, "task_planning_skill_v1"),
                step(3, "review_agent_risk", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="approval_v1",
            name="Approval",
            description="Assess a controlled action and place Human Root at the decision boundary.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "prepare_request", "ceo_agent_v1", "request_approval", PermissionLevel.L1_DRAFT, "approval_request_skill_v1"),
                step(2, "assess_request_risk", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
                step(3, "audit_decision", "audit_agent_v1", "record_approval", PermissionLevel.L1_DRAFT, "audit_logging_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="quality_check_v1",
            name="Quality Check",
            description="Review output quality and safety before completion.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "check_quality", "quality_agent_v1", "quality_check", PermissionLevel.L1_DRAFT, "quality_check_skill_v1"),
                step(2, "check_output_risk", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
                step(3, "audit_quality", "audit_agent_v1", "record_quality", PermissionLevel.L1_DRAFT, "audit_logging_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="retrospective_v1",
            name="Retrospective",
            description="Capture quality outcomes, lessons, memory, and follow-up improvements.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "review_outcome", "quality_agent_v1", "quality_check", PermissionLevel.L1_DRAFT, "quality_check_skill_v1"),
                step(2, "write_review_memory", "memory_agent_v1", "write_memory", PermissionLevel.L2_INTERNAL_WRITE, "memory_write_skill_v1"),
                step(3, "audit_retrospective", "audit_agent_v1", "record_review", PermissionLevel.L1_DRAFT, "audit_logging_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="github_project_analysis_v1",
            name="GitHub Project Analysis",
            description="Treat repository material as untrusted, assess it, and register knowledge only after approval.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "analyze_repository", "tech_agent_v1", "analyze_github_repository", PermissionLevel.L1_DRAFT, "github_project_analysis_skill_v1"),
                step(2, "review_repository_risk", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
                step(3, "curate_capability", "skill_manager_agent_v1", "review_github_capability", PermissionLevel.L1_DRAFT, "github_project_analysis_skill_v1"),
            ),
        ),
        WorkflowDefinition(
            workflow_id="tool_call_v1",
            name="Tool Call",
            description="Validate Tool registration, Agent permission, risk, approval, execution, and audit.",
            entrypoint="POST /workflows/run",
            execution_mode="native",
            steps=(
                step(1, "prepare_tool_call", "workflow_agent_v1", "prepare_tool_call", PermissionLevel.L1_DRAFT, "approval_request_skill_v1"),
                step(2, "review_tool_risk", "risk_agent_v1", "risk_check", PermissionLevel.L1_DRAFT, "risk_check_skill_v1"),
                step(3, "audit_tool_call", "audit_agent_v1", "record_tool_call", PermissionLevel.L1_DRAFT, "audit_logging_skill_v1"),
            ),
        ),
    ]
