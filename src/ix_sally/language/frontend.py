"""Receipt-grade front-end analysis for embedded IX source programs."""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.language.errors import DiagnosticSeverity, IXValidationError, LanguageDiagnostic
from ix_sally.language.lexer import tokenize_ix
from ix_sally.language.statement_parser import IXStatementParser
from ix_sally.language.statements import Program
from ix_sally.language.tokens import LanguageToken, TokenKind
from ix_sally.language.type_system import (
    IXTypeBinding,
    IXTypeChecker,
    IXTypeContext,
    IXTypeReport,
)
from ix_sally.language.validation import (
    IXSemanticValidator,
    IXValidationContext,
    IXValidationReport,
)


@dataclass(frozen=True, slots=True)
class IXFrontendContext:
    """Typed host names available before front-end analysis begins."""

    local_types: tuple[IXTypeBinding, ...] = ()
    memory_types: tuple[IXTypeBinding, ...] = ()

    def __post_init__(self) -> None:
        """Normalize context bindings through the shared type contract."""
        normalized = IXTypeContext(
            local_types=self.local_types,
            memory_types=self.memory_types,
        )
        object.__setattr__(self, "local_types", normalized.local_types)
        object.__setattr__(self, "memory_types", normalized.memory_types)

    def validation_context(self) -> IXValidationContext:
        """Return the semantic names represented by this typed context."""
        return IXValidationContext(
            local_names=tuple(binding.name for binding in self.local_types),
            memory_names=tuple(binding.name for binding in self.memory_types),
        )

    def type_context(self) -> IXTypeContext:
        """Return the static type context represented by this front-end context."""
        return IXTypeContext(
            local_types=self.local_types,
            memory_types=self.memory_types,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible front-end context."""
        local_types: JsonArray = [binding.to_payload() for binding in self.local_types]
        memory_types: JsonArray = [
            binding.to_payload() for binding in self.memory_types
        ]
        return {
            "local_types": local_types,
            "memory_types": memory_types,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this front-end context."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class IXFrontendAnalysis:
    """Complete lexical, syntactic, semantic, and static type analysis."""

    source_digest: DigestRecord
    source_length: int
    tokens: tuple[LanguageToken, ...]
    program: Program
    validation_report: IXValidationReport
    type_report: IXTypeReport
    context_digest: DigestRecord

    def __post_init__(self) -> None:
        """Require every front-end stage to describe the same source program."""
        self.source_digest.require_algorithm("sha256")
        self.context_digest.require_algorithm("sha256")
        if self.source_length < 0:
            raise FoundationError("IX front-end source_length must not be negative")
        if not self.tokens or self.tokens[-1].kind is not TokenKind.EOF:
            raise FoundationError("IX front-end tokens must end with EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise FoundationError("IX front-end tokens contain an early EOF")

        filename = self.program.span.filename
        if any(token.span.filename != filename for token in self.tokens):
            raise FoundationError(
                "IX front-end tokens and program must use one source filename"
            )
        if self.tokens[-1].span.end.offset != self.source_length:
            raise FoundationError(
                "IX front-end EOF offset must match the source length"
            )

        program_digest = self.program.digest()
        if self.validation_report.program_digest != program_digest:
            raise FoundationError(
                "IX front-end validation report does not match the program"
            )
        if self.type_report.program_digest != program_digest:
            raise FoundationError(
                "IX front-end type report does not match the program"
            )
              @property
    def filename(self) -> str:
        """Return the analyzed source filename."""
        return self.program.span.filename

    def diagnostics(self) -> tuple[LanguageDiagnostic, ...]:
        """Return all semantic and type diagnostics in stable source order."""
        diagnostics = (
            *self.validation_report.diagnostics,
            *self.type_report.diagnostics,
        )
        return tuple(
            sorted(
                diagnostics,
                key=lambda diagnostic: (
                    diagnostic.span.start.offset,
                    diagnostic.span.end.offset,
                    diagnostic.code.value,
                ),
            )
        )

    def errors(self) -> tuple[LanguageDiagnostic, ...]:
        """Return all front-end error diagnostics in stable source order."""
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics()
            if diagnostic.severity is DiagnosticSeverity.ERROR
        )

    def is_accepted(self) -> bool:
        """Return whether semantic and static type analysis both passed."""
        return not self.errors()

    def require_accepted(self) -> IXFrontendAnalysis:
        """Return this analysis or raise its first front-end error."""
        errors = self.errors()
        if errors:
            raise IXValidationError(errors[0])
        return self

    def to_payload(self) -> JsonObject:
        """Return a stable receipt-grade front-end analysis payload."""
        token_digests: JsonArray = [
            {
                "algorithm": token.digest().algorithm,
                "value": token.digest().value,
            }
            for token in self.tokens
        ]
        diagnostics: JsonArray = [
            diagnostic.to_payload() for diagnostic in self.diagnostics()
        ]
        program_digest = self.program.digest()
        validation_digest = self.validation_report.digest()
        type_digest = self.type_report.digest()
        return {
            "filename": self.filename,
            "source_digest": {
                "algorithm": self.source_digest.algorithm,
                "value": self.source_digest.value,
            },
            "source_length": self.source_length,
            "context_digest": {
                "algorithm": self.context_digest.algorithm,
                "value": self.context_digest.value,
            },
            "token_count": len(self.tokens),
            "token_digests": token_digests,
            "program_digest": {
                "algorithm": program_digest.algorithm,
                "value": program_digest.value,
            },
            "validation_report_digest": {
                "algorithm": validation_digest.algorithm,
                "value": validation_digest.value,
            },
            "type_report_digest": {
                "algorithm": type_digest.algorithm,
                "value": type_digest.value,
            },
            "diagnostics": diagnostics,
            "diagnostic_count": len(self.diagnostics()),
            "error_count": len(self.errors()),
            "is_accepted": self.is_accepted(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this front-end analysis."""
        return DigestRecord.from_payload(self.to_payload())
      @dataclass(frozen=True, slots=True)
class IXFrontendAnalyzer:
    """Run the complete non-executing IX source front end."""

    context: IXFrontendContext = field(default_factory=IXFrontendContext)

    def analyze(
        self,
        source: str,
        *,
        filename: str = "<memory>",
    ) -> IXFrontendAnalysis:
        """Tokenize, parse, validate, and type-check one IX source document."""
        tokens = tokenize_ix(source, filename=filename)
        program = IXStatementParser(tokens=tokens).parse()
        validation_report = IXSemanticValidator(
            context=self.context.validation_context()
        ).validate(program)
        type_report = IXTypeChecker(
            context=self.context.type_context()
        ).check(program)
        return IXFrontendAnalysis(
            source_digest=DigestRecord.from_payload({"source": source}),
            source_length=len(source),
            tokens=tokens,
            program=program,
            validation_report=validation_report,
            type_report=type_report,
            context_digest=self.context.digest(),
        )


def analyze_ix_source(
    source: str,
    *,
    filename: str = "<memory>",
    context: IXFrontendContext | None = None,
) -> IXFrontendAnalysis:
    """Run complete inspectable front-end analysis for one IX source document."""
    return IXFrontendAnalyzer(
        context=context or IXFrontendContext(),
    ).analyze(source, filename=filename)


def require_accepted_ix_source(
    source: str,
    *,
    filename: str = "<memory>",
    context: IXFrontendContext | None = None,
) -> IXFrontendAnalysis:
    """Analyze IX source and fail closed on its first semantic or type error."""
    return analyze_ix_source(
        source,
        filename=filename,
        context=context,
    ).require_accepted()
