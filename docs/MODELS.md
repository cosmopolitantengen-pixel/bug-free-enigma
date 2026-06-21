# MODELS

## Gateway Boundary

The Model Gateway is the only place where Agents and Workflows request generation. The Embedding Gateway is the only place where Knowledge text becomes a vector. Provider credentials, request formats, timeouts, response parsing, token usage, and error sanitization stay behind these two boundaries.

## Providers

The default remains offline and deterministic:

- `AI_COMPANY_OS_MODEL_PROVIDER=local`
- model `deterministic_mock_v1`
- `AI_COMPANY_OS_EMBEDDING_PROVIDER=disabled`
- lexical Knowledge search remains active

The `openai` adapters use the OpenAI Responses and Embeddings APIs. Requests set `store=false` for generated responses, embedding requests explicitly ask for 1536 float dimensions, and API keys are read only from `OPENAI_API_KEY`. The implementation follows the official [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) and [Embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create) references.

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

`OPENAI_BASE_URL` is Root-managed deployment configuration, must be an absolute HTTP(S) URL, and cannot contain credentials. Provider names and model names may be selected per manual model request only from adapters and the comma-separated model allowlist configured at process startup. The configured default model is always included.

## Controls

Before every generation or embedding request, the Budget Guard evaluates estimated tokens and cost. Generation requests also receive a hard `max_output_tokens` cap derived from the smallest remaining per-call, total-token, and cost allowance. Successful calls write `ModelUsageRecord`, `CostLog`, and Audit records. Prompts and outputs are represented by SHA-256 references rather than raw content in usage and audit records.

Generation failures write a failed CostLog, `model_failed` Audit event, and Incident before returning a sanitized provider error. Embedding failures write `embedding_failed` or `embedding_blocked`, create an Incident, and leave lexical Knowledge search available.

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
