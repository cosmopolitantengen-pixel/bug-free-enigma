# AI Company OS

AI Company OS is a general-purpose company operating system for agentic work. It turns company roles into Agents, role capabilities into Skills, business procedures into Workflows, and risky actions into permissioned, auditable approval flows.

The first version focuses on the operating foundation:

- Human Root always keeps the highest authority.
- Agents, Skills, and Workflows are registered before use.
- Skill calls use validated inputs and run through Agent authorization, risk, approval, audit, persistence, and evaluation controls.
- Tools are registered before use and run through Agent permission, risk, approval, and audit checks.
- Model calls go through a gateway that records usage and audit events.
- Budget guardrails check model calls before usage and cost are recorded.
- Blocked and high-risk operational failures create incidents for human follow-up.
- Human Root can create verified state backups and apply approval-gated durable restores with automatic pre-restore checkpoints.
- Risk, permissions, approvals, and audit logs exist from day one.
- Missing Skills and missing Agents become controlled proposals, not uncontrolled self-modification.
- The V1 catalog boots with 17 scoped Agent roles and 18 registered Skills; approved catalog additions persist across restarts.
- All 10 required V1 Workflows have native controlled runners, including Tool Call and GitHub project analysis with persisted approval continuation.
- Native Workflow steps dispatch through the durable Skill Runtime, so Skill authorization, failure, approval, audit, and evaluation state remain inspectable alongside Workflow traces.
- Memory and Knowledge Base receive completed work so the system can improve over time.
- Durable schedules can create or run internal tasks and publish append-only domain events.

## Current Scope

This repository currently contains:

- Project planning docs in `docs/`
- A no-dependency Python core in `backend/app/`
- Unit tests in `backend/tests/`
- A Next.js and TypeScript operations console in `apps/web/`

The core remains framework-light so the safety model can be tested independently. FastAPI and SQLite provide the complete deterministic V1 baseline. PostgreSQL/pgvector persistence, Redis/RQ scheduler workers, backend and web containers, the Next.js operations console, and service-level CI coverage are also present. Embedding-provider wiring and live provider/connector adapters remain production-expansion work; see `docs/V1_COMPLETION_AUDIT.md`.

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

The current SQLite adapter persists Agent and Skill catalogs, Skill Runs, tasks, approvals, audit logs, memory records, knowledge docs, evaluations, tools, Tool Runs, workflow traces, model usage, cost logs, incidents, backups, and capability proposals.
It also persists local users with PBKDF2 password hashes for the development auth flow.

For the PostgreSQL/pgvector stack, create `.env` from `.env.example`, replace the password, and run:

```powershell
docker compose --env-file .env up --build
```

## Local Operations Console

Start the API, then run the Next.js console:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. The console defaults to `http://127.0.0.1:8000` and lets Human Root run Workflows, decide approvals, manage schedules and Incidents, inspect catalogs, and review system integrity. Set `NEXT_PUBLIC_API_BASE` before building when the API is hosted elsewhere.

The dependency-free dashboard is retained as a fallback at:

```text
apps/web_dashboard/index.html
```

Start the backend, open that file in a browser, and keep the API Base field pointed at `http://127.0.0.1:8000`.

## Next Production Direction

1. Keep the core rules deterministic and well tested.
2. Add queue failure alerts and operational worker metrics.
3. Expand browser-level end-to-end coverage for the Next.js console.
4. Wire live embedding and model providers through the existing gateways.
5. Add real connectors only through the existing audit, risk, approval, and permission gates.
