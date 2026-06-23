# TESTING

## Required Test Areas

- Permission checks
- Approval routing
- Risk blocking
- External-content prompt-injection boundary checks
- Task state machine
- Agent registration
- Skill registration
- V1 Agent/Skill catalog completeness and reference integrity
- Formal Agent/Skill catalog SQLite reload and backup restore
- Skill missing handling
- Agent missing handling
- Proposal sandbox checks before Skill and Agent registration
- Workflow execution
- Complete 10-Workflow V1 catalog registration and definition validation
- Native task-planning Workflow permission/risk/Skill checks, traces, audit, Memory, Evaluation, Incident, API, dashboard, and SQLite reload
- Approval-gated Workflow resume after Human Root approval
- Workflow Run and Workflow Step trace persistence
- Tool registration, controlled tool run requests, approval-gated completion, internal adapter execution, filesystem read boundaries, and adapter failure handling
- Model Gateway usage and cost logging
- OpenAI Responses and Embeddings request/response contracts through mocked HTTP transports
- pgvector Knowledge indexing orchestration, semantic search, Root-only reindex, and lexical fallback
- Budget Guard allowed and blocked model calls
- Root-managed Budget Policy updates and SQLite reload
- Incident creation, acknowledgement, resolution, and persistence
- Optional outbound Incident alert delivery, webhook configuration validation, audit success/failure records, and secret-safe status reporting
- Incident runbook catalog exposure and source-based runbook matching
- Backup creation, snapshot contents, checksum verification, restore approval requests, audit events, tamper detection, and persistence
- Agent message and meeting creation, audit events, dashboard summary, and persistence
- Task handoff permission/risk flow, linked handoff messages, audit events, dashboard summary, and persistence
- Agent broadcast permission/risk flow, filtering, audit events, dashboard summary, and persistence
- Agent conflict opening, filtering, resolution, audit events, dashboard summary, and persistence
- Task review recording, review memory, review knowledge docs, audit events, dashboard summary, and persistence
- Review-driven improvement proposal approval, sandbox, knowledge registration, dashboard summary, and persistence
- GitHub absorption approval, sandbox, knowledge registration, dashboard summary, and persistence
- Strategic goal creation, progress tracking, task/review/improvement linking, dashboard summary, and persistence
- Structured JSON log export, filtering, dashboard summary, and dashboard mount points
- SQLite schema migration ledger, API exposure, and dashboard mount points
- Audit log append-only behavior, including SQLite trigger guards against update and delete
- System integrity API checks, dashboard summary fields, and dashboard mount points
- One-time and recurring scheduler execution, pause/resume/cancel controls, queue health reporting, failure incidents, domain-event filtering, append-only event guards, and SQLite reload
- Memory writes
- Knowledge Base writes
- API smoke tests
- Frontend build checks
- Next.js desktop and mobile browser acceptance checks

## Critical Safety Tests

- AI cannot automatically refund.
- AI cannot delete audit logs.
- AI cannot disable risk control.
- AI cannot modify Root permissions.
- AI cannot execute high-risk tools without approval.
- External writes must enter approval.
- Missing Skills must enter the missing-Skill flow.
- Missing Agents must enter Agent Factory and approval flow.

## Current Test Command

```powershell
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m unittest discover -s backend/tests
```

The suite currently covers:

- Core safety invariants
- FastAPI route contracts
- SQLite reload of tasks, audit logs, memory, and knowledge docs
- Local auth registration, login, duplicate-user rejection, password hashing, and SQLite reload
- Static dashboard mount points and backend dashboard data contract
- Next.js console dependency pins, required operational surfaces, responsive states, type checks, and production build
- Approval request routing for pending and blocked actions
- Approval decision audit events and SQLite persistence
- PostgreSQL migrations, append-only guards, and pgvector round trips when `AI_COMPANY_OS_TEST_POSTGRES_URL` is configured
- Redis/RQ delivery deduplication, queue health reporting, and worker execution when both PostgreSQL and Redis test URLs are configured
- Skill and Agent proposal persistence plus approval-gated registration
- Complete 17-Agent/18-Skill V1 bootstrap catalogs, invalid reference rejection, audited formal registration, SQLite reload, and backup rollback
- Skill and Agent proposal sandbox gating, audit events, dashboard controls, and SQLite reload
- Evaluation record creation, API exposure, dashboard summary, and SQLite reload
- Tool registry bootstrap, low-risk internal adapter output, approval-gated Tool Run completion, knowledge/audit/database/filesystem adapters, failed adapter input, filesystem path boundary checks, disallowed/disabled Tool Run blocking, API exposure, dashboard mount points, and SQLite reload
- Filesystem read external-content inspection for clean and instruction-risk source files
- Workflow Run and Workflow Step creation, API exposure, dashboard summary, dashboard mount points, and SQLite reload
- V1 Workflow catalog API/detail exposure, all 10 common native entrypoints, and dashboard catalog rendering
- Native Tool Call completion, adapter failure, authorization block, approval/rejection, post-approval revalidation, and SQLite restart continuation
- Approval-gated document Workflow resume, non-waiting resume rejection, and dashboard resume controls
- Model Gateway deterministic generation, model usage API exposure, dashboard summary, dashboard mount points, audit event creation, and SQLite reload
- Budget Guard cost recording, over-budget blocking, dashboard summary, API exposure, and SQLite reload
- Budget Policy update auditing, non-root blocking, dashboard mount points, and SQLite reload
- Incident creation from blocked actions, API acknowledge/resolve flow, dashboard summary counts, dashboard mount points, audit events, and SQLite reload
- Optional Incident alert delivery through a mocked webhook transport, failed delivery audit records, configuration validation, and `/alerts/status`
- Operational runbook matching for blocked safety controls and failed schedules, plus `/runbooks`
- Backup creation, state snapshot contents, checksum verification, restore approval requests, approved transactional restore, pre-restore safety checkpoints, approval replay prevention, execution-time tamper detection, dashboard controls, audit events, and SQLite reload
- Agent communication API routes, dashboard mount points, audit events, and SQLite reload
- Task handoff API routes, linked messages, dashboard mount points, audit events, and SQLite reload
- Agent broadcast API routes, filters, dashboard mount points, audit events, and SQLite reload
- Agent conflict API routes, filters, resolution, dashboard mount points, audit events, and SQLite reload
- Task review API routes, review memory/knowledge generation, dashboard mount points, audit events, and SQLite reload
- Improvement proposal API routes, approval gating, sandbox gating, dashboard mount points, knowledge registration, audit events, and SQLite reload
- GitHub absorption API routes, approval gating, sandbox gating, dashboard mount points, knowledge registration, audit events, unsafe repository rejection, and SQLite reload
- Strategic goal API routes, progress auto-completion, dashboard mount points, audit events, and SQLite reload
- Structured JSON log API routes, category/level filters, dashboard summary fields, and dashboard mount points
- SQLite migration ledger through `0005_agent_skill_catalogs`, audit append-only trigger migration, `user_version`, `/database/schema`, and dashboard mount points
- System integrity checks for memory mode warnings, SQLite audit guards, backup checksums, and dashboard exposure
- Durable scheduler and event-bus API routes, one-time/recurring timing, controls, queue health reporting, failure incidents, append-only event triggers, dashboard controls, and SQLite reload
