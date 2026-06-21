from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.persistence import sqlite_store as codecs
from app.services.serializers import to_plain


POSTGRES_SCHEMA_VERSION = 3


@dataclass(frozen=True)
class _RecordSpec:
    table: str
    id_attr: str
    sort_attr: str
    decoder: Callable[[dict[str, Any]], Any]
    append_only: bool = False


_SPECS = {
    "users": _RecordSpec("users", "user_id", "email", codecs._user_from_plain),
    "tasks": _RecordSpec("tasks", "task_id", "task_id", codecs._task_from_plain),
    "approvals": _RecordSpec("approvals", "approval_id", "approval_id", codecs._approval_from_plain),
    "audit_events": _RecordSpec(
        "audit_logs", "event_id", "created_at", codecs._audit_from_plain, append_only=True
    ),
    "memory_records": _RecordSpec("memories", "record_id", "record_id", codecs._memory_from_plain),
    "knowledge_docs": _RecordSpec("knowledge_docs", "doc_id", "doc_id", codecs._knowledge_from_plain),
    "evaluations": _RecordSpec(
        "evaluations", "record_id", "created_at", codecs._evaluation_from_plain, append_only=True
    ),
    "agents": _RecordSpec("agents", "agent_id", "agent_id", codecs._agent_from_plain),
    "skills": _RecordSpec("skills", "skill_id", "skill_id", codecs._skill_from_plain),
    "tools": _RecordSpec("tools", "tool_id", "tool_id", codecs._tool_from_plain),
    "tool_runs": _RecordSpec("tool_runs", "run_id", "created_at", codecs._tool_run_from_plain),
    "skill_runs": _RecordSpec("skill_runs", "run_id", "created_at", codecs._skill_run_from_plain),
    "workflow_runs": _RecordSpec(
        "workflow_runs", "run_id", "started_at", codecs._workflow_run_from_plain
    ),
    "workflow_steps": _RecordSpec(
        "workflow_steps", "step_id", "sequence", codecs._workflow_step_from_plain
    ),
    "model_usage": _RecordSpec(
        "model_usage", "record_id", "created_at", codecs._model_usage_from_plain, append_only=True
    ),
    "cost_logs": _RecordSpec(
        "cost_logs", "record_id", "created_at", codecs._cost_log_from_plain, append_only=True
    ),
    "incidents": _RecordSpec("incidents", "incident_id", "created_at", codecs._incident_from_plain),
    "skill_proposals": _RecordSpec(
        "skill_proposals", "proposal_id", "proposal_id", codecs._skill_proposal_from_plain
    ),
    "agent_proposals": _RecordSpec(
        "agent_proposals", "proposal_id", "proposal_id", codecs._agent_proposal_from_plain
    ),
    "improvement_proposals": _RecordSpec(
        "improvement_proposals",
        "proposal_id",
        "proposal_id",
        codecs._improvement_proposal_from_plain,
    ),
    "github_absorptions": _RecordSpec(
        "github_absorptions", "proposal_id", "proposal_id", codecs._github_absorption_from_plain
    ),
    "backups": _RecordSpec(
        "backups", "backup_id", "created_at", codecs._backup_from_plain, append_only=True
    ),
    "agent_messages": _RecordSpec(
        "agent_messages", "message_id", "created_at", codecs._agent_message_from_plain, append_only=True
    ),
    "agent_meetings": _RecordSpec(
        "agent_meetings", "meeting_id", "created_at", codecs._agent_meeting_from_plain, append_only=True
    ),
    "task_handoffs": _RecordSpec(
        "task_handoffs", "handoff_id", "created_at", codecs._task_handoff_from_plain, append_only=True
    ),
    "agent_broadcasts": _RecordSpec(
        "agent_broadcasts",
        "broadcast_id",
        "created_at",
        codecs._agent_broadcast_from_plain,
        append_only=True,
    ),
    "agent_conflicts": _RecordSpec(
        "agent_conflicts", "conflict_id", "created_at", codecs._agent_conflict_from_plain
    ),
    "task_reviews": _RecordSpec(
        "task_reviews", "review_id", "created_at", codecs._task_review_from_plain, append_only=True
    ),
    "strategic_goals": _RecordSpec(
        "strategic_goals", "goal_id", "created_at", codecs._strategic_goal_from_plain
    ),
    "domain_events": _RecordSpec(
        "domain_events", "event_id", "created_at", codecs._domain_event_from_plain, append_only=True
    ),
    "scheduled_jobs": _RecordSpec(
        "scheduled_jobs", "schedule_id", "next_run_at", codecs._scheduled_job_from_plain
    ),
    "scheduled_executions": _RecordSpec(
        "scheduled_executions",
        "execution_id",
        "started_at",
        codecs._scheduled_execution_from_plain,
        append_only=True,
    ),
}

