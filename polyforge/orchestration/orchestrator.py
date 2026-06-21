"""
Orchestration layer.

Ties the pieces together: given extracted blocks, run an AI task per block
through whatever model the registry selects. This is where capability-based
routing and human-in-the-loop gates live. Generation is never trusted blindly;
every produced artifact is returned for review, not applied.
"""
from __future__ import annotations

from dataclasses import dataclass

from polyforge.adapters.base import ModelRegistry, ModelRequest
from polyforge.blocks.analyzer import Block


@dataclass
class BlockReview:
    block: Block
    model_used: str
    suggestion: str
    approved: bool = False  # human flips this; nothing is auto-applied


class Orchestrator:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def summarize_block(self, block: Block, min_context: int = 0) -> BlockReview:
        adapter = self.registry.select(min_context=min_context)
        prompt = (
            "Summarize what this function does in one sentence, then list any "
            "risks a reviewer should check:\n\n" + block.source
        )
        resp = adapter.generate(ModelRequest(prompt=prompt, max_tokens=256))
        return BlockReview(block=block, model_used=resp.model, suggestion=resp.text)

    def process_all(self, blocks: list[Block]) -> list[BlockReview]:
        return [self.summarize_block(b) for b in blocks]
