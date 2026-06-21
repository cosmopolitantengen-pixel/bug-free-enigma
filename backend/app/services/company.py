from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.auth.service import AuthService
from app.bootstrap import CompanyOS, build_company_os
from app.core.enums import ActionDecision, GoalStatus, ProposalStatus, SandboxStatus, ScheduleAction, ScheduleExecutionStatus, ScheduleStatus
from app.core.models import Agent, AgentBroadcast, AgentConflict, AgentMeeting, AgentMessage, BackupRecord, DomainEvent, Incident, ScheduledExecution, ScheduledJob, Skill, SkillRun, StrategicGoal, TaskHandoff, TaskReview, Tool, ToolRun
from app.core.enums import ApprovalStatus, PermissionLevel, RiskLevel, SkillRunStatus, TaskStatus, ToolRunStatus
from app.core.models import ActionRequest, AuditEvent, EvaluationRecord, KnowledgeDoc, MemoryRecord, RiskAssessment, Task, utc_now
from app.factory.proposals import AgentProposal, GitHubAbsorption, ImprovementProposal, SkillProposal
from app.observability import build_structured_logs
from app.persistence.store import StateStore
from app.services.serializers import to_plain
from app.skills.runtime import SkillRuntimeContext, SkillRuntimeError, execute_skill_adapter
from app.tools.adapters import ToolAdapterContext, ToolAdapterError, execute_tool_adapter


ARBITRATION_PRIORITY_AREAS = {
    "safety",
    "compliance",
    "privacy",
    "user_confirmation",
    "quality",
    "cost",
    "efficiency",
}


