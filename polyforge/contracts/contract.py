"""
Contract layer.

A Contract is the single source of truth for what a function block does:
its typed inputs, typed outputs, and metadata. Everything else in the system
(adapters, blocks, orchestration) speaks in terms of Contracts so that the
implementation behind a block can change — including swapping the AI model —
without anything that depends on the block needing to change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


@dataclass(frozen=True)
class Field:
    name: str
    type: FieldType
    required: bool = True
    description: str = ""

    def validate(self, value: Any) -> list[str]:
        errors: list[str] = []
        if value is None:
            if self.required:
                errors.append(f"'{self.name}' is required but was None")
            return errors
        ok = {
            FieldType.STRING: str,
            FieldType.INTEGER: int,
            FieldType.FLOAT: (int, float),
            FieldType.BOOLEAN: bool,
            FieldType.OBJECT: dict,
            FieldType.ARRAY: list,
        }[self.type]
        # bool is a subclass of int — guard against silent acceptance
        if self.type == FieldType.INTEGER and isinstance(value, bool):
            errors.append(f"'{self.name}' expected integer, got bool")
        elif not isinstance(value, ok):
            errors.append(
                f"'{self.name}' expected {self.type.value}, got {type(value).__name__}"
            )
        return errors


@dataclass(frozen=True)
class Contract:
    name: str
    description: str
    inputs: tuple[Field, ...] = field(default_factory=tuple)
    outputs: tuple[Field, ...] = field(default_factory=tuple)
    version: str = "0.1.0"

    def validate_inputs(self, payload: dict[str, Any]) -> list[str]:
        return self._validate(self.inputs, payload)

    def validate_outputs(self, payload: dict[str, Any]) -> list[str]:
        return self._validate(self.outputs, payload)

    @staticmethod
    def _validate(fields: tuple[Field, ...], payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for f in fields:
            errors.extend(f.validate(payload.get(f.name)))
        return errors
