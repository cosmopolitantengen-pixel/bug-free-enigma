from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from app.bootstrap import build_company_os
from app.persistence.factory import create_state_store
from app.services.company import CompanyApplicationService


DEFAULT_QUEUE_NAME = "ai-company-os-scheduler"


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