@dataclass
class CompanyApplicationService:
    company_os: CompanyOS = field(default_factory=build_company_os)
    tasks: dict[str, Task] = field(default_factory=dict)
    persistence: StateStore | None = None
    auth: AuthService = field(default_factory=AuthService)
    skill_proposals: dict[str, SkillProposal] = field(default_factory=dict)
    agent_proposals: dict[str, AgentProposal] = field(default_factory=dict)
    improvement_proposals: dict[str, ImprovementProposal] = field(default_factory=dict)
    github_absorptions: dict[str, GitHubAbsorption] = field(default_factory=dict)
    tool_runs: dict[str, ToolRun] = field(default_factory=dict)
    skill_runs: dict[str, SkillRun] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._bind_workflow_skill_runtime()
        if self.persistence is None:
            return
        loaded_users = self.persistence.load_users()
        loaded_tasks = self.persistence.load_tasks()
        loaded_approvals = self.persistence.load_approvals()
        loaded_audit = self.persistence.load_audit_events()
        loaded_memory = self.persistence.load_memory()
        loaded_knowledge = self.persistence.load_knowledge()
        loaded_evaluations = self.persistence.load_evaluations()
        loaded_agents = self.persistence.load_agents()
        loaded_skills = self.persistence.load_skills()
        loaded_tools = self.persistence.load_tools()
        loaded_tool_runs = self.persistence.load_tool_runs()
        loaded_skill_runs = self.persistence.load_skill_runs()
        loaded_workflow_runs = self.persistence.load_workflow_runs()
        loaded_workflow_steps = self.persistence.load_workflow_steps()
        loaded_model_usage = self.persistence.load_model_usage()
        loaded_cost_logs = self.persistence.load_cost_logs()
        loaded_budget_policy = self.persistence.load_budget_policy()
        loaded_incidents = self.persistence.load_incidents()
        loaded_skill_proposals = self.persistence.load_skill_proposals()
        loaded_agent_proposals = self.persistence.load_agent_proposals()
        loaded_improvement_proposals = self.persistence.load_improvement_proposals()
        loaded_github_absorptions = self.persistence.load_github_absorptions()
        loaded_backups = self.persistence.load_backups()
        loaded_agent_messages = self.persistence.load_agent_messages()
        loaded_agent_meetings = self.persistence.load_agent_meetings()
        loaded_task_handoffs = self.persistence.load_task_handoffs()
        loaded_agent_broadcasts = self.persistence.load_agent_broadcasts()
        loaded_agent_conflicts = self.persistence.load_agent_conflicts()
        loaded_task_reviews = self.persistence.load_task_reviews()
        loaded_strategic_goals = self.persistence.load_strategic_goals()
        loaded_domain_events = self.persistence.load_domain_events()
        loaded_scheduled_jobs = self.persistence.load_scheduled_jobs()
        loaded_scheduled_executions = self.persistence.load_scheduled_executions()
        self.auth = AuthService(users={user.email: user for user in loaded_users})
        self.tasks = {task.task_id: task for task in loaded_tasks}
        self.skill_proposals = {proposal.proposal_id: proposal for proposal in loaded_skill_proposals}
        self.agent_proposals = {proposal.proposal_id: proposal for proposal in loaded_agent_proposals}
        self.improvement_proposals = {
            proposal.proposal_id: proposal for proposal in loaded_improvement_proposals
        }
        self.github_absorptions = {proposal.proposal_id: proposal for proposal in loaded_github_absorptions}
        self.tool_runs = {run.run_id: run for run in loaded_tool_runs}
        self.skill_runs = {run.run_id: run for run in loaded_skill_runs}
        self.company_os = build_company_os(
            approvals=loaded_approvals,
            audit_events=loaded_audit,
            memory_records=loaded_memory,
            knowledge_docs=loaded_knowledge,
            evaluations=loaded_evaluations,
            registered_agents=loaded_agents,
            registered_skills=loaded_skills,
            tools=loaded_tools,
            model_usage=loaded_model_usage,
            cost_logs=loaded_cost_logs,
            budget_policy=loaded_budget_policy,
            incidents=loaded_incidents,
            backups=loaded_backups,
            agent_messages=loaded_agent_messages,
            agent_meetings=loaded_agent_meetings,
            task_handoffs=loaded_task_handoffs,
            agent_broadcasts=loaded_agent_broadcasts,
            agent_conflicts=loaded_agent_conflicts,
            task_reviews=loaded_task_reviews,
            strategic_goals=loaded_strategic_goals,
            workflow_runs=loaded_workflow_runs,
            workflow_steps=loaded_workflow_steps,
            domain_events=loaded_domain_events,
            scheduled_jobs=loaded_scheduled_jobs,
            scheduled_executions=loaded_scheduled_executions,
        )
        self._bind_workflow_skill_runtime()

    def sync(self) -> None:
        if self.persistence is None:
            return
        self.persistence.sync_state(
            users=self.auth.list_users(),
            tasks=list(self.tasks.values()),
            approvals=self.company_os.approvals.list(),
            audit_events=list(self.company_os.audit.list()),
            memory_records=list(self.company_os.memory.list()),
            knowledge_docs=list(self.company_os.knowledge.list()),
            evaluations=list(self.company_os.evaluations.list()),
            agents=list(self.company_os.agents.list()),
            skills=list(self.company_os.skills.list()),
            tools=list(self.company_os.tools.list()),
            tool_runs=list(self.tool_runs.values()),
            skill_runs=list(self.skill_runs.values()),
            workflow_runs=list(self.company_os.traces.list_runs()),
            workflow_steps=list(self.company_os.traces.list_steps()),
            model_usage=list(self.company_os.models.list_usage()),
            cost_logs=list(self.company_os.budget.list_cost_logs()),
            budget_policy=self.company_os.budget.policy,
            incidents=list(self.company_os.incidents.list()),
            skill_proposals=list(self.skill_proposals.values()),
            agent_proposals=list(self.agent_proposals.values()),
            improvement_proposals=list(self.improvement_proposals.values()),
            github_absorptions=list(self.github_absorptions.values()),
            backups=list(self.company_os.backups.list()),
            agent_messages=list(self.company_os.communication.list_messages()),
            agent_meetings=list(self.company_os.communication.list_meetings()),
            task_handoffs=list(self.company_os.communication.list_handoffs()),
            agent_broadcasts=list(self.company_os.communication.list_broadcasts()),
            agent_conflicts=list(self.company_os.communication.list_conflicts()),
            task_reviews=list(self.company_os.reviews.list()),
            strategic_goals=list(self.company_os.goals.list()),
            domain_events=list(self.company_os.events.list()),
            scheduled_jobs=list(self.company_os.scheduler.list()),
            scheduled_executions=list(self.company_os.scheduler.list_executions()),
        )

    def register_user(self, email: str, password: str) -> dict:
        user = self.auth.register(email, password)
        self.sync()
        return user

    def login_user(self, email: str, password: str) -> dict:
        return self.auth.login(email, password)

    def logout_user(self, token: str | None = None) -> dict:
        return self.auth.logout(token)

    def health(self) -> dict[str, str]:
        return {"status": "ok", "system": "AI Company OS"}

    def database_schema(self) -> dict:
        if self.persistence is None:
            return {
                "backend": "memory",
                "schema_version": None,
                "migrations": [],
            }
        return {
            "backend": self.persistence.backend_name,
            "schema_version": self.persistence.schema_version(),
            "migrations": self.persistence.list_schema_migrations(),
        }

    def system_integrity(self) -> dict:
        checks = [
            self._persistence_integrity_check(),
            self._schema_integrity_check(),
            self._audit_storage_integrity_check(),
            self._backup_integrity_check(),
            self._incident_integrity_check(),
            self._approval_integrity_check(),
            self._budget_integrity_check(),
            self._scheduler_integrity_check(),
        ]
        issue_count = len([check for check in checks if check["status"] in {"warning", "critical"}])
        if any(check["status"] == "critical" for check in checks):
            status = "critical"
        elif any(check["status"] == "warning" for check in checks):
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "check_count": len(checks),
            "issue_count": issue_count,
            "checks": checks,
        }

    def list_agents(self) -> list[dict]:
        return [to_plain(agent) for agent in self.company_os.agents.list()]

    def get_agent(self, agent_id: str) -> dict:
        return to_plain(self.company_os.agents.get(agent_id))

    def register_agent(
        self,
        agent_id: str,
        name: str,
        department: str,
        role: str,
        permissions: list[PermissionLevel],
        forbidden: list[str],
        allowed_skills: list[str],
        allowed_tools: list[str],
        reports_to: str,
        risk_level: RiskLevel,
        version: str,
        enabled: bool,
    ) -> dict:
        self._validate_agent_catalog_entry(agent_id, allowed_skills, allowed_tools, reports_to)
        agent = Agent(
            agent_id=agent_id,
            name=name,
            department=department,
            role=role,
            permissions=set(permissions),
            forbidden=set(forbidden),
            allowed_skills=set(allowed_skills),
            allowed_tools=set(allowed_tools),
            reports_to=reports_to,
            risk_level=risk_level,
            version=version,
            enabled=enabled,
        )
        registered = self.company_os.agents.register(agent)
        for skill_id in registered.allowed_skills:
            self.company_os.skills.allow_agent(skill_id, registered.agent_id)
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_registered",
                actor_id="human_root",
                action="register_agent",
                task_id=None,
                risk_level=risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=registered.agent_id,
            )
        )
        self.sync()
        return to_plain(registered)

    def list_skills(self) -> list[dict]:
        return [to_plain(skill) for skill in self.company_os.skills.list()]

    def register_skill(
        self,
        skill_id: str,
        name: str,
        type: str,
        description: str,
        input_schema: dict[str, str],
        output_schema: dict[str, str],
        allowed_agents: list[str],
        risk_level: RiskLevel,
        requires_approval: bool,
        version: str,
        enabled: bool,
    ) -> dict:
        self._validate_skill_catalog_entry(skill_id, allowed_agents)
        skill = Skill(
            skill_id=skill_id,
            name=name,
            type=type,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            allowed_agents=set(allowed_agents),
            risk_level=risk_level,
            requires_approval=requires_approval,
            version=version,
            enabled=enabled,
        )
        registered = self.company_os.skills.register(skill)
        for agent_id in registered.allowed_agents:
            self.company_os.agents.grant_skill(agent_id, registered.skill_id)
        self.company_os.audit.append(
            AuditEvent(
                event_type="skill_registered",
                actor_id="human_root",
                action="register_skill",
                task_id=None,
                risk_level=risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=registered.skill_id,
            )
        )
        self.sync()
        return to_plain(registered)

    def search_skills(self, query: str) -> list[dict]:
        return [to_plain(skill) for skill in self.company_os.skills.search(query)]

    def list_tools(self) -> list[dict]:
        return [to_plain(tool) for tool in self.company_os.tools.list()]

    def register_tool(
        self,
        tool_id: str,
        name: str,
        type: str,
        description: str,
        action: str,
        permission_level: PermissionLevel,
        risk_level: RiskLevel,
        requires_approval: bool,
        input_schema: dict[str, str],
        output_schema: dict[str, str],
        version: str,
        enabled: bool,
    ) -> dict:
        tool = Tool(
            tool_id=tool_id,
            name=name,
            type=type,
            description=description,
            action=action,
            permission_level=permission_level,
            risk_level=risk_level,
            requires_approval=requires_approval,
            input_schema=input_schema,
            output_schema=output_schema,
            version=version,
            enabled=enabled,
        )
        registered = self.company_os.tools.register(tool)
        self.sync()
        return to_plain(registered)

    def list_tool_runs(self) -> list[dict]:
        return [to_plain(run) for run in self.tool_runs.values()]

    def list_skill_runs(self) -> list[dict]:
        return [to_plain(run) for run in self.skill_runs.values()]

    def complete_skill_run(self, run_id: str, completed_by: str = "human_root", note: str | None = None) -> dict:
        run = self.skill_runs[run_id]
        if run.status != SkillRunStatus.WAITING_APPROVAL:
            raise ValueError("skill run is not waiting for approval")
        if not run.approval_id:
            raise ValueError("skill run has no approval")
        approval = self.company_os.approvals.get(run.approval_id)
        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("skill run approval is not approved")

        skill = self.company_os.skills.get(run.skill_id)
        agent = self.company_os.agents.get(run.actor_id)
        if not skill.enabled:
            run.status, run.error = SkillRunStatus.BLOCKED, "skill is disabled"
            run.completed_at = utc_now()
        elif run.skill_id not in agent.allowed_skills or agent.agent_id not in skill.allowed_agents:
            run.status, run.error = SkillRunStatus.BLOCKED, "skill is not authorized for this agent"
            run.completed_at = utc_now()
        else:
            self._execute_skill_run(run, skill)
        self.company_os.audit.append(
            AuditEvent(
                event_type="skill_run_completed",
                actor_id=completed_by,
                action=f"run_skill:{skill.skill_id}",
                task_id=run.task_id,
                risk_level=run.risk_level,
                approval_status=approval.status,
                result=run.status.value,
                input_ref=note,
                output_ref=run.run_id,
                error=run.error,
            )
        )
        self.sync()
        return {"skill": to_plain(skill), "run": to_plain(run), "approval": to_plain(approval)}

    def complete_tool_run(self, run_id: str, completed_by: str = "human_root", note: str | None = None) -> dict:
        run = self.tool_runs[run_id]
        if run.status != ToolRunStatus.WAITING_APPROVAL:
            raise ValueError("tool run is not waiting for approval")
        if not run.approval_id:
            raise ValueError("tool run has no approval")

        approval = self.company_os.approvals.get(run.approval_id)
        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("tool run approval is not approved")

        tool = self.company_os.tools.get(run.tool_id)
        agent = self.company_os.agents.get(run.actor_id)
        request = ActionRequest(
            action=tool.action,
            actor_id=run.actor_id,
            task_id=run.task_id,
            permission_level=tool.permission_level,
            reason=run.reason,
            target=tool.tool_id,
            metadata={"tool_id": tool.tool_id},
        )
        permission = self.company_os.permissions.evaluate(agent, request)
        risk = self.company_os.risks.assess(request)
        if not tool.enabled:
            run.status = ToolRunStatus.BLOCKED
            run.error = "tool is disabled"
            run.completed_at = utc_now()
        elif tool.tool_id not in agent.allowed_tools:
            run.status = ToolRunStatus.BLOCKED
            run.error = "tool is not allowed for this agent"
            run.completed_at = utc_now()
        elif risk.blocked or permission.decision == ActionDecision.BLOCK:
            run.status = ToolRunStatus.BLOCKED
            run.error = permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons)
            run.completed_at = utc_now()
        else:
            self._execute_tool_run(run, tool)

        incident = None
        if run.status == ToolRunStatus.BLOCKED:
            incident = self._report_incident(
                title="Approved Tool run blocked on revalidation",
                description=run.error or "Tool run controls changed before execution.",
                source_type="tool_run",
                source_id=run.run_id,
                risk_level=run.risk_level,
                task_id=run.task_id,
                actor_id=run.actor_id,
                recommendation="Review live Tool state, Agent authorization, permission, and risk policy.",
            )

        self.company_os.audit.append(
            AuditEvent(
                event_type="tool_run_completed",
                actor_id=completed_by,
                action=run.action,
                task_id=run.task_id,
                risk_level=run.risk_level,
                approval_status=approval.status,
                result=run.status.value,
                input_ref=note,
                output_ref=run.run_id,
                error=run.error,
            )
        )
        self.sync()
        return {
            "tool": to_plain(tool),
            "run": to_plain(run),
            "approval": to_plain(approval),
            "incident": to_plain(incident) if incident else None,
        }

    def deny_tool_run(self, run_id: str, reason: str) -> dict:
        run = self.tool_runs[run_id]
        if run.status != ToolRunStatus.WAITING_APPROVAL:
            raise ValueError("tool run is not waiting for approval")
        if not run.approval_id:
            raise ValueError("tool run has no approval")
        approval = self.company_os.approvals.get(run.approval_id)
        if approval.status not in {
            ApprovalStatus.REJECTED,
            ApprovalStatus.BLOCKED,
            ApprovalStatus.MODIFIED,
        }:
            raise ValueError("tool run approval has not denied execution")
        run.status = ToolRunStatus.BLOCKED
        run.error = reason
        run.completed_at = utc_now()
        tool = self.company_os.tools.get(run.tool_id)
        self.company_os.audit.append(
            AuditEvent(
                event_type="tool_run_decision_enforced",
                actor_id="human_root",
                action=run.action,
                task_id=run.task_id,
                risk_level=run.risk_level,
                approval_status=approval.status,
                result="not_executed",
                input_ref=reason,
                output_ref=run.run_id,
            )
        )
        self.sync()
        return {"tool": to_plain(tool), "run": to_plain(run), "approval": to_plain(approval)}

    def list_workflow_runs(self) -> list[dict]:
        return [to_plain(run) for run in self.company_os.traces.list_runs()]

    def list_workflows(self) -> list[dict]:
        return [to_plain(workflow) for workflow in self.company_os.workflows.list()]

    def get_workflow(self, workflow_id: str) -> dict:
        return to_plain(self.company_os.workflows.get(workflow_id))

    def run_registered_workflow(
        self,
        workflow_id: str,
        title: str,
        description: str,
        user_id: str = "human_root",
        input: dict | None = None,
    ) -> dict:
        definition = self.company_os.workflows.get(workflow_id)
        if not definition.enabled:
            raise ValueError("workflow is disabled")
        if workflow_id not in {
            "document_generation_v1",
            "task_planning_v1",
            "agent_collaboration_v1",
            "skill_missing_v1",
            "agent_missing_v1",
            "approval_v1",
            "quality_check_v1",
            "retrospective_v1",
            "github_project_analysis_v1",
            "tool_call_v1",
        }:
            raise ValueError(f"workflow uses dedicated entrypoint: {definition.entrypoint}")
        workflow_input = input or {}
        if workflow_id == "agent_collaboration_v1":
            self.company_os.agent_collaboration_workflow.validate_input(workflow_input, description)
        if workflow_id == "skill_missing_v1":
            self.company_os.skill_missing_workflow.validate_input(workflow_input, description)
        if workflow_id == "agent_missing_v1":
            self.company_os.agent_missing_workflow.validate_input(workflow_input, description)
        if workflow_id == "approval_v1":
            self.company_os.approval_workflow.validate_input(workflow_input, description)
        if workflow_id == "retrospective_v1":
            self.company_os.retrospective_workflow.validate_input(workflow_input, description)
            source_task_id = workflow_input.get("source_task_id")
            if source_task_id is not None and source_task_id not in self.tasks:
                raise ValueError(f"retrospective source task not found: {source_task_id}")
        if workflow_id == "github_project_analysis_v1":
            github_input = self.company_os.github_project_analysis_workflow.validate_input(workflow_input)
            self.company_os.agents.get(github_input["requested_by_agent"])
        if workflow_id == "tool_call_v1":
            tool_input = self.company_os.tool_call_workflow.validate_input(workflow_input)
            self.company_os.tools.get(tool_input["tool_id"])
            self.company_os.agents.get(tool_input["actor_id"])
        task = self.create_task(title, description, user_id)
        if workflow_id == "document_generation_v1":
            result = self.run_task(task["task_id"])
            return {"workflow": to_plain(definition), **result}
        if workflow_id == "task_planning_v1":
            planning_result = self.company_os.task_planning_workflow.run(self.tasks[task["task_id"]])
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(planning_result.task),
                "output": planning_result.output,
                "approval_required": planning_result.approval_required,
                "blocked": planning_result.blocked,
                "incident": None,
            }
        if workflow_id == "agent_collaboration_v1":
            collaboration_result = self.company_os.agent_collaboration_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(collaboration_result.task),
                "output": collaboration_result.output,
                "meeting": to_plain(collaboration_result.meeting) if collaboration_result.meeting else None,
                "handoff": to_plain(collaboration_result.handoff) if collaboration_result.handoff else None,
                "message": to_plain(collaboration_result.message) if collaboration_result.message else None,
                "approval_required": False,
                "blocked": collaboration_result.blocked,
                "incident": to_plain(collaboration_result.incident) if collaboration_result.incident else None,
            }
        if workflow_id == "skill_missing_v1":
            missing_result = self.company_os.skill_missing_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(missing_result.task),
                "output": missing_result.output,
                "outcome": missing_result.outcome,
                "replacement": missing_result.replacement,
                "composition": missing_result.composition,
                "temporary_skill": missing_result.temporary_skill,
                "proposal": missing_result.proposal,
                "approval_required": missing_result.approval_required,
                "blocked": missing_result.blocked,
                "incident": to_plain(missing_result.incident) if missing_result.incident else None,
            }
        if workflow_id == "agent_missing_v1":
            missing_result = self.company_os.agent_missing_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(missing_result.task),
                "output": missing_result.output,
                "outcome": missing_result.outcome,
                "existing_agent": missing_result.existing_agent,
                "knowledge_matches": missing_result.knowledge_matches,
                "proposal_plan": missing_result.proposal_plan,
                "risk_review": missing_result.risk_review,
                "proposal": missing_result.proposal,
                "approval_required": missing_result.approval_required,
                "blocked": missing_result.blocked,
                "incident": to_plain(missing_result.incident) if missing_result.incident else None,
            }
        if workflow_id == "approval_v1":
            approval_result = self.company_os.approval_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(approval_result.task),
                "output": approval_result.output,
                "outcome": approval_result.outcome,
                "approval": approval_result.approval,
                "risk": approval_result.risk,
                "approval_required": approval_result.approval_required,
                "blocked": approval_result.blocked,
                "incident": approval_result.incident,
            }
        if workflow_id == "quality_check_v1":
            quality_result = self.company_os.quality_check_workflow.run(self.tasks[task["task_id"]])
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(quality_result.task),
                "output": quality_result.output,
                "approval_required": quality_result.approval_required,
                "blocked": quality_result.blocked,
                "passed": quality_result.passed,
                "incident": to_plain(quality_result.incident) if quality_result.incident else None,
            }
        if workflow_id == "retrospective_v1":
            retrospective_result = self.company_os.retrospective_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return {
                "workflow": to_plain(definition),
                "task": to_plain(retrospective_result.task),
                "output": retrospective_result.output,
                "review": to_plain(retrospective_result.review) if retrospective_result.review else None,
                "knowledge": to_plain(retrospective_result.knowledge) if retrospective_result.knowledge else None,
                "approval_required": False,
                "blocked": retrospective_result.blocked,
                "incident": to_plain(retrospective_result.incident) if retrospective_result.incident else None,
            }
        if workflow_id == "github_project_analysis_v1":
            github_result = self.company_os.github_project_analysis_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return self._github_workflow_response(definition, github_result)
        if workflow_id == "tool_call_v1":
            tool_result = self.company_os.tool_call_workflow.run(
                self.tasks[task["task_id"]],
                workflow_input,
            )
            self.sync()
            return self._tool_workflow_response(definition, tool_result)
        raise ValueError("unsupported workflow execution mode")

    def _github_workflow_response(self, definition, result) -> dict:
        return {
            "workflow": to_plain(definition),
            "task": to_plain(result.task),
            "output": result.output,
            "outcome": result.outcome,
            "approval": result.approval,
            "proposal": result.proposal,
            "sandbox": result.sandbox,
            "knowledge": result.knowledge,
            "analysis": result.analysis,
            "risk": result.risk,
            "approval_required": result.approval_required,
            "blocked": result.blocked,
            "incident": to_plain(result.incident) if result.incident else None,
        }

    def _tool_workflow_response(self, definition, result) -> dict:
        return {
            "workflow": to_plain(definition),
            "task": to_plain(result.task),
            "output": result.output,
            "outcome": result.outcome,
            "tool": result.tool,
            "tool_run": result.tool_run,
            "approval": result.approval,
            "risk": result.risk,
            "approval_required": result.approval_required,
            "blocked": result.blocked,
            "incident": to_plain(result.incident) if result.incident else None,
        }

    def list_workflow_steps(self, run_id: str | None = None) -> list[dict]:
        return [to_plain(step) for step in self.company_os.traces.list_steps(run_id)]

    def list_model_usage(self) -> list[dict]:
        return [to_plain(record) for record in self.company_os.models.list_usage()]

    def list_cost_logs(self) -> list[dict]:
        return [to_plain(record) for record in self.company_os.budget.list_cost_logs()]

    def budget_summary(self) -> dict:
        return self.company_os.budget.summary()

    def update_budget_policy(
        self,
        actor_id: str,
        name: str,
        max_tokens_per_call: int,
        max_total_tokens: int,
        max_estimated_cost: float,
        cost_per_token: float,
        currency: str,
        enabled: bool,
    ) -> dict:
        if actor_id != "human_root":
            incident = self._report_incident(
                title="Budget policy update blocked",
                description="Only Human Root can update budget policy.",
                source_type="budget_policy",
                source_id=self.company_os.budget.policy.policy_id,
                risk_level=RiskLevel.HIGH,
                actor_id=actor_id,
                recommendation="Confirm the actor identity and keep Root-managed settings under Human Root control.",
            )
            self.company_os.audit.append(
                AuditEvent(
                    event_type="budget_policy_update_blocked",
                    actor_id=actor_id,
                    action="update_budget_policy",
                    task_id=None,
                    risk_level=RiskLevel.HIGH,
                    approval_status=ApprovalStatus.BLOCKED,
                    result="only_human_root_can_update_budget_policy",
                    output_ref=incident.incident_id,
                )
            )
            self.sync()
            raise ValueError("only human_root can update budget policy")

        policy = self.company_os.budget.update_policy(
            name=name,
            max_tokens_per_call=max_tokens_per_call,
            max_total_tokens=max_total_tokens,
            max_estimated_cost=max_estimated_cost,
            cost_per_token=cost_per_token,
            currency=currency,
            enabled=enabled,
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="budget_policy_updated",
                actor_id=actor_id,
                action="update_budget_policy",
                task_id=None,
                risk_level=RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="updated",
                input_ref=policy.name,
                output_ref=policy.policy_id,
            )
        )
        self.sync()
        return self.budget_summary()

    def list_incidents(self) -> list[dict]:
        return [to_plain(incident) for incident in self.company_os.incidents.list()]

    def list_backups(self) -> list[dict]:
        return [to_plain(backup) for backup in self.company_os.backups.list()]

    def list_agent_messages(self, agent_id: str | None = None, task_id: str | None = None) -> list[dict]:
        return [to_plain(message) for message in self.company_os.communication.list_messages(agent_id, task_id)]

    def send_agent_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        priority: str = "medium",
        requires_response: bool = False,
        task_id: str | None = None,
    ) -> dict:
        self.company_os.agents.get(from_agent)
        self.company_os.agents.get(to_agent)
        if not content.strip():
            raise ValueError("message content is required")
        message = self.company_os.communication.send_message(
            AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                message_type=message_type.strip() or "direct",
                content=content.strip(),
                priority=priority.strip() or "medium",
                requires_response=requires_response,
                task_id=task_id,
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_message_sent",
                actor_id=from_agent,
                action=f"send_{message.message_type}",
                task_id=task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="sent",
                input_ref=to_agent,
                output_ref=message.message_id,
            )
        )
        self.sync()
        return to_plain(message)

    def list_agent_meetings(self, task_id: str | None = None) -> list[dict]:
        return [to_plain(meeting) for meeting in self.company_os.communication.list_meetings(task_id)]

    def list_task_handoffs(self, task_id: str | None = None, agent_id: str | None = None) -> list[dict]:
        return [to_plain(handoff) for handoff in self.company_os.communication.list_handoffs(task_id, agent_id)]

    def list_agent_broadcasts(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict]:
        return [
            to_plain(broadcast)
            for broadcast in self.company_os.communication.list_broadcasts(task_id, agent_id, event_type)
        ]

    def list_agent_conflicts(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        return [to_plain(conflict) for conflict in self.company_os.communication.list_conflicts(task_id, agent_id, status)]

    def open_agent_conflict(
        self,
        raised_by_agent: str,
        opposing_agents: list[str],
        issue: str,
        positions: dict[str, str],
        priority_area: str = "safety",
        task_id: str | None = None,
    ) -> dict:
        raiser = self.company_os.agents.get(raised_by_agent)
        clean_opponents = [agent_id.strip() for agent_id in opposing_agents if agent_id.strip()]
        if not clean_opponents:
            raise ValueError("opposing agents are required")
        participants = [raised_by_agent, *clean_opponents]
        for agent_id in clean_opponents:
            self.company_os.agents.get(agent_id)
        if task_id is not None:
            self.tasks[task_id]
        if not issue.strip():
            raise ValueError("conflict issue is required")
        clean_priority_area = priority_area.strip() or "safety"
        if clean_priority_area not in ARBITRATION_PRIORITY_AREAS:
            raise ValueError("unknown arbitration priority area")
        clean_positions = {agent_id: text.strip() for agent_id, text in positions.items() if text.strip()}
        missing_positions = [agent_id for agent_id in participants if agent_id not in clean_positions]
        if missing_positions:
            raise ValueError(f"missing conflict positions for: {', '.join(missing_positions)}")
        request = ActionRequest(
            action="open_conflict",
            actor_id=raised_by_agent,
            task_id=task_id,
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            reason=issue.strip(),
            target=",".join(clean_opponents),
            metadata={"priority_area": clean_priority_area},
        )
        risk = self.company_os.risks.assess(request)
        permission = self.company_os.permissions.evaluate(raiser, request)
        if risk.blocked or permission.decision == ActionDecision.BLOCK:
            incident = self._report_incident(
                title="Agent conflict opening blocked",
                description=permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons),
                source_type="agent_conflict",
                source_id=raised_by_agent,
                risk_level=risk.level,
                task_id=task_id,
                actor_id=raised_by_agent,
                recommendation="Review the raising Agent permissions before retrying conflict arbitration.",
            )
            self.company_os.audit.append(
                AuditEvent(
                    event_type="agent_conflict_blocked",
                    actor_id=raised_by_agent,
                    action="open_conflict",
                    task_id=task_id,
                    risk_level=risk.level,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=incident.description,
                    input_ref=",".join(clean_opponents),
                    output_ref=incident.incident_id,
                )
            )
            self.sync()
            raise ValueError(incident.description)
        conflict = self.company_os.communication.open_conflict(
            AgentConflict(
                raised_by_agent=raised_by_agent,
                opposing_agents=clean_opponents,
                issue=issue.strip(),
                positions=clean_positions,
                priority_area=clean_priority_area,
                task_id=task_id,
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_conflict_opened",
                actor_id=raised_by_agent,
                action="open_conflict",
                task_id=task_id,
                risk_level=risk.level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="opened",
                input_ref=",".join(clean_opponents),
                output_ref=conflict.conflict_id,
            )
        )
        self.sync()
        return to_plain(conflict)

    def resolve_agent_conflict(
        self,
        conflict_id: str,
        resolved_by: str,
        resolution: str,
        selected_position_agent: str | None = None,
    ) -> dict:
        conflict = self.company_os.communication.get_conflict(conflict_id)
        if conflict.status != "open":
            raise ValueError("conflict is already resolved")
        if not resolution.strip():
            raise ValueError("conflict resolution is required")
        participants = {conflict.raised_by_agent, *conflict.opposing_agents}
        if selected_position_agent and selected_position_agent not in participants:
            raise ValueError("selected position agent must be a conflict participant")
        risk_level = RiskLevel.LOW
        if resolved_by != "human_root":
            resolver = self.company_os.agents.get(resolved_by)
            request = ActionRequest(
                action="resolve_conflict",
                actor_id=resolved_by,
                task_id=conflict.task_id,
                permission_level=PermissionLevel.L2_INTERNAL_WRITE,
                reason=resolution.strip(),
                target=conflict.conflict_id,
                metadata={"priority_area": conflict.priority_area},
            )
            risk = self.company_os.risks.assess(request)
            permission = self.company_os.permissions.evaluate(resolver, request)
            risk_level = risk.level
            if risk.blocked or permission.decision == ActionDecision.BLOCK:
                incident = self._report_incident(
                    title="Agent conflict resolution blocked",
                    description=permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons),
                    source_type="agent_conflict",
                    source_id=conflict.conflict_id,
                    risk_level=risk.level,
                    task_id=conflict.task_id,
                    actor_id=resolved_by,
                    recommendation="Escalate the conflict to Human Root or an Agent with internal-write authority.",
                )
                self.company_os.audit.append(
                    AuditEvent(
                        event_type="agent_conflict_resolution_blocked",
                        actor_id=resolved_by,
                        action="resolve_conflict",
                        task_id=conflict.task_id,
                        risk_level=risk.level,
                        approval_status=ApprovalStatus.BLOCKED,
                        result=incident.description,
                        input_ref=conflict.conflict_id,
                        output_ref=incident.incident_id,
                    )
                )
                self.sync()
                raise ValueError(incident.description)

        resolved = self.company_os.communication.resolve_conflict(
            conflict_id=conflict_id,
            resolved_by=resolved_by,
            resolution=resolution.strip(),
            selected_position_agent=selected_position_agent,
            resolved_at=utc_now(),
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_conflict_resolved",
                actor_id=resolved_by,
                action="resolve_conflict",
                task_id=conflict.task_id,
                risk_level=risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="resolved",
                input_ref=selected_position_agent,
                output_ref=conflict.conflict_id,
            )
        )
        self.sync()
        return to_plain(resolved)

    def broadcast_agent_event(
        self,
        from_agent: str,
        audience_agents: list[str],
        event_type: str,
        title: str,
        content: str,
        priority: str = "medium",
        task_id: str | None = None,
    ) -> dict:
        sender = self.company_os.agents.get(from_agent)
        clean_audience = [agent_id.strip() for agent_id in audience_agents if agent_id.strip()]
        if not clean_audience:
            raise ValueError("broadcast audience is required")
        for agent_id in clean_audience:
            self.company_os.agents.get(agent_id)
        if task_id is not None:
            self.tasks[task_id]
        if not event_type.strip():
            raise ValueError("broadcast event_type is required")
        if not title.strip():
            raise ValueError("broadcast title is required")
        if not content.strip():
            raise ValueError("broadcast content is required")
        request = ActionRequest(
            action="broadcast_event",
            actor_id=from_agent,
            task_id=task_id,
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            reason=title.strip(),
            target=",".join(clean_audience),
            metadata={"event_type": event_type.strip(), "audience_agents": clean_audience},
        )
        risk = self.company_os.risks.assess(request)
        permission = self.company_os.permissions.evaluate(sender, request)
        if risk.blocked or permission.decision == ActionDecision.BLOCK:
            incident = self._report_incident(
                title="Agent broadcast blocked",
                description=permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons),
                source_type="agent_broadcast",
                source_id=from_agent,
                risk_level=risk.level,
                task_id=task_id,
                actor_id=from_agent,
                recommendation="Review the sender Agent permissions before retrying the broadcast.",
            )
            self.company_os.audit.append(
                AuditEvent(
                    event_type="agent_broadcast_blocked",
                    actor_id=from_agent,
                    action="broadcast_event",
                    task_id=task_id,
                    risk_level=risk.level,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=incident.description,
                    input_ref=",".join(clean_audience),
                    output_ref=incident.incident_id,
                )
            )
            self.sync()
            raise ValueError(incident.description)
        if risk.requires_approval or permission.decision == ActionDecision.REQUIRE_APPROVAL:
            raise ValueError("agent broadcast unexpectedly requires approval")

        broadcast = self.company_os.communication.broadcast_event(
            AgentBroadcast(
                from_agent=from_agent,
                audience_agents=clean_audience,
                event_type=event_type.strip(),
                title=title.strip(),
                content=content.strip(),
                priority=priority.strip() or "medium",
                task_id=task_id,
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_broadcast_sent",
                actor_id=from_agent,
                action="broadcast_event",
                task_id=task_id,
                risk_level=risk.level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="sent",
                input_ref=",".join(clean_audience),
                output_ref=broadcast.broadcast_id,
            )
        )
        self.sync()
        return to_plain(broadcast)

    def handoff_task(
        self,
        task_id: str,
        from_agent: str,
        to_agent: str,
        reason: str,
        instructions: str | None = None,
    ) -> dict:
        task = self.tasks[task_id]
        from_agent_record = self.company_os.agents.get(from_agent)
        self.company_os.agents.get(to_agent)
        if not reason.strip():
            raise ValueError("handoff reason is required")
        request = ActionRequest(
            action="handoff_task",
            actor_id=from_agent,
            task_id=task_id,
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            reason=reason.strip(),
            target=to_agent,
            metadata={"to_agent": to_agent},
        )
        risk = self.company_os.risks.assess(request)
        permission = self.company_os.permissions.evaluate(from_agent_record, request)
        if risk.blocked or permission.decision == ActionDecision.BLOCK:
            incident = self._report_incident(
                title="Task handoff blocked",
                description=permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons),
                source_type="task_handoff",
                source_id=task_id,
                risk_level=risk.level,
                task_id=task_id,
                actor_id=from_agent,
                recommendation="Review the sender Agent permissions before retrying the handoff.",
            )
            self.company_os.audit.append(
                AuditEvent(
                    event_type="task_handoff_blocked",
                    actor_id=from_agent,
                    action="handoff_task",
                    task_id=task_id,
                    risk_level=risk.level,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=incident.description,
                    input_ref=to_agent,
                    output_ref=incident.incident_id,
                )
            )
            self.sync()
            raise ValueError(incident.description)
        if risk.requires_approval or permission.decision == ActionDecision.REQUIRE_APPROVAL:
            raise ValueError("task handoff unexpectedly requires approval")

        content = instructions.strip() if instructions and instructions.strip() else reason.strip()
        message = self.company_os.communication.send_message(
            AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                message_type="handoff",
                content=content,
                priority="medium",
                requires_response=True,
                task_id=task_id,
            )
        )
        handoff = self.company_os.communication.record_handoff(
            TaskHandoff(
                task_id=task_id,
                from_agent=from_agent,
                to_agent=to_agent,
                reason=reason.strip(),
                instructions=content,
                task_status=task.status,
                message_id=message.message_id,
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="task_handoff_recorded",
                actor_id=from_agent,
                action="handoff_task",
                task_id=task_id,
                risk_level=risk.level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="recorded",
                input_ref=message.message_id,
                output_ref=handoff.handoff_id,
            )
        )
        self.sync()
        return {"handoff": to_plain(handoff), "message": to_plain(message)}

    def record_agent_meeting(
        self,
        title: str,
        organizer_agent: str,
        participant_agents: list[str],
        agenda: str,
        meeting_type: str = "group",
        task_id: str | None = None,
        minutes: str | None = None,
    ) -> dict:
        self.company_os.agents.get(organizer_agent)
        clean_participants = [agent_id.strip() for agent_id in participant_agents if agent_id.strip()]
        if not clean_participants:
            raise ValueError("meeting participants are required")
        for agent_id in clean_participants:
            self.company_os.agents.get(agent_id)
        if not title.strip():
            raise ValueError("meeting title is required")
        if not agenda.strip():
            raise ValueError("meeting agenda is required")
        meeting = self.company_os.communication.record_meeting(
            AgentMeeting(
                title=title.strip(),
                organizer_agent=organizer_agent,
                participant_agents=clean_participants,
                agenda=agenda.strip(),
                meeting_type=meeting_type.strip() or "group",
                task_id=task_id,
                minutes=minutes.strip() if minutes and minutes.strip() else None,
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_meeting_recorded",
                actor_id=organizer_agent,
                action=f"record_{meeting.meeting_type}_meeting",
                task_id=task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="recorded",
                input_ref=",".join(clean_participants),
                output_ref=meeting.meeting_id,
            )
        )
        self.sync()
        return to_plain(meeting)

    def create_backup(self, actor_id: str, reason: str) -> dict:
        if not reason.strip():
            raise ValueError("backup reason is required")
        snapshot = self._state_snapshot()
        backup = self.company_os.backups.create(
            BackupRecord(
                reason=reason.strip(),
                actor_id=actor_id,
                snapshot=snapshot,
                rollback_plan="Restore through checksum verification, Human Root approval, and an automatic pre-restore checkpoint.",
                backup_checksum=self._backup_checksum(snapshot),
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="backup_created",
                actor_id=actor_id,
                action="create_backup",
                task_id=None,
                risk_level=RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="created",
                input_ref=reason,
                output_ref=backup.backup_id,
            )
        )
        self.sync()
        return to_plain(backup)

    def verify_backup(self, backup_id: str, actor_id: str) -> dict:
        backup = self.company_os.backups.get(backup_id)
        verification = self._backup_integrity_result(backup)
        self.company_os.audit.append(
            AuditEvent(
                event_type="backup_verified",
                actor_id=actor_id,
                action="verify_backup",
                task_id=None,
                risk_level=RiskLevel.LOW if verification["verified"] else RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=verification["status"],
                input_ref=verification["expected_checksum"],
                output_ref=backup.backup_id,
                error=None if verification["verified"] else f"Backup integrity status: {verification['status']}",
            )
        )
        self.sync()
        return verification

    def request_backup_restore(self, backup_id: str, actor_id: str, reason: str) -> dict:
        if not reason.strip():
            raise ValueError("restore reason is required")
        backup = self.company_os.backups.get(backup_id)
        verification = self._backup_integrity_result(backup)
        if not verification["verified"]:
            self.company_os.audit.append(
                AuditEvent(
                    event_type="backup_restore_request_blocked",
                    actor_id=actor_id,
                    action="restore_backup",
                    task_id=None,
                    risk_level=RiskLevel.MEDIUM,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=verification["status"],
                    input_ref=reason,
                    output_ref=backup.backup_id,
                    error=f"Backup integrity status: {verification['status']}",
                )
            )
            incident = self._report_incident(
                title="Backup restore request blocked",
                description=f"Backup {backup.backup_id} failed integrity verification: {verification['status']}.",
                source_type="backup",
                source_id=backup.backup_id,
                risk_level=RiskLevel.MEDIUM,
                actor_id=actor_id,
                recommendation="Use a verified backup or inspect storage tampering before requesting restore approval.",
            )
            self.sync()
            return {
                "backup": to_plain(backup),
                "verification": verification,
                "approval": None,
                "result": "blocked",
                "incident": to_plain(incident),
            }
        approval = self.request_action_approval(
            action="restore_backup",
            actor_id=actor_id,
            permission_level=PermissionLevel.L4_HIGH_RISK,
            reason=reason.strip(),
            target=backup.backup_id,
            possible_benefit="Restore system state from a verified backup after Human Root review.",
            possible_loss="Restoring state can overwrite current operational state and must not bypass audit or approval.",
            reversible=False,
        )
        return {
            "backup": to_plain(backup),
            "verification": verification,
            "approval": approval["approval"],
            "result": approval["result"],
            "risk": approval["risk"],
            "permission_decision": approval["permission_decision"],
            "permission_reason": approval["permission_reason"],
            "incident": approval["incident"],
        }

    def execute_backup_restore(
        self,
        backup_id: str,
        approval_id: str,
        actor_id: str,
        reason: str,
    ) -> dict:
        if self.persistence is None:
            raise ValueError("backup restore execution requires durable persistence")
        if actor_id != "human_root":
            raise ValueError("only human_root can execute a backup restore")
        if not reason.strip():
            raise ValueError("restore execution reason is required")

        backup = self.company_os.backups.get(backup_id)
        verification = self._backup_integrity_result(backup)
        if not verification["verified"]:
            self.company_os.audit.append(
                AuditEvent(
                    event_type="backup_restore_execution_blocked",
                    actor_id=actor_id,
                    action="restore_backup",
                    task_id=None,
                    risk_level=RiskLevel.HIGH,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=verification["status"],
                    input_ref=approval_id,
                    output_ref=backup.backup_id,
                    error=f"Backup integrity status: {verification['status']}",
                )
            )
            incident = self._report_incident(
                title="Backup restore execution blocked",
                description=f"Backup {backup.backup_id} failed integrity verification during restore execution.",
                source_type="backup",
                source_id=backup.backup_id,
                risk_level=RiskLevel.HIGH,
                actor_id=actor_id,
                recommendation="Do not restore this backup; inspect storage integrity and use a verified checkpoint.",
            )
            self.sync()
            return {
                "backup": to_plain(backup),
                "verification": verification,
                "approval": None,
                "safety_backup": None,
                "restored_counts": None,
                "result": "blocked",
                "incident": to_plain(incident),
            }

        approval = self.company_os.approvals.get(approval_id)
        if approval.request.action != "restore_backup" or approval.request.target != backup_id:
            raise ValueError("approval does not authorize this backup restore")
        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("backup restore approval is not approved")
        if approval.decided_by != "human_root":
            raise ValueError("backup restore must be approved by human_root")
        if any(
            event.event_type == "backup_restored" and event.input_ref == approval_id
            for event in self.company_os.audit.list()
        ):
            raise ValueError("backup restore approval has already been used")

        backup_payload = to_plain(backup)
        approval_payload = to_plain(approval)
        safety_backup = self.create_backup(
            actor_id,
            f"Automatic pre-restore checkpoint before applying {backup_id}: {reason.strip()}",
        )
        restored_counts = self.persistence.restore_snapshot(
            backup.snapshot,
            approval_id=approval_id,
            backup_id=backup_id,
            actor_id=actor_id,
            safety_backup_id=safety_backup["backup_id"],
        )

        # Reload the committed snapshot while retaining users, approvals, audit, incidents, and backups.
        self.__post_init__()
        self.company_os.audit.append(
            AuditEvent(
                event_type="backup_restored",
                actor_id=actor_id,
                action="restore_backup",
                task_id=None,
                risk_level=RiskLevel.HIGH,
                approval_status=ApprovalStatus.APPROVED,
                result="restored",
                input_ref=approval_id,
                output_ref=backup_id,
            )
        )
        self.sync()
        return {
            "backup": backup_payload,
            "verification": verification,
            "approval": approval_payload,
            "safety_backup": safety_backup,
            "restored_counts": restored_counts,
            "result": "restored",
            "incident": None,
        }

    def list_domain_events(
        self,
        event_type: str | None = None,
        source_type: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if limit <= 0 or limit > 500:
            raise ValueError("event limit must be between 1 and 500")
        events = self.company_os.events.list(event_type, source_type, task_id)
        return [to_plain(event) for event in events[-limit:]]

    def list_scheduled_jobs(
        self,
        status: str | None = None,
        action: str | None = None,
    ) -> list[dict]:
        return [to_plain(job) for job in self.company_os.scheduler.list(status, action)]

    def list_scheduled_executions(self, schedule_id: str | None = None) -> list[dict]:
        return [
            to_plain(execution)
            for execution in self.company_os.scheduler.list_executions(schedule_id)
        ]

    def list_due_scheduled_jobs(
        self,
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if limit <= 0 or limit > 100:
            raise ValueError("scheduler due-job limit must be between 1 and 100")
        tick_time = self._aware_utc(now or utc_now(), "now")
        due_jobs = sorted(
            (
                job
                for job in self.company_os.scheduler.list(status=ScheduleStatus.ACTIVE.value)
                if job.next_run_at <= tick_time
            ),
            key=lambda item: (item.next_run_at, item.schedule_id),
        )[:limit]
        return [to_plain(job) for job in due_jobs]

    def create_scheduled_job(
        self,
        name: str,
        action: ScheduleAction,
        payload: dict,
        created_by: str,
        next_run_at: datetime,
        interval_seconds: int | None = None,
        max_runs: int | None = None,
    ) -> dict:
        if not name.strip():
            raise ValueError("schedule name is required")
        self._authorize_schedule_actor(created_by)
        next_run_at = self._aware_utc(next_run_at, "next_run_at")
        if interval_seconds is not None and interval_seconds < 60:
            raise ValueError("recurring schedule interval must be at least 60 seconds")
        if max_runs is not None and max_runs <= 0:
            raise ValueError("schedule max_runs must be greater than zero")
        if max_runs is not None and interval_seconds is None and max_runs != 1:
            raise ValueError("one-time schedules can only use max_runs=1")
        clean_payload = self._validate_schedule_payload(action, payload)

        job = self.company_os.scheduler.create(
            ScheduledJob(
                name=name.strip(),
                action=action,
                payload=clean_payload,
                created_by=created_by,
                next_run_at=next_run_at,
                interval_seconds=interval_seconds,
                max_runs=max_runs,
            )
        )
        self._publish_domain_event(
            event_type="schedule.created",
            source_type="schedule",
            source_id=job.schedule_id,
            actor_id=created_by,
            payload={"action": job.action.value, "next_run_at": job.next_run_at.isoformat()},
            task_id=job.payload.get("task_id"),
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="scheduled_job_created",
                actor_id=created_by,
                action="create_schedule",
                task_id=job.payload.get("task_id"),
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=job.status.value,
                input_ref=job.action.value,
                output_ref=job.schedule_id,
            )
        )
        self.sync()
        return to_plain(job)

    def pause_scheduled_job(self, schedule_id: str, actor_id: str) -> dict:
        job = self.company_os.scheduler.get(schedule_id)
        self._authorize_schedule_control(job, actor_id)
        if job.status != ScheduleStatus.ACTIVE:
            raise ValueError("only active schedules can be paused")
        job.status = ScheduleStatus.PAUSED
        job.updated_at = utc_now()
        self._record_schedule_state_change(job, actor_id, "paused")
        return to_plain(job)

    def resume_scheduled_job(self, schedule_id: str, actor_id: str) -> dict:
        job = self.company_os.scheduler.get(schedule_id)
        self._authorize_schedule_control(job, actor_id)
        if job.status != ScheduleStatus.PAUSED:
            raise ValueError("only paused schedules can be resumed")
        job.status = ScheduleStatus.ACTIVE
        job.updated_at = utc_now()
        self._record_schedule_state_change(job, actor_id, "resumed")
        return to_plain(job)

    def cancel_scheduled_job(self, schedule_id: str, actor_id: str) -> dict:
        job = self.company_os.scheduler.get(schedule_id)
        self._authorize_schedule_control(job, actor_id)
        if job.status not in {ScheduleStatus.ACTIVE, ScheduleStatus.PAUSED}:
            raise ValueError("only active or paused schedules can be cancelled")
        job.status = ScheduleStatus.CANCELLED
        job.updated_at = utc_now()
        self._record_schedule_state_change(job, actor_id, "cancelled")
        return to_plain(job)

    def tick_scheduler(
        self,
        actor_id: str = "human_root",
        now: datetime | None = None,
        limit: int = 50,
    ) -> dict:
        if actor_id != "human_root":
            raise ValueError("only human_root can tick the scheduler")
        if limit <= 0 or limit > 100:
            raise ValueError("scheduler tick limit must be between 1 and 100")
        tick_time = self._aware_utc(now or utc_now(), "now")
        due_job_ids = [
            item["schedule_id"]
            for item in self.list_due_scheduled_jobs(tick_time, limit)
        ]
        due_jobs = [self.company_os.scheduler.get(schedule_id) for schedule_id in due_job_ids]
        executions = [
            self._execute_scheduled_job(job, actor_id, tick_time)
            for job in due_jobs
        ]
        self.company_os.audit.append(
            AuditEvent(
                event_type="scheduler_tick",
                actor_id=actor_id,
                action="tick_scheduler",
                task_id=None,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=f"{len(executions)} executed",
                input_ref=tick_time.isoformat(),
                output_ref=None,
            )
        )
        self.sync()
        return {
            "tick_time": tick_time.isoformat(),
            "due_count": len(due_jobs),
            "executed_count": len(executions),
            "executions": [to_plain(execution) for execution in executions],
        }

    def execute_queued_schedule(
        self,
        schedule_id: str,
        expected_next_run_at: str,
        actor_id: str = "human_root",
        now: datetime | None = None,
    ) -> dict:
        if self.persistence is None:
            raise ValueError("queued schedule execution requires durable persistence")
        if actor_id != "human_root":
            raise ValueError("only human_root can execute queued schedules")
        expected = self._aware_utc(
            datetime.fromisoformat(expected_next_run_at),
            "expected_next_run_at",
        )
        execution_time = self._aware_utc(now or utc_now(), "now")
        job = self.company_os.scheduler.get(schedule_id)
        if job.status != ScheduleStatus.ACTIVE or job.next_run_at != expected:
            return {
                "schedule_id": schedule_id,
                "status": "skipped",
                "reason": "schedule state no longer matches the queued delivery",
                "execution": None,
            }
        if job.next_run_at > execution_time:
            return {
                "schedule_id": schedule_id,
                "status": "skipped",
                "reason": "schedule is not due yet",
                "execution": None,
            }

        execution_token = f"{schedule_id}:{expected.isoformat()}"
        execution = self._execute_scheduled_job(
            job,
            actor_id,
            execution_time,
            execution_token=execution_token,
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="scheduler_worker_execution",
                actor_id=actor_id,
                action="execute_queued_schedule",
                task_id=job.payload.get("task_id"),
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=execution.status.value,
                input_ref=execution_token,
                output_ref=execution.execution_id,
                error=execution.error,
            )
        )
        self.sync()
        return {
            "schedule_id": schedule_id,
            "status": "executed",
            "reason": None,
            "execution": to_plain(execution),
        }

    def acknowledge_incident(self, incident_id: str, actor_id: str, note: str | None = None) -> dict:
        incident = self.company_os.incidents.acknowledge(incident_id, actor_id, note)
        self.company_os.audit.append(
            AuditEvent(
                event_type="incident_acknowledged",
                actor_id=actor_id,
                action="acknowledge_incident",
                task_id=incident.task_id,
                risk_level=incident.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=incident.status.value,
                input_ref=note,
                output_ref=incident.incident_id,
            )
        )
        self.sync()
        return to_plain(incident)

    def resolve_incident(self, incident_id: str, actor_id: str, note: str) -> dict:
        incident = self.company_os.incidents.resolve(incident_id, actor_id, note)
        self.company_os.audit.append(
            AuditEvent(
                event_type="incident_resolved",
                actor_id=actor_id,
                action="resolve_incident",
                task_id=incident.task_id,
                risk_level=incident.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=incident.status.value,
                input_ref=note,
                output_ref=incident.incident_id,
            )
        )
        self.sync()
        return to_plain(incident)

    def generate_model_response(
        self,
        prompt: str,
        actor_id: str,
        purpose: str,
        task_id: str | None = None,
        model_name: str = "deterministic_mock_v1",
        provider: str = "local",
    ) -> dict:
        self.company_os.agents.get(actor_id)
        budget_check = self.company_os.budget.check_model_call(prompt, purpose)
        if not budget_check.allowed:
            cost_log = self.company_os.budget.record_cost(
                source_type="model_usage",
                source_id="blocked",
                actor_id=actor_id,
                task_id=task_id,
                tokens=budget_check.estimated_tokens,
                amount=budget_check.estimated_cost,
                result="blocked",
                reason=budget_check.reason,
            )
            self.company_os.audit.append(
                AuditEvent(
                    event_type="model_blocked",
                    actor_id=actor_id,
                    action=purpose,
                    task_id=task_id,
                    risk_level=RiskLevel.MEDIUM,
                    approval_status=ApprovalStatus.BLOCKED,
                    result=budget_check.reason,
                )
            )
            incident = self._report_incident(
                title="Model call blocked by budget policy",
                description=budget_check.reason,
                source_type="model_usage",
                source_id=cost_log.record_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=task_id,
                actor_id=actor_id,
                recommendation="Review the budget policy, prompt size, or model usage need before retrying.",
            )
            self.sync()
            return {
                "output": None,
                "usage": None,
                "budget": to_plain(budget_check),
                "cost_log": to_plain(cost_log),
                "incident": to_plain(incident),
                "blocked": True,
            }
        response = self.company_os.models.generate(
            prompt=prompt,
            actor_id=actor_id,
            purpose=purpose,
            task_id=task_id,
            model_name=model_name,
            provider=provider,
            cost_per_token=self.company_os.budget.policy.cost_per_token,
        )
        cost_log = self.company_os.budget.record_cost(
            source_type="model_usage",
            source_id=response.usage.record_id,
            actor_id=actor_id,
            task_id=task_id,
            tokens=response.usage.total_tokens,
            amount=response.usage.estimated_cost,
            result="recorded",
            reason="model usage recorded",
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="model_called",
                actor_id=actor_id,
                action=purpose,
                task_id=task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="model usage recorded",
                input_ref=response.usage.input_ref,
                output_ref=response.usage.output_ref,
                model_name=response.usage.model_name,
            )
        )
        self.sync()
        return {
            "output": response.output,
            "usage": to_plain(response.usage),
            "budget": to_plain(budget_check),
            "cost_log": to_plain(cost_log),
            "incident": None,
            "blocked": False,
        }

    def request_skill_run(
        self,
        skill_id: str,
        actor_id: str,
        input: dict,
        reason: str,
        task_id: str | None = None,
        authorization_approval_id: str | None = None,
    ) -> dict:
        skill = self.company_os.skills.get(skill_id)
        agent = self.company_os.agents.get(actor_id)
        permission_level = PermissionLevel.L2_INTERNAL_WRITE if skill_id == "memory_write_skill_v1" else PermissionLevel.L1_DRAFT
        request = ActionRequest(
            action=f"run_skill:{skill.skill_id}",
            actor_id=actor_id,
            task_id=task_id,
            permission_level=permission_level,
            reason=reason,
            target=skill.skill_id,
            metadata={"skill_id": skill.skill_id},
        )
        assessed = self.company_os.risks.assess(request)
        risk = RiskAssessment(
            request=request,
            level=skill.risk_level,
            reasons=(f"registered Skill risk is {skill.risk_level.value}",),
            requires_approval=skill.requires_approval or assessed.requires_approval,
            blocked=skill.risk_level == RiskLevel.FORBIDDEN or assessed.blocked,
        )
        permission = self.company_os.permissions.evaluate(agent, request)
        run = SkillRun(
            skill_id=skill.skill_id,
            actor_id=actor_id,
            input=input,
            reason=reason,
            task_id=task_id,
            risk_level=risk.level,
        )
        approval = None
        approval_status = ApprovalStatus.NOT_REQUIRED
        authorization = None
        if authorization_approval_id is not None:
            authorization = self.company_os.approvals.get(authorization_approval_id)
            approved_skills = authorization.request.metadata.get("approved_skill_ids", [])
            if authorization.status != ApprovalStatus.APPROVED:
                raise ValueError("Skill authorization approval is not approved")
            if authorization.request.task_id != task_id:
                raise ValueError("Skill authorization approval does not match task")
            if skill.skill_id not in approved_skills:
                raise ValueError("Skill is outside the authorization approval scope")

        if not skill.enabled:
            run.status, run.error = SkillRunStatus.BLOCKED, "skill is disabled"
            run.completed_at = utc_now()
        elif skill.skill_id not in agent.allowed_skills or agent.agent_id not in skill.allowed_agents:
            run.status, run.error = SkillRunStatus.BLOCKED, "skill is not authorized for this agent"
            run.completed_at = utc_now()
        elif risk.blocked or permission.decision == ActionDecision.BLOCK:
            run.status = SkillRunStatus.BLOCKED
            run.error = permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons)
            run.completed_at = utc_now()
        elif risk.requires_approval or permission.decision == ActionDecision.REQUIRE_APPROVAL:
            if authorization is not None:
                approval = authorization
                run.approval_id = authorization.approval_id
                approval_status = authorization.status
                self._execute_skill_run(run, skill)
            else:
                approval = self.company_os.approvals.request_approval(
                    request=request,
                    risk=risk,
                    possible_benefit=f"Run {skill.name} for a controlled task step.",
                    possible_loss="Skill output could be incorrect, unsafe, or create unintended internal state.",
                )
                run.status = SkillRunStatus.WAITING_APPROVAL
                run.approval_id = approval.approval_id
                approval_status = approval.status
        else:
            self._execute_skill_run(run, skill)

        self.skill_runs[run.run_id] = run
        incident = None
        if run.status == SkillRunStatus.BLOCKED:
            incident = self._report_incident(
                title="Skill run blocked",
                description=run.error or "Skill run was blocked by policy.",
                source_type="skill_run",
                source_id=run.run_id,
                risk_level=run.risk_level,
                task_id=task_id,
                actor_id=actor_id,
                recommendation="Review Skill enablement, symmetric Agent authorization, risk, and permission boundaries.",
            )
        self.company_os.audit.append(
            AuditEvent(
                event_type="skill_run_requested",
                actor_id=actor_id,
                action=request.action,
                task_id=task_id,
                risk_level=risk.level,
                approval_status=approval_status,
                result=run.status.value,
                input_ref=reason,
                output_ref=run.run_id,
                error=run.error,
            )
        )
        self.sync()
        return {
            "skill": to_plain(skill),
            "run": to_plain(run),
            "risk": to_plain(risk),
            "permission_decision": permission.decision.value,
            "permission_reason": permission.reason,
            "approval": to_plain(approval) if approval else None,
            "incident": to_plain(incident) if incident else None,
        }

    def request_tool_run(
        self,
        tool_id: str,
        actor_id: str,
        input: dict,
        reason: str,
        task_id: str | None = None,
    ) -> dict:
        tool = self.company_os.tools.get(tool_id)
        agent = self.company_os.agents.get(actor_id)
        request = ActionRequest(
            action=tool.action,
            actor_id=actor_id,
            task_id=task_id,
            permission_level=tool.permission_level,
            reason=reason,
            target=tool.tool_id,
            metadata={"tool_id": tool.tool_id},
        )
        risk = self.company_os.risks.assess(request)
        permission = self.company_os.permissions.evaluate(agent, request)
        run = ToolRun(
            tool_id=tool.tool_id,
            actor_id=actor_id,
            action=tool.action,
            input=input,
            reason=reason,
            task_id=task_id,
            risk_level=risk.level,
        )
        approval = None
        approval_status = ApprovalStatus.NOT_REQUIRED

        if not tool.enabled:
            run.status = ToolRunStatus.BLOCKED
            run.error = "tool is disabled"
            run.completed_at = utc_now()
        elif tool.tool_id not in agent.allowed_tools:
            run.status = ToolRunStatus.BLOCKED
            run.error = "tool is not allowed for this agent"
            run.completed_at = utc_now()
        elif risk.blocked or permission.decision == ActionDecision.BLOCK:
            run.status = ToolRunStatus.BLOCKED
            run.error = permission.reason if permission.decision == ActionDecision.BLOCK else "; ".join(risk.reasons)
            run.completed_at = utc_now()
        elif risk.requires_approval or permission.decision == ActionDecision.REQUIRE_APPROVAL or tool.requires_approval:
            approval = self.company_os.approvals.request_approval(
                request=request,
                risk=risk,
                possible_benefit=f"Use {tool.name} for a controlled task step.",
                possible_loss="Tool execution could change state, expose data, or call an external system.",
            )
            run.status = ToolRunStatus.WAITING_APPROVAL
            run.approval_id = approval.approval_id
            approval_status = approval.status
        else:
            self._execute_tool_run(run, tool)

        self.tool_runs[run.run_id] = run
        incident = None
        if run.status == ToolRunStatus.BLOCKED:
            incident = self._report_incident(
                title="Tool run blocked",
                description=run.error or "Tool run was blocked by policy.",
                source_type="tool_run",
                source_id=run.run_id,
                risk_level=run.risk_level,
                task_id=task_id,
                actor_id=actor_id,
                recommendation="Review tool enablement, Agent allowed_tools, and permission boundaries.",
            )
        self.company_os.audit.append(
            AuditEvent(
                event_type="tool_run_requested",
                actor_id=actor_id,
                action=tool.action,
                task_id=task_id,
                risk_level=risk.level,
                approval_status=approval_status,
                result=run.status.value,
                input_ref=reason,
                output_ref=run.run_id,
                error=run.error,
            )
        )
        self.sync()
        return {
            "tool": to_plain(tool),
            "run": to_plain(run),
            "risk": to_plain(risk),
            "permission_decision": permission.decision.value,
            "permission_reason": permission.reason,
            "approval": to_plain(approval) if approval else None,
            "incident": to_plain(incident) if incident else None,
        }

    def create_task(
        self,
        title: str,
        description: str,
        user_id: str = "human_root",
        task_id: str | None = None,
    ) -> dict:
        if task_id is not None and task_id in self.tasks:
            existing = self.tasks[task_id]
            if (
                existing.title != title
                or existing.description != description
                or existing.user_id != user_id
            ):
                raise ValueError("task_id already exists with different task input")
            return to_plain(existing)
        if task_id is None:
            task = Task(title=title, description=description, user_id=user_id)
        else:
            task = Task(
                title=title,
                description=description,
                user_id=user_id,
                task_id=task_id,
            )
        self.tasks[task.task_id] = task
        self.sync()
        return to_plain(task)

    def create_strategic_goal(
        self,
        title: str,
        description: str,
        owner_agent: str,
        target_metric: str,
        target_value: float,
        current_value: float = 0.0,
    ) -> dict:
        self.company_os.agents.get(owner_agent)
        if not title.strip():
            raise ValueError("goal title is required")
        if not description.strip():
            raise ValueError("goal description is required")
        if not target_metric.strip():
            raise ValueError("goal target_metric is required")
        if target_value <= 0:
            raise ValueError("goal target_value must be greater than 0")
        goal = self.company_os.goals.create(
            StrategicGoal(
                title=title.strip(),
                description=description.strip(),
                owner_agent=owner_agent,
                target_metric=target_metric.strip(),
                target_value=target_value,
                current_value=current_value,
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="strategic_goal_created",
                actor_id=owner_agent,
                action="create_strategic_goal",
                task_id=None,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=goal.status.value,
                input_ref=goal.target_metric,
                output_ref=goal.goal_id,
            )
        )
        self.sync()
        return to_plain(goal)

    def list_strategic_goals(self, status: str | None = None, owner_agent: str | None = None) -> list[dict]:
        return [to_plain(goal) for goal in self.company_os.goals.list(status, owner_agent)]

    def update_strategic_goal_progress(
        self,
        goal_id: str,
        current_value: float,
        status: GoalStatus | None = None,
        note: str | None = None,
        actor_id: str = "ceo_agent_v1",
    ) -> dict:
        self.company_os.agents.get(actor_id)
        goal = self.company_os.goals.get(goal_id)
        goal.current_value = current_value
        if status is not None:
            goal.status = status
        elif goal.progress_ratio() >= 1:
            goal.status = GoalStatus.COMPLETED
        goal.updated_at = utc_now()
        self.company_os.audit.append(
            AuditEvent(
                event_type="strategic_goal_progress_updated",
                actor_id=actor_id,
                action="update_strategic_goal_progress",
                task_id=None,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=goal.status.value,
                input_ref=note,
                output_ref=goal.goal_id,
            )
        )
        self.sync()
        return to_plain(goal)

    def link_task_to_goal(self, goal_id: str, task_id: str, actor_id: str = "ceo_agent_v1") -> dict:
        self.company_os.agents.get(actor_id)
        goal = self.company_os.goals.get(goal_id)
        self.tasks[task_id]
        if task_id not in goal.linked_task_ids:
            goal.linked_task_ids.append(task_id)
            goal.updated_at = utc_now()
        self._audit_goal_link(goal, actor_id, "link_task_to_goal", task_id)
        self.sync()
        return to_plain(goal)

    def link_review_to_goal(self, goal_id: str, review_id: str, actor_id: str = "ceo_agent_v1") -> dict:
        self.company_os.agents.get(actor_id)
        goal = self.company_os.goals.get(goal_id)
        self.company_os.reviews.get(review_id)
        if review_id not in goal.linked_review_ids:
            goal.linked_review_ids.append(review_id)
            goal.updated_at = utc_now()
        self._audit_goal_link(goal, actor_id, "link_review_to_goal", review_id)
        self.sync()
        return to_plain(goal)

    def link_improvement_to_goal(self, goal_id: str, proposal_id: str, actor_id: str = "ceo_agent_v1") -> dict:
        self.company_os.agents.get(actor_id)
        goal = self.company_os.goals.get(goal_id)
        self.improvement_proposals[proposal_id]
        if proposal_id not in goal.linked_improvement_ids:
            goal.linked_improvement_ids.append(proposal_id)
            goal.updated_at = utc_now()
        self._audit_goal_link(goal, actor_id, "link_improvement_to_goal", proposal_id)
        self.sync()
        return to_plain(goal)

    def list_tasks(self) -> list[dict]:
        return [to_plain(task) for task in self.tasks.values()]

    def get_task(self, task_id: str) -> dict:
        return to_plain(self.tasks[task_id])

    def run_task(self, task_id: str) -> dict:
        task = self.tasks[task_id]
        result = self.company_os.document_workflow.run(task)
        incident = None
        if result.blocked:
            incident = self._report_incident(
                title="Workflow task blocked",
                description=result.output or task.result or "Workflow ended in a blocked state.",
                source_type="task",
                source_id=task.task_id,
                risk_level=task.risk_level,
                task_id=task.task_id,
                actor_id="workflow_engine",
                recommendation="Review workflow trace, audit events, and approval/risk outputs before retrying.",
            )
        self.sync()
        return {
            "task": to_plain(result.task),
            "output": result.output,
            "approval_required": result.approval_required,
            "blocked": result.blocked,
            "incident": to_plain(incident) if incident else None,
        }

    def resume_task(self, task_id: str) -> dict:
        task = self.tasks[task_id]
        workflow_run = self.company_os.traces.latest_run_for_task(task_id)
        if workflow_run and workflow_run.workflow_id == "skill_missing_v1":
            result = self.company_os.skill_missing_workflow.resume_after_approval(task)
            self.sync()
            return {
                "task": to_plain(result.task),
                "output": result.output,
                "outcome": result.outcome,
                "replacement": result.replacement,
                "composition": result.composition,
                "temporary_skill": result.temporary_skill,
                "proposal": result.proposal,
                "approval_required": result.approval_required,
                "blocked": result.blocked,
                "incident": to_plain(result.incident) if result.incident else None,
            }
        if workflow_run and workflow_run.workflow_id == "approval_v1":
            result = self.company_os.approval_workflow.resume_after_decision(task)
            self.sync()
            return {
                "task": to_plain(result.task),
                "output": result.output,
                "outcome": result.outcome,
                "approval": result.approval,
                "risk": result.risk,
                "approval_required": result.approval_required,
                "blocked": result.blocked,
                "incident": result.incident,
            }
        if workflow_run and workflow_run.workflow_id == "github_project_analysis_v1":
            if not task.approval_id:
                raise ValueError("GitHub project analysis task has no approval")
            approval = to_plain(self.company_os.approvals.get(task.approval_id))
            result = self.company_os.github_project_analysis_workflow.resume_after_decision(task, approval)
            self.sync()
            return self._github_workflow_response(
                self.company_os.workflows.get("github_project_analysis_v1"),
                result,
            )
        if workflow_run and workflow_run.workflow_id == "tool_call_v1":
            if not task.approval_id:
                raise ValueError("Tool Call task has no approval")
            approval = to_plain(self.company_os.approvals.get(task.approval_id))
            candidates = [
                run
                for run in self.tool_runs.values()
                if run.task_id == task.task_id and run.approval_id == task.approval_id
            ]
            if not candidates:
                raise ValueError("Tool Call task has no waiting Tool Run")
            result = self.company_os.tool_call_workflow.resume_after_decision(
                task,
                approval,
                to_plain(candidates[-1]),
            )
            self.sync()
            return self._tool_workflow_response(
                self.company_os.workflows.get("tool_call_v1"),
                result,
            )
        result = self.company_os.document_workflow.resume_after_approval(task)
        incident = None
        if result.blocked:
            incident = self._report_incident(
                title="Workflow resume blocked",
                description=result.output or task.result or "Workflow resume ended in a blocked state.",
                source_type="task",
                source_id=task.task_id,
                risk_level=task.risk_level,
                task_id=task.task_id,
                actor_id="workflow_engine",
                recommendation="Review approval state, workflow trace, audit events, and budget policy before retrying.",
            )
        self.sync()
        return {
            "task": to_plain(result.task),
            "output": result.output,
            "approval_required": result.approval_required,
            "blocked": result.blocked,
            "incident": to_plain(incident) if incident else None,
        }

    def pause_task(self, task_id: str) -> dict:
        task = self.tasks[task_id]
        task.transition(TaskStatus.PAUSED)
        self.sync()
        return to_plain(task)

    def cancel_task(self, task_id: str) -> dict:
        task = self.tasks[task_id]
        task.transition(TaskStatus.CANCELLED)
        self.sync()
        return to_plain(task)

    def list_approvals(self) -> list[dict]:
        return [to_plain(approval) for approval in self.company_os.approvals.list()]

    def decide_approval(self, approval_id: str, status: ApprovalStatus, decided_by: str, note: str) -> dict:
        approval = self.company_os.approvals.decide(approval_id, status, decided_by, note)
        self.company_os.audit.append(
            AuditEvent(
                event_type="approval_decided",
                actor_id=decided_by,
                action=approval.request.action,
                task_id=approval.request.task_id,
                risk_level=approval.risk.level,
                approval_status=approval.status,
                result=approval.status.value,
                input_ref=note,
                output_ref=approval.approval_id,
            )
        )
        self.sync()
        return to_plain(approval)

    def request_action_approval(
        self,
        action: str,
        actor_id: str,
        permission_level: PermissionLevel,
        reason: str,
        task_id: str | None = None,
        target: str | None = None,
        possible_benefit: str = "Complete the requested action.",
        possible_loss: str = "Unsafe or unauthorized action.",
        reversible: bool = True,
        metadata: dict | None = None,
    ) -> dict:
        request = ActionRequest(
            action=action,
            actor_id=actor_id,
            task_id=task_id,
            permission_level=permission_level,
            reason=reason,
            target=target,
            reversible=reversible,
            metadata=metadata or {},
        )
        risk = self.company_os.risks.assess(request)
        permission_decision = None
        permission_reason = "actor is not a registered agent"
        agent = None
        try:
            agent = self.company_os.agents.get(actor_id)
        except KeyError:
            pass
        if agent is not None:
            permission = self.company_os.permissions.evaluate(agent, request)
            permission_decision = permission.decision
            permission_reason = permission.reason
        else:
            permission_decision = ActionDecision.REQUIRE_APPROVAL

        should_block = risk.blocked or permission_decision == ActionDecision.BLOCK
        should_approve = risk.requires_approval or permission_decision == ActionDecision.REQUIRE_APPROVAL
        approval = None
        approval_status = ApprovalStatus.NOT_REQUIRED
        result = "allowed"

        if should_block or should_approve:
            approval = self.company_os.approvals.request_approval(
                request=request,
                risk=risk,
                possible_benefit=possible_benefit,
                possible_loss=possible_loss if not should_block else f"{possible_loss} Permission: {permission_reason}",
            )
            if should_block and approval.status == ApprovalStatus.PENDING:
                approval.status = ApprovalStatus.BLOCKED
                approval.decided_at = utc_now()
                approval.decided_by = "permission_system"
                approval.decision_note = permission_reason
            approval_status = approval.status
            result = "blocked" if approval_status == ApprovalStatus.BLOCKED else "approval_required"

        incident = None
        if approval_status == ApprovalStatus.BLOCKED:
            incident = self._report_incident(
                title="Action request blocked",
                description=permission_reason,
                source_type="approval",
                source_id=approval.approval_id if approval else "none",
                risk_level=risk.level,
                task_id=task_id,
                actor_id=actor_id,
                recommendation="Review the requested action, actor permissions, and safety policy.",
            )

        self.company_os.audit.append(
            AuditEvent(
                event_type="action_requested",
                actor_id=actor_id,
                action=action,
                task_id=task_id,
                risk_level=risk.level,
                approval_status=approval_status,
                result=result,
                input_ref=reason,
                output_ref=approval.approval_id if approval else None,
            )
        )
        self.sync()
        return {
            "request": to_plain(request),
            "risk": to_plain(risk),
            "permission_decision": permission_decision.value if permission_decision else None,
            "permission_reason": permission_reason,
            "approval": to_plain(approval) if approval else None,
            "result": result,
            "incident": to_plain(incident) if incident else None,
        }

    def list_audit_logs(self) -> list[dict]:
        return [to_plain(event) for event in self.company_os.audit.list()]

    def list_structured_logs(
        self,
        category: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if limit <= 0:
            return []
        normalized_category = category.lower() if category else None
        normalized_level = level.lower() if level else None
        logs = build_structured_logs(
            audit_events=self.company_os.audit.list(),
            workflow_runs=self.company_os.traces.list_runs(),
            workflow_steps=self.company_os.traces.list_steps(),
            tool_runs=list(self.tool_runs.values()),
            model_usage=self.company_os.models.list_usage(),
            cost_logs=self.company_os.budget.list_cost_logs(),
            incidents=self.company_os.incidents.list(),
        )
        if normalized_category:
            logs = [log for log in logs if log["category"] == normalized_category]
        if normalized_level:
            logs = [log for log in logs if log["level"] == normalized_level]
        return logs[-min(limit, 500):]

    def list_memory(self) -> list[dict]:
        return [to_plain(record) for record in self.company_os.memory.list()]

    def write_memory(self, task_id: str, content: str, memory_type: str = "manual") -> dict:
        record = self.company_os.memory.write(MemoryRecord(task_id=task_id, content=content, memory_type=memory_type))
        self.sync()
        return to_plain(record)

    def list_knowledge(self) -> list[dict]:
        return [to_plain(doc) for doc in self.company_os.knowledge.list()]

    def list_evaluations(self) -> list[dict]:
        return [to_plain(record) for record in self.company_os.evaluations.list()]

    def write_knowledge(self, title: str, content: str, source_task_id: str | None = None) -> dict:
        doc = self.company_os.knowledge.write(KnowledgeDoc(title=title, content=content, source_task_id=source_task_id))
        self.sync()
        return to_plain(doc)

    def list_task_reviews(self, task_id: str | None = None, reviewer_agent: str | None = None) -> list[dict]:
        return [to_plain(review) for review in self.company_os.reviews.list(task_id, reviewer_agent)]

    def record_task_review(
        self,
        task_id: str,
        reviewer_agent: str,
        outcome: str,
        summary: str,
        what_went_well: str,
        what_went_wrong: str,
        lessons: list[str],
        follow_up_actions: list[str],
        quality_score: float,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> dict:
        task = self.tasks[task_id]
        self.company_os.agents.get(reviewer_agent)
        clean_outcome = outcome.strip() or "reviewed"
        clean_summary = summary.strip()
        clean_well = what_went_well.strip()
        clean_wrong = what_went_wrong.strip()
        clean_lessons = self._clean_text_list(lessons)
        clean_follow_ups = self._clean_text_list(follow_up_actions)
        if not clean_summary:
            raise ValueError("review summary is required")
        if quality_score < 0 or quality_score > 1:
            raise ValueError("quality_score must be between 0 and 1")

        review = self.company_os.reviews.record(
            TaskReview(
                task_id=task_id,
                reviewer_agent=reviewer_agent,
                outcome=clean_outcome,
                summary=clean_summary,
                what_went_well=clean_well,
                what_went_wrong=clean_wrong,
                lessons=clean_lessons,
                follow_up_actions=clean_follow_ups,
                quality_score=quality_score,
                risk_level=risk_level,
            )
        )
        memory = self.company_os.memory.write(
            MemoryRecord(
                task_id=task_id,
                memory_type="review",
                content=(
                    f"Review outcome: {clean_outcome}\n"
                    f"Summary: {clean_summary}\n"
                    f"Lessons: {', '.join(clean_lessons) if clean_lessons else 'none'}"
                ),
            )
        )
        knowledge = self.company_os.knowledge.write(
            KnowledgeDoc(
                title=f"Review lessons for {task.title}",
                source_task_id=task_id,
                content=(
                    f"Task: {task.title}\n"
                    f"Outcome: {clean_outcome}\n"
                    f"Quality score: {quality_score}\n"
                    f"What went well: {clean_well or 'n/a'}\n"
                    f"What went wrong: {clean_wrong or 'n/a'}\n"
                    f"Lessons: {', '.join(clean_lessons) if clean_lessons else 'none'}\n"
                    f"Follow-up actions: {', '.join(clean_follow_ups) if clean_follow_ups else 'none'}"
                ),
            )
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type="task_review_recorded",
                actor_id=reviewer_agent,
                action="record_task_review",
                task_id=task_id,
                risk_level=risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=clean_outcome,
                input_ref=task.status.value,
                output_ref=review.review_id,
            )
        )
        self.sync()
        return {
            "review": to_plain(review),
            "memory": to_plain(memory),
            "knowledge": to_plain(knowledge),
        }

    def list_risks(self) -> list[dict]:
        risky_events = [
            event
            for event in self.company_os.audit.list()
            if event.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.FORBIDDEN}
        ]
        return [to_plain(event) for event in risky_events]

    def missing_skill(
        self,
        capability: str,
        requested_by_agent: str,
        risk_level: RiskLevel,
        task_id: str | None = None,
    ) -> dict:
        proposal = self.company_os.gaps.missing_skill(capability, requested_by_agent, risk_level)
        approval = self.request_action_approval(
            action="create_skill",
            actor_id="ceo_agent_v1",
            permission_level=PermissionLevel.L2_INTERNAL_WRITE if risk_level == RiskLevel.LOW else PermissionLevel.L3_EXTERNAL_PREPARE,
            reason=f"Create Skill proposal: {proposal.name}",
            task_id=task_id,
            target=proposal.proposal_id,
            possible_benefit=f"Add missing capability: {capability}",
            possible_loss="A new Skill could expand system behavior beyond intended boundaries.",
        )
        proposal.approval_id = approval["approval"]["approval_id"] if approval["approval"] else None
        proposal.status = self._proposal_status_from_approval(approval["approval"])
        self.skill_proposals[proposal.proposal_id] = proposal
        self.sync()
        return to_plain(proposal)

    def missing_agent(
        self,
        role: str,
        department: str,
        repeated_reason: str,
        task_id: str | None = None,
    ) -> dict:
        proposal = self.company_os.gaps.missing_agent(role, department, repeated_reason)
        approval = self.request_action_approval(
            action="create_agent",
            actor_id="ceo_agent_v1",
            permission_level=PermissionLevel.L3_EXTERNAL_PREPARE,
            reason=f"Create Agent proposal: {proposal.name}",
            task_id=task_id,
            target=proposal.proposal_id,
            possible_benefit=f"Add a dedicated Agent for repeated need: {repeated_reason}",
            possible_loss="A new Agent could receive inappropriate permissions or responsibilities.",
        )
        proposal.approval_id = approval["approval"]["approval_id"] if approval["approval"] else None
        proposal.status = self._proposal_status_from_approval(approval["approval"])
        self.agent_proposals[proposal.proposal_id] = proposal
        self.sync()
        return to_plain(proposal)

    def propose_improvement_from_review(
        self,
        review_id: str,
        proposed_by_agent: str,
        target_type: str,
        title: str,
        description: str,
        rationale: str | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> dict:
        review = self.company_os.reviews.get(review_id)
        self.tasks[review.task_id]
        self.company_os.agents.get(proposed_by_agent)
        clean_target = target_type.strip().lower()
        clean_title = title.strip()
        clean_description = description.strip()
        if not clean_target:
            raise ValueError("improvement target_type is required")
        if not clean_title:
            raise ValueError("improvement title is required")
        if not clean_description:
            raise ValueError("improvement description is required")
        proposal = self.company_os.gaps.review_improvement(
            source_review_id=review.review_id,
            task_id=review.task_id,
            proposed_by_agent=proposed_by_agent,
            target_type=clean_target,
            title=clean_title,
            description=clean_description,
            rationale=rationale.strip() if rationale and rationale.strip() else review.summary,
            lessons=review.lessons,
            follow_up_actions=review.follow_up_actions,
            risk_level=risk_level,
        )
        approval = self.request_action_approval(
            action="register_improvement",
            actor_id=proposed_by_agent,
            permission_level=PermissionLevel.L2_INTERNAL_WRITE
            if risk_level == RiskLevel.LOW
            else PermissionLevel.L3_EXTERNAL_PREPARE,
            reason=f"Create improvement proposal: {proposal.title}",
            task_id=review.task_id,
            target=proposal.proposal_id,
            possible_benefit=f"Turn review lessons into a controlled improvement: {proposal.title}",
            possible_loss="A weak improvement could add process noise or expand behavior without enough evidence.",
        )
        proposal.approval_id = approval["approval"]["approval_id"] if approval["approval"] else None
        proposal.status = self._proposal_status_from_approval(approval["approval"])
        self.improvement_proposals[proposal.proposal_id] = proposal
        self.sync()
        return to_plain(proposal)

    def list_skill_proposals(self) -> list[dict]:
        self._refresh_proposal_statuses()
        return [to_plain(proposal) for proposal in self.skill_proposals.values()]

    def list_agent_proposals(self) -> list[dict]:
        self._refresh_proposal_statuses()
        return [to_plain(proposal) for proposal in self.agent_proposals.values()]

    def list_improvement_proposals(self) -> list[dict]:
        self._refresh_proposal_statuses()
        return [to_plain(proposal) for proposal in self.improvement_proposals.values()]

    def analyze_github_absorption(
        self,
        repo_url: str,
        requested_by_agent: str,
        readme: str,
        license_name: str = "unknown",
        maintenance_signal: str = "unknown",
        task_id: str | None = None,
        approval_id: str | None = None,
    ) -> dict:
        self.company_os.agents.get(requested_by_agent)
        clean_url = repo_url.strip()
        clean_readme = readme.strip()
        if not clean_url:
            raise ValueError("repo_url is required")
        if not clean_readme:
            raise ValueError("readme is required")
        proposal = self.company_os.gaps.github_absorption(
            repo_url=clean_url,
            requested_by_agent=requested_by_agent,
            readme=clean_readme,
            license_name=license_name,
            maintenance_signal=maintenance_signal,
        )
        if approval_id is not None:
            existing_approval = self.company_os.approvals.get(approval_id)
            if existing_approval.status != ApprovalStatus.APPROVED:
                raise ValueError("GitHub analysis approval is not approved")
            if existing_approval.request.task_id != task_id:
                raise ValueError("GitHub analysis approval does not match task")
            if existing_approval.request.metadata.get("workflow_id") != "github_project_analysis_v1":
                raise ValueError("approval is outside GitHub Project Analysis Workflow scope")
            approval_payload = to_plain(existing_approval)
        else:
            approval_result = self.request_action_approval(
                action="analyze_github_repository",
                actor_id=requested_by_agent,
                permission_level=PermissionLevel.L3_EXTERNAL_PREPARE,
                reason=f"Analyze GitHub repository for controlled absorption: {proposal.repo_url}",
                task_id=task_id,
                target=proposal.proposal_id,
                possible_benefit="Capture reusable open-source capability ideas as controlled internal knowledge.",
                possible_loss="Unsafe, incompatible, or prompt-injection content could be mistaken for executable system behavior.",
            )
            approval_payload = approval_result["approval"]
        proposal.approval_id = approval_payload["approval_id"] if approval_payload else None
        proposal.status = self._proposal_status_from_approval(approval_payload)
        self.github_absorptions[proposal.proposal_id] = proposal
        self.company_os.audit.append(
            AuditEvent(
                event_type="github_absorption_analyzed",
                actor_id=requested_by_agent,
                action="analyze_github_repository",
                task_id=task_id,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus(approval_payload["status"]) if approval_payload else ApprovalStatus.NOT_REQUIRED,
                result=proposal.status.value,
                input_ref=proposal.repo_url,
                output_ref=proposal.proposal_id,
            )
        )
        self.sync()
        return to_plain(proposal)

    def list_github_absorptions(self) -> list[dict]:
        self._refresh_proposal_statuses()
        return [to_plain(proposal) for proposal in self.github_absorptions.values()]

    def sandbox_github_absorption(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.github_absorptions[proposal_id]
        task_id = (
            self.company_os.approvals.get(proposal.approval_id).request.task_id
            if proposal.approval_id
            else None
        )
        known_agent_ids = {agent.agent_id for agent in self.company_os.agents.list()}
        proposal = self.company_os.sandbox.test_github_absorption(proposal, known_agent_ids)
        self.company_os.audit.append(
            AuditEvent(
                event_type="github_absorption_sandboxed",
                actor_id="sandbox_center",
                action="sandbox_github_absorption",
                task_id=task_id,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=proposal.sandbox_status.value,
                input_ref=proposal.proposal_id,
                output_ref=proposal.sandbox_notes,
            )
        )
        self.sync()
        return to_plain(proposal)

    def register_github_absorption(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.github_absorptions[proposal_id]
        self._ensure_proposal_approved(proposal.approval_id)
        self._ensure_proposal_sandbox_passed(proposal.sandbox_status)
        approval = self.company_os.approvals.get(proposal.approval_id)
        task_id = approval.request.task_id
        content = (
            f"Repository: {proposal.repo_url}\n"
            f"License: {proposal.license_name}\n"
            f"Maintenance: {proposal.maintenance_signal}\n"
            f"Risk level: {proposal.risk_level.value}\n"
            f"Summary: {proposal.summary}\n"
            f"Recommended capabilities: {', '.join(proposal.recommended_capabilities) or 'none'}\n"
            f"External content findings: {', '.join(proposal.external_content_findings) or 'none'}\n"
            f"Security findings: {', '.join(proposal.security_findings) or 'none'}\n\n"
            "Absorption result: registered as knowledge only. No unknown code, script, Tool, Skill, or Workflow was executed or enabled.\n\n"
            f"README excerpt:\n{proposal.readme_excerpt}"
        )
        knowledge = self.company_os.knowledge.write(
            KnowledgeDoc(
                title=f"GitHub absorption analysis: {proposal.repo_url}",
                content=content,
                source_task_id=task_id,
            )
        )
        proposal.status = ProposalStatus.REGISTERED
        proposal.registered_doc_id = knowledge.doc_id
        self.company_os.audit.append(
            AuditEvent(
                event_type="github_absorption_registered",
                actor_id="human_root",
                action="register_github_absorption",
                task_id=task_id,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.APPROVED,
                result=knowledge.doc_id,
                input_ref=proposal.proposal_id,
                output_ref=proposal.repo_url,
            )
        )
        self.sync()
        return {"proposal": to_plain(proposal), "knowledge": to_plain(knowledge)}

    def sandbox_skill_proposal(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.skill_proposals[proposal_id]
        known_agent_ids = {agent.agent_id for agent in self.company_os.agents.list()}
        proposal = self.company_os.sandbox.test_skill(proposal, known_agent_ids)
        self.company_os.audit.append(
            AuditEvent(
                event_type="skill_proposal_sandboxed",
                actor_id="sandbox_center",
                action="sandbox_skill_proposal",
                task_id=None,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=proposal.sandbox_status.value,
                input_ref=proposal.proposal_id,
                output_ref=proposal.sandbox_notes,
            )
        )
        self.sync()
        return to_plain(proposal)

    def sandbox_agent_proposal(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.agent_proposals[proposal_id]
        proposal = self.company_os.sandbox.test_agent(proposal)
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_proposal_sandboxed",
                actor_id="sandbox_center",
                action="sandbox_agent_proposal",
                task_id=None,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=proposal.sandbox_status.value,
                input_ref=proposal.proposal_id,
                output_ref=proposal.sandbox_notes,
            )
        )
        self.sync()
        return to_plain(proposal)

    def sandbox_improvement_proposal(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.improvement_proposals[proposal_id]
        proposal = self.company_os.sandbox.test_improvement(proposal)
        self.company_os.audit.append(
            AuditEvent(
                event_type="improvement_proposal_sandboxed",
                actor_id="sandbox_center",
                action="sandbox_improvement_proposal",
                task_id=proposal.task_id,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=proposal.sandbox_status.value,
                input_ref=proposal.proposal_id,
                output_ref=proposal.sandbox_notes,
            )
        )
        self.sync()
        return to_plain(proposal)

    def register_skill_proposal(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.skill_proposals[proposal_id]
        self._ensure_proposal_approved(proposal.approval_id)
        self._ensure_proposal_sandbox_passed(proposal.sandbox_status)
        skill_id = f"{self._slug(proposal.name)}_v1"
        if skill_id in {skill.skill_id for skill in self.company_os.skills.list()}:
            raise ValueError(f"skill already exists for proposal: {skill_id}")
        self._validate_skill_catalog_entry(skill_id, [proposal.requested_by_agent])
        skill = self.company_os.skills.register(
            Skill(
                skill_id=skill_id,
                name=proposal.name,
                type="generated",
                description=proposal.description,
                input_schema={"request": "string"},
                output_schema={"result": "string"},
                allowed_agents={proposal.requested_by_agent},
                risk_level=proposal.risk_level,
                requires_approval=proposal.requires_approval,
                enabled=True,
            )
        )
        self.company_os.agents.grant_skill(proposal.requested_by_agent, skill.skill_id)
        proposal.status = ProposalStatus.REGISTERED
        self.company_os.audit.append(
            AuditEvent(
                event_type="skill_registered_from_proposal",
                actor_id="human_root",
                action="register_skill",
                task_id=None,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.APPROVED,
                result=skill.skill_id,
                input_ref=proposal.proposal_id,
            )
        )
        self.sync()
        return {"proposal": to_plain(proposal), "skill": to_plain(skill)}

    def register_agent_proposal(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.agent_proposals[proposal_id]
        self._ensure_proposal_approved(proposal.approval_id)
        self._ensure_proposal_sandbox_passed(proposal.sandbox_status)
        agent_id = f"{self._slug(proposal.name)}_v1"
        if agent_id in {agent.agent_id for agent in self.company_os.agents.list()}:
            raise ValueError(f"agent already exists for proposal: {agent_id}")
        self._validate_agent_catalog_entry(
            agent_id,
            list(proposal.proposed_skills),
            [],
            "ceo_agent_v1",
        )
        common_forbidden = {
            "execute_payment",
            "execute_refund",
            "delete_audit_log",
            "modify_audit_log",
            "disable_risk_system",
            "modify_root_permissions",
        }
        agent = self.company_os.agents.register(
            Agent(
                agent_id=agent_id,
                name=proposal.name,
                department=proposal.department,
                role=proposal.role,
                permissions=proposal.proposed_permissions,
                forbidden=common_forbidden,
                allowed_skills=proposal.proposed_skills,
                allowed_tools=set(),
                reports_to="ceo_agent_v1",
                risk_level=proposal.risk_level,
                enabled=True,
            )
        )
        for skill_id in agent.allowed_skills:
            self.company_os.skills.allow_agent(skill_id, agent.agent_id)
        proposal.status = ProposalStatus.REGISTERED
        self.company_os.audit.append(
            AuditEvent(
                event_type="agent_registered_from_proposal",
                actor_id="human_root",
                action="register_agent",
                task_id=None,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.APPROVED,
                result=agent.agent_id,
                input_ref=proposal.proposal_id,
            )
        )
        self.sync()
        return {"proposal": to_plain(proposal), "agent": to_plain(agent)}

    def register_improvement_proposal(self, proposal_id: str) -> dict:
        self._refresh_proposal_statuses()
        proposal = self.improvement_proposals[proposal_id]
        self._ensure_proposal_approved(proposal.approval_id)
        self._ensure_proposal_sandbox_passed(proposal.sandbox_status)
        knowledge = self.company_os.knowledge.write(
            KnowledgeDoc(
                title=f"Registered improvement: {proposal.title}",
                source_task_id=proposal.task_id,
                content=(
                    f"Target type: {proposal.target_type}\n"
                    f"Source review: {proposal.source_review_id}\n"
                    f"Description: {proposal.description}\n"
                    f"Rationale: {proposal.rationale}\n"
                    f"Lessons: {', '.join(proposal.lessons) if proposal.lessons else 'none'}\n"
                    f"Follow-up actions: {', '.join(proposal.follow_up_actions) if proposal.follow_up_actions else 'none'}"
                ),
            )
        )
        proposal.status = ProposalStatus.REGISTERED
        self.company_os.audit.append(
            AuditEvent(
                event_type="improvement_registered_from_proposal",
                actor_id="human_root",
                action="register_improvement",
                task_id=proposal.task_id,
                risk_level=proposal.risk_level,
                approval_status=ApprovalStatus.APPROVED,
                result=knowledge.doc_id,
                input_ref=proposal.proposal_id,
                output_ref=knowledge.doc_id,
            )
        )
        self.sync()
        return {"proposal": to_plain(proposal), "knowledge": to_plain(knowledge)}

    def assess_action(
        self,
        action: str,
        actor_id: str,
        permission_level: PermissionLevel,
        reason: str,
        task_id: str | None = None,
    ) -> dict:
        request = ActionRequest(
            action=action,
            actor_id=actor_id,
            task_id=task_id,
            permission_level=permission_level,
            reason=reason,
        )
        risk = self.company_os.risks.assess(request)
        return to_plain(risk)

    def dashboard_summary(self) -> dict:
        tasks = list(self.tasks.values())
        approvals = self.company_os.approvals.list()
        audit_events = self.company_os.audit.list()
        memory_records = self.company_os.memory.list()
        knowledge_docs = self.company_os.knowledge.list()
        evaluations = self.company_os.evaluations.list()
        tools = self.company_os.tools.list()
        tool_runs = list(self.tool_runs.values())
        skill_runs = list(self.skill_runs.values())
        workflow_runs = self.company_os.traces.list_runs()
        workflow_steps = self.company_os.traces.list_steps()
        workflows = self.company_os.workflows.list()
        model_usage = self.company_os.models.list_usage()
        cost_logs = self.company_os.budget.list_cost_logs()
        incidents = self.company_os.incidents.list()
        backups = self.company_os.backups.list()
        agent_messages = self.company_os.communication.list_messages()
        agent_meetings = self.company_os.communication.list_meetings()
        task_handoffs = self.company_os.communication.list_handoffs()
        agent_broadcasts = self.company_os.communication.list_broadcasts()
        agent_conflicts = self.company_os.communication.list_conflicts()
        task_reviews = self.company_os.reviews.list()
        improvement_proposals = list(self.improvement_proposals.values())
        github_absorptions = list(self.github_absorptions.values())
        strategic_goals = self.company_os.goals.list()
        domain_events = self.company_os.events.list()
        scheduled_jobs = self.company_os.scheduler.list()
        scheduled_executions = self.company_os.scheduler.list_executions()
        budget = self.company_os.budget.summary()
        agents = self.company_os.agents.list()
        skills = self.company_os.skills.list()
        pending_approvals = [
            approval
            for approval in approvals
            if approval.status in {ApprovalStatus.PENDING, ApprovalStatus.NEED_MORE_INFO}
        ]
        failed_tasks = [
            task
            for task in tasks
                if task.status in {TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.ROLLBACK, TaskStatus.ESCALATED}
        ]
        risky_events = [
            event
            for event in audit_events
            if event.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.FORBIDDEN}
        ]
        recent_audit = audit_events[-10:]
        structured_logs = build_structured_logs(
            audit_events=audit_events,
            workflow_runs=workflow_runs,
            workflow_steps=workflow_steps,
            tool_runs=tool_runs,
            model_usage=model_usage,
            cost_logs=cost_logs,
            incidents=incidents,
        )
        task_status_counts = self._count_by_value(task.status.value for task in tasks)
        approval_status_counts = self._count_by_value(approval.status.value for approval in approvals)
        agent_status_counts = self._count_by_value("enabled" if agent.enabled else "disabled" for agent in agents)
        skill_status_counts = self._count_by_value("enabled" if skill.enabled else "disabled" for skill in skills)
        skill_risk_counts = self._count_by_value(skill.risk_level.value for skill in skills)
        recent_tasks = sorted(tasks, key=lambda task: task.task_id)[-10:]
        recent_approvals = sorted(approvals, key=lambda approval: approval.created_at)[-10:]
        integrity = self.system_integrity()
        return {
            "task_count": len(tasks),
            "pending_approval_count": len(pending_approvals),
            "recent_risk_count": len(risky_events),
            "recent_failure_count": len(failed_tasks),
            "agent_count": len(agents),
            "skill_count": len(skills),
            "skill_run_count": len(skill_runs),
            "workflow_count": 1,
            "workflow_run_count": len(workflow_runs),
            "workflow_step_count": len(workflow_steps),
            "registered_workflow_count": len(workflows),
            "model_usage_count": len(model_usage),
            "model_token_count": sum(record.total_tokens for record in model_usage),
            "model_estimated_cost": round(sum(record.estimated_cost for record in model_usage), 6),
            "cost_log_count": len(cost_logs),
            "incident_count": len(incidents),
            "open_incident_count": len([incident for incident in incidents if incident.status.value != "resolved"]),
            "backup_count": len(backups),
            "agent_message_count": len(agent_messages),
            "agent_meeting_count": len(agent_meetings),
            "task_handoff_count": len(task_handoffs),
            "agent_broadcast_count": len(agent_broadcasts),
            "agent_conflict_count": len(agent_conflicts),
            "open_agent_conflict_count": len([conflict for conflict in agent_conflicts if conflict.status == "open"]),
            "task_review_count": len(task_reviews),
            "average_review_score": self._average_review_score(task_reviews),
            "improvement_proposal_count": len(improvement_proposals),
            "github_absorption_count": len(github_absorptions),
            "strategic_goal_count": len(strategic_goals),
            "active_strategic_goal_count": len([goal for goal in strategic_goals if goal.status == GoalStatus.ACTIVE]),
            "average_goal_progress": self._average_goal_progress(strategic_goals),
            "domain_event_count": len(domain_events),
            "scheduled_job_count": len(scheduled_jobs),
            "active_scheduled_job_count": len(
                [job for job in scheduled_jobs if job.status == ScheduleStatus.ACTIVE]
            ),
            "scheduled_execution_count": len(scheduled_executions),
            "failed_scheduled_job_count": len(
                [job for job in scheduled_jobs if job.status == ScheduleStatus.FAILED]
            ),
            "budget_used_tokens": budget["used_tokens"],
            "budget_used_cost": budget["used_cost"],
            "budget_policy_name": budget["policy_name"],
            "budget_policy_enabled": budget["enabled"],
            "budget_max_total_tokens": budget["max_total_tokens"],
            "budget_max_estimated_cost": budget["max_estimated_cost"],
            "memory_count": len(memory_records),
            "knowledge_count": len(knowledge_docs),
            "audit_log_count": len(audit_events),
            "structured_log_count": len(structured_logs),
            "evaluation_count": len(evaluations),
            "average_evaluation_score": self._average_score(evaluations),
            "tool_count": len(tools),
            "tool_run_count": len(tool_runs),
            "system_health": "ok",
            "integrity_status": integrity["status"],
            "integrity_issue_count": integrity["issue_count"],
            "integrity_checks": integrity["checks"],
            "task_status_counts": task_status_counts,
            "approval_status_counts": approval_status_counts,
            "agent_status_counts": agent_status_counts,
            "skill_status_counts": skill_status_counts,
            "skill_risk_counts": skill_risk_counts,
            "skill_run_status_counts": self._count_by_value(run.status.value for run in skill_runs),
            "tool_status_counts": self._count_by_value("enabled" if tool.enabled else "disabled" for tool in tools),
            "tool_run_status_counts": self._count_by_value(run.status.value for run in tool_runs),
            "workflow_run_status_counts": self._count_by_value(run.status.value for run in workflow_runs),
            "model_usage_by_model": self._count_by_value(record.model_name for record in model_usage),
            "cost_log_result_counts": self._count_by_value(record.result for record in cost_logs),
            "incident_status_counts": self._count_by_value(incident.status.value for incident in incidents),
            "recent_tasks": [to_plain(task) for task in recent_tasks],
            "recent_approvals": [to_plain(approval) for approval in recent_approvals],
            "recent_risks": [to_plain(event) for event in risky_events[-10:]],
            "recent_logs": [to_plain(event) for event in recent_audit],
            "recent_structured_logs": structured_logs[-10:],
            "recent_evaluations": [to_plain(record) for record in evaluations[-10:]],
            "recent_skill_runs": [to_plain(run) for run in skill_runs[-10:]],
            "recent_tool_runs": [to_plain(run) for run in tool_runs[-10:]],
            "recent_workflow_runs": [to_plain(run) for run in workflow_runs[-10:]],
            "recent_workflow_steps": [to_plain(step) for step in workflow_steps[-10:]],
            "recent_model_usage": [to_plain(record) for record in model_usage[-10:]],
            "recent_cost_logs": [to_plain(record) for record in cost_logs[-10:]],
            "recent_incidents": [to_plain(incident) for incident in incidents[-10:]],
            "recent_backups": [to_plain(backup) for backup in backups[-10:]],
            "recent_agent_messages": [to_plain(message) for message in agent_messages[-10:]],
            "recent_agent_meetings": [to_plain(meeting) for meeting in agent_meetings[-10:]],
            "recent_task_handoffs": [to_plain(handoff) for handoff in task_handoffs[-10:]],
            "recent_agent_broadcasts": [to_plain(broadcast) for broadcast in agent_broadcasts[-10:]],
            "recent_agent_conflicts": [to_plain(conflict) for conflict in agent_conflicts[-10:]],
            "recent_task_reviews": [to_plain(review) for review in task_reviews[-10:]],
            "recent_improvement_proposals": [to_plain(proposal) for proposal in improvement_proposals[-10:]],
            "recent_github_absorptions": [to_plain(proposal) for proposal in github_absorptions[-10:]],
            "recent_strategic_goals": [to_plain(goal) for goal in strategic_goals[-10:]],
            "recent_domain_events": [to_plain(event) for event in domain_events[-10:]],
            "recent_scheduled_jobs": [to_plain(job) for job in scheduled_jobs[-10:]],
            "recent_scheduled_executions": [
                to_plain(execution) for execution in scheduled_executions[-10:]
            ],
        }

    def _report_incident(
        self,
        title: str,
        description: str,
        source_type: str,
        source_id: str,
        risk_level: RiskLevel,
        task_id: str | None = None,
        actor_id: str | None = None,
        recommendation: str = "Review the blocked action and decide whether policy, permissions, or task input should change.",
    ) -> Incident:
        return self.company_os.incidents.report(
            Incident(
                title=title,
                description=description,
                source_type=source_type,
                source_id=source_id,
                risk_level=risk_level,
                task_id=task_id,
                actor_id=actor_id,
                recommendation=recommendation,
            )
        )

    def _execute_tool_run(self, run: ToolRun, tool: Tool) -> None:
        try:
            adapter_result = execute_tool_adapter(
                tool.tool_id,
                run.input,
                ToolAdapterContext(company_os=self.company_os, tasks=self.tasks, tool_runs=self.tool_runs),
            )
        except ToolAdapterError as exc:
            run.status = ToolRunStatus.FAILED
            run.error = str(exc)
            run.completed_at = utc_now()
            return

        run.status = ToolRunStatus.COMPLETED
        if adapter_result is None:
            adapter_result = {"message": f"Simulated {tool.name} execution completed."}
        run.result = json.dumps(to_plain(adapter_result), sort_keys=True)
        run.completed_at = utc_now()

    def _execute_skill_run(self, run: SkillRun, skill: Skill) -> None:
        try:
            adapter_result = execute_skill_adapter(
                skill.skill_id,
                run.input,
                SkillRuntimeContext(company_os=self.company_os),
            )
        except (SkillRuntimeError, KeyError) as exc:
            run.status = SkillRunStatus.FAILED
            run.error = str(exc)
            run.completed_at = utc_now()
            return

        run.status = SkillRunStatus.COMPLETED
        run.result = json.dumps(to_plain(adapter_result), sort_keys=True)
        run.completed_at = utc_now()
        self.company_os.evaluations.write(
            EvaluationRecord(
                subject_type="skill",
                subject_id=skill.skill_id,
                task_id=run.task_id,
                score=1.0,
                metric="skill_run_completed",
                notes=f"Skill adapter completed run {run.run_id} with validated input.",
                risk_level=run.risk_level,
            )
        )

    def _bind_workflow_skill_runtime(self) -> None:
        self.company_os.document_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.task_planning_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.agent_collaboration_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.skill_missing_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.skill_missing_workflow.set_skill_requester(self.request_skill_run)
        self.company_os.skill_missing_workflow.set_skill_continuation(self._continue_workflow_skill)
        self.company_os.skill_missing_workflow.set_proposal_creator(self.missing_skill)
        self.company_os.agent_missing_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.agent_missing_workflow.set_proposal_creator(self.missing_agent)
        self.company_os.approval_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.approval_workflow.set_approval_requester(self.request_action_approval)
        self.company_os.github_project_analysis_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.github_project_analysis_workflow.set_approved_skill_executor(
            self._execute_approved_workflow_skill
        )
        self.company_os.github_project_analysis_workflow.set_approval_requester(self.request_action_approval)
        self.company_os.github_project_analysis_workflow.set_proposal_creator(self.analyze_github_absorption)
        self.company_os.github_project_analysis_workflow.set_sandbox_runner(self.sandbox_github_absorption)
        self.company_os.github_project_analysis_workflow.set_proposal_registrar(self.register_github_absorption)
        self.company_os.quality_check_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.retrospective_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.tool_call_workflow.set_skill_executor(self._execute_workflow_skill)
        self.company_os.tool_call_workflow.set_tool_requester(self.request_tool_run)
        self.company_os.tool_call_workflow.set_tool_completer(self.complete_tool_run)
        self.company_os.tool_call_workflow.set_tool_denier(self.deny_tool_run)
        self.company_os.tool_call_workflow.set_tool_getter(self._get_tool)

    def _execute_workflow_skill(
        self,
        skill_id: str,
        actor_id: str,
        input: dict,
        reason: str,
        task_id: str,
    ) -> dict:
        requested = self.request_skill_run(skill_id, actor_id, input, reason, task_id)
        run = requested["run"]
        if run["status"] != SkillRunStatus.COMPLETED.value:
            detail = run.get("error") or f"Skill run entered {run['status']}"
            raise PermissionError(f"{skill_id}: {detail}")
        return json.loads(run["result"])

    def _get_tool(self, tool_id: str) -> dict:
        return to_plain(self.company_os.tools.get(tool_id))

    def _execute_approved_workflow_skill(
        self,
        skill_id: str,
        actor_id: str,
        input: dict,
        reason: str,
        task_id: str,
        approval_id: str,
    ) -> dict:
        requested = self.request_skill_run(
            skill_id,
            actor_id,
            input,
            reason,
            task_id,
            authorization_approval_id=approval_id,
        )
        run = requested["run"]
        if run["status"] != SkillRunStatus.COMPLETED.value:
            detail = run.get("error") or f"Skill run entered {run['status']}"
            raise PermissionError(f"{skill_id}: {detail}")
        return json.loads(run["result"])

    def _continue_workflow_skill(self, task_id: str, skill_id: str) -> dict:
        candidates = [
            run
            for run in self.skill_runs.values()
            if run.task_id == task_id and run.skill_id == skill_id
        ]
        if not candidates:
            raise ValueError("workflow Skill Run not found")
        run = candidates[-1]
        if run.status == SkillRunStatus.WAITING_APPROVAL:
            return self.complete_skill_run(
                run.run_id,
                completed_by="human_root",
                note="Resume approved Skill Missing Workflow step.",
            )
        if run.status == SkillRunStatus.COMPLETED:
            approval = self.company_os.approvals.get(run.approval_id) if run.approval_id else None
            return {
                "skill": to_plain(self.company_os.skills.get(run.skill_id)),
                "run": to_plain(run),
                "approval": to_plain(approval) if approval else None,
            }
        raise ValueError(f"workflow Skill Run cannot continue from {run.status.value}")

    def _authorize_schedule_actor(self, actor_id: str) -> None:
        if actor_id == "human_root":
            return
        agent = self.company_os.agents.get(actor_id)
        request = ActionRequest(
            action="create_schedule",
            actor_id=actor_id,
            task_id=None,
            permission_level=PermissionLevel.L2_INTERNAL_WRITE,
            reason="Create an internal scheduled job.",
            target="scheduler",
        )
        permission = self.company_os.permissions.evaluate(agent, request)
        risk = self.company_os.risks.assess(request)
        if permission.decision != ActionDecision.ALLOW or risk.blocked or risk.requires_approval:
            raise ValueError(f"schedule creation is not allowed: {permission.reason}")

    def _authorize_schedule_control(self, job: ScheduledJob, actor_id: str) -> None:
        if actor_id != "human_root" and actor_id != job.created_by:
            raise ValueError("only human_root or the schedule creator can change this schedule")
        self._authorize_schedule_actor(actor_id)

    def _validate_schedule_payload(self, action: ScheduleAction, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("schedule payload must be an object")
        if action == ScheduleAction.CREATE_TASK:
            title = payload.get("title")
            description = payload.get("description")
            if not isinstance(title, str) or not title.strip():
                raise ValueError("create_task schedule requires a title")
            if not isinstance(description, str) or not description.strip():
                raise ValueError("create_task schedule requires a description")
            return {"title": title.strip(), "description": description.strip()}
        if action == ScheduleAction.RUN_TASK:
            task_id = payload.get("task_id")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("run_task schedule requires a task_id")
            self.tasks[task_id]
            return {"task_id": task_id}
        raise ValueError("unsupported schedule action")

    def _aware_utc(self, value: datetime, field_name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must include a timezone")
        return value.astimezone(timezone.utc)

    def _publish_domain_event(
        self,
        event_type: str,
        source_type: str,
        source_id: str,
        actor_id: str,
        payload: dict,
        task_id: str | None = None,
    ) -> DomainEvent:
        return self.company_os.events.publish(
            DomainEvent(
                event_type=event_type,
                source_type=source_type,
                source_id=source_id,
                actor_id=actor_id,
                payload=payload,
                task_id=task_id,
            )
        )

    def _record_schedule_state_change(
        self,
        job: ScheduledJob,
        actor_id: str,
        transition: str,
    ) -> None:
        self._publish_domain_event(
            event_type=f"schedule.{transition}",
            source_type="schedule",
            source_id=job.schedule_id,
            actor_id=actor_id,
            payload={"status": job.status.value},
            task_id=job.payload.get("task_id"),
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type=f"scheduled_job_{transition}",
                actor_id=actor_id,
                action=f"{transition}_schedule",
                task_id=job.payload.get("task_id"),
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=job.status.value,
                input_ref=None,
                output_ref=job.schedule_id,
            )
        )
        self.sync()

    def _execute_scheduled_job(
        self,
        job: ScheduledJob,
        actor_id: str,
        now: datetime,
        execution_token: str | None = None,
    ) -> ScheduledExecution:
        output_ref = None
        error = None
        status = ScheduleExecutionStatus.COMPLETED
        try:
            if job.action == ScheduleAction.CREATE_TASK:
                deterministic_task_id = None
                if execution_token is not None:
                    digest = hashlib.sha256(execution_token.encode("utf-8")).hexdigest()[:20]
                    deterministic_task_id = f"task_schedule_{digest}"
                task = self.create_task(
                    job.payload["title"],
                    job.payload["description"],
                    user_id=job.created_by,
                    task_id=deterministic_task_id,
                )
                output_ref = task["task_id"]
            elif job.action == ScheduleAction.RUN_TASK:
                output_ref = job.payload["task_id"]
                if execution_token is None or self.tasks[output_ref].status != TaskStatus.COMPLETED:
                    result = self.run_task(output_ref)
                    if result["blocked"]:
                        raise ValueError(result["output"] or "scheduled task execution was blocked")
            else:
                raise ValueError("unsupported schedule action")
        except Exception as exc:
            status = ScheduleExecutionStatus.FAILED
            error = str(exc)

        job.run_count += 1
        job.last_run_at = now
        job.last_error = error
        if status == ScheduleExecutionStatus.FAILED:
            job.failure_count += 1

        reached_limit = job.max_runs is not None and job.run_count >= job.max_runs
        if job.interval_seconds is not None and not reached_limit:
            job.next_run_at = now + timedelta(seconds=job.interval_seconds)
            job.status = ScheduleStatus.ACTIVE
        elif status == ScheduleExecutionStatus.COMPLETED:
            job.status = ScheduleStatus.COMPLETED
        else:
            job.status = ScheduleStatus.FAILED
        job.updated_at = now

        execution = self.company_os.scheduler.record_execution(
            ScheduledExecution(
                schedule_id=job.schedule_id,
                action=job.action,
                status=status,
                actor_id=actor_id,
                output_ref=output_ref,
                error=error,
                started_at=now,
                completed_at=now,
            )
        )
        self._publish_domain_event(
            event_type=f"schedule.execution.{status.value}",
            source_type="schedule",
            source_id=job.schedule_id,
            actor_id=actor_id,
            payload={
                "execution_id": execution.execution_id,
                "action": job.action.value,
                "output_ref": output_ref,
                "error": error,
            },
            task_id=job.payload.get("task_id") or output_ref,
        )
        self.company_os.audit.append(
            AuditEvent(
                event_type=f"scheduled_job_{status.value}",
                actor_id=actor_id,
                action=job.action.value,
                task_id=job.payload.get("task_id") or output_ref,
                risk_level=RiskLevel.LOW if error is None else RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=status.value,
                input_ref=job.schedule_id,
                output_ref=output_ref,
                error=error,
            )
        )
        if error is not None:
            self._report_incident(
                title="Scheduled job failed",
                description=f"Schedule {job.schedule_id} failed: {error}",
                source_type="schedule",
                source_id=job.schedule_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=job.payload.get("task_id"),
                actor_id=actor_id,
                recommendation="Inspect the schedule payload, target task state, and audit trail before retrying.",
            )
        return execution

    def _state_snapshot(self) -> dict:
        return {
            "tasks": to_plain(list(self.tasks.values())),
            "approvals": to_plain(self.company_os.approvals.list()),
            "audit_logs": to_plain(self.company_os.audit.list()),
            "memory": to_plain(self.company_os.memory.list()),
            "knowledge": to_plain(self.company_os.knowledge.list()),
            "evaluations": to_plain(self.company_os.evaluations.list()),
            "agents": to_plain(self.company_os.agents.list()),
            "skills": to_plain(self.company_os.skills.list()),
            "strategic_goals": to_plain(self.company_os.goals.list()),
            "tools": to_plain(self.company_os.tools.list()),
            "tool_runs": to_plain(list(self.tool_runs.values())),
            "skill_runs": to_plain(list(self.skill_runs.values())),
            "workflow_runs": to_plain(self.company_os.traces.list_runs()),
            "workflow_steps": to_plain(self.company_os.traces.list_steps()),
            "model_usage": to_plain(self.company_os.models.list_usage()),
            "cost_logs": to_plain(self.company_os.budget.list_cost_logs()),
            "budget_policy": to_plain(self.company_os.budget.policy),
            "incidents": to_plain(self.company_os.incidents.list()),
            "skill_proposals": to_plain(list(self.skill_proposals.values())),
            "agent_proposals": to_plain(list(self.agent_proposals.values())),
            "improvement_proposals": to_plain(list(self.improvement_proposals.values())),
            "github_absorptions": to_plain(list(self.github_absorptions.values())),
            "agent_messages": to_plain(self.company_os.communication.list_messages()),
            "agent_meetings": to_plain(self.company_os.communication.list_meetings()),
            "task_handoffs": to_plain(self.company_os.communication.list_handoffs()),
            "agent_broadcasts": to_plain(self.company_os.communication.list_broadcasts()),
            "agent_conflicts": to_plain(self.company_os.communication.list_conflicts()),
            "task_reviews": to_plain(self.company_os.reviews.list()),
            "scheduled_jobs": to_plain(self.company_os.scheduler.list()),
        }

    def _backup_checksum(self, snapshot: dict) -> str:
        canonical = json.dumps(to_plain(snapshot), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _backup_integrity_result(self, backup: BackupRecord) -> dict:
        actual_checksum = self._backup_checksum(backup.snapshot)
        expected_checksum = backup.backup_checksum
        if expected_checksum is None:
            status = "missing_checksum"
        elif expected_checksum == actual_checksum:
            status = "verified"
        else:
            status = "checksum_mismatch"
        return {
            "backup_id": backup.backup_id,
            "status": status,
            "verified": status == "verified",
            "expected_checksum": expected_checksum,
            "actual_checksum": actual_checksum,
        }

    def _persistence_integrity_check(self) -> dict:
        if self.persistence is None:
            return {
                "name": "persistence_backend",
                "status": "warning",
                "message": "Running with in-memory state; data will not survive process restart.",
            }
        return {
            "name": "persistence_backend",
            "status": "ok",
            "message": f"{self.persistence.backend_name} persistence is configured.",
        }

    def _schema_integrity_check(self) -> dict:
        if self.persistence is None:
            return {
                "name": "schema_version",
                "status": "skipped",
                "message": "Schema version check is skipped for in-memory state.",
            }
        version = self.persistence.schema_version()
        expected = self.persistence.expected_schema_version
        backend = self.persistence.backend_name
        return {
            "name": "schema_version",
            "status": "ok" if version == expected else "critical",
            "message": f"{backend} schema version is {version}; expected {expected}.",
        }

    def _audit_storage_integrity_check(self) -> dict:
        if self.persistence is None:
            return {
                "name": "audit_append_only_storage",
                "status": "skipped",
                "message": "Database audit append-only trigger check is skipped for in-memory state.",
            }
        enabled = self.persistence.audit_append_only_guards_enabled()
        backend = self.persistence.backend_name
        return {
            "name": "audit_append_only_storage",
            "status": "ok" if enabled else "critical",
            "message": (
                f"{backend} audit append-only triggers are installed."
                if enabled
                else f"{backend} audit append-only triggers are missing."
            ),
        }

    def _backup_integrity_check(self) -> dict:
        backups = self.company_os.backups.list()
        if not backups:
            return {
                "name": "backup_integrity",
                "status": "warning",
                "message": "No backups exist yet.",
            }
        results = [self._backup_integrity_result(backup) for backup in backups]
        broken = [result for result in results if not result["verified"]]
        return {
            "name": "backup_integrity",
            "status": "ok" if not broken else "critical",
            "message": f"{len(results) - len(broken)} of {len(results)} backups passed checksum verification.",
            "details": results[-5:],
        }

    def _incident_integrity_check(self) -> dict:
        open_incidents = [incident for incident in self.company_os.incidents.list() if incident.status.value != "resolved"]
        return {
            "name": "open_incidents",
            "status": "ok" if not open_incidents else "warning",
            "message": f"{len(open_incidents)} open incidents require follow-up.",
        }

    def _approval_integrity_check(self) -> dict:
        pending = [
            approval
            for approval in self.company_os.approvals.list()
            if approval.status in {ApprovalStatus.PENDING, ApprovalStatus.NEED_MORE_INFO}
        ]
        return {
            "name": "pending_approvals",
            "status": "ok" if not pending else "warning",
            "message": f"{len(pending)} approvals are pending or need more information.",
        }

    def _budget_integrity_check(self) -> dict:
        budget = self.company_os.budget.summary()
        if not budget["enabled"]:
            status = "warning"
            message = "Budget policy is disabled."
        elif budget["used_tokens"] > budget["max_total_tokens"] or budget["used_cost"] > budget["max_estimated_cost"]:
            status = "critical"
            message = "Budget usage exceeds configured policy."
        else:
            status = "ok"
            message = "Budget policy is enabled and current usage is within limits."
        return {
            "name": "budget_policy",
            "status": status,
            "message": message,
        }

    def _scheduler_integrity_check(self) -> dict:
        jobs = self.company_os.scheduler.list()
        failed = [job for job in jobs if job.status == ScheduleStatus.FAILED]
        overdue = [
            job
            for job in jobs
            if job.status == ScheduleStatus.ACTIVE and job.next_run_at < utc_now()
        ]
        if failed:
            status = "critical"
        elif overdue:
            status = "warning"
        else:
            status = "ok"
        return {
            "name": "scheduler",
            "status": status,
            "message": f"{len(failed)} failed and {len(overdue)} overdue scheduled jobs.",
        }

    def _validate_agent_catalog_entry(
        self,
        agent_id: str,
        allowed_skills: list[str],
        allowed_tools: list[str],
        reports_to: str,
    ) -> None:
        if not agent_id.strip():
            raise ValueError("agent_id is required")
        known_skills = {skill.skill_id for skill in self.company_os.skills.list()}
        known_tools = {tool.tool_id for tool in self.company_os.tools.list()}
        known_agents = {agent.agent_id for agent in self.company_os.agents.list()}
        unknown_skills = set(allowed_skills) - known_skills
        unknown_tools = set(allowed_tools) - known_tools
        if unknown_skills:
            raise ValueError(f"agent references unknown skills: {sorted(unknown_skills)}")
        if unknown_tools:
            raise ValueError(f"agent references unknown tools: {sorted(unknown_tools)}")
        if reports_to != "human_root" and reports_to not in known_agents:
            raise ValueError(f"agent reports to unknown agent: {reports_to}")

    def _validate_skill_catalog_entry(self, skill_id: str, allowed_agents: list[str]) -> None:
        if not skill_id.strip():
            raise ValueError("skill_id is required")
        known_agents = {agent.agent_id for agent in self.company_os.agents.list()}
        unknown_agents = set(allowed_agents) - known_agents
        if unknown_agents:
            raise ValueError(f"skill references unknown agents: {sorted(unknown_agents)}")

    def _count_by_value(self, values) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            counts[str(value)] = counts.get(str(value), 0) + 1
        return counts

    def _average_score(self, evaluations) -> float | None:
        records = list(evaluations)
        if not records:
            return None
        return round(sum(record.score for record in records) / len(records), 4)

    def _average_review_score(self, reviews) -> float | None:
        records = list(reviews)
        if not records:
            return None
        return round(sum(record.quality_score for record in records) / len(records), 4)

    def _average_goal_progress(self, goals) -> float | None:
        records = list(goals)
        if not records:
            return None
        return round(sum(goal.progress_ratio() for goal in records) / len(records), 4)

    def _audit_goal_link(self, goal: StrategicGoal, actor_id: str, action: str, linked_id: str) -> None:
        self.company_os.audit.append(
            AuditEvent(
                event_type="strategic_goal_linked",
                actor_id=actor_id,
                action=action,
                task_id=None,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=goal.goal_id,
                input_ref=linked_id,
                output_ref=goal.goal_id,
            )
        )

    def _clean_text_list(self, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def _proposal_status_from_approval(self, approval: dict | None) -> ProposalStatus:
        if approval is None:
            return ProposalStatus.PROPOSED
        status = approval["status"]
        if status == ApprovalStatus.BLOCKED.value:
            return ProposalStatus.BLOCKED
        if status == ApprovalStatus.APPROVED.value:
            return ProposalStatus.APPROVED
        if status == ApprovalStatus.REJECTED.value:
            return ProposalStatus.REJECTED
        return ProposalStatus.PENDING_APPROVAL

    def _refresh_proposal_statuses(self) -> None:
        changed = False
        proposals = (
            list(self.skill_proposals.values())
            + list(self.agent_proposals.values())
            + list(self.improvement_proposals.values())
            + list(self.github_absorptions.values())
        )
        for proposal in proposals:
            if proposal.status == ProposalStatus.REGISTERED or not proposal.approval_id:
                continue
            approval = self.company_os.approvals.get(proposal.approval_id)
            next_status = self._proposal_status_from_approval(to_plain(approval))
            if proposal.status != next_status:
                proposal.status = next_status
                changed = True
        if changed:
            self.sync()

    def _ensure_proposal_approved(self, approval_id: str | None) -> None:
        if not approval_id:
            raise ValueError("proposal has no approval")
        approval = self.company_os.approvals.get(approval_id)
        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("proposal approval is not approved")

    def _ensure_proposal_sandbox_passed(self, sandbox_status: SandboxStatus) -> None:
        if sandbox_status != SandboxStatus.PASSED:
            raise ValueError("proposal sandbox has not passed")

    def _slug(self, value: str) -> str:
        chars = [char.lower() if char.isalnum() else "_" for char in value]
        slug = "_".join(part for part in "".join(chars).split("_") if part)
        return slug or "generated"
