# API

## Required V1 API Surface

```text
POST /auth/register
POST /auth/login
POST /auth/logout

GET /database/schema
GET /system/integrity
GET /deployment/readiness
GET /events

GET /schedules
POST /schedules
POST /schedules/{id}/pause
POST /schedules/{id}/resume
POST /schedules/{id}/cancel
GET /scheduler/executions
GET /scheduler/queue-health
POST /scheduler/tick

GET /agents
POST /agents
GET /agents/{id}
POST /agents/missing
GET /agents/proposals
POST /agents/proposals/{id}/sandbox
POST /agents/proposals/{id}/register
POST /agents/factory/create

GET /skills
POST /skills
POST /skills/search
POST /skills/missing
GET /skills/proposals
POST /skills/proposals/{id}/sandbox
POST /skills/proposals/{id}/register
POST /skills/factory/create

GET /tools
POST /tools
GET /tools/runs
POST /tools/runs/request
POST /tools/runs/{id}/complete

GET /workflows
GET /workflows/{id}
GET /workflow-runs
GET /workflow-runs/{id}/steps
POST /workflows/run

GET /goals
POST /goals
POST /goals/{id}/progress
POST /goals/{id}/tasks/{task_id}
POST /goals/{id}/reviews/{review_id}
POST /goals/{id}/improvements/{proposal_id}

GET /tasks
POST /tasks
GET /tasks/{id}
POST /tasks/{id}/run
POST /tasks/{id}/resume
POST /tasks/{id}/pause
POST /tasks/{id}/cancel

GET /approvals
POST /approvals/request
POST /approvals/{id}/approve
POST /approvals/{id}/reject

GET /audit-logs
GET /logs/structured

GET /memory
POST /memory

GET /knowledge
POST /knowledge

GET /evaluations

GET /model-usage
POST /models/generate
GET /cost-logs
GET /budget/summary
POST /budget/policy

GET /incidents
GET /alerts/status
GET /runbooks
GET /incidents/{id}/runbook
POST /incidents/{id}/acknowledge
POST /incidents/{id}/resolve

GET /backups
POST /backups
POST /backups/{id}/verify
POST /backups/{id}/restore-request
POST /backups/{id}/restore

GET /agent-messages
POST /agent-messages
GET /agent-meetings
POST /agent-meetings
GET /task-handoffs
POST /tasks/{id}/handoff
GET /agent-broadcasts
POST /agent-broadcasts
GET /agent-conflicts
POST /agent-conflicts
POST /agent-conflicts/{id}/resolve
GET /task-reviews
POST /task-reviews
POST /task-reviews/{id}/improvements
GET /improvement-proposals
POST /improvement-proposals/{id}/sandbox
POST /improvement-proposals/{id}/register
GET /github/absorptions
POST /github/absorptions/analyze
POST /github/absorptions/{id}/sandbox
POST /github/absorptions/{id}/register

GET /risks

GET /dashboard/summary
```

## API Contract Rule

API handlers should be thin. Permission, risk, approval, audit, Agent, Skill, and Workflow behavior belongs in core services first, then the API calls those services.

The scheduler API persists one-time and recurring internal jobs, supports pause/resume/cancel controls, records every execution, and exposes an explicit Human Root tick. `GET /events` provides filtered append-only domain events by event type, source type, or task. `GET /scheduler/queue-health` reports Redis/RQ transport health, worker count, backlog counts, failed-job counts, and sample job IDs without exposing Redis credentials.

`GET /deployment/readiness` is stricter than `/health`. It reports whether production-facing requirements are satisfied, including HTTP auth, durable persistence, schema state, audit append-only guards, Redis/RQ scheduler queue configuration, alert delivery metadata, model provider mode, embeddings/vector store status, runbooks, and operator backlog. It exposes booleans, hostnames, counts, and statuses only; raw API tokens, provider keys, Redis URLs, database URLs, and full webhook URLs are not returned.

## Current Implementation

The first FastAPI route layer is implemented in:

```text
backend/app/api/routes.py
backend/app/api/schemas.py
backend/app/main.py
```

