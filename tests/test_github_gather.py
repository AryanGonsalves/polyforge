"""Tests for the GitHub signal gatherer.

All HTTP is mocked via an injected ``http_get`` so these tests are
deterministic and never touch the network (same philosophy as the scorer).
"""
from datetime import date

import pytest

from polyforge.mcp.github_gather import (
    GitHubGatherError,
    gather_from_github,
    merge_signals,
    parse_repo_url,
)
from polyforge.mcp.scorer import Health, ServerSignals, score_server


class FakeHTTP:
    """Route canned responses by URL path suffix (query string ignored).

    Any path not matching a sub-endpoint suffix is treated as the repo-root
    call and answered with ``repo_status`` — letting tests simulate 404/403.
    """

    def __init__(self, routes=None, repo_status=200, repo_data=None):
        self.routes = routes or {}
        self.repo_status = repo_status
        self.repo_data = repo_data if repo_data is not None else {"full_name": "owner/repo"}
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        path = url.split("?", 1)[0]
        for suffix, resp in self.routes.items():
            if path.endswith(suffix):
                return resp
        return self.repo_status, {}, self.repo_data


def healthy_routes():
    return {
        "/commits": (200, {}, [{"commit": {"committer": {"date": "2026-05-25T12:00:00Z"}}}]),
        "/contributors": (200, {"link": '<https://api.github.com/x?page=12>; rel="last"'}, [{"login": "a"}]),
        "/actions/runs": (200, {}, {"workflow_runs": [{"conclusion": "success"}]}),
    }


# --- parse_repo_url -------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/owner/repo", ("owner", "repo")),
    ("https://github.com/owner/repo.git", ("owner", "repo")),
    ("https://github.com/owner/repo/", ("owner", "repo")),
    ("git@github.com:owner/repo.git", ("owner", "repo")),
    ("owner/repo", ("owner", "repo")),
    ("  owner/repo  ", ("owner", "repo")),
])
def test_parse_repo_url(url, expected):
    assert parse_repo_url(url) == expected


def test_parse_repo_url_rejects_garbage():
    with pytest.raises(GitHubGatherError):
        parse_repo_url("not a repo")


# --- gather_from_github (happy paths) -------------------------------------

def test_gather_builds_expected_signals():
    s = gather_from_github("https://github.com/owner/repo", http_get=FakeHTTP(healthy_routes()))
    assert s.name == "repo"
    assert s.last_commit == date(2026, 5, 25)
    assert s.contributor_count == 12          # read from the Link "last" page
    assert s.ci_passing is True
    assert s.open_unpatched_cve is None       # un-fetchable -> unknown
    assert s.uptime_30d is None


def test_gather_explicit_name_overrides_repo_name():
    s = gather_from_github("owner/repo", name="my-mcp-server", http_get=FakeHTTP(healthy_routes()))
    assert s.name == "my-mcp-server"


def test_gather_parses_timezone_offset_commit_date():
    routes = healthy_routes()
    routes["/commits"] = (200, {}, [{"commit": {"committer": {"date": "2026-05-25T23:30:00+05:30"}}}])
    s = gather_from_github("owner/repo", http_get=FakeHTTP(routes))
    assert s.last_commit == date(2026, 5, 25)


def test_gather_handles_missing_ci_as_unknown():
    routes = healthy_routes()
    routes["/actions/runs"] = (200, {}, {"workflow_runs": []})  # CI configured but no runs
    s = gather_from_github("owner/repo", http_get=FakeHTTP(routes))
    assert s.ci_passing is None


def test_gather_failing_ci_is_false():
    routes = healthy_routes()
    routes["/actions/runs"] = (200, {}, {"workflow_runs": [{"conclusion": "failure"}]})
    s = gather_from_github("owner/repo", http_get=FakeHTTP(routes))
    assert s.ci_passing is False


def test_gather_counts_contributors_without_link_header():
    routes = healthy_routes()
    routes["/contributors"] = (200, {}, [{"login": "a"}, {"login": "b"}, {"login": "c"}])
    s = gather_from_github("owner/repo", http_get=FakeHTTP(routes))
    assert s.contributor_count == 3


def test_gather_contributor_count_unknown_on_non_200():
    routes = healthy_routes()
    routes["/contributors"] = (403, {}, None)  # GitHub 403s contributors on huge repos
    s = gather_from_github("owner/repo", http_get=FakeHTTP(routes))
    assert s.contributor_count is None


def test_gather_empty_commit_list_is_unknown():
    routes = healthy_routes()
    routes["/commits"] = (200, {}, [])
    s = gather_from_github("owner/repo", http_get=FakeHTTP(routes))
    assert s.last_commit is None


# --- gather_from_github (error paths) -------------------------------------

def test_gather_raises_on_repo_not_found():
    with pytest.raises(GitHubGatherError, match="repo not found"):
        gather_from_github("owner/missing", http_get=FakeHTTP(repo_status=404))


def test_gather_raises_on_forbidden_or_rate_limited():
    with pytest.raises(GitHubGatherError, match="forbidden|rate-limited"):
        gather_from_github("owner/repo", http_get=FakeHTTP(repo_status=403))


def test_gather_raises_on_unexpected_status():
    with pytest.raises(GitHubGatherError, match="status 500"):
        gather_from_github("owner/repo", http_get=FakeHTTP(repo_status=500))


# --- scoring contract -----------------------------------------------------

def test_gather_only_signals_score_as_dead_because_unknown_gets_no_credit():
    # The 3 cheap signals max out at 4 points (commit +1, contributors +2,
    # CI +1). With everything else unknown, the conservative scorer buckets it
    # DEAD. This is *why* merge_signals exists.
    s = gather_from_github("owner/repo", http_get=FakeHTTP(healthy_routes()))
    r = score_server(s, today=date(2026, 6, 1))
    assert r.score == 4
    assert r.health == Health.DEAD


# --- merge_signals --------------------------------------------------------

def test_merge_fills_unknown_fields_from_fallback():
    fetched = gather_from_github("owner/repo", http_get=FakeHTTP(healthy_routes()))
    yaml_fallback = ServerSignals(
        name="ignored",
        open_unpatched_cve=False,
        clean_install=True,
        uptime_30d=0.998,
        breaking_schema_change_90d=False,
    )
    merged = merge_signals(fetched, yaml_fallback)
    assert merged.name == "repo"                # primary keeps its name
    assert merged.last_commit == date(2026, 5, 25)
    assert merged.clean_install is True         # gap filled from YAML
    assert merged.uptime_30d == 0.998
    r = score_server(merged, today=date(2026, 6, 1))
    assert r.score == 8
    assert r.health == Health.PRODUCTION


def test_merge_does_not_override_known_primary_values():
    primary = ServerSignals(name="p", ci_passing=True)
    fallback = ServerSignals(name="f", ci_passing=False)
    merged = merge_signals(primary, fallback)
    assert merged.ci_passing is True            # primary's known value wins
