"""Typed executable statements for the embedded IX language kernel."""

from __future__ import annotations

import re
from abc import abstractmethod
from dataclasses import dataclass

from ix_sally.digest import JsonArray, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.language.ast import Expression, LanguageNode
from ix_sally.language.source import SourceSpan

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class Statement(LanguageNode):
    """Base class for executable IX statements."""

    @abstractmethod
    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible statement representation."""


@dataclass(frozen=True, slots=True)
class Program(LanguageNode):
    """A complete ordered IX source program."""

    statements: tuple[Statement, ...]

    def __post_init__(self) -> None:
        """Require contained statements in source order."""
        _require_ordered_children(
            parent=self.span,
            children=self.statements,
            field_name="program statement",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return top-level statements in source order."""
        return self.statements

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible program representation."""
        statements: JsonArray = [statement.to_payload() for statement in self.statements]
        return {
            "node_type": "program",
            "span": self.span.to_payload(),
            "statement_count": len(self.statements),
            "statements": statements,
        }


@dataclass(frozen=True, slots=True)
class LetStatement(Statement):
    """Bind one expression result to a local IX name."""

    name: str
    expression: Expression

    def __post_init__(self) -> None:
        """Validate the binding name and expression range."""
        _require_identifier(self.name, field_name="let binding name")
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="let expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the bound expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible let statement."""
        return {
            "node_type": "let_statement",
            "span": self.span.to_payload(),
            "name": self.name,
            "expression": self.expression.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class RememberStatement(Statement):
    """Persist one expression result under a governed memory name."""

    name: str
    expression: Expression

    def __post_init__(self) -> None:
        """Validate the memory name and expression range."""
        _require_identifier(self.name, field_name="remember target name")
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="remember expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the remembered expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible remember statement."""
        return {
            "node_type": "remember_statement",
            "span": self.span.to_payload(),
            "name": self.name,
            "expression": self.expression.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class RecallStatement(Statement):
    """Recall one governed memory value by name."""

    name: str

    def __post_init__(self) -> None:
        """Validate the recalled memory name."""
        _require_identifier(self.name, field_name="recall target name")

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible recall statement."""
        return {
            "node_type": "recall_statement",
            "span": self.span.to_payload(),
            "name": self.name,
        }


@dataclass(frozen=True, slots=True)
class PrintStatement(Statement):
    """Emit one expression result to the local output stream."""

    expression: Expression

    def __post_init__(self) -> None:
        """Require the printed expression inside this statement."""
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="print expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the printed expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible print statement."""
        return {
            "node_type": "print_statement",
            "span": self.span.to_payload(),
            "expression": self.expression.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class ReplyStatement(Statement):
    """Emit one expression result as an agent reply."""

    expression: Expression

    def __post_init__(self) -> None:
        """Require the reply expression inside this statement."""
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="reply expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the reply expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reply statement."""
        return {
            "node_type": "reply_statement",
            "span": self.span.to_payload(),
            "expression": self.expression.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class AssertStatement(Statement):
    """Require one expression to evaluate truthfully at runtime."""

    expression: Expression

    def __post_init__(self) -> None:
        """Require the asserted expression inside this statement."""
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="assert expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the asserted expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible assert statement."""
        return {
            "node_type": "assert_statement",
            "span": self.span.to_payload(),
            "expression": self.expression.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class TraceStatement(Statement):
    """Record one expression result in the governed execution trace."""

    expression: Expression

    def __post_init__(self) -> None:
        """Require the traced expression inside this statement."""
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="trace expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the traced expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible trace statement."""
        return {
            "node_type": "trace_statement",
            "span": self.span.to_payload(),
            "expression": self.expression.to_payload(),
        }


def _require_identifier(value: str, *, field_name: str) -> None:
    """Require one value to follow the IX identifier grammar."""
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise FoundationError(f"IX {field_name} must be an ASCII identifier")


def _require_child_span(
    *,
    parent: SourceSpan,
    child: SourceSpan,
    field_name: str,
) -> None:
    """Require one child span to belong to and fit inside its parent."""
    if parent.filename != child.filename:
        raise FoundationError(f"IX {field_name} span must use the parent filename")
    if child.start < parent.start or child.end > parent.end:
        raise FoundationError(f"IX {field_name} span must be contained by the parent span")


def _require_ordered_children(
    *,
    parent: SourceSpan,
    children: tuple[Statement, ...],
    field_name: str,
) -> None:
    """Require children inside a parent and ordered without overlap."""
    previous_end = parent.start
    for child in children:
        _require_child_span(
            parent=parent,
            child=child.span,
            field_name=field_name,
        )
        if child.span.start < previous_end:
            raise FoundationError(
                f"IX {field_name}s must remain non-overlapping and in source order"
            )
        previous_end = child.span.end
