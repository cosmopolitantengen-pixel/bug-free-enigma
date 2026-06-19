# BACKUPS

## Purpose

Backups capture the current AI Company OS state before important changes. They provide a stored reference point and manual rollback plan, but they do not automatically mutate live state.

## Current Snapshot Contents

- tasks
- approvals
- audit logs
- memory and knowledge records
- evaluations
- tools and tool runs
- workflow runs and steps
- model usage and cost logs
- active budget policy
- incidents
- Skill and Agent proposals

## API

```text
GET /backups
POST /backups
POST /backups/{backup_id}/verify
POST /backups/{backup_id}/restore-request
```

`POST /backups` requires a reason and records the actor. It writes a `backup_created` audit event. Created backups include a deterministic SHA-256 checksum over the canonical snapshot payload.

`POST /backups/{backup_id}/verify` recomputes the snapshot checksum and writes a `backup_verified` audit event. It returns `verified` when the stored checksum matches, `checksum_mismatch` when the snapshot payload has changed, and `missing_checksum` for legacy backup records created before checksum support.

`POST /backups/{backup_id}/restore-request` verifies backup integrity first. Verified backups create a high-risk `restore_backup` approval request for Human Root review. Mismatched or legacy checksum-missing backups are blocked, audited, and surfaced as incidents.

## Restore Policy

Automatic restore is intentionally disabled in the first implementation. The current restore flow stops at an approval-gated restore request; applying a backup snapshot to live state remains a future high-impact mutation that must preserve audit history and require Human Root approval.
