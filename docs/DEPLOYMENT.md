# DEPLOYMENT

## Local Development

The deterministic core can run in memory or on SQLite. PostgreSQL/pgvector is the production persistence backend. Redis/RQ carries production scheduler deliveries while PostgreSQL remains the source of truth.

1. FastAPI backend
2. SQLite local persistence
3. PostgreSQL persistence (implemented)
4. pgvector Knowledge indexing and semantic search (implemented)
5. Docker Compose (implemented for web, backend, PostgreSQL, and Redis)
6. Redis worker queue (implemented for scheduled execution)
7. Next.js operations console (implemented)

Current local persistence can be enabled with:

```text
AI_COMPANY_OS_SQLITE_PATH=E:\1\data\company_os.db
```

This is suitable for local development only. SQLite enforces local audit append-only behavior with triggers.

For PostgreSQL, install `backend/requirements.txt` and configure:

```text
AI_COMPANY_OS_DATABASE_URL=postgresql://user:password@localhost:5432/ai_company_os
```

Do not configure the SQLite path and PostgreSQL URL together. The PostgreSQL store automatically applies three idempotent migrations: JSONB state storage and restore ledger, append-only audit/domain-event triggers, and pgvector knowledge embeddings with an HNSW cosine index.

To start the current production service foundation:

```text
docker compose --env-file .env up --build
```

Create `.env` from `.env.example` and replace the default database password first. The operations console is exposed on `http://localhost:3000` and the API on `http://localhost:8000` by default. Compose also starts the scheduler dispatcher and RQ worker. Set `NEXT_PUBLIC_API_BASE` to the browser-reachable API origin before building for a remote deployment.

For any non-local deployment, enable the HTTP auth gate:

```text
AI_COMPANY_OS_AUTH_REQUIRED=true
AI_COMPANY_OS_API_TOKEN_SHA256=<sha256 hex digest of your operator token>
```

`AI_COMPANY_OS_API_TOKEN` is also supported for secret-manager backed environments, but the SHA-256 digest form avoids storing the raw token in application config. When auth is required, only `GET /health` and `POST /auth/login` are public; all other API calls require `Authorization: Bearer <token>`. Operators can enter the token in the Next.js console System page. Do not put API tokens in `NEXT_PUBLIC_*` build variables because those are visible to the browser.

Local user logins issue expiring bearer sessions. The default session TTL is eight hours; adjust it explicitly for your environment:

```text
AI_COMPANY_OS_SESSION_TTL_SECONDS=28800
```

Secrets can be supplied directly or through Docker/Kubernetes-style file variables. Do not set both forms for the same secret:

```text
AI_COMPANY_OS_API_TOKEN_FILE=/run/secrets/ai_company_os_api_token
AI_COMPANY_OS_API_TOKEN_SHA256_FILE=/run/secrets/ai_company_os_api_token_sha256
AI_COMPANY_OS_DATABASE_URL_FILE=/run/secrets/ai_company_os_database_url
AI_COMPANY_OS_REDIS_URL_FILE=/run/secrets/ai_company_os_redis_url
OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
DEEPSEEK_API_KEY_FILE=/run/secrets/deepseek_api_key
GITHUB_TOKEN_FILE=/run/secrets/github_token
AI_COMPANY_OS_ALERT_WEBHOOK_URL_FILE=/run/secrets/incident_alert_webhook
```

Optional outbound alert delivery can be enabled for service-reported Incidents:

```text
AI_COMPANY_OS_ALERTS_ENABLED=true
AI_COMPANY_OS_ALERT_WEBHOOK_URL=https://alerts.example/webhook
AI_COMPANY_OS_ALERT_TIMEOUT_SECONDS=5
```

Keep webhook URLs in deployment secrets. The API exposes only alert status and endpoint host through `GET /alerts/status`; delivery success and failure are written to Audit.

Operational runbooks are available through `GET /runbooks` and are attached to Incident responses. Treat them as the first response checklist before retrying failed schedules, provider calls, blocked actions, or restore operations.

Before exposing the service, check `GET /deployment/readiness` from an authenticated operator session. It is stricter than `/health`: local memory state, disabled API auth, missing Redis/RQ queue configuration, missing audit guards, or embedding/vector-store mismatches are reported as readiness blockers or warnings without exposing secret values.

Live provider calls remain disabled until a provider credential and matching `AI_COMPANY_OS_MODEL_PROVIDER` are configured. Use `DEEPSEEK_API_KEY` with `deepseek`, or `OPENAI_API_KEY` with `openai`; OpenAI remains separately configurable for embeddings. `AI_COMPANY_OS_MODEL_FALLBACKS` may name only providers whose credentials are present. The same provider, fallback, model, and pricing settings are passed to the API, scheduler dispatcher, and worker so scheduled Workflows use the same controlled gateways. Keep API keys in deployment secrets, never in the committed `.env.example` or image layers.

The optional PostgreSQL integration test requires a dedicated database because it applies migrations and writes a knowledge fixture:

```text
AI_COMPANY_OS_TEST_POSTGRES_URL=postgresql://user:password@localhost:5432/ai_company_os_test
python -m unittest backend.tests.test_postgres_integration
```

## Deployment Rules

- Production requires append-only audit storage.
- Secrets must not be stored in source code.
- API auth must be enabled before exposing the backend outside a trusted local network.
- `GET /deployment/readiness` must be reviewed before a production cutover.
- `python scripts/release_gate.py` must pass before tagging or deploying a release.
- Alert webhook URLs must be supplied through deployment secrets, never committed files.
- Model and tool credentials require Root-managed configuration.
- Risk and approval services must start before any high-risk tool adapter is enabled.
- Dangerous tool adapters are disabled by default.
- PostgreSQL deployments require the `vector` extension; the Compose image includes it.
