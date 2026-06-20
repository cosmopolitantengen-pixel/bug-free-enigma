from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentRegistry, default_agents
from app.approvals.service import ApprovalCenter
from app.audit.log import AuditLog
from app.backups.store import BackupStore
from app.budget.guard import BudgetGuard
from app.communication.store import CommunicationStore
from app.core.models import (
    AgentBroadcast,
    AgentConflict,
    AgentMeeting,
    AgentMessage,
    Agent,
    ApprovalRequest,
    AuditEvent,
    BackupRecord,
    BudgetPolicy,
    CostLog,
    DomainEvent,
    EvaluationRecord,
    StrategicGoal,
    Incident,
    KnowledgeDoc,
    MemoryRecord,
    ModelUsageRecord,
    ScheduledExecution,
    ScheduledJob,
    Skill,
    Tool,
    TaskHandoff,
    TaskReview,
    WorkflowRun,
    WorkflowStep,
)
from app.evaluations.store import EvaluationStore
from app.events.store import EventBus
from app.factory.proposals import CapabilityGapDetector, ProposalSandbox
from app.goals.store import GoalStore
from app.incidents.store import IncidentStore
from app.knowledge_base.store import KnowledgeBase
from app.memory.store import MemoryStore
from app.models.gateway import ModelGateway
from app.permissions.engine import PermissionEngine
from app.reviews.store import ReviewStore
from app.safety.risk import RiskEngine
from app.scheduler.store import SchedulerStore
from app.skills.registry import SkillRegistry, default_skills
from app.tools.registry import ToolRegistry, default_tools
from app.workflows.document_generation import DocumentGenerationWorkflow
from app.workflows.quality_check import QualityCheckWorkflow
from app.workflows.registry import WorkflowRegistry, default_workflows
from app.workflows.task_planning import TaskPlanningWorkflow
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class CompanyOS:
    agents: AgentRegistry
    skills: SkillRegistry
    tools: ToolRegistry
    permissions: PermissionEngine
    risks: RiskEngine
    approvals: ApprovalCenter
    audit: AuditLog
    memory: MemoryStore
    knowledge: KnowledgeBase
    evaluations: EvaluationStore
    models: ModelGateway
    budget: BudgetGuard
    incidents: IncidentStore
    traces: WorkflowTraceStore
    gaps: CapabilityGapDetector
    sandbox: ProposalSandbox
    backups: BackupStore
    communication: CommunicationStore
    reviews: ReviewStore
    goals: GoalStore
    events: EventBus
    scheduler: SchedulerStore
    workflows: WorkflowRegistry
    document_workflow: DocumentGenerationWorkflow
    task_planning_workflow: TaskPlanningWorkflow
    quality_check_workflow: QualityCheckWorkflow


