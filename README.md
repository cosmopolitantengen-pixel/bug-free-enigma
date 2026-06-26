# AI Company OS

AI Company OS is a general-purpose company operating system for agentic work. It turns company roles into Agents, role capabilities into Skills, business procedures into Workflows, and risky actions into permissioned, auditable approval flows.

The first version focuses on the operating foundation:

- Human Root always keeps the highest authority.
- Agents, Skills, and Workflows are registered before use.
- Skill calls use validated inputs and run through Agent authorization, risk, approval, audit, persistence, and evaluation controls.
- Tools are registered before use and run through Agent permission, risk, approval, and audit checks.
- Model calls go through a gateway that records usage and audit events.
- Budget guardrails check model calls before usage and cost are recorded.
- Blocked and high-risk operational failures create incidents for human follow-up, with optional outbound alert delivery.
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

The core remains framework-light so the safety model can be tested independently. FastAPI and SQLite provide the complete deterministic V1 baseline. PostgreSQL/pgvector persistence, Redis/RQ scheduler workers with queue health reporting, backend and web containers, the Next.js operations console, optional production HTTP bearer auth, optional Incident alert webhooks, Incident runbook matching, deployment readiness checks, controlled GitHub metadata import, configurable OpenAI model and embedding providers, service-level CI coverage, and browser E2E console smoke coverage are also present. Live connector adapters remain production-expansion work; see `docs/V1_COMPLETION_AUDIT.md`.

## Quick Check

```powershell
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m unittest discover -s backend/tests
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' scripts\release_gate.py
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
It also persists local users with PBKDF2 password hashes. For local development, HTTP auth is disabled by default. For a protected deployment, set `AI_COMPANY_OS_AUTH_REQUIRED=true` and provide `AI_COMPANY_OS_API_TOKEN` or `AI_COMPANY_OS_API_TOKEN_SHA256`; only `/health` and `/auth/login` stay public.

For the PostgreSQL/pgvector stack, create `.env` from `.env.example`, replace the password, and run:

```powershell
docker compose --env-file .env up --build
```

Live providers are opt-in. Set `OPENAI_API_KEY`, `AI_COMPANY_OS_MODEL_PROVIDER=openai`, and `AI_COMPANY_OS_EMBEDDING_PROVIDER=openai` in `.env` to enable Responses API generation plus 1536-dimensional pgvector Knowledge indexing and semantic search. Without those settings, deterministic generation and lexical Knowledge search remain fully available.

## Local Operations Console

Start the API, then run the Next.js console:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. The console defaults to `http://127.0.0.1:8000` and lets Human Root run Workflows, decide approvals, manage schedules and Incidents, inspect catalogs, and review system integrity. Set `NEXT_PUBLIC_API_BASE` before building when the API is hosted elsewhere. When API auth is enabled, enter the bearer token on the System page; it is stored in the browser and sent as an `Authorization` header. CI runs Playwright browser E2E for the console after type-check and production build. Locally, run `npm run e2e` from `apps/web` after installing the Playwright Chromium browser.

The dependency-free dashboard is retained as a fallback at:

```text
apps/web_dashboard/index.html
```

Start the backend, open that file in a browser, and keep the API Base field pointed at `http://127.0.0.1:8000`.

## Next Production Direction

1. Keep the core rules deterministic and well tested.
2. Add managed secret backends and production identity provider integration.
3. Add managed alert routing and escalation for queue/worker failures.
4. Broaden browser-level failure-path coverage and release automation for the Next.js console.
5. Add real connectors only through the existing audit, risk, approval, and permission gates.
