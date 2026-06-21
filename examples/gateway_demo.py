"""
Gateway demo. Run: python -m examples.gateway_demo

Proves both headline capabilities with zero credentials:
  1. Deprecation awareness — a dead model is skipped, a near-shutdown warns.
  2. Automatic fallback — a failing model rolls over to a working backup.
"""
from datetime import date

from polyforge.adapters.base import ModelRegistry, ModelRequest
from polyforge.adapters.concrete import FailingAdapter, MockAdapter
from polyforge.gateway.deprecation import DeprecationInfo, DeprecationRegistry
from polyforge.gateway.gateway import Gateway

TODAY = date(2026, 6, 1)


def main() -> None:
    registry = ModelRegistry()
    registry.register(FailingAdapter("primary-model"))   # simulated outage
    registry.register(MockAdapter("backup-model"))

    deps = DeprecationRegistry(entries={})
    deps.add(DeprecationInfo("old-model", date(2026, 1, 1), "primary-model"))  # dead
    deps.add(DeprecationInfo("primary-model", date(2026, 7, 1)))               # warning (~30d)
    deps.add(DeprecationInfo("backup-model", date(2027, 1, 1)))                # healthy

    gw = Gateway(registry, ["old-model", "primary-model", "backup-model"],
                 deps, warn_within_days=90)

    print("PREFLIGHT (no calls made):")
    for msg in gw.preflight(today=TODAY):
        print(f"  - {msg}")

    print("\nGENERATE (with fallback):")
    result = gw.generate(ModelRequest(prompt="summarize this"), today=TODAY)
    print(f"  skipped (dead):  {result.skipped_dead}")
    print(f"  attempted:       {result.attempts}")
    print(f"  succeeded with:  {result.model_used}")
    print(f"  warnings:        {result.warnings}")
    print(f"  response:        {result.response.text}")

    print("\nTakeaway: the app kept working. Changing behavior = editing the "
          "fallback list, not the code.")


if __name__ == "__main__":
    main()
