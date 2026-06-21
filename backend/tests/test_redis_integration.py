import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.bootstrap import build_company_os
from app.core.enums import ScheduleAction
from app.persistence.postgres_store import PostgresStateStore
from app.scheduler.redis_queue import dispatch_once
from app.services.company import CompanyApplicationService


POSTGRES_TEST_URL = os.getenv("AI_COMPANY_OS_TEST_POSTGRES_URL")
REDIS_TEST_URL = os.getenv("AI_COMPANY_OS_TEST_REDIS_URL")


@unittest.skipUnless(
    POSTGRES_TEST_URL and REDIS_TEST_URL,
    "set PostgreSQL and Redis test URLs to run the scheduler worker integration test",
)
class RedisSchedulerIntegrationTests(unittest.TestCase):
    def test_rq_worker_executes_due_schedule_once(self):
        import redis
        from rq import Queue, SimpleWorker

        queue_name = f"ai-company-os-test-{uuid.uuid4().hex}"
        redis_connection = redis.Redis.from_url(REDIS_TEST_URL)
        store = PostgresStateStore(POSTGRES_TEST_URL)
        service = CompanyApplicationService(build_company_os(), persistence=store)
        scheduled = service.create_scheduled_job(
            name="Redis integration fixture",
            action=ScheduleAction.CREATE_TASK,
            payload={"title": "Redis fixture", "description": "Executed exactly once."},
            created_by="human_root",
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            max_runs=1,
        )

        environment = {
            "AI_COMPANY_OS_DATABASE_URL": POSTGRES_TEST_URL,
            "AI_COMPANY_OS_REDIS_URL": REDIS_TEST_URL,
            "AI_COMPANY_OS_SCHEDULER_QUEUE": queue_name,
        }
        try:
            with patch.dict(os.environ, environment):
                dispatched = dispatch_once(limit=100)
                replayed = dispatch_once(limit=100)
                queue = Queue(queue_name, connection=redis_connection)
                worked = SimpleWorker([queue], connection=redis_connection).work(burst=True)

            reloaded = CompanyApplicationService(build_company_os(), persistence=store)
            executions = reloaded.list_scheduled_executions(scheduled["schedule_id"])

            self.assertEqual(dispatched["enqueued_count"], 1)
            self.assertEqual(replayed["enqueued_count"], 0)
            self.assertTrue(worked)
            self.assertEqual(len(executions), 1)
            self.assertEqual(executions[0]["status"], "completed")
        finally:
            queue = Queue(queue_name, connection=redis_connection)
            for job_id in queue.job_ids:
                job = queue.fetch_job(job_id)
                if job is not None:
                    job.delete()
            queue.empty()


if __name__ == "__main__":
    unittest.main()
