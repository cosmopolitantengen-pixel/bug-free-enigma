# AI Company OS

AI Company OS is a general-purpose company operating system for agentic work. It turns company roles into Agents, role capabilities into Skills, business procedures into Workflows, and risky actions into permissioned, auditable approval flows.

The first version focuses on the operating foundation:

- Human Root always keeps the highest authority.
- Agents, Skills, and Workflows are registered before use.
- Tools are registered before use and run through Agent permission, risk, approval, and audit checks.
- Model calls go through a gateway that records usage and audit events.
- Budget guardrails check model calls before usage and cost are recorded.
- Blocked and high-risk operational failures create incidents for human follow-up.
- Human Root can create verified state backups and apply approval-gated SQLite restores with automatic pre-restore checkpoints.
- Risk, permissions, approvals, and audit logs exist from day one.
- Missing Skills and missing Agents become controlled proposals, not uncontrolled self-modification.
- Memory and Knowledge Base receive completed work so the system can improve over time.
- Durable schedules can create or run internal tasks and publish append-only domain events.

## Current Scope

This repository currently contains:

- Project planning docs in `docs/`
- A no-dependency Python core in `backend/app/`
- Unit tests in `backend/tests/`

The core remains framework-light so the safety model can be tested independently. A thin FastAPI layer now exposes the first API routes over that core; persistence, Next.js, PostgreSQL, Redis, and pgvector come later.

## Quick Check

```powershell
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m unittest discover -s backend/tests
```

## Local API

The FastAPI app is exposed as `app.main:app`.

```powershell
cd backend
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m app.main
```

To enable local SQLite persistence for the API, set:

```powershell
$env:AI_COMPANY_OS_SQLITE_PATH='E:\1\data\company_os.db'
```

The current SQLite adapter persists tasks, approvals, audit logs, memory records, knowledge docs, evaluations, tools, tool runs, workflow traces, model usage, cost logs, incidents, backups, and capability proposals.
It also persists local users with PBKDF2 password hashes for the development auth flow.

## Local Dashboard

A dependency-free dashboard shell is available at:

```text
apps/web_dashboard/index.html
```

Start the backend, open that file in a browser, and keep the API Base field pointed at `http://127.0.0.1:8000`.

## First Build Direction

1. Keep the core rules deterministic and well tested.
2. Add FastAPI endpoints over the core services.
3. Add SQLite/PostgreSQL persistence.
4. Add the dashboard once the backend contracts are stable.
5. Add real model calls only after audit, risk, approval, and permission gates are already in place.
