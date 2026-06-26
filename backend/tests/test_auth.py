import os
import sys
import tempfile
import unittest
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.auth.http import AuthConfigurationError, HttpAuthSettings
from app.auth.passwords import hash_password, verify_password
from app.auth.service import AuthError, AuthService
from app.main import create_app
from app.persistence.sqlite_store import SQLiteStateStore


class AuthTests(unittest.TestCase):
    def test_password_hash_uses_pbkdf2_and_verifies(self):
        stored = hash_password("safe-password")

        self.assertNotIn("safe-password", stored)
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password("safe-password", stored))
        self.assertFalse(verify_password("wrong-password", stored))

    def test_register_login_duplicate_and_wrong_password_paths(self):
        client = TestClient(create_app())

        registered = client.post(
            "/auth/register",
            json={"email": "Root@Example.com", "password": "password123"},
        )
        duplicate = client.post(
            "/auth/register",
            json={"email": "root@example.com", "password": "password123"},
        )
        bad_login = client.post(
            "/auth/login",
            json={"email": "root@example.com", "password": "wrong"},
        )
        login = client.post(
            "/auth/login",
            json={"email": "root@example.com", "password": "password123"},
        )
        logout = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )

        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["email"], "root@example.com")
        self.assertNotIn("password_hash", registered.json())
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(bad_login.status_code, 401)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["token_type"], "bearer")
        self.assertIn("expires_at", login.json())
        self.assertEqual(login.json()["expires_in_seconds"], 8 * 60 * 60)
        self.assertEqual(logout.json()["status"], "ok")

    def test_registered_user_persists_and_can_login_after_app_recreation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "auth.db")
            first = TestClient(create_app(sqlite_path=db_path))
            first.post(
                "/auth/register",
                json={"email": "persist@example.com", "password": "password123"},
            )

            users = SQLiteStateStore(db_path).load_users()
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0].email, "persist@example.com")
            self.assertNotIn("password123", users[0].password_hash)

            second = TestClient(create_app(sqlite_path=db_path))
            login = second.post(
                "/auth/login",
                json={"email": "persist@example.com", "password": "password123"},
            )

            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json()["user"]["email"], "persist@example.com")

    def test_required_http_auth_blocks_requests_until_static_token_is_present(self):
        client = TestClient(create_app(auth_settings=HttpAuthSettings(required=True, api_token="root-token")))

        health = client.get("/health")
        blocked = client.get("/agents")
        allowed = client.get("/agents", headers={"Authorization": "Bearer root-token"})

        self.assertEqual(health.status_code, 200)
        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json()["detail"], "authentication required")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(len(allowed.json()), 17)

    def test_required_http_auth_accepts_sha256_static_token_and_session_tokens(self):
        token_hash = hashlib.sha256("bootstrap-token".encode("utf-8")).hexdigest()
        client = TestClient(
            create_app(auth_settings=HttpAuthSettings(required=True, api_token_sha256=token_hash))
        )

        blocked_registration = client.post(
            "/auth/register",
            json={"email": "blocked@example.com", "password": "password123"},
        )
        registered = client.post(
            "/auth/register",
            json={"email": "root@example.com", "password": "password123"},
            headers={"Authorization": "Bearer bootstrap-token"},
        )
        login = client.post(
            "/auth/login",
            json={"email": "root@example.com", "password": "password123"},
        )
        via_session = client.get(
            "/agents",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )

        self.assertEqual(blocked_registration.status_code, 401)
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(via_session.status_code, 200)

    def test_session_tokens_expire_and_are_pruned(self):
        now = datetime(2026, 6, 26, 8, 0, tzinfo=timezone.utc)
        service = AuthService(session_ttl_seconds=60, clock=lambda: now)
        service.register("root@example.com", "password123")

        login = service.login("root@example.com", "password123")
        token = login["access_token"]

        self.assertEqual(login["expires_in_seconds"], 60)
        self.assertEqual(login["expires_at"], (now + timedelta(seconds=60)).isoformat())
        self.assertIsNotNone(service.authenticate_session_token(token))

        service.clock = lambda: now + timedelta(seconds=61)

        self.assertIsNone(service.authenticate_session_token(token))
        self.assertNotIn(token, service.sessions)

    def test_session_ttl_env_must_be_positive_integer(self):
        with self.assertRaises(AuthError):
            with patch.dict(os.environ, {"AI_COMPANY_OS_SESSION_TTL_SECONDS": "0"}):
                AuthService.from_env()

        with patch.dict(os.environ, {"AI_COMPANY_OS_SESSION_TTL_SECONDS": "120"}):
            self.assertEqual(AuthService.from_env().session_ttl_seconds, 120)

    def test_required_http_auth_rejects_locked_startup_configuration(self):
        with self.assertRaises(AuthConfigurationError):
            create_app(auth_settings=HttpAuthSettings(required=True))


if __name__ == "__main__":
    unittest.main()
