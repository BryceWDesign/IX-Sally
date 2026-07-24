"""Tests for typed IX expression parsing."""

from __future__ import annotations

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
from ix_sally.language.errors import IXSyntaxError
from ix_sally.language.expression_parser import (
    IXExpressionParser,
    parse_ix_expression,
)
from ix_sally.language.lexer import tokenize_ix
from ix_sally.language.source import SourcePosition, SourceSpan
from ix_sally.language.tokens import LanguageToken, TokenKind


def test_expression_parser_applies_arithmetic_precedence() -> None:
    """Multiplication must bind more tightly than addition."""
    expression = parse_ix_expression("1 + 2 * 3", filename="math.ix")

    assert isinstance(expression, BinaryExpression)
    assert expression.operator is BinaryOperator.ADD
    assert isinstance(expression.left, LiteralExpression)
    assert expression.left.value == 1
    assert isinstance(expression.right, BinaryExpression)
    assert expression.right.operator is BinaryOperator.MULTIPLY
    assert expression.right.left.to_payload()["value"] == 2
    assert expression.right.right.to_payload()["value"] == 3
    assert expression.span.label() == "math.ix:1:1-10"


def test_expression_parser_applies_logical_and_comparison_precedence() -> None:
    """Comparison, and, and or precedence must remain explicit."""
    expression = parse_ix_expression(
        "score >= 75 and ready or override",
        filename="decision.ix",
    )

    assert isinstance(expression, BinaryExpression)
    assert expression.operator is BinaryOperator.OR
    assert isinstance(expression.left, BinaryExpression)
    assert expression.left.operator is BinaryOperator.AND
    comparison = expression.left.left
    assert isinstance(comparison, BinaryExpression)
    assert comparison.operator is BinaryOperator.GREATER_EQUAL
    assert isinstance(expression.right, NameExpression)
    assert expression.right.name == "override"


def test_expression_parser_preserves_left_associativity() -> None:
    """Operators at one precedence level must associate from the left."""
    expression = parse_ix_expression("10 - 3 - 2")

    assert isinstance(expression, BinaryExpression)
    assert expression.operator is BinaryOperator.SUBTRACT
    assert isinstance(expression.left, BinaryExpression)
    assert expression.left.operator is BinaryOperator.SUBTRACT
    assert expression.left.left.to_payload()["value"] == 10
    assert expression.left.right.to_payload()["value"] == 3
    assert expression.right.to_payload()["value"] == 2


def test_expression_parser_builds_nested_unary_and_group_nodes() -> None:
    """Prefix operators and parentheses must remain explicit AST nodes."""
    expression = parse_ix_expression("not (-score + 2)", filename="guard.ix")

    assert isinstance(expression, UnaryExpression)
    assert expression.operator is UnaryOperator.NOT
    assert isinstance(expression.operand, GroupExpression)
    grouped = expression.operand.expression
    assert isinstance(grouped, BinaryExpression)
    assert grouped.operator is BinaryOperator.ADD
    assert isinstance(grouped.left, UnaryExpression)
    assert grouped.left.operator is UnaryOperator.NEGATE
    assert grouped.span.label() == "guard.ix:1:6-16"
    assert expression.span.label() == "guard.ix:1:1-17"


def test_expression_parser_reads_all_literal_categories() -> None:
    """Boolean, null, string, integer, and float literals must stay typed."""
    cases = (
        ("true", True),
        ("false", False),
        ("null", None),
        ('"ready"', "ready"),
        ("42", 42),
        ("4.25", 4.25),
    )

    for source, expected in cases:
        expression = parse_ix_expression(source)
        assert isinstance(expression, LiteralExpression)
        assert expression.value == expected


def test_expression_parser_allows_outer_and_group_newlines() -> None:
    """Standalone expressions may span newlines inside explicit groups."""
    expression = parse_ix_expression("\n(\n1 + 2\n)\n", filename="multiline.ix")

    assert isinstance(expression, GroupExpression)
    assert isinstance(expression.expression, BinaryExpression)
    assert expression.span.start == SourcePosition(
        line=2,
        column=1,
        offset=1,
    )
    assert expression.span.end == SourcePosition(
        line=4,
        column=2,
        offset=10,
    )


def test_expression_parser_rejects_missing_operand() -> None:
    """A binary operator without a right operand must fail at EOF."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_expression("score +", filename="broken.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-expected-expression"
    assert diagnostic.span.label() == "broken.ix:1:8"
    assert diagnostic.message == "Expected an IX expression, found end of source."


def test_expression_parser_rejects_missing_right_parenthesis() -> None:
    """Unclosed groups must produce an exact delimiter diagnostic."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_expression("(score + 1", filename="broken.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-missing-right-parenthesis"
    assert diagnostic.span.label() == "broken.ix:1:11"
    assert diagnostic.hint == "Close the parenthesized expression with ')'."


def test_expression_parser_rejects_trailing_primary() -> None:
    """Two adjacent primaries must not be silently combined."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_expression("score ready", filename="broken.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-unexpected-token"
    assert diagnostic.span.label() == "broken.ix:1:7-12"
    assert diagnostic.message == "Unexpected token 'ready' after expression."
  def test_expression_parser_validates_supplied_token_stream() -> None:
    """The token-based boundary must reject malformed token sequences."""
    with pytest.raises(
        FoundationError,
        match="must not be empty",
    ):
        IXExpressionParser(tokens=()).parse()

    with pytest.raises(
        FoundationError,
        match="must end with EOF",
    ):
        IXExpressionParser(
            tokens=(
                LanguageToken(
                    kind=TokenKind.IDENTIFIER,
                    lexeme="value",
                    span=SourceSpan.covering(
                        filename="tokens.ix",
                        start=SourcePosition.start(),
                        text="value",
                    ),
                ),
            )
        ).parse()

    foreign_eof = LanguageToken.end_of_file(
        span=SourceSpan.point(
            filename="other.ix",
            line=1,
        )
    )
    with pytest.raises(
        FoundationError,
        match="one source filename",
    ):
        IXExpressionParser(
            tokens=(
                LanguageToken(
                    kind=TokenKind.IDENTIFIER,
                    lexeme="value",
                    span=SourceSpan.covering(
                        filename="tokens.ix",
                        start=SourcePosition.start(),
                        text="value",
                    ),
                ),
                foreign_eof,
            )
        )


def test_expression_parser_digest_is_stable_across_reparse() -> None:
    """Equivalent source must produce the same typed-expression digest."""
    first = IXExpressionParser(
        tokens=tokenize_ix("a == 1 or b == 2", filename="stable.ix"),
    ).parse()
    second = parse_ix_expression(
        "a == 1 or b == 2",
        filename="stable.ix",
    )

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
