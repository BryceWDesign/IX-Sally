"""Tests for receipt-grade IX front-end source analysis."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.language.errors import IXSyntaxError, IXValidationError
from ix_sally.language.frontend import (
    IXFrontendAnalyzer,
    IXFrontendContext,
    analyze_ix_source,
    require_accepted_ix_source,
)
from ix_sally.language.type_system import IXTypeBinding, IXValueType


def test_frontend_analyzes_complete_valid_program() -> None:
    """One front-end call must preserve every non-executing language stage."""
    source = (
        "let score = 80\n"
        "let ready = score >= 75\n"
        "remember result = ready\n"
        "recall result\n"
        "assert ready\n"
    )

    analysis = analyze_ix_source(source, filename="decision.ix")

    assert analysis.filename == "decision.ix"
    assert analysis.source_length == len(source)
    assert analysis.program.to_payload()["statement_count"] == 5
    assert analysis.validation_report.is_valid() is True
    assert analysis.type_report.is_valid() is True
    assert analysis.type_report.local_type("score") is IXValueType.INTEGER
    assert analysis.type_report.local_type("ready") is IXValueType.BOOLEAN
    assert analysis.type_report.memory_type("result") is IXValueType.BOOLEAN
    assert analysis.diagnostics() == ()
    assert analysis.is_accepted() is True
    assert analysis.require_accepted() is analysis


def test_frontend_context_seeds_semantic_and_type_analysis() -> None:
    """Typed host context must remain aligned across both analysis stages."""
    context = IXFrontendContext(
        local_types=(
            IXTypeBinding("input_value", IXValueType.FLOAT),
        ),
        memory_types=(
            IXTypeBinding("prior_result", IXValueType.STRING),
        ),
    )

    analysis = IXFrontendAnalyzer(context=context).analyze(
        "let total = input_value + 1\nrecall prior_result\n",
        filename="context.ix",
    )

    assert analysis.is_accepted() is True
    assert analysis.validation_report.local_names == ("input_value", "total")
    assert analysis.validation_report.memory_names == ("prior_result",)
    assert analysis.type_report.local_type("total") is IXValueType.FLOAT
    assert analysis.context_digest == context.digest()


def test_frontend_collects_semantic_and_type_errors_in_source_order() -> None:
    """Independent semantic and type failures must form one stable diagnostic stream."""
    analysis = analyze_ix_source(
        'let bad = "text" - 1\nprint missing\nassert bad\n',
        filename="invalid.ix",
    )

    assert analysis.is_accepted() is False
    assert [diagnostic.code.value for diagnostic in analysis.errors()] == [
        "typing-invalid-operator-operands",
        "validation-undefined-name",
    ]
    assert [diagnostic.span.label() for diagnostic in analysis.errors()] == [
        "invalid.ix:1:11-21",
        "invalid.ix:2:7-14",
    ]


def test_frontend_fail_closed_boundary_raises_first_error() -> None:
    """Accepted-source callers must receive the first ordered diagnostic."""
    with pytest.raises(IXValidationError) as captured:
        require_accepted_ix_source(
            'let bad = "text" - 1\nprint missing\n',
            filename="invalid.ix",
        )

    assert captured.value.diagnostic.code.value == (
        "typing-invalid-operator-operands"
    )
    assert captured.value.diagnostic.span.label() == "invalid.ix:1:11-21"


def test_frontend_preserves_syntax_failures() -> None:
    """Lexical and parser failures must stop before semantic reports are created."""
    with pytest.raises(IXSyntaxError) as captured:
        analyze_ix_source("let value =", filename="syntax.ix")

    assert captured.value.diagnostic.code.value == "syntax-expected-expression"
    assert captured.value.diagnostic.span.label() == "syntax.ix:1:12"


def test_frontend_analysis_payload_and_digest_are_deterministic() -> None:
    """Equivalent source and context must produce identical analysis receipts."""
    source = "let value = 2 * 3\nassert value == 6\n"
    context = IXFrontendContext()

    first = analyze_ix_source(
        source,
        filename="stable.ix",
        context=context,
    )
    second = analyze_ix_source(
        source,
        filename="stable.ix",
        context=context,
    )

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
    assert first.to_payload()["token_count"] == len(first.tokens)
    assert first.to_payload()["error_count"] == 0
    assert first.to_payload()["is_accepted"] is True
  def test_frontend_source_digest_changes_with_source_content() -> None:
    """The front-end receipt must bind analysis to exact source content."""
    first = analyze_ix_source("print 1", filename="source.ix")
    second = analyze_ix_source("print 2", filename="source.ix")

    assert first.source_digest != second.source_digest
    assert first.digest() != second.digest()


def test_frontend_context_normalizes_bindings() -> None:
    """Front-end contexts must retain deterministic typed binding order."""
    alpha = IXTypeBinding("alpha", IXValueType.INTEGER)
    zeta = IXTypeBinding("zeta", IXValueType.STRING)

    context = IXFrontendContext(local_types=(zeta, alpha, zeta))

    assert context.local_types == (alpha, zeta)
    assert context.validation_context().local_names == ("alpha", "zeta")
    assert context.type_context().local_types == (alpha, zeta)


def test_frontend_analysis_rejects_mismatched_report_identity() -> None:
    """Receipt construction must reject reports for a different program."""
    first = analyze_ix_source("print 1", filename="first.ix")
    second = analyze_ix_source("print 2", filename="second.ix")

    with pytest.raises(
        FoundationError,
        match="validation report does not match the program",
    ):
        replace(
            first,
            validation_report=second.validation_report,
        )


def test_frontend_analysis_rejects_source_length_mismatch() -> None:
    """EOF identity must remain bound to the exact analyzed source length."""
    analysis = analyze_ix_source("print 1", filename="length.ix")

    with pytest.raises(
        FoundationError,
        match="EOF offset must match the source length",
    ):
        replace(
            analysis,
            source_length=analysis.source_length + 1,
        )


def test_frontend_analysis_requires_sha256_identity() -> None:
    """Source and context identities must retain the repository digest contract."""
    analysis = analyze_ix_source("print 1", filename="digest.ix")

    with pytest.raises(
        FoundationError,
        match="digest algorithm mismatch",
    ):
        replace(
            analysis,
            source_digest=DigestRecord(
                algorithm="sha1",
                value="0" * 40,
            ),
        )
