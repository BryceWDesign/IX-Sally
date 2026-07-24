"""Tests for structured IX language diagnostics and exceptions."""

from __future__ import annotations

import pytest

from ix_sally.language.errors import (
    DiagnosticSeverity,
    IXSyntaxError,
    LanguageDiagnostic,
)
from ix_sally.language.source import SourceSpan


def test_language_diagnostic_formats_stable_message() -> None:
    """Diagnostics must render source, severity, code, message, and hint."""
    diagnostic = LanguageDiagnostic.create(
        code="syntax.unexpected-token",
        severity=DiagnosticSeverity.ERROR,
        message="Unexpected closing brace.",
        span=SourceSpan.point(
            filename="agent.ix",
            line=7,
            column=3,
            offset=42,
        ),
        hint="Remove the brace or open a matching block.",
    )

    assert diagnostic.code.value == "syntax-unexpected-token"
    assert diagnostic.format() == (
        "agent.ix:7:3: error "
        "[syntax-unexpected-token]: "
        "Unexpected closing brace. "
        "Hint: Remove the brace or open a matching block."
    )
    assert (
        diagnostic.to_payload()["formatted"]
        == diagnostic.format()
    )


def test_language_diagnostic_digest_is_deterministic() -> None:
    """Equivalent diagnostics must produce the same receipt digest."""
    first = LanguageDiagnostic.create(
        code="validation.empty-program",
        severity=DiagnosticSeverity.ERROR,
        message="Program must contain at least one statement.",
        span=SourceSpan.point(
            filename="empty.ix",
            line=1,
        ),
    )
    second = LanguageDiagnostic.create(
        code="validation.empty-program",
        severity=DiagnosticSeverity.ERROR,
        message="Program must contain at least one statement.",
        span=SourceSpan.point(
            filename="empty.ix",
            line=1,
        ),
    )

    assert first.digest() == second.digest()


def test_syntax_error_carries_structured_diagnostic() -> None:
    """Language exceptions must preserve their machine-readable diagnostic."""
    diagnostic = LanguageDiagnostic.create(
        code="syntax.missing-brace",
        severity=DiagnosticSeverity.ERROR,
        message="Missing closing brace.",
        span=SourceSpan.point(
            filename="agent.ix",
            line=9,
            column=1,
        ),
    )

    with pytest.raises(IXSyntaxError) as captured:
        raise IXSyntaxError(diagnostic)

    assert captured.value.diagnostic is diagnostic
    assert str(captured.value) == diagnostic.format()
