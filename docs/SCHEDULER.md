# SCHEDULER AND EVENT BUS

## Purpose

The scheduler gives AI Company OS a durable way to trigger internal work. The event bus records append-only domain events for schedule lifecycle and execution outcomes.

## Supported Actions

- `create_task`: create a new task from a title and description.
- `run_task`: run an existing task through the document workflow.

Schedule creation is an internal write operation. Human Root may create and control any schedule; an Agent may create a schedule only within its normal internal-write permission boundary. Only Human Root can tick the scheduler or execute a queued delivery.

## Timing Rules

- `next_run_at` and tick `now` values must include a timezone and are normalized to UTC.
- A schedule without `interval_seconds` is one-time.
- Recurring intervals must be at least 60 seconds.
- `max_runs` limits total attempts, including failures.
- A tick executes each due schedule at most once. A recurring job advances from the tick time, so a delayed worker does not create a catch-up burst.
- Failed one-time jobs become `failed`; failed recurring jobs stay active until their run limit is reached.

Local mode exposes an explicit deterministic tick endpoint. Production mode uses two additional processes:

- `scheduler-dispatcher` scans durable PostgreSQL state and enqueues each due occurrence into Redis/RQ with a deterministic delivery ID.
- `scheduler-worker` consumes the queue, reloads current PostgreSQL state, validates the queued due timestamp, executes the job, and persists the result before RQ acknowledges it.

RQ retries infrastructure failures three times. Replayed deliveries are harmless: the schedule must still be active at the exact queued `next_run_at`, and scheduled task creation uses a deterministic task ID for that occurrence.

## Queue Health

`GET /scheduler/queue-health` reports Redis/RQ transport health without exposing the Redis URL or credentials. It returns whether Redis is configured, the queue name, Redis ping status, registered worker count, queued/started/deferred/scheduled/failed job counts, and a small sample of job IDs for follow-up.

Health status is:

- `disabled` when Redis is not configured.
- `ok` when the queue is reachable and workers are registered.
- `warning` when Redis is reachable but no workers are registered.
- `critical` when the queue cannot be checked or failed jobs are present.

## API

```text
GET /events
GET /schedules
POST /schedules
POST /schedules/{schedule_id}/pause
POST /schedules/{schedule_id}/resume
POST /schedules/{schedule_id}/cancel
GET /scheduler/executions
GET /scheduler/queue-health
POST /scheduler/tick
```

## Safety And History

- Schedule creation, state changes, ticks, and executions write audit events.
- Schedule lifecycle and execution outcomes publish domain events.
- Failed execution creates an incident for Human Root follow-up.
- Queue health exposes worker/backlog/failure metrics for operations follow-up; PostgreSQL schedule state remains the execution source of truth.
- Domain events are append-only at the SQLite and PostgreSQL layers.
- Jobs, executions, and events survive SQLite or PostgreSQL reload.
- Backups include scheduled job state. Restore preserves domain-event and execution history.
- Redis is transport, not source of truth; PostgreSQL schedule state decides whether a delivery may execute.
