"""Tests for deterministic IX semantic validation."""

from __future__ import annotations

import pytest

from ix_sally.foundation import FoundationError
from ix_sally.language.errors import IXValidationError
from ix_sally.language.statement_parser import parse_ix_program
from ix_sally.language.validation import (
    IXSemanticValidator,
    IXValidationContext,
    require_valid_ix_program,
    validate_ix_program,
)


def test_semantic_validator_accepts_defined_names_and_memory() -> None:
    """Ordered local bindings and remembered values must validate cleanly."""
    program = parse_ix_program(
        "let a = 10\n"
        "let b = a + 5\n"
        "remember total = b\n"
        "recall total\n"
        "assert b == 15\n",
        filename="valid.ix",
    )

    report = validate_ix_program(program)

    assert report.is_valid() is True
    assert report.diagnostics == ()
    assert report.local_names == ("a", "b")
    assert report.memory_names == ("total",)
    assert report.program_digest == program.digest()


def test_semantic_validator_reports_undefined_names_in_source_order() -> None:
    """Every unavailable expression name must produce an exact diagnostic."""
    program = parse_ix_program(
        "print missing\nassert other == missing\n",
        filename="undefined.ix",
    )

    report = validate_ix_program(program)

    assert [diagnostic.code.value for diagnostic in report.errors()] == [
        "validation-undefined-name",
        "validation-undefined-name",
        "validation-undefined-name",
    ]
    assert [diagnostic.span.label() for diagnostic in report.errors()] == [
        "undefined.ix:1:7-14",
        "undefined.ix:2:8-13",
        "undefined.ix:2:17-24",
    ]


def test_semantic_validator_enforces_use_before_definition() -> None:
    """A later binding must not retroactively satisfy an earlier reference."""
    program = parse_ix_program(
        "print ready\nlet ready = true\nprint ready\n",
        filename="ordered.ix",
    )

    report = validate_ix_program(program)

    assert len(report.errors()) == 1
    assert report.errors()[0].span.label() == "ordered.ix:1:7-12"
    assert report.local_names == ("ready",)


def test_semantic_validator_rejects_self_reference_and_duplicate_binding() -> None:
    """Let initializers use the prior scope and local names bind only once."""
    program = parse_ix_program(
        "let value = value + 1\nlet value = 2\n",
        filename="binding.ix",
    )

    report = validate_ix_program(program)

    assert [diagnostic.code.value for diagnostic in report.errors()] == [
        "validation-undefined-name",
        "validation-duplicate-binding",
    ]
    assert report.local_names == ("value",)


def test_semantic_validator_tracks_remembered_names() -> None:
    """Recall may use memories established earlier in the same program."""
    valid = validate_ix_program(
        parse_ix_program(
            "remember answer = 42\nrecall answer\n",
            filename="memory.ix",
        )
    )
    invalid = validate_ix_program(
        parse_ix_program(
            "recall answer\nremember answer = 42\n",
            filename="memory.ix",
        )
    )

    assert valid.is_valid() is True
    assert invalid.is_valid() is False
    assert invalid.errors()[0].code.value == "validation-unknown-memory"
    assert invalid.errors()[0].span.label() == "memory.ix:1:1-14"


def test_semantic_validator_accepts_preexisting_context() -> None:
    """Host-provided locals and durable memories must be visible immediately."""
    context = IXValidationContext(
        local_names=("input_value",),
        memory_names=("prior_result",),
    )
    program = parse_ix_program(
        "let total = input_value + 1\nrecall prior_result\n",
        filename="context.ix",
    )

    report = IXSemanticValidator(context=context).validate(program)

    assert report.is_valid() is True
    assert report.local_names == ("input_value", "total")
    assert report.memory_names == ("prior_result",)


def test_validation_context_normalizes_and_rejects_invalid_names() -> None:
    """External semantic names must be unique deterministic IX identifiers."""
    context = IXValidationContext(
        local_names=("zeta", "alpha", "zeta"),
        memory_names=("memory", "memory"),
    )

    assert context.local_names == ("alpha", "zeta")
    assert context.memory_names == ("memory",)

    with pytest.raises(
        FoundationError,
        match="local_names must contain ASCII identifiers",
    ):
        IXValidationContext(local_names=("not-valid",))


def test_local_and_memory_names_use_separate_namespaces() -> None:
    """A local binding and durable memory may intentionally share a name."""
    report = validate_ix_program(
        parse_ix_program(
            "let value = 1\nremember value = value\nrecall value\n",
            filename="namespaces.ix",
        )
    )

    assert report.is_valid() is True
    assert report.local_names == ("value",)
    assert report.memory_names == ("value",)


def test_validation_report_payload_and_digest_are_deterministic() -> None:
    """Equivalent semantic analysis must produce stable report receipts."""
    program = parse_ix_program(
        "let value = missing\nrecall absent\n",
        filename="stable.ix",
    )

    first = validate_ix_program(program)
    second = validate_ix_program(program)

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
    assert first.to_payload()["error_count"] == 2
    assert first.to_payload()["is_valid"] is False


def test_require_valid_ix_program_raises_first_semantic_error() -> None:
    """The fail-closed boundary must preserve the first structured diagnostic."""
    program = parse_ix_program(
        "print missing\nrecall absent\n",
        filename="invalid.ix",
    )

    with pytest.raises(IXValidationError) as captured:
        require_valid_ix_program(program)

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "validation-undefined-name"
    assert diagnostic.span.label() == "invalid.ix:1:7-14"


def test_empty_program_is_semantically_valid() -> None:
    """An empty parsed document must have a stable valid validation report."""
    report = validate_ix_program(
        parse_ix_program("", filename="empty.ix")
    )

    assert report.is_valid() is True
    assert report.local_names == ()
    assert report.memory_names == ()
