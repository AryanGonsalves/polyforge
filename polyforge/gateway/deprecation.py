"""
Deprecation registry.

Holds known shutdown dates for models so the gateway can warn *before* a model
vanishes — turning a surprise outage into a planned config change. Dates are
data, not code: ship a default snapshot and let users override/extend it.

This is deliberately a static, user-maintainable table. A live-updating feed
is a later phase; correctness here matters more than freshness, and a wrong
auto-fetched date is worse than a known-stale one a human curated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DeprecationInfo:
    model: str
    shutdown_date: date
    replacement: str = ""
    note: str = ""


# Default snapshot. Users should treat this as a starting point and override
# with their own source of truth. Dates reflect publicly announced shutdowns.
_DEFAULT: dict[str, DeprecationInfo] = {
    "claude-3-opus-20240229": DeprecationInfo(
        "claude-3-opus-20240229", date(2026, 1, 5), "claude-opus-4-8",
        "Original flagship Claude retired"),
    "claude-sonnet-4-0": DeprecationInfo(
        "claude-sonnet-4-0", date(2026, 6, 15), "claude-sonnet-4-6"),
    "claude-opus-4-0": DeprecationInfo(
        "claude-opus-4-0", date(2026, 6, 15), "claude-opus-4-8"),
    "claude-3-5-haiku": DeprecationInfo(
        "claude-3-5-haiku", date(2026, 7, 5), "claude-haiku-4-5-20251001"),
    "gpt-4o": DeprecationInfo(
        "gpt-4o", date(2026, 2, 28), "gpt-5", "Retired from ChatGPT Feb 2026"),
    "o4-mini": DeprecationInfo(
        "o4-mini", date(2026, 2, 28), "gpt-5"),
}


class DeprecationRegistry:
    def __init__(self, entries: dict[str, DeprecationInfo] | None = None) -> None:
        self._entries = dict(_DEFAULT if entries is None else entries)

    def add(self, info: DeprecationInfo) -> None:
        self._entries[info.model] = info

    def lookup(self, model: str) -> DeprecationInfo | None:
        return self._entries.get(model)

    def days_until_shutdown(self, model: str, today: date | None = None) -> int | None:
        info = self._entries.get(model)
        if info is None:
            return None
        return (info.shutdown_date - (today or date.today())).days

    def status(self, model: str, today: date | None = None,
               warn_within_days: int = 90) -> str:
        """Return 'ok', 'warning', or 'dead' for a model."""
        days = self.days_until_shutdown(model, today)
        if days is None:
            return "ok"          # unknown = not flagged
        if days < 0:
            return "dead"
        if days <= warn_within_days:
            return "warning"
        return "ok"
