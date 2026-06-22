"""Tests for manifest loading + optional GitHub enrichment.

Network is mocked via injected ``http_get``; deterministic and offline.
"""
from datetime import date

from polyforge.mcp.manifest import load_manifest_signals, signals_from_entry
from polyforge.mcp.scorer import Health, score_server


class FakeHTTP:
    """Route by URL path suffix; non-endpoint paths are the repo-root call."""

    def __init__(self, routes=None, repo_status=200):
        self.routes = routes or {}
        self.repo_status = repo_status

    def __call__(self, url, headers):
        path = url.split("?", 1)[0]
        for suffix, resp in self.routes.items():
            if path.endswith(suffix):
                return resp
        return self.repo_status, {}, {"full_name": "owner/repo"}


def healthy_routes():
    return {
        "/commits": (200, {}, [{"commit": {"committer": {"date": "2026-05-25T12:00:00Z"}}}]),
        "/contributors": (200, {"link": '<https://api.github.com/x?page=12>; rel="last"'}, [{"login": "a"}]),
        "/actions/runs": (200, {}, {"workflow_runs": [{"conclusion": "success"}]}),
    }


def test_signals_from_entry_parses_dates_and_fields():
    s = signals_from_entry({
        "name": "srv", "last_commit": "2026-04-10", "contributor_count": 3,
        "ci_passing": True, "open_unpatched_cve": False,
    })
    assert s.name == "srv"
    assert s.last_commit == date(2026, 4, 10)
    assert s.contributor_count == 3
    assert s.ci_passing is True
    assert s.uptime_30d is None  # unspecified -> unknown


def test_load_without_gather_is_yaml_only():
    entries = [{"name": "srv", "repo": "owner/repo", "contributor_count": 9}]
    signals, warnings = load_manifest_signals(entries, gather=False, http_get=FakeHTTP(healthy_routes()))
    assert warnings == []
    assert signals[0].contributor_count == 9
    assert signals[0].last_commit is None  # not fetched, not in YAML


def test_load_with_gather_merges_github_over_yaml():
    entries = [{
        "name": "srv",
        "repo": "https://github.com/owner/repo",
        # YAML provides the signals GitHub can't:
        "open_unpatched_cve": False,
        "clean_install": True,
        "uptime_30d": 0.999,
        "breaking_schema_change_90d": False,
    }]
    signals, warnings = load_manifest_signals(
        entries, gather=True, http_get=FakeHTTP(healthy_routes())
    )
    assert warnings == []
    s = signals[0]
    assert s.name == "srv"
    assert s.last_commit == date(2026, 5, 25)   # from GitHub
    assert s.contributor_count == 12            # from GitHub
    assert s.ci_passing is True                 # from GitHub
    assert s.clean_install is True              # from YAML
    r = score_server(s, today=date(2026, 6, 1))
    assert r.score == 8 and r.health == Health.PRODUCTION


def test_gather_failure_degrades_to_yaml_with_warning():
    entries = [{
        "name": "srv", "repo": "owner/missing",
        "contributor_count": 5, "ci_passing": True,
    }]
    signals, warnings = load_manifest_signals(
        entries, gather=True, http_get=FakeHTTP(repo_status=404)
    )
    assert len(signals) == 1
    assert signals[0].contributor_count == 5    # fell back to YAML
    assert len(warnings) == 1
    assert "could not gather" in warnings[0]
    assert "srv" in warnings[0]


def test_entry_without_repo_is_not_gathered():
    entries = [{"name": "srv", "contributor_count": 2}]  # no 'repo'
    signals, warnings = load_manifest_signals(
        entries, gather=True, http_get=FakeHTTP(healthy_routes())
    )
    assert warnings == []
    assert signals[0].contributor_count == 2
    assert signals[0].last_commit is None       # never fetched
