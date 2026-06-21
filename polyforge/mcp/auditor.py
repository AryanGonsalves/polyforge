"""
MCP auditor + fallback router.

Auditor: scores a set of MCP servers and reports which are safe to wire into
an agent, which need fallback, and which are dead.

FallbackRouter: given a capability backed by several candidate servers (in
preference order), picks the healthiest usable one and skips dead ones — the
same fallback principle proven in the model gateway, applied to tools so a
dead/drifted server can't silently corrupt an agent's workflow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from polyforge.mcp.scorer import Health, ScoreResult, ServerSignals, score_server


@dataclass
class AuditReport:
    results: list[ScoreResult] = field(default_factory=list)

    @property
    def dead(self) -> list[ScoreResult]:
        return [r for r in self.results if r.health == Health.DEAD]

    @property
    def needs_fallback(self) -> list[ScoreResult]:
        return [r for r in self.results if r.health == Health.LIGHT]

    @property
    def production(self) -> list[ScoreResult]:
        return [r for r in self.results if r.health == Health.PRODUCTION]


def audit(servers: list[ServerSignals], today: date | None = None) -> AuditReport:
    return AuditReport(results=[score_server(s, today) for s in servers])


class NoHealthyServerError(RuntimeError):
    pass


class FallbackRouter:
    """Resolve a capability to the best usable server, skipping dead ones."""

    def __init__(self, servers: list[ServerSignals], today: date | None = None) -> None:
        self._today = today
        # Pre-score once; map name -> (signals, result)
        self._scored = {s.name: (s, score_server(s, today)) for s in servers}

    def resolve(self, preference_order: list[str]) -> ScoreResult:
        skipped: list[str] = []
        for name in preference_order:
            entry = self._scored.get(name)
            if entry is None:
                skipped.append(f"{name}(unknown)")
                continue
            _, result = entry
            if result.health == Health.DEAD:
                skipped.append(f"{name}(dead)")
                continue
            # production or light-with-fallback are both usable; prefer first.
            return result
        raise NoHealthyServerError(
            f"No usable server in {preference_order}. Skipped: {skipped}"
        )
