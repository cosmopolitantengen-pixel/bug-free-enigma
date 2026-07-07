# ROADMAP

## Vision

Build AI Company OS as a controllable, extensible AI company operating system. The system should coordinate Agents, Skills, Workflows, Tools, Memory, Knowledge Base, Permission, Approval, Risk, Audit, and Evaluation under Human Root control.

## Phase 0: Foundation

- Split product requirements into executable module docs.
- Build a deterministic backend core that does not depend on live model calls.
- Prove safety invariants with tests.
- Keep all high-risk and forbidden behavior blocked or routed through approval.

## Phase 1: Minimal Closed Loop

The first runnable loop is:

1. User creates a strategic goal or task.
2. CEO Agent plans the task.
3. Project Manager Agent assigns execution.
4. Document Agent calls a registered document Skill.
5. Risk Agent checks the planned action.
6. Quality Agent checks the output.
7. Approval Center handles medium/high risk actions.
8. Audit Log records every key action.
9. Memory and Knowledge Base store the result.
10. Tool requests run through permission, risk, approval, and audit controls.
11. Skill requests run through schema validation, two-sided authorization, risk, approval, audit, persistence, and evaluation controls.
12. Workflow Run and Workflow Step traces record the execution path.
13. Model calls go through a gateway with usage and audit records.
14. Budget guardrails check model calls and record cost logs.
15. Blocked operational events create incidents for human follow-up.
16. Agents can leave auditable messages, coordination meeting records, task handoffs, internal event broadcasts, and conflict arbitration records.
17. Task reviews turn retrospective notes into review memory, knowledge docs, and audit events.
18. Review-driven improvement proposals route lessons through approval, sandbox checks, and registered knowledge.
19. Strategic goals track operating progress and link tasks, reviews, and improvements to the higher-level objective.
20. Dashboard can read task, goal, agent, skill, tool, workflow, model, budget, incident, communication, review, improvement, approval, risk, and audit state.

Current status:

