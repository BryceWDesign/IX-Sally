"""Precedence parser for typed IX expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, NoReturn

from ix_sally.foundation import FoundationError
from ix_sally.language.ast import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    GroupExpression,
    LiteralExpression,
    NameExpression,
    UnaryExpression,
    UnaryOperator,
)
from ix_sally.language.errors import (
    DiagnosticSeverity,
    IXSyntaxError,
    LanguageDiagnostic,
)
from ix_sally.language.lexer import tokenize_ix
from ix_sally.language.tokens import Keyword, LanguageToken, TokenKind

_BINARY_OPERATORS: Final[dict[TokenKind | Keyword, BinaryOperator]] = {
    Keyword.OR: BinaryOperator.OR,
    Keyword.AND: BinaryOperator.AND,
    TokenKind.EQUAL_EQUAL: BinaryOperator.EQUAL,
    TokenKind.BANG_EQUAL: BinaryOperator.NOT_EQUAL,
    TokenKind.GREATER: BinaryOperator.GREATER,
    TokenKind.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL,
    TokenKind.LESS: BinaryOperator.LESS,
    TokenKind.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
    TokenKind.PLUS: BinaryOperator.ADD,
    TokenKind.MINUS: BinaryOperator.SUBTRACT,
    TokenKind.STAR: BinaryOperator.MULTIPLY,
    TokenKind.SLASH: BinaryOperator.DIVIDE,
}
_UNARY_OPERATORS: Final[dict[TokenKind | Keyword, UnaryOperator]] = {
    TokenKind.PLUS: UnaryOperator.POSITIVE,
    TokenKind.MINUS: UnaryOperator.NEGATE,
    Keyword.NOT: UnaryOperator.NOT,
}


@dataclass(slots=True)
class IXExpressionParser:
    """Parse one complete IX expression from a validated token stream."""

    tokens: tuple[LanguageToken, ...]
    _position: int = field(init=False, repr=False, default=0)

    def __post_init__(self) -> None:
        """Require a non-empty stream ending in one EOF token."""
        if not self.tokens:
            raise FoundationError("IX expression token stream must not be empty")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise FoundationError("IX expression token stream must end with EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise FoundationError("IX expression token stream contains an early EOF")

        filename = self.tokens[0].span.filename
        if any(token.span.filename != filename for token in self.tokens):
            raise FoundationError("IX expression token stream must use one source filename")

    def parse(self) -> Expression:
        """Parse and return one complete typed IX expression."""
        self._position = 0
        self._skip_newlines()
        expression = self._parse_precedence(minimum_precedence=1)
        self._skip_newlines()

        if not self._at_end():
            token = self._peek()
            self._raise_syntax(
                token=token,
                code="syntax.unexpected-token",
                message=f"Unexpected token {token.lexeme!r} after expression.",
                hint="End the expression or add a supported IX operator.",
            )

        return expression

    def _parse_precedence(self, *, minimum_precedence: int) -> Expression:
        """Parse left-associative binary operators by precedence."""
        left = self._parse_unary()

        while True:
            operator = self._binary_operator(self._peek())
            if operator is None or operator.precedence() < minimum_precedence:
                return left

            self._advance()
            right = self._parse_precedence(
                minimum_precedence=operator.precedence() + 1,
            )
            left = BinaryExpression(
                span=left.span.merge(right.span),
                left=left,
                operator=operator,
                right=right,
            )

    def _parse_unary(self) -> Expression:
        """Parse prefix unary operators or a primary expression."""
        token = self._peek()
        operator = self._unary_operator(token)
        if operator is None:
            return self._parse_primary()

        operator_token = self._advance()
        operand = self._parse_unary()
        return UnaryExpression(
            span=operator_token.span.merge(operand.span),
            operator=operator,
            operand=operand,
        )

    def _parse_primary(self) -> Expression:
        """Parse one literal, name, or parenthesized expression."""
        token = self._peek()

        if token.kind in {
            TokenKind.STRING,
            TokenKind.INTEGER,
            TokenKind.FLOAT,
        }:
            self._advance()
            return LiteralExpression(
                span=token.span,
                value=token.literal,
            )

        if (
            token.kind is TokenKind.KEYWORD
            and token.keyword is not None
            and token.keyword.is_literal()
        ):
            self._advance()
            return LiteralExpression(
                span=token.span,
                value=token.literal,
            )

        if token.kind is TokenKind.IDENTIFIER:
            self._advance()
            return NameExpression(
                span=token.span,
                name=token.lexeme,
            )

        if token.kind is TokenKind.LEFT_PAREN:
            return self._parse_group()

        return self._raise_expected_expression(token)

    def _parse_group(self) -> GroupExpression:
        """Parse one parenthesized expression including both delimiters."""
        opening = self._advance()
        self._skip_newlines()
        expression = self._parse_precedence(minimum_precedence=1)
        self._skip_newlines()

        if not self._check(TokenKind.RIGHT_PAREN):
            token = self._peek()
            self._raise_syntax(
                token=token,
                code="syntax.missing-right-parenthesis",
                message="Expected ')' after grouped expression.",
                hint="Close the parenthesized expression with ')'.",
            )

        closing = self._advance()
        return GroupExpression(
            span=opening.span.merge(closing.span),
            expression=expression,
        )

    def _binary_operator(self, token: LanguageToken) -> BinaryOperator | None:
        """Return the binary operator represented by ``token``."""
        if token.kind is TokenKind.KEYWORD and token.keyword is not None:
            return _BINARY_OPERATORS.get(token.keyword)
        return _BINARY_OPERATORS.get(token.kind)

    def _unary_operator(self, token: LanguageToken) -> UnaryOperator | None:
        """Return the unary operator represented by ``token``."""
        if token.kind is TokenKind.KEYWORD and token.keyword is not None:
            return _UNARY_OPERATORS.get(token.keyword)
        return _UNARY_OPERATORS.get(token.kind)

    def _raise_expected_expression(self, token: LanguageToken) -> NoReturn:
        """Raise a structured error when no primary expression can begin."""
        rendered = "end of source" if token.kind is TokenKind.EOF else repr(token.lexeme)
        self._raise_syntax(
            token=token,
            code="syntax.expected-expression",
            message=f"Expected an IX expression, found {rendered}.",
            hint="Use a literal, identifier, unary operator, or parenthesized expression.",
        )

    def _raise_syntax(
        self,
        *,
        token: LanguageToken,
        code: str,
        message: str,
        hint: str | None = None,
    ) -> NoReturn:
        """Raise one structured parser diagnostic at ``token``."""
        raise IXSyntaxError(
            LanguageDiagnostic.create(
                code=code,
                severity=DiagnosticSeverity.ERROR,
                message=message,
                span=token.span,
                hint=hint,
            )
        )

    def _skip_newlines(self) -> None:
        """Consume newline tokens allowed around a complete expression."""
        while self._check(TokenKind.NEWLINE):
            self._advance()

    def _check(self, kind: TokenKind) -> bool:
        """Return whether the current token has ``kind``."""
        return self._peek().kind is kind

    def _at_end(self) -> bool:
        """Return whether the current token is EOF."""
        return self._check(TokenKind.EOF)

    def _peek(self) -> LanguageToken:
        """Return the current token without consuming it."""
        return self.tokens[self._position]

    def _advance(self) -> LanguageToken:
        """Consume and return the current token."""
        token = self._peek()
        if token.kind is not TokenKind.EOF:
            self._position += 1
        return token


def parse_ix_expression(
    source: str,
    *,
    filename: str = "<memory>",
) -> Expression:
    """Tokenize and parse one complete typed IX expression."""
    return IXExpressionParser(
        tokens=tokenize_ix(source, filename=filename),
    ).parse()
