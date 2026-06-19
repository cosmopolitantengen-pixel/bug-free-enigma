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

## Audit

Goal creation writes `strategic_goal_created`.

Goal progress writes `strategic_goal_progress_updated`.

Goal links write `strategic_goal_linked`.

## Dashboard

The static dashboard includes a Strategic Goals panel near task creation. Human Root can create goals, update progress, and link task, review, or improvement records to a goal.
