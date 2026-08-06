"""Tests for typed IX expression abstract-syntax-tree nodes."""

from __future__ import annotations

import math

import pytest

from ix_sally.foundation import FoundationError
from ix_sally.language.ast import (
    BinaryExpression,
    BinaryOperator,
    GroupExpression,
    LiteralExpression,
    NameExpression,
    UnaryExpression,
    UnaryOperator,
)
from ix_sally.language.source import SourcePosition, SourceSpan


def _span(
    start: int,
    end: int,
    *,
    filename: str = "expression.ix",
) -> SourceSpan:
    """Return a single-line source span for focused AST tests."""
    return SourceSpan(
        filename=filename,
        start=SourcePosition(
            line=1,
            column=start + 1,
            offset=start,
        ),
        end=SourcePosition(
            line=1,
            column=end + 1,
            offset=end,
        ),
    )


def test_literal_expression_payload_and_digest_are_deterministic() -> None:
    """Equivalent literals must preserve stable syntax receipts."""
    first = LiteralExpression(
        span=_span(0, 4),
        value=True,
    )
    second = LiteralExpression(
        span=_span(0, 4),
        value=True,
    )

    assert first.to_payload() == {
        "node_type": "literal_expression",
        "span": first.span.to_payload(),
        "value": True,
    }
    assert first.digest() == second.digest()


def test_literal_expression_rejects_non_finite_float() -> None:
    """Canonical AST payloads must never contain NaN or infinity."""
    for value in (
        math.nan,
        math.inf,
        -math.inf,
    ):
        with pytest.raises(
            FoundationError,
            match="floating-point literals must be finite",
        ):
            LiteralExpression(
                span=_span(0, 3),
                value=value,
            )


def test_name_expression_enforces_ix_identifier_grammar() -> None:
    """Variable references must use the same ASCII grammar as the lexer."""
    expression = NameExpression(
        span=_span(0, 11),
        name="memory_key",
    )

    assert expression.to_payload()["name"] == "memory_key"

    with pytest.raises(
        FoundationError,
        match="must be an ASCII identifier",
    ):
        NameExpression(
            span=_span(0, 9),
            name="not-valid",
        )


def test_binary_operator_precedence_matches_ix_grammar() -> None:
    """Parser precedence must remain explicit and deterministic."""
    assert BinaryOperator.OR.precedence() == 1
    assert BinaryOperator.AND.precedence() == 2
    assert BinaryOperator.EQUAL.precedence() == 3
    assert BinaryOperator.GREATER_EQUAL.precedence() == 4
    assert BinaryOperator.ADD.precedence() == 5
    assert BinaryOperator.MULTIPLY.precedence() == 6


def test_binary_expression_preserves_typed_tree_and_source_order() -> None:
    """Binary expressions must retain typed operands and deterministic traversal."""
    left = NameExpression(
        span=_span(0, 5),
        name="score",
    )
    right = LiteralExpression(
        span=_span(9, 11),
        value=75,
    )
    expression = BinaryExpression(
        span=_span(0, 11),
        left=left,
        operator=BinaryOperator.GREATER_EQUAL,
        right=right,
    )

    assert expression.children() == (
        left,
        right,
    )
    assert expression.walk() == (
        expression,
        left,
        right,
    )
    assert expression.to_payload()["operator"] == ">="
    assert expression.to_payload()["precedence"] == 4


def test_binary_expression_rejects_reversed_operands() -> None:
    """A syntax tree must not reorder operands independently of source text."""
    left = NameExpression(
        span=_span(6, 11),
        name="right",
    )
    right = NameExpression(
        span=_span(0, 4),
        name="left",
    )

    with pytest.raises(
        FoundationError,
        match="operands must remain in source order",
    ):
        BinaryExpression(
            span=_span(0, 11),
            left=left,
            operator=BinaryOperator.ADD,
            right=right,
        )


def test_composite_expression_rejects_child_outside_parent() -> None:
    """Composite nodes must not claim source ranges they do not contain."""
    operand = NameExpression(
        span=_span(4, 9),
        name="value",
    )

    with pytest.raises(
        FoundationError,
        match="must be contained by the parent span",
    ):
        UnaryExpression(
            span=_span(0, 3),
            operator=UnaryOperator.NOT,
            operand=operand,
        )


def test_composite_expression_rejects_cross_file_child() -> None:
    """One AST node must never combine source ranges from different files."""
    child = LiteralExpression(
        span=_span(
            1,
            2,
            filename="other.ix",
        ),
        value=1,
    )

    with pytest.raises(
        FoundationError,
        match="must use the parent filename",
    ):
        GroupExpression(
            span=_span(0, 3),
            expression=child,
        )


def test_nested_expression_walk_is_preorder() -> None:
    """AST traversal must remain stable for later validation and compilation."""
    name = NameExpression(
        span=_span(5, 10),
        name="ready",
    )
    negation = UnaryExpression(
        span=_span(1, 10),
        operator=UnaryOperator.NOT,
        operand=name,
    )
    group = GroupExpression(
        span=_span(0, 11),
        expression=negation,
    )

    assert group.walk() == (
        group,
        negation,
        name,
    )
    assert group.to_payload()["expression"] == negation.to_payload()
