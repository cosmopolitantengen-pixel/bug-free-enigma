# GOALS

## Purpose

Strategic Goals are the first OKR-style layer above individual tasks. They give the AI CEO and Human Root a way to express operating intent, track progress, and connect execution evidence back to the larger objective.

## Current Model

Each strategic goal stores:

- title and description
- owner Agent
- target metric
- target value
- current value
- status
- linked task ids
- linked review ids
- linked improvement proposal ids

Progress is reported as `current_value / target_value`. If progress reaches the target and no explicit status is supplied, the goal becomes `completed`.

## API

```text
GET /goals
GET /goals?status=active
GET /goals?owner_agent=ceo_agent_v1
POST /goals
POST /goals/{goal_id}/progress
POST /goals/{goal_id}/tasks/{task_id}
POST /goals/{goal_id}/reviews/{review_id}
POST /goals/{goal_id}/improvements/{proposal_id}
```

## Chat Entry Point

Human Root can create a goal from chat with messages such as `set goal: ...` or `设置目标：...`. The chat layer creates an audited confirmation card with `kind=strategic_goal`; no goal is written until Human Root confirms the action. Pending goal cards are persisted with the chat session and can be confirmed after a backend restart. Ordinary chat prompts include a compact list of active goals so the assistant can keep long-running operating intent in context.

When an active goal exists, newly created Workflow tasks are automatically linked to the most recently updated active goal. This includes ordinary confirmed chat actions and each task created by a governed Agent Run step. The link writes the same `strategic_goal_linked` audit event as manual goal linking.

Messages such as `下一步`, `继续目标`, `推进目标`, or `continue goal` use the current active goal as the objective. With a configured non-local model provider, chat creates a governed Agent Run confirmation card for the goal. With the local deterministic provider, chat falls back to a controlled task-planning proposal instead of pretending to run a model-driven Agent.

## Audit

Goal creation writes `strategic_goal_created`.

Goal progress writes `strategic_goal_progress_updated`.

Goal links write `strategic_goal_linked`.

## Dashboard

The Next.js operations console reads `GET /goals`, shows strategic goal counts in Overview, and lists recent goals with linked task counts. The static dashboard includes a Strategic Goals panel near task creation. Human Root can create goals, update progress, and link task, review, or improvement records to a goal.
