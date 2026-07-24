"""Parser for typed executable IX statements and programs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, NoReturn

from ix_sally.foundation import FoundationError
from ix_sally.language.ast import Expression
from ix_sally.language.errors import (
    DiagnosticSeverity,
    IXSyntaxError,
    LanguageDiagnostic,
)
from ix_sally.language.expression_parser import IXExpressionParser
from ix_sally.language.lexer import tokenize_ix
from ix_sally.language.source import SourcePosition, SourceSpan
from ix_sally.language.statements import (
    AssertStatement,
    LetStatement,
    PrintStatement,
    Program,
    RecallStatement,
    RememberStatement,
    ReplyStatement,
    Statement,
    TraceStatement,
)
from ix_sally.language.tokens import Keyword, LanguageToken, TokenKind

_EXPRESSION_STATEMENTS: Final[
    dict[Keyword, type[PrintStatement | ReplyStatement | AssertStatement | TraceStatement]]
] = {
    Keyword.PRINT: PrintStatement,
    Keyword.REPLY: ReplyStatement,
    Keyword.ASSERT: AssertStatement,
    Keyword.TRACE: TraceStatement,
}


@dataclass(slots=True)
class IXStatementParser:
    """Parse one complete IX token stream into typed executable statements."""

    tokens: tuple[LanguageToken, ...]
    _position: int = field(init=False, repr=False, default=0)

    def __post_init__(self) -> None:
        """Require a complete, single-file token stream."""
        if not self.tokens:
            raise FoundationError("IX program token stream must not be empty")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise FoundationError("IX program token stream must end with EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise FoundationError("IX program token stream contains an early EOF")

        filename = self.tokens[0].span.filename
        if any(token.span.filename != filename for token in self.tokens):
            raise FoundationError("IX program token stream must use one source filename")

    def parse(self) -> Program:
        """Parse and return one complete executable IX program."""
        self._position = 0
        statements: list[Statement] = []
        self._skip_newlines()

        while not self._at_end():
            statements.append(self._parse_statement())
            self._skip_newlines()

        eof = self._peek()
        return Program(
            span=SourceSpan(
                filename=eof.span.filename,
                start=SourcePosition.start(),
                end=eof.span.end,
            ),
            statements=tuple(statements),
        )

    def _parse_statement(self) -> Statement:
        """Parse one supported executable statement."""
        token = self._peek()
        if token.kind is not TokenKind.KEYWORD or token.keyword is None:
            rendered = (
                "end of source"
                if token.kind is TokenKind.EOF
                else repr(token.lexeme)
            )
            self._raise_syntax(
                token=token,
                code="syntax.expected-statement",
                message=f"Expected an executable IX statement, found {rendered}.",
                hint=(
                    "Begin with let, remember, recall, print, reply, assert, or trace."
                ),
            )

        keyword = token.keyword
        if keyword is Keyword.LET:
            return self._parse_assignment(remember=False)
        if keyword is Keyword.REMEMBER:
            return self._parse_assignment(remember=True)
        if keyword is Keyword.RECALL:
            return self._parse_recall()

        statement_type = _EXPRESSION_STATEMENTS.get(keyword)
        if statement_type is not None:
            return self._parse_expression_statement(statement_type)

        self._raise_syntax(
            token=token,
            code="syntax.unsupported-statement",
            message=f"Unsupported executable IX statement keyword {token.lexeme!r}.",
            hint=(
                "This parser currently accepts let, remember, recall, print, reply, "
                "assert, and trace statements."
            ),
        )

    def _parse_assignment(
        self,
        *,
        remember: bool,
    ) -> LetStatement | RememberStatement:
        """Parse one ``let`` or ``remember`` assignment."""
        opening = self._advance()
        name = self._consume(
            TokenKind.IDENTIFIER,
            code="syntax.expected-assignment-name",
            message=f"Expected an identifier after {opening.lexeme!r}.",
            hint=f"Use the form: {opening.lexeme} name = expression.",
        )
        self._consume(
            TokenKind.EQUAL,
            code="syntax.expected-assignment-equal",
            message=f"Expected '=' after assignment name {name.lexeme!r}.",
            hint=f"Use the form: {opening.lexeme} {name.lexeme} = expression.",
        )
        expression = self._parse_expression_to_statement_end()
        span = opening.span.merge(expression.span)

        if remember:
            return RememberStatement(
                span=span,
                name=name.lexeme,
                expression=expression,
            )
        return LetStatement(
            span=span,
            name=name.lexeme,
            expression=expression,
        )

    def _parse_recall(self) -> RecallStatement:
        """Parse one governed memory recall statement."""
        opening = self._advance()
        name = self._consume(
            TokenKind.IDENTIFIER,
            code="syntax.expected-recall-name",
            message="Expected a memory name after 'recall'.",
            hint="Use the form: recall memory_name.",
        )
        self._require_statement_end(context="recall target")
        return RecallStatement(
            span=opening.span.merge(name.span),
            name=name.lexeme,
        )

    def _parse_expression_statement(
        self,
        statement_type: type[
            PrintStatement | ReplyStatement | AssertStatement | TraceStatement
        ],
    ) -> PrintStatement | ReplyStatement | AssertStatement | TraceStatement:
        """Parse one keyword followed by a typed expression."""
        opening = self._advance()
        expression = self._parse_expression_to_statement_end()
        return statement_type(
            span=opening.span.merge(expression.span),
            expression=expression,
        )

    def _parse_expression_to_statement_end(self) -> Expression:
        """Parse expression tokens through newline or EOF at group depth zero."""
        start = self._position
        depth = 0

        while not self._at_end():
            token = self._peek()
            if token.kind is TokenKind.NEWLINE and depth == 0:
                break
            if token.kind is TokenKind.LEFT_PAREN:
                depth += 1
            elif token.kind is TokenKind.RIGHT_PAREN and depth > 0:
                depth -= 1
            self._advance()

        terminator = self._peek()
        expression_tokens = self.tokens[start : self._position]
        expression_eof = LanguageToken.end_of_file(
            span=SourceSpan(
                filename=terminator.span.filename,
                start=terminator.span.start,
                end=terminator.span.start,
            )
        )
        return IXExpressionParser(
            tokens=(*expression_tokens, expression_eof)
        ).parse()
          def _require_statement_end(self, *, context: str) -> None:
        """Require newline or EOF after a non-expression statement."""
        token = self._peek()
        if token.kind in {TokenKind.NEWLINE, TokenKind.EOF}:
            return
        self._raise_syntax(
            token=token,
            code="syntax.unexpected-token",
            message=f"Unexpected token {token.lexeme!r} after {context}.",
            hint="End the statement with a newline.",
        )

    def _consume(
        self,
        kind: TokenKind,
        *,
        code: str,
        message: str,
        hint: str | None = None,
    ) -> LanguageToken:
        """Consume one required token kind or raise a structured diagnostic."""
        token = self._peek()
        if token.kind is kind:
            return self._advance()
        self._raise_syntax(
            token=token,
            code=code,
            message=message,
            hint=hint,
        )

    def _raise_syntax(
        self,
        *,
        token: LanguageToken,
        code: str,
        message: str,
        hint: str | None = None,
    ) -> NoReturn:
        """Raise one structured statement-parser diagnostic."""
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
        """Consume blank lines and statement terminators."""
        while self._peek().kind is TokenKind.NEWLINE:
            self._advance()

    def _at_end(self) -> bool:
        """Return whether the current token is EOF."""
        return self._peek().kind is TokenKind.EOF

    def _peek(self) -> LanguageToken:
        """Return the current token without consuming it."""
        return self.tokens[self._position]

    def _advance(self) -> LanguageToken:
        """Consume and return the current token."""
        token = self._peek()
        if token.kind is not TokenKind.EOF:
            self._position += 1
        return token


def parse_ix_program(
    source: str,
    *,
    filename: str = "<memory>",
) -> Program:
    """Tokenize and parse one complete executable IX program."""
    return IXStatementParser(
        tokens=tokenize_ix(source, filename=filename),
    ).parse()
