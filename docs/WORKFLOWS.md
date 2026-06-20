# WORKFLOWS

## Workflow Definition

A Workflow coordinates Agents, Skills, Tools, approvals, quality checks, audit logs, and memory writes into a full process.

## V1 Workflows

- Document generation Workflow
- Task planning Workflow
- Agent collaboration Workflow
- Skill missing Workflow
- Agent missing Workflow
- Approval Workflow
- Quality check Workflow
- Review / retrospective Workflow
- GitHub project analysis Workflow
- Tool call Workflow

## Document Generation Workflow

1. User creates document task.
2. CEO Agent classifies intent and creates a plan.
3. Project Manager Agent assigns work.
4. Document Agent uses Document Writing Skill.
5. Risk Agent checks content and actions.
6. Quality Agent checks output.
7. Approval Center handles any medium/high risk step.
8. Audit Agent records every key event.
9. Memory Agent stores task result.
10. Knowledge Base stores reusable output when appropriate.

## Workflow Requirements

- Every step has a state.
- Every important action is audited.
- Every run should have a structured `WorkflowRun` record.
- Every meaningful step should have a `WorkflowStep` record with sequence, actor, action, risk, approval status, and result.
- Risk and permission checks happen before execution.
- Medium/high risk actions cannot bypass approval.
- Approval-gated workflows must resume only after the linked approval is approved.
- Failure must leave useful audit and risk records.
- Completed workflows write evaluation records for the workflow, participating Agent, and Skill.

## Current Implementation

The Workflow Registry now contains all 10 V1 definitions. Every definition declares an ID, version, execution mode, entrypoint, ordered steps, responsible Agent, action, permission level, and optional Skill. Registration rejects non-contiguous steps, missing Agents or Skills, Agent permissions that do not exactly include the requested level, and unauthorized Agent/Skill pairs.

`GET /workflows` lists the catalog and `GET /workflows/{workflow_id}` returns one definition. `POST /workflows/run` is the common native runner for `document_generation_v1`, `task_planning_v1`, `quality_check_v1`, and `retrospective_v1`. Definitions backed by an existing controlled service expose that service as their dedicated entrypoint rather than pretending a no-op generic run completed real work.

The document generation workflow writes one `WorkflowRun` and seven ordered `WorkflowStep` records:

1. `task_created`
2. `plan_task`
3. `assign_document_agent`
4. `write_document`
5. `risk_check`
6. `quality_check`
7. `complete_task`

These records are exposed through `GET /workflow-runs`, `GET /workflow-runs/{run_id}/steps`, `GET /dashboard/summary`, and the static dashboard.

When invoked through the application service or API, the Workflow steps dispatch through the same controlled Skill Runtime used by `POST /skills/runs/request`. A successful document run creates five task-linked Skill Runs: CEO planning, Project Manager assignment planning, document writing, risk checking, and quality checking. The document Skill draft becomes the Model Gateway input; risk or quality Skill failure stops the Workflow instead of being treated as a successful trace-only step.

If `write_document` requires approval, the task enters `needs_approval` and the `WorkflowRun` enters `waiting_approval`. After Human Root approves the linked approval, `POST /tasks/{task_id}/resume` continues the same workflow run through document writing, risk check, quality check, memory write, knowledge write, evaluation, and completion. Resume is rejected for pending, rejected, blocked, or non-waiting tasks.

The task planning workflow writes three ordered steps:

1. `understand_goal`
2. `decompose_task`
3. `validate_plan_risk`

Each step rechecks Agent enabled state, Skill enabled state, exact permission, and risk policy at runtime. Success writes a scoped plan to the task, plan Memory, Workflow evaluation, audit events, and persisted traces. A disabled Skill, disabled Agent, permission violation, or blocked risk stops the Workflow and creates an Incident. The task remains `planned`; planning does not claim that execution has happened.

The task planning runner produces three task-linked Skill Runs and uses the planning Skill output as the execution-plan body. Skill Runs and their Evaluations persist independently from Workflow traces, so operators can inspect both process state and capability execution state.

The quality check runner executes three ordered Skills:

1. `quality_check_skill_v1` evaluates supplied content.
2. `risk_check_skill_v1` checks the review action.
3. `audit_logging_skill_v1` prepares the structured quality event.

All three calls create task-linked Skill Runs. Content that fails quality is a business failure: the task and Workflow become `failed`, but risk and audit steps still run. A disabled, unauthorized, blocked, or malformed Skill is a control failure: the task and Workflow become `blocked`, the failing step is recorded, and an Incident is created.

The retrospective runner accepts an optional structured `input` object with `source_task_id`, outcome, summary, what-went-well/wrong notes, lessons, follow-up actions, quality score, and risk level. It validates the complete payload and source task before creating the Workflow task, then executes quality, memory-write, and audit Skills. Only after all three Skill Runs complete does it persist the TaskReview and reusable Knowledge document. The Workflow task and source task remain distinct and are linked through Review, Memory, and Knowledge records.

The other catalog definitions point to their operational entrypoints:

- Agent collaboration: meetings and task handoffs
- Skill/Agent missing handling: controlled Factory proposal APIs
- Approval: Approval Center request and decision APIs
- GitHub analysis: absorption analysis, sandbox, approval, and knowledge registration APIs
- Tool call: controlled Tool Run request and completion APIs
