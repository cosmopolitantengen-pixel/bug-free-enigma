from __future__ import annotations

from dataclasses import dataclass
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


def _provider_http_error(provider: str, response: httpx.Response) -> str:
    request_id = response.headers.get("x-request-id")
    suffix = f" (request {request_id})" if request_id else ""
    return f"{provider} returned HTTP {response.status_code}{suffix}"


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
