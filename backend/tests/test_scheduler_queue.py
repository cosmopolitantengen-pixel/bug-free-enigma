import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.bootstrap import build_company_os
from app.core.enums import ScheduleAction
from app.persistence.sqlite_store import SQLiteStateStore
from app.scheduler import redis_queue
from app.services.company import CompanyApplicationService


class SchedulerQueueTests(unittest.TestCase):
    def test_queued_delivery_is_idempotent_across_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteStateStore(os.path.join(tmpdir, "queue.db"))
            service = CompanyApplicationService(build_company_os(), persistence=store)
            due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            scheduled = service.create_scheduled_job(
                name="Queued task",
                action=ScheduleAction.CREATE_TASK,
                payload={"title": "Queue task", "description": "Created once."},
                created_by="human_root",
                next_run_at=due_at,
                max_runs=1,
            )

            first = service.execute_queued_schedule(
                scheduled["schedule_id"],
                scheduled["next_run_at"],
                now=datetime.now(timezone.utc),
            )
            reloaded = CompanyApplicationService(build_company_os(), persistence=store)
            replay = reloaded.execute_queued_schedule(
                scheduled["schedule_id"],
                scheduled["next_run_at"],
                now=datetime.now(timezone.utc),
            )

            self.assertEqual(first["status"], "executed")
            self.assertEqual(replay["status"], "skipped")
            self.assertEqual(len(reloaded.tasks), 1)
            self.assertEqual(len(reloaded.list_scheduled_executions()), 1)

    def test_queue_job_id_is_stable_per_schedule_occurrence(self):
        first = redis_queue.scheduler_queue_job_id("schedule-1", "2026-01-01T00:00:00+00:00")
        replay = redis_queue.scheduler_queue_job_id("schedule-1", "2026-01-01T00:00:00+00:00")
        next_run = redis_queue.scheduler_queue_job_id("schedule-1", "2026-01-01T00:01:00+00:00")

        self.assertEqual(first, replay)
        self.assertNotEqual(first, next_run)

    def test_dispatcher_rejects_naive_time(self):
        with patch.object(
            redis_queue,
            "_load_queue_runtime",
            return_value=(object(), object(), object()),
        ), patch.object(redis_queue, "_build_worker_service"):
            with self.assertRaisesRegex(ValueError, "must include a timezone"):
                redis_queue.dispatch_once(
                    redis_url="redis://test",
                    now=datetime(2026, 1, 1),
                )

    def test_dispatcher_does_not_enqueue_an_existing_delivery(self):
        class FakeRedisClient:
            keys = set()

            @classmethod
            def from_url(cls, _url):
                return cls()

            def set(self, key, _value, *, nx, ex):
                self.assert_options = (nx, ex)
                if key in self.keys:
                    return None
                self.keys.add(key)
                return True

            def delete(self, key):
                self.keys.discard(key)

        class FakeRedisModule:
            Redis = FakeRedisClient

        class FakeRetry:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeQueue:
            jobs = {}

            def __init__(self, *_args, **_kwargs):
                pass

            def fetch_job(self, job_id):
                return self.jobs.get(job_id)

            def enqueue_call(self, **kwargs):
                self.jobs[kwargs["job_id"]] = kwargs

        class FakeService:
            def list_due_scheduled_jobs(self, _now, _limit):
                return [
                    {
                        "schedule_id": "schedule-1",
                        "next_run_at": "2026-01-01T00:00:00+00:00",
                    }
                ]

        FakeQueue.jobs = {}
        FakeRedisClient.keys = set()
        with patch.object(
            redis_queue,
            "_load_queue_runtime",
            return_value=(FakeRedisModule, FakeQueue, FakeRetry),
        ), patch.object(redis_queue, "_build_worker_service", return_value=FakeService()):
            first = redis_queue.dispatch_once(redis_url="redis://test")
            second = redis_queue.dispatch_once(redis_url="redis://test")

        self.assertEqual(first["enqueued_count"], 1)
        self.assertEqual(second["enqueued_count"], 0)
        self.assertEqual(second["existing_count"], 1)

    def test_queue_health_reports_disabled_without_redis_url(self):
        with patch.dict(os.environ, {"AI_COMPANY_OS_REDIS_URL": ""}, clear=False):
            health = redis_queue.scheduler_queue_health()

        self.assertEqual(health["status"], "disabled")
        self.assertFalse(health["configured"])
        self.assertEqual(health["queue_name"], redis_queue.DEFAULT_QUEUE_NAME)

    def test_queue_health_reports_worker_and_registry_counts(self):
        class FakeRegistry:
            def __init__(self, job_ids):
                self._job_ids = job_ids

            def get_job_ids(self):
                return self._job_ids

            @property
            def count(self):
                return len(self._job_ids)

        class FakeRedisClient:
            @classmethod
            def from_url(cls, _url):
                return cls()

            def ping(self):
                return True

        class FakeRedisModule:
            Redis = FakeRedisClient

        class FakeQueue:
            def __init__(self, *_args, **_kwargs):
                self.job_ids = ["queued-1", "queued-2"]
                self.failed_job_registry = FakeRegistry(["failed-1"])
                self.started_job_registry = FakeRegistry(["started-1"])
                self.deferred_job_registry = FakeRegistry([])
                self.scheduled_job_registry = FakeRegistry(["scheduled-1"])

        class FakeWorker:
            @classmethod
            def all(cls, **_kwargs):
                return ["worker-1", "worker-2"]

        with patch.object(
            redis_queue,
            "_load_queue_health_runtime",
            return_value=(FakeRedisModule, FakeQueue, FakeWorker),
        ):
            health = redis_queue.scheduler_queue_health(redis_url="redis://test")

        self.assertEqual(health["status"], "critical")
        self.assertEqual(health["worker_count"], 2)
        self.assertEqual(health["queued_count"], 2)
        self.assertEqual(health["failed_count"], 1)
        self.assertEqual(health["failed_job_ids"], ["failed-1"])

    def test_worker_service_rejects_non_postgres_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite = SQLiteStateStore(os.path.join(tmpdir, "worker.db"))
            with patch.object(redis_queue, "create_state_store", return_value=sqlite):
                with self.assertRaisesRegex(RuntimeError, "require PostgreSQL"):
                    redis_queue._build_worker_service()


if __name__ == "__main__":
    unittest.main()
