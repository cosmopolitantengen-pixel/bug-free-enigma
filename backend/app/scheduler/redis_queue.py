from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from app.bootstrap import build_company_os
from app.persistence.factory import create_state_store
from app.services.company import CompanyApplicationService


DEFAULT_QUEUE_NAME = "ai-company-os-scheduler"
REGISTRY_SAMPLE_LIMIT = 20


def dispatch_once(
    *,
    redis_url: str | None = None,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    redis_module, queue_class, retry_class = _load_queue_runtime()
    selected_redis_url = redis_url or os.getenv("AI_COMPANY_OS_REDIS_URL")
    if not selected_redis_url:
        raise RuntimeError("AI_COMPANY_OS_REDIS_URL is required for scheduler dispatch")
    service = _build_worker_service()
    selected_time = now or datetime.now(timezone.utc)
    if selected_time.tzinfo is None or selected_time.utcoffset() is None:
        raise ValueError("scheduler dispatch time must include a timezone")
    tick_time = selected_time.astimezone(timezone.utc)
    due_jobs = service.list_due_scheduled_jobs(tick_time, limit)
    redis_connection = redis_module.Redis.from_url(selected_redis_url)
    queue = queue_class(
        os.getenv("AI_COMPANY_OS_SCHEDULER_QUEUE", DEFAULT_QUEUE_NAME),
        connection=redis_connection,
        default_timeout=int(os.getenv("AI_COMPANY_OS_SCHEDULER_JOB_TIMEOUT", "900")),
    )

    enqueued = []
    existing = []
    for job in due_jobs:
        expected_next_run_at = job["next_run_at"]
        queue_job_id = scheduler_queue_job_id(job["schedule_id"], expected_next_run_at)
        delivery_key = f"ai-company-os:scheduler:delivery:{queue_job_id}"
        acquired = redis_connection.set(delivery_key, "1", nx=True, ex=86400)
        if not acquired:
            existing.append(queue_job_id)
            continue
        prior = queue.fetch_job(queue_job_id)
        if prior is not None:
            existing.append(queue_job_id)
            continue
        try:
            queue.enqueue_call(
                func=execute_schedule_job,
                kwargs={
                    "schedule_id": job["schedule_id"],
                    "expected_next_run_at": expected_next_run_at,
                },
                job_id=queue_job_id,
                retry=retry_class(max=3, interval=[10, 30, 60]),
                result_ttl=3600,
                failure_ttl=86400,
            )
        except Exception:
            redis_connection.delete(delivery_key)
            raise
        enqueued.append(queue_job_id)

    return {
        "dispatch_time": tick_time.isoformat(),
        "due_count": len(due_jobs),
        "enqueued_count": len(enqueued),
        "existing_count": len(existing),
        "enqueued_job_ids": enqueued,
        "existing_job_ids": existing,
    }


def execute_schedule_job(schedule_id: str, expected_next_run_at: str) -> dict[str, Any]:
    service = _build_worker_service()
    return service.execute_queued_schedule(
        schedule_id=schedule_id,
        expected_next_run_at=expected_next_run_at,
        actor_id="human_root",
    )


def scheduler_queue_job_id(schedule_id: str, expected_next_run_at: str) -> str:
    digest = hashlib.sha256(
        f"{schedule_id}:{expected_next_run_at}".encode("utf-8")
    ).hexdigest()[:24]
    return f"schedule-{digest}"


def scheduler_queue_health(redis_url: str | None = None) -> dict[str, Any]:
    selected_redis_url = redis_url or os.getenv("AI_COMPANY_OS_REDIS_URL")
    queue_name = os.getenv("AI_COMPANY_OS_SCHEDULER_QUEUE", DEFAULT_QUEUE_NAME)
    if not selected_redis_url:
        return {
            "status": "disabled",
            "configured": False,
            "queue_name": queue_name,
            "message": "AI_COMPANY_OS_REDIS_URL is not configured.",
        }

    try:
        redis_module, queue_class, worker_class = _load_queue_health_runtime()
        redis_connection = redis_module.Redis.from_url(selected_redis_url)
        ping_result = bool(redis_connection.ping())
        queue = queue_class(queue_name, connection=redis_connection)
        queued_job_ids = list(getattr(queue, "job_ids", []) or [])
        worker_count = len(worker_class.all(connection=redis_connection))
        failed_registry = getattr(queue, "failed_job_registry", None)
        started_registry = getattr(queue, "started_job_registry", None)
        deferred_registry = getattr(queue, "deferred_job_registry", None)
        scheduled_registry = getattr(queue, "scheduled_job_registry", None)
        failed_count, failed_job_ids = _registry_snapshot(failed_registry)
        started_count, started_job_ids = _registry_snapshot(started_registry)
        deferred_count, deferred_job_ids = _registry_snapshot(deferred_registry)
        scheduled_count, scheduled_job_ids = _registry_snapshot(scheduled_registry)
    except Exception as exc:
        return {
            "status": "critical",
            "configured": True,
            "queue_name": queue_name,
            "message": f"Redis scheduler queue health check failed: {exc}",
        }

    if failed_count > 0:
        status = "critical"
        message = "Scheduler queue has failed jobs that need Human Root follow-up."
    elif worker_count == 0:
        status = "warning"
        message = "Scheduler queue is reachable but no RQ workers are registered."
    else:
        status = "ok"
        message = "Scheduler queue is reachable and workers are registered."

    return {
        "status": status,
        "configured": True,
        "queue_name": queue_name,
        "redis_ping": ping_result,
        "worker_count": worker_count,
        "queued_count": _queue_count(queue, queued_job_ids),
        "started_count": started_count,
        "deferred_count": deferred_count,
        "scheduled_count": scheduled_count,
        "failed_count": failed_count,
        "queued_job_ids": queued_job_ids[:REGISTRY_SAMPLE_LIMIT],
        "started_job_ids": started_job_ids,
        "deferred_job_ids": deferred_job_ids,
        "scheduled_job_ids": scheduled_job_ids,
        "failed_job_ids": failed_job_ids,
        "message": message,
    }


def _build_worker_service() -> CompanyApplicationService:
    persistence = create_state_store()
    if persistence is None or persistence.backend_name != "postgresql":
        raise RuntimeError("Redis scheduler workers require PostgreSQL persistence")
    return CompanyApplicationService(
        company_os=build_company_os(),
        persistence=persistence,
    )


def _load_queue_runtime():
    try:
        import redis
        from rq import Queue, Retry
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Redis scheduler workers require the redis and rq production dependencies"
        ) from exc
    return redis, Queue, Retry


def _load_queue_health_runtime():
    try:
        import redis
        from rq import Queue, Worker
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Redis scheduler workers require the redis and rq production dependencies"
        ) from exc
    return redis, Queue, Worker


def _queue_count(queue: Any, queued_job_ids: list[str]) -> int:
    count = getattr(queue, "count", None)
    if isinstance(count, int):
        return count
    if callable(count):
        return int(count())
    return len(queued_job_ids)


def _registry_snapshot(registry: Any) -> tuple[int, list[str]]:
    if registry is None:
        return 0, []
    job_ids: list[str]
    get_job_ids = getattr(registry, "get_job_ids", None)
    if callable(get_job_ids):
        job_ids = list(get_job_ids())[:REGISTRY_SAMPLE_LIMIT]
    else:
        job_ids = []

    count = getattr(registry, "count", None)
    if isinstance(count, int):
        total = count
    elif callable(count):
        total = int(count())
    elif job_ids:
        total = len(job_ids)
    else:
        total = 0
    return total, job_ids
