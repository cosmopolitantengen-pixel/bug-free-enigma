from __future__ import annotations

from app.core.enums import IncidentStatus
from app.core.models import Incident, utc_now


class IncidentStore:
    def __init__(self, incidents: list[Incident] | None = None) -> None:
        self._incidents: dict[str, Incident] = {incident.incident_id: incident for incident in incidents or []}

    def report(self, incident: Incident) -> Incident:
        self._incidents[incident.incident_id] = incident
        return incident

    def get(self, incident_id: str) -> Incident:
        return self._incidents[incident_id]

    def list(self) -> list[Incident]:
        return list(self._incidents.values())

    def acknowledge(self, incident_id: str, actor_id: str, note: str | None = None) -> Incident:
        incident = self._incidents[incident_id]
        if incident.status == IncidentStatus.RESOLVED:
            raise ValueError("resolved incident cannot be acknowledged")
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = utc_now()
        incident.acknowledged_by = actor_id
        if note:
            incident.resolution_note = note
        return incident

    def resolve(self, incident_id: str, actor_id: str, note: str) -> Incident:
        incident = self._incidents[incident_id]
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = utc_now()
        incident.resolved_by = actor_id
        incident.resolution_note = note
        return incident
