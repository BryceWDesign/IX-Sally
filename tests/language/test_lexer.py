"""Tests for deterministic IX lexical analysis."""

from __future__ import annotations

import pytest

from ix_sally.foundation import FoundationError
from ix_sally.language.errors import IXSyntaxError
from ix_sally.language.lexer import IXLexer, tokenize_ix
from ix_sally.language.source import SourcePosition
from ix_sally.language.tokens import Keyword, TokenKind


def test_lexer_tokenizes_governed_ix_source_with_exact_spans() -> None:
    """Keywords, values, operators, and blocks must retain source locations."""
    source = 'let score = 80\nif score >= 75 {\n    reply "pass\\nready"\n}\n'

    tokens = tokenize_ix(source, filename="review.ix")

    assert [token.kind for token in tokens] == [
        TokenKind.KEYWORD,
        TokenKind.IDENTIFIER,
        TokenKind.EQUAL,
        TokenKind.INTEGER,
        TokenKind.NEWLINE,
        TokenKind.KEYWORD,
        TokenKind.IDENTIFIER,
        TokenKind.GREATER_EQUAL,
        TokenKind.INTEGER,
        TokenKind.LEFT_BRACE,
        TokenKind.NEWLINE,
        TokenKind.KEYWORD,
        TokenKind.STRING,
        TokenKind.NEWLINE,
        TokenKind.RIGHT_BRACE,
        TokenKind.NEWLINE,
        TokenKind.EOF,
    ]
    assert tokens[0].keyword is Keyword.LET
    assert tokens[3].literal == 80
    assert tokens[5].keyword is Keyword.IF
    assert tokens[12].literal == "pass\nready"
    assert tokens[12].lexeme == '"pass\\nready"'
    assert tokens[12].span.start == SourcePosition(
        line=3,
        column=11,
        offset=42,
    )
    assert tokens[12].span.end == SourcePosition(
        line=3,
        column=24,
        offset=55,
    )
    assert tokens[-1].span.start == SourcePosition(
        line=5,
        column=1,
        offset=len(source),
    )
    assert tokens[-1].span.start == tokens[-1].span.end


def test_lexer_preserves_newlines_around_comments() -> None:
    """Comments must disappear without erasing statement boundaries."""
    tokens = tokenize_ix(
        "# first\r\nlet value = 2 # trailing\r\n",
        filename="comments.ix",
    )

    assert [token.kind for token in tokens] == [
        TokenKind.NEWLINE,
        TokenKind.KEYWORD,
        TokenKind.IDENTIFIER,
        TokenKind.EQUAL,
        TokenKind.INTEGER,
        TokenKind.NEWLINE,
        TokenKind.EOF,
    ]
    assert tokens[0].lexeme == "\r\n"
    assert tokens[0].span.start.line == 1
    assert tokens[0].span.end.line == 2
    assert tokens[-1].span.start.line == 3


def test_lexer_tokenizes_numbers_and_all_comparison_operators() -> None:
    """Numeric types and multi-character comparisons must remain distinct."""
    tokens = tokenize_ix("1 2.5 == != > >= < <= + - * / . : , ( )")

    assert [token.kind for token in tokens] == [
        TokenKind.INTEGER,
        TokenKind.FLOAT,
        TokenKind.EQUAL_EQUAL,
        TokenKind.BANG_EQUAL,
        TokenKind.GREATER,
        TokenKind.GREATER_EQUAL,
        TokenKind.LESS,
        TokenKind.LESS_EQUAL,
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.DOT,
        TokenKind.COLON,
        TokenKind.COMMA,
        TokenKind.LEFT_PAREN,
        TokenKind.RIGHT_PAREN,
        TokenKind.EOF,
    ]
    assert tokens[0].literal == 1
    assert tokens[1].literal == 2.5


def test_lexer_decodes_supported_string_escapes() -> None:
    """String values must decode only the documented deterministic escapes."""
    token = tokenize_ix(r'"quote: \" slash: \\ tab:\t return:\r line:\n"')[0]

    assert token.kind is TokenKind.STRING
    assert token.literal == 'quote: " slash: \\ tab:\t return:\r line:\n'


def test_lexer_rejects_unexpected_character_with_source_diagnostic() -> None:
    """Unknown source characters must fail closed at their exact location."""
    with pytest.raises(IXSyntaxError) as captured:
        tokenize_ix("let value = @", filename="invalid.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-unexpected-character"
    assert diagnostic.span.label() == "invalid.ix:1:13-14"
    assert diagnostic.message == "Unexpected character '@'."


def test_lexer_rejects_unary_bang_with_keyword_hint() -> None:
    """The unsupported bang operator must direct authors to IX syntax."""
    with pytest.raises(IXSyntaxError) as captured:
        tokenize_ix("!ready", filename="condition.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-unexpected-bang"
    assert diagnostic.hint == "Use the 'not' keyword for logical negation."


def test_lexer_rejects_invalid_string_escape_at_escape_span() -> None:
    """Unsupported escapes must identify only the offending source range."""
    with pytest.raises(IXSyntaxError) as captured:
        tokenize_ix(r'"bad\q"', filename="string.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-invalid-string-escape"
    assert diagnostic.span.label() == "string.ix:1:5-7"
    assert diagnostic.message == "Unsupported string escape '\\q'."


def test_lexer_rejects_unterminated_string_before_newline() -> None:
    """IX strings must never consume a later statement by crossing a newline."""
    with pytest.raises(IXSyntaxError) as captured:
        tokenize_ix('reply "unfinished\nprint "next"', filename="string.ix")

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-unterminated-string"
    assert diagnostic.span.label() == "string.ix:1:7-18"


def test_lexer_empty_source_contains_only_eof() -> None:
    """An empty document must still produce a parseable EOF boundary."""
    tokens = IXLexer(filename="empty.ix").tokenize("")

    assert len(tokens) == 1
    assert tokens[0].kind is TokenKind.EOF
    assert tokens[0].span.label() == "empty.ix:1:1"


def test_lexer_rejects_non_text_source() -> None:
    """The public lexer boundary must reject non-text source values."""
    with pytest.raises(
        FoundationError,
        match="IX source must be text",
    ):
        IXLexer().tokenize(42)  # type: ignore[arg-type]
