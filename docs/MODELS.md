# MODELS

## Model Gateway Definition

The Model Gateway is the only place where Agents and Workflows should request model generation. This keeps model calls auditable, measurable, and replaceable.

## Current Implementation

The first gateway is deterministic and local:

- provider: `local`
- model: `deterministic_mock_v1`
- cost: estimated from token count and the active budget policy cost-per-token
- token counts: simple estimated prompt/completion/total tokens

It is intentionally not a live provider adapter yet. Real model providers should be added only after privacy, budget, approval, and audit rules are covered by tests.

## Current Records

Every model call writes a `ModelUsageRecord` with:

- `model_name`
- `provider`
- `actor_id`
- `task_id`
- `purpose`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `estimated_cost`
- `input_ref`
- `output_ref`

Before generation, the Budget Guard checks per-call token, total-token, and estimated-cost limits. Allowed calls write a `CostLog` and a `model_called` audit event. Blocked calls write a blocked `CostLog` and a `model_blocked` audit event.

## Current API

- `POST /models/generate`
- `GET /model-usage`
- `GET /cost-logs`
- `GET /budget/summary`

The document generation workflow now uses the gateway for its deterministic document output, so workflow runs create model usage records automatically.
