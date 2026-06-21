"""
Config layer.

Lets a team declare their fallback chain in a YAML file checked into their
repo, then build a Gateway from it. The point: the routing policy becomes
version-controlled config a team reviews in PRs — not buried in code.

Example polyforge.yaml:

    warn_within_days: 90
    fallback:
      - claude-sonnet-4-6
      - claude-haiku-4-5-20251001
      - local-mock
    # Optional: override/extend the built-in deprecation snapshot
    deprecations:
      - model: internal-llm-v1
        shutdown_date: 2026-12-31
        replacement: internal-llm-v2
        note: scheduled internal retirement
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from polyforge.gateway.deprecation import DeprecationInfo, DeprecationRegistry


@dataclass
class GatewayConfig:
    fallback: list[str]
    warn_within_days: int = 90
    deprecations: list[DeprecationInfo] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GatewayConfig":
        if "fallback" not in data or not data["fallback"]:
            raise ValueError("config must define a non-empty 'fallback' list")
        if not isinstance(data["fallback"], list):
            raise ValueError("'fallback' must be a list of model names")

        deps: list[DeprecationInfo] = []
        for raw in data.get("deprecations", []) or []:
            missing = {"model", "shutdown_date"} - raw.keys()
            if missing:
                raise ValueError(f"deprecation entry missing {missing}: {raw}")
            sd = raw["shutdown_date"]
            sd = sd if isinstance(sd, date) else date.fromisoformat(str(sd))
            deps.append(DeprecationInfo(
                model=raw["model"],
                shutdown_date=sd,
                replacement=raw.get("replacement", ""),
                note=raw.get("note", ""),
            ))

        return GatewayConfig(
            fallback=list(data["fallback"]),
            warn_within_days=int(data.get("warn_within_days", 90)),
            deprecations=deps,
        )

    @staticmethod
    def load(path: str | Path) -> "GatewayConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"config not found: {p}")
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("config root must be a mapping")
        return GatewayConfig.from_dict(data)

    def build_registry(self) -> DeprecationRegistry:
        """Built-in snapshot + user overrides layered on top."""
        reg = DeprecationRegistry()
        for info in self.deprecations:
            reg.add(info)
        return reg
