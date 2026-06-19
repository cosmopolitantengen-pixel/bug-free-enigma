# DEPLOYMENT

## V1 Local Development

Start with a local deterministic core and tests. Add services in this order:

1. FastAPI backend
2. SQLite local persistence
3. PostgreSQL persistence
4. Redis queue
5. Next.js dashboard
6. Docker Compose
7. pgvector memory search

Current local persistence can be enabled with:

```text
AI_COMPANY_OS_SQLITE_PATH=E:\1\data\company_os.db
```

This is suitable for first local development only. SQLite currently enforces local audit append-only behavior with triggers, while production should use PostgreSQL with equivalent append-only audit guarantees.

## Deployment Rules

- Production requires append-only audit storage.
- Secrets must not be stored in source code.
- Model and tool credentials require Root-managed configuration.
- Risk and approval services must start before any high-risk tool adapter is enabled.
- Dangerous tool adapters are disabled by default.
