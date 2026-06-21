"""
Model adapter layer.

The whole point: when a new AI model releases, you write ONE adapter that
conforms to ModelAdapter — you do not touch any block or orchestration code.

Adapters normalize the *interface*. They cannot normalize *capability*
(context window, reasoning quality), so each adapter advertises its
capabilities and the orchestrator can route accordingly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Capabilities:
    context_tokens: int
    supports_tools: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    system: str = ""
    max_tokens: int = 1024


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str
    raw: dict = field(default_factory=dict)


class ModelAdapter(ABC):
    """Implement these four members to onboard any model."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class ModelRegistry:
    """Holds adapters and provides capability-based selection + fallback."""

    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}

    def register(self, adapter: ModelAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ModelAdapter:
        if name not in self._adapters:
            raise KeyError(f"No adapter named '{name}'. Have: {list(self._adapters)}")
        return self._adapters[name]

    def select(self, min_context: int = 0, needs_tools: bool = False) -> ModelAdapter:
        """Pick the first adapter that meets the capability floor."""
        for adapter in self._adapters.values():
            c = adapter.capabilities
            if c.context_tokens >= min_context and (c.supports_tools or not needs_tools):
                return adapter
        raise RuntimeError("No registered adapter meets the required capabilities")

    def names(self) -> list[str]:
        return list(self._adapters)
