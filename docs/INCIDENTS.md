# INCIDENTS

## Purpose

Incident Management turns blocked or operationally risky events into visible follow-up work. It is not an escape hatch around Permission, Risk, Approval, or Budget controls.

## Current Incident Sources

- Blocked approval requests
- Blocked Tool Run requests
- Blocked Workflow task runs
- Model calls blocked by the Budget Guard
- Failed schedules and provider failures

## Incident Lifecycle

1. The service reports an incident with source context, risk level, task or actor context when available, and a recommendation.
2. If outbound alerts are enabled, service-reported Incidents send a sanitized payload to the configured webhook.
3. The service matches the Incident to an operational runbook with immediate actions, verification steps, owner Agent, and escalation policy.
4. Alert delivery success or failure writes an audit event and never blocks Incident creation.
5. Human Root or an operator acknowledges the incident.
6. Human Root or an operator resolves the incident with an optional note.
7. Acknowledgement and resolution write audit events.

## Optional Alert Delivery

Alert delivery is disabled by default. Enable it only in deployment secrets:

```text
AI_COMPANY_OS_ALERTS_ENABLED=true
AI_COMPANY_OS_ALERT_WEBHOOK_URL=https://alerts.example/webhook
AI_COMPANY_OS_ALERT_TIMEOUT_SECONDS=5
```

The webhook receives `event_type=incident.opened`, system name, and selected Incident fields. The API exposes only the webhook host through `GET /alerts/status`, never the full URL.

## Runbooks

The runbook catalog is code-owned and deterministic. It currently covers:

- General incident triage
- Safety control blocks
- Scheduler and queue failures
- Model and embedding provider failures
- Budget guard blocks
- Backup integrity failures

Incident API responses include `runbook_id`, `runbook_title`, and a nested `runbook` object. Use `GET /runbooks` to list the catalog and `GET /incidents/{incident_id}/runbook` to retrieve the matched response plan for one Incident.

## API

```text
GET /incidents
GET /alerts/status
GET /runbooks
GET /incidents/{incident_id}/runbook
POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/resolve
```

## Persistence

Incidents are stored by the local SQLite adapter in `backend/app/persistence/sqlite_store.py` and are included in service reloads.

## Dashboard

The dashboards show incident counts, open incident counts, recent incidents with matched runbook guidance, the runbook catalog, alert delivery status, and action buttons for acknowledgement and resolution.
