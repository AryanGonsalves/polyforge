"""
Code-to-blocks analyzer.

Takes unorganized source and extracts structured "blocks" — one per function
or method — each carrying a derived Contract (inferred I/O), a dependency list,
and source span. This is the dev-assistive piece: it turns a large messy file
into a navigable, contract-shaped inventory a human can manage.

Uses Python's AST (no LLM needed for structure), so it is fast, deterministic,
and scales to large files. The AI layer is then used per-block for the fuzzy
work (summaries, refactor suggestions) — never for the structural parse.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

from polyforge.contracts.contract import Contract, Field, FieldType


_ANNOT = {
    "str": FieldType.STRING,
    "int": FieldType.INTEGER,
    "float": FieldType.FLOAT,
    "bool": FieldType.BOOLEAN,
    "dict": FieldType.OBJECT,
    "list": FieldType.ARRAY,
}


@dataclass
class Block:
    name: str
    qualified_name: str
    contract: Contract
    calls: list[str] = field(default_factory=list)
    lineno: int = 0
    end_lineno: int = 0
    source: str = ""


def _annotation_to_type(node: ast.expr | None) -> FieldType:
    if isinstance(node, ast.Name):
        return _ANNOT.get(node.id, FieldType.OBJECT)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        return _ANNOT.get(node.value.id, FieldType.OBJECT)
    return FieldType.OBJECT


def _calls_within(func: ast.AST) -> list[str]:
    names: list[str] = []
    for n in ast.walk(func):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                names.append(f.id)
            elif isinstance(f, ast.Attribute):
                names.append(f.attr)
    return sorted(set(names))


def extract_blocks(source: str, source_name: str = "<source>") -> list[Block]:
    tree = ast.parse(source)
    lines = source.splitlines()
    blocks: list[Block] = []

    def handle(fn: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str) -> None:
        inputs = []
        for arg in fn.args.args:
            if arg.arg in ("self", "cls"):
                continue
            inputs.append(Field(
                name=arg.arg,
                type=_annotation_to_type(arg.annotation),
                required=True,
            ))
        outputs = (Field(name="return", type=_annotation_to_type(fn.returns),
                         required=False),) if fn.returns else ()
        doc = ast.get_docstring(fn) or ""
        contract = Contract(
            name=fn.name,
            description=doc.strip().splitlines()[0] if doc else "",
            inputs=tuple(inputs),
            outputs=outputs,
        )
        end = getattr(fn, "end_lineno", fn.lineno)
        blocks.append(Block(
            name=fn.name,
            qualified_name=f"{prefix}{fn.name}",
            contract=contract,
            calls=_calls_within(fn),
            lineno=fn.lineno,
            end_lineno=end,
            source="\n".join(lines[fn.lineno - 1:end]),
        ))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            handle(node, "")
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    handle(sub, f"{node.name}.")

    return blocks
