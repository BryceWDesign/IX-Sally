"""Typed value, compiler, and VM tests."""

from __future__ import annotations

import pytest
from ix_sally.cognition import (
    BytecodeProgram,
    CognitiveValue,
    CognitiveValueType,
    IXVirtualMachine,
    Instruction,
    OpCode,
    VMStatus,
    compile_ix_source,
    value_from_payload,
)
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def test_cognitive_value_preserves_exact_scalar_types() -> None:
    """Boolean, integer, float, string, and null must remain distinct."""
    assert CognitiveValue.from_python(True).value_type is CognitiveValueType.BOOLEAN
    assert CognitiveValue.from_python(1).value_type is CognitiveValueType.INTEGER
    assert CognitiveValue.from_python(1.0).value_type is CognitiveValueType.FLOAT
    assert CognitiveValue.from_python("1").value_type is CognitiveValueType.STRING
    assert CognitiveValue.from_python(None).value_type is CognitiveValueType.NULL


def test_cognitive_value_rejects_declared_type_mismatch() -> None:
    """Construction must not silently coerce a stored value."""
    with pytest.raises(FoundationError, match="does not match"):
        CognitiveValue(CognitiveValueType.FLOAT, 1)


def test_cognitive_value_round_trip_is_exact() -> None:
    """Canonical payload restoration must preserve the exact type."""
    original = CognitiveValue.from_python(4.5)
    assert value_from_payload(original.to_payload()) == original


def test_compiler_and_vm_execute_all_statement_outputs() -> None:
    """Compiled IX source must produce local, memory, output, reply, and trace state."""
    program = compile_ix_source(
        "let total = 20 + 22\n"
        "remember answer = total\n"
        "print total\n"
        "reply total\n"
        "trace total == 42\n"
        "assert total == 42\n",
        filename="complete.ix",
    )
    result = IXVirtualMachine().execute(program)

    assert result.status is VMStatus.HALTED
    assert result.local_map()["total"] == CognitiveValue.from_python(42)
    assert result.memory_map()["answer"] == CognitiveValue.from_python(42)
    assert result.outputs == (CognitiveValue.from_python(42),)
    assert result.replies == (CognitiveValue.from_python(42),)
    assert result.traces == (CognitiveValue.from_python(True),)


def test_vm_fails_closed_on_false_assertion() -> None:
    """A false assertion must return a failed receipt without raising outward."""
    result = IXVirtualMachine().execute(
        compile_ix_source("assert 1 == 2\n", filename="false.ix")
    )

    assert result.status is VMStatus.FAILED
    assert result.failure is not None
    assert "assertion evaluated to false" in result.failure


def test_vm_fails_closed_on_missing_runtime_memory() -> None:
    """Recall of a statically declared but absent runtime memory must fail deterministically."""
    program = compile_ix_source(
        "remember answer = 42\nrecall answer\n",
        filename="memory.ix",
    )
    modified = tuple(
        instruction
        for instruction in program.instructions
        if instruction.opcode is not OpCode.STORE_MEMORY
    )
    broken = BytecodeProgram.create(
        instructions=modified,
        source_digest=program.source_digest,
    )

    result = IXVirtualMachine().execute(broken)

    assert result.status is VMStatus.FAILED
    assert result.failure is not None
    assert "unknown memory name" in result.failure


def test_vm_reports_division_by_zero_without_partial_memory_commit() -> None:
    """A runtime fault must be visible and preserve only operations completed before it."""
    result = IXVirtualMachine().execute(
        compile_ix_source(
            "remember safe = 1\nprint 1 / 0\nremember unsafe = 2\n",
            filename="division.ix",
        )
    )

    assert result.status is VMStatus.FAILED
    assert result.memory_map() == {"safe": CognitiveValue.from_python(1)}
    assert "unsafe" not in result.memory_map()


def test_bytecode_requires_exactly_one_final_halt() -> None:
    """Malformed instruction streams must be rejected before execution."""
    digest = DigestRecord.from_payload({"source": "test"})
    with pytest.raises(FoundationError, match="exactly one final halt"):
        BytecodeProgram.create(
            instructions=(Instruction(OpCode.HALT), Instruction(OpCode.HALT)),
            source_digest=digest,
        )


def test_vm_result_digest_is_repeatable() -> None:
    """Equivalent executions must produce the same receipt identity."""
    program = compile_ix_source("print 40 + 2\n", filename="stable.ix")
    first = IXVirtualMachine().execute(program)
    second = IXVirtualMachine().execute(program)

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
