"""Deterministic lexer for the embedded IX language kernel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NoReturn

from ix_sally.foundation import FoundationError, require_text
from ix_sally.language.errors import (
    DiagnosticSeverity,
    IXSyntaxError,
    LanguageDiagnostic,
)
from ix_sally.language.source import SourcePosition, SourceSpan
from ix_sally.language.tokens import LanguageToken, TokenKind

_SINGLE_CHARACTER_TOKENS: dict[str, TokenKind] = {
    "{": TokenKind.LEFT_BRACE,
    "}": TokenKind.RIGHT_BRACE,
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    ",": TokenKind.COMMA,
    ".": TokenKind.DOT,
    ":": TokenKind.COLON,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
}
_ESCAPE_VALUES: dict[str, str] = {
    '"': '"',
    "\\": "\\",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


@dataclass(slots=True)
class IXLexer:
    """Tokenize one IX source document while preserving exact locations."""

    filename: str = "<memory>"
    _source: str = field(init=False, repr=False, default="")
    _index: int = field(init=False, repr=False, default=0)
    _position: SourcePosition = field(
        init=False,
        repr=False,
        default_factory=SourcePosition.start,
    )
    _token_start_index: int = field(init=False, repr=False, default=0)
    _token_start: SourcePosition = field(
        init=False,
        repr=False,
        default_factory=SourcePosition.start,
    )
    _tokens: list[LanguageToken] = field(
        init=False,
        repr=False,
        default_factory=list,
    )

    def __post_init__(self) -> None:
        """Normalize the source filename."""
        self.filename = require_text(self.filename, field_name="filename")

    def tokenize(self, source: str) -> tuple[LanguageToken, ...]:
        """Return a complete token stream ending with one EOF token."""
        if not isinstance(source, str):
            raise FoundationError("IX source must be text")

        self._source = source
        self._index = 0
        self._position = SourcePosition.start()
        self._token_start_index = 0
        self._token_start = self._position
        self._tokens = []

        while not self._at_end():
            self._token_start_index = self._index
            self._token_start = self._position
            self._scan_token()

        eof_span = SourceSpan(
            filename=self.filename,
            start=self._position,
            end=self._position,
        )
        self._tokens.append(LanguageToken.end_of_file(span=eof_span))
        return tuple(self._tokens)

    def _scan_token(self) -> None:
        """Scan one token or skip one non-token source region."""
        character = self._advance()

        if self._scan_trivia(character):
            return
        if self._scan_punctuation_or_operator(character):
            return
        if character == '"':
            self._scan_string()
            return
        if _is_ascii_digit(character):
            self._scan_number()
            return
        if _is_identifier_start(character):
            self._scan_identifier()
            return

        self._raise_syntax(
            code="syntax.unexpected-character",
            message=f"Unexpected character {character!r}.",
        )

    def _scan_trivia(self, character: str) -> bool:
        """Consume whitespace or comments and report whether trivia matched."""
        if character in {" ", "\t", "\f"}:
            self._skip_horizontal_whitespace()
            return True
        if character in {"\r", "\n"}:
            self._scan_newline(character)
            return True
        if character == "#":
            self._skip_line_comment()
            return True
        return False

    def _scan_punctuation_or_operator(self, character: str) -> bool:
        """Consume punctuation or an operator and report whether one matched."""
        token_kind = _SINGLE_CHARACTER_TOKENS.get(character)
        if token_kind is not None:
            self._emit(token_kind)
            return True

        if character == "=":
            self._emit(
                TokenKind.EQUAL_EQUAL if self._match("=") else TokenKind.EQUAL
            )
            return True

        if character == "!":
            if self._match("="):
                self._emit(TokenKind.BANG_EQUAL)
                return True
            self._raise_syntax(
                code="syntax.unexpected-bang",
                message="Unexpected '!'; IX supports '!=' but not unary bang.",
                hint="Use the 'not' keyword for logical negation.",
            )
                  if character == ">":
            self._emit(
                TokenKind.GREATER_EQUAL
                if self._match("=")
                else TokenKind.GREATER
            )
            return True

        if character == "<":
            self._emit(
                TokenKind.LESS_EQUAL if self._match("=") else TokenKind.LESS
            )
            return True

        return False

    def _skip_horizontal_whitespace(self) -> None:
        """Consume spaces, tabs, and form feeds without emitting a token."""
        while self._peek() in {" ", "\t", "\f"}:
            self._advance()

    def _scan_newline(self, first_character: str) -> None:
        """Consume one logical newline and emit a newline token."""
        if first_character == "\r" and self._peek() == "\n":
            self._advance()
        self._emit(TokenKind.NEWLINE)

    def _skip_line_comment(self) -> None:
        """Consume a hash-prefixed comment while preserving its newline."""
        while not self._at_end() and self._peek() not in {"\r", "\n"}:
            self._advance()

    def _scan_identifier(self) -> None:
        """Consume one ASCII identifier or reserved IX keyword."""
        while _is_identifier_continue(self._peek()):
            self._advance()

        lexeme = self._lexeme()
        self._tokens.append(
            LanguageToken.keyword_or_identifier(
                lexeme=lexeme,
                span=self._span(),
            )
        )

    def _scan_number(self) -> None:
        """Consume one integer or decimal floating-point literal."""
        while _is_ascii_digit(self._peek()):
            self._advance()

        token_kind = TokenKind.INTEGER
        if self._peek() == "." and _is_ascii_digit(self._peek_next()):
            token_kind = TokenKind.FLOAT
            self._advance()
            while _is_ascii_digit(self._peek()):
                self._advance()

        lexeme = self._lexeme()
        literal: int | float
        if token_kind is TokenKind.INTEGER:
            literal = int(lexeme)
        else:
            literal = float(lexeme)

        self._tokens.append(
            LanguageToken(
                kind=token_kind,
                lexeme=lexeme,
                span=self._span(),
                literal=literal,
            )
        )

    def _scan_string(self) -> None:
        """Consume one double-quoted string with deterministic escapes."""
        value_parts: list[str] = []

        while not self._at_end():
            character = self._peek()
            if character == '"':
                self._advance()
                self._tokens.append(
                    LanguageToken(
                        kind=TokenKind.STRING,
                        lexeme=self._lexeme(),
                        span=self._span(),
                        literal="".join(value_parts),
                    )
                )
                return

            if character in {"\r", "\n"}:
                self._raise_syntax(
                    code="syntax.unterminated-string",
                    message="String literal must close before the end of the line.",
                    hint='Add a closing double quote (\").',
                )

            if character == "\\":
                escape_start = self._position
                self._advance()
                if self._at_end():
                    self._raise_syntax(
                        code="syntax.unterminated-string",
                        message="String literal ends after an escape marker.",
                        hint='Add an escaped character and a closing double quote (\").',
                    )

                escaped = self._advance()
                value = _ESCAPE_VALUES.get(escaped)
                if value is None:
                    span = SourceSpan(
                        filename=self.filename,
                        start=escape_start,
                        end=self._position,
                    )
                    raise IXSyntaxError(
                        LanguageDiagnostic.create(
                            code="syntax.invalid-string-escape",
                            severity=DiagnosticSeverity.ERROR,
                            message=f"Unsupported string escape '\\{escaped}'.",
                            span=span,
                            hint='Use one of: \", \\\\, \\n, \\r, or \\t.',
                        )
                    )
                value_parts.append(value)
                continue

            value_parts.append(self._advance())

        self._raise_syntax(
            code="syntax.unterminated-string",
            message="String literal reaches the end of the source without closing.",
            hint='Add a closing double quote (\").',
        )

    def _emit(self, kind: TokenKind) -> None:
        """Append one non-literal token for the current source range."""
        self._tokens.append(
            LanguageToken(
                kind=kind,
                lexeme=self._lexeme(),
                span=self._span(),
            )
        )

    def _raise_syntax(
        self,
        *,
        code: str,
              message: str,
        hint: str | None = None,
    ) -> NoReturn:
        """Raise a structured syntax error for the current token range."""
        raise IXSyntaxError(
            LanguageDiagnostic.create(
                code=code,
                severity=DiagnosticSeverity.ERROR,
                message=message,
                span=self._span(),
                hint=hint,
            )
        )

    def _at_end(self) -> bool:
        """Return whether the source cursor reached the end."""
        return self._index >= len(self._source)

    def _advance(self) -> str:
        """Consume and return one source character."""
        character = self._source[self._index]
        self._index += 1
        self._position = self._position.advance(character)
        return character

    def _match(self, expected: str) -> bool:
        """Consume ``expected`` when it is the next source character."""
        if self._at_end() or self._source[self._index] != expected:
            return False
        self._advance()
        return True

    def _peek(self) -> str:
        """Return the next source character without consuming it."""
        if self._at_end():
            return "\0"
        return self._source[self._index]

    def _peek_next(self) -> str:
        """Return the character after the next source character."""
        next_index = self._index + 1
        if next_index >= len(self._source):
            return "\0"
        return self._source[next_index]

    def _lexeme(self) -> str:
        """Return the exact source text for the current token."""
        return self._source[self._token_start_index : self._index]

    def _span(self) -> SourceSpan:
        """Return the exact source span for the current token."""
        return SourceSpan(
            filename=self.filename,
            start=self._token_start,
            end=self._position,
        )


def tokenize_ix(
    source: str,
    *,
    filename: str = "<memory>",
) -> tuple[LanguageToken, ...]:
    """Tokenize IX source with a fresh deterministic lexer."""
    return IXLexer(filename=filename).tokenize(source)


def _is_ascii_digit(character: str) -> bool:
    """Return whether ``character`` is one ASCII decimal digit."""
    return "0" <= character <= "9"


def _is_identifier_start(character: str) -> bool:
    """Return whether ``character`` may begin an IX identifier."""
    return (
        character == "_"
        or "a" <= character <= "z"
        or "A" <= character <= "Z"
    )


def _is_identifier_continue(character: str) -> bool:
    """Return whether ``character`` may continue an IX identifier."""
    return _is_identifier_start(character) or _is_ascii_digit(character)
