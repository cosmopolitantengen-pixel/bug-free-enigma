# DASHBOARD

## Current Dashboard

The primary Human Root console is a responsive Next.js and TypeScript app:

```text
apps/web/
```

Its Chinese-language seven-view operations console opens on a multi-turn chat workspace and also covers overview metrics, Workflow execution and approvals, schedules with Redis/RQ queue health, Agent/Skill/Tool/Workflow catalogs, Incidents with matched runbooks and audit records, and system status including production readiness, persistence/integrity, and alert delivery. Chat sessions persist in the current browser, support explicit provider/model selection, and show actual routing, fallback, token, and cost metadata returned by the governed Model Gateway. It has explicit loading, error, empty, and mobile navigation states, supports a configurable API origin, and is production-built as a standalone container. Playwright browser E2E coverage runs in CI against mocked API responses for desktop and 390 px mobile viewports, including chat generation and reload persistence, readiness visibility, navigation, bearer-token storage, Workflow submission, approval approve/reject decisions, schedule create/pause/resume/cancel controls, Incident response, invalid API-base handling, and auth-required API degradation.

The first dependency-free control panel remains available as a fallback:

```text
apps/web_dashboard/index.html
apps/web_dashboard/styles.css
apps/web_dashboard/app.js
```

It connects to the FastAPI backend through:

```text
GET /dashboard/summary
GET /database/schema
GET /system/integrity
GET /deployment/readiness
GET /events
GET /schedules
GET /scheduler/executions
GET /scheduler/queue-health
GET /goals
GET /agents
GET /skills
GET /tools
GET /tools/runs
GET /workflows
GET /workflow-runs
GET /model-usage
GET /budget/summary
POST /budget/policy
GET /cost-logs
GET /incidents
GET /runbooks
GET /backups
GET /agent-messages
GET /agent-meetings
GET /task-handoffs
GET /agent-broadcasts
GET /agent-conflicts
GET /task-reviews
GET /improvement-proposals
GET /github/absorptions
GET /logs/structured
GET /alerts/status
GET /memory
GET /knowledge
GET /evaluations
POST /workflows/run
POST /tasks/{task_id}/resume
POST /approvals/request
POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/resolve
POST /backups
POST /backups/{backup_id}/verify
POST /backups/{backup_id}/restore-request
POST /backups/{backup_id}/restore
POST /schedules
POST /schedules/{schedule_id}/pause
POST /schedules/{schedule_id}/resume
POST /schedules/{schedule_id}/cancel
POST /scheduler/tick
POST /agent-messages
POST /agent-meetings
POST /tasks/{task_id}/handoff
POST /agent-broadcasts
POST /agent-conflicts
POST /agent-conflicts/{conflict_id}/resolve
POST /task-reviews
POST /task-reviews/{review_id}/improvements
POST /improvement-proposals/{proposal_id}/sandbox
POST /improvement-proposals/{proposal_id}/register
POST /github/absorptions/analyze
POST /github/absorptions/{proposal_id}/sandbox
POST /github/absorptions/{proposal_id}/register
POST /goals
POST /goals/{goal_id}/progress
POST /goals/{goal_id}/tasks/{task_id}
POST /goals/{goal_id}/reviews/{review_id}
POST /goals/{goal_id}/improvements/{proposal_id}
POST /tools/runs/request
POST /tools/runs/{run_id}/complete
POST /models/generate
GET /skills/proposals
GET /agents/proposals
POST /skills/proposals/{proposal_id}/sandbox
POST /agents/proposals/{proposal_id}/sandbox
POST /skills/proposals/{proposal_id}/register
POST /agents/proposals/{proposal_id}/register
```

## Current Capabilities

- Hold multi-turn conversations through the governed Model Gateway, with browser-local session history and provider/model controls.
- Inspect actual provider, model, fallback, token usage, and estimated cost on each assistant response.
- View system health and core counts.
- Create, pause, resume, cancel, and tick durable schedules; inspect execution history, failed executions, Redis/RQ worker counts, queue backlog, failed queue jobs, and domain events.
- View active persistence backend, schema version, and applied SQLite migrations.
- View production readiness checks for auth, persistence, queue, alerts, providers, embeddings, runbooks, and operator backlog.
- View outbound alert delivery status without exposing the webhook URL.
- View system integrity checks for persistence, schema, audit guards, backups, incidents, approvals, and budget policy.
- View task status distribution.
- Create strategic goals, update progress, and link tasks, reviews, and improvements.
- View skill risk distribution.
- View Agents and Skills.
- View registered Tools, recent Tool Runs, and adapter result/error summaries.
- View the complete V1 Workflow catalog, declared steps, execution modes, entrypoints, recent runs, and step traces.
- View model usage counts, token estimates, and recent model calls.
- View budget usage and recent cost logs.
- Update the active model budget policy from Settings as Human Root.
- View, acknowledge, and resolve operational incidents.
- See matched operational runbooks for open Incidents.
- Create, view, verify checksum integrity, request Human Root restore approval, and apply an approved SQLite restore with an automatic safety checkpoint.
- Send Agent messages and record Agent coordination meetings.
- Record auditable task handoffs with linked Agent messages.
- Broadcast internal events to multiple Agents and view recent broadcasts.
- Open and resolve Agent conflicts from the Communication panel.
- Record task reviews and view recent retrospective lessons.
- Create review-driven improvement proposals, run their sandbox checks, and register approved improvements as knowledge records.
- Analyze user-supplied GitHub repository metadata, run sandbox checks, and register approved absorption analyses as knowledge records.
- View recent approvals, risks, and audit logs.
- View normalized structured JSON logs across audit, workflow, tool, model, cost, and incident categories.
- View Memory and Knowledge Base entries.
- View recent evaluation records and average score.
- Select and run all 10 V1 native Workflows, including GitHub Project Analysis and Tool Call.
- Resume a waiting document Workflow after Human Root approval.
- Submit an action through the Approval Center.
- Request a controlled Tool Run from the dashboard.
- Complete approval-gated Tool Runs after Human Root approval.
- Run deterministic Model Gateway calls from the dashboard.
- Approve or reject pending approvals from the Approvals panel.
- View pending/approved capability proposals.
- Run proposal sandbox tests and register proposals only after approval and sandbox pass.
- Change the API base URL from the page.

Provider API keys are backend secrets configured through environment variables or secret files. The System page bearer-token field is only for authenticating the browser to AI Company OS and must not be used for a DeepSeek or OpenAI API key.

## Local Use

1. Start the FastAPI backend.
2. Run `npm install` and `npm run dev` from `apps/web`.
3. Open `http://127.0.0.1:3000` and keep the API Base pointed at `http://127.0.0.1:8000`.

The backend enables CORS for local development. For a dependency-free fallback, open `apps/web_dashboard/index.html` directly.

## Next Dashboard Step

Expand browser-level E2E coverage into deeper provider failure states, destructive restore approval flows, and cross-session auth behavior while keeping the existing operational data contract stable.
