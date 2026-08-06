"""Tests for deterministic IX static value-type analysis."""

from __future__ import annotations

import pytest

from ix_sally.foundation import FoundationError
from ix_sally.language.errors import IXValidationError
from ix_sally.language.expression_parser import parse_ix_expression
from ix_sally.language.statement_parser import parse_ix_program
from ix_sally.language.type_system import (
    IXTypeBinding,
    IXTypeChecker,
    IXTypeContext,
    IXValueType,
    check_ix_program_types,
    infer_ix_expression_type,
    require_typed_ix_program,
)


def test_type_checker_infers_local_and_memory_types() -> None:
    """Bindings and remembered expressions must populate static environments."""
    program = parse_ix_program(
        "let count = 2\n"
        "let ratio = count / 4\n"
        'let label = "ready" + "!"\n'
        "remember approved = count >= 1\n",
        filename="types.ix",
    )

    report = check_ix_program_types(program)

    assert report.is_valid() is True
    assert report.local_type("count") is IXValueType.INTEGER
    assert report.local_type("ratio") is IXValueType.FLOAT
    assert report.local_type("label") is IXValueType.STRING
    assert report.memory_type("approved") is IXValueType.BOOLEAN


def test_type_checker_applies_numeric_promotion() -> None:
    """Mixed numeric arithmetic must promote deterministically to float."""
    program = parse_ix_program(
        "let integer_sum = 1 + 2\nlet mixed_sum = 1 + 2.5\nlet product = mixed_sum * 2\n",
        filename="numeric.ix",
    )

    report = check_ix_program_types(program)

    assert report.local_type("integer_sum") is IXValueType.INTEGER
    assert report.local_type("mixed_sum") is IXValueType.FLOAT
    assert report.local_type("product") is IXValueType.FLOAT


def test_type_checker_accepts_boolean_assertion_and_logic() -> None:
    """Comparisons and Boolean operators must produce assertion-safe values."""
    report = check_ix_program_types(
        parse_ix_program(
            "let score = 80\nlet ready = score >= 75 and true\nassert ready\n",
            filename="assertion.ix",
        )
    )

    assert report.is_valid() is True
    assert report.local_type("ready") is IXValueType.BOOLEAN


def test_type_checker_rejects_non_boolean_assertion() -> None:
    """Assert statements must consume a statically Boolean expression."""
    report = check_ix_program_types(
        parse_ix_program(
            "let score = 80\nassert score\n",
            filename="assertion.ix",
        )
    )

    assert report.is_valid() is False
    diagnostic = report.errors()[0]
    assert diagnostic.code.value == "typing-assertion-not-boolean"
    assert diagnostic.span.label() == "assertion.ix:2:8-13"
    assert diagnostic.message == ("Assert expression must be Boolean, not integer.")


def test_type_checker_rejects_invalid_operator_operands() -> None:
    """Operators must reject statically incompatible operand categories."""
    report = check_ix_program_types(
        parse_ix_program(
            'let bad_add = "count" + 1\nlet bad_logic = true and 2\nlet bad_negation = -"value"\n',
            filename="operators.ix",
        )
    )

    assert [diagnostic.code.value for diagnostic in report.errors()] == [
        "typing-invalid-operator-operands",
        "typing-invalid-operator-operands",
        "typing-invalid-operator-operands",
    ]
    assert [diagnostic.span.label() for diagnostic in report.errors()] == [
        "operators.ix:1:15-26",
        "operators.ix:2:17-27",
        "operators.ix:3:20-28",
    ]


def test_type_checker_avoids_cascading_unknown_name_errors() -> None:
    """Unknown names remain unknown so semantic validation owns that diagnostic."""
    report = check_ix_program_types(
        parse_ix_program(
            "let result = missing + 1\nassert result\n",
            filename="unknown.ix",
        )
    )

    assert report.errors() == ()
    assert report.local_type("result") is IXValueType.UNKNOWN


def test_type_context_supplies_host_types() -> None:
    """Host-provided local and memory types must seed static analysis."""
    context = IXTypeContext(
        local_types=(IXTypeBinding("input_value", IXValueType.FLOAT),),
        memory_types=(IXTypeBinding("prior_result", IXValueType.STRING),),
    )
    program = parse_ix_program(
        "let total = input_value + 1\nrecall prior_result\n",
        filename="context.ix",
    )

    report = IXTypeChecker(context=context).check(program)

    assert report.is_valid() is True
    assert report.local_type("input_value") is IXValueType.FLOAT
    assert report.local_type("total") is IXValueType.FLOAT
    assert report.memory_type("prior_result") is IXValueType.STRING


def test_type_context_normalizes_and_rejects_conflicts() -> None:
    """External type bindings must be deterministic and non-conflicting."""
    alpha = IXTypeBinding("alpha", IXValueType.INTEGER)
    zeta = IXTypeBinding("zeta", IXValueType.STRING)
    context = IXTypeContext(local_types=(zeta, alpha, zeta))

    assert context.local_types == (alpha, zeta)

    with pytest.raises(
        FoundationError,
        match="contains conflicting types for 'value'",
    ):
        IXTypeContext(
            local_types=(
                IXTypeBinding("value", IXValueType.INTEGER),
                IXTypeBinding("value", IXValueType.STRING),
            )
        )


def test_type_binding_rejects_invalid_identifier() -> None:
    """Static environments must use the same identifier grammar as IX source."""
    with pytest.raises(
        FoundationError,
        match="name must be an ASCII identifier",
    ):
        IXTypeBinding("not-valid", IXValueType.STRING)


def test_expression_type_inference_covers_literal_categories() -> None:
    """The expression-only API must expose all primitive IX value types."""
    cases = (
        ("null", IXValueType.NULL),
        ("true", IXValueType.BOOLEAN),
        ("1", IXValueType.INTEGER),
        ("1.5", IXValueType.FLOAT),
        ('"text"', IXValueType.STRING),
        ('"a" == "b"', IXValueType.BOOLEAN),
    )

    for source, expected in cases:
        assert infer_ix_expression_type(parse_ix_expression(source)) is expected


def test_type_report_payload_and_digest_are_deterministic() -> None:
    """Equivalent type analysis must produce stable receipt payloads."""
    program = parse_ix_program(
        "let value = 2 * 3\nremember answer = value == 6\n",
        filename="stable.ix",
    )

    first = check_ix_program_types(program)
    second = check_ix_program_types(program)

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
    assert first.to_payload()["error_count"] == 0
    assert first.to_payload()["is_valid"] is True


def test_require_typed_program_raises_first_type_error() -> None:
    """The fail-closed type boundary must preserve structured diagnostics."""
    program = parse_ix_program(
        'let value = "text" - 1\nassert value\n',
        filename="invalid.ix",
    )

    with pytest.raises(IXValidationError) as captured:
        require_typed_ix_program(program)

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "typing-invalid-operator-operands"
    assert diagnostic.span.label() == "invalid.ix:1:13-23"