- Core domain models exist.
- Default Agent and Skill registries exist.
- Permission, risk, approval, audit, memory, and knowledge services exist.
- Document generation Workflow runs to completion.
- FastAPI route layer exposes the first required endpoints.
- Local auth uses persisted users with PBKDF2 password hashes.
- Optional production HTTP bearer auth protects the API when enabled.
- Static dashboard shell exists and consumes the backend dashboard API.
- Approval request flow exists for Permission + Risk + Approval + Audit.
- Approval decisions are audited and can be made from the dashboard shell.
- Missing Skill and Agent flows create persisted proposals linked to approval.
- Proposals must pass deterministic sandbox checks before approved proposals can be registered as formal Skills or Agents.
- Evaluation records are written for the document workflow, quality agent, and document skill.
- Tool registry and controlled Tool Run request flow exist.
- Tool Runs are persisted and visible in the dashboard.
- Approval-gated Tool Runs can be explicitly completed after Human Root approval and write separate completion audit events.
- Workflow Runs and Workflow Steps are persisted and visible in the dashboard.
- Approval-gated document Workflow runs can resume after Human Root approval and continue to completion.
- Model Gateway records deterministic local model usage and audit events.
- Budget Guard blocks over-budget model calls and persists cost logs.
- Human Root can update the active Budget Policy through API and dashboard settings.
- Incident Management records blocked approvals, blocked tool runs, blocked workflow tasks, and blocked model calls.
- Incidents can be acknowledged and resolved from the API and static dashboard.
- Human Root can create persisted state backups with checksum verification and controlled rollback plans.
- Agent messages and meetings are persisted, audited, included in backups, and visible in the dashboard.
- Task handoffs validate Agent permission/risk, create linked handoff messages, persist to SQLite, and appear in the dashboard.
- Agent broadcasts validate Agent permission/risk, persist to SQLite, and appear in the dashboard.
- Agent conflicts can be opened, filtered, resolved, audited, persisted, and shown in the dashboard.
- Task reviews persist to SQLite, write review memory and knowledge docs, audit the retrospective, and appear in the dashboard.
- Review-driven improvement proposals persist to SQLite, require approval and sandbox checks, register as knowledge, and appear in the dashboard.
- Strategic goals persist to SQLite, track progress, link tasks/reviews/improvements, audit changes, and appear in the dashboard.
- Low-risk internal Tool Runs now execute deterministic adapters for task state, knowledge docs, audit reads, aggregate database state, and safe workspace file reads instead of returning only simulated text.
- Workspace file reads include deterministic external-content inspection so prompt-injection-like text is flagged as untrusted source data.
- GitHub absorption analysis accepts user-supplied repo metadata or controlled GitHub connector metadata import, applies external-content/license/security checks, requires approval and sandbox, and registers safe analyses as Knowledge only.
- Structured JSON operational logs are exposed as a read-only view over audit, workflow, tool, model, cost, and incident records.
- SQLite now records a baseline schema migration ledger and exposes database schema status through API and dashboard.
- SQLite audit logs are guarded by append-only triggers that reject direct update and delete attempts.
- Backups include deterministic snapshot checksums and an auditable verification endpoint/dashboard action.
- Backup restore requests require checksum verification; approved SQLite restores recheck integrity, create a pre-restore checkpoint, replace business state transactionally, and preserve control-plane history.
- System integrity checks expose persistence, schema, audit guard, backup, incident, approval, and budget status through API and dashboard.
- Durable one-time and recurring internal schedules can create or run tasks through an explicit Human Root tick, with lifecycle controls, execution history, Redis/RQ queue health, incidents, matched runbooks, optional outbound alerts, audit events, and append-only domain events.
- The catalog now boots with 18 scoped Agents, including a dedicated Workspace Agent, and 18 registered Skills, with cross-catalog reference validation.
- Formal Agent and Skill registrations are audited, persisted in SQLite, included in verified backups, and restored transactionally.
- All 10 required V1 Workflows are registered as validated Agent/Skill step definitions with explicit operational entrypoints.
- Task planning now runs as a second native Workflow with permission/risk checks, persisted traces, audit, plan Memory, Evaluation, and blocked-run Incidents.
- All 18 V1 Skills now execute through a controlled runtime with deterministic adapters, schema validation, symmetric Agent authorization, approval continuation, durable Skill Runs, blocked-run Incidents, and successful-run Evaluations.
- SQLite schema v6 persists Skill Runs, and the dashboard exposes Skill Run requests, status, results, and approval continuation.
- Document generation and task planning execute registered Skills through the unified Skill Runtime. Document generation produces five linked Skill Runs and task planning produces three; blocked or failed Skills stop the parent Workflow.
- Quality checking is the third native Workflow, with separate quality-failure and control-block semantics, three linked Skill Runs, persisted traces, Evaluation, Audit, and Incident handling.
- Retrospective is the fourth native Workflow. Structured review input produces three controlled Skill Runs and gates TaskReview and Knowledge creation on successful quality, memory, and audit steps.
- Agent collaboration is the fifth native Workflow. It validates participants before task creation, executes three controlled Skill Runs, records a meeting and linked task handoff, preserves partial records on a later control block, and persists the complete communication trail.
- Skill Missing handling is the sixth native Workflow. It prefers an authorized replacement, then an authorized multi-Skill composition, and creates a controlled proposal only for a real gap. Medium-risk temporary Skill preparation pauses at Human Root approval and can resume after a SQLite restart.
- Agent Missing handling is the seventh native Workflow. It reuses an existing role when possible, otherwise runs Knowledge, planning, and risk Skills before creating a disabled Agent proposal whose approval is linked to the Workflow task.
- Approval is the eighth native Workflow. Low-risk requests complete without a fabricated approval, controlled requests pause for Human Root and resume after a persisted decision, rejection is enforced as a valid outcome, and forbidden actions remain blocked.
- GitHub project analysis is the ninth native Workflow. It uses one task-scoped Human Root approval, executes registered analysis/risk Skills only after approval, preserves the external-content boundary, blocks failed sandbox evidence, and registers passed analyses as Knowledge only across SQLite restarts.
- Tool Call is the tenth native Workflow. It preserves the authoritative Tool Runtime, links three control Skills and the Tool Run to one task, resumes approvals across SQLite restarts, enforces rejection without execution, and separates adapter failure from permission/risk blocks.
- Approval-gated chat actions now expose risk and command context inline. Human Root can reject or approve-and-resume through one idempotent persisted-task endpoint, including after browser reload or SQLite process restart.
- Chat action selection is rule-first and model-assisted only for ambiguous operational language. Structured model output is restricted to a bounded intent catalog, while executable parameters remain fixed server mappings and planner usage stays inside Budget and Audit controls.
- Human Root chat sessions, messages, model metadata, and action-card state are now server-persisted, included in verified backup/restore state, and recover pending confirmation after browser or backend restart. Legacy browser transcripts import as text only.
- Governed multi-step Agent Runs now let a configured non-local model choose one validated tool intent at a time, automatically continue low-risk reads, pause exact patches and fixed commands for Human Root approval, display the persisted execution trace in chat, and resume after SQLite restart. Runs are capped at eight tool steps and never accept model-selected Tool IDs, commands, URLs, or approval outcomes.
- Native OpenAI/DeepSeek token streaming now reaches the console through authenticated SSE with final usage/cost/audit accounting, safe pre-delta fallback, and no planner/Agent-JSON leakage. Agent action execution separately streams persisted run and step snapshots into the live trace.
- Chat can now create Strategic Goal confirmation cards from explicit goal-setting language; confirmed goals use the existing Goal service, Audit, persistence, and restart recovery path, ordinary conversation includes active goal context, and new Workflow/Agent Run step tasks auto-link to the current active goal.
- Unit and API tests cover the current closed loop.

