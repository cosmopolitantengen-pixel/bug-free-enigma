from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Callable
from dataclasses import dataclass

from app.core.models import ModelUsageRecord
from app.models.providers import (
    DeepSeekChatProvider,
    DeterministicModelProvider,
    ModelProvider,
    ModelProviderConfigurationError,
    ModelProviderError,
    OpenAIResponsesProvider,
)
from app.secrets import read_secret


@dataclass(frozen=True)
class ModelResponse:
    output: str
    usage: ModelUsageRecord
    requested_provider: str
    attempted_providers: tuple[str, ...]
    fallback_used: bool


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.input_per_million)
            or not math.isfinite(self.output_per_million)
            or self.input_per_million < 0
            or self.output_per_million < 0
        ):
            raise ModelProviderConfigurationError(
                "model pricing must contain finite non-negative values"
            )

    def estimate(self, prompt_tokens: int, completion_tokens: int) -> float:
        amount = (
            prompt_tokens * self.input_per_million
            + completion_tokens * self.output_per_million
        ) / 1_000_000
        return round(amount, 9)

    def per_token_rates(self) -> tuple[float, float]:
        return (
            self.input_per_million / 1_000_000,
            self.output_per_million / 1_000_000,
        )


class ModelGateway:
    def __init__(
        self,
        usage_records: list[ModelUsageRecord] | None = None,
        *,
        providers: dict[str, ModelProvider] | None = None,
        default_provider: str = "local",
        allowed_models: dict[str, set[str]] | None = None,
        fallback_order: tuple[str, ...] | list[str] | None = None,
        pricing: dict[str, dict[str, ModelPricing]] | None = None,
    ) -> None:
        self._usage: list[ModelUsageRecord] = list(usage_records or [])
        self._providers = providers or {"local": DeterministicModelProvider()}
        if default_provider not in self._providers:
            raise ModelProviderConfigurationError(
                f"model provider is not configured: {default_provider}"
            )
        self.default_provider = default_provider
        self._fallback_order = tuple(fallback_order or ())
        if len(set(self._fallback_order)) != len(self._fallback_order):
            raise ModelProviderConfigurationError(
                "model fallback providers must not contain duplicates"
            )
        missing_fallbacks = [
            name for name in self._fallback_order if name not in self._providers
        ]
        if missing_fallbacks:
            raise ModelProviderConfigurationError(
                "model fallback provider is not configured: "
                + ", ".join(missing_fallbacks)
            )
        self._pricing = pricing or {}
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
        on_delta: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        provider_name = provider or self.default_provider
        selected_model = self._selected_model(provider_name, model_name)
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be greater than zero")
        attempts = self._generation_attempts(provider_name, selected_model)
        attempted_providers: list[str] = []
        last_error: ModelProviderError | None = None
        for attempt_provider, attempt_model in attempts:
            attempted_providers.append(attempt_provider)
            adapter = self._providers[attempt_provider]
            emitted_delta = False
            try:
                stream = getattr(adapter, "stream", None)
                if on_delta is not None and callable(stream):
                    generated = None
                    for event in stream(
                        prompt, attempt_model, purpose, max_output_tokens
                    ):
                        if event.delta:
                            emitted_delta = True
                            on_delta(event.delta)
                        if event.generation is not None:
                            generated = event.generation
                    if generated is None:
                        raise ModelProviderError(
                            f"{attempt_provider} stream ended without a final response"
                        )
                else:
                    generated = adapter.generate(
                        prompt, attempt_model, purpose, max_output_tokens
                    )
                    if on_delta is not None:
                        emitted_delta = True
                        on_delta(generated.output)
            except ModelProviderError as exc:
                last_error = exc
                if emitted_delta:
                    raise ModelProviderError(
                        f"{attempt_provider} stream was interrupted after partial output"
                    ) from exc
                continue
            pricing = self._pricing.get(attempt_provider, {}).get(attempt_model)
            estimated_cost = (
                pricing.estimate(
                    generated.prompt_tokens, generated.completion_tokens
                )
                if pricing
                else round(generated.total_tokens * cost_per_token, 9)
            )
            usage = self.record_usage(
                model_name=attempt_model,
                provider=attempt_provider,
                actor_id=actor_id,
                task_id=task_id,
                purpose=purpose,
                prompt_tokens=generated.prompt_tokens,
                completion_tokens=generated.completion_tokens,
                total_tokens=generated.total_tokens,
                cost_per_token=cost_per_token,
                estimated_cost=estimated_cost,
                input_ref=self.fingerprint(prompt, "input"),
                output_ref=self.fingerprint(generated.output, "output"),
            )
            return ModelResponse(
                output=generated.output,
                usage=usage,
                requested_provider=provider_name,
                attempted_providers=tuple(attempted_providers),
                fallback_used=attempt_provider != provider_name,
            )
        if len(attempted_providers) == 1 and last_error is not None:
            raise last_error
        raise ModelProviderError(
            "model providers failed: " + ", ".join(attempted_providers)
        ) from last_error

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
        estimated_cost: float | None = None,
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
            estimated_cost=(
                round(estimated_cost, 9)
                if estimated_cost is not None
                else round(total_tokens * cost_per_token, 9)
            ),
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
            "fallback_order": list(self._fallback_order),
            "provider_details": {
                name: {
                    "default_model": adapter.default_model,
                    "allowed_models": sorted(self._allowed_models.get(name, set())),
                    "pricing_usd_per_million": {
                        model: {
                            "input": rate.input_per_million,
                            "output": rate.output_per_million,
                        }
                        for model, rate in self._pricing.get(name, {}).items()
                    },
                }
                for name, adapter in sorted(self._providers.items())
            },
        }

    def budget_rates(
        self,
        provider: str | None,
        model_name: str | None,
        fallback_cost_per_token: float,
    ) -> tuple[float, float]:
        provider_name = provider or self.default_provider
        selected_model = self._selected_model(provider_name, model_name)
        rates: list[tuple[float, float]] = []
        for route_provider, route_model in self._generation_attempts(
            provider_name, selected_model
        ):
            pricing = self._pricing.get(route_provider, {}).get(route_model)
            rates.append(
                pricing.per_token_rates()
                if pricing
                else (fallback_cost_per_token, fallback_cost_per_token)
            )
        return (
            max(rate[0] for rate in rates),
            max(rate[1] for rate in rates),
        )

    def with_usage(self, usage_records: list[ModelUsageRecord]) -> ModelGateway:
        return ModelGateway(
            usage_records,
            providers=self._providers,
            default_provider=self.default_provider,
            allowed_models=self._allowed_models,
            fallback_order=self._fallback_order,
            pricing=self._pricing,
        )

    def _selected_model(self, provider_name: str, model_name: str | None) -> str:
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
        return selected_model

    def _generation_attempts(
        self, provider_name: str, selected_model: str
    ) -> list[tuple[str, str]]:
        attempts = [(provider_name, selected_model)]
        for fallback_provider in self._fallback_order:
            if fallback_provider == provider_name:
                continue
            adapter = self._providers[fallback_provider]
            fallback_model = adapter.default_model
            if fallback_model in self._allowed_models.get(fallback_provider, set()):
                attempts.append((fallback_provider, fallback_model))
        return attempts

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
    deepseek_api_key = (read_secret("DEEPSEEK_API_KEY", "") or "").strip()
    if deepseek_api_key:
        providers["deepseek"] = DeepSeekChatProvider(
            deepseek_api_key,
            default_model=os.getenv(
                "AI_COMPANY_OS_DEEPSEEK_MODEL", "deepseek-v4-flash"
            ),
            base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ),
            timeout_seconds=_timeout_seconds(),
        )
    default_provider = os.getenv("AI_COMPANY_OS_MODEL_PROVIDER", "local").strip().lower()
    allowed_models = {
        "local": {providers["local"].default_model},
    }
    if "openai" in providers:
        configured = _configured_models("AI_COMPANY_OS_ALLOWED_MODELS")
        allowed_models["openai"] = configured or {providers["openai"].default_model}
    if "deepseek" in providers:
        configured = _configured_models(
            "AI_COMPANY_OS_DEEPSEEK_ALLOWED_MODELS"
        )
        allowed_models["deepseek"] = configured or {
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        }
    pricing = {
        "deepseek": {
            "deepseek-v4-flash": ModelPricing(
                input_per_million=_price_per_million(
                    "AI_COMPANY_OS_DEEPSEEK_V4_FLASH_INPUT_PER_MILLION", 0.14
                ),
                output_per_million=_price_per_million(
                    "AI_COMPANY_OS_DEEPSEEK_V4_FLASH_OUTPUT_PER_MILLION", 0.28
                ),
            ),
            "deepseek-v4-pro": ModelPricing(
                input_per_million=_price_per_million(
                    "AI_COMPANY_OS_DEEPSEEK_V4_PRO_INPUT_PER_MILLION", 0.435
                ),
                output_per_million=_price_per_million(
                    "AI_COMPANY_OS_DEEPSEEK_V4_PRO_OUTPUT_PER_MILLION", 0.87
                ),
            ),
        }
    }
    return ModelGateway(
        usage_records,
        providers=providers,
        default_provider=default_provider,
        allowed_models=allowed_models,
        fallback_order=_configured_fallbacks(),
        pricing=pricing,
    )


def _configured_models(setting_name: str) -> set[str]:
    return {
        value.strip()
        for value in os.getenv(setting_name, "").split(",")
        if value.strip()
    }


def _configured_fallbacks() -> tuple[str, ...]:
    return tuple(
        value.strip().lower()
        for value in os.getenv("AI_COMPANY_OS_MODEL_FALLBACKS", "").split(",")
        if value.strip()
    )


def _price_per_million(setting_name: str, default: float) -> float:
    raw = os.getenv(setting_name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ModelProviderConfigurationError(
            f"{setting_name} must be numeric"
        ) from exc
    if not math.isfinite(value) or value < 0:
        raise ModelProviderConfigurationError(
            f"{setting_name} must be a finite non-negative value"
        )
    return value


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
