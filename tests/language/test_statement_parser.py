"""Tests for typed IX executable statement parsing."""

from __future__ import annotations

import pytest

from ix_sally.foundation import FoundationError
from ix_sally.language.ast import (
    BinaryExpression,
    BinaryOperator,
    LiteralExpression,
)
from ix_sally.language.errors import IXSyntaxError
from ix_sally.language.lexer import tokenize_ix
from ix_sally.language.source import SourcePosition, SourceSpan
from ix_sally.language.statement_parser import (
    IXStatementParser,
    parse_ix_program,
)
from ix_sally.language.statements import (
    AssertStatement,
    LetStatement,
    PrintStatement,
    RecallStatement,
    RememberStatement,
    ReplyStatement,
    TraceStatement,
)
from ix_sally.language.tokens import LanguageToken, TokenKind


def test_statement_parser_builds_typed_executable_program() -> None:
    """The flat executable IX core must parse into typed statement nodes."""
    source = (
        'trace "program started"\n'
        "let a = 10\n"
        "let b = 5\n"
        "remember total = a + b\n"
        "recall total\n"
        "print total\n"
        'reply "done"\n'
        "assert total == 15\n"
    )

    program = parse_ix_program(source, filename="program.ix")

    assert [type(statement) for statement in program.statements] == [
        TraceStatement,
        LetStatement,
        LetStatement,
        RememberStatement,
        RecallStatement,
        PrintStatement,
        ReplyStatement,
        AssertStatement,
    ]
    remember = program.statements[3]
    assert isinstance(remember, RememberStatement)
    assert isinstance(remember.expression, BinaryExpression)
    assert remember.expression.operator is BinaryOperator.ADD
    assertion = program.statements[-1]
    assert isinstance(assertion, AssertStatement)
    assert assertion.span.label() == "program.ix:8:1-19"
    assert program.span.start == SourcePosition.start()
    assert program.span.end.offset == len(source)


def test_statement_parser_migrates_canonical_hello_program() -> None:
    """The original IX hello example must parse without raw expression strings."""
    source = (
        'trace "hello example started"\n'
        'let name = "IX"\n'
        'reply "Hello from {name}"\n'
        'assert name == "IX"\n'
    )

    program = parse_ix_program(source, filename="hello.ix")

    assert len(program.statements) == 4
    assert isinstance(program.statements[0], TraceStatement)
    assert isinstance(program.statements[1], LetStatement)
    assert isinstance(program.statements[2], ReplyStatement)
    assert isinstance(program.statements[3], AssertStatement)
    assert program.to_payload()["statement_count"] == 4


def test_statement_parser_preserves_literal_types_and_statement_spans() -> None:
    """Assignments and output statements must retain typed values and ranges."""
    program = parse_ix_program(
        'let answer = 42\nprint answer\nreply "ready"',
        filename="values.ix",
    )

    binding = program.statements[0]
    assert isinstance(binding, LetStatement)
    assert isinstance(binding.expression, LiteralExpression)
    assert binding.expression.value == 42
    assert binding.span.label() == "values.ix:1:1-16"
    assert program.statements[1].span.label() == "values.ix:2:1-13"
    assert program.statements[2].span.label() == "values.ix:3:1-14"


def test_statement_parser_accepts_blank_lines_and_comment_only_source() -> None:
    """Blank lines and comments must not create placeholder statements."""
    program = parse_ix_program(
        "# heading\n\nlet ready = true # trailing\n\n",
        filename="comments.ix",
    )

    assert len(program.statements) == 1
    assert isinstance(program.statements[0], LetStatement)
    assert program.statements[0].name == "ready"
    assert program.span.end.offset == 40

    empty = parse_ix_program(
        "# comment only\n",
        filename="empty.ix",
    )
    assert empty.statements == ()
    assert empty.span.start == SourcePosition.start()


def test_statement_parser_allows_grouped_expression_newlines() -> None:
    """Newlines inside parentheses must remain part of one statement expression."""
    program = parse_ix_program(
        "let total = (\n1 + 2\n)\nprint total\n",
        filename="multiline.ix",
    )

    binding = program.statements[0]
    assert isinstance(binding, LetStatement)
    assert binding.span.label() == "multiline.ix:1:1-3:2"
    assert isinstance(program.statements[1], PrintStatement)


def test_statement_parser_rejects_missing_assignment_name() -> None:
    """Assignments without an identifier must fail at the exact token."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_program(
            "let = 1",
            filename="broken.ix",
        )

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-expected-assignment-name"
    assert diagnostic.span.label() == "broken.ix:1:5-6"
    assert diagnostic.message == "Expected an identifier after 'let'."


def test_statement_parser_rejects_missing_assignment_equal() -> None:
    """Assignments must retain an explicit equality delimiter."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_program(
            "remember value 1",
            filename="broken.ix",
        )

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-expected-assignment-equal"
    assert diagnostic.span.label() == "broken.ix:1:16-17"
    assert diagnostic.message == "Expected '=' after assignment name 'value'."


def test_statement_parser_rejects_missing_expression() -> None:
    """Expression statements and assignments must never accept empty tails."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_program(
            "print\n",
            filename="broken.ix",
        )

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-expected-expression"
    assert diagnostic.span.label() == "broken.ix:1:6"


def test_statement_parser_rejects_recall_trailing_tokens() -> None:
    """Recall accepts exactly one memory name and no expression tail."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_program(
            "recall memory extra",
            filename="broken.ix",
        )

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-unexpected-token"
    assert diagnostic.span.label() == "broken.ix:1:15-20"
    assert diagnostic.message == "Unexpected token 'extra' after recall target."


def test_statement_parser_rejects_unsupported_block_keyword() -> None:
    """Unmigrated block syntax must fail closed instead of being ignored."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_program(
            "if ready {\n}\n",
            filename="blocked.ix",
        )

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-unsupported-statement"
    assert diagnostic.span.label() == "blocked.ix:1:1-3"
    assert diagnostic.message == ("Unsupported executable IX statement keyword 'if'.")


def test_statement_parser_rejects_non_keyword_statement_start() -> None:
    """Bare expressions must not be silently treated as statements."""
    with pytest.raises(IXSyntaxError) as captured:
        parse_ix_program(
            "ready",
            filename="broken.ix",
        )

    diagnostic = captured.value.diagnostic
    assert diagnostic.code.value == "syntax-expected-statement"
    assert diagnostic.span.label() == "broken.ix:1:1-6"


def test_statement_parser_validates_supplied_token_stream() -> None:
    """The token-based boundary must reject incomplete or mixed-file streams."""
    with pytest.raises(
        FoundationError,
        match="must not be empty",
    ):
        IXStatementParser(tokens=()).parse()

    token = LanguageToken(
        kind=TokenKind.IDENTIFIER,
        lexeme="ready",
        span=SourceSpan.covering(
            filename="tokens.ix",
            start=SourcePosition.start(),
            text="ready",
        ),
    )
    with pytest.raises(
        FoundationError,
        match="must end with EOF",
    ):
        IXStatementParser(
            tokens=(token,),
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
        IXStatementParser(
            tokens=(
                token,
                foreign_eof,
            )
        ).parse()


def test_statement_parser_digest_is_stable_across_reparse() -> None:
    """Equivalent source must produce the same complete-program digest."""
    source = "let value = 2 * 3\nassert value == 6\n"
    first = IXStatementParser(
        tokens=tokenize_ix(
            source,
            filename="stable.ix",
        ),
    ).parse()
    second = parse_ix_program(
        source,
        filename="stable.ix",
    )

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
