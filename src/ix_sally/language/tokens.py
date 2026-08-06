"""Lexical vocabulary and token records for the embedded IX language."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeAlias

from ix_sally.digest import DigestRecord, JsonObject, JsonPrimitive
from ix_sally.foundation import FoundationError
from ix_sally.language.source import SourceSpan

TokenLiteral: TypeAlias = str | int | float | bool | None


class TokenKind(StrEnum):
    """Kinds of lexical tokens recognized by the IX language kernel."""

    IDENTIFIER = "identifier"
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    KEYWORD = "keyword"
    NEWLINE = "newline"
    LEFT_BRACE = "left_brace"
    RIGHT_BRACE = "right_brace"
    LEFT_PAREN = "left_paren"
    RIGHT_PAREN = "right_paren"
    COMMA = "comma"
    DOT = "dot"
    COLON = "colon"
    EQUAL = "equal"
    EQUAL_EQUAL = "equal_equal"
    BANG_EQUAL = "bang_equal"
    GREATER = "greater"
    GREATER_EQUAL = "greater_equal"
    LESS = "less"
    LESS_EQUAL = "less_equal"
    PLUS = "plus"
    MINUS = "minus"
    STAR = "star"
    SLASH = "slash"
    EOF = "eof"


class Keyword(StrEnum):
    """Reserved words in the migrated IX language vocabulary."""

    AGENT = "agent"
    ALLOW = "allow"
    AND = "and"
    AS = "as"
    ASSERT = "assert"
    ATTEMPT = "attempt"
    CALL = "call"
    CLAIM_BOUNDARY = "claim_boundary"
    DENY = "deny"
    ELSE = "else"
    EVIDENCE_REQUIRED = "evidence_required"
    FALSE = "false"
    FALSIFY_IF = "falsify_if"
    HANDOFF_CONTRACT = "handoff_contract"
    HUMAN_APPROVAL = "human_approval"
    IF = "if"
    LET = "let"
    NON_GOAL = "non_goal"
    NOT = "not"
    NULL = "null"
    OBLIGATION = "obligation"
    ON = "on"
    OR = "or"
    PRINT = "print"
    PURPOSE = "purpose"
    REASON = "reason"
    RECALL = "recall"
    REMEMBER = "remember"
    REPLY = "reply"
    REQUIRE = "require"
    SCHEMA = "schema"
    SEND = "send"
    TRACE = "trace"
    TRUE = "true"
    WITH = "with"

    def is_literal(self) -> bool:
        """Return whether this keyword represents a literal value."""
        return self in {
            Keyword.FALSE,
            Keyword.NULL,
            Keyword.TRUE,
        }

    def literal_value(self) -> bool | None:
        """Return the literal value represented by this keyword."""
        if self is Keyword.TRUE:
            return True
        if self is Keyword.FALSE:
            return False
        if self is Keyword.NULL:
            return None
        raise FoundationError(f"IX keyword {self.value!r} does not represent a literal value")


KEYWORDS_BY_LEXEME: Final[dict[str, Keyword]] = {keyword.value: keyword for keyword in Keyword}


@dataclass(frozen=True, slots=True)
class LanguageToken:
    """One validated token produced from IX source text."""

    kind: TokenKind
    lexeme: str
    span: SourceSpan
    literal: TokenLiteral = None
    keyword: Keyword | None = None

    def __post_init__(self) -> None:
        """Reject inconsistent token records."""
        if not isinstance(self.lexeme, str):
            raise FoundationError("language token lexeme must be text")

        if self.kind is TokenKind.EOF:
            if self.lexeme:
                raise FoundationError("end-of-file token lexeme must be empty")
            if self.span.start != self.span.end:
                raise FoundationError("end-of-file token span must be zero-width")
        elif not self.lexeme:
            raise FoundationError("language token lexeme must not be empty")

        if self.kind is TokenKind.KEYWORD:
            self._require_keyword_consistency()
        elif self.keyword is not None:
            raise FoundationError("non-keyword token must not carry a keyword")

        self._require_literal_consistency()

    @classmethod
    def keyword_or_identifier(
        cls,
        *,
        lexeme: str,
        span: SourceSpan,
    ) -> LanguageToken:
        """Create a keyword token when reserved, otherwise an identifier."""
        keyword = KEYWORDS_BY_LEXEME.get(lexeme)
        if keyword is None:
            return cls(
                kind=TokenKind.IDENTIFIER,
                lexeme=lexeme,
                span=span,
            )

        literal: TokenLiteral = None
        if keyword.is_literal():
            literal = keyword.literal_value()

        return cls(
            kind=TokenKind.KEYWORD,
            lexeme=lexeme,
            span=span,
            literal=literal,
            keyword=keyword,
        )

    @classmethod
    def end_of_file(cls, *, span: SourceSpan) -> LanguageToken:
        """Create a validated end-of-file token."""
        return cls(
            kind=TokenKind.EOF,
            lexeme="",
            span=span,
        )

    def is_keyword(self, keyword: Keyword) -> bool:
        """Return whether this token is the requested keyword."""
        return self.kind is TokenKind.KEYWORD and self.keyword is keyword

    def has_literal(self) -> bool:
        """Return whether this token semantically carries a literal value."""
        if self.kind in {
            TokenKind.STRING,
            TokenKind.INTEGER,
            TokenKind.FLOAT,
        }:
            return True
        return (
            self.kind is TokenKind.KEYWORD
            and self.keyword is not None
            and self.keyword.is_literal()
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible token record."""
        literal: JsonPrimitive = self.literal
        return {
            "kind": self.kind.value,
            "lexeme": self.lexeme,
            "span": self.span.to_payload(),
            "literal": literal,
            "has_literal": self.has_literal(),
            "keyword": self.keyword.value if self.keyword is not None else None,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this lexical token."""
        return DigestRecord.from_payload(self.to_payload())

    def _require_keyword_consistency(self) -> None:
        """Reject missing or mismatched keyword metadata."""
        if self.keyword is None:
            raise FoundationError("keyword token must carry a keyword")
        if self.lexeme != self.keyword.value:
            raise FoundationError("keyword token lexeme must match its keyword value")

    def _require_literal_consistency(self) -> None:
        """Reject literal values that do not match their token kind."""
        if self.kind is TokenKind.STRING:
            if not isinstance(self.literal, str):
                raise FoundationError("string token literal must be text")
            return

        if self.kind is TokenKind.INTEGER:
            if not isinstance(self.literal, int) or isinstance(self.literal, bool):
                raise FoundationError("integer token literal must be an integer")
            return

        if self.kind is TokenKind.FLOAT:
            if not isinstance(self.literal, float):
                raise FoundationError("float token literal must be a float")
            return

        if (
            self.kind is TokenKind.KEYWORD
            and self.keyword is not None
            and self.keyword.is_literal()
        ):
            expected = self.keyword.literal_value()
            if self.literal is not expected:
                raise FoundationError("literal keyword token carries an incorrect literal value")
            return

        if self.literal is not None:
            raise FoundationError(f"{self.kind.value} token must not carry a literal value")
