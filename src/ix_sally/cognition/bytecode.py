"""Deterministic bytecode records for the embedded IX cognitive VM."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.values import CognitiveValue
from ix_sally.digest import DigestRecord, JsonArray, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text


class OpCode(StrEnum):
    """Instructions supported by the dependency-free IX virtual machine."""

    PUSH = "push"
    LOAD_LOCAL = "load_local"
    STORE_LOCAL = "store_local"
    LOAD_MEMORY = "load_memory"
    STORE_MEMORY = "store_memory"
    UNARY_POSITIVE = "unary_positive"
    UNARY_NEGATE = "unary_negate"
    UNARY_NOT = "unary_not"
    BINARY_OR = "binary_or"
    BINARY_AND = "binary_and"
    BINARY_EQUAL = "binary_equal"
    BINARY_NOT_EQUAL = "binary_not_equal"
    BINARY_GREATER = "binary_greater"
    BINARY_GREATER_EQUAL = "binary_greater_equal"
    BINARY_LESS = "binary_less"
    BINARY_LESS_EQUAL = "binary_less_equal"
    BINARY_ADD = "binary_add"
    BINARY_SUBTRACT = "binary_subtract"
    BINARY_MULTIPLY = "binary_multiply"
    BINARY_DIVIDE = "binary_divide"
    EMIT_OUTPUT = "emit_output"
    EMIT_REPLY = "emit_reply"
    ASSERT = "assert"
    TRACE = "trace"
    HALT = "halt"


_NAME_OPERATIONS = {
    OpCode.LOAD_LOCAL,
    OpCode.STORE_LOCAL,
    OpCode.LOAD_MEMORY,
    OpCode.STORE_MEMORY,
}


@dataclass(frozen=True, slots=True)
class Instruction:
    """One immutable VM instruction with validated operands."""

    opcode: OpCode
    value: CognitiveValue | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        """Require exactly the operands expected by the opcode."""
        normalized_name = require_optional_text(self.name, field_name="instruction name")
        object.__setattr__(self, "name", normalized_name)
        if self.opcode is OpCode.PUSH:
            if self.value is None or self.name is not None:
                raise FoundationError("push requires a value and no name")
            return
        if self.opcode in _NAME_OPERATIONS:
            if self.name is None or self.value is not None:
                raise FoundationError(
                    f"{self.opcode.value} requires a name and no literal value"
                )
            return
        if self.value is not None or self.name is not None:
            raise FoundationError(
                f"{self.opcode.value} does not accept instruction operands"
            )

    def to_payload(self) -> JsonObject:
        """Return a canonical instruction payload."""
        value_payload: JsonValue = None
        if self.value is not None:
            value_payload = self.value.to_payload()
        return {
            "opcode": self.opcode.value,
            "name": self.name,
            "value": value_payload,
        }


@dataclass(frozen=True, slots=True)
class BytecodeProgram:
    """A complete, digest-bound sequence of VM instructions."""

    program_id: CanonicalKey
    instructions: tuple[Instruction, ...]
    source_digest: DigestRecord

    @classmethod
    def create(
        cls,
        *,
        instructions: Iterable[Instruction],
        source_digest: DigestRecord,
        program_id: CanonicalKey | None = None,
    ) -> BytecodeProgram:
        """Create bytecode and require a single final halt instruction."""
        normalized = tuple(instructions)
        source_digest.require_algorithm("sha256")
        if not normalized:
            raise FoundationError("bytecode program must contain instructions")
        halt_positions = tuple(
            index for index, instruction in enumerate(normalized)
            if instruction.opcode is OpCode.HALT
        )
        if halt_positions != (len(normalized) - 1,):
            raise FoundationError("bytecode program requires exactly one final halt")
        return cls(
            program_id=program_id
            or CanonicalKey.from_text(
                f"ix-program-{source_digest.value[:20]}",
                field_name="program_id",
            ),
            instructions=normalized,
            source_digest=source_digest,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical bytecode representation."""
        instructions: JsonArray = [
            instruction.to_payload() for instruction in self.instructions
        ]
        return {
            "program_id": self.program_id.value,
            "source_digest": {
                "algorithm": self.source_digest.algorithm,
                "value": self.source_digest.value,
            },
            "instruction_count": len(self.instructions),
            "instructions": instructions,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic identity for this bytecode program."""
        return DigestRecord.from_payload(self.to_payload())
