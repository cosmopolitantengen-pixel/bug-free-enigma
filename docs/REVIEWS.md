# REVIEWS

## Purpose

Task Reviews are the first retrospective loop for AI Company OS. They turn completed or interrupted work into reusable learning instead of leaving lessons buried in audit logs.

## Current Implementation

The implementation stores `TaskReview` records with:

- task id
- reviewer Agent
- outcome
- summary
- what went well
- what went wrong
- lessons
- follow-up actions
- quality score from 0 to 1
- risk level

Recording a review also writes:

- a `MemoryRecord` with `memory_type=review`
- a `KnowledgeDoc` titled with the task review lessons
- a `task_review_recorded` audit event
- optional review-driven improvement proposals through the controlled evolution flow

## API

```text
GET /task-reviews
GET /task-reviews?task_id={task_id}
GET /task-reviews?reviewer_agent={agent_id}
POST /task-reviews
POST /task-reviews/{review_id}/improvements
GET /improvement-proposals
POST /improvement-proposals/{proposal_id}/sandbox
POST /improvement-proposals/{proposal_id}/register
```

## Improvement Proposals

Improvement proposals are generated from review lessons and follow-up actions. They must pass Human Root approval and deterministic sandbox checks before registration. Registration currently creates a knowledge document that captures the approved change intent; it does not automatically edit code or enable new high-risk behavior.

## Persistence

SQLite stores review payloads in `task_reviews` and review-driven improvement proposals in `improvement_proposals`. Review memory, knowledge docs, and audit events are persisted through their existing tables.

## Dashboard

The static dashboard includes a Task Reviews panel for recording retrospectives, creating improvement proposals from review records, and viewing recent review records. The dashboard summary exposes review count, average review score, and improvement proposal count.
