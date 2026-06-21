# BACKUPS

## Purpose

Backups capture the current AI Company OS state before important changes. Verified snapshots can be restored to SQLite only after a matching high-risk approval from Human Root.

## Current Snapshot Contents

- tasks
- approvals
- audit logs
- memory and knowledge records
- evaluations
- formal Agent and Skill catalogs
- tools and tool runs
- workflow runs and steps
- model usage and cost logs
- active budget policy
- incidents
- Skill, Agent, improvement, and GitHub absorption proposals
- strategic goals, Agent communication, handoffs, conflicts, and task reviews
- scheduled job definitions and current schedule state

## API

```text
GET /backups
POST /backups
POST /backups/{backup_id}/verify
POST /backups/{backup_id}/restore-request
POST /backups/{backup_id}/restore
```

`POST /backups` requires a reason and records the actor. It writes a `backup_created` audit event. Created backups include a deterministic SHA-256 checksum over the canonical snapshot payload.

`POST /backups/{backup_id}/verify` recomputes the snapshot checksum and writes a `backup_verified` audit event. It returns `verified` when the stored checksum matches, `checksum_mismatch` when the snapshot payload has changed, and `missing_checksum` for legacy backup records created before checksum support.

`POST /backups/{backup_id}/restore-request` verifies backup integrity first. Verified backups create a high-risk `restore_backup` approval request for Human Root review. Mismatched or legacy checksum-missing backups are blocked, audited, and surfaced as incidents.

`POST /backups/{backup_id}/restore` consumes a matching approved restore request. It verifies the checksum again, requires both execution and approval by `human_root`, rejects approval replay, creates an automatic pre-restore checkpoint, and applies the snapshot in one SQLite transaction.

## Restore Policy

Restore replaces restorable business state such as Agent and Skill catalogs, tasks, memory, knowledge, evaluations, goals, tools, workflow traces, usage records, proposals, communication records, and scheduled jobs. It deliberately preserves users, approvals, append-only audit logs, domain events, schedule execution history, incidents, backups, and the schema migration ledger. Failed integrity checks do not mutate live state and create an audit event plus incident.

Restore execution is supported with SQLite and PostgreSQL persistence. In-memory mode can create and inspect snapshots but cannot apply them durably.
