from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.main import create_app


REQUIRED_API_PATHS = {
    "/deployment/readiness",
    "/github/absorptions/import",
    "/github/absorptions/analyze",
    "/scheduler/queue-health",
    "/alerts/status",
    "/runbooks",
    "/workflows/run",
}

REQUIRED_CONSOLE_ENDPOINTS = {
    "/deployment/readiness",
    "/alerts/status",
    "/runbooks",
    "/scheduler/queue-health",
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AI_COMPANY_OS_API_TOKEN=\S+"),
    re.compile(r"Bearer [A-Za-z0-9_\-]{20,}"),
    re.compile(r"GITHUB_TOKEN=\S+"),
]

PLACEHOLDER_ALLOWLIST = {
    "OPENAI_API_KEY=...",
    "AI_COMPANY_OS_ALERT_WEBHOOK_URL=https://alerts.example/webhook",
}

SKIPPED_DIRS = {".git", ".next", "__pycache__", "node_modules"}


def main() -> int:
    failures: list[str] = []
    client = TestClient(create_app())
    failures.extend(check_api_contract(client))
    failures.extend(check_readiness_is_secret_safe(client))
    failures.extend(check_core_workflow(client))
    failures.extend(check_console_contract())
    failures.extend(check_secret_scan())

    if failures:
        print("RELEASE_GATE_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("RELEASE_GATE_OK")
    return 0


def check_api_contract(client: TestClient) -> list[str]:
    openapi = client.get("/openapi.json").json()
    paths = set(openapi.get("paths", {}))
    missing = sorted(REQUIRED_API_PATHS - paths)
    return [f"missing API path: {path}" for path in missing]


def check_readiness_is_secret_safe(client: TestClient) -> list[str]:
    marker = "release-gate-token"
    with patched_env(
        AI_COMPANY_OS_AUTH_REQUIRED="true",
        AI_COMPANY_OS_API_TOKEN=marker,
        AI_COMPANY_OS_API_TOKEN_SHA256=None,
        AI_COMPANY_OS_ALERTS_ENABLED="true",
        AI_COMPANY_OS_ALERT_WEBHOOK_URL="https://alerts.example/private-hook",
        AI_COMPANY_OS_ALERT_TIMEOUT_SECONDS="5",
    ):
        secure_client = TestClient(create_app())
        response = secure_client.get(
            "/deployment/readiness",
            headers={"Authorization": f"Bearer {marker}"},
        )
    failures = []
    if response.status_code != 200:
        failures.append(f"readiness endpoint returned HTTP {response.status_code}")
        return failures
    payload = response.json()
    rendered = json.dumps(payload, sort_keys=True)
    if marker in rendered:
        failures.append("readiness response leaked API token")
    if "https://alerts.example/private-hook" in rendered:
        failures.append("readiness response leaked full alert webhook URL")
    checks = {check.get("name"): check for check in payload.get("checks", [])}
    if checks.get("http_auth_gate", {}).get("status") != "ok":
        failures.append("readiness auth check did not pass with configured bearer token")
    return failures


def check_core_workflow(client: TestClient) -> list[str]:
    response = client.post(
        "/workflows/run",
        json={
            "workflow_id": "task_planning_v1",
            "title": "Release gate task plan",
            "description": "Verify the native Workflow path before release.",
        },
    )
    if response.status_code != 200:
        return [f"task planning workflow returned HTTP {response.status_code}"]
    payload = response.json()
    if payload.get("task", {}).get("status") != "planned":
        return ["task planning workflow did not reach planned status"]
    if payload.get("blocked"):
        return ["task planning workflow was unexpectedly blocked"]
    return []


def check_console_contract() -> list[str]:
    console_path = ROOT / "apps" / "web" / "components" / "operations-console.tsx"
    content = console_path.read_text(encoding="utf-8")
    return [
        f"operations console does not reference endpoint {endpoint}"
        for endpoint in sorted(REQUIRED_CONSOLE_ENDPOINTS)
        if endpoint not in content
    ]


def check_secret_scan() -> list[str]:
    failures = []
    scanned_roots = [ROOT / ".env.example", ROOT / "README.md", ROOT / "docs", ROOT / "backend", ROOT / "apps"]
    for path in iter_text_files(scanned_roots):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            for match in pattern.findall(text):
                if match not in PLACEHOLDER_ALLOWLIST:
                    failures.append(f"secret-like value in {path.relative_to(ROOT)}: {match}")
    return failures


def iter_text_files(paths: list[Path]):
    for path in paths:
        if path.is_file():
            yield path
            continue
        if not path.exists():
            continue
        for child in path.rglob("*"):
            if any(part in SKIPPED_DIRS for part in child.parts):
                continue
            if child.is_file() and child.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".md", ".yml", ".yaml", ".json", ".txt", ".example"}:
                yield child


class patched_env:
    def __init__(self, **values: str | None) -> None:
        self.values = values
        self.previous: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.values.items():
            self.previous[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, *_exc: Any) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
