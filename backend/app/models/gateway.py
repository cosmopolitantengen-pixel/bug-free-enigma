from __future__ import annotations

from dataclasses import dataclass

from app.core.models import ModelUsageRecord


@dataclass(frozen=True)
class ModelResponse:
    output: str
    usage: ModelUsageRecord


class ModelGateway:
    def __init__(self, usage_records: list[ModelUsageRecord] | None = None) -> None:
        self._usage: list[ModelUsageRecord] = list(usage_records or [])

    def generate(
        self,
        prompt: str,
        actor_id: str,
        purpose: str,
        task_id: str | None = None,
        model_name: str = "deterministic_mock_v1",
        provider: str = "local",
        cost_per_token: float = 0.000001,
    ) -> ModelResponse:
        output = self._mock_generate(prompt, purpose)
        prompt_tokens = self._estimate_tokens(prompt)
        completion_tokens = self._estimate_tokens(output)
        usage = ModelUsageRecord(
            model_name=model_name,
            provider=provider,
            actor_id=actor_id,
            task_id=task_id,
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=round((prompt_tokens + completion_tokens) * cost_per_token, 6),
            input_ref=self._fingerprint(prompt),
            output_ref=self._fingerprint(output),
        )
        self._usage.append(usage)
        return ModelResponse(output=output, usage=usage)

    def list_usage(self) -> list[ModelUsageRecord]:
        return list(self._usage)

    def _mock_generate(self, prompt: str, purpose: str) -> str:
        compact = " ".join(prompt.split())
        if len(compact) > 180:
            compact = f"{compact[:177]}..."
        return f"[{purpose}] Deterministic model response: {compact}"

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    def _fingerprint(self, text: str) -> str:
        checksum = sum(ord(char) for char in text) % 1_000_000
        return f"mock_ref_{checksum:06d}_{len(text)}"
