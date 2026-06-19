# COMMUNICATION

## Purpose

Agent Communication records internal coordination without bypassing Human Root control. Messages and meetings are stored, auditable, and available to the dashboard.

## Current Records

Agent messages include:

- `message_id`
- `task_id`
- `from_agent`
- `to_agent`
- `message_type`
- `content`
- `priority`
- `requires_response`
- `created_at`

Agent meetings include:

- `meeting_id`
- `task_id`
- `title`
- `organizer_agent`
- `participant_agents`
- `agenda`
- `meeting_type`
- `minutes`
- `created_at`

Task handoffs include:

- `handoff_id`
- `task_id`
- `from_agent`
- `to_agent`
- `reason`
- `instructions`
- `task_status`
- `message_id`
- `created_at`

Agent broadcasts include:

- `broadcast_id`
- `task_id`
- `from_agent`
- `audience_agents`
- `event_type`
- `title`
- `content`
- `priority`
- `created_at`

Agent conflicts include:

- `conflict_id`
- `task_id`
- `raised_by_agent`
- `opposing_agents`
- `issue`
- `positions`
- `priority_area`
- `status`
- `resolution`
- `resolved_by`
- `selected_position_agent`
- `created_at`
- `resolved_at`

## API

```text
GET /agent-messages
POST /agent-messages
GET /agent-meetings
POST /agent-meetings
GET /task-handoffs
POST /tasks/{task_id}/handoff
GET /agent-broadcasts
POST /agent-broadcasts
GET /agent-conflicts
POST /agent-conflicts
POST /agent-conflicts/{conflict_id}/resolve
```

`GET /agent-messages` can filter by `agent_id` or `task_id`. `GET /agent-meetings` can filter by `task_id`.
`GET /task-handoffs` can filter by `task_id` or `agent_id`.
`GET /agent-broadcasts` can filter by `task_id`, `agent_id`, or `event_type`.
`GET /agent-conflicts` can filter by `task_id`, `agent_id`, or `status`.

## Safety Rules

- Sender, receiver, organizer, and meeting participants must be known Agents.
- Empty message content is rejected.
- Empty meeting title, agenda, or participants are rejected.
- Task handoffs validate the task, sender Agent, receiver Agent, risk policy, and internal-write permission.
- Broadcasts validate sender Agent, audience Agents, optional task, risk policy, and internal-write permission.
- Conflicts validate the raising Agent, opposing Agents, positions, optional task, risk policy, and internal-write permission.
- Conflict resolution can be made by Human Root or an Agent with internal-write permission.
- Message and meeting creation write audit events.
- Task handoff creation writes a linked `handoff` message and an audit event.
- Broadcast creation writes an audit event.
- Conflict opening and resolution write audit events.
- Communication records are included in state backups.

## Arbitration Priority

The current priority areas are:

```text
safety > compliance > privacy > user_confirmation > quality > cost > efficiency
```

The first implementation records the selected `priority_area` for the conflict. It does not automatically override Human Root.

## Current Audit Events

- `agent_message_sent`
- `agent_meeting_recorded`
- `task_handoff_recorded`
- `task_handoff_blocked`
- `agent_broadcast_sent`
- `agent_broadcast_blocked`
- `agent_conflict_opened`
- `agent_conflict_resolved`
- `agent_conflict_blocked`
- `agent_conflict_resolution_blocked`

## Current Limits

Task handoff is implemented as an auditable internal transfer record plus a linked Agent message. Event broadcast is implemented as an auditable internal event stream for multiple Agents. Conflict arbitration is implemented as an auditable open/resolve flow with recorded positions and priority area.
