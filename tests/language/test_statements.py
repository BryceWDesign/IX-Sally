"""Tests for typed IX executable statement nodes."""

from __future__ import annotations

import pytest
from ix_sally.foundation import FoundationError
from ix_sally.language.ast import LiteralExpression, NameExpression
from ix_sally.language.source import SourcePosition, SourceSpan
from ix_sally.language.statements import (
    AssertStatement,
    LetStatement,
    PrintStatement,
    Program,
    RecallStatement,
    RememberStatement,
    ReplyStatement,
    TraceStatement,
)


def _span(
    start: int,
    end: int,
    *,
    filename: str = "program.ix",
) -> SourceSpan:
    """Return a one-line source span for statement tests."""
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


def test_let_statement_preserves_typed_expression() -> None:
    """Bindings must retain expression nodes instead of raw source strings."""
    expression = LiteralExpression(
        span=_span(12, 14),
        value=42,
    )
    statement = LetStatement(
        span=_span(0, 14),
        name="answer",
        expression=expression,
    )

    assert statement.children() == (expression,)
    assert statement.walk() == (
        statement,
        expression,
    )
    assert statement.to_payload()["expression"] == expression.to_payload()
    assert statement.to_payload()["name"] == "answer"


def test_memory_statements_validate_identifier_names() -> None:
    """Remember and recall targets must use the IX identifier grammar."""
    expression = NameExpression(
        span=_span(17, 22),
        name="value",
    )
    remember = RememberStatement(
        span=_span(0, 22),
        name="memory_key",
        expression=expression,
    )
    recall = RecallStatement(
        span=_span(23, 40),
        name="memory_key",
    )

    assert remember.to_payload()["name"] == "memory_key"
    assert recall.to_payload()["name"] == "memory_key"

    with pytest.raises(
        FoundationError,
        match="remember target name must be an ASCII identifier",
    ):
        RememberStatement(
            span=_span(0, 22),
            name="memory-key",
            expression=expression,
        )

    with pytest.raises(
        FoundationError,
        match="recall target name must be an ASCII identifier",
    ):
        RecallStatement(
            span=_span(0, 15),
            name="memory.key",
        )


def test_expression_statements_share_typed_child_contract() -> None:
    """Output, assertion, and trace nodes must expose their expression child."""
    expression = NameExpression(
        span=_span(7, 12),
        name="ready",
    )
    statements = (
        PrintStatement(
            span=_span(0, 12),
            expression=expression,
        ),
        ReplyStatement(
            span=_span(0, 12),
            expression=expression,
        ),
        AssertStatement(
            span=_span(0, 12),
            expression=expression,
        ),
        TraceStatement(
            span=_span(0, 12),
            expression=expression,
        ),
    )

    for statement in statements:
        assert statement.children() == (expression,)
        assert statement.to_payload()["expression"] == expression.to_payload()


def test_statement_rejects_expression_outside_its_span() -> None:
    """A statement must not claim an expression outside its source range."""
    expression = LiteralExpression(
        span=_span(10, 12),
        value=1,
    )

    with pytest.raises(
        FoundationError,
        match="print expression span must be contained by the parent span",
    ):
        PrintStatement(
            span=_span(0, 8),
            expression=expression,
        )


def test_statement_rejects_expression_from_another_file() -> None:
    """One statement must never combine nodes from separate source files."""
    expression = LiteralExpression(
        span=_span(6, 7, filename="other.ix"),
        value=1,
    )

    with pytest.raises(
        FoundationError,
        match="assert expression span must use the parent filename",
    ):
        AssertStatement(
            span=_span(0, 7),
            expression=expression,
        )


def test_program_preserves_statement_order_and_payload() -> None:
    """Programs must retain deterministic top-level source order."""
    first_expression = LiteralExpression(
        span=_span(8, 9),
        value=1,
    )
    first = LetStatement(
        span=_span(0, 9),
        name="a",
        expression=first_expression,
    )
    second_expression = NameExpression(
        span=_span(16, 17),
        name="a",
    )
    second = PrintStatement(
        span=_span(10, 17),
        expression=second_expression,
    )
    program = Program(
        span=_span(0, 17),
        statements=(first, second),
    )

    assert program.children() == (
        first,
        second,
    )
    assert program.walk() == (
        program,
        first,
        first_expression,
        second,
        second_expression,
    )
    assert program.to_payload()["statement_count"] == 2
    assert program.digest() == Program(
        span=_span(0, 17),
        statements=(first, second),
    ).digest()


def test_program_rejects_reordered_or_overlapping_statements() -> None:
    """Top-level statements must remain non-overlapping and in source order."""
    later = RecallStatement(
        span=_span(10, 18),
        name="later",
    )
    earlier = RecallStatement(
        span=_span(0, 8),
        name="earlier",
    )

    with pytest.raises(
        FoundationError,
        match="must remain non-overlapping and in source order",
    ):
        Program(
            span=_span(0, 18),
            statements=(later, earlier),
        )


def test_empty_program_is_valid_and_deterministic() -> None:
    """An empty source file must have a valid zero-statement AST root."""
    span = SourceSpan.point(
        filename="empty.ix",
        line=1,
    )
    program = Program(
        span=span,
        statements=(),
    )

    assert program.children() == ()
    assert program.to_payload()["statement_count"] == 0
    assert program.to_payload()["statements"] == []
