import base64
import json
import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.connectors.github import GitHubConnector, GitHubConnectorError
from app.main import create_app


README = "# Safe Docs\n\nA documentation and API workflow helper with tests."


def fake_transport(url, headers, _timeout):
    fake_transport.calls.append((url, dict(headers)))
    if url.endswith("/readme"):
        return {
            "content": base64.b64encode(README.encode("utf-8")).decode("ascii"),
            "encoding": "base64",
        }
    return {
        "default_branch": "main",
        "archived": False,
        "disabled": False,
        "pushed_at": "2030-01-02T00:00:00Z",
        "license": {"spdx_id": "MIT", "name": "MIT License"},
    }


fake_transport.calls = []


class GitHubConnectorTests(unittest.TestCase):
    def setUp(self):
        fake_transport.calls = []

    def test_connector_fetches_safe_repository_metadata(self):
        connector = GitHubConnector(
            token="test-token",
            timeout_seconds=5,
            transport=fake_transport,
        )

        metadata = connector.fetch_repository("https://github.com/example/safe-docs")

        self.assertEqual(metadata.repo_url, "https://github.com/example/safe-docs")
        self.assertEqual(metadata.owner, "example")
        self.assertEqual(metadata.repo, "safe-docs")
        self.assertEqual(metadata.readme, README)
        self.assertEqual(metadata.license_name, "MIT")
        self.assertEqual(metadata.maintenance_signal, "active")
        self.assertEqual(fake_transport.calls[0][1]["Authorization"], "Bearer test-token")
        self.assertNotIn("test-token", json.dumps(metadata.safe_summary()))

    def test_connector_rejects_non_root_or_non_github_urls(self):
        connector = GitHubConnector(timeout_seconds=5, transport=fake_transport)

        for url in [
            "http://github.com/example/repo",
            "https://example.com/example/repo",
            "https://github.com/example/repo/tree/main",
            "https://token@github.com/example/repo",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    connector.fetch_repository(url)

    def test_connector_rejects_empty_readme(self):
        def empty_readme_transport(url, _headers, _timeout):
            if url.endswith("/readme"):
                return {"content": base64.b64encode(b"").decode("ascii"), "encoding": "base64"}
            return {"license": {"spdx_id": "MIT"}}

        connector = GitHubConnector(timeout_seconds=5, transport=empty_readme_transport)

        with self.assertRaises(GitHubConnectorError):
            connector.fetch_repository("https://github.com/example/empty")

    def test_api_import_uses_connector_and_existing_absorption_controls(self):
        original_fetch = GitHubConnector.fetch_repository

        def fake_fetch(self, repo_url):
            connector = GitHubConnector(timeout_seconds=5, transport=fake_transport)
            return original_fetch(connector, repo_url)

        GitHubConnector.fetch_repository = fake_fetch
        try:
            response = TestClient(create_app()).post(
                "/github/absorptions/import",
                json={
                    "repo_url": "https://github.com/example/safe-docs",
                    "requested_by_agent": "ceo_agent_v1",
                },
            )
        finally:
            GitHubConnector.fetch_repository = original_fetch

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["metadata"]["license_name"], "MIT")
        self.assertEqual(payload["metadata"]["readme_char_count"], len(README))
        self.assertEqual(payload["proposal"]["repo_url"], "https://github.com/example/safe-docs")
        self.assertEqual(payload["proposal"]["status"], "pending_approval")
        self.assertIn("documentation", payload["proposal"]["recommended_capabilities"])


if __name__ == "__main__":
    unittest.main()
