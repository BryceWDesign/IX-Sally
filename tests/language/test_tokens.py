"""Tests for IX lexical vocabulary and token records."""

from __future__ import annotations

import pytest

from ix_sally.foundation import FoundationError
from ix_sally.language.source import SourcePosition, SourceSpan
from ix_sally.language.tokens import (
    KEYWORDS_BY_LEXEME,
    Keyword,
    LanguageToken,
    TokenKind,
)


def _span(text: str = "token") -> SourceSpan:
    """Return a deterministic source span for one token lexeme."""
    return SourceSpan.covering(
        filename="program.ix",
        start=SourcePosition.start(),
        text=text,
    )


def test_keyword_vocabulary_maps_every_reserved_lexeme() -> None:
    """Every reserved word must have one deterministic lookup entry."""
    assert KEYWORDS_BY_LEXEME == {
        keyword.value: keyword for keyword in Keyword
    }
    assert KEYWORDS_BY_LEXEME["human_approval"] is Keyword.HUMAN_APPROVAL
    assert KEYWORDS_BY_LEXEME["claim_boundary"] is Keyword.CLAIM_BOUNDARY


def test_keyword_or_identifier_classifies_reserved_words() -> None:
    """Reserved words and user identifiers must produce distinct token kinds."""
    reserved = LanguageToken.keyword_or_identifier(
        lexeme="remember",
        span=_span("remember"),
    )
    identifier = LanguageToken.keyword_or_identifier(
        lexeme="memory_key",
        span=_span("memory_key"),
    )

    assert reserved.kind is TokenKind.KEYWORD
    assert reserved.keyword is Keyword.REMEMBER
    assert reserved.is_keyword(Keyword.REMEMBER) is True
    assert identifier.kind is TokenKind.IDENTIFIER
    assert identifier.keyword is None


def test_literal_keywords_preserve_typed_values() -> None:
    """Boolean and null keywords must carry their semantic values."""
    true_token = LanguageToken.keyword_or_identifier(
        lexeme="true",
        span=_span("true"),
    )
    false_token = LanguageToken.keyword_or_identifier(
        lexeme="false",
        span=_span("false"),
    )
    null_token = LanguageToken.keyword_or_identifier(
        lexeme="null",
        span=_span("null"),
    )

    assert true_token.literal is True
    assert false_token.literal is False
    assert null_token.literal is None
    assert true_token.has_literal() is True
    assert false_token.has_literal() is True
    assert null_token.has_literal() is True


def test_literal_token_payload_and_digest_are_deterministic() -> None:
    """Equivalent lexical records must produce identical receipt digests."""
    first = LanguageToken(
        kind=TokenKind.INTEGER,
        lexeme="42",
        span=_span("42"),
        literal=42,
    )
    second = LanguageToken(
        kind=TokenKind.INTEGER,
        lexeme="42",
        span=_span("42"),
        literal=42,
    )

    assert first.to_payload()["has_literal"] is True
    assert first.to_payload()["literal"] == 42
    assert first.digest() == second.digest()


def test_end_of_file_token_requires_zero_width_span() -> None:
    """End-of-file tokens must contain no lexeme and consume no source text."""
    eof_span = SourceSpan.point(
        filename="program.ix",
        line=4,
        column=2,
        offset=27,
    )

    token = LanguageToken.end_of_file(span=eof_span)

    assert token.kind is TokenKind.EOF
    assert token.lexeme == ""
    assert token.span == eof_span

    with pytest.raises(
        FoundationError,
        match="span must be zero-width",
    ):
        LanguageToken(
            kind=TokenKind.EOF,
            lexeme="",
            span=_span("x"),
        )


def test_keyword_token_rejects_mismatched_metadata() -> None:
    """Keyword records must not misrepresent their source lexeme."""
    with pytest.raises(
        FoundationError,
        match="lexeme must match",
    ):
        LanguageToken(
            kind=TokenKind.KEYWORD,
            lexeme="allow",
            span=_span("allow"),
            keyword=Keyword.DENY,
        )


def test_literal_token_rejects_wrong_python_type() -> None:
    """Literal token kinds must retain exact runtime value types."""
    with pytest.raises(
        FoundationError,
        match="integer token literal must be an integer",
    ):
        LanguageToken(
            kind=TokenKind.INTEGER,
            lexeme="true",
            span=_span("true"),
            literal=True,
        )

    with pytest.raises(
        FoundationError,
        match="incorrect literal value",
    ):
        LanguageToken(
            kind=TokenKind.KEYWORD,
            lexeme="false",
            span=_span("false"),
            literal=True,
            keyword=Keyword.FALSE,
        )


def test_structural_token_rejects_literal_value() -> None:
    """Punctuation and structural tokens must not carry runtime values."""
    with pytest.raises(
        FoundationError,
        match="left_brace token must not carry a literal value",
    ):
        LanguageToken(
            kind=TokenKind.LEFT_BRACE,
            lexeme="{",
            span=_span("{"),
            literal="unexpected",
        )
