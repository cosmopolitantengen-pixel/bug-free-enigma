import os
import tempfile
import unittest
from unittest.mock import patch

from app.persistence.factory import _normalize_postgres_url, create_state_store
from app.persistence.postgres_store import PostgresStateStore, _vector
from app.persistence.sqlite_store import SQLiteStateStore


class PersistenceFactoryTests(unittest.TestCase):
    def test_explicit_sqlite_configuration_is_environment_independent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.db")
            with patch.dict(
                os.environ,
                {"AI_COMPANY_OS_DATABASE_URL": "postgresql://ignored/ignored"},
            ):
                store = create_state_store(sqlite_path=path)

        self.assertIsInstance(store, SQLiteStateStore)

    def test_environment_rejects_multiple_persistence_backends(self):
        with patch.dict(
            os.environ,
            {
                "AI_COMPANY_OS_SQLITE_PATH": "state.db",
                "AI_COMPANY_OS_DATABASE_URL": "postgresql://localhost/state",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "only one persistence backend"):
                create_state_store()

    def test_postgres_driver_url_is_normalized_before_store_creation(self):
        with patch("app.persistence.factory.PostgresStateStore") as store_class:
            create_state_store(database_url="postgresql+psycopg://user:pass@db/company")

        store_class.assert_called_once_with("postgresql://user:pass@db/company")

    def test_non_postgres_database_url_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must use a PostgreSQL URL"):
            _normalize_postgres_url("mysql://localhost/company")

    def test_missing_psycopg_has_an_actionable_error(self):
        with patch(
            "app.persistence.postgres_store.importlib.import_module",
            side_effect=ModuleNotFoundError("psycopg"),
        ):
            with self.assertRaisesRegex(RuntimeError, "requires psycopg"):
                PostgresStateStore("postgresql://localhost/company")

    def test_pgvector_serialization_is_deterministic(self):
        self.assertEqual(_vector([1, 2.5, -3]), "[1.0,2.5,-3.0]")


if __name__ == "__main__":
    unittest.main()
