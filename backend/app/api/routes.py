from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.auth.service import AuthError
from app.api.schemas import (
    AgentBroadcastCreateRequest,
    AgentConflictCreateRequest,
    AgentConflictResolveRequest,
    AgentCreateRequest,
    AgentMeetingCreateRequest,
    AgentMessageCreateRequest,
    ApprovalDecisionRequest,
    ApprovalRequestCreate,
    BackupCreateRequest,
    BackupRestoreExecuteRequest,
    BackupRestoreRequest,
    BackupVerifyRequest,
    BudgetPolicyUpdateRequest,
    GitHubAbsorptionAnalyzeRequest,
    ImprovementProposalCreateRequest,
    IncidentUpdateRequest,
    KnowledgeWriteRequest,
    KnowledgeSearchRequest,
    KnowledgeReindexRequest,
    LoginRequest,
    MemoryWriteRequest,
    ModelGenerateRequest,
    MissingAgentRequest,
    MissingSkillRequest,
    RegisterRequest,
    RiskAssessRequest,
    ScheduleActorRequest,
    ScheduleCreateRequest,
    SchedulerTickRequest,
    SkillSearchRequest,
    SkillCreateRequest,
    SkillRunCompleteRequest,
    SkillRunRequest,
    StrategicGoalCreateRequest,
    StrategicGoalLinkRequest,
    StrategicGoalProgressRequest,
    TaskCreateRequest,
    TaskHandoffRequest,
    TaskReviewCreateRequest,
    ToolCreateRequest,
    ToolRunCompleteRequest,
    ToolRunRequest,
    WorkflowRunRequest,
)
from app.core.enums import ApprovalStatus
from app.models.providers import ModelProviderError
from app.scheduler.redis_queue import scheduler_queue_health
from app.services.company import CompanyApplicationService


