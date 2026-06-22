"""
Load MCP server signals from a YAML manifest, optionally enriching each entry
with auto-gathered GitHub signals.

A manifest entry is a plain dict (already parsed from YAML) with a ``name`` and
any of the scorer's signal fields. It may also carry an optional ``repo`` field
(a GitHub URL or ``owner/repo`` shorthand). When gathering is enabled, entries
with a ``repo`` get their ``last_commit`` / ``contributor_count`` / ``ci_passing``
fetched live and merged over the hand-written YAML (live data wins; YAML fills
the signals GitHub can't provide).

Gathering is opt-in and fails soft: if a single repo can't be fetched, that
entry degrades to its YAML-only signals and a warning is collected, so one bad
repo never aborts a whole audit. Network access is injected (``http_get``) for
testability.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from polyforge.mcp.github_gather import (
    GitHubGatherError,
    HttpGet,
    gather_from_github,
    merge_signals,
)
from polyforge.mcp.scorer import ServerSignals


def _to_date(v) -> Optional[date]:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def signals_from_entry(entry: dict) -> ServerSignals:
    """Build ``ServerSignals`` from a single parsed-YAML manifest entry."""
    return ServerSignals(
        name=entry["name"],
        last_commit=_to_date(entry.get("last_commit")),
        contributor_count=entry.get("contributor_count"),
        ci_passing=entry.get("ci_passing"),
        open_unpatched_cve=entry.get("open_unpatched_cve"),
        clean_install=entry.get("clean_install"),
        uptime_30d=entry.get("uptime_30d"),
        breaking_schema_change_90d=entry.get("breaking_schema_change_90d"),
    )


def load_manifest_signals(
    entries: list[dict],
    *,
    gather: bool = False,
    token: Optional[str] = None,
    http_get: Optional[HttpGet] = None,
) -> tuple[list[ServerSignals], list[str]]:
    """Turn manifest entries into ``ServerSignals``, optionally GitHub-enriched.

    Returns ``(signals, warnings)``. With ``gather=True``, any entry that has a
    ``repo`` field is fetched from GitHub and merged over its YAML signals
    (fetched wins; YAML fills the gaps). A per-repo fetch failure degrades to
    YAML-only signals and appends a human-readable warning rather than raising.
    """
    signals: list[ServerSignals] = []
    warnings: list[str] = []

    for entry in entries:
        hand = signals_from_entry(entry)
        repo = entry.get("repo")
        if gather and repo:
            try:
                fetched = gather_from_github(
                    repo, name=entry["name"], token=token, http_get=http_get
                )
                signals.append(merge_signals(fetched, hand))
            except GitHubGatherError as e:
                warnings.append(
                    f"{entry['name']}: could not gather from '{repo}' ({e}); "
                    f"using YAML signals only"
                )
                signals.append(hand)
        else:
            signals.append(hand)

    return signals, warnings
