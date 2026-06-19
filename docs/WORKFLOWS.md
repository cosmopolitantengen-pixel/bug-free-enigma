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

The document generation workflow writes one `WorkflowRun` and seven ordered `WorkflowStep` records:

1. `task_created`
2. `plan_task`
3. `assign_document_agent`
4. `write_document`
5. `risk_check`
6. `quality_check`
7. `complete_task`

These records are exposed through `GET /workflow-runs`, `GET /workflow-runs/{run_id}/steps`, `GET /dashboard/summary`, and the static dashboard.

If `write_document` requires approval, the task enters `needs_approval` and the `WorkflowRun` enters `waiting_approval`. After Human Root approves the linked approval, `POST /tasks/{task_id}/resume` continues the same workflow run through document writing, risk check, quality check, memory write, knowledge write, evaluation, and completion. Resume is rejected for pending, rejected, blocked, or non-waiting tasks.
