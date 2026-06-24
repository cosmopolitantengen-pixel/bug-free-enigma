from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from app.core.models import ModelUsageRecord
from app.models.providers import (
    DeterministicModelProvider,
    ModelProvider,
    ModelProviderConfigurationError,
    OpenAIResponsesProvider,
)
from app.secrets import read_secret


@dataclass(frozen=True)
class ModelResponse:
    output: str
    usage: ModelUsageRecord


class ModelGateway:
    def __init__(
        self,
        usage_records: list[ModelUsageRecord] | None = None,
        *,
        providers: dict[str, ModelProvider] | None = None,
        default_provider: str = "local",
        allowed_models: dict[str, set[str]] | None = None,
    ) -> None:
        self._usage: list[ModelUsageRecord] = list(usage_records or [])
        self._providers = providers or {"local": DeterministicModelProvider()}
        if default_provider not in self._providers:
            raise ModelProviderConfigurationError(
                f"model provider is not configured: {default_provider}"
            )
        self.default_provider = default_provider
        self._allowed_models = allowed_models or {
            name: {adapter.default_model} for name, adapter in self._providers.items()
        }
        for name, adapter in self._providers.items():
            configured = self._allowed_models.setdefault(name, set())
            configured.add(adapter.default_model)

    def generate(
        self,
        prompt: str,
        actor_id: str,
        purpose: str,
        task_id: str | None = None,
        model_name: str | None = None,
        provider: str | None = None,
        cost_per_token: float = 0.000001,
        max_output_tokens: int = 1024,
    ) -> ModelResponse:
        provider_name = provider or self.default_provider
        adapter = self._providers.get(provider_name)
        if adapter is None:
            raise ModelProviderConfigurationError(
                f"model provider is not configured: {provider_name}"
            )
        selected_model = model_name or adapter.default_model
        if selected_model not in self._allowed_models.get(provider_name, set()):
            raise ModelProviderConfigurationError(
                f"model is not allowlisted for {provider_name}: {selected_model}"
            )
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be greater than zero")
        generated = adapter.generate(
            prompt, selected_model, purpose, max_output_tokens
        )
        usage = self.record_usage(
            model_name=selected_model,
            provider=provider_name,
            actor_id=actor_id,
            task_id=task_id,
            purpose=purpose,
            prompt_tokens=generated.prompt_tokens,
            completion_tokens=generated.completion_tokens,
            total_tokens=generated.total_tokens,
            cost_per_token=cost_per_token,
            input_ref=self.fingerprint(prompt, "input"),
            output_ref=self.fingerprint(generated.output, "output"),
        )
        return ModelResponse(output=generated.output, usage=usage)

    def record_usage(
        self,
        *,
        model_name: str,
        provider: str,
        actor_id: str,
        task_id: str | None,
        purpose: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_per_token: float,
        input_ref: str,
        output_ref: str,
    ) -> ModelUsageRecord:
        usage = ModelUsageRecord(
            model_name=model_name,
            provider=provider,
            actor_id=actor_id,
            task_id=task_id,
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=round(total_tokens * cost_per_token, 6),
            input_ref=input_ref,
            output_ref=output_ref,
        )
        self._usage.append(usage)
        return usage

    def list_usage(self) -> list[ModelUsageRecord]:
        return list(self._usage)

    def provider_status(self) -> dict[str, object]:
        return {
            "default_provider": self.default_provider,
            "providers": sorted(self._providers),
            "default_model": self._providers[self.default_provider].default_model,
            "allowed_models": {
                name: sorted(models) for name, models in self._allowed_models.items()
            },
        }

    def with_usage(self, usage_records: list[ModelUsageRecord]) -> ModelGateway:
        return ModelGateway(
            usage_records,
            providers=self._providers,
            default_provider=self.default_provider,
            allowed_models=self._allowed_models,
        )

    @staticmethod
    def fingerprint(value: str, kind: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{kind}_sha256_{digest}"


def create_model_gateway(
    usage_records: list[ModelUsageRecord] | None = None,
) -> ModelGateway:
    providers: dict[str, ModelProvider] = {"local": DeterministicModelProvider()}
    api_key = (read_secret("OPENAI_API_KEY", "") or "").strip()
    if api_key:
        providers["openai"] = OpenAIResponsesProvider(
            api_key,
            default_model=os.getenv("AI_COMPANY_OS_MODEL_NAME", "gpt-4.1-mini"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=_timeout_seconds(),
        )
    default_provider = os.getenv("AI_COMPANY_OS_MODEL_PROVIDER", "local").strip().lower()
    allowed_models = {
        "local": {providers["local"].default_model},
    }
    if "openai" in providers:
        configured = {
            value.strip()
            for value in os.getenv("AI_COMPANY_OS_ALLOWED_MODELS", "").split(",")
            if value.strip()
        }
        allowed_models["openai"] = configured or {providers["openai"].default_model}
    return ModelGateway(
        usage_records,
        providers=providers,
        default_provider=default_provider,
        allowed_models=allowed_models,
    )


def _timeout_seconds() -> float:
    raw = os.getenv("AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS", "60")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ModelProviderConfigurationError(
            "AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS must be numeric"
        ) from exc
    if value <= 0 or value > 300:
        raise ModelProviderConfigurationError(
            "AI_COMPANY_OS_PROVIDER_TIMEOUT_SECONDS must be between 0 and 300"
        )
    return value
