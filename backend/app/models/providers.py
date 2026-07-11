from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


class ModelProviderError(RuntimeError):
    """A sanitized provider failure that is safe to expose to operators."""


class ModelProviderConfigurationError(ModelProviderError):
    pass


@dataclass(frozen=True)
class ProviderGeneration:
    output: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ProviderStreamEvent:
    delta: str | None = None
    generation: ProviderGeneration | None = None


class ModelProvider(Protocol):
    name: str
    default_model: str

    def generate(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> ProviderGeneration: ...


class DeterministicModelProvider:
    name = "local"
    default_model = "deterministic_mock_v1"

    def generate(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> ProviderGeneration:
        compact = " ".join(prompt.split())
        if len(compact) > 180:
            compact = f"{compact[:177]}..."
        output = f"[{purpose}] Deterministic model response: {compact}"
        prompt_tokens = _estimate_tokens(prompt)
        completion_tokens = _estimate_tokens(output)
        return ProviderGeneration(
            output=output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def stream(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> Iterator[ProviderStreamEvent]:
        generation = self.generate(prompt, model_name, purpose, max_output_tokens)
        yield ProviderStreamEvent(delta=generation.output)
        yield ProviderStreamEvent(generation=generation)


_CODEX_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "hooks",
    "image_generation",
    "in_app_browser",
    "multi_agent",
    "plugin_hooks",
    "plugins",
    "shell_snapshot",
    "tool_search",
    "workspace_dependencies",
)
_CODEX_ENVIRONMENT_ALLOWLIST = {
    "APPDATA",
    "CODEX_HOME",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "COMSPEC",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "USERNAME",
    "WINDIR",
}


class CodexCliProvider:
    """Runs Codex as a read-only reasoning provider behind OS governance."""

    name = "codex"
    DEFAULT_MODEL = "codex-default"

    def __init__(
        self,
        executable: str,
        *,
        workspace_root: str | Path,
        entrypoint: str | Path | None = None,
        default_model: str = DEFAULT_MODEL,
        timeout_seconds: float = 180.0,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        if not executable.strip():
            raise ModelProviderConfigurationError("Codex CLI executable is required")
        if not default_model.strip():
            raise ModelProviderConfigurationError(
                "AI_COMPANY_OS_CODEX_MODEL is required"
            )
        workspace = Path(workspace_root).expanduser().resolve()
        if not workspace.is_dir():
            raise ModelProviderConfigurationError(
                "AI_COMPANY_OS_CODEX_WORKSPACE_ROOT must be an existing directory"
            )
        if timeout_seconds <= 0 or timeout_seconds > 600:
            raise ModelProviderConfigurationError(
                "AI_COMPANY_OS_CODEX_TIMEOUT_SECONDS must be between 0 and 600"
            )
        self.default_model = default_model.strip()
        self._command_prefix = [executable.strip()]
        if entrypoint is not None and str(entrypoint).strip():
            entrypoint_path = Path(entrypoint).expanduser().resolve()
            if not entrypoint_path.is_file():
                raise ModelProviderConfigurationError(
                    "AI_COMPANY_OS_CODEX_ENTRYPOINT must be an existing file"
                )
            self._command_prefix.append(str(entrypoint_path))
        self._workspace = workspace
        self._timeout_seconds = timeout_seconds
        self._runner = runner
        self.status_details = {
            "transport": "local_codex_cli",
            "sandbox": "read-only",
            "governed_execution": True,
        }

    def generate(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> ProviderGeneration:
        command = self._command(model_name)
        try:
            completed = self._runner(
                command,
                input=self._wrapped_prompt(prompt, purpose, max_output_tokens),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                cwd=str(self._workspace),
                env=_codex_environment(),
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ModelProviderError("codex request timed out") from exc
        except OSError as exc:
            raise ModelProviderError(
                f"codex CLI could not be started: {exc.__class__.__name__}"
            ) from exc
        stdout = str(completed.stdout or "")
        stderr = str(completed.stderr or "")
        if completed.returncode != 0:
            raise ModelProviderError(
                _codex_failure_message(stdout, stderr, completed.returncode)
            )
        return _codex_generation(stdout, prompt)

    def _command(self, model_name: str) -> list[str]:
        command = [
            *self._command_prefix,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
        ]
        for feature in _CODEX_DISABLED_FEATURES:
            command.extend(("--disable", feature))
        command.extend(
            (
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "-C",
                str(self._workspace),
            )
        )
        if model_name != self.DEFAULT_MODEL:
            command.extend(("--model", model_name))
        command.append("-")
        return command

    @staticmethod
    def _wrapped_prompt(
        prompt: str, purpose: str, max_output_tokens: int
    ) -> str:
        return "\n".join(
            (
                "AI Company OS is invoking Codex as a read-only reasoning provider.",
                "Inspect only the configured workspace. Do not modify files or cause external side effects.",
                f"Purpose: {purpose}",
                f"Keep the final answer within approximately {max_output_tokens} tokens.",
                "Follow the task-specific response format below exactly.",
                "",
                prompt,
            )
        )


class OpenAIResponsesProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        *,
        default_model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ModelProviderConfigurationError("OPENAI_API_KEY is required for the openai provider")
        _validate_base_url(base_url, "OPENAI_BASE_URL")
        if not default_model.strip():
            raise ModelProviderConfigurationError("AI_COMPANY_OS_MODEL_NAME is required")
        self.default_model = default_model.strip()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=timeout_seconds,
        )

    def generate(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> ProviderGeneration:
        try:
            response = self._client.post(
                "/responses",
                json={
                    "model": model_name,
                    "input": prompt,
                    "store": False,
                    "max_output_tokens": max_output_tokens,
                },
            )
        except httpx.HTTPError as exc:
            raise ModelProviderError(f"openai request failed: {exc.__class__.__name__}") from exc
        if not response.is_success:
            raise ModelProviderError(_provider_http_error("openai", response))
        try:
            payload = response.json()
            output = _response_text(payload)
            usage = payload.get("usage") or {}
            prompt_tokens = int(usage.get("input_tokens") or _estimate_tokens(prompt))
            completion_tokens = int(usage.get("output_tokens") or _estimate_tokens(output))
            total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
        except (TypeError, ValueError, KeyError) as exc:
            raise ModelProviderError("openai returned an invalid response payload") from exc
        if not output:
            raise ModelProviderError("openai returned no text output")
        return ProviderGeneration(output, prompt_tokens, completion_tokens, total_tokens)

    def stream(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> Iterator[ProviderStreamEvent]:
        output_parts: list[str] = []
        completed_response: dict[str, Any] | None = None
        try:
            with self._client.stream(
                "POST",
                "/responses",
                json={
                    "model": model_name,
                    "input": prompt,
                    "store": False,
                    "stream": True,
                    "max_output_tokens": max_output_tokens,
                },
            ) as response:
                if not response.is_success:
                    raise ModelProviderError(_provider_http_error("openai", response))
                for raw_data in _iter_sse_data(response.iter_lines()):
                    if raw_data == "[DONE]":
                        break
                    try:
                        event = json.loads(raw_data)
                    except json.JSONDecodeError as exc:
                        raise ModelProviderError("openai returned an invalid streaming event") from exc
                    event_type = event.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            output_parts.append(delta)
                            yield ProviderStreamEvent(delta=delta)
                    elif event_type == "response.completed":
                        value = event.get("response")
                        if isinstance(value, dict):
                            completed_response = value
                    elif event_type in {"error", "response.failed", "response.incomplete"}:
                        raise ModelProviderError("openai streaming response failed")
        except ModelProviderError:
            raise
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"openai request failed: {exc.__class__.__name__}"
            ) from exc

        output = "".join(output_parts).strip()
        if not output:
            raise ModelProviderError("openai returned no text output")
        usage = (completed_response or {}).get("usage") or {}
        try:
            prompt_tokens = int(usage.get("input_tokens") or _estimate_tokens(prompt))
            completion_tokens = int(usage.get("output_tokens") or _estimate_tokens(output))
            total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
        except (TypeError, ValueError) as exc:
            raise ModelProviderError("openai returned invalid streaming usage") from exc
        yield ProviderStreamEvent(
            generation=ProviderGeneration(
                output, prompt_tokens, completion_tokens, total_tokens
            )
        )


class DeepSeekChatProvider:
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        *,
        default_model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ModelProviderConfigurationError(
                "DEEPSEEK_API_KEY is required for the deepseek provider"
            )
        _validate_base_url(base_url, "DEEPSEEK_BASE_URL")
        if not default_model.strip():
            raise ModelProviderConfigurationError(
                "AI_COMPANY_OS_DEEPSEEK_MODEL is required"
            )
        self.default_model = default_model.strip()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=timeout_seconds,
        )

    def generate(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> ProviderGeneration:
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"Complete the request for purpose: {purpose}.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "max_tokens": max_output_tokens,
                },
            )
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"deepseek request failed: {exc.__class__.__name__}"
            ) from exc
        if not response.is_success:
            raise ModelProviderError(_provider_http_error("deepseek", response))
        try:
            payload = response.json()
            output = _chat_completion_text(payload)
            usage = payload.get("usage") or {}
            prompt_tokens = int(
                usage.get("prompt_tokens") or _estimate_tokens(prompt)
            )
            completion_tokens = int(
                usage.get("completion_tokens") or _estimate_tokens(output)
            )
            total_tokens = int(
                usage.get("total_tokens") or prompt_tokens + completion_tokens
            )
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise ModelProviderError(
                "deepseek returned an invalid response payload"
            ) from exc
        if not output:
            raise ModelProviderError("deepseek returned no text output")
        return ProviderGeneration(output, prompt_tokens, completion_tokens, total_tokens)

    def stream(
        self, prompt: str, model_name: str, purpose: str, max_output_tokens: int
    ) -> Iterator[ProviderStreamEvent]:
        output_parts: list[str] = []
        final_usage: dict[str, Any] = {}
        try:
            with self._client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"Complete the request for purpose: {purpose}.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    "max_tokens": max_output_tokens,
                },
            ) as response:
                if not response.is_success:
                    raise ModelProviderError(_provider_http_error("deepseek", response))
                for raw_data in _iter_sse_data(response.iter_lines()):
                    if raw_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw_data)
                    except json.JSONDecodeError as exc:
                        raise ModelProviderError(
                            "deepseek returned an invalid streaming event"
                        ) from exc
                    usage = chunk.get("usage")
                    if isinstance(usage, dict):
                        final_usage = usage
                    choices = chunk.get("choices") or []
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta") if isinstance(choice, dict) else None
                    content = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(content, str) and content:
                        output_parts.append(content)
                        yield ProviderStreamEvent(delta=content)
        except ModelProviderError:
            raise
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"deepseek request failed: {exc.__class__.__name__}"
            ) from exc

        output = "".join(output_parts).strip()
        if not output:
            raise ModelProviderError("deepseek returned no text output")
        try:
            prompt_tokens = int(
                final_usage.get("prompt_tokens") or _estimate_tokens(prompt)
            )
            completion_tokens = int(
                final_usage.get("completion_tokens") or _estimate_tokens(output)
            )
            total_tokens = int(
                final_usage.get("total_tokens") or prompt_tokens + completion_tokens
            )
        except (TypeError, ValueError) as exc:
            raise ModelProviderError("deepseek returned invalid streaming usage") from exc
        yield ProviderStreamEvent(
            generation=ProviderGeneration(
                output, prompt_tokens, completion_tokens, total_tokens
            )
        )


