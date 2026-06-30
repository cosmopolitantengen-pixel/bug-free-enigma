# MODELS

## Gateway Boundary

The Model Gateway is the only place where Agents and Workflows request generation. The Embedding Gateway is the only place where Knowledge text becomes a vector. Provider credentials, request formats, timeouts, response parsing, token usage, and error sanitization stay behind these two boundaries.

## Providers

The default remains offline and deterministic:

- `AI_COMPANY_OS_MODEL_PROVIDER=local`
- model `deterministic_mock_v1`
- `AI_COMPANY_OS_EMBEDDING_PROVIDER=disabled`
- lexical Knowledge search remains active

The `openai` adapters use the OpenAI Responses and Embeddings APIs. Requests set `store=false` for generated responses, embedding requests explicitly ask for 1536 float dimensions, and API keys are read from `OPENAI_API_KEY` or `OPENAI_API_KEY_FILE`. The implementation follows the official [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) and [Embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create) references.

The native `deepseek` adapter uses the official OpenAI-compatible Chat Completions endpoint without pretending that it is an OpenAI Responses endpoint. Credentials come from `DEEPSEEK_API_KEY` or `DEEPSEEK_API_KEY_FILE`. The supported V4 defaults and request shape follow the official [DeepSeek quick start](https://api-docs.deepseek.com/zh-cn/) and [model list](https://api-docs.deepseek.com/api/list-models/).

```text
AI_COMPANY_OS_MODEL_PROVIDER=openai
AI_COMPANY_OS_MODEL_NAME=gpt-4.1-mini
AI_COMPANY_OS_ALLOWED_MODELS=gpt-4.1-mini
AI_COMPANY_OS_EMBEDDING_PROVIDER=openai
AI_COMPANY_OS_EMBEDDING_MODEL=text-embedding-3-small
AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS=60
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=...
```

For DeepSeek as the primary generator with an explicit OpenAI/local fallback order:

```text
AI_COMPANY_OS_MODEL_PROVIDER=deepseek
AI_COMPANY_OS_DEEPSEEK_MODEL=deepseek-v4-flash
AI_COMPANY_OS_DEEPSEEK_ALLOWED_MODELS=deepseek-v4-flash,deepseek-v4-pro
AI_COMPANY_OS_MODEL_FALLBACKS=openai,local
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=...
OPENAI_API_KEY=...
```

Fallback is disabled by default. Every provider named in `AI_COMPANY_OS_MODEL_FALLBACKS` must be configured at startup. The gateway tries the requested provider first, then each configured fallback with that provider's default allowlisted model. It records the requested provider, attempted providers, actual provider, and whether fallback occurred. Local fallback must therefore be selected deliberately; the system never silently substitutes deterministic output for a failed live model.

DeepSeek V4 pricing is calculated separately for input and output tokens. Defaults match the official [DeepSeek pricing page](https://api-docs.deepseek.com/quick_start/pricing) as checked on 2026-06-29 and can be overridden with the four `AI_COMPANY_OS_DEEPSEEK_*_PER_MILLION` settings when prices change. Pre-call budget checks conservatively use the highest configured rate across the selected route and its fallbacks.

`OPENAI_BASE_URL` and `DEEPSEEK_BASE_URL` are Root-managed deployment configuration, must be absolute HTTP(S) URLs, and cannot contain credentials. Provider names and model names may be selected per manual model request only from adapters and the comma-separated model allowlist configured at process startup. The configured default model is always included.

## Controls

Before every generation or embedding request, the Budget Guard evaluates estimated tokens and cost. Generation requests also receive a hard `max_output_tokens` cap derived from the smallest remaining per-call, total-token, and cost allowance. Successful calls write `ModelUsageRecord`, `CostLog`, and Audit records. Prompts and outputs are represented by SHA-256 references rather than raw content in usage and audit records.

Generation failures write a failed CostLog, `model_failed` Audit event, and Incident before returning a sanitized provider error. Embedding failures write `embedding_failed` or `embedding_blocked`, create an Incident, and leave lexical Knowledge search available.

The Next.js chat workspace sends ordinary conversation turns through this same generation boundary. It sends a bounded recent transcript, keeps conversation text in browser-local storage, and renders routing/usage/cost metadata from the response. Explicit operational language can instead produce a deterministic, audited Workflow proposal; proposal generation does not spend model tokens or create a task, and Human Root must confirm it before the normal Workflow boundary runs. Provider credentials remain server-side; the browser never receives or stores `DEEPSEEK_API_KEY` or `OPENAI_API_KEY`.

Knowledge documents are persisted before their vectors are inserted, preserving the PostgreSQL foreign-key boundary. Existing or failed documents can be rebuilt by Human Root through `POST /knowledge/embeddings/reindex`.

## API

- `POST /models/generate`
- `GET /models/providers`
- `GET /model-usage`
- `GET /cost-logs`
- `GET /budget/summary`
- `POST /knowledge/search`
- `GET /knowledge/embeddings/status`
- `POST /knowledge/embeddings/reindex`
