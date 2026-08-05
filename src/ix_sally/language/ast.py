"""Typed expression nodes for the embedded IX language kernel."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject, JsonPrimitive
from ix_sally.foundation import FoundationError
from ix_sally.language.source import SourceSpan
from ix_sally.language.tokens import TokenLiteral

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UnaryOperator(StrEnum):
    """Unary operators supported by typed IX expressions."""

    POSITIVE = "+"
    NEGATE = "-"
    NOT = "not"


class BinaryOperator(StrEnum):
    """Binary operators supported by typed IX expressions."""

    OR = "or"
    AND = "and"
    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER = ">"
    GREATER_EQUAL = ">="
    LESS = "<"
    LESS_EQUAL = "<="
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"

    def precedence(self) -> int:
        """Return the parser precedence for this operator."""
        if self is BinaryOperator.OR:
            return 1
        if self is BinaryOperator.AND:
            return 2
        if self in {BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL}:
            return 3
        if self in {
            BinaryOperator.GREATER,
            BinaryOperator.GREATER_EQUAL,
            BinaryOperator.LESS,
            BinaryOperator.LESS_EQUAL,
        }:
            return 4
        if self in {BinaryOperator.ADD, BinaryOperator.SUBTRACT}:
            return 5
        return 6


@dataclass(frozen=True, slots=True)
class LanguageNode(ABC):
    """Base class for immutable IX abstract-syntax-tree nodes."""

    span: SourceSpan

    @abstractmethod
    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible representation of this node."""

    def children(self) -> tuple[LanguageNode, ...]:
        """Return this node's direct children in source order."""
        return ()

    def walk(self) -> tuple[LanguageNode, ...]:
        """Return a deterministic pre-order traversal rooted at this node."""
        nodes: list[LanguageNode] = [self]
        for child in self.children():
            nodes.extend(child.walk())
        return tuple(nodes)

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this AST node."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class Expression(LanguageNode):
    """Base class for value-producing IX syntax."""

    @abstractmethod
    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible expression representation."""


@dataclass(frozen=True, slots=True)
class LiteralExpression(Expression):
    """A string, number, Boolean, or null IX literal."""

    value: TokenLiteral

    def __post_init__(self) -> None:
        """Reject non-finite numbers that cannot be canonical JSON values."""
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise FoundationError("IX floating-point literals must be finite")

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible literal expression."""
        value: JsonPrimitive = self.value
        return {
            "node_type": "literal_expression",
            "span": self.span.to_payload(),
            "value": value,
        }


@dataclass(frozen=True, slots=True)
class NameExpression(Expression):
    """A reference to one IX variable or memory name."""

    name: str

    def __post_init__(self) -> None:
        """Reject names outside the IX identifier grammar."""
        if not isinstance(self.name, str) or not _IDENTIFIER_PATTERN.fullmatch(self.name):
            raise FoundationError(
                "IX expression name must be an ASCII identifier"
            )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible name expression."""
        return {
            "node_type": "name_expression",
            "span": self.span.to_payload(),
            "name": self.name,
        }


@dataclass(frozen=True, slots=True)
class GroupExpression(Expression):
    """A parenthesized IX expression."""

    expression: Expression

    def __post_init__(self) -> None:
        """Require the group span to contain its expression."""
        _require_child_span(
            parent=self.span,
            child=self.expression.span,
            field_name="group expression",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the grouped expression."""
        return (self.expression,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible group expression."""
        return {
            "node_type": "group_expression",
            "span": self.span.to_payload(),
            "expression": self.expression.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class UnaryExpression(Expression):
    """An IX unary operation over one operand."""

    operator: UnaryOperator
    operand: Expression

    def __post_init__(self) -> None:
        """Require the unary span to contain its operand."""
        _require_child_span(
            parent=self.span,
            child=self.operand.span,
            field_name="unary operand",
        )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return the unary operand."""
        return (self.operand,)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible unary expression."""
        return {
            "node_type": "unary_expression",
            "span": self.span.to_payload(),
            "operator": self.operator.value,
            "operand": self.operand.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class BinaryExpression(Expression):
    """An IX binary operation with explicit typed operands."""

    left: Expression
    operator: BinaryOperator
    right: Expression

    def __post_init__(self) -> None:
        """Require the binary span to contain both operands."""
        _require_child_span(
            parent=self.span,
            child=self.left.span,
            field_name="binary left operand",
        )
        _require_child_span(
            parent=self.span,
            child=self.right.span,
            field_name="binary right operand",
        )
        if self.left.span.start > self.right.span.start:
            raise FoundationError(
                "IX binary expression operands must remain in source order"
            )

    def children(self) -> tuple[LanguageNode, ...]:
        """Return binary operands in source order."""
        return (self.left, self.right)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible binary expression."""
        return {
            "node_type": "binary_expression",
            "span": self.span.to_payload(),
            "left": self.left.to_payload(),
            "operator": self.operator.value,
            "precedence": self.operator.precedence(),
            "right": self.right.to_payload(),
        }


def _require_child_span(
    *,
    parent: SourceSpan,
    child: SourceSpan,
    field_name: str,
) -> None:
    """Require one child span to belong to and fit inside its parent."""
    if parent.filename != child.filename:
        raise FoundationError(
            f"IX {field_name} span must use the parent filename"
        )
    if child.start < parent.start or child.end > parent.end:
        raise FoundationError(
            f"IX {field_name} span must be contained by the parent span"
        )