Current implemented routes include:

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /database/schema`
- `GET /system/integrity`
- `GET /deployment/readiness`
- `GET /agents`
- `POST /agents`
- `GET /agents/{agent_id}`
- `POST /agents/missing`
- `GET /agents/proposals`
- `POST /agents/proposals/{proposal_id}/sandbox`
- `POST /agents/proposals/{proposal_id}/register`
- `POST /agents/factory/create`
- `GET /skills`
- `POST /skills`
- `POST /skills/search`
- `POST /skills/missing`
- `GET /skills/proposals`
- `POST /skills/proposals/{proposal_id}/sandbox`
- `POST /skills/proposals/{proposal_id}/register`
- `POST /skills/factory/create`
- `GET /tools`
- `POST /tools`
- `GET /tools/runs`
- `POST /tools/runs/request`
- `POST /tools/runs/{run_id}/complete`
- `GET /workflows`
- `GET /workflow-runs`
- `GET /workflow-runs/{run_id}/steps`
- `POST /workflows/run`
- `GET /goals`
- `POST /goals`
- `POST /goals/{goal_id}/progress`
- `POST /goals/{goal_id}/tasks/{task_id}`
- `POST /goals/{goal_id}/reviews/{review_id}`
- `POST /goals/{goal_id}/improvements/{proposal_id}`
- `GET /tasks`
- `POST /tasks`
- `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/run`
- `POST /tasks/{task_id}/resume`
- `POST /tasks/{task_id}/pause`
- `POST /tasks/{task_id}/cancel`
- `GET /approvals`
- `POST /approvals/request`
- `POST /approvals/{approval_id}/approve`
- `POST /approvals/{approval_id}/reject`
- `GET /audit-logs`
- `GET /logs/structured`
- `GET /memory`
- `POST /memory`
- `GET /knowledge`
- `POST /knowledge`
- `GET /evaluations`
- `GET /model-usage`
- `POST /models/generate`
- `GET /cost-logs`
- `GET /budget/summary`
- `POST /budget/policy`
- `GET /incidents`
- `GET /alerts/status`
- `GET /runbooks`
- `GET /incidents/{incident_id}/runbook`
- `POST /incidents/{incident_id}/acknowledge`
- `POST /incidents/{incident_id}/resolve`
- `GET /backups`
- `POST /backups`
- `POST /backups/{backup_id}/verify`
- `POST /backups/{backup_id}/restore-request`
- `POST /backups/{backup_id}/restore`
- `GET /agent-messages`
- `POST /agent-messages`
- `GET /agent-meetings`
- `POST /agent-meetings`
- `GET /task-handoffs`
- `POST /tasks/{task_id}/handoff`
- `GET /agent-broadcasts`
- `POST /agent-broadcasts`
- `GET /agent-conflicts`
- `POST /agent-conflicts`
- `POST /agent-conflicts/{conflict_id}/resolve`
- `GET /task-reviews`
- `POST /task-reviews`
- `POST /task-reviews/{review_id}/improvements`
- `GET /improvement-proposals`
- `POST /improvement-proposals/{proposal_id}/sandbox`
- `POST /improvement-proposals/{proposal_id}/register`
- `GET /github/absorptions`
- `POST /github/absorptions/analyze`
- `POST /github/absorptions/{proposal_id}/sandbox`
- `POST /github/absorptions/{proposal_id}/register`
- `GET /risks`
- `POST /risks/assess`
- `GET /dashboard/summary`

Authentication supports local user registration, PBKDF2 password verification, local bearer token sessions, duplicate-email rejection, and SQLite-backed user reload.

HTTP authentication is disabled by default for local development. In protected deployments, set `AI_COMPANY_OS_AUTH_REQUIRED=true` and configure either `AI_COMPANY_OS_API_TOKEN` or `AI_COMPANY_OS_API_TOKEN_SHA256`. When enabled, only `GET /health` and `POST /auth/login` are public; every other API route requires `Authorization: Bearer <token>`. Valid bearer values are either the configured static API token or a session token returned by `POST /auth/login`. Startup fails if auth is required and neither a static API token nor a persisted user exists.

`GET /database/schema` returns the active persistence backend. In memory mode it reports `backend=memory` with no schema version. In SQLite mode it reports `backend=sqlite`, the current `schema_version`, and the applied migration ledger from `schema_migrations`.

`POST /agents` and `POST /skills` validate every referenced Skill, Tool, Agent, and reporting line before Human Root registration. Accepted entries write audit events and persist in SQLite. Factory-approved registrations use the same durable catalogs.

`GET /workflows` returns the 10 validated V1 Workflow definitions, including ordered Agent/Skill steps. Every V1 definition is native and uses `POST /workflows/run`, which accepts `workflow_id`, `title`, `description`, optional `user_id`, and an optional Workflow-specific `input` object. Agent-collaboration input may include `target_agent_id`, `participant_agents`, `agenda`, `handoff_reason`, and `instructions`; all referenced Agents are validated before task creation. Skill-Missing input may include `capability`, `requested_by_agent`, `candidate_skill_ids`, `constraints`, `risk_level`, and `allow_replacement`; unauthorized composition candidates are rejected before task creation, and approval-gated temporary Skill preparation resumes through `POST /tasks/{task_id}/resume`. Agent-Missing input may include `role`, `department`, `repeated_reason`, `knowledge_query`, and `allow_existing_agent`; existing roles are reused, while new disabled proposals carry a task-linked approval. Approval input may include `action`, `actor_id`, `permission_level`, `reason`, `target`, `possible_benefit`, `possible_loss`, and `reversible`; pending decisions resume through the same task endpoint and only final decisions can continue. Retrospective input may include `source_task_id`, `outcome`, `summary`, `what_went_well`, `what_went_wrong`, `lessons`, `follow_up_actions`, `quality_score`, and `risk_level`; invalid input or an unknown source task is rejected before a Workflow task is created. GitHub Project Analysis input includes `repo_url`, `readme`, optional `requested_by_agent`, `license_name`, and `maintenance_signal`; it pauses once for task-scoped approval, then resumes through controlled Skills, sandbox, and Knowledge-only registration. Tool Call input includes `tool_id`, `actor_id`, `tool_input`, and `reason`; it creates a task-linked Tool Run and resumes approval-gated execution through the same task endpoint.

`GET /system/integrity` returns operational self-checks for persistence backend, schema version, SQLite audit append-only guards, backup checksum state, open incidents, pending approvals, and budget policy status. It reports an overall `ok`, `warning`, or `critical` status plus individual check messages.

`GET /dashboard/summary` returns operational sections for the dashboard:

- task status counts
- approval status counts
- Agent status counts
- Skill status counts
- Skill risk counts
- recent tasks
- recent approvals
- recent risks
- recent audit logs
- recent structured logs
- system integrity checks
- recent evaluations
- recent tool runs
- recent workflow runs
- recent workflow steps
- recent model usage
- recent cost logs
- recent incidents
- recent backups
- recent Agent messages
- recent Agent meetings
- recent task handoffs
- recent Agent broadcasts
- recent Agent conflicts
- recent task reviews
- recent improvement proposals
- recent GitHub absorptions
- recent strategic goals
- recent failed scheduled executions
- memory, knowledge, and audit counts
- structured log counts
- integrity status and issue counts
- evaluation count and average score
- tool and tool-run counts
- registered Workflow, Workflow Run, and Workflow Step counts
- model usage, token, and estimated cost counts
- budget used/max token and cost counts
- incident and open-incident counts
- scheduler queue health and failed scheduled execution counts
- backup counts
- Agent message and meeting counts
- task handoff counts
- Agent broadcast counts
- Agent conflict and open conflict counts
- task review counts and average review score
- improvement proposal counts
- GitHub absorption counts
- strategic goal counts, active goal counts, and average goal progress

`GET /evaluations` returns Agent, Skill, and Workflow evaluation records. Every native Workflow writes deterministic Workflow evaluations, while successful Skill Runtime calls write their own Skill evaluations.

`POST /models/generate` checks the Budget Guard, then dispatches through the configured local or OpenAI provider. Allowed calls record `ModelUsageRecord`, `CostLog`, and a `model_called` audit event. Blocked calls record `model_blocked`; sanitized provider failures record `model_failed` plus an Incident. `GET /models/providers` exposes configured provider names and defaults without secrets. `GET /model-usage` returns usage records with provider, model, actor, task, purpose, token counts, and estimated cost.

`POST /knowledge/search` combines pgvector semantic matches with lexical matches when an embedding provider and vector-capable PostgreSQL store are active. `GET /knowledge/embeddings/status` reports provider, model, dimensions, indexed count, and failed count without secrets. `POST /knowledge/embeddings/reindex` is restricted to `human_root`. Disabled or failed embeddings fall back to lexical search.

`GET /budget/summary` returns the active local budget policy and current usage. `POST /budget/policy` lets Human Root update the active model budget policy and writes a `budget_policy_updated` audit event. Non-root attempts are blocked, audited, and incidented. `GET /cost-logs` returns recorded and blocked cost log records.

`GET /incidents` returns blocked or operationally risky events that need follow-up. Blocked approval requests, blocked Tool Runs, blocked Workflow tasks, over-budget model calls, failed schedules, and provider failures create incidents. Incident responses include a matched runbook with immediate actions, verification steps, owner Agent, and escalation policy. `GET /runbooks` lists the response catalog, and `GET /incidents/{incident_id}/runbook` returns the runbook matched to a specific Incident. When outbound alerts are enabled, service-reported Incidents are posted to the configured webhook and delivery success or failure is audited without exposing the full webhook URL. `GET /alerts/status` reports whether alert delivery is enabled, configured, and which endpoint host is used. `POST /incidents/{incident_id}/acknowledge` records who acknowledged the issue. `POST /incidents/{incident_id}/resolve` closes the incident with an optional resolution note. Incident updates are audited.

`POST /backups` creates a state snapshot, including formal Agent and Skill catalogs, with a controlled rollback plan and deterministic snapshot checksum, then writes a `backup_created` audit event. `GET /backups` lists stored backups. `POST /backups/{backup_id}/verify` recomputes the snapshot checksum, reports verified/mismatched/missing-checksum status, and writes a `backup_verified` audit event. `POST /backups/{backup_id}/restore-request` creates a high-risk restore approval only when checksum verification passes; failed integrity checks are blocked, audited, and incidented. `POST /backups/{backup_id}/restore` applies a verified snapshot to SQLite after a matching Human Root approval, creates a pre-restore safety checkpoint, rejects approval replay, and preserves users, approvals, append-only audit history, incidents, backups, and migrations.

`POST /agent-messages` stores an Agent-to-Agent message after validating both Agents exist and writes an `agent_message_sent` audit event. `GET /agent-messages` lists messages and can filter by `agent_id` or `task_id`.

`POST /agent-meetings` records a coordination meeting after validating the organizer and participants exist and writes an `agent_meeting_recorded` audit event. `GET /agent-meetings` lists meetings and can filter by `task_id`.

`POST /tasks/{task_id}/handoff` records an internal task handoff after validating the task, sender Agent, receiver Agent, permission, and risk policy. It also creates a linked `handoff` message requiring response and writes a `task_handoff_recorded` audit event. `GET /task-handoffs` lists handoffs and can filter by `task_id` or `agent_id`.

`POST /agent-broadcasts` records an internal event broadcast for multiple Agents after validating the sender, audience, optional task, permission, and risk policy. It writes an `agent_broadcast_sent` audit event. `GET /agent-broadcasts` lists broadcasts and can filter by `task_id`, `agent_id`, or `event_type`.

`POST /agent-conflicts` opens an arbitration record with participant positions and priority area after validating Agents, optional task, permission, and risk policy. `POST /agent-conflicts/{conflict_id}/resolve` records the final resolution and selected participant position. Conflict opening and resolution are audited. `GET /agent-conflicts` lists conflicts and can filter by `task_id`, `agent_id`, or `status`.

`POST /task-reviews` records a task retrospective after validating the task and reviewer Agent. It stores structured outcome, summary, what-went-well/wrong notes, lessons, follow-up actions, quality score, and risk level. Recording a review also writes review memory, creates a knowledge-base lesson document, and appends a `task_review_recorded` audit event. `GET /task-reviews` lists reviews and can filter by `task_id` or `reviewer_agent`.

`POST /task-reviews/{review_id}/improvements` creates a controlled improvement proposal grounded in a review's lessons and follow-up actions. The proposal receives an approval request before it can be registered. `POST /improvement-proposals/{proposal_id}/sandbox` runs deterministic checks for target type, review linkage, risk boundary, and evidence. `POST /improvement-proposals/{proposal_id}/register` requires approved approval plus passed sandbox, then records the improvement as a knowledge document and writes an `improvement_registered_from_proposal` audit event.

`POST /github/absorptions/analyze` accepts user-supplied repository metadata, README text, license name, and maintenance signal. It does not fetch from GitHub or execute repository code. The analysis applies external-content inspection, license checks, security-signal checks, and capability extraction, then creates an approval-linked absorption proposal. `POST /github/absorptions/{proposal_id}/sandbox` validates GitHub URL shape, Agent reference, license risk, and security findings. `POST /github/absorptions/{proposal_id}/register` requires approved approval plus passed sandbox, then registers the analysis as a Knowledge document only.

`POST /workflows/run` with `github_project_analysis_v1` provides the end-to-end form of the same controls. One task-linked Human Root decision authorizes only the registered GitHub Analysis Skill within that Workflow. Approval, resumed Skill Runs, proposal, sandbox evidence, Knowledge document, Workflow traces, Evaluation, Audit, and Incidents all retain the same task linkage and persist across SQLite restart.

`POST /goals` creates a strategic operating goal with an owner Agent, metric, target value, current value, and active status. `POST /goals/{goal_id}/progress` updates progress and auto-completes the goal when current value reaches the target unless a status is supplied. Goal link endpoints connect tasks, reviews, and improvement proposals back to the goal. Goal creation, progress updates, and links are audited.

`GET /workflow-runs` returns structured Workflow Run records. `GET /workflow-runs/{run_id}/steps` returns the ordered step trace for one run. The document workflow currently records task creation, planning, assignment, document writing, risk check, quality check, and completion. `POST /tasks/{task_id}/resume` resumes a document workflow only when the task is waiting for approval and the linked approval has been approved.

`GET /logs/structured` returns normalized JSON operational logs derived from audit events, Workflow Runs, Workflow Steps, Tool Runs, model usage, cost logs, and incidents. It supports optional `category`, `level`, and `limit` query parameters. Audit logs remain the append-only source of truth; this endpoint is a read-only observability view with stable fields such as `timestamp`, `level`, `category`, `event_type`, `source_id`, `actor_id`, `task_id`, `risk_level`, `status`, `message`, and `payload`.

`POST /tools/runs/request` requests a controlled tool run. The service checks that the Tool is enabled, the Agent is allowed to use it, the requested action stays within permission boundaries, and the risk policy allows it. Low-risk allowed internal tools execute deterministic adapters and store JSON output on the Tool Run. The filesystem adapter is workspace-only and read-only for small text files, and read/search results include external-content inspection metadata so prompt-injection-like text is treated as untrusted source data. Medium/high-risk tools or tools marked `requires_approval` create approval-linked waiting runs. Disabled, forbidden, or unauthorized runs are blocked and audited.

`POST /tools/runs/{run_id}/complete` completes a waiting Tool Run only after its linked approval has been approved. Pending, rejected, blocked, or non-waiting Tool Runs cannot be completed. Completion writes a separate `tool_run_completed` audit event.

`POST /workflows/run` with `tool_call_v1` is the end-to-end task form of those Tool controls. It adds three controlled Skill Runs, Workflow traces and Evaluation, distinguishes adapter `failed` state from policy `blocked` state, enforces rejection without execution, and revalidates live Agent/Tool permissions immediately before approved execution. Waiting Tool Call Workflows survive SQLite restart and resume through `POST /tasks/{task_id}/resume`.

`POST /approvals/request` evaluates a proposed action through Permission and Risk. Low-risk allowed actions are audited as allowed. Medium/high-risk actions create pending approvals. Forbidden or permission-blocked actions create blocked approvals and audit events.

Approval decisions are also audited:

- approving writes an `approval_decided` audit event with `approval_status=approved`
- rejecting writes an `approval_decided` audit event with `approval_status=rejected`
- decisions are persisted by the SQLite adapter

Missing Skill and Agent requests now create stored proposals linked to approval requests. A proposal cannot be registered as a formal Skill or Agent until its approval is approved and its sandbox test has passed. `POST /skills/proposals/{proposal_id}/sandbox` and `POST /agents/proposals/{proposal_id}/sandbox` run deterministic safety checks and write sandbox audit events.
