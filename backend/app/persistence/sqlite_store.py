from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.enums import (
    ApprovalStatus,
    IncidentStatus,
    PermissionLevel,
    RiskLevel,
    SandboxStatus,
    GoalStatus,
    ScheduleAction,
    ScheduleExecutionStatus,
    ScheduleStatus,
    SkillRunStatus,
    TaskStatus,
    ToolRunStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import (
    ActionRequest,
    Agent,
    AgentBroadcast,
    AgentConflict,
    AgentMeeting,
    AgentMessage,
    ApprovalRequest,
    AuditEvent,
    BackupRecord,
    CostLog,
    DomainEvent,
    BudgetPolicy,
    EvaluationRecord,
    Incident,
    KnowledgeDoc,
    MemoryRecord,
    ModelUsageRecord,
    RiskAssessment,
    ScheduledExecution,
    ScheduledJob,
    Skill,
    SkillRun,
    StrategicGoal,
    Task,
    TaskHandoff,
    TaskReview,
    Tool,
    ToolRun,
    User,
    WorkflowRun,
    WorkflowStep,
)
from app.chat.sessions import AgentRunStepRecord, ChatAgentRunRecord, ChatMessageRecord, ChatSessionRecord
from app.factory.proposals import AgentProposal, GitHubAbsorption, ImprovementProposal, SkillProposal
from app.services.serializers import to_plain


SQLITE_SCHEMA_VERSION = 7
BASELINE_MIGRATION_VERSION = 1
BASELINE_MIGRATION_ID = "0001_initial_local_state"
BASELINE_MIGRATION_DESCRIPTION = "Create initial local AI Company OS state tables."
AUDIT_GUARD_MIGRATION_VERSION = 2
AUDIT_GUARD_MIGRATION_ID = "0002_audit_append_only_guards"
AUDIT_GUARD_MIGRATION_DESCRIPTION = "Prevent updates and deletes on SQLite audit logs."
BACKUP_RESTORE_LEDGER_MIGRATION_VERSION = 3
BACKUP_RESTORE_LEDGER_MIGRATION_ID = "0003_backup_restore_execution_ledger"
BACKUP_RESTORE_LEDGER_MIGRATION_DESCRIPTION = "Record one-time backup restore approval consumption."
SCHEDULER_EVENT_MIGRATION_VERSION = 4
SCHEDULER_EVENT_MIGRATION_ID = "0004_scheduler_event_bus"
SCHEDULER_EVENT_MIGRATION_DESCRIPTION = "Add durable schedules, executions, and append-only domain events."
CATALOG_PERSISTENCE_MIGRATION_VERSION = 5
CATALOG_PERSISTENCE_MIGRATION_ID = "0005_agent_skill_catalogs"
CATALOG_PERSISTENCE_MIGRATION_DESCRIPTION = "Persist registered Agent and Skill catalogs."
SKILL_RUNTIME_MIGRATION_VERSION = 6
SKILL_RUNTIME_MIGRATION_ID = "0006_skill_runtime"
SKILL_RUNTIME_MIGRATION_DESCRIPTION = "Persist controlled Skill execution runs."
CHAT_SESSION_MIGRATION_VERSION = 7
CHAT_SESSION_MIGRATION_ID = "0007_chat_sessions"
CHAT_SESSION_MIGRATION_DESCRIPTION = "Persist Human Root chat sessions and action state."


class SQLiteStateStore:
    backend_name = "sqlite"
    expected_schema_version = SQLITE_SCHEMA_VERSION

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    record_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_docs (
                    doc_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    record_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tools (
                    tool_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tool_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS skill_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_steps (
                    step_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_usage (
                    record_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cost_logs (
                    record_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS budget_policies (
                    policy_id TEXT PRIMARY KEY,
                    active_key TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS skill_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS improvement_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS github_absorptions (
                    proposal_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backups (
                    backup_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_messages (
                    message_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_meetings (
                    meeting_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_broadcasts (
                    broadcast_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_reviews (
                    review_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS strategic_goals (
                    goal_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )
            self._record_baseline_migration(connection)
            self._apply_migrations(connection)
            connection.commit()

    def schema_version(self) -> int:
        with closing(self._connect()) as connection:
            cursor = connection.execute("PRAGMA user_version")
            return int(cursor.fetchone()[0])

    def list_schema_migrations(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "SELECT migration_id, version, description, applied_at "
                "FROM schema_migrations ORDER BY version"
            )
            return [
                {
                    "migration_id": row[0],
                    "version": row[1],
                    "description": row[2],
                    "applied_at": row[3],
                }
                for row in cursor.fetchall()
            ]

    def audit_append_only_guards_enabled(self) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND name IN ('audit_logs_no_update', 'audit_logs_no_delete')"
            )
            return {row[0] for row in cursor.fetchall()} == {"audit_logs_no_update", "audit_logs_no_delete"}

    def load_tasks(self) -> list[Task]:
        rows = self._select_payloads("tasks", "task_id")
        return [_task_from_plain(row) for row in rows]

    def load_users(self) -> list[User]:
        rows = self._select_payloads("users", "email")
        return [_user_from_plain(row) for row in rows]

    def load_approvals(self) -> list[ApprovalRequest]:
        rows = self._select_payloads("approvals", "approval_id")
        return [_approval_from_plain(row) for row in rows]

    def load_audit_events(self) -> list[AuditEvent]:
        rows = self._select_payloads("audit_logs", "created_at")
        return [_audit_from_plain(row) for row in rows]

    def load_memory(self) -> list[MemoryRecord]:
        rows = self._select_payloads("memories", "record_id")
        return [_memory_from_plain(row) for row in rows]

    def load_knowledge(self) -> list[KnowledgeDoc]:
        rows = self._select_payloads("knowledge_docs", "doc_id")
        return [_knowledge_from_plain(row) for row in rows]

    def load_evaluations(self) -> list[EvaluationRecord]:
        rows = self._select_payloads("evaluations", "created_at")
        return [_evaluation_from_plain(row) for row in rows]

    def load_agents(self) -> list[Agent]:
        rows = self._select_payloads("agents", "agent_id")
        return [_agent_from_plain(row) for row in rows]

    def load_skills(self) -> list[Skill]:
        rows = self._select_payloads("skills", "skill_id")
        return [_skill_from_plain(row) for row in rows]

    def load_tools(self) -> list[Tool]:
        rows = self._select_payloads("tools", "tool_id")
        return [_tool_from_plain(row) for row in rows]

    def load_tool_runs(self) -> list[ToolRun]:
        rows = self._select_payloads("tool_runs", "created_at")
        return [_tool_run_from_plain(row) for row in rows]

    def load_skill_runs(self) -> list[SkillRun]:
        rows = self._select_payloads("skill_runs", "created_at")
        return [_skill_run_from_plain(row) for row in rows]

    def load_workflow_runs(self) -> list[WorkflowRun]:
        rows = self._select_payloads("workflow_runs", "started_at")
        return [_workflow_run_from_plain(row) for row in rows]

    def load_workflow_steps(self) -> list[WorkflowStep]:
        rows = self._select_payloads("workflow_steps", "sequence")
        return [_workflow_step_from_plain(row) for row in rows]

    def load_model_usage(self) -> list[ModelUsageRecord]:
        rows = self._select_payloads("model_usage", "created_at")
        return [_model_usage_from_plain(row) for row in rows]

    def load_cost_logs(self) -> list[CostLog]:
        rows = self._select_payloads("cost_logs", "created_at")
        return [_cost_log_from_plain(row) for row in rows]

    def load_budget_policy(self) -> BudgetPolicy | None:
        rows = self._select_payloads("budget_policies", "active_key")
        if not rows:
            return None
        return _budget_policy_from_plain(rows[-1])

    def load_incidents(self) -> list[Incident]:
        rows = self._select_payloads("incidents", "created_at")
        return [_incident_from_plain(row) for row in rows]

    def load_skill_proposals(self) -> list[SkillProposal]:
        rows = self._select_payloads("skill_proposals", "proposal_id")
        return [_skill_proposal_from_plain(row) for row in rows]

    def load_agent_proposals(self) -> list[AgentProposal]:
        rows = self._select_payloads("agent_proposals", "proposal_id")
        return [_agent_proposal_from_plain(row) for row in rows]

    def load_improvement_proposals(self) -> list[ImprovementProposal]:
        rows = self._select_payloads("improvement_proposals", "proposal_id")
        return [_improvement_proposal_from_plain(row) for row in rows]

    def load_backups(self) -> list[BackupRecord]:
        rows = self._select_payloads("backups", "created_at")
        return [_backup_from_plain(row) for row in rows]

    def load_agent_messages(self) -> list[AgentMessage]:
        rows = self._select_payloads("agent_messages", "created_at")
        return [_agent_message_from_plain(row) for row in rows]

    def load_agent_meetings(self) -> list[AgentMeeting]:
        rows = self._select_payloads("agent_meetings", "created_at")
        return [_agent_meeting_from_plain(row) for row in rows]

    def load_task_handoffs(self) -> list[TaskHandoff]:
        rows = self._select_payloads("task_handoffs", "created_at")
        return [_task_handoff_from_plain(row) for row in rows]

    def load_agent_broadcasts(self) -> list[AgentBroadcast]:
        rows = self._select_payloads("agent_broadcasts", "created_at")
        return [_agent_broadcast_from_plain(row) for row in rows]

    def load_agent_conflicts(self) -> list[AgentConflict]:
        rows = self._select_payloads("agent_conflicts", "created_at")
        return [_agent_conflict_from_plain(row) for row in rows]

    def load_task_reviews(self) -> list[TaskReview]:
        rows = self._select_payloads("task_reviews", "created_at")
        return [_task_review_from_plain(row) for row in rows]

    def load_strategic_goals(self) -> list[StrategicGoal]:
        rows = self._select_payloads("strategic_goals", "created_at")
        return [_strategic_goal_from_plain(row) for row in rows]

    def load_domain_events(self) -> list[DomainEvent]:
        rows = self._select_payloads("domain_events", "created_at")
        return [_domain_event_from_plain(row) for row in rows]

    def load_scheduled_jobs(self) -> list[ScheduledJob]:
        rows = self._select_payloads("scheduled_jobs", "next_run_at")
        return [_scheduled_job_from_plain(row) for row in rows]

    def load_scheduled_executions(self) -> list[ScheduledExecution]:
        rows = self._select_payloads("scheduled_executions", "started_at")
        return [_scheduled_execution_from_plain(row) for row in rows]

    def load_chat_sessions(self) -> list[ChatSessionRecord]:
        rows = self._select_payloads("chat_sessions", "updated_at")
        return [_chat_session_from_plain(row) for row in rows]

    def load_github_absorptions(self) -> list[GitHubAbsorption]:
        rows = self._select_payloads("github_absorptions", "proposal_id")
        return [_github_absorption_from_plain(row) for row in rows]

    def save_task(self, task: Task) -> None:
        self._upsert("tasks", "task_id", task.task_id, to_plain(task))

    def save_user(self, user: User) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO users (user_id, email, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET email = excluded.email, payload_json = excluded.payload_json",
                (user.user_id, user.email, _json(to_plain(user))),
            )
            connection.commit()

    def save_approval(self, approval: ApprovalRequest) -> None:
        self._upsert("approvals", "approval_id", approval.approval_id, to_plain(approval))

    def append_audit_event(self, event: AuditEvent) -> None:
        payload = _json(to_plain(event))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO audit_logs (event_id, created_at, payload_json) VALUES (?, ?, ?)",
                (event.event_id, event.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_memory(self, record: MemoryRecord) -> None:
        self._upsert("memories", "record_id", record.record_id, to_plain(record))

    def save_knowledge(self, doc: KnowledgeDoc) -> None:
        self._upsert("knowledge_docs", "doc_id", doc.doc_id, to_plain(doc))

    def save_evaluation(self, record: EvaluationRecord) -> None:
        payload = _json(to_plain(record))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO evaluations (record_id, created_at, payload_json) VALUES (?, ?, ?)",
                (record.record_id, record.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_tool(self, tool: Tool) -> None:
        self._upsert("tools", "tool_id", tool.tool_id, to_plain(tool))

    def save_agent(self, agent: Agent) -> None:
        self._upsert("agents", "agent_id", agent.agent_id, to_plain(agent))

    def save_skill(self, skill: Skill) -> None:
        self._upsert("skills", "skill_id", skill.skill_id, to_plain(skill))

    def save_tool_run(self, run: ToolRun) -> None:
        payload = _json(to_plain(run))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO tool_runs (run_id, created_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET payload_json = excluded.payload_json",
                (run.run_id, run.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_skill_run(self, run: SkillRun) -> None:
        payload = _json(to_plain(run))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO skill_runs (run_id, created_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET payload_json = excluded.payload_json",
                (run.run_id, run.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_workflow_run(self, run: WorkflowRun) -> None:
        payload = _json(to_plain(run))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO workflow_runs (run_id, started_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET payload_json = excluded.payload_json",
                (run.run_id, run.started_at.isoformat(), payload),
            )
            connection.commit()

    def save_workflow_step(self, step: WorkflowStep) -> None:
        payload = _json(to_plain(step))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO workflow_steps (step_id, run_id, sequence, payload_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(step_id) DO UPDATE SET payload_json = excluded.payload_json",
                (step.step_id, step.run_id, step.sequence, payload),
            )
            connection.commit()

    def save_model_usage(self, record: ModelUsageRecord) -> None:
        payload = _json(to_plain(record))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO model_usage (record_id, created_at, payload_json) VALUES (?, ?, ?)",
                (record.record_id, record.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_cost_log(self, record: CostLog) -> None:
        payload = _json(to_plain(record))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO cost_logs (record_id, created_at, payload_json) VALUES (?, ?, ?)",
                (record.record_id, record.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_budget_policy(self, policy: BudgetPolicy) -> None:
        payload = _json(to_plain(policy))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO budget_policies (policy_id, active_key, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(active_key) DO UPDATE SET policy_id = excluded.policy_id, payload_json = excluded.payload_json",
                (policy.policy_id, "active", payload),
            )
            connection.commit()

    def save_incident(self, incident: Incident) -> None:
        payload = _json(to_plain(incident))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO incidents (incident_id, created_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(incident_id) DO UPDATE SET payload_json = excluded.payload_json",
                (incident.incident_id, incident.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_skill_proposal(self, proposal: SkillProposal) -> None:
        self._upsert("skill_proposals", "proposal_id", proposal.proposal_id, to_plain(proposal))

    def save_agent_proposal(self, proposal: AgentProposal) -> None:
        self._upsert("agent_proposals", "proposal_id", proposal.proposal_id, to_plain(proposal))

    def save_improvement_proposal(self, proposal: ImprovementProposal) -> None:
        self._upsert("improvement_proposals", "proposal_id", proposal.proposal_id, to_plain(proposal))

    def save_github_absorption(self, proposal: GitHubAbsorption) -> None:
        self._upsert("github_absorptions", "proposal_id", proposal.proposal_id, to_plain(proposal))

    def save_backup(self, backup: BackupRecord) -> None:
        payload = _json(to_plain(backup))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO backups (backup_id, created_at, payload_json) VALUES (?, ?, ?)",
                (backup.backup_id, backup.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_agent_message(self, message: AgentMessage) -> None:
        payload = _json(to_plain(message))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO agent_messages (message_id, created_at, payload_json) VALUES (?, ?, ?)",
                (message.message_id, message.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_agent_meeting(self, meeting: AgentMeeting) -> None:
        payload = _json(to_plain(meeting))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO agent_meetings (meeting_id, created_at, payload_json) VALUES (?, ?, ?)",
                (meeting.meeting_id, meeting.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_task_handoff(self, handoff: TaskHandoff) -> None:
        payload = _json(to_plain(handoff))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO task_handoffs (handoff_id, created_at, payload_json) VALUES (?, ?, ?)",
                (handoff.handoff_id, handoff.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_agent_broadcast(self, broadcast: AgentBroadcast) -> None:
        payload = _json(to_plain(broadcast))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO agent_broadcasts (broadcast_id, created_at, payload_json) VALUES (?, ?, ?)",
                (broadcast.broadcast_id, broadcast.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_agent_conflict(self, conflict: AgentConflict) -> None:
        payload = _json(to_plain(conflict))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO agent_conflicts (conflict_id, created_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(conflict_id) DO UPDATE SET payload_json = excluded.payload_json",
                (conflict.conflict_id, conflict.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_task_review(self, review: TaskReview) -> None:
        payload = _json(to_plain(review))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO task_reviews (review_id, created_at, payload_json) VALUES (?, ?, ?)",
                (review.review_id, review.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_strategic_goal(self, goal: StrategicGoal) -> None:
        payload = _json(to_plain(goal))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO strategic_goals (goal_id, created_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(goal_id) DO UPDATE SET payload_json = excluded.payload_json",
                (goal.goal_id, goal.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_domain_event(self, event: DomainEvent) -> None:
        payload = _json(to_plain(event))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO domain_events (event_id, created_at, payload_json) VALUES (?, ?, ?)",
                (event.event_id, event.created_at.isoformat(), payload),
            )
            connection.commit()

    def save_scheduled_job(self, job: ScheduledJob) -> None:
        payload = _json(to_plain(job))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO scheduled_jobs (schedule_id, next_run_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(schedule_id) DO UPDATE SET "
                "next_run_at = excluded.next_run_at, payload_json = excluded.payload_json",
                (job.schedule_id, job.next_run_at.isoformat(), payload),
            )
            connection.commit()

    def save_scheduled_execution(self, execution: ScheduledExecution) -> None:
        payload = _json(to_plain(execution))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO scheduled_executions "
                "(execution_id, schedule_id, started_at, payload_json) VALUES (?, ?, ?, ?)",
                (
                    execution.execution_id,
                    execution.schedule_id,
                    execution.started_at.isoformat(),
                    payload,
                ),
            )
            connection.commit()

    def save_chat_session(self, session: ChatSessionRecord) -> None:
        payload = _json(to_plain(session))
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO chat_sessions (session_id, updated_at, payload_json) VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at, "
                "payload_json = excluded.payload_json",
                (session.session_id, session.updated_at.isoformat(), payload),
            )
            connection.commit()

    def delete_chat_session(self, session_id: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            connection.commit()

    def sync_state(
        self,
        users: list[User],
        tasks: list[Task],
        approvals: list[ApprovalRequest],
        audit_events: list[AuditEvent],
        memory_records: list[MemoryRecord],
        knowledge_docs: list[KnowledgeDoc],
        evaluations: list[EvaluationRecord],
        agents: list[Agent],
        skills: list[Skill],
        tools: list[Tool],
        tool_runs: list[ToolRun],
        skill_runs: list[SkillRun],
        workflow_runs: list[WorkflowRun],
        workflow_steps: list[WorkflowStep],
        model_usage: list[ModelUsageRecord],
        cost_logs: list[CostLog],
        budget_policy: BudgetPolicy,
        incidents: list[Incident],
        skill_proposals: list[SkillProposal],
        agent_proposals: list[AgentProposal],
        improvement_proposals: list[ImprovementProposal],
        github_absorptions: list[GitHubAbsorption],
        backups: list[BackupRecord],
        agent_messages: list[AgentMessage],
        agent_meetings: list[AgentMeeting],
        task_handoffs: list[TaskHandoff],
        agent_broadcasts: list[AgentBroadcast],
        agent_conflicts: list[AgentConflict],
        task_reviews: list[TaskReview],
        strategic_goals: list[StrategicGoal],
        domain_events: list[DomainEvent],
        scheduled_jobs: list[ScheduledJob],
        scheduled_executions: list[ScheduledExecution],
        chat_sessions: list[ChatSessionRecord],
    ) -> None:
        for user in users:
            self.save_user(user)
        for task in tasks:
            self.save_task(task)
        for approval in approvals:
            self.save_approval(approval)
        for event in audit_events:
            self.append_audit_event(event)
        for record in memory_records:
            self.save_memory(record)
        for doc in knowledge_docs:
            self.save_knowledge(doc)
        for record in evaluations:
            self.save_evaluation(record)
        for agent in agents:
            self.save_agent(agent)
        for skill in skills:
            self.save_skill(skill)
        for tool in tools:
            self.save_tool(tool)
        for run in tool_runs:
            self.save_tool_run(run)
        for run in skill_runs:
            self.save_skill_run(run)
        for run in workflow_runs:
            self.save_workflow_run(run)
        for step in workflow_steps:
            self.save_workflow_step(step)
        for record in model_usage:
            self.save_model_usage(record)
        for record in cost_logs:
            self.save_cost_log(record)
        self.save_budget_policy(budget_policy)
        for incident in incidents:
            self.save_incident(incident)
        for proposal in skill_proposals:
            self.save_skill_proposal(proposal)
        for proposal in agent_proposals:
            self.save_agent_proposal(proposal)
        for proposal in improvement_proposals:
            self.save_improvement_proposal(proposal)
        for proposal in github_absorptions:
            self.save_github_absorption(proposal)
        for backup in backups:
            self.save_backup(backup)
        for message in agent_messages:
            self.save_agent_message(message)
        for meeting in agent_meetings:
            self.save_agent_meeting(meeting)
        for handoff in task_handoffs:
            self.save_task_handoff(handoff)
        for broadcast in agent_broadcasts:
            self.save_agent_broadcast(broadcast)
        for conflict in agent_conflicts:
            self.save_agent_conflict(conflict)
        for review in task_reviews:
            self.save_task_review(review)
        for goal in strategic_goals:
            self.save_strategic_goal(goal)
        for event in domain_events:
            self.save_domain_event(event)
        for job in scheduled_jobs:
            self.save_scheduled_job(job)
        for execution in scheduled_executions:
            self.save_scheduled_execution(execution)
        for session in chat_sessions:
            self.save_chat_session(session)

    def restore_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        approval_id: str,
        backup_id: str,
        actor_id: str,
        safety_backup_id: str,
    ) -> dict[str, int]:
        """Replace restorable business state while preserving control-plane history."""
        collection_specs = {
            "tasks": ("tasks", (("task_id", "task_id"),)),
            "memory": ("memories", (("record_id", "record_id"),)),
            "knowledge": ("knowledge_docs", (("doc_id", "doc_id"),)),
            "evaluations": (
                "evaluations",
                (("record_id", "record_id"), ("created_at", "created_at")),
            ),
            "strategic_goals": (
                "strategic_goals",
                (("goal_id", "goal_id"), ("created_at", "created_at")),
            ),
            "agents": ("agents", (("agent_id", "agent_id"),)),
            "skills": ("skills", (("skill_id", "skill_id"),)),
            "tools": ("tools", (("tool_id", "tool_id"),)),
            "tool_runs": (
                "tool_runs",
                (("run_id", "run_id"), ("created_at", "created_at")),
            ),
            "skill_runs": (
                "skill_runs",
                (("run_id", "run_id"), ("created_at", "created_at")),
            ),
            "workflow_runs": (
                "workflow_runs",
                (("run_id", "run_id"), ("started_at", "started_at")),
            ),
            "workflow_steps": (
                "workflow_steps",
                (
                    ("step_id", "step_id"),
                    ("run_id", "run_id"),
                    ("sequence", "sequence"),
                ),
            ),
            "model_usage": (
                "model_usage",
                (("record_id", "record_id"), ("created_at", "created_at")),
            ),
            "cost_logs": (
                "cost_logs",
                (("record_id", "record_id"), ("created_at", "created_at")),
            ),
            "skill_proposals": ("skill_proposals", (("proposal_id", "proposal_id"),)),
            "agent_proposals": ("agent_proposals", (("proposal_id", "proposal_id"),)),
            "improvement_proposals": (
                "improvement_proposals",
                (("proposal_id", "proposal_id"),),
            ),
            "github_absorptions": (
                "github_absorptions",
                (("proposal_id", "proposal_id"),),
            ),
            "agent_messages": (
                "agent_messages",
                (("message_id", "message_id"), ("created_at", "created_at")),
            ),
            "agent_meetings": (
                "agent_meetings",
                (("meeting_id", "meeting_id"), ("created_at", "created_at")),
            ),
            "task_handoffs": (
                "task_handoffs",
                (("handoff_id", "handoff_id"), ("created_at", "created_at")),
            ),
            "agent_broadcasts": (
                "agent_broadcasts",
                (("broadcast_id", "broadcast_id"), ("created_at", "created_at")),
            ),
            "agent_conflicts": (
                "agent_conflicts",
                (("conflict_id", "conflict_id"), ("created_at", "created_at")),
            ),
            "task_reviews": (
                "task_reviews",
                (("review_id", "review_id"), ("created_at", "created_at")),
            ),
            "scheduled_jobs": (
                "scheduled_jobs",
                (("schedule_id", "schedule_id"), ("next_run_at", "next_run_at")),
            ),
            "chat_sessions": (
                "chat_sessions",
                (("session_id", "session_id"), ("updated_at", "updated_at")),
            ),
        }

        prepared: dict[str, tuple[str, tuple[tuple[str, str], ...], list[dict[str, Any]]]] = {}
        optional_legacy_collections = {
            "agents", "skills", "skill_runs", "scheduled_jobs", "chat_sessions"
        }
        for snapshot_key, (table, columns) in collection_specs.items():
            records = snapshot.get(
                snapshot_key,
                [] if snapshot_key in optional_legacy_collections else None,
            )
            if not isinstance(records, list):
                raise ValueError(f"backup snapshot field {snapshot_key} must be a list")
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError(f"backup snapshot field {snapshot_key} contains a non-object record")
                for _, payload_key in columns:
                    if payload_key not in record:
                        raise ValueError(
                            f"backup snapshot field {snapshot_key} record is missing {payload_key}"
                        )
            prepared[snapshot_key] = (table, columns, records)

        budget_policy = snapshot.get("budget_policy")
        if not isinstance(budget_policy, dict) or "policy_id" not in budget_policy:
            raise ValueError("backup snapshot field budget_policy must contain a policy_id")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO backup_restore_executions "
                    "(approval_id, backup_id, actor_id, safety_backup_id, executed_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        approval_id,
                        backup_id,
                        actor_id,
                        safety_backup_id,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                for table, _, _ in prepared.values():
                    connection.execute(f"DELETE FROM {table}")
                connection.execute("DELETE FROM budget_policies")

                for table, columns, records in prepared.values():
                    column_names = [column for column, _ in columns] + ["payload_json"]
                    placeholders = ", ".join("?" for _ in column_names)
                    rows = [
                        tuple(record[payload_key] for _, payload_key in columns) + (_json(record),)
                        for record in records
                    ]
                    if rows:
                        connection.executemany(
                            f"INSERT INTO {table} ({', '.join(column_names)}) VALUES ({placeholders})",
                            rows,
                        )

                connection.execute(
                    "INSERT INTO budget_policies (policy_id, active_key, payload_json) VALUES (?, ?, ?)",
                    (budget_policy["policy_id"], "active", _json(budget_policy)),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                if "backup_restore_executions.approval_id" in str(exc):
                    raise ValueError("backup restore approval has already been used") from exc
                raise
            except Exception:
                connection.rollback()
                raise

        counts = {snapshot_key: len(records) for snapshot_key, (_, _, records) in prepared.items()}
        counts["budget_policy"] = 1
        return counts

    def _select_payloads(self, table: str, order_by: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            cursor = connection.execute(f"SELECT payload_json FROM {table} ORDER BY {order_by}")
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def _upsert(self, table: str, key_name: str, key_value: str, payload: dict[str, Any]) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                f"INSERT INTO {table} ({key_name}, payload_json) VALUES (?, ?) "
                f"ON CONFLICT({key_name}) DO UPDATE SET payload_json = excluded.payload_json",
                (key_value, _json(payload)),
            )
            connection.commit()

    def _record_baseline_migration(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL UNIQUE,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                BASELINE_MIGRATION_ID,
                BASELINE_MIGRATION_VERSION,
                BASELINE_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        if self._current_schema_version(connection) < BASELINE_MIGRATION_VERSION:
            connection.execute(f"PRAGMA user_version = {BASELINE_MIGRATION_VERSION}")

    def _apply_migrations(self, connection: sqlite3.Connection) -> None:
        if self._current_schema_version(connection) < AUDIT_GUARD_MIGRATION_VERSION:
            self._apply_audit_append_only_guards(connection)
        if self._current_schema_version(connection) < BACKUP_RESTORE_LEDGER_MIGRATION_VERSION:
            self._apply_backup_restore_execution_ledger(connection)
        if self._current_schema_version(connection) < SCHEDULER_EVENT_MIGRATION_VERSION:
            self._apply_scheduler_event_bus(connection)
        if self._current_schema_version(connection) < CATALOG_PERSISTENCE_MIGRATION_VERSION:
            self._apply_catalog_persistence(connection)
        if self._current_schema_version(connection) < SKILL_RUNTIME_MIGRATION_VERSION:
            self._apply_skill_runtime(connection)
        if self._current_schema_version(connection) < CHAT_SESSION_MIGRATION_VERSION:
            self._apply_chat_sessions(connection)

    def _apply_audit_append_only_guards(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs are append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'audit_logs are append-only');
            END;
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                AUDIT_GUARD_MIGRATION_ID,
                AUDIT_GUARD_MIGRATION_VERSION,
                AUDIT_GUARD_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(f"PRAGMA user_version = {AUDIT_GUARD_MIGRATION_VERSION}")

    def _apply_backup_restore_execution_ledger(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS backup_restore_executions (
                approval_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                safety_backup_id TEXT NOT NULL,
                executed_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                BACKUP_RESTORE_LEDGER_MIGRATION_ID,
                BACKUP_RESTORE_LEDGER_MIGRATION_VERSION,
                BACKUP_RESTORE_LEDGER_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(f"PRAGMA user_version = {BACKUP_RESTORE_LEDGER_MIGRATION_VERSION}")

    def _apply_scheduler_event_bus(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS domain_events (
                event_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                schedule_id TEXT PRIMARY KEY,
                next_run_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scheduled_executions (
                execution_id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS domain_events_no_update
            BEFORE UPDATE ON domain_events
            BEGIN
                SELECT RAISE(ABORT, 'domain_events are append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS domain_events_no_delete
            BEFORE DELETE ON domain_events
            BEGIN
                SELECT RAISE(ABORT, 'domain_events are append-only');
            END;
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                SCHEDULER_EVENT_MIGRATION_ID,
                SCHEDULER_EVENT_MIGRATION_VERSION,
                SCHEDULER_EVENT_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(f"PRAGMA user_version = {SCHEDULER_EVENT_MIGRATION_VERSION}")

    def _apply_catalog_persistence(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                CATALOG_PERSISTENCE_MIGRATION_ID,
                CATALOG_PERSISTENCE_MIGRATION_VERSION,
                CATALOG_PERSISTENCE_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(f"PRAGMA user_version = {CATALOG_PERSISTENCE_MIGRATION_VERSION}")

    def _apply_skill_runtime(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                SKILL_RUNTIME_MIGRATION_ID,
                SKILL_RUNTIME_MIGRATION_VERSION,
                SKILL_RUNTIME_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(f"PRAGMA user_version = {SKILL_RUNTIME_MIGRATION_VERSION}")

    def _apply_chat_sessions(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (
                CHAT_SESSION_MIGRATION_ID,
                CHAT_SESSION_MIGRATION_VERSION,
                CHAT_SESSION_MIGRATION_DESCRIPTION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(f"PRAGMA user_version = {CHAT_SESSION_MIGRATION_VERSION}")

    def _current_schema_version(self, connection: sqlite3.Connection) -> int:
        cursor = connection.execute("PRAGMA user_version")
        return int(cursor.fetchone()[0])


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _chat_message_from_plain(payload: dict[str, Any]) -> ChatMessageRecord:
    return ChatMessageRecord(
        role=payload["role"],
        content=payload["content"],
        message_id=payload["message_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        provider=payload.get("provider"),
        model=payload.get("model"),
        total_tokens=payload.get("total_tokens"),
        cost=payload.get("cost"),
        fallback_used=payload.get("fallback_used"),
        failed=payload.get("failed", False),
        action=dict(payload["action"]) if payload.get("action") else None,
    )


def _chat_session_from_plain(payload: dict[str, Any]) -> ChatSessionRecord:
    return ChatSessionRecord(
        owner_id=payload.get("owner_id", "human_root"),
        title=payload.get("title", "New chat"),
        messages=[_chat_message_from_plain(item) for item in payload.get("messages", [])],
        session_id=payload["session_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        updated_at=_dt(payload["updated_at"]) or datetime.min,
        import_key=payload.get("import_key"),
        agent_runs=[_chat_agent_run_from_plain(item) for item in payload.get("agent_runs", [])],
    )


def _agent_run_step_from_plain(payload: dict[str, Any]) -> AgentRunStepRecord:
    return AgentRunStepRecord(
        sequence=int(payload["sequence"]),
        intent=payload["intent"],
        status=payload.get("status", "planned"),
        tool_id=payload.get("tool_id"),
        tool_input=dict(payload.get("tool_input", {})),
        task_id=payload.get("task_id"),
        approval_id=payload.get("approval_id"),
        observation=payload.get("observation"),
        usage=dict(payload["usage"]) if payload.get("usage") else None,
        step_id=payload["step_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        completed_at=_dt(payload.get("completed_at")),
    )


def _chat_agent_run_from_plain(payload: dict[str, Any]) -> ChatAgentRunRecord:
    return ChatAgentRunRecord(
        session_id=payload["session_id"],
        proposal_id=payload["proposal_id"],
        objective=payload["objective"],
        provider=payload["provider"],
        model=payload["model"],
        max_steps=int(payload.get("max_steps", 8)),
        status=payload.get("status", "running"),
        steps=[_agent_run_step_from_plain(item) for item in payload.get("steps", [])],
        final_answer=payload.get("final_answer"),
        error=payload.get("error"),
        run_id=payload["run_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        updated_at=_dt(payload["updated_at"]) or datetime.min,
    )


def _task_from_plain(payload: dict[str, Any]) -> Task:
    task = Task(
        title=payload["title"],
        description=payload["description"],
        user_id=payload.get("user_id", "human_root"),
        task_id=payload["task_id"],
        status=TaskStatus(payload["status"]),
        result=payload.get("result"),
        risk_level=RiskLevel(payload.get("risk_level", RiskLevel.LOW.value)),
        approval_id=payload.get("approval_id"),
        history=[TaskStatus(item) for item in payload.get("history", [TaskStatus.CREATED.value])],
    )
    return task


def _user_from_plain(payload: dict[str, Any]) -> User:
    return User(
        email=payload["email"],
        password_hash=payload["password_hash"],
        role=payload.get("role", "human_root"),
        user_id=payload["user_id"],
        enabled=payload.get("enabled", True),
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _action_from_plain(payload: dict[str, Any]) -> ActionRequest:
    return ActionRequest(
        action=payload["action"],
        actor_id=payload["actor_id"],
        task_id=payload.get("task_id"),
        permission_level=PermissionLevel(payload["permission_level"]),
        reason=payload["reason"],
        target=payload.get("target"),
        reversible=payload.get("reversible", True),
        metadata=payload.get("metadata", {}),
    )


def _risk_from_plain(payload: dict[str, Any]) -> RiskAssessment:
    return RiskAssessment(
        request=_action_from_plain(payload["request"]),
        level=RiskLevel(payload["level"]),
        reasons=tuple(payload.get("reasons", [])),
        requires_approval=payload["requires_approval"],
        blocked=payload["blocked"],
    )


def _approval_from_plain(payload: dict[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        request=_action_from_plain(payload["request"]),
        risk=_risk_from_plain(payload["risk"]),
        possible_benefit=payload["possible_benefit"],
        possible_loss=payload["possible_loss"],
        recommendation=payload["recommendation"],
        approval_id=payload["approval_id"],
        status=ApprovalStatus(payload["status"]),
        created_at=_dt(payload["created_at"]) or datetime.min,
        decided_at=_dt(payload.get("decided_at")),
        decided_by=payload.get("decided_by"),
        decision_note=payload.get("decision_note"),
    )


def _audit_from_plain(payload: dict[str, Any]) -> AuditEvent:
    return AuditEvent(
        event_type=payload["event_type"],
        actor_id=payload["actor_id"],
        action=payload["action"],
        task_id=payload.get("task_id"),
        risk_level=RiskLevel(payload["risk_level"]),
        approval_status=ApprovalStatus(payload["approval_status"]),
        result=payload["result"],
        input_ref=payload.get("input_ref"),
        output_ref=payload.get("output_ref"),
        error=payload.get("error"),
        model_name=payload.get("model_name"),
        version=payload.get("version", "1.0.0"),
        event_id=payload["event_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _memory_from_plain(payload: dict[str, Any]) -> MemoryRecord:
    return MemoryRecord(
        task_id=payload["task_id"],
        content=payload["content"],
        memory_type=payload.get("memory_type", "task"),
        record_id=payload["record_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _knowledge_from_plain(payload: dict[str, Any]) -> KnowledgeDoc:
    return KnowledgeDoc(
        title=payload["title"],
        content=payload["content"],
        source_task_id=payload.get("source_task_id"),
        doc_id=payload["doc_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _evaluation_from_plain(payload: dict[str, Any]) -> EvaluationRecord:
    return EvaluationRecord(
        subject_type=payload["subject_type"],
        subject_id=payload["subject_id"],
        task_id=payload.get("task_id"),
        score=float(payload["score"]),
        metric=payload["metric"],
        notes=payload["notes"],
        risk_level=RiskLevel(payload.get("risk_level", RiskLevel.LOW.value)),
        record_id=payload["record_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _agent_from_plain(payload: dict[str, Any]) -> Agent:
    return Agent(
        agent_id=payload["agent_id"],
        name=payload["name"],
        department=payload["department"],
        role=payload["role"],
        permissions={PermissionLevel(value) for value in payload.get("permissions", [])},
        forbidden=set(payload.get("forbidden", [])),
        allowed_skills=set(payload.get("allowed_skills", [])),
        allowed_tools=set(payload.get("allowed_tools", [])),
        reports_to=payload["reports_to"],
        risk_level=RiskLevel(payload["risk_level"]),
        version=payload.get("version", "1.0.0"),
        enabled=payload.get("enabled", True),
    )


def _skill_from_plain(payload: dict[str, Any]) -> Skill:
    return Skill(
        skill_id=payload["skill_id"],
        name=payload["name"],
        type=payload["type"],
        description=payload["description"],
        input_schema=dict(payload.get("input_schema", {})),
        output_schema=dict(payload.get("output_schema", {})),
        allowed_agents=set(payload.get("allowed_agents", [])),
        risk_level=RiskLevel(payload["risk_level"]),
        requires_approval=payload["requires_approval"],
        version=payload.get("version", "1.0.0"),
        enabled=payload.get("enabled", True),
    )


def _tool_from_plain(payload: dict[str, Any]) -> Tool:
    return Tool(
        tool_id=payload["tool_id"],
        name=payload["name"],
        type=payload["type"],
        description=payload["description"],
        action=payload["action"],
        permission_level=PermissionLevel(payload["permission_level"]),
        risk_level=RiskLevel(payload["risk_level"]),
        requires_approval=payload["requires_approval"],
        input_schema=payload.get("input_schema", {}),
        output_schema=payload.get("output_schema", {}),
        version=payload.get("version", "1.0.0"),
        enabled=payload.get("enabled", True),
    )


def _tool_run_from_plain(payload: dict[str, Any]) -> ToolRun:
    return ToolRun(
        tool_id=payload["tool_id"],
        actor_id=payload["actor_id"],
        action=payload["action"],
        input=payload.get("input", {}),
        reason=payload["reason"],
        task_id=payload.get("task_id"),
        status=ToolRunStatus(payload.get("status", ToolRunStatus.REQUESTED.value)),
        result=payload.get("result"),
        risk_level=RiskLevel(payload.get("risk_level", RiskLevel.LOW.value)),
        approval_id=payload.get("approval_id"),
        error=payload.get("error"),
        run_id=payload["run_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        completed_at=_dt(payload.get("completed_at")),
    )


def _skill_run_from_plain(payload: dict[str, Any]) -> SkillRun:
    return SkillRun(
        skill_id=payload["skill_id"],
        actor_id=payload["actor_id"],
        input=payload.get("input", {}),
        reason=payload["reason"],
        task_id=payload.get("task_id"),
        status=SkillRunStatus(payload.get("status", SkillRunStatus.REQUESTED.value)),
        result=payload.get("result"),
        risk_level=RiskLevel(payload.get("risk_level", RiskLevel.LOW.value)),
        approval_id=payload.get("approval_id"),
        error=payload.get("error"),
        run_id=payload["run_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        completed_at=_dt(payload.get("completed_at")),
    )


def _workflow_run_from_plain(payload: dict[str, Any]) -> WorkflowRun:
    return WorkflowRun(
        workflow_id=payload["workflow_id"],
        task_id=payload["task_id"],
        status=WorkflowRunStatus(payload.get("status", WorkflowRunStatus.RUNNING.value)),
        result=payload.get("result"),
        run_id=payload["run_id"],
        started_at=_dt(payload["started_at"]) or datetime.min,
        completed_at=_dt(payload.get("completed_at")),
    )


def _workflow_step_from_plain(payload: dict[str, Any]) -> WorkflowStep:
    return WorkflowStep(
        run_id=payload["run_id"],
        task_id=payload["task_id"],
        sequence=int(payload["sequence"]),
        step_name=payload["step_name"],
        actor_id=payload["actor_id"],
        action=payload["action"],
        status=WorkflowStepStatus(payload["status"]),
        risk_level=RiskLevel(payload["risk_level"]),
        approval_status=ApprovalStatus(payload["approval_status"]),
        result=payload["result"],
        error=payload.get("error"),
        step_id=payload["step_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        completed_at=_dt(payload.get("completed_at")),
    )


def _model_usage_from_plain(payload: dict[str, Any]) -> ModelUsageRecord:
    return ModelUsageRecord(
        model_name=payload["model_name"],
        provider=payload["provider"],
        actor_id=payload["actor_id"],
        task_id=payload.get("task_id"),
        purpose=payload["purpose"],
        prompt_tokens=int(payload["prompt_tokens"]),
        completion_tokens=int(payload["completion_tokens"]),
        total_tokens=int(payload["total_tokens"]),
        estimated_cost=float(payload["estimated_cost"]),
        input_ref=payload["input_ref"],
        output_ref=payload["output_ref"],
        record_id=payload["record_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _cost_log_from_plain(payload: dict[str, Any]) -> CostLog:
    return CostLog(
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        actor_id=payload["actor_id"],
        task_id=payload.get("task_id"),
        tokens=int(payload["tokens"]),
        amount=float(payload["amount"]),
        currency=payload.get("currency", "USD"),
        result=payload["result"],
        reason=payload["reason"],
        record_id=payload["record_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _budget_policy_from_plain(payload: dict[str, Any]) -> BudgetPolicy:
    return BudgetPolicy(
        name=payload.get("name", "Default Model Budget"),
        max_tokens_per_call=int(payload.get("max_tokens_per_call", 2_000)),
        max_total_tokens=int(payload.get("max_total_tokens", 100_000)),
        max_estimated_cost=float(payload.get("max_estimated_cost", 10.0)),
        cost_per_token=float(payload.get("cost_per_token", 0.000001)),
        currency=payload.get("currency", "USD"),
        enabled=payload.get("enabled", True),
        policy_id=payload["policy_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _incident_from_plain(payload: dict[str, Any]) -> Incident:
    return Incident(
        title=payload["title"],
        description=payload["description"],
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        risk_level=RiskLevel(payload["risk_level"]),
        status=IncidentStatus(payload.get("status", IncidentStatus.OPEN.value)),
        task_id=payload.get("task_id"),
        actor_id=payload.get("actor_id"),
        recommendation=payload.get(
            "recommendation",
            "Review the blocked action and decide whether policy, permissions, or task input should change.",
        ),
        incident_id=payload["incident_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        acknowledged_at=_dt(payload.get("acknowledged_at")),
        acknowledged_by=payload.get("acknowledged_by"),
        resolved_at=_dt(payload.get("resolved_at")),
        resolved_by=payload.get("resolved_by"),
        resolution_note=payload.get("resolution_note"),
    )


def _skill_proposal_from_plain(payload: dict[str, Any]) -> SkillProposal:
    from app.core.enums import ProposalStatus

    return SkillProposal(
        name=payload["name"],
        description=payload["description"],
        requested_by_agent=payload["requested_by_agent"],
        risk_level=RiskLevel(payload["risk_level"]),
        requires_approval=payload["requires_approval"],
        proposal_id=payload["proposal_id"],
        enabled_by_default=payload.get("enabled_by_default", False),
        status=ProposalStatus(payload.get("status", ProposalStatus.PROPOSED.value)),
        approval_id=payload.get("approval_id"),
        sandbox_status=SandboxStatus(payload.get("sandbox_status", SandboxStatus.NOT_RUN.value)),
        sandbox_notes=payload.get("sandbox_notes"),
        sandboxed_at=_dt(payload.get("sandboxed_at")),
    )


def _agent_proposal_from_plain(payload: dict[str, Any]) -> AgentProposal:
    from app.core.enums import ProposalStatus

    return AgentProposal(
        name=payload["name"],
        department=payload["department"],
        role=payload["role"],
        proposed_permissions={PermissionLevel(item) for item in payload.get("proposed_permissions", [])},
        proposed_skills=set(payload.get("proposed_skills", [])),
        risk_level=RiskLevel(payload["risk_level"]),
        proposal_id=payload["proposal_id"],
        enabled_by_default=payload.get("enabled_by_default", False),
        status=ProposalStatus(payload.get("status", ProposalStatus.PROPOSED.value)),
        approval_id=payload.get("approval_id"),
        sandbox_status=SandboxStatus(payload.get("sandbox_status", SandboxStatus.NOT_RUN.value)),
        sandbox_notes=payload.get("sandbox_notes"),
        sandboxed_at=_dt(payload.get("sandboxed_at")),
    )


def _improvement_proposal_from_plain(payload: dict[str, Any]) -> ImprovementProposal:
    from app.core.enums import ProposalStatus

    return ImprovementProposal(
        source_review_id=payload["source_review_id"],
        task_id=payload["task_id"],
        proposed_by_agent=payload["proposed_by_agent"],
        target_type=payload["target_type"],
        title=payload["title"],
        description=payload["description"],
        rationale=payload["rationale"],
        lessons=list(payload.get("lessons", [])),
        follow_up_actions=list(payload.get("follow_up_actions", [])),
        risk_level=RiskLevel(payload["risk_level"]),
        requires_approval=payload.get("requires_approval", True),
        proposal_id=payload["proposal_id"],
        enabled_by_default=payload.get("enabled_by_default", False),
        status=ProposalStatus(payload.get("status", ProposalStatus.PROPOSED.value)),
        approval_id=payload.get("approval_id"),
        sandbox_status=SandboxStatus(payload.get("sandbox_status", SandboxStatus.NOT_RUN.value)),
        sandbox_notes=payload.get("sandbox_notes"),
        sandboxed_at=_dt(payload.get("sandboxed_at")),
    )


def _github_absorption_from_plain(payload: dict[str, Any]) -> GitHubAbsorption:
    from app.core.enums import ProposalStatus

    return GitHubAbsorption(
        repo_url=payload["repo_url"],
        requested_by_agent=payload["requested_by_agent"],
        summary=payload["summary"],
        readme_excerpt=payload.get("readme_excerpt", ""),
        license_name=payload.get("license_name", "unknown"),
        maintenance_signal=payload.get("maintenance_signal", "unknown"),
        external_content_findings=list(payload.get("external_content_findings", [])),
        security_findings=list(payload.get("security_findings", [])),
        recommended_capabilities=list(payload.get("recommended_capabilities", [])),
        risk_level=RiskLevel(payload["risk_level"]),
        requires_approval=payload.get("requires_approval", True),
        proposal_id=payload["proposal_id"],
        status=ProposalStatus(payload.get("status", ProposalStatus.PROPOSED.value)),
        approval_id=payload.get("approval_id"),
        sandbox_status=SandboxStatus(payload.get("sandbox_status", SandboxStatus.NOT_RUN.value)),
        sandbox_notes=payload.get("sandbox_notes"),
        sandboxed_at=_dt(payload.get("sandboxed_at")),
        registered_doc_id=payload.get("registered_doc_id"),
    )


def _backup_from_plain(payload: dict[str, Any]) -> BackupRecord:
    return BackupRecord(
        reason=payload["reason"],
        actor_id=payload["actor_id"],
        snapshot=payload.get("snapshot", {}),
        rollback_plan=payload.get("rollback_plan", "Manual restore from stored snapshot after Human Root approval."),
        backup_checksum=payload.get("backup_checksum"),
        backup_id=payload["backup_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _domain_event_from_plain(payload: dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type=payload["event_type"],
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        actor_id=payload["actor_id"],
        payload=dict(payload.get("payload", {})),
        task_id=payload.get("task_id"),
        event_id=payload["event_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _scheduled_job_from_plain(payload: dict[str, Any]) -> ScheduledJob:
    return ScheduledJob(
        name=payload["name"],
        action=ScheduleAction(payload["action"]),
        payload=dict(payload.get("payload", {})),
        created_by=payload["created_by"],
        next_run_at=_dt(payload["next_run_at"]) or datetime.min,
        interval_seconds=payload.get("interval_seconds"),
        max_runs=payload.get("max_runs"),
        schedule_id=payload["schedule_id"],
        status=ScheduleStatus(payload.get("status", ScheduleStatus.ACTIVE.value)),
        run_count=int(payload.get("run_count", 0)),
        failure_count=int(payload.get("failure_count", 0)),
        last_run_at=_dt(payload.get("last_run_at")),
        last_error=payload.get("last_error"),
        created_at=_dt(payload["created_at"]) or datetime.min,
        updated_at=_dt(payload["updated_at"]) or datetime.min,
    )


def _scheduled_execution_from_plain(payload: dict[str, Any]) -> ScheduledExecution:
    return ScheduledExecution(
        schedule_id=payload["schedule_id"],
        action=ScheduleAction(payload["action"]),
        status=ScheduleExecutionStatus(payload["status"]),
        actor_id=payload["actor_id"],
        output_ref=payload.get("output_ref"),
        error=payload.get("error"),
        execution_id=payload["execution_id"],
        started_at=_dt(payload["started_at"]) or datetime.min,
        completed_at=_dt(payload["completed_at"]) or datetime.min,
    )


def _agent_message_from_plain(payload: dict[str, Any]) -> AgentMessage:
    return AgentMessage(
        from_agent=payload["from_agent"],
        to_agent=payload["to_agent"],
        message_type=payload["message_type"],
        content=payload["content"],
        priority=payload.get("priority", "medium"),
        requires_response=payload.get("requires_response", False),
        task_id=payload.get("task_id"),
        message_id=payload["message_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _agent_meeting_from_plain(payload: dict[str, Any]) -> AgentMeeting:
    return AgentMeeting(
        title=payload["title"],
        organizer_agent=payload["organizer_agent"],
        participant_agents=list(payload.get("participant_agents", [])),
        agenda=payload["agenda"],
        meeting_type=payload.get("meeting_type", "group"),
        task_id=payload.get("task_id"),
        minutes=payload.get("minutes"),
        meeting_id=payload["meeting_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _task_handoff_from_plain(payload: dict[str, Any]) -> TaskHandoff:
    return TaskHandoff(
        task_id=payload["task_id"],
        from_agent=payload["from_agent"],
        to_agent=payload["to_agent"],
        reason=payload["reason"],
        task_status=TaskStatus(payload["task_status"]),
        instructions=payload.get("instructions"),
        message_id=payload.get("message_id"),
        handoff_id=payload["handoff_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _agent_broadcast_from_plain(payload: dict[str, Any]) -> AgentBroadcast:
    return AgentBroadcast(
        from_agent=payload["from_agent"],
        audience_agents=list(payload.get("audience_agents", [])),
        event_type=payload["event_type"],
        title=payload["title"],
        content=payload["content"],
        priority=payload.get("priority", "medium"),
        task_id=payload.get("task_id"),
        broadcast_id=payload["broadcast_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _agent_conflict_from_plain(payload: dict[str, Any]) -> AgentConflict:
    return AgentConflict(
        raised_by_agent=payload["raised_by_agent"],
        opposing_agents=list(payload.get("opposing_agents", [])),
        issue=payload["issue"],
        positions=dict(payload.get("positions", {})),
        priority_area=payload.get("priority_area", "safety"),
        task_id=payload.get("task_id"),
        status=payload.get("status", "open"),
        resolution=payload.get("resolution"),
        resolved_by=payload.get("resolved_by"),
        selected_position_agent=payload.get("selected_position_agent"),
        conflict_id=payload["conflict_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        resolved_at=_dt(payload.get("resolved_at")),
    )


def _task_review_from_plain(payload: dict[str, Any]) -> TaskReview:
    return TaskReview(
        task_id=payload["task_id"],
        reviewer_agent=payload["reviewer_agent"],
        outcome=payload["outcome"],
        summary=payload["summary"],
        what_went_well=payload.get("what_went_well", ""),
        what_went_wrong=payload.get("what_went_wrong", ""),
        lessons=list(payload.get("lessons", [])),
        follow_up_actions=list(payload.get("follow_up_actions", [])),
        quality_score=float(payload["quality_score"]),
        risk_level=RiskLevel(payload.get("risk_level", RiskLevel.LOW.value)),
        review_id=payload["review_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
    )


def _strategic_goal_from_plain(payload: dict[str, Any]) -> StrategicGoal:
    return StrategicGoal(
        title=payload["title"],
        description=payload["description"],
        owner_agent=payload["owner_agent"],
        target_metric=payload["target_metric"],
        target_value=float(payload["target_value"]),
        current_value=float(payload.get("current_value", 0.0)),
        status=GoalStatus(payload.get("status", GoalStatus.ACTIVE.value)),
        linked_task_ids=list(payload.get("linked_task_ids", [])),
        linked_review_ids=list(payload.get("linked_review_ids", [])),
        linked_improvement_ids=list(payload.get("linked_improvement_ids", [])),
        goal_id=payload["goal_id"],
        created_at=_dt(payload["created_at"]) or datetime.min,
        updated_at=_dt(payload["updated_at"]) or datetime.min,
    )