def build_router(service: CompanyApplicationService) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return service.health()

    @router.get("/database/schema")
    def database_schema() -> dict:
        return service.database_schema()

    @router.get("/system/integrity")
    def system_integrity() -> dict:
        return service.system_integrity()

    @router.get("/events")
    def list_domain_events(
        event_type: str | None = None,
        source_type: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        try:
            return service.list_domain_events(event_type, source_type, task_id, limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/schedules")
    def list_scheduled_jobs(status: str | None = None, action: str | None = None) -> list[dict]:
        return service.list_scheduled_jobs(status, action)

    @router.post("/schedules")
    def create_scheduled_job(payload: ScheduleCreateRequest) -> dict:
        try:
            return service.create_scheduled_job(
                payload.name,
                payload.action,
                payload.payload,
                payload.created_by,
                payload.next_run_at,
                payload.interval_seconds,
                payload.max_runs,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="schedule actor or target task not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/schedules/{schedule_id}/pause")
    def pause_scheduled_job(schedule_id: str, payload: ScheduleActorRequest) -> dict:
        try:
            return service.pause_scheduled_job(schedule_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="schedule not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/schedules/{schedule_id}/resume")
    def resume_scheduled_job(schedule_id: str, payload: ScheduleActorRequest) -> dict:
        try:
            return service.resume_scheduled_job(schedule_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="schedule not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/schedules/{schedule_id}/cancel")
    def cancel_scheduled_job(schedule_id: str, payload: ScheduleActorRequest) -> dict:
        try:
            return service.cancel_scheduled_job(schedule_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="schedule not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/scheduler/executions")
    def list_scheduled_executions(schedule_id: str | None = None) -> list[dict]:
        return service.list_scheduled_executions(schedule_id)

    @router.get("/scheduler/queue-health")
    def scheduler_queue_health_status() -> dict:
        return scheduler_queue_health()

    @router.post("/scheduler/tick")
    def tick_scheduler(payload: SchedulerTickRequest) -> dict:
        try:
            return service.tick_scheduler(payload.actor_id, payload.now, payload.limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/auth/register")
    def register(payload: RegisterRequest) -> dict:
        try:
            return service.register_user(payload.email, payload.password)
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/auth/login")
    def login(payload: LoginRequest) -> dict:
        try:
            return service.login_user(payload.email, payload.password)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @router.post("/auth/logout")
    def logout(authorization: str | None = Header(default=None)) -> dict:
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:]
        return service.logout_user(token)

    @router.get("/agents")
    def list_agents() -> list[dict]:
        return service.list_agents()

    @router.post("/agents")
    def register_agent(payload: AgentCreateRequest) -> dict:
        try:
            return service.register_agent(
                payload.agent_id,
                payload.name,
                payload.department,
                payload.role,
                payload.permissions,
                payload.forbidden,
                payload.allowed_skills,
                payload.allowed_tools,
                payload.reports_to,
                payload.risk_level,
                payload.version,
                payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/agents/missing")
    def missing_agent(payload: MissingAgentRequest) -> dict:
        return service.missing_agent(payload.role, payload.department, payload.repeated_reason)

    @router.get("/agents/proposals")
    def list_agent_proposals() -> list[dict]:
        return service.list_agent_proposals()

    @router.post("/agents/proposals/{proposal_id}/sandbox")
    def sandbox_agent_proposal(proposal_id: str) -> dict:
        try:
            return service.sandbox_agent_proposal(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent proposal not found") from exc

    @router.post("/agents/proposals/{proposal_id}/register")
    def register_agent_proposal(proposal_id: str) -> dict:
        try:
            return service.register_agent_proposal(proposal_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/agents/factory/create")
    def create_agent_proposal(payload: MissingAgentRequest) -> dict:
        return service.missing_agent(payload.role, payload.department, payload.repeated_reason)

    @router.get("/agents/{agent_id}")
    def get_agent(agent_id: str) -> dict:
        try:
            return service.get_agent(agent_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc

    @router.get("/skills")
    def list_skills() -> list[dict]:
        return service.list_skills()

    @router.post("/skills")
    def register_skill(payload: SkillCreateRequest) -> dict:
        try:
            return service.register_skill(
                payload.skill_id,
                payload.name,
                payload.type,
                payload.description,
                payload.input_schema,
                payload.output_schema,
                payload.allowed_agents,
                payload.risk_level,
                payload.requires_approval,
                payload.version,
                payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/skills/search")
    def search_skills(payload: SkillSearchRequest) -> list[dict]:
        return service.search_skills(payload.query)

    @router.post("/skills/missing")
    def missing_skill(payload: MissingSkillRequest) -> dict:
        return service.missing_skill(payload.capability, payload.requested_by_agent, payload.risk_level)

    @router.get("/skills/proposals")
    def list_skill_proposals() -> list[dict]:
        return service.list_skill_proposals()

    @router.post("/skills/proposals/{proposal_id}/sandbox")
    def sandbox_skill_proposal(proposal_id: str) -> dict:
        try:
            return service.sandbox_skill_proposal(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="skill proposal not found") from exc

    @router.post("/skills/proposals/{proposal_id}/register")
    def register_skill_proposal(proposal_id: str) -> dict:
        try:
            return service.register_skill_proposal(proposal_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/skills/factory/create")
    def create_skill_proposal(payload: MissingSkillRequest) -> dict:
        return service.missing_skill(payload.capability, payload.requested_by_agent, payload.risk_level)

    @router.get("/skills/runs")
    def list_skill_runs() -> list[dict]:
        return service.list_skill_runs()

    @router.post("/skills/runs/request")
    def request_skill_run(payload: SkillRunRequest) -> dict:
        try:
            return service.request_skill_run(
                payload.skill_id,
                payload.actor_id,
                payload.input,
                payload.reason,
                payload.task_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="skill or agent not found") from exc

    @router.post("/skills/runs/{run_id}/complete")
    def complete_skill_run(run_id: str, payload: SkillRunCompleteRequest) -> dict:
        try:
            return service.complete_skill_run(run_id, payload.completed_by, payload.note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="skill run, skill, agent, or approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/tools")
    def list_tools() -> list[dict]:
        return service.list_tools()

    @router.post("/tools")
    def register_tool(payload: ToolCreateRequest) -> dict:
        try:
            return service.register_tool(
                payload.tool_id,
                payload.name,
                payload.type,
                payload.description,
                payload.action,
                payload.permission_level,
                payload.risk_level,
                payload.requires_approval,
                payload.input_schema,
                payload.output_schema,
                payload.version,
                payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/tools/runs")
    def list_tool_runs() -> list[dict]:
        return service.list_tool_runs()

    @router.post("/tools/runs/request")
    def request_tool_run(payload: ToolRunRequest) -> dict:
        try:
            return service.request_tool_run(
                payload.tool_id,
                payload.actor_id,
                payload.input,
                payload.reason,
                payload.task_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="tool or agent not found") from exc

    @router.post("/tools/runs/{run_id}/complete")
    def complete_tool_run(run_id: str, payload: ToolRunCompleteRequest) -> dict:
        try:
            return service.complete_tool_run(run_id, payload.completed_by, payload.note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="tool run, tool, agent, or approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/workflows")
    def list_workflows() -> list[dict]:
        return service.list_workflows()

    @router.get("/workflows/{workflow_id}")
    def get_workflow(workflow_id: str) -> dict:
        try:
            return service.get_workflow(workflow_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc

    @router.get("/workflow-runs")
    def list_workflow_runs() -> list[dict]:
        return service.list_workflow_runs()

    @router.get("/workflow-runs/{run_id}/steps")
    def list_workflow_steps(run_id: str) -> list[dict]:
        return service.list_workflow_steps(run_id)

    @router.get("/model-usage")
    def list_model_usage() -> list[dict]:
        return service.list_model_usage()

    @router.get("/cost-logs")
    def list_cost_logs() -> list[dict]:
        return service.list_cost_logs()

    @router.get("/budget/summary")
    def budget_summary() -> dict:
        return service.budget_summary()

    @router.post("/budget/policy")
    def update_budget_policy(payload: BudgetPolicyUpdateRequest) -> dict:
        try:
            return service.update_budget_policy(
                actor_id=payload.actor_id,
                name=payload.name,
                max_tokens_per_call=payload.max_tokens_per_call,
                max_total_tokens=payload.max_total_tokens,
                max_estimated_cost=payload.max_estimated_cost,
                cost_per_token=payload.cost_per_token,
                currency=payload.currency,
                enabled=payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/incidents")
    def list_incidents() -> list[dict]:
        return service.list_incidents()

    @router.get("/backups")
    def list_backups() -> list[dict]:
        return service.list_backups()

    @router.post("/backups")
    def create_backup(payload: BackupCreateRequest) -> dict:
        try:
            return service.create_backup(payload.actor_id, payload.reason)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/backups/{backup_id}/verify")
    def verify_backup(backup_id: str, payload: BackupVerifyRequest) -> dict:
        try:
            return service.verify_backup(backup_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="backup not found") from exc

    @router.post("/backups/{backup_id}/restore-request")
    def request_backup_restore(backup_id: str, payload: BackupRestoreRequest) -> dict:
        try:
            return service.request_backup_restore(backup_id, payload.actor_id, payload.reason)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="backup not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/backups/{backup_id}/restore")
    def execute_backup_restore(backup_id: str, payload: BackupRestoreExecuteRequest) -> dict:
        try:
            return service.execute_backup_restore(
                backup_id,
                payload.approval_id,
                payload.actor_id,
                payload.reason,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="backup or approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/agent-messages")
    def list_agent_messages(agent_id: str | None = None, task_id: str | None = None) -> list[dict]:
        return service.list_agent_messages(agent_id, task_id)

    @router.post("/agent-messages")
    def send_agent_message(payload: AgentMessageCreateRequest) -> dict:
        try:
            return service.send_agent_message(
                from_agent=payload.from_agent,
                to_agent=payload.to_agent,
                message_type=payload.message_type,
                content=payload.content,
                priority=payload.priority,
                requires_response=payload.requires_response,
                task_id=payload.task_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/agent-meetings")
    def list_agent_meetings(task_id: str | None = None) -> list[dict]:
        return service.list_agent_meetings(task_id)

    @router.post("/agent-meetings")
    def record_agent_meeting(payload: AgentMeetingCreateRequest) -> dict:
        try:
            return service.record_agent_meeting(
                title=payload.title,
                organizer_agent=payload.organizer_agent,
                participant_agents=payload.participant_agents,
                agenda=payload.agenda,
                meeting_type=payload.meeting_type,
                task_id=payload.task_id,
                minutes=payload.minutes,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/task-handoffs")
    def list_task_handoffs(task_id: str | None = None, agent_id: str | None = None) -> list[dict]:
        return service.list_task_handoffs(task_id, agent_id)

    @router.get("/agent-broadcasts")
    def list_agent_broadcasts(
        task_id: str | None = None,
        agent_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict]:
        return service.list_agent_broadcasts(task_id, agent_id, event_type)

    @router.post("/agent-broadcasts")
    def broadcast_agent_event(payload: AgentBroadcastCreateRequest) -> dict:
        try:
            return service.broadcast_agent_event(
                from_agent=payload.from_agent,
                audience_agents=payload.audience_agents,
                event_type=payload.event_type,
                title=payload.title,
                content=payload.content,
                priority=payload.priority,
                task_id=payload.task_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task or agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/agent-conflicts")
    def list_agent_conflicts(
        task_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        return service.list_agent_conflicts(task_id, agent_id, status)

    @router.post("/agent-conflicts")
    def open_agent_conflict(payload: AgentConflictCreateRequest) -> dict:
        try:
            return service.open_agent_conflict(
                raised_by_agent=payload.raised_by_agent,
                opposing_agents=payload.opposing_agents,
                issue=payload.issue,
                positions=payload.positions,
                priority_area=payload.priority_area,
                task_id=payload.task_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task or agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/agent-conflicts/{conflict_id}/resolve")
    def resolve_agent_conflict(conflict_id: str, payload: AgentConflictResolveRequest) -> dict:
        try:
            return service.resolve_agent_conflict(
                conflict_id=conflict_id,
                resolved_by=payload.resolved_by,
                resolution=payload.resolution,
                selected_position_agent=payload.selected_position_agent,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="conflict or agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/task-reviews")
    def list_task_reviews(task_id: str | None = None, reviewer_agent: str | None = None) -> list[dict]:
        return service.list_task_reviews(task_id, reviewer_agent)

    @router.post("/task-reviews")
    def record_task_review(payload: TaskReviewCreateRequest) -> dict:
        try:
            return service.record_task_review(
                task_id=payload.task_id,
                reviewer_agent=payload.reviewer_agent,
                outcome=payload.outcome,
                summary=payload.summary,
                what_went_well=payload.what_went_well,
                what_went_wrong=payload.what_went_wrong,
                lessons=payload.lessons,
                follow_up_actions=payload.follow_up_actions,
                quality_score=payload.quality_score,
                risk_level=payload.risk_level,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task or agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/task-reviews/{review_id}/improvements")
    def propose_improvement_from_review(review_id: str, payload: ImprovementProposalCreateRequest) -> dict:
        try:
            return service.propose_improvement_from_review(
                review_id=review_id,
                proposed_by_agent=payload.proposed_by_agent,
                target_type=payload.target_type,
                title=payload.title,
                description=payload.description,
                rationale=payload.rationale,
                risk_level=payload.risk_level,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="review, task, or agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/improvement-proposals")
    def list_improvement_proposals() -> list[dict]:
        return service.list_improvement_proposals()

    @router.post("/improvement-proposals/{proposal_id}/sandbox")
    def sandbox_improvement_proposal(proposal_id: str) -> dict:
        try:
            return service.sandbox_improvement_proposal(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="improvement proposal not found") from exc

    @router.post("/improvement-proposals/{proposal_id}/register")
    def register_improvement_proposal(proposal_id: str) -> dict:
        try:
            return service.register_improvement_proposal(proposal_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/github/absorptions")
    def list_github_absorptions() -> list[dict]:
        return service.list_github_absorptions()

    @router.post("/github/absorptions/analyze")
    def analyze_github_absorption(payload: GitHubAbsorptionAnalyzeRequest) -> dict:
        try:
            return service.analyze_github_absorption(
                repo_url=payload.repo_url,
                requested_by_agent=payload.requested_by_agent,
                readme=payload.readme,
                license_name=payload.license_name,
                maintenance_signal=payload.maintenance_signal,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/github/absorptions/{proposal_id}/sandbox")
    def sandbox_github_absorption(proposal_id: str) -> dict:
        try:
            return service.sandbox_github_absorption(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="github absorption not found") from exc

    @router.post("/github/absorptions/{proposal_id}/register")
    def register_github_absorption(proposal_id: str) -> dict:
        try:
            return service.register_github_absorption(proposal_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/incidents/{incident_id}/acknowledge")
    def acknowledge_incident(incident_id: str, payload: IncidentUpdateRequest) -> dict:
        try:
            return service.acknowledge_incident(incident_id, payload.actor_id, payload.note)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/incidents/{incident_id}/resolve")
    def resolve_incident(incident_id: str, payload: IncidentUpdateRequest) -> dict:
        try:
            return service.resolve_incident(incident_id, payload.actor_id, payload.note or "Resolved by Human Root.")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="incident not found") from exc

    @router.post("/models/generate")
    def generate_model_response(payload: ModelGenerateRequest) -> dict:
        try:
            return service.generate_model_response(
                prompt=payload.prompt,
                actor_id=payload.actor_id,
                purpose=payload.purpose,
                task_id=payload.task_id,
                model_name=payload.model_name,
                provider=payload.provider,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc
        except ModelProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/models/providers")
    def model_provider_status() -> dict:
        return service.model_provider_status()

    @router.post("/workflows/run")
    def run_workflow(payload: WorkflowRunRequest) -> dict:
        try:
            return service.run_registered_workflow(
                payload.workflow_id,
                payload.title,
                payload.description,
                payload.user_id,
                payload.input,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="workflow not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/goals")
    def list_strategic_goals(status: str | None = None, owner_agent: str | None = None) -> list[dict]:
        return service.list_strategic_goals(status, owner_agent)

    @router.post("/goals")
    def create_strategic_goal(payload: StrategicGoalCreateRequest) -> dict:
        try:
            return service.create_strategic_goal(
                title=payload.title,
                description=payload.description,
                owner_agent=payload.owner_agent,
                target_metric=payload.target_metric,
                target_value=payload.target_value,
                current_value=payload.current_value,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="owner agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/goals/{goal_id}/progress")
    def update_strategic_goal_progress(goal_id: str, payload: StrategicGoalProgressRequest) -> dict:
        try:
            return service.update_strategic_goal_progress(
                goal_id=goal_id,
                current_value=payload.current_value,
                status=payload.status,
                note=payload.note,
                actor_id=payload.actor_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="goal or actor agent not found") from exc

    @router.post("/goals/{goal_id}/tasks/{task_id}")
    def link_task_to_goal(goal_id: str, task_id: str, payload: StrategicGoalLinkRequest) -> dict:
        try:
            return service.link_task_to_goal(goal_id, task_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="goal, task, or actor agent not found") from exc

    @router.post("/goals/{goal_id}/reviews/{review_id}")
    def link_review_to_goal(goal_id: str, review_id: str, payload: StrategicGoalLinkRequest) -> dict:
        try:
            return service.link_review_to_goal(goal_id, review_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="goal, review, or actor agent not found") from exc

    @router.post("/goals/{goal_id}/improvements/{proposal_id}")
    def link_improvement_to_goal(goal_id: str, proposal_id: str, payload: StrategicGoalLinkRequest) -> dict:
        try:
            return service.link_improvement_to_goal(goal_id, proposal_id, payload.actor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="goal, proposal, or actor agent not found") from exc

    @router.get("/tasks")
    def list_tasks() -> list[dict]:
        return service.list_tasks()

    @router.post("/tasks")
    def create_task(payload: TaskCreateRequest) -> dict:
        return service.create_task(payload.title, payload.description, payload.user_id)

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        try:
            return service.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    @router.post("/tasks/{task_id}/run")
    def run_task(task_id: str) -> dict:
        try:
            return service.run_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    @router.post("/tasks/{task_id}/resume")
    def resume_task(task_id: str) -> dict:
        try:
            return service.resume_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task or approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/tasks/{task_id}/handoff")
    def handoff_task(task_id: str, payload: TaskHandoffRequest) -> dict:
        try:
            return service.handoff_task(
                task_id=task_id,
                from_agent=payload.from_agent,
                to_agent=payload.to_agent,
                reason=payload.reason,
                instructions=payload.instructions,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task or agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/tasks/{task_id}/pause")
    def pause_task(task_id: str) -> dict:
        try:
            return service.pause_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    @router.post("/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict:
        try:
            return service.cancel_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    @router.get("/approvals")
    def list_approvals() -> list[dict]:
        return service.list_approvals()

    @router.post("/approvals/request")
    def request_approval(payload: ApprovalRequestCreate) -> dict:
        return service.request_action_approval(
            action=payload.action,
            actor_id=payload.actor_id,
            permission_level=payload.permission_level,
            reason=payload.reason,
            task_id=payload.task_id,
            target=payload.target,
            possible_benefit=payload.possible_benefit,
            possible_loss=payload.possible_loss,
            reversible=payload.reversible,
        )

    @router.post("/approvals/{approval_id}/approve")
    def approve(approval_id: str, payload: ApprovalDecisionRequest) -> dict:
        try:
            status = payload.status or ApprovalStatus.APPROVED
            if status not in {ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED, ApprovalStatus.NEED_MORE_INFO}:
                raise HTTPException(status_code=400, detail="approve endpoint cannot reject or block")
            return service.decide_approval(approval_id, status, payload.decided_by, payload.note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="approval not found") from exc

    @router.post("/approvals/{approval_id}/reject")
    def reject(approval_id: str, payload: ApprovalDecisionRequest) -> dict:
        try:
            status = payload.status or ApprovalStatus.REJECTED
            if status not in {ApprovalStatus.REJECTED, ApprovalStatus.BLOCKED}:
                raise HTTPException(status_code=400, detail="reject endpoint cannot approve")
            return service.decide_approval(approval_id, status, payload.decided_by, payload.note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="approval not found") from exc

    @router.get("/audit-logs")
    def list_audit_logs() -> list[dict]:
        return service.list_audit_logs()

    @router.get("/logs/structured")
    def list_structured_logs(
        category: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        return service.list_structured_logs(category=category, level=level, limit=limit)

    @router.get("/memory")
    def list_memory() -> list[dict]:
        return service.list_memory()

    @router.post("/memory")
    def write_memory(payload: MemoryWriteRequest) -> dict:
        return service.write_memory(payload.task_id, payload.content, payload.memory_type)

    @router.get("/knowledge")
    def list_knowledge() -> list[dict]:
        return service.list_knowledge()

    @router.post("/knowledge")
    def write_knowledge(payload: KnowledgeWriteRequest) -> dict:
        return service.write_knowledge(payload.title, payload.content, payload.source_task_id)

    @router.post("/knowledge/search")
    def search_knowledge(payload: KnowledgeSearchRequest) -> list[dict]:
        try:
            return service.search_knowledge(payload.query, payload.actor_id, payload.limit)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/knowledge/embeddings/status")
    def embedding_status() -> dict:
        return service.embedding_status()

    @router.post("/knowledge/embeddings/reindex")
    def reindex_knowledge(payload: KnowledgeReindexRequest) -> dict:
        try:
            return service.reindex_knowledge(payload.actor_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.get("/evaluations")
    def list_evaluations() -> list[dict]:
        return service.list_evaluations()

    @router.get("/risks")
    def list_risks() -> list[dict]:
        return service.list_risks()

    @router.post("/risks/assess")
    def assess_risk(payload: RiskAssessRequest) -> dict:
        return service.assess_action(
            payload.action,
            payload.actor_id,
            payload.permission_level,
            payload.reason,
            payload.task_id,
        )

    @router.get("/dashboard/summary")
    def dashboard_summary() -> dict:
        return service.dashboard_summary()

    return router
