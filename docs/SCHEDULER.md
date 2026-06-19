# SCHEDULER AND EVENT BUS

## Purpose

The scheduler gives AI Company OS a durable way to trigger internal work. The event bus records append-only domain events for schedule lifecycle and execution outcomes.

## Supported Actions

- `create_task`: create a new task from a title and description.
- `run_task`: run an existing task through the document workflow.

Schedule creation is an internal write operation. Human Root may create and control any schedule; an Agent may create a schedule only within its normal internal-write permission boundary. Only Human Root can tick the scheduler in the current implementation.

## Timing Rules

- `next_run_at` and tick `now` values must include a timezone and are normalized to UTC.
- A schedule without `interval_seconds` is one-time.
- Recurring intervals must be at least 60 seconds.
- `max_runs` limits total attempts, including failures.
- A tick executes each due schedule at most once. A recurring job advances from the tick time, so a delayed worker does not create a catch-up burst.
- Failed one-time jobs become `failed`; failed recurring jobs stay active until their run limit is reached.

The current scheduler is deterministic and worker-neutral. It stores jobs and exposes an explicit tick endpoint; a future Redis worker or process supervisor can call that endpoint or the same service method on a cadence.

## API

```text
GET /events
GET /schedules
POST /schedules
POST /schedules/{schedule_id}/pause
POST /schedules/{schedule_id}/resume
POST /schedules/{schedule_id}/cancel
GET /scheduler/executions
POST /scheduler/tick
```

## Safety And History

- Schedule creation, state changes, ticks, and executions write audit events.
- Schedule lifecycle and execution outcomes publish domain events.
- Failed execution creates an incident for Human Root follow-up.
- Domain events are append-only at the SQLite layer.
- Jobs, executions, and events survive SQLite reload.
- Backups include scheduled job state. Restore preserves domain-event and execution history.
