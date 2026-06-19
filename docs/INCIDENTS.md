# INCIDENTS

## Purpose

Incident Management turns blocked or operationally risky events into visible follow-up work. It is not an escape hatch around Permission, Risk, Approval, or Budget controls.

## Current Incident Sources

- Blocked approval requests
- Blocked Tool Run requests
- Blocked Workflow task runs
- Model calls blocked by the Budget Guard

## Incident Lifecycle

1. The service reports an incident with source context, risk level, task or actor context when available, and a recommendation.
2. Human Root or an operator acknowledges the incident.
3. Human Root or an operator resolves the incident with an optional note.
4. Acknowledgement and resolution write audit events.

## API

```text
GET /incidents
POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/resolve
```

## Persistence

Incidents are stored by the local SQLite adapter in `backend/app/persistence/sqlite_store.py` and are included in service reloads.

## Dashboard

The static dashboard shows incident counts, open incident counts, recent incidents, and action buttons for acknowledgement and resolution.
