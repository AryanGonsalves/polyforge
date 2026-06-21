"""
The Gateway.

One call site, many models. The gateway tries models in a configured order
and falls back automatically when one errors or has been shut down. It is
deprecation-aware: a model past its shutdown date is skipped before it can
even be attempted, and a model nearing shutdown raises a warning the caller
can surface.

This is the "a vanished model becomes a config change" promise made concrete:
to change behavior you edit the fallback order, not your application code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from polyforge.adapters.base import ModelRegistry, ModelRequest, ModelResponse
from polyforge.gateway.deprecation import DeprecationRegistry


@dataclass
class GatewayResult:
    response: ModelResponse
    model_used: str
    attempts: list[str] = field(default_factory=list)   # models tried, in order
    warnings: list[str] = field(default_factory=list)
    skipped_dead: list[str] = field(default_factory=list)


class ModelDeadError(RuntimeError):
    pass


class Gateway:
    def __init__(
        self,
        models: ModelRegistry,
        fallback_order: list[str],
        deprecations: DeprecationRegistry | None = None,
        warn_within_days: int = 90,
    ) -> None:
        self.models = models
        self.fallback_order = fallback_order
        self.deprecations = deprecations or DeprecationRegistry()
        self.warn_within_days = warn_within_days

    def preflight(self, today: date | None = None) -> list[str]:
        """Report deprecation issues across the configured chain, no calls made."""
        msgs: list[str] = []
        for name in self.fallback_order:
            status = self.deprecations.status(name, today, self.warn_within_days)
            if status == "dead":
                msgs.append(f"DEAD: '{name}' is past its shutdown date — remove it.")
            elif status == "warning":
                days = self.deprecations.days_until_shutdown(name, today)
                info = self.deprecations.lookup(name)
                rep = f" Replace with '{info.replacement}'." if info and info.replacement else ""
                msgs.append(f"WARNING: '{name}' shuts down in {days} days.{rep}")
        return msgs

    def generate(self, request: ModelRequest, today: date | None = None) -> GatewayResult:
        result = GatewayResult(response=None, model_used="")  # type: ignore[arg-type]
        last_error: Exception | None = None

        for name in self.fallback_order:
            status = self.deprecations.status(name, today, self.warn_within_days)
            if status == "dead":
                result.skipped_dead.append(name)
                continue
            if status == "warning":
                days = self.deprecations.days_until_shutdown(name, today)
                result.warnings.append(f"'{name}' shuts down in {days} days")

            result.attempts.append(name)
            try:
                adapter = self.models.get(name)
                resp = adapter.generate(request)
                result.response = resp
                result.model_used = name
                return result
            except Exception as e:  # adapter/provider failure -> fall back
                last_error = e
                continue

        raise ModelDeadError(
            f"All models exhausted. Tried={result.attempts}, "
            f"skipped_dead={result.skipped_dead}, last_error={last_error}"
        )
