"""
End-to-end demo. Run: python -m examples.demo

Proves the full loop with zero credentials:
  messy source -> AST blocks (with inferred contracts) -> AI review per block,
  through a model selected from a registry of swappable adapters.
"""
from pathlib import Path

from polyforge.adapters.base import ModelRegistry
from polyforge.adapters.concrete import MockAdapter
from polyforge.blocks.analyzer import extract_blocks
from polyforge.orchestration.orchestrator import Orchestrator


def main() -> None:
    source = Path(__file__).parent.joinpath("messy_input.py").read_text()

    # 1. Structural pass — deterministic, no model needed.
    blocks = extract_blocks(source, "messy_input.py")
    print(f"Extracted {len(blocks)} blocks:\n")
    for b in blocks:
        ins = ", ".join(f"{f.name}:{f.type.value}" for f in b.contract.inputs)
        outs = ", ".join(f"{f.name}:{f.type.value}" for f in b.contract.outputs) or "—"
        print(f"  {b.qualified_name}({ins}) -> {outs}   [lines {b.lineno}-{b.end_lineno}]")
        if b.calls:
            print(f"      calls: {', '.join(b.calls)}")

    # 2. Register swappable models. Swap MockAdapter for AnthropicAdapter()
    #    (with a key) and nothing below changes.
    registry = ModelRegistry()
    registry.register(MockAdapter("mock-fast", context=32_000))
    registry.register(MockAdapter("mock-large", context=200_000))
    print(f"\nRegistered models: {registry.names()}")

    # 3. AI review per block (human approves later — nothing auto-applied).
    orch = Orchestrator(registry)
    print("\nPer-block AI review:\n")
    for review in orch.process_all(blocks):
        print(f"  [{review.block.qualified_name}] via {review.model_used}: "
              f"{review.suggestion}  (approved={review.approved})")


if __name__ == "__main__":
    main()