def _response_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                value = content.get("text")
                if isinstance(value, str):
                    chunks.append(value)
    return "\n".join(chunks).strip()


def _chat_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message") or {}
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def _iter_sse_data(lines: Iterator[str]) -> Iterator[str]:
    data_lines: list[str] = []
    for line in lines:
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _provider_http_error(provider: str, response: httpx.Response) -> str:
    request_id = response.headers.get("x-request-id")
    suffix = f" (request {request_id})" if request_id else ""
    return f"{provider} returned HTTP {response.status_code}{suffix}"


def _codex_environment() -> dict[str, str]:
    allowed = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _CODEX_ENVIRONMENT_ALLOWLIST
    }
    allowed.update({"NO_COLOR": "1", "RUST_LOG": "error", "TERM": "dumb"})
    return allowed


def _codex_generation(stdout: str, prompt: str) -> ProviderGeneration:
    messages: list[str] = []
    usage: dict[str, Any] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                value = item.get("text")
                if isinstance(value, str) and value.strip():
                    messages.append(value.strip())
        elif event.get("type") == "turn.completed":
            value = event.get("usage")
            if isinstance(value, dict):
                usage = value
    output = "\n\n".join(messages).strip()
    if not output:
        raise ModelProviderError(_codex_failure_message(stdout, "", None))
    prompt_tokens = _non_negative_int(
        usage.get("input_tokens"), _estimate_tokens(prompt)
    )
    completion_tokens = _non_negative_int(
        usage.get("output_tokens"), _estimate_tokens(output)
    )
    return ProviderGeneration(
        output=output,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def _non_negative_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback


def _codex_failure_message(
    stdout: str, stderr: str, exit_code: int | None
) -> str:
    diagnostic = f"{stdout}\n{stderr}".lower()
    if any(
        marker in diagnostic
        for marker in ("usage limit", "purchase more credits", "rate limit")
    ):
        return "codex usage limit reached; try again later or select another provider"
    if "not logged in" in diagnostic or "authentication" in diagnostic:
        return "codex CLI is not authenticated"
    if "model" in diagnostic and any(
        marker in diagnostic
        for marker in ("not found", "not supported", "unavailable")
    ):
        return "the selected Codex model is unavailable"
    if exit_code is None:
        return "codex returned no text output"
    return f"codex CLI returned exit code {exit_code}"


def _validate_base_url(base_url: str, setting_name: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ModelProviderConfigurationError(
            f"{setting_name} must be an absolute HTTP(S) URL"
        )
    if parsed.username or parsed.password:
        raise ModelProviderConfigurationError(
            f"{setting_name} must not contain credentials"
        )
    if parsed.query or parsed.fragment:
        raise ModelProviderConfigurationError(
            f"{setting_name} must not contain a query or fragment"
        )
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ModelProviderConfigurationError(
            f"{setting_name} must use HTTPS unless it targets a loopback host"
        )


def _estimate_tokens(text: str) -> int:
    return 0 if not text else max(1, (len(text) + 3) // 4)