## Phase 2: API and Persistence

- Add FastAPI routes for the required API surface.
- Add database models and migrations.
- Use SQLite for local development and PostgreSQL/pgvector for production persistence.
- Add append-only audit storage.
- Add structured JSON logs.

Current implementation: the required FastAPI surface, optional production HTTP bearer auth with expiring local sessions, Docker/Kubernetes-style secret file loading, optional Incident alert webhooks, Incident runbook matching, deployment readiness checks, controlled GitHub connector metadata import, release gate checks, SQLite and PostgreSQL schema migrations, append-only audit guards, pgvector Knowledge indexing/search, configurable model and embedding providers, structured logs, Compose services, Redis/RQ scheduler workers with queue health reporting, the Next.js operations console, and service-level CI jobs with browser E2E smoke coverage are complete. Broader production operations remain.

## Phase 3: Dashboard

- Expand automated browser-level coverage for provider failure states, destructive restore approval flows, and cross-session auth behavior in the Next.js TypeScript console.
- Pages: Dashboard, Tasks, Agents, Skills, Workflows, Approvals, Risks, Audit Logs, Memory, Knowledge Base, Settings.
- The first dashboard is operational, not decorative.

Current interim implementation:

- Static dashboard shell in `apps/web_dashboard/`
- Backend CORS enabled for local dashboard calls
- Dashboard summary API includes operational counts and recent records
- Dashboard Settings can update the active model budget policy
- Dashboard includes an incident panel for open follow-up work
- Dashboard proposal cards can run sandbox checks before registration
- Dashboard includes a backup panel for manual checkpoints
- Dashboard includes Agent communication forms and recent message/meeting lists
- Dashboard includes task handoff controls and recent handoff history
- Dashboard includes Agent broadcast controls and recent broadcast history
- Dashboard includes conflict opening/resolution controls and recent conflict history
- Dashboard includes a task review form and recent review history
- Dashboard includes review-driven improvement proposal controls
- Dashboard includes strategic goal creation, progress updates, and record linking
- Dashboard lists and can run all 10 validated V1 Workflows from one selector
- Next.js Scheduler view includes Redis/RQ queue health, worker counts, backlog counts, failed queue jobs, and failed scheduled executions
- Next.js System view includes alert delivery status without exposing webhook secrets
- Next.js System view includes production readiness checks without exposing secret values
- Next.js Governance view includes Incident runbook guidance and runbook catalog visibility

The Next.js console satisfies the production UI migration, while the static shell remains as a fallback. The console can store an operator bearer token for protected API calls and now has CI browser E2E coverage for desktop/mobile navigation, multi-turn chat, inline high-risk action approval across reload, Workflow submission, approval approve/reject decisions, schedule create/pause/resume/cancel controls, Incident response, invalid API-base handling, and auth-required API degradation. Deeper browser coverage for provider failures and destructive restore approval remains alongside deployment promotion automation, managed alert routing/escalation, external secret-manager adapters beyond file-mounted secrets, managed identity, and full production session hardening.

## Phase 4: Controlled Evolution

- Implement Skill Missing Handler.
- Implement Agent Missing Handler.
- Implement Skill Factory and Agent Factory as proposal generators.
- Require sandbox checks, risk checks, and approval before enabling new formal Agents or Skills.

Current interim implementation:

- Missing Skill and Agent requests create proposal records.
- Native Skill/Agent Missing Workflows now prefer registered capability before proposing expansion and retain task-linked traces, Skill Runs, evaluations, approvals, and blocked-run incidents.
- Proposal sandbox checks verify basic permission/risk boundaries before registration.
- Registration is blocked until both approval and sandbox checks pass.
- Review-driven improvement proposals follow the same approval and sandbox pattern, then register as knowledge records instead of mutating runtime behavior directly.

## Phase 5: Tool and Model Expansion

- Current first Tool layer: task manager, knowledge base, audit read, external API, and code execution tool definitions.
- Safe internal adapters exist for task manager, knowledge base, audit read, database read, and workspace-only filesystem read tools.
- Exact workspace patching and fixed development commands are implemented behind mandatory Human Root approval; general code execution and external API adapters remain disabled by default.
- Add further model adapters without bypassing provider-specific pricing, budget, privacy, or Audit controls. Native OpenAI Responses and DeepSeek Chat Completions adapters now share explicit fallback routing, actual-provider usage records, and provider-native streaming.
- Add file, document, GitHub, and database tools.
- Add browser and computer-control adapters only behind strict permission and approval gates.
- Expand GitHub absorber beyond metadata/README import only after license, security, sandbox, and human approval checks remain covered.

## Non-Goals for V1

- No automatic money movement.
- No deleting audit logs.
- No disabling risk control.
- No platform abuse, phishing, credential theft, captcha bypass, attack tooling, malicious scraping, or spam automation.
- No complex billing or CRM before the operating foundation is stable.
