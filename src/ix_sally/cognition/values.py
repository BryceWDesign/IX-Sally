"""Typed runtime values used by the IX-Sally cognitive execution core."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from ix_sally.digest import JsonPrimitive, JsonValue
from ix_sally.foundation import FoundationError

CognitiveScalar: TypeAlias = str | int | float | bool | None


class CognitiveValueType(StrEnum):
    """Closed set of values accepted by deterministic cognitive execution."""

    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"


@dataclass(frozen=True, slots=True)
class CognitiveValue:
    """One validated scalar value with an explicit runtime type."""

    value_type: CognitiveValueType
    value: CognitiveScalar

    @classmethod
    def from_python(cls, value: CognitiveScalar) -> CognitiveValue:
        """Create a typed value without coercing between Python scalar types."""
        if value is None:
            return cls(CognitiveValueType.NULL, None)
        if isinstance(value, bool):
            return cls(CognitiveValueType.BOOLEAN, value)
        if isinstance(value, int):
            return cls(CognitiveValueType.INTEGER, value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise FoundationError("cognitive floating-point values must be finite")
            return cls(CognitiveValueType.FLOAT, value)
        if isinstance(value, str):
            return cls(CognitiveValueType.STRING, value)
        raise FoundationError(f"unsupported cognitive value type: {type(value).__name__}")

    def __post_init__(self) -> None:
        """Require the declared type to exactly match the stored scalar."""
        expected = _value_type(self.value)
        if self.value_type is not expected:
            raise FoundationError(
                "cognitive value type does not match its stored scalar: "
                f"declared {self.value_type.value}, actual {expected.value}"
            )

    def to_payload(self) -> dict[str, JsonValue]:
        """Return a deterministic JSON-compatible representation."""
        primitive: JsonPrimitive = self.value
        return {"type": self.value_type.value, "value": primitive}

    def require_boolean(self, *, operation: str) -> bool:
        """Return the Boolean value or fail closed with operation context."""
        if self.value_type is not CognitiveValueType.BOOLEAN:
            raise FoundationError(f"{operation} requires Boolean, got {self.value_type.value}")
        assert isinstance(self.value, bool)
        return self.value

    def require_numeric(self, *, operation: str) -> int | float:
        """Return an integer or float without converting its exact type."""
        if self.value_type not in {
            CognitiveValueType.INTEGER,
            CognitiveValueType.FLOAT,
        }:
            raise FoundationError(
                f"{operation} requires numeric value, got {self.value_type.value}"
            )
        assert isinstance(self.value, int | float)
        assert not isinstance(self.value, bool)
        return self.value


def value_from_payload(payload: JsonValue) -> CognitiveValue:
    """Restore one cognitive value from its canonical payload."""
    if not isinstance(payload, dict):
        raise FoundationError("cognitive value payload must be an object")
    if "type" not in payload or "value" not in payload:
        raise FoundationError("cognitive value payload requires type and value fields")
    value_type = payload.get("type")
    if not isinstance(value_type, str):
        raise FoundationError("cognitive value payload requires a text type")
    try:
        declared = CognitiveValueType(value_type)
    except ValueError as exc:
        raise FoundationError(f"unknown cognitive value type: {value_type}") from exc
    value = payload.get("value")
    if not isinstance(value, str | int | float | bool | type(None)):
        raise FoundationError("cognitive value payload contains a non-scalar value")
    return CognitiveValue(declared, value)


def _value_type(value: CognitiveScalar) -> CognitiveValueType:
    """Return the exact cognitive type for one supported Python scalar."""
    if value is None:
        return CognitiveValueType.NULL
    if isinstance(value, bool):
        return CognitiveValueType.BOOLEAN
    if isinstance(value, int):
        return CognitiveValueType.INTEGER
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FoundationError("cognitive floating-point values must be finite")
        return CognitiveValueType.FLOAT
    if isinstance(value, str):
        return CognitiveValueType.STRING
    raise FoundationError(f"unsupported cognitive value type: {type(value).__name__}")
