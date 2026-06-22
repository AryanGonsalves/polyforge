"""CLI-level tests for `polyforge mcp-gather`.

The network-facing gather is monkeypatched so we test the CLI wiring,
exit codes, and output formatting deterministically.
"""
from datetime import date

import pytest

from polyforge.cli import main
from polyforge.mcp.github_gather import GitHubGatherError
from polyforge.mcp.scorer import ServerSignals


def test_mcp_gather_is_registered_in_help(capsys):
    # argparse prints help and exits 0
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "mcp-gather" in out


def test_mcp_gather_healthy_exit_zero(monkeypatch, capsys):
    healthy = ServerSignals(
        name="cool-server", last_commit=date.today(), contributor_count=9,
        ci_passing=True, open_unpatched_cve=False, clean_install=True,
        uptime_30d=0.999, breaking_schema_change_90d=False,
    )
    monkeypatch.setattr("polyforge.mcp.github_gather.gather_from_github",
                        lambda *a, **k: healthy)
    rc = main(["mcp-gather", "owner/cool-server"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PRODUCTION" in out
    assert "cool-server" in out


def test_mcp_gather_dead_exit_one(monkeypatch, capsys):
    dead = ServerSignals(name="abandoned")  # all unknown -> DEAD
    monkeypatch.setattr("polyforge.mcp.github_gather.gather_from_github",
                        lambda *a, **k: dead)
    rc = main(["mcp-gather", "owner/abandoned"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "DEAD" in out


def test_mcp_gather_error_exit_two(monkeypatch, capsys):
    def boom(*a, **k):
        raise GitHubGatherError("repo not found: owner/missing")
    monkeypatch.setattr("polyforge.mcp.github_gather.gather_from_github", boom)
    rc = main(["mcp-gather", "owner/missing"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "repo not found" in err
