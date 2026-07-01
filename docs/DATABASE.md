# DATABASE

## V1 Tables

- users
- roles
- permissions
- agents
- agent_versions
- agent_permissions
- agent_messages
- agent_meetings
- skills
- skill_versions
- skill_permissions
- skill_requests
- skill_runs
- skill_test_results
- workflows
- workflow_runs
- workflow_steps
- tasks
- task_states
- events
- scheduled_jobs
- scheduled_executions
- approvals
- approval_logs
- audit_logs
- traces
- risk_logs
- quality_checks
- evaluations
- memories
- knowledge_docs
- tools
- tool_permissions
- tool_runs
- model_usage
- cost_logs
- budget_policies
- incidents
- backups
- schema_migrations
- backup_restore_executions

## Storage Rules

- Audit logs are append-only.
- Schema migrations are recorded once and the SQLite `user_version` reflects the current schema version.
- Approval decisions are immutable after final decision.
- Risk logs are retained with task context.
- Agent and Skill changes create new versions.
- Rollback plans are stored before important changes.

## Current Local Persistence

The first persistence adapter uses Python standard-library SQLite:

```text
backend/app/persistence/sqlite_store.py
```

It currently stores:

- users
- agents
- skills
- tasks
- approvals
- audit_logs
- memories
- knowledge_docs
- evaluations
- tools
- skill_runs
- tool_runs
- workflow_runs
- workflow_steps
- strategic_goals
- model_usage
- cost_logs
- budget_policies
- incidents
- backups
- agent_messages
- agent_meetings
- task_handoffs
- agent_broadcasts
- agent_conflicts
- task_reviews
- skill_proposals
- agent_proposals
- improvement_proposals
- github_absorptions
- schema_migrations
- domain_events
- scheduled_jobs
- scheduled_executions
- backup_restore_executions

Schema migration `0006_skill_runtime` adds durable Skill Run lifecycle records, including input, result or error, risk, approval linkage, and completion timestamps.

Schema migration `0007_chat_sessions` adds durable Human Root conversations. A session stores bounded display messages, model usage/cost metadata, and governed action-card state so pending confirmation can recover after a process restart. Legacy browser imports never restore executable action parameters.

User records store PBKDF2 password hashes, not plaintext passwords.

SQLite initialization records the baseline migration `0001_initial_local_state`, applies migrations through `0007_chat_sessions`, and sets `PRAGMA user_version` to `7`. The migrations protect append-only history, add the unique restore-approval ledger, durable schedules and events, formal Agent and Skill catalogs, Skill Run lifecycle records, and server-owned chat sessions. PostgreSQL records the corresponding chat-session migration as schema version `4`. The `GET /database/schema` API exposes the active backend, schema version, and applied migration ledger for operational checks.

Skill and Agent proposal payloads include approval state plus sandbox status, notes, and sandbox timestamp. The first implementation stores proposal state as JSON so the future migration layer can promote fields into relational columns when needed.

Improvement proposal payloads link back to task reviews and store target type, rationale, lessons, follow-up actions, approval state, sandbox state, and registration state.

GitHub absorption payloads store repository URL, README excerpt, license and maintenance signals, external-content findings, security findings, recommended capabilities, approval state, sandbox state, and registered Knowledge document ID.

Strategic goal payloads store the owner Agent, target metric, target/current values, status, and links to tasks, reviews, and improvement proposals.

Backup payloads store state snapshots, checksums, and controlled rollback plans. Approved restores replace restorable business tables in one transaction while preserving users, approvals, append-only audit logs, incidents, backups, and migration history.

Agent and Skill catalog payloads preserve permissions, forbidden actions, cross-catalog references, schemas, risk, approval, version, and enabled state. Runtime registration validates references before the catalog entry is accepted or persisted.

Agent communication payloads store Agent-to-Agent messages, coordination meeting records, task handoff records, internal broadcasts, and conflict arbitration records. They are included in dashboard summaries and backup snapshots.

Scheduled job payloads store action, timing, recurrence, run limits, counters, and latest errors. Scheduled execution records and domain events are retained as operational history; backup restore changes job state but does not erase that history.

Task review payloads store retrospective outcomes, quality scores, lessons, and follow-up actions. Recording a review also creates review memory, a knowledge document, and an audit event.

## PostgreSQL And pgvector

The production adapter lives at `backend/app/persistence/postgres_store.py`. It implements the same application persistence contract with PostgreSQL JSONB records and three migrations:

1. State tables, indexes, and the one-time restore approval ledger.
2. PostgreSQL append-only triggers for audit logs and domain events.
3. The `vector` extension plus 1536-dimensional knowledge embeddings and an HNSW cosine index.

When `AI_COMPANY_OS_EMBEDDING_PROVIDER=openai`, every newly persisted Knowledge document is embedded after its `knowledge_docs` row exists and then upserted into `knowledge_embeddings`. Semantic query vectors use the same 1536-dimensional contract. Model usage, cost, Audit, and failure Incidents are persisted through the normal application state transaction path; lexical search remains the fallback.

The application selects this backend when `AI_COMPANY_OS_DATABASE_URL` or `DATABASE_URL` contains a PostgreSQL URL. The SQLite path and PostgreSQL URL are mutually exclusive.

Use this environment variable to enable SQLite for the API:

```text
AI_COMPANY_OS_SQLITE_PATH=E:\1\data\company_os.db
```

Use this environment variable for PostgreSQL:

```text
AI_COMPANY_OS_DATABASE_URL=postgresql://user:password@localhost:5432/ai_company_os
```
