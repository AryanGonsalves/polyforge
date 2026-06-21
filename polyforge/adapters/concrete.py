"""
Concrete adapters.

- MockAdapter: deterministic, offline. Lets the whole pipeline run and be
  tested with zero credentials or network. This is what the demo uses.
- AnthropicAdapter: a real example showing how little code onboarding a
  provider takes. Activates only if `anthropic` is installed and a key is set.

Onboarding a future model = add one class like these. Nothing else changes.
"""
from __future__ import annotations

import os

from .base import Capabilities, ModelAdapter, ModelRequest, ModelResponse


class MockAdapter(ModelAdapter):
    def __init__(self, name: str = "mock-1", context: int = 200_000) -> None:
        self._name = name
        self._context = context

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(context_tokens=self._context, supports_tools=True,
                            notes="Offline deterministic stub")

    def generate(self, request: ModelRequest) -> ModelResponse:
        # Deterministic echo-style behavior so tests are stable.
        text = f"[{self._name}] processed {len(request.prompt)} chars"
        return ModelResponse(text=text, model=self._name, raw={"stub": True})


class FailingAdapter(ModelAdapter):
    """Always raises. Used to demonstrate/test fallback behavior."""

    def __init__(self, name: str = "broken-1") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(context_tokens=8_000, notes="Simulated outage")

    def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError(f"{self._name} is unavailable (simulated outage)")


class AnthropicAdapter(ModelAdapter):
    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self._model = model

    @property
    def name(self) -> str:
        return self._model

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(context_tokens=200_000, supports_tools=True)

    def generate(self, request: ModelRequest) -> ModelResponse:
        from anthropic import Anthropic  # imported lazily

        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model=self._model,
            max_tokens=request.max_tokens,
            system=request.system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": request.prompt}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return ModelResponse(text=text, model=self._model, raw={})
