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
- tasks
- approvals
- audit_logs
- memories
- knowledge_docs
- evaluations
- tools
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

User records store PBKDF2 password hashes, not plaintext passwords.

SQLite initialization records the baseline migration `0001_initial_local_state`, applies `0002_audit_append_only_guards`, and sets `PRAGMA user_version` to `2`. The second migration creates SQLite triggers that reject `UPDATE` and `DELETE` statements on `audit_logs`, so audit append-only behavior is enforced below the application service. The `GET /database/schema` API exposes the active backend, schema version, and applied migration ledger for operational checks.

Skill and Agent proposal payloads include approval state plus sandbox status, notes, and sandbox timestamp. The first implementation stores proposal state as JSON so the future migration layer can promote fields into relational columns when needed.

Improvement proposal payloads link back to task reviews and store target type, rationale, lessons, follow-up actions, approval state, sandbox state, and registration state.

GitHub absorption payloads store repository URL, README excerpt, license and maintenance signals, external-content findings, security findings, recommended capabilities, approval state, sandbox state, and registered Knowledge document ID.

Strategic goal payloads store the owner Agent, target metric, target/current values, status, and links to tasks, reviews, and improvement proposals.

Backup payloads store state snapshots and manual rollback plans. Automatic restore is not enabled in the first local adapter.

Agent communication payloads store Agent-to-Agent messages, coordination meeting records, task handoff records, internal broadcasts, and conflict arbitration records. They are included in dashboard summaries and backup snapshots.

Task review payloads store retrospective outcomes, quality scores, lessons, and follow-up actions. Recording a review also creates review memory, a knowledge document, and an audit event.

The adapter is intentionally small and can be replaced by SQLAlchemy/PostgreSQL later without changing the core permission, risk, approval, audit, Agent, Skill, and Workflow services.

Use this environment variable to enable SQLite for the API:

```text
AI_COMPANY_OS_SQLITE_PATH=E:\1\data\company_os.db
```
