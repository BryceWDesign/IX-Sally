"""Semantic validation for typed IX executable programs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.language.ast import Expression, NameExpression
from ix_sally.language.errors import (
    DiagnosticSeverity,
    IXValidationError,
    LanguageDiagnostic,
)
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

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class IXValidationContext:
    """Names available before validation of one IX program begins."""

    local_names: tuple[str, ...] = ()
    memory_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize context names into deterministic unique sequences."""
        object.__setattr__(
            self,
            "local_names",
            _normalize_names(self.local_names, field_name="local_names"),
        )
        object.__setattr__(
            self,
            "memory_names",
            _normalize_names(self.memory_names, field_name="memory_names"),
        )


@dataclass(frozen=True, slots=True)
class IXValidationReport:
    """Deterministic semantic-validation report for one IX program."""

    program_digest: DigestRecord
    diagnostics: tuple[LanguageDiagnostic, ...]
    local_names: tuple[str, ...]
    memory_names: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate report identity and normalize exported name sets."""
        self.program_digest.require_algorithm("sha256")
        object.__setattr__(
            self,
            "local_names",
            _normalize_names(self.local_names, field_name="local_names"),
        )
        object.__setattr__(
            self,
            "memory_names",
            _normalize_names(self.memory_names, field_name="memory_names"),
        )

    def errors(self) -> tuple[LanguageDiagnostic, ...]:
        """Return all error diagnostics in deterministic source order."""
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.ERROR
        )

    def warnings(self) -> tuple[LanguageDiagnostic, ...]:
        """Return all warning diagnostics in deterministic source order."""
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.WARNING
        )

    def is_valid(self) -> bool:
        """Return whether validation found no semantic errors."""
        return not self.errors()

    def require_valid(self) -> IXValidationReport:
        """Return this report or raise its first semantic error."""
        errors = self.errors()
        if errors:
            raise IXValidationError(errors[0])
        return self

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible validation report."""
        diagnostics: JsonArray = [
            diagnostic.to_payload() for diagnostic in self.diagnostics
        ]
        return {
            "program_digest": {
                "algorithm": self.program_digest.algorithm,
                "value": self.program_digest.value,
            },
            "diagnostics": diagnostics,
            "diagnostic_count": len(self.diagnostics),
            "error_count": len(self.errors()),
            "warning_count": len(self.warnings()),
            "local_names": list(self.local_names),
            "memory_names": list(self.memory_names),
            "is_valid": self.is_valid(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this validation report."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class IXSemanticValidator:
    """Validate name and memory semantics for typed IX programs."""

    context: IXValidationContext = field(default_factory=IXValidationContext)

    def validate(self, program: Program) -> IXValidationReport:
        """Return a complete semantic-validation report for ``program``."""
        local_names = set(self.context.local_names)
        memory_names = set(self.context.memory_names)
        diagnostics: list[LanguageDiagnostic] = []

        for statement in program.statements:
            diagnostics.extend(
                self._validate_statement(
                    statement,
                    local_names=local_names,
                    memory_names=memory_names,
                )
            )

        return IXValidationReport(
            program_digest=program.digest(),
            diagnostics=tuple(diagnostics),
            local_names=tuple(local_names),
            memory_names=tuple(memory_names),
        )

    def _validate_statement(
        self,
        statement: Statement,
        *,
        local_names: set[str],
        memory_names: set[str],
    ) -> tuple[LanguageDiagnostic, ...]:
        """Validate one statement and update the visible semantic context."""
        diagnostics: list[LanguageDiagnostic] = []

        if isinstance(statement, LetStatement):
            diagnostics.extend(
                _undefined_name_diagnostics(
                    statement.expression,
                    local_names=local_names,
                )
            )
            if statement.name in local_names:
                diagnostics.append(
                    LanguageDiagnostic.create(
                        code="validation.duplicate-binding",
                        severity=DiagnosticSeverity.ERROR,
                        message=(
                            f"Local name {statement.name!r} is already defined."
                        ),
                        span=statement.span,
                        hint="Choose a new local name instead of redefining it.",
                    )
                )
            else:
                local_names.add(statement.name)
            return tuple(diagnostics)

        if isinstance(statement, RememberStatement):
            diagnostics.extend(
                _undefined_name_diagnostics(
                    statement.expression,
                    local_names=local_names,
                )
            )
            memory_names.add(statement.name)
            return tuple(diagnostics)

        if isinstance(statement, RecallStatement):
            if statement.name not in memory_names:
                diagnostics.append(
                    LanguageDiagnostic.create(
                        code="validation.unknown-memory",
                        severity=DiagnosticSeverity.ERROR,
                        message=(
                            f"Memory name {statement.name!r} is not available."
                        ),
                        span=statement.span,
                        hint=(
                            "Remember the name earlier or provide it in the "
                            "validation context."
                        ),
                    )
                )
            return tuple(diagnostics)

        expression = _statement_expression(statement)
        diagnostics.extend(
            _undefined_name_diagnostics(
                expression,
                local_names=local_names,
            )
        )
        return tuple(diagnostics)


def validate_ix_program(
    program: Program,
    *,
    context: IXValidationContext | None = None,
) -> IXValidationReport:
    """Validate one typed IX program without raising semantic errors."""
    return IXSemanticValidator(
        context=context or IXValidationContext(),
    ).validate(program)


def require_valid_ix_program(
    program: Program,
    *,
    context: IXValidationContext | None = None,
) -> IXValidationReport:
    """Validate one typed IX program and raise its first semantic error."""
    return validate_ix_program(
        program,
        context=context,
    ).require_valid()


def _statement_expression(statement: Statement) -> Expression:
    """Return the expression owned by a supported expression statement."""
    if isinstance(
        statement,
        (PrintStatement, ReplyStatement, AssertStatement, TraceStatement),
    ):
        return statement.expression
    raise FoundationError(
        f"unsupported IX statement type for semantic validation: "
        f"{type(statement).__name__}"
    )


def _undefined_name_diagnostics(
    expression: Expression,
    *,
    local_names: set[str],
) -> tuple[LanguageDiagnostic, ...]:
    """Return diagnostics for name references unavailable at this point."""
    diagnostics: list[LanguageDiagnostic] = []
    for node in expression.walk():
        if isinstance(node, NameExpression) and node.name not in local_names:
            diagnostics.append(
                LanguageDiagnostic.create(
                    code="validation.undefined-name",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Local name {node.name!r} is not defined.",
                    span=node.span,
                    hint="Define the name with 'let' before using it.",
                )
            )
    return tuple(diagnostics)


def _normalize_names(
    names: Iterable[str],
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate, deduplicate, and sort one external name collection."""
    normalized: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not _IDENTIFIER_PATTERN.fullmatch(name):
            raise FoundationError(
                f"IX validation {field_name} must contain ASCII identifiers"
            )
        normalized.add(name)
    return tuple(sorted(normalized))
