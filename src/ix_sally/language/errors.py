"""Structured diagnostics and exceptions for the embedded IX language."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import (
    CanonicalKey,
    FoundationError,
    require_text,
)
from ix_sally.language.source import SourceSpan


class DiagnosticSeverity(StrEnum):
    """Severity values for IX language diagnostics."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class LanguageDiagnostic:
    """One deterministic diagnostic produced by the IX language kernel."""

    code: CanonicalKey
    severity: DiagnosticSeverity
    message: str
    span: SourceSpan
    hint: str | None = None

    def __post_init__(self) -> None:
        """Normalize diagnostic text."""
        object.__setattr__(
            self,
            "message",
            require_text(
                self.message,
                field_name="message",
            ),
        )

        if self.hint is not None:
            object.__setattr__(
                self,
                "hint",
                require_text(
                    self.hint,
                    field_name="hint",
                ),
            )

    @classmethod
    def create(
        cls,
        *,
        code: str,
        severity: DiagnosticSeverity,
        message: str,
        span: SourceSpan,
        hint: str | None = None,
    ) -> LanguageDiagnostic:
        """Create a normalized language diagnostic."""
        return cls(
            code=CanonicalKey.from_text(
                code,
                field_name="code",
            ),
            severity=severity,
            message=message,
            span=span,
            hint=hint,
        )

    def format(self) -> str:
        """Return a stable one-line diagnostic rendering."""
        rendered = f"{self.span.label()}: {self.severity.value} [{self.code.value}]: {self.message}"

        if self.hint is not None:
            return f"{rendered} Hint: {self.hint}"

        return rendered

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible diagnostic."""
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "span": self.span.to_payload(),
            "hint": self.hint,
            "formatted": self.format(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this diagnostic."""
        return DigestRecord.from_payload(self.to_payload())


class IXLanguageError(FoundationError):
    """Base exception for embedded IX language failures."""

    def __init__(
        self,
        diagnostic: LanguageDiagnostic,
    ) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.format())


class IXSyntaxError(IXLanguageError):
    """Raised when IX source cannot be tokenized or parsed."""


class IXValidationError(IXLanguageError):
    """Raised when parsed IX source violates semantic rules."""


class IXExecutionError(IXLanguageError):
    """Raised when a validated IX program fails during execution."""