def build_company_os(
    approvals: list[ApprovalRequest] | None = None,
    audit_events: list[AuditEvent] | None = None,
    memory_records: list[MemoryRecord] | None = None,
    knowledge_docs: list[KnowledgeDoc] | None = None,
    evaluations: list[EvaluationRecord] | None = None,
    registered_agents: list[Agent] | None = None,
    registered_skills: list[Skill] | None = None,
    tools: list[Tool] | None = None,
    model_usage: list[ModelUsageRecord] | None = None,
    budget_policy: BudgetPolicy | None = None,
    cost_logs: list[CostLog] | None = None,
    incidents: list[Incident] | None = None,
    backups: list[BackupRecord] | None = None,
    agent_messages: list[AgentMessage] | None = None,
    agent_meetings: list[AgentMeeting] | None = None,
    task_handoffs: list[TaskHandoff] | None = None,
    agent_broadcasts: list[AgentBroadcast] | None = None,
    agent_conflicts: list[AgentConflict] | None = None,
    task_reviews: list[TaskReview] | None = None,
    strategic_goals: list[StrategicGoal] | None = None,
    workflow_runs: list[WorkflowRun] | None = None,
    workflow_steps: list[WorkflowStep] | None = None,
    domain_events: list[DomainEvent] | None = None,
    scheduled_jobs: list[ScheduledJob] | None = None,
    scheduled_executions: list[ScheduledExecution] | None = None,
) -> CompanyOS:
    agents = AgentRegistry()
    for agent in default_agents():
        agents.register(agent)
    for agent in registered_agents or []:
        agents.restore(agent)

    skills = SkillRegistry()
    for skill in default_skills():
        skills.register(skill)
    for skill in registered_skills or []:
        skills.restore(skill)

    tool_registry = ToolRegistry()
    for tool in default_tools():
        tool_registry.register(tool)
    for tool in tools or []:
        if tool.tool_id not in {existing.tool_id for existing in tool_registry.list()}:
            tool_registry.register(tool)

    _validate_catalog_references(agents, skills, tool_registry)

    permissions = PermissionEngine()
    risks = RiskEngine()
    approvals_center = ApprovalCenter(approvals)
    audit = AuditLog(audit_events)
    memory = MemoryStore(memory_records)
    knowledge = KnowledgeBase(knowledge_docs)
    evaluation_store = EvaluationStore(evaluations)
    model_gateway = ModelGateway(model_usage)
    budget_guard = BudgetGuard(budget_policy, cost_logs)
    incident_store = IncidentStore(incidents)
    traces = WorkflowTraceStore(workflow_runs, workflow_steps)
    gaps = CapabilityGapDetector()
    sandbox = ProposalSandbox()
    backup_store = BackupStore(backups)
    communication = CommunicationStore(
        agent_messages,
        agent_meetings,
        task_handoffs,
        agent_broadcasts,
        agent_conflicts,
    )
    reviews = ReviewStore(task_reviews)
    goals = GoalStore(strategic_goals)
    events = EventBus(domain_events)
    scheduler = SchedulerStore(scheduled_jobs, scheduled_executions)
    workflows = WorkflowRegistry(agents, skills)
    for workflow in default_workflows():
        workflows.register(workflow)
    document_workflow = DocumentGenerationWorkflow(
        agents=agents,
        skills=skills,
        permissions=permissions,
        risks=risks,
        approvals=approvals_center,
        audit=audit,
        memory=memory,
        knowledge=knowledge,
        evaluations=evaluation_store,
        models=model_gateway,
        budget=budget_guard,
        incidents=incident_store,
        traces=traces,
    )
    task_planning_workflow = TaskPlanningWorkflow(
        workflows=workflows,
        agents=agents,
        skills=skills,
        permissions=permissions,
        risks=risks,
        approvals=approvals_center,
        audit=audit,
        memory=memory,
        evaluations=evaluation_store,
        incidents=incident_store,
        traces=traces,
    )
    quality_check_workflow = QualityCheckWorkflow(
        workflows=workflows,
        audit=audit,
        evaluations=evaluation_store,
        incidents=incident_store,
        traces=traces,
    )
    return CompanyOS(
        agents=agents,
        skills=skills,
        tools=tool_registry,
        permissions=permissions,
        risks=risks,
        approvals=approvals_center,
        audit=audit,
        memory=memory,
        knowledge=knowledge,
        evaluations=evaluation_store,
        models=model_gateway,
        budget=budget_guard,
        incidents=incident_store,
        traces=traces,
        gaps=gaps,
        sandbox=sandbox,
        backups=backup_store,
        communication=communication,
        reviews=reviews,
        goals=goals,
        events=events,
        scheduler=scheduler,
        workflows=workflows,
        document_workflow=document_workflow,
        task_planning_workflow=task_planning_workflow,
        quality_check_workflow=quality_check_workflow,
    )


def _validate_catalog_references(
    agents: AgentRegistry,
    skills: SkillRegistry,
    tools: ToolRegistry,
) -> None:
    agent_ids = {agent.agent_id for agent in agents.list()}
    skill_ids = {skill.skill_id for skill in skills.list()}
    tool_ids = {tool.tool_id for tool in tools.list()}
    for agent in agents.list():
        unknown_skills = agent.allowed_skills - skill_ids
        unknown_tools = agent.allowed_tools - tool_ids
        if unknown_skills:
            raise ValueError(f"agent {agent.agent_id} references unknown skills: {sorted(unknown_skills)}")
        if unknown_tools:
            raise ValueError(f"agent {agent.agent_id} references unknown tools: {sorted(unknown_tools)}")
        if agent.reports_to != "human_root" and agent.reports_to not in agent_ids:
            raise ValueError(f"agent {agent.agent_id} reports to unknown agent: {agent.reports_to}")
        for skill_id in agent.allowed_skills:
            if agent.agent_id not in skills.get(skill_id).allowed_agents:
                raise ValueError(
                    f"agent {agent.agent_id} and skill {skill_id} have asymmetric authorization"
                )
    for skill in skills.list():
        unknown_agents = skill.allowed_agents - agent_ids
        if unknown_agents:
            raise ValueError(f"skill {skill.skill_id} references unknown agents: {sorted(unknown_agents)}")
        for agent_id in skill.allowed_agents:
            if skill.skill_id not in agents.get(agent_id).allowed_skills:
                raise ValueError(
                    f"skill {skill.skill_id} and agent {agent_id} have asymmetric authorization"
                )
