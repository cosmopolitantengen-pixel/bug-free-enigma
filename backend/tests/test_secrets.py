import os
import sys
import tempfile
import unittest
from unittest.mock import patch


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.auth.http import HttpAuthSettings
from app.knowledge_base.embeddings import create_embedding_gateway
from app.main import create_app
from app.models.gateway import create_model_gateway
from app.observability.alerts import AlertSettings
from app.persistence.factory import create_state_store
from app.scheduler import redis_queue
from app.secrets import SecretConfigurationError, read_secret, secret_configured


class SecretFileTests(unittest.TestCase):
    def test_read_secret_supports_file_and_rejects_conflict(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("from-file\n")
            secret_path = handle.name
        try:
            with patch.dict(os.environ, {"TEST_SECRET_FILE": secret_path}, clear=True):
                self.assertEqual(read_secret("TEST_SECRET"), "from-file")
                self.assertTrue(secret_configured("TEST_SECRET"))
            with patch.dict(os.environ, {"TEST_SECRET": "direct", "TEST_SECRET_FILE": secret_path}, clear=True):
                with self.assertRaisesRegex(SecretConfigurationError, "configure only one"):
                    read_secret("TEST_SECRET")
        finally:
            os.unlink(secret_path)

    def test_http_auth_static_token_can_come_from_secret_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("file-token\n")
            secret_path = handle.name
        try:
            with patch.dict(os.environ, {"AI_COMPANY_OS_API_TOKEN_FILE": secret_path}, clear=True):
                settings = HttpAuthSettings.from_env()
            client = TestClient(create_app(auth_settings=HttpAuthSettings(required=True, api_token=settings.api_token)))
            allowed = client.get("/agents", headers={"Authorization": "Bearer file-token"})

            self.assertEqual(allowed.status_code, 200)
        finally:
            os.unlink(secret_path)

    def test_alert_webhook_can_come_from_secret_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("https://alerts.example/secret-hook\n")
            secret_path = handle.name
        try:
            with patch.dict(
                os.environ,
                {
                    "AI_COMPANY_OS_ALERTS_ENABLED": "true",
                    "AI_COMPANY_OS_ALERT_WEBHOOK_URL_FILE": secret_path,
                },
                clear=True,
            ):
                settings = AlertSettings.from_env()

            self.assertTrue(settings.configured)
            self.assertEqual(settings.endpoint_host, "alerts.example")
        finally:
            os.unlink(secret_path)

    def test_openai_model_and_embedding_factories_accept_api_key_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("file-openai-key\n")
            secret_path = handle.name
        try:
            with patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY_FILE": secret_path,
                    "AI_COMPANY_OS_MODEL_PROVIDER": "openai",
                    "AI_COMPANY_OS_EMBEDDING_PROVIDER": "openai",
                },
                clear=True,
            ):
                model_gateway = create_model_gateway()
                embedding_gateway = create_embedding_gateway()

            self.assertEqual(model_gateway.provider_status()["default_provider"], "openai")
            self.assertTrue(embedding_gateway.status()["enabled"])
        finally:
            os.unlink(secret_path)

    def test_database_url_file_is_accepted_without_exposing_secret(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("postgresql://user:secret@db/company\n")
            secret_path = handle.name
        try:
            with patch.dict(os.environ, {"AI_COMPANY_OS_DATABASE_URL_FILE": secret_path}, clear=True):
                with patch("app.persistence.factory.PostgresStateStore") as store_class:
                    create_state_store()

            store_class.assert_called_once_with("postgresql://user:secret@db/company")
        finally:
            os.unlink(secret_path)

    def test_redis_url_file_is_accepted_by_queue_health(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("redis://localhost:6379/9\n")
            secret_path = handle.name

        class FakeRedisClient:
            @classmethod
            def from_url(cls, url):
                self = cls()
                self.url = url
                return self

            def ping(self):
                return True

        class FakeRedisModule:
            Redis = FakeRedisClient

        class FakeQueue:
            job_ids = []

            def __init__(self, *_args, **_kwargs):
                self.failed_job_registry = None
                self.started_job_registry = None
                self.deferred_job_registry = None
                self.scheduled_job_registry = None

        class FakeWorker:
            @staticmethod
            def all(connection):
                return [connection]

        try:
            with patch.dict(os.environ, {"AI_COMPANY_OS_REDIS_URL_FILE": secret_path}, clear=True), patch.object(
                redis_queue,
                "_load_queue_health_runtime",
                return_value=(FakeRedisModule, FakeQueue, FakeWorker),
            ):
                health = redis_queue.scheduler_queue_health()

            self.assertEqual(health["status"], "ok")
            self.assertTrue(health["configured"])
            self.assertEqual(health["worker_count"], 1)
        finally:
            os.unlink(secret_path)


if __name__ == "__main__":
    unittest.main()
