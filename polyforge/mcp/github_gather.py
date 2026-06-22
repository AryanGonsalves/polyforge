"""
Auto-gather reliability signals for an MCP server from its GitHub repository.

This is the "next phase" front-end to the scorer: instead of hand-writing
signals in YAML, fetch the cheap, high-signal ones — last commit date,
contributor count, and CI status — straight from the GitHub REST API, then hand
a ``ServerSignals`` to the existing scorer.

Design note: gathering is kept deliberately separate from scoring. The scorer
stays deterministic and testable; this module is the messy, network-facing part.
Anything we cannot fetch is left as ``None`` (unknown) — the scorer already
treats unknown conservatively (no credit). Use :func:`merge_signals` to fill
those gaps from a hand-written YAML entry.

Network access is injected (``http_get``) so this module is fully unit-testable
without touching the network.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import fields, replace
from datetime import date, datetime
from typing import Callable, Optional

from polyforge.mcp.scorer import ServerSignals

GITHUB_API = "https://api.github.com"

# An HTTP getter takes (url, headers) and returns
# (status_code: int, headers: dict[str, str], parsed_json: object | None).
HttpGet = Callable[[str, dict], tuple]


class GitHubGatherError(RuntimeError):
    """Raised on a bad repo URL, a missing repo, or an unreachable API."""


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract ``(owner, repo)`` from a GitHub URL or ``owner/repo`` shorthand.

    Accepts forms like:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        https://github.com/owner/repo/
        git@github.com:owner/repo.git
        owner/repo
    """
    s = url.strip().rstrip("/")
    s = re.sub(r"\.git$", "", s)
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+)$", s)
    if m:
        return m.group(1), m.group(2)
    m = re.fullmatch(r"([^/\s]+)/([^/\s]+)", s)
    if m:
        return m.group(1), m.group(2)
    raise GitHubGatherError(f"can't parse owner/repo from: {url!r}")


def _auth_headers(token: Optional[str]) -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "polyforge"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _default_http_get(url: str, headers: dict) -> tuple:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            data = json.loads(body) if body else None
            return resp.status, hdrs, data
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
        return e.code, hdrs, None
    except urllib.error.URLError as e:
        raise GitHubGatherError(f"network error fetching {url}: {e}") from e


def _fetch_last_commit(http_get: HttpGet, base: str, headers: dict) -> Optional[date]:
    status, _, data = http_get(f"{base}/commits?per_page=1", headers)
    if status == 200 and data:
        iso = data[0]["commit"]["committer"]["date"]  # e.g. 2026-05-25T12:00:00Z
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    return None


def _fetch_contributor_count(http_get: HttpGet, base: str, headers: dict) -> Optional[int]:
    # per_page=1 + anon=true makes the "last" page number equal the contributor
    # count, so we read it from the Link header instead of paging through everyone.
    status, hdrs, data = http_get(
        f"{base}/contributors?per_page=1&anon=true", headers
    )
    if status != 200:
        return None
    link = hdrs.get("link", "") or ""
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    if m:
        return int(m.group(1))
    return len(data) if isinstance(data, list) else None


def _fetch_ci_passing(http_get: HttpGet, base: str, headers: dict) -> Optional[bool]:
    status, _, data = http_get(f"{base}/actions/runs?per_page=1", headers)
    if status == 200 and data:
        runs = data.get("workflow_runs") or []
        if runs:
            return runs[0].get("conclusion") == "success"
    return None  # no Actions configured / no runs -> unknown


def gather_from_github(
    repo_url: str,
    *,
    name: Optional[str] = None,
    token: Optional[str] = None,
    http_get: Optional[HttpGet] = None,
) -> ServerSignals:
    """Fetch the auto-gatherable signals for a repo and return ``ServerSignals``.

    Only ``last_commit``, ``contributor_count`` and ``ci_passing`` are fetched.
    The remaining signals (CVE, clean install, uptime, schema stability) stay
    ``None`` (unknown) — fill them from YAML via :func:`merge_signals`.

    Pass ``token`` (or set ``GITHUB_TOKEN`` upstream) to raise the API rate
    limit. ``http_get`` can be injected in tests to avoid the network.

    Raises :class:`GitHubGatherError` if the URL can't be parsed, the repo
    doesn't exist (404), or the API is forbidden/rate-limited (403) — so a
    typo'd repo never silently masquerades as a DEAD server.
    """
    owner, repo = parse_repo_url(repo_url)
    http_get = http_get or _default_http_get
    headers = _auth_headers(token)
    base = f"{GITHUB_API}/repos/{owner}/{repo}"

    # Verify the repo first so errors are explicit, not silently scored DEAD.
    status, _, _ = http_get(base, headers)
    if status == 404:
        raise GitHubGatherError(f"repo not found: {owner}/{repo}")
    if status == 403:
        raise GitHubGatherError(
            "GitHub API forbidden or rate-limited — set a GITHUB_TOKEN "
            "(or --token) to raise the limit"
        )
    if status != 200:
        raise GitHubGatherError(
            f"GitHub API returned status {status} for {owner}/{repo}"
        )

    return ServerSignals(
        name=name or repo,
        last_commit=_fetch_last_commit(http_get, base, headers),
        contributor_count=_fetch_contributor_count(http_get, base, headers),
        ci_passing=_fetch_ci_passing(http_get, base, headers),
        # Everything below stays unknown; gather only covers cheap GitHub signals.
    )


def merge_signals(primary: ServerSignals, fallback: ServerSignals) -> ServerSignals:
    """Combine signals: ``primary`` wins, but any ``None`` field falls back.

    Intended use: ``merge_signals(fetched_from_github, hand_written_yaml)`` so
    that anything the auto-gatherer could not determine is filled in from the
    YAML entry. The ``name`` is always kept from ``primary``.
    """
    updates = {}
    for f in fields(primary):
        if f.name == "name":
            continue
        if getattr(primary, f.name) is None and getattr(fallback, f.name) is not None:
            updates[f.name] = getattr(fallback, f.name)
    return replace(primary, **updates)
