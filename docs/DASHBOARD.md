# DASHBOARD

## Current Dashboard

The first dashboard is a dependency-free static control panel:

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
GET /events
GET /schedules
GET /scheduler/executions
GET /goals
GET /agents
GET /skills
GET /tools
GET /tools/runs
GET /workflow-runs
GET /model-usage
GET /budget/summary
POST /budget/policy
GET /cost-logs
GET /incidents
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
GET /memory
GET /knowledge
GET /evaluations
POST /tasks
POST /tasks/{task_id}/run
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

- View system health and core counts.
- Create, pause, resume, cancel, and tick durable schedules; inspect execution history and domain events.
- View active persistence backend, schema version, and applied SQLite migrations.
- View system integrity checks for persistence, schema, audit guards, backups, incidents, approvals, and budget policy.
- View task status distribution.
- Create strategic goals, update progress, and link tasks, reviews, and improvements.
- View skill risk distribution.
- View Agents and Skills.
- View registered Tools, recent Tool Runs, and adapter result/error summaries.
- View recent Workflow Runs and step traces.
- View model usage counts, token estimates, and recent model calls.
- View budget usage and recent cost logs.
- Update the active model budget policy from Settings as Human Root.
- View, acknowledge, and resolve operational incidents.
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
- Create and run a document Workflow task.
- Resume a waiting document Workflow after Human Root approval.
- Submit an action through the Approval Center.
- Request a controlled Tool Run from the dashboard.
- Complete approval-gated Tool Runs after Human Root approval.
- Run deterministic Model Gateway calls from the dashboard.
- Approve or reject pending approvals from the Approvals panel.
- View pending/approved capability proposals.
- Run proposal sandbox tests and register proposals only after approval and sandbox pass.
- Change the API base URL from the page.

## Local Use

1. Start the FastAPI backend.
2. Open `apps/web_dashboard/index.html` in a browser.
3. Keep the API Base field pointed at `http://127.0.0.1:8000`.

The backend enables CORS for local development so the static page can call the API.

## Next Dashboard Step

Move this shell into a Next.js TypeScript app once dependency installation and package management are set up. Keep the same operational data contract.
