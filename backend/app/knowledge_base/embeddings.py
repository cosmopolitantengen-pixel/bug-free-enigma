from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx


EMBEDDING_DIMENSIONS = 1536


class EmbeddingProviderError(RuntimeError):
    """A sanitized embedding failure that is safe to expose to operators."""


class EmbeddingProviderConfigurationError(EmbeddingProviderError):
    pass


@dataclass(frozen=True)
class ProviderEmbedding:
    values: list[float]
    input_tokens: int


@dataclass(frozen=True)
class EmbeddingResult:
    values: list[float]
    input_tokens: int
    provider: str
    model_name: str
    input_ref: str


class EmbeddingProvider(Protocol):
    name: str
    default_model: str

    def embed(self, text: str, model_name: str) -> ProviderEmbedding: ...


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        *,
        default_model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise EmbeddingProviderConfigurationError(
                "OPENAI_API_KEY is required for the openai embedding provider"
            )
        _validate_base_url(base_url)
        if not default_model.strip():
            raise EmbeddingProviderConfigurationError(
                "AI_COMPANY_OS_EMBEDDING_MODEL is required"
            )
        self.default_model = default_model.strip()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=timeout_seconds,
        )

    def embed(self, text: str, model_name: str) -> ProviderEmbedding:
        try:
            response = self._client.post(
                "/embeddings",
                json={
                    "model": model_name,
                    "input": text,
                    "dimensions": EMBEDDING_DIMENSIONS,
                    "encoding_format": "float",
                },
            )
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(
                f"openai embedding request failed: {exc.__class__.__name__}"
            ) from exc
        if not response.is_success:
            request_id = response.headers.get("x-request-id")
            suffix = f" (request {request_id})" if request_id else ""
            raise EmbeddingProviderError(
                f"openai embeddings returned HTTP {response.status_code}{suffix}"
            )
        try:
            payload = response.json()
            values = [float(value) for value in payload["data"][0]["embedding"]]
            input_tokens = int((payload.get("usage") or {}).get("prompt_tokens") or 0)
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise EmbeddingProviderError(
                "openai embeddings returned an invalid response payload"
            ) from exc
        _validate_embedding(values)
        return ProviderEmbedding(values=values, input_tokens=input_tokens)


class EmbeddingGateway:
    def __init__(
        self,
        *,
        providers: dict[str, EmbeddingProvider] | None = None,
        default_provider: str = "disabled",
    ) -> None:
        self._providers = providers or {}
        self.default_provider = default_provider
        if self.enabled and default_provider not in self._providers:
            raise EmbeddingProviderConfigurationError(
                f"embedding provider is not configured: {default_provider}"
            )

    @property
    def enabled(self) -> bool:
        return self.default_provider != "disabled"

    def embed(
        self,
        text: str,
        *,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> EmbeddingResult:
        provider_name = provider or self.default_provider
        adapter = self._providers.get(provider_name)
        if adapter is None:
            raise EmbeddingProviderConfigurationError(
                f"embedding provider is not configured: {provider_name}"
            )
        selected_model = model_name or adapter.default_model
        result = adapter.embed(text, selected_model)
        _validate_embedding(result.values)
        return EmbeddingResult(
            values=result.values,
            input_tokens=result.input_tokens or _estimate_tokens(text),
            provider=provider_name,
            model_name=selected_model,
            input_ref=_fingerprint(text),
        )

    def status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "default_provider": self.default_provider,
            "providers": sorted(self._providers),
            "default_model": (
                self._providers[self.default_provider].default_model if self.enabled else None
            ),
            "dimensions": EMBEDDING_DIMENSIONS,
        }


def create_embedding_gateway() -> EmbeddingGateway:
    providers: dict[str, EmbeddingProvider] = {}
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        providers["openai"] = OpenAIEmbeddingProvider(
            api_key,
            default_model=os.getenv(
                "AI_COMPANY_OS_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=_timeout_seconds(),
        )
    return EmbeddingGateway(
        providers=providers,
        default_provider=os.getenv(
            "AI_COMPANY_OS_EMBEDDING_PROVIDER", "disabled"
        ).strip().lower(),
    )


def _validate_embedding(values: list[float]) -> None:
    if len(values) != EMBEDDING_DIMENSIONS:
        raise EmbeddingProviderError(
            f"embedding must contain exactly {EMBEDDING_DIMENSIONS} dimensions"
        )
    if not all(math.isfinite(value) for value in values):
        raise EmbeddingProviderError("embedding contains non-finite values")


def _fingerprint(text: str) -> str:
    return f"input_sha256_{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _estimate_tokens(text: str) -> int:
    return 0 if not text else max(1, (len(text) + 3) // 4)


def _timeout_seconds() -> float:
    raw = os.getenv("AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS", "60")
    try:
        value = float(raw)
    except ValueError as exc:
        raise EmbeddingProviderConfigurationError(
            "AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS must be numeric"
        ) from exc
    if value <= 0 or value > 300:
        raise EmbeddingProviderConfigurationError(
            "AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS must be between 0 and 300"
        )
    return value


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise EmbeddingProviderConfigurationError(
            "OPENAI_BASE_URL must be an absolute HTTP(S) URL"
        )
    if parsed.username or parsed.password:
        raise EmbeddingProviderConfigurationError(
            "OPENAI_BASE_URL must not contain credentials"
        )
    if parsed.query or parsed.fragment:
        raise EmbeddingProviderConfigurationError(
            "OPENAI_BASE_URL must not contain a query or fragment"
        )
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise EmbeddingProviderConfigurationError(
            "OPENAI_BASE_URL must use HTTPS unless it targets a loopback host"
        )
