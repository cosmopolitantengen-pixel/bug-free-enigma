from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.secrets import secret_configured


def deployment_readiness(service: Any, scheduler_queue: dict[str, Any]) -> dict[str, Any]:
    checks = [
        _auth_check(service),
        _persistence_check(service),
        _schema_check(service),
        _audit_guard_check(service),
        _scheduler_queue_check(scheduler_queue),
        _alert_delivery_check(service),
        _model_provider_check(service),
        _embedding_check(service),
        _runbook_check(service),
        _operator_backlog_check(service),
    ]
    critical_count = len([check for check in checks if check["status"] == "critical"])
    warning_count = len([check for check in checks if check["status"] == "warning"])
    if critical_count:
        status = "not_ready"
    elif warning_count:
        status = "warning"
    else:
        status = "ready"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "check_count": len(checks),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "checks": checks,
    }


def _auth_check(service: Any) -> dict[str, Any]:
    required = _truthy(os.environ.get("AI_COMPANY_OS_AUTH_REQUIRED"))
    has_static_token = secret_configured("AI_COMPANY_OS_API_TOKEN") or secret_configured("AI_COMPANY_OS_API_TOKEN_SHA256")
    has_users = bool(getattr(service.auth, "has_users")())
    configured = has_static_token or has_users
    if required and configured:
        status = "ok"
        message = "HTTP bearer auth is required and at least one credential source is configured."
    elif required:
        status = "critical"
        message = "HTTP auth is required but no API token, token digest, or persisted user exists."
    else:
        status = "critical"
        message = "HTTP auth is disabled; do not expose the backend outside a trusted local network."
    return {
        "name": "http_auth_gate",
        "status": status,
        "required_for_production": True,
        "message": message,
        "details": {
            "auth_required": required,
            "static_token_configured": has_static_token,
            "persisted_user_configured": has_users,
        },
    }


def _persistence_check(service: Any) -> dict[str, Any]:
    schema = service.database_schema()
    backend = schema["backend"]
    if backend == "postgresql":
        status = "ok"
        message = "PostgreSQL persistence is configured."
    elif backend == "sqlite":
        status = "warning"
        message = "SQLite persistence is configured; use PostgreSQL for shared production services."
    else:
        status = "critical"
        message = "The service is running with in-memory state; production needs durable persistence."
    return {
        "name": "production_persistence",
        "status": status,
        "required_for_production": True,
        "message": message,
        "details": {
            "backend": backend,
            "schema_version": schema["schema_version"],
        },
    }


def _schema_check(service: Any) -> dict[str, Any]:
    return _integrity_named_check(
        service,
        "schema_version",
        "database_schema",
        required_for_production=True,
    )


def _audit_guard_check(service: Any) -> dict[str, Any]:
    return _integrity_named_check(
        service,
        "audit_append_only_storage",
        "audit_append_only_storage",
        required_for_production=True,
    )


def _scheduler_queue_check(queue: dict[str, Any]) -> dict[str, Any]:
    queue_status = queue.get("status")
    configured = bool(queue.get("configured"))
    if not configured:
        status = "critical"
        message = "Redis/RQ scheduler queue is not configured."
    elif queue_status == "critical":
        status = "critical"
        message = str(queue.get("message") or "Scheduler queue health is critical.")
    elif queue_status == "warning":
        status = "warning"
        message = str(queue.get("message") or "Scheduler queue has warnings.")
    else:
        status = "ok"
        message = str(queue.get("message") or "Scheduler queue is healthy.")
    return {
        "name": "scheduler_queue",
        "status": status,
        "required_for_production": True,
        "message": message,
        "details": {
            "configured": configured,
            "queue_name": queue.get("queue_name"),
            "worker_count": queue.get("worker_count"),
            "failed_count": queue.get("failed_count"),
        },
    }


def _alert_delivery_check(service: Any) -> dict[str, Any]:
    alerts = service.alert_status()
    if alerts["enabled"] and alerts["configured"]:
        status = "ok"
        message = "Outbound Incident alert delivery is configured."
    elif alerts["enabled"]:
        status = "critical"
        message = "Outbound Incident alerts are enabled but not fully configured."
    else:
        status = "warning"
        message = "Outbound Incident alert delivery is disabled."
    return {
        "name": "incident_alert_delivery",
        "status": status,
        "required_for_production": False,
        "message": message,
        "details": alerts,
    }


def _model_provider_check(service: Any) -> dict[str, Any]:
    provider = service.model_provider_status()
    default_provider = str(provider["default_provider"])
    if default_provider == "local":
        status = "warning"
        message = "The deterministic local model provider is active."
    else:
        status = "ok"
        message = f"The {default_provider} model provider is configured."
    return {
        "name": "model_provider",
        "status": status,
        "required_for_production": False,
        "message": message,
        "details": provider,
    }


def _embedding_check(service: Any) -> dict[str, Any]:
    embeddings = service.embedding_status()
    if not embeddings["enabled"]:
        status = "warning"
        message = "Semantic Knowledge embeddings are disabled."
    elif not embeddings["vector_store"]:
        status = "critical"
        message = "Embedding provider is enabled without a vector-capable persistence backend."
    elif embeddings["failed_documents"]:
        status = "warning"
        message = f"{embeddings['failed_documents']} Knowledge documents failed embedding."
    else:
        status = "ok"
        message = "Semantic Knowledge embeddings are configured."
    return {
        "name": "knowledge_embeddings",
        "status": status,
        "required_for_production": False,
        "message": message,
        "details": embeddings,
    }


def _runbook_check(service: Any) -> dict[str, Any]:
    runbooks = service.list_runbooks()
    return {
        "name": "incident_runbooks",
        "status": "ok" if runbooks else "critical",
        "required_for_production": True,
        "message": f"{len(runbooks)} operational runbooks are available.",
        "details": {
            "runbook_count": len(runbooks),
            "runbook_ids": [runbook["runbook_id"] for runbook in runbooks],
        },
    }


def _operator_backlog_check(service: Any) -> dict[str, Any]:
    integrity = service.system_integrity()
    interesting = {
        item["name"]: item
        for item in integrity["checks"]
        if item["name"] in {"open_incidents", "pending_approvals", "budget_policy"}
    }
    critical = [item for item in interesting.values() if item["status"] == "critical"]
    warnings = [item for item in interesting.values() if item["status"] == "warning"]
    if critical:
        status = "critical"
        message = "Operator backlog includes critical items."
    elif warnings:
        status = "warning"
        message = "Operator backlog has items that need Human Root attention."
    else:
        status = "ok"
        message = "No open Incident, pending Approval, or budget-policy backlog blocks readiness."
    return {
        "name": "operator_backlog",
        "status": status,
        "required_for_production": False,
        "message": message,
        "details": interesting,
    }


def _integrity_named_check(
    service: Any,
    integrity_name: str,
    readiness_name: str,
    *,
    required_for_production: bool,
) -> dict[str, Any]:
    integrity = service.system_integrity()
    match = next(
        (check for check in integrity["checks"] if check["name"] == integrity_name),
        None,
    )
    if match is None:
        return {
            "name": readiness_name,
            "status": "critical",
            "required_for_production": required_for_production,
            "message": f"System integrity check {integrity_name} is missing.",
        }
    status = "warning" if match["status"] == "skipped" else match["status"]
    return {
        "name": readiness_name,
        "status": status,
        "required_for_production": required_for_production,
        "message": match["message"],
        "details": {key: value for key, value in match.items() if key not in {"name", "status", "message"}},
    }


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None
