from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from app.core.models import Incident
from app.secrets import read_secret
from app.services.serializers import to_plain


AlertTransport = Callable[[str, dict[str, Any], float], int]


class AlertConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class AlertSettings:
    enabled: bool = False
    webhook_url: str | None = None
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "AlertSettings":
        timeout = float(os.environ.get("AI_COMPANY_OS_ALERT_TIMEOUT_SECONDS", "5"))
        return cls(
            enabled=_truthy(os.environ.get("AI_COMPANY_OS_ALERTS_ENABLED")),
            webhook_url=read_secret("AI_COMPANY_OS_ALERT_WEBHOOK_URL"),
            timeout_seconds=timeout,
        )

    def validate(self) -> None:
        if self.timeout_seconds <= 0 or self.timeout_seconds > 30:
            raise AlertConfigurationError(
                "AI_COMPANY_OS_ALERT_TIMEOUT_SECONDS must be greater than 0 and at most 30"
            )
        if not self.enabled:
            return
        if not self.webhook_url:
            raise AlertConfigurationError(
                "AI_COMPANY_OS_ALERTS_ENABLED requires AI_COMPANY_OS_ALERT_WEBHOOK_URL"
            )
        parsed = urllib.parse.urlparse(self.webhook_url)
        if parsed.scheme != "https" and not _is_loopback_http(parsed):
            raise AlertConfigurationError(
                "AI_COMPANY_OS_ALERT_WEBHOOK_URL must use https, except loopback http for tests"
            )
        if not parsed.netloc:
            raise AlertConfigurationError("AI_COMPANY_OS_ALERT_WEBHOOK_URL must include a host")

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    @property
    def endpoint_host(self) -> str | None:
        if not self.webhook_url:
            return None
        parsed = urllib.parse.urlparse(self.webhook_url)
        return parsed.netloc or None


@dataclass(frozen=True)
class AlertDeliveryResult:
    status: str
    destination: str | None = None
    http_status: int | None = None
    error: str | None = None


class AlertDispatcher:
    def __init__(
        self,
        settings: AlertSettings | None = None,
        transport: AlertTransport | None = None,
    ) -> None:
        self.settings = settings or AlertSettings.from_env()
        self.settings.validate()
        self._transport = transport or _post_json

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.enabled,
            "configured": self.settings.configured,
            "destination": "webhook" if self.settings.configured else None,
            "endpoint_host": self.settings.endpoint_host if self.settings.configured else None,
            "timeout_seconds": self.settings.timeout_seconds,
        }

    def send_incident(self, incident: Incident) -> AlertDeliveryResult:
        if not self.settings.configured or not self.settings.webhook_url:
            return AlertDeliveryResult(status="disabled")
        payload = {
            "event_type": "incident.opened",
            "system": "AI Company OS",
            "incident": _incident_payload(incident),
        }
        try:
            http_status = self._transport(
                self.settings.webhook_url,
                payload,
                self.settings.timeout_seconds,
            )
        except Exception as exc:
            return AlertDeliveryResult(
                status="failed",
                destination="webhook",
                error=f"{exc.__class__.__name__}: {exc}",
            )
        if http_status < 200 or http_status >= 300:
            return AlertDeliveryResult(
                status="failed",
                destination="webhook",
                http_status=http_status,
                error=f"webhook returned HTTP {http_status}",
            )
        return AlertDeliveryResult(
            status="sent",
            destination="webhook",
            http_status=http_status,
        )


def _incident_payload(incident: Incident) -> dict[str, Any]:
    payload = to_plain(incident)
    return {
        "incident_id": payload["incident_id"],
        "title": payload["title"],
        "description": payload["description"],
        "source_type": payload["source_type"],
        "source_id": payload["source_id"],
        "risk_level": payload["risk_level"],
        "status": payload["status"],
        "task_id": payload.get("task_id"),
        "actor_id": payload.get("actor_id"),
        "recommendation": payload.get("recommendation"),
        "created_at": payload["created_at"],
    }


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: float) -> int:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_loopback_http(parsed: urllib.parse.ParseResult) -> bool:
    if parsed.scheme != "http":
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}
