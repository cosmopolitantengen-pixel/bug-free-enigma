from __future__ import annotations

from dataclasses import replace

from app.core.models import BudgetCheck, BudgetPolicy, CostLog


class BudgetGuard:
    def __init__(
        self,
        policy: BudgetPolicy | None = None,
        cost_logs: list[CostLog] | None = None,
    ) -> None:
        self.policy = policy or BudgetPolicy()
        self._cost_logs: list[CostLog] = list(cost_logs or [])

    def check_model_call(self, prompt: str, purpose: str) -> BudgetCheck:
        estimated_tokens = self._estimate_tokens(prompt) + self._estimate_tokens(self._mock_response(prompt, purpose))
        estimated_cost = self.estimate_cost(estimated_tokens)
        spent_tokens = sum(log.tokens for log in self._cost_logs if log.result == "recorded")
        spent_cost = sum(log.amount for log in self._cost_logs if log.result == "recorded")

        if not self.policy.enabled:
            return BudgetCheck(True, "budget policy disabled", estimated_tokens, estimated_cost, self.policy.policy_id)
        if estimated_tokens > self.policy.max_tokens_per_call:
            return BudgetCheck(False, "model call exceeds per-call token budget", estimated_tokens, estimated_cost, self.policy.policy_id)
        if spent_tokens + estimated_tokens > self.policy.max_total_tokens:
            return BudgetCheck(False, "model call exceeds total token budget", estimated_tokens, estimated_cost, self.policy.policy_id)
        if spent_cost + estimated_cost > self.policy.max_estimated_cost:
            return BudgetCheck(False, "model call exceeds estimated cost budget", estimated_tokens, estimated_cost, self.policy.policy_id)
        return BudgetCheck(True, "budget allowed", estimated_tokens, estimated_cost, self.policy.policy_id)

    def estimate_cost(self, tokens: int) -> float:
        return round(tokens * self.policy.cost_per_token, 6)

    def max_output_tokens(self, prompt: str) -> int:
        prompt_tokens = self._estimate_tokens(prompt)
        if not self.policy.enabled:
            return max(1, self.policy.max_tokens_per_call - prompt_tokens)
        spent_tokens = sum(log.tokens for log in self._cost_logs if log.result == "recorded")
        spent_cost = sum(log.amount for log in self._cost_logs if log.result == "recorded")
        limits = [
            self.policy.max_tokens_per_call - prompt_tokens,
            self.policy.max_total_tokens - spent_tokens - prompt_tokens,
        ]
        if self.policy.cost_per_token > 0:
            remaining_cost_tokens = int(
                max(0, self.policy.max_estimated_cost - spent_cost)
                / self.policy.cost_per_token
            )
            limits.append(remaining_cost_tokens - prompt_tokens)
        return max(1, min(limits))

    def record_cost(
        self,
        source_type: str,
        source_id: str,
        actor_id: str,
        task_id: str | None,
        tokens: int,
        amount: float,
        result: str,
        reason: str,
    ) -> CostLog:
        log = CostLog(
            source_type=source_type,
            source_id=source_id,
            actor_id=actor_id,
            task_id=task_id,
            tokens=tokens,
            amount=amount,
            currency=self.policy.currency,
            result=result,
            reason=reason,
        )
        self._cost_logs.append(log)
        return log

    def list_cost_logs(self) -> list[CostLog]:
        return list(self._cost_logs)

    def update_policy(
        self,
        name: str,
        max_tokens_per_call: int,
        max_total_tokens: int,
        max_estimated_cost: float,
        cost_per_token: float,
        currency: str,
        enabled: bool,
    ) -> BudgetPolicy:
        if not name.strip():
            raise ValueError("budget policy name is required")
        if max_tokens_per_call <= 0:
            raise ValueError("max_tokens_per_call must be greater than zero")
        if max_total_tokens <= 0:
            raise ValueError("max_total_tokens must be greater than zero")
        if max_total_tokens < max_tokens_per_call:
            raise ValueError("max_total_tokens must be greater than or equal to max_tokens_per_call")
        if max_estimated_cost < 0:
            raise ValueError("max_estimated_cost cannot be negative")
        if cost_per_token < 0:
            raise ValueError("cost_per_token cannot be negative")
        if not currency.strip():
            raise ValueError("currency is required")

        self.policy = replace(
            self.policy,
            name=name.strip(),
            max_tokens_per_call=max_tokens_per_call,
            max_total_tokens=max_total_tokens,
            max_estimated_cost=max_estimated_cost,
            cost_per_token=cost_per_token,
            currency=currency.strip().upper(),
            enabled=enabled,
        )
        return self.policy

    def summary(self) -> dict:
        recorded = [log for log in self._cost_logs if log.result == "recorded"]
        return {
            "policy_id": self.policy.policy_id,
            "policy_name": self.policy.name,
            "enabled": self.policy.enabled,
            "max_tokens_per_call": self.policy.max_tokens_per_call,
            "max_total_tokens": self.policy.max_total_tokens,
            "max_estimated_cost": self.policy.max_estimated_cost,
            "currency": self.policy.currency,
            "used_tokens": sum(log.tokens for log in recorded),
            "used_cost": round(sum(log.amount for log in recorded), 6),
            "cost_log_count": len(self._cost_logs),
        }

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    def _mock_response(self, prompt: str, purpose: str) -> str:
        compact = " ".join(prompt.split())
        if len(compact) > 180:
            compact = f"{compact[:177]}..."
        return f"[{purpose}] Deterministic model response: {compact}"
