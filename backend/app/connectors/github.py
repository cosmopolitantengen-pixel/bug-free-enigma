from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from app.secrets import read_secret


GitHubTransport = Callable[[str, dict[str, str], float], dict[str, Any]]


class GitHubConnectorError(RuntimeError):
    """A sanitized GitHub connector failure that is safe to expose to operators."""


@dataclass(frozen=True)
class GitHubRepositoryMetadata:
    repo_url: str
    owner: str
    repo: str
    readme: str
    license_name: str
    maintenance_signal: str
    default_branch: str | None = None
    archived: bool = False

    def safe_summary(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "owner": self.owner,
            "repo": self.repo,
            "license_name": self.license_name,
            "maintenance_signal": self.maintenance_signal,
            "default_branch": self.default_branch,
            "archived": self.archived,
            "readme_char_count": len(self.readme),
        }


class GitHubConnector:
    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: float | None = None,
        transport: GitHubTransport | None = None,
    ) -> None:
        self._token = (token if token is not None else read_secret("GITHUB_TOKEN", "") or "").strip()
        self._timeout_seconds = timeout_seconds or _timeout_seconds()
        self._transport = transport or _get_json

    def fetch_repository(self, repo_url: str) -> GitHubRepositoryMetadata:
        owner, repo = _parse_github_repo_url(repo_url)
        headers = _headers(self._token)
        repo_payload = self._transport(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers,
            self._timeout_seconds,
        )
        readme_payload = self._transport(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers,
            self._timeout_seconds,
        )
        readme = _decode_readme(readme_payload)
        if not readme.strip():
            raise GitHubConnectorError("GitHub repository README is empty")
        archived = bool(repo_payload.get("archived"))
        disabled = bool(repo_payload.get("disabled"))
        return GitHubRepositoryMetadata(
            repo_url=f"https://github.com/{owner}/{repo}",
            owner=owner,
            repo=repo,
            readme=readme,
            license_name=_license_name(repo_payload),
            maintenance_signal=_maintenance_signal(repo_payload, archived, disabled),
            default_branch=_optional_string(repo_payload.get("default_branch")),
            archived=archived,
        )


def _parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(repo_url.strip())
    if parsed.scheme != "https":
        raise ValueError("repo_url must use https")
    if parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("repo_url must target github.com")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("repo_url must not include credentials, query, or fragment")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError("repo_url must include owner and repository")
    if len(parts) > 2:
        raise ValueError("repo_url must point to a repository root")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if not _safe_github_name(owner) or not _safe_github_name(repo):
        raise ValueError("repo_url contains an invalid owner or repository name")
    return owner, repo


def _headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Company-OS-GitHub-Connector",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str, headers: dict[str, str], timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GitHubConnectorError(f"GitHub returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GitHubConnectorError(f"GitHub request failed: {exc.reason}") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubConnectorError(f"GitHub returned an invalid response: {exc.__class__.__name__}") from exc


def _decode_readme(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, str):
        raise GitHubConnectorError("GitHub README response is missing content")
    encoding = str(payload.get("encoding") or "").lower()
    if encoding != "base64":
        raise GitHubConnectorError("GitHub README response uses an unsupported encoding")
    try:
        return base64.b64decode(content, validate=False).decode("utf-8", errors="replace")
    except ValueError as exc:
        raise GitHubConnectorError("GitHub README content is not valid base64") from exc


def _license_name(payload: dict[str, Any]) -> str:
    license_payload = payload.get("license")
    if isinstance(license_payload, dict):
        value = license_payload.get("spdx_id") or license_payload.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _maintenance_signal(payload: dict[str, Any], archived: bool, disabled: bool) -> str:
    if disabled:
        return "disabled"
    if archived:
        return "archived"
    pushed_at = payload.get("pushed_at")
    if isinstance(pushed_at, str) and pushed_at.strip():
        return "active"
    return "unknown"


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe_github_name(value: str) -> bool:
    return bool(value) and all(character.isalnum() or character in {"-", "_", "."} for character in value)


def _timeout_seconds() -> float:
    raw = os.getenv("AI_COMPANY_OS_GITHUB_TIMEOUT_SECONDS", "20")
    try:
        value = float(raw)
    except ValueError as exc:
        raise GitHubConnectorError("AI_COMPANY_OS_GITHUB_TIMEOUT_SECONDS must be numeric") from exc
    if value <= 0 or value > 60:
        raise GitHubConnectorError("AI_COMPANY_OS_GITHUB_TIMEOUT_SECONDS must be greater than 0 and at most 60")
    return value
