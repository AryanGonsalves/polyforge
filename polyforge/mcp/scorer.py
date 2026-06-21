"""
MCP server reliability scoring.

Encodes the kind of reliability rubric teams are currently applying by hand
in blog posts: score each MCP server a project depends on, and classify it as
production-ready / lightly-maintained / dead so a dead server never gets wired
into an agent silently.

The score is computed from metadata about a server (commit recency, contributor
count, build status, etc.). Gathering that metadata (e.g. from GitHub) is a
separate concern — this module scores whatever signals it's given, so it stays
deterministic and testable. Unknown signals are treated conservatively.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Health(str, Enum):
    PRODUCTION = "production"   # 8-9
    LIGHT = "light"            # 5-7  -> use with fallback
    DEAD = "dead"              # 0-4  -> do not wire in


@dataclass
class ServerSignals:
    """Observable facts about an MCP server. All optional; None = unknown."""
    name: str
    last_commit: date | None = None
    contributor_count: int | None = None
    ci_passing: bool | None = None
    open_unpatched_cve: bool | None = None
    clean_install: bool | None = None
    uptime_30d: float | None = None        # 0.0-1.0 for hosted servers
    breaking_schema_change_90d: bool | None = None


@dataclass
class ScoreResult:
    name: str
    score: int
    max_score: int
    health: Health
    reasons: list[str] = field(default_factory=list)


def score_server(s: ServerSignals, today: date | None = None) -> ScoreResult:
    today = today or date.today()
    pts = 0
    reasons: list[str] = []

    # Commit recency: non-trivial commit in last 45 days
    if s.last_commit is not None:
        age = (today - s.last_commit).days
        if age <= 45:
            pts += 1
        else:
            reasons.append(f"last commit {age} days ago (>45)")
    else:
        reasons.append("commit recency unknown")

    # Sole-maintainer heuristic — the highest-signal "dead" indicator.
    if s.contributor_count is not None:
        if s.contributor_count >= 2:
            pts += 2
        else:
            reasons.append("single contributor (high abandonment risk)")
    else:
        reasons.append("contributor count unknown")

    # CI passing
    if s.ci_passing:
        pts += 1
    elif s.ci_passing is False:
        reasons.append("CI not passing")

    # No unpatched CVE
    if s.open_unpatched_cve is False:
        pts += 1
    elif s.open_unpatched_cve is True:
        reasons.append("unpatched CVE present")

    # Clean install from scratch
    if s.clean_install:
        pts += 1
    elif s.clean_install is False:
        reasons.append("clean install fails")

    # Hosted uptime
    if s.uptime_30d is not None:
        if s.uptime_30d >= 0.99:
            pts += 1
        else:
            reasons.append(f"uptime {s.uptime_30d:.1%} (<99%)")

    # Schema stability
    if s.breaking_schema_change_90d is False:
        pts += 1
    elif s.breaking_schema_change_90d is True:
        reasons.append("breaking schema change in last 90 days")

    max_score = 9
    if pts >= 8:
        health = Health.PRODUCTION
    elif pts >= 5:
        health = Health.LIGHT
    else:
        health = Health.DEAD

    return ScoreResult(s.name, pts, max_score, health, reasons)
