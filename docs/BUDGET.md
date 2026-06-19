# BUDGET

## Budget Guard Definition

The Budget Guard checks model calls before generation. It prevents model usage from growing without a policy boundary and records cost outcomes for later review.

## Current Policy

The local default policy is deterministic and simple:

- max tokens per call: `2000`
- max total tokens: `100000`
- max estimated cost: `10.0`
- cost per token: `0.000001`
- currency: `USD`

Human Root can update the active policy through the API or static dashboard. Policy updates are audited and persisted by SQLite.

## Current Flow

1. A model call request enters `ModelGateway`.
2. Budget Guard estimates prompt and completion tokens.
3. If the request exceeds per-call, total-token, or estimated-cost limits, the call is blocked.
4. Allowed calls write `ModelUsageRecord`, `CostLog`, and `model_called` audit events.
5. Blocked calls write a blocked `CostLog` and a `model_blocked` audit event.

## Current API

- `GET /budget/summary`
- `POST /budget/policy`
- `GET /cost-logs`

Budget data is also included in `GET /dashboard/summary` and rendered in the static dashboard.
