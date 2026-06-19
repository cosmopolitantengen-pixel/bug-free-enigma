import os
import sys
import tempfile
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.auth.passwords import hash_password, verify_password
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


if __name__ == "__main__":
    unittest.main()
