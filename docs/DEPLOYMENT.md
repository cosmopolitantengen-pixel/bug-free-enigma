# DEPLOYMENT

## Local Development

The deterministic core can run in memory or on SQLite. PostgreSQL/pgvector is the production persistence backend. Redis/RQ carries production scheduler deliveries while PostgreSQL remains the source of truth.

1. FastAPI backend
2. SQLite local persistence
3. PostgreSQL persistence (implemented)
4. pgvector knowledge search (implemented at the persistence boundary)
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

The optional PostgreSQL integration test requires a dedicated database because it applies migrations and writes a knowledge fixture:

```text
AI_COMPANY_OS_TEST_POSTGRES_URL=postgresql://user:password@localhost:5432/ai_company_os_test
python -m unittest backend.tests.test_postgres_integration
```

## Deployment Rules

- Production requires append-only audit storage.
- Secrets must not be stored in source code.
- Model and tool credentials require Root-managed configuration.
- Risk and approval services must start before any high-risk tool adapter is enabled.
- Dangerous tool adapters are disabled by default.
- PostgreSQL deployments require the `vector` extension; the Compose image includes it.