_RESTORE_COLLECTIONS = {
    "tasks": "tasks",
    "memory": "memory_records",
    "knowledge": "knowledge_docs",
    "evaluations": "evaluations",
    "strategic_goals": "strategic_goals",
    "agents": "agents",
    "skills": "skills",
    "tools": "tools",
    "tool_runs": "tool_runs",
    "skill_runs": "skill_runs",
    "workflow_runs": "workflow_runs",
    "workflow_steps": "workflow_steps",
    "model_usage": "model_usage",
    "cost_logs": "cost_logs",
    "skill_proposals": "skill_proposals",
    "agent_proposals": "agent_proposals",
    "improvement_proposals": "improvement_proposals",
    "github_absorptions": "github_absorptions",
    "agent_messages": "agent_messages",
    "agent_meetings": "agent_meetings",
    "task_handoffs": "task_handoffs",
    "agent_broadcasts": "agent_broadcasts",
    "agent_conflicts": "agent_conflicts",
    "task_reviews": "task_reviews",
    "scheduled_jobs": "scheduled_jobs",
}

_OPTIONAL_LEGACY_COLLECTIONS = {"agents", "skills", "skill_runs", "scheduled_jobs"}


class PostgresStateStore:
    backend_name = "postgresql"
    expected_schema_version = POSTGRES_SCHEMA_VERSION

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        try:
            self._psycopg = importlib.import_module("psycopg")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PostgreSQL persistence requires psycopg; install the backend production dependencies"
            ) from exc
        self.database_url = database_url
        self._init_schema()

    def _connect(self):
        return self._psycopg.connect(self.database_url)

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('ai_company_os_schema_migrations'))"
            )
            applied = {
                row[0]
                for row in connection.execute("SELECT migration_id FROM schema_migrations").fetchall()
            }
            if "0001_postgresql_state" not in applied:
                self._apply_state_schema(connection)
                self._record_migration(
                    connection,
                    "0001_postgresql_state",
                    1,
                    "Create PostgreSQL JSONB state tables and restore execution ledger.",
                )
            if "0002_append_only_guards" not in applied:
                self._apply_append_only_guards(connection)
                self._record_migration(
                    connection,
                    "0002_append_only_guards",
                    2,
                    "Protect audit logs and domain events from updates and deletes.",
                )
            if "0003_pgvector_knowledge" not in applied:
                self._apply_pgvector_schema(connection)
                self._record_migration(
                    connection,
                    "0003_pgvector_knowledge",
                    3,
                    "Enable pgvector and create indexed knowledge embeddings.",
                )

    def _apply_state_schema(self, connection: Any) -> None:
        for spec in _SPECS.values():
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {spec.table} (
                    record_id TEXT PRIMARY KEY,
                    sort_key TEXT NOT NULL,
                    payload_json JSONB NOT NULL
                )
                """
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {spec.table}_sort_key_idx ON {spec.table} (sort_key)"
            )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS users_email_idx ON users ((payload_json->>'email'))"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS budget_policies (
                record_id TEXT PRIMARY KEY,
                sort_key TEXT NOT NULL UNIQUE,
                payload_json JSONB NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS backup_restore_executions (
                approval_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                safety_backup_id TEXT NOT NULL,
                executed_at TIMESTAMPTZ NOT NULL
            )
            """
        )

    def _apply_append_only_guards(self, connection: Any) -> None:
        connection.execute(
            """
            CREATE OR REPLACE FUNCTION reject_append_only_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
            END;
            $$
            """
        )
        for table in ("audit_logs", "domain_events"):
            connection.execute(f"DROP TRIGGER IF EXISTS {table}_no_update ON {table}")
            connection.execute(f"DROP TRIGGER IF EXISTS {table}_no_delete ON {table}")
            connection.execute(
                f"CREATE TRIGGER {table}_no_update BEFORE UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()"
            )
            connection.execute(
                f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()"
            )

    def _apply_pgvector_schema(self, connection: Any) -> None:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                doc_id TEXT PRIMARY KEY REFERENCES knowledge_docs(record_id) ON DELETE CASCADE,
                embedding vector(1536) NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS knowledge_embeddings_cosine_idx
            ON knowledge_embeddings USING hnsw (embedding vector_cosine_ops)
            """
        )

    def _record_migration(
        self, connection: Any, migration_id: str, version: int, description: str
    ) -> None:
        connection.execute(
            "INSERT INTO schema_migrations (migration_id, version, description, applied_at) "
            "VALUES (%s, %s, %s, %s)",
            (migration_id, version, description, datetime.now(timezone.utc)),
        )

    def schema_version(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
            return int(row[0])

    def list_schema_migrations(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT migration_id, version, description, applied_at "
                "FROM schema_migrations ORDER BY version"
            ).fetchall()
        return [
            {
                "migration_id": row[0],
                "version": row[1],
                "description": row[2],
                "applied_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
            }
            for row in rows
        ]

    def audit_append_only_guards_enabled(self) -> bool:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT tgname FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgrelid = 'audit_logs'::regclass "
                "AND tgname IN ('audit_logs_no_update', 'audit_logs_no_delete')"
            ).fetchall()
        return {row[0] for row in rows} == {"audit_logs_no_update", "audit_logs_no_delete"}

    def _load(self, kind: str) -> list[Any]:
        spec = _SPECS[kind]
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {spec.table} ORDER BY sort_key, record_id"
            ).fetchall()
        return [spec.decoder(_plain_payload(row[0])) for row in rows]

    def _save(self, kind: str, value: Any) -> None:
        with self._connect() as connection:
            self._save_on(connection, kind, value)

    def _save_on(self, connection: Any, kind: str, value: Any) -> None:
        spec = _SPECS[kind]
        payload = to_plain(value)
        record_id = str(getattr(value, spec.id_attr))
        sort_value = getattr(value, spec.sort_attr)
        sort_key = _sort_key(sort_value)
        conflict_action = "DO NOTHING" if spec.append_only else (
            "DO UPDATE SET sort_key = EXCLUDED.sort_key, payload_json = EXCLUDED.payload_json"
        )
        connection.execute(
            f"INSERT INTO {spec.table} (record_id, sort_key, payload_json) "
            f"VALUES (%s, %s, %s::jsonb) ON CONFLICT(record_id) {conflict_action}",
            (record_id, sort_key, _json(payload)),
        )

    def _save_budget_policy_on(self, connection: Any, policy: Any) -> None:
        connection.execute(
            "INSERT INTO budget_policies (record_id, sort_key, payload_json) "
            "VALUES (%s, 'active', %s::jsonb) ON CONFLICT(sort_key) DO UPDATE SET "
            "record_id = EXCLUDED.record_id, payload_json = EXCLUDED.payload_json",
            (policy.policy_id, _json(to_plain(policy))),
        )

    def load_users(self): return self._load("users")
    def load_tasks(self): return self._load("tasks")
    def load_approvals(self): return self._load("approvals")
    def load_audit_events(self): return self._load("audit_events")
    def load_memory(self): return self._load("memory_records")
    def load_knowledge(self): return self._load("knowledge_docs")
    def load_evaluations(self): return self._load("evaluations")
    def load_agents(self): return self._load("agents")
    def load_skills(self): return self._load("skills")
    def load_tools(self): return self._load("tools")
    def load_tool_runs(self): return self._load("tool_runs")
    def load_skill_runs(self): return self._load("skill_runs")
    def load_workflow_runs(self): return self._load("workflow_runs")
    def load_workflow_steps(self): return self._load("workflow_steps")
    def load_model_usage(self): return self._load("model_usage")
    def load_cost_logs(self): return self._load("cost_logs")
    def load_incidents(self): return self._load("incidents")
    def load_skill_proposals(self): return self._load("skill_proposals")
    def load_agent_proposals(self): return self._load("agent_proposals")
    def load_improvement_proposals(self): return self._load("improvement_proposals")
    def load_github_absorptions(self): return self._load("github_absorptions")
    def load_backups(self): return self._load("backups")
    def load_agent_messages(self): return self._load("agent_messages")
    def load_agent_meetings(self): return self._load("agent_meetings")
    def load_task_handoffs(self): return self._load("task_handoffs")
    def load_agent_broadcasts(self): return self._load("agent_broadcasts")
    def load_agent_conflicts(self): return self._load("agent_conflicts")
    def load_task_reviews(self): return self._load("task_reviews")
    def load_strategic_goals(self): return self._load("strategic_goals")
    def load_domain_events(self): return self._load("domain_events")
    def load_scheduled_jobs(self): return self._load("scheduled_jobs")
    def load_scheduled_executions(self): return self._load("scheduled_executions")

    def load_budget_policy(self):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM budget_policies WHERE sort_key = 'active'"
            ).fetchone()
        return codecs._budget_policy_from_plain(_plain_payload(row[0])) if row else None

    def save_user(self, value): self._save("users", value)
    def save_task(self, value): self._save("tasks", value)
    def save_approval(self, value): self._save("approvals", value)
    def append_audit_event(self, value): self._save("audit_events", value)
    def save_memory(self, value): self._save("memory_records", value)
    def save_knowledge(self, value): self._save("knowledge_docs", value)
    def save_evaluation(self, value): self._save("evaluations", value)
    def save_agent(self, value): self._save("agents", value)
    def save_skill(self, value): self._save("skills", value)
    def save_tool(self, value): self._save("tools", value)
    def save_tool_run(self, value): self._save("tool_runs", value)
    def save_skill_run(self, value): self._save("skill_runs", value)
    def save_workflow_run(self, value): self._save("workflow_runs", value)
    def save_workflow_step(self, value): self._save("workflow_steps", value)
    def save_model_usage(self, value): self._save("model_usage", value)
    def save_cost_log(self, value): self._save("cost_logs", value)
    def save_incident(self, value): self._save("incidents", value)
    def save_skill_proposal(self, value): self._save("skill_proposals", value)
    def save_agent_proposal(self, value): self._save("agent_proposals", value)
    def save_improvement_proposal(self, value): self._save("improvement_proposals", value)
    def save_github_absorption(self, value): self._save("github_absorptions", value)
    def save_backup(self, value): self._save("backups", value)
    def save_agent_message(self, value): self._save("agent_messages", value)
    def save_agent_meeting(self, value): self._save("agent_meetings", value)
    def save_task_handoff(self, value): self._save("task_handoffs", value)
    def save_agent_broadcast(self, value): self._save("agent_broadcasts", value)
    def save_agent_conflict(self, value): self._save("agent_conflicts", value)
    def save_task_review(self, value): self._save("task_reviews", value)
    def save_strategic_goal(self, value): self._save("strategic_goals", value)
    def save_domain_event(self, value): self._save("domain_events", value)
    def save_scheduled_job(self, value): self._save("scheduled_jobs", value)
    def save_scheduled_execution(self, value): self._save("scheduled_executions", value)

    def save_budget_policy(self, policy: Any) -> None:
        with self._connect() as connection:
            self._save_budget_policy_on(connection, policy)

    def sync_state(self, **state: Any) -> None:
        missing = set(_SPECS) - set(state)
        if missing:
            raise ValueError(f"sync_state is missing collections: {', '.join(sorted(missing))}")
        with self._connect() as connection:
            for kind in _SPECS:
                for value in state[kind]:
                    self._save_on(connection, kind, value)
            self._save_budget_policy_on(connection, state["budget_policy"])

    def restore_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        approval_id: str,
        backup_id: str,
        actor_id: str,
        safety_backup_id: str,
    ) -> dict[str, int]:
        prepared: dict[str, list[Any]] = {}
        for snapshot_key, kind in _RESTORE_COLLECTIONS.items():
            records = snapshot.get(
                snapshot_key,
                [] if snapshot_key in _OPTIONAL_LEGACY_COLLECTIONS else None,
            )
            if not isinstance(records, list):
                raise ValueError(f"backup snapshot field {snapshot_key} must be a list")
            spec = _SPECS[kind]
            decoded = []
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError(
                        f"backup snapshot field {snapshot_key} contains a non-object record"
                    )
                if spec.id_attr not in record:
                    raise ValueError(
                        f"backup snapshot field {snapshot_key} record is missing {spec.id_attr}"
                    )
                decoded.append(spec.decoder(record))
            prepared[kind] = decoded

        budget_payload = snapshot.get("budget_policy")
        if not isinstance(budget_payload, dict) or "policy_id" not in budget_payload:
            raise ValueError("backup snapshot field budget_policy must contain a policy_id")
        budget_policy = codecs._budget_policy_from_plain(budget_payload)

        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO backup_restore_executions "
                    "(approval_id, backup_id, actor_id, safety_backup_id, executed_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        approval_id,
                        backup_id,
                        actor_id,
                        safety_backup_id,
                        datetime.now(timezone.utc),
                    ),
                )
                for kind, values in prepared.items():
                    connection.execute(f"DELETE FROM {_SPECS[kind].table}")
                    for value in values:
                        self._save_on(connection, kind, value)
                connection.execute("DELETE FROM budget_policies")
                self._save_budget_policy_on(connection, budget_policy)
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505" and "backup_restore_executions" in str(exc):
                raise ValueError("backup restore approval has already been used") from exc
            raise

        counts = {
            snapshot_key: len(prepared[kind])
            for snapshot_key, kind in _RESTORE_COLLECTIONS.items()
        }
        counts["budget_policy"] = 1
        return counts

    def upsert_knowledge_embedding(
        self,
        doc_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if len(embedding) != 1536:
            raise ValueError("knowledge embeddings must contain exactly 1536 dimensions")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO knowledge_embeddings (doc_id, embedding, metadata, updated_at) "
                "VALUES (%s, %s::vector, %s::jsonb, NOW()) ON CONFLICT(doc_id) DO UPDATE SET "
                "embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata, updated_at = NOW()",
                (doc_id, _vector(embedding), _json(metadata or {})),
            )

    def list_knowledge_embedding_doc_ids(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT doc_id FROM knowledge_embeddings").fetchall()
        return {str(row[0]) for row in rows}

    def search_knowledge_embeddings(
        self, embedding: list[float], *, limit: int = 10
    ) -> list[dict[str, Any]]:
        if len(embedding) != 1536:
            raise ValueError("knowledge embeddings must contain exactly 1536 dimensions")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT doc_id, 1 - (embedding <=> %s::vector) AS score, metadata "
                "FROM knowledge_embeddings ORDER BY embedding <=> %s::vector LIMIT %s",
                (_vector(embedding), _vector(embedding), limit),
            ).fetchall()
        return [
            {"doc_id": row[0], "score": float(row[1]), "metadata": _plain_payload(row[2])}
            for row in rows
        ]


def _sort_key(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, int):
        return f"{value:020d}"
    return str(value)


def _plain_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _vector(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"
