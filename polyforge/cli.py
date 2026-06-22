"""
PolyForge CLI.

Usage:
    polyforge analyze <path>            Analyze a .py file or directory
    polyforge analyze <path> --json     Machine-readable output
    polyforge mcp-audit <manifest>      Audit MCP servers from a YAML manifest
    polyforge mcp-audit <manifest> --gather   Enrich entries (with a 'repo') from GitHub
    polyforge mcp-gather <repo>         Fetch signals from a GitHub repo and score
    polyforge version

Deterministic structural analysis (AST). No credentials or network needed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from polyforge.blocks.analyzer import extract_blocks


def _iter_py_files(path: Path):
    if path.is_file() and path.suffix == ".py":
        yield path
    elif path.is_dir():
        yield from sorted(path.rglob("*.py"))


def _mcp_audit(manifest_path: str, gather: bool = False, token: str | None = None) -> int:
    """Audit MCP servers declared in a YAML manifest.

    With ``gather=True``, entries that declare a ``repo`` field have their
    GitHub signals (commit recency, contributors, CI) fetched live and merged
    over the YAML before scoring.
    """
    import os

    import yaml

    from polyforge.mcp.auditor import audit
    from polyforge.mcp.manifest import load_manifest_signals

    p = Path(manifest_path)
    if not p.exists():
        print(f"error: manifest not found: {p}", file=sys.stderr)
        return 2
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = data.get("servers", [])
    if not raw:
        print("error: manifest has no 'servers'", file=sys.stderr)
        return 2

    token = token or os.environ.get("GITHUB_TOKEN")
    servers, warnings = load_manifest_signals(raw, gather=gather, token=token)
    for w in warnings:
        print(f"  \033[33mwarning\033[0m  {w}", file=sys.stderr)

    report = audit(servers)
    color = {"production": "32", "light": "33", "dead": "31"}
    for r in report.results:
        c = color[r.health.value]
        print(f"  \033[{c}m{r.health.value.upper():>10}\033[0m  {r.name}  "
              f"({r.score}/{r.max_score})")
        for reason in r.reasons:
            print(f"               - {reason}")

    dead = len(report.dead)
    print(f"\n{len(report.production)} production, {len(report.needs_fallback)} "
          f"need fallback, {dead} dead.")
    return 1 if dead else 0


def _mcp_gather(repo: str, token: str | None) -> int:
    """Auto-gather signals for one MCP server from GitHub, then score it."""
    import os

    from polyforge.mcp.github_gather import GitHubGatherError, gather_from_github
    from polyforge.mcp.scorer import score_server

    token = token or os.environ.get("GITHUB_TOKEN")
    try:
        signals = gather_from_github(repo, token=token)
    except GitHubGatherError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    r = score_server(signals)
    color = {"production": "32", "light": "33", "dead": "31"}
    c = color[r.health.value]
    print(f"  \033[{c}m{r.health.value.upper():>10}\033[0m  {r.name}  "
          f"({r.score}/{r.max_score})")
    for reason in r.reasons:
        print(f"               - {reason}")
    print("\nSignals auto-gathered from GitHub: last_commit, contributor_count, "
          "ci_passing.\nOther signals are unknown (no credit) — provide them via "
          "YAML and merge to get a full score.")
    return 1 if r.health.value == "dead" else 0


def _check(models_csv: str | None, config_path: str | None) -> int:
    """Preflight a fallback chain (inline or from a config file)."""
    from polyforge.gateway.config import GatewayConfig
    from polyforge.gateway.deprecation import DeprecationRegistry

    if config_path:
        try:
            cfg = GatewayConfig.load(config_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        chain = cfg.fallback
        reg = cfg.build_registry()
        warn_within = cfg.warn_within_days
        print(f"Loaded {config_path}")
    else:
        chain = [m.strip() for m in (models_csv or "").split(",") if m.strip()]
        reg = DeprecationRegistry()
        warn_within = 90

    if not chain:
        print("error: no models given", file=sys.stderr)
        return 2

    problems = 0
    print(f"Checking fallback chain: {' -> '.join(chain)}\n")
    for name in chain:
        status = reg.status(name, warn_within_days=warn_within)
        if status == "dead":
            problems += 1
            print(f"  \033[31mDEAD\033[0m     {name}  (remove it)")
        elif status == "warning":
            problems += 1
            days = reg.days_until_shutdown(name)
            info = reg.lookup(name)
            rep = f" -> {info.replacement}" if info and info.replacement else ""
            print(f"  \033[33mWARNING\033[0m  {name}  ({days} days left){rep}")
        else:
            print(f"  \033[32mOK\033[0m       {name}")

    healthy = [m for m in chain if reg.status(m, warn_within_days=warn_within) != "dead"]
    print()
    if not healthy:
        print("\033[31mNo healthy models in chain — app would fail.\033[0m")
        return 1
    print(f"{problems} issue(s) found." if problems else "All models healthy.")
    return 0


def _analyze(path_str: str, as_json: bool) -> int:
    path = Path(path_str)
    if not path.exists():
        print(f"error: path not found: {path}", file=sys.stderr)
        return 2

    files = list(_iter_py_files(path))
    if not files:
        print(f"error: no .py files at {path}", file=sys.stderr)
        return 2

    results = []
    for f in files:
        try:
            blocks = extract_blocks(f.read_text(encoding="utf-8"), str(f))
        except SyntaxError as e:
            print(f"skip {f}: syntax error ({e.msg})", file=sys.stderr)
            continue
        results.append((f, blocks))

    if as_json:
        payload = [
            {
                "file": str(f),
                "blocks": [
                    {
                        "name": b.qualified_name,
                        "inputs": [{"name": fld.name, "type": fld.type.value}
                                   for fld in b.contract.inputs],
                        "outputs": [{"name": fld.name, "type": fld.type.value}
                                    for fld in b.contract.outputs],
                        "calls": b.calls,
                        "lines": [b.lineno, b.end_lineno],
                    }
                    for b in blocks
                ],
            }
            for f, blocks in results
        ]
        print(json.dumps(payload, indent=2))
        return 0

    total = 0
    for f, blocks in results:
        print(f"\n\033[1m{f}\033[0m  ({len(blocks)} blocks)")
        for b in blocks:
            total += 1
            ins = ", ".join(f"{x.name}:{x.type.value}" for x in b.contract.inputs)
            outs = ", ".join(f"{x.type.value}" for x in b.contract.outputs) or "—"
            print(f"  • {b.qualified_name}({ins}) -> {outs}  [L{b.lineno}-{b.end_lineno}]")
            if b.calls:
                print(f"      calls: {', '.join(b.calls)}")
    print(f"\n{total} blocks across {len(results)} file(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polyforge")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Extract clean blocks from Python code")
    a.add_argument("path", help="A .py file or a directory")
    a.add_argument("--json", action="store_true", help="Machine-readable output")

    c = sub.add_parser("check", help="Check a fallback chain for deprecation risk")
    c.add_argument("models", nargs="?", help="Comma-separated model names, in fallback order")
    c.add_argument("--config", help="Path to a polyforge.yaml config file")

    m = sub.add_parser("mcp-audit", help="Audit MCP servers from a YAML manifest")
    m.add_argument("manifest", help="Path to an MCP servers manifest (YAML)")
    m.add_argument("--gather", action="store_true",
                   help="Auto-fetch GitHub signals for entries that declare a 'repo'")
    m.add_argument("--token", default=None,
                   help="GitHub token (or set GITHUB_TOKEN) for --gather")

    g = sub.add_parser("mcp-gather",
                       help="Fetch signals from a GitHub repo and score one server")
    g.add_argument("repo", help="GitHub repo URL or owner/repo shorthand")
    g.add_argument("--token", default=None,
                   help="GitHub token (or set GITHUB_TOKEN) to raise rate limits")

    sub.add_parser("version", help="Print version")

    args = parser.parse_args(argv)

    if args.command == "version":
        from polyforge import __version__
        print(f"polyforge {__version__}")
        return 0
    if args.command == "analyze":
        return _analyze(args.path, args.json)
    if args.command == "check":
        if not args.models and not args.config:
            print("error: provide models or --config", file=sys.stderr)
            return 2
        return _check(args.models, args.config)
    if args.command == "mcp-audit":
        return _mcp_audit(args.manifest, args.gather, args.token)
    if args.command == "mcp-gather":
        return _mcp_gather(args.repo, args.token)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
