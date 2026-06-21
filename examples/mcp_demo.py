"""
MCP reliability demo. Run: python -m examples.mcp_demo

Proves both capabilities, reusing the registry/status/fallback pattern:
  1. Audit — score each MCP server, bucket into production / fallback / dead.
  2. Fallback — resolve a capability to the healthiest server, skipping dead.
"""
from datetime import date

from polyforge.mcp.auditor import FallbackRouter, audit
from polyforge.mcp.scorer import ServerSignals

TODAY = date(2026, 6, 1)

SERVERS = [
    ServerSignals("mcp-server-postgres", date(2026, 5, 25), 12, True, False, True, 0.998, False),
    ServerSignals("mcp-weather-community", date(2026, 4, 10), 3, True, False, True, None, False),
    ServerSignals("mcp-scraper-solo", date(2025, 10, 1), 1, False, True, False, 0.80, True),
]


def main() -> None:
    report = audit(SERVERS, TODAY)
    print("AUDIT:\n")
    for r in report.results:
        line = f"  [{r.health.value:>10}] {r.name}  {r.score}/{r.max_score}"
        print(line)
        for reason in r.reasons:
            print(f"               - {reason}")

    print(f"\n  production-ready: {[r.name for r in report.production]}")
    print(f"  needs fallback:   {[r.name for r in report.needs_fallback]}")
    print(f"  DEAD (do not wire): {[r.name for r in report.dead]}")

    print("\nFALLBACK ROUTING:")
    router = FallbackRouter(SERVERS, TODAY)
    chosen = router.resolve(["mcp-scraper-solo", "mcp-weather-community"])
    print(f"  scraping capability -> resolved to '{chosen.name}' "
          f"(skipped dead 'mcp-scraper-solo')")
    print("\nTakeaway: the dead server was caught at audit time and routed "
          "around — not discovered when an agent silently corrupted its context.")


if __name__ == "__main__":
    main()
