# AI Company OS

AI Company OS is a general-purpose company operating system for agentic work. It turns company roles into Agents, role capabilities into Skills, business procedures into Workflows, and risky actions into permissioned, auditable approval flows.

The first version focuses on the operating foundation:

- Human Root always keeps the highest authority.
- Agents, Skills, and Workflows are registered before use.
- Skill calls use validated inputs and run through Agent authorization, risk, approval, audit, persistence, and evaluation controls.
- Tools are registered before use and run through Agent permission, risk, approval, and audit checks; workspace search, exact patching, allowlisted commands, and read-only Git inspection now use this boundary.
- Model calls go through a gateway that records usage and audit events.
- Governed Agent Runs can reason over a bounded tool catalog for up to eight steps, automatically continue low-risk reads, and pause patches or commands for Human Root approval.
- Native OpenAI and DeepSeek streams deliver conversation text and persisted Agent Run progress through server-sent events while preserving final usage, cost, fallback, and audit records.
- Budget guardrails check model calls before usage and cost are recorded.
- Blocked and high-risk operational failures create incidents for human follow-up, with optional outbound alert delivery.
- Human Root can create verified state backups and apply approval-gated durable restores with automatic pre-restore checkpoints.
- Risk, permissions, approvals, and audit logs exist from day one.
- Missing Skills and missing Agents become controlled proposals, not uncontrolled self-modification.
- The catalog boots with 18 scoped Agent roles, including a dedicated Workspace Agent, and 18 registered Skills; approved catalog additions persist across restarts.
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

The core remains framework-light so the safety model can be tested independently. FastAPI and SQLite provide the complete deterministic V1 baseline. PostgreSQL/pgvector persistence, Redis/RQ scheduler workers with queue health reporting, backend and web containers, the Next.js operations console, optional production HTTP bearer auth, optional Incident alert webhooks, Incident runbook matching, deployment readiness checks, controlled GitHub metadata import, native OpenAI/DeepSeek generation providers, OpenAI embeddings, explicit model fallback routing, service-level CI coverage, and browser E2E console smoke coverage are also present. Live connector adapters remain production-expansion work; see `docs/V1_COMPLETION_AUDIT.md`.

## Quick Check

```powershell
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m unittest discover -s backend/tests
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' scripts\release_gate.py
```

## Local API

The FastAPI app is exposed as `app.main:app`.

```powershell
cd backend
& 'C:\Users\weiis\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

To enable local SQLite persistence for the API, set:

```powershell
$env:AI_COMPANY_OS_SQLITE_PATH='E:\1\data\company_os.db'
```

The current SQLite adapter persists Agent and Skill catalogs, Skill Runs, tasks, approvals, audit logs, memory records, knowledge docs, evaluations, tools, Tool Runs, workflow traces, model usage, cost logs, incidents, backups, and capability proposals.
It also persists local users with PBKDF2 password hashes and expiring bearer sessions. For local development, HTTP auth is disabled by default. For a protected deployment, set `AI_COMPANY_OS_AUTH_REQUIRED=true` and provide `AI_COMPANY_OS_API_TOKEN` or `AI_COMPANY_OS_API_TOKEN_SHA256`; only `/health` and `/auth/login` stay public.

For the PostgreSQL/pgvector stack, create `.env` from `.env.example`, replace the password, and run:

```powershell
docker compose --env-file .env up --build
```

Live providers are opt-in. Generation supports native OpenAI Responses and DeepSeek Chat Completions adapters, per-request provider/model selection, explicit provider fallback, and provider-specific DeepSeek V4 pricing. Set `DEEPSEEK_API_KEY` with `AI_COMPANY_OS_MODEL_PROVIDER=deepseek`, or set `OPENAI_API_KEY` with `AI_COMPANY_OS_MODEL_PROVIDER=openai`. OpenAI remains the embedding provider for 1536-dimensional pgvector Knowledge indexing. Without live-provider settings, deterministic generation and lexical Knowledge search remain fully available.

## Local Operations Console

Start the API, then run the Next.js console:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The Chinese console defaults to `http://127.0.0.1:8000` and opens on a multi-turn chat workspace with server-persisted conversation history, native token streaming, provider/model selection, routing feedback, token usage, and estimated cost. Existing browser-only transcripts are imported once as plain text; cached action parameters are deliberately discarded. The default automatic mode keeps exploratory discussion conversational, but explicit action language creates an audited Workflow proposal that Human Root must confirm before any task is created or executed. Explicit goal-setting language creates an audited Strategic Goal card; the Goal is persisted only after Human Root confirmation and then appears in Overview. Rules handle known requests without a model call; ambiguous operational language can use the selected non-local model as a bounded intent classifier whose output cannot supply Tool IDs, commands, paths, or approval decisions. The dedicated Agent mode creates a governed proposal, then lets the selected non-local model choose one validated step at a time from fixed read, Git, type-check, test, and exact-patch capabilities. Low-risk reads continue automatically; patches and commands pause for Human Root, show bounded approval evidence, and resume the same persisted run after approval or backend restart. The UI receives persisted Agent Run step snapshots as they change. Workspace excerpts used for reasoning may be sent to the selected provider only after the initial Agent Run confirmation. Human Root can reject or approve without leaving the conversation, and the complete transcript, action cards, goal cards, execution trace, and pending approvals survive browser and backend restarts. Human Root can also use dedicated views to manage approvals, schedules and Incidents, inspect catalogs, and review system integrity. Set `NEXT_PUBLIC_API_BASE` before building when the API is hosted elsewhere. Provider API keys stay in backend environment variables or secret files; they are never entered in the chat UI. When API auth is enabled, enter only the AI Company OS bearer token on the System page; it is stored in the browser and sent as an `Authorization` header. CI runs Playwright browser E2E for the console after type-check and production build. Locally, run `npm run e2e` from `apps/web` after installing the Playwright Chromium browser.

On Windows, `powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1` starts both services with hidden background processes and durable SQLite state at `data/company_os.db`. The SQLite path is scoped to the launched services, so backend tests remain isolated from live local data.

The dependency-free dashboard is retained as a fallback at:

```text
apps/web_dashboard/index.html
```

Start the backend, open that file in a browser, and keep the API Base field pointed at `http://127.0.0.1:8000`.

## Next Production Direction

1. Keep the core rules deterministic and well tested.
2. Add managed secret backends and production identity provider integration.
3. Add managed alert routing and escalation for queue/worker failures.
4. Broaden browser-level provider/restore failure coverage and release automation for the Next.js console.
5. Add real connectors only through the existing audit, risk, approval, and permission gates.
