"""Static value-type analysis for typed IX executable programs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.language.ast import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    GroupExpression,
    LiteralExpression,
    NameExpression,
    UnaryExpression,
    UnaryOperator,
)
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


class IXValueType(StrEnum):
    """Static value categories supported by the IX expression kernel."""

    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    UNKNOWN = "unknown"

    def is_numeric(self) -> bool:
        """Return whether this type participates in numeric operations."""
        return self in {IXValueType.INTEGER, IXValueType.FLOAT}

    def is_known(self) -> bool:
        """Return whether static analysis resolved a concrete value type."""
        return self is not IXValueType.UNKNOWN


@dataclass(frozen=True, slots=True)
class IXTypeBinding:
    """One deterministic name-to-type binding in an IX type environment."""

    name: str
    value_type: IXValueType

    def __post_init__(self) -> None:
        """Require one valid IX identifier."""
        if not isinstance(self.name, str) or not _IDENTIFIER_PATTERN.fullmatch(
            self.name
        ):
            raise FoundationError("IX type binding name must be an ASCII identifier")

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible type binding."""
        return {
            "name": self.name,
            "value_type": self.value_type.value,
        }


@dataclass(frozen=True, slots=True)
class IXTypeContext:
    """Static types available before one IX program is checked."""

    local_types: tuple[IXTypeBinding, ...] = ()
    memory_types: tuple[IXTypeBinding, ...] = ()

    def __post_init__(self) -> None:
        """Normalize context bindings into deterministic unique sequences."""
        object.__setattr__(
            self,
            "local_types",
            _normalize_bindings(self.local_types, field_name="local_types"),
        )
        object.__setattr__(
            self,
            "memory_types",
            _normalize_bindings(self.memory_types, field_name="memory_types"),
        )


@dataclass(frozen=True, slots=True)
class IXTypeReport:
    """Deterministic static type report for one IX program."""

    program_digest: DigestRecord
    diagnostics: tuple[LanguageDiagnostic, ...]
    local_types: tuple[IXTypeBinding, ...]
    memory_types: tuple[IXTypeBinding, ...]

    def __post_init__(self) -> None:
        """Validate report identity and normalize exported environments."""
        self.program_digest.require_algorithm("sha256")
        object.__setattr__(
            self,
            "local_types",
            _normalize_bindings(self.local_types, field_name="local_types"),
        )
        object.__setattr__(
            self,
            "memory_types",
            _normalize_bindings(self.memory_types, field_name="memory_types"),
        )

    def errors(self) -> tuple[LanguageDiagnostic, ...]:
        """Return static type errors in deterministic source order."""
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is DiagnosticSeverity.ERROR
        )

    def is_valid(self) -> bool:
        """Return whether type analysis found no errors."""
        return not self.errors()

    def require_valid(self) -> IXTypeReport:
        """Return this report or raise its first static type error."""
        errors = self.errors()
        if errors:
            raise IXValidationError(errors[0])
        return self

    def local_type(self, name: str) -> IXValueType | None:
        """Return the final static type for one local name."""
        return _binding_type(self.local_types, name=name)

    def memory_type(self, name: str) -> IXValueType | None:
        """Return the final static type for one memory name."""
        return _binding_type(self.memory_types, name=name)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible type report."""
        diagnostics: JsonArray = [
            diagnostic.to_payload() for diagnostic in self.diagnostics
        ]
        local_types: JsonArray = [binding.to_payload() for binding in self.local_types]
        memory_types: JsonArray = [
            binding.to_payload() for binding in self.memory_types
        ]
        return {
            "program_digest": {
                "algorithm": self.program_digest.algorithm,
                "value": self.program_digest.value,
            },
            "diagnostics": diagnostics,
            "diagnostic_count": len(self.diagnostics),
            "error_count": len(self.errors()),
                  "local_types": local_types,
            "memory_types": memory_types,
            "is_valid": self.is_valid(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this type report."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class IXTypeChecker:
    """Infer expression types and enforce IX operator contracts."""

    context: IXTypeContext = field(default_factory=IXTypeContext)

    def check(self, program: Program) -> IXTypeReport:
        """Return a complete static type report for ``program``."""
        local_types = _binding_map(self.context.local_types)
        memory_types = _binding_map(self.context.memory_types)
        diagnostics: list[LanguageDiagnostic] = []

        for statement in program.statements:
            self._check_statement(
                statement,
                local_types=local_types,
                memory_types=memory_types,
                diagnostics=diagnostics,
            )

        return IXTypeReport(
            program_digest=program.digest(),
            diagnostics=tuple(diagnostics),
            local_types=_bindings_from_map(local_types),
            memory_types=_bindings_from_map(memory_types),
        )

    def _check_statement(
        self,
        statement: Statement,
        *,
        local_types: dict[str, IXValueType],
        memory_types: dict[str, IXValueType],
        diagnostics: list[LanguageDiagnostic],
    ) -> None:
        """Check one statement and update visible static environments."""
        if isinstance(statement, LetStatement):
            value_type = _infer_expression_type(
                statement.expression,
                local_types=local_types,
                diagnostics=diagnostics,
            )
            local_types.setdefault(statement.name, value_type)
            return

        if isinstance(statement, RememberStatement):
            memory_types[statement.name] = _infer_expression_type(
                statement.expression,
                local_types=local_types,
                diagnostics=diagnostics,
            )
            return

        if isinstance(statement, RecallStatement):
            return

        expression = _statement_expression(statement)
        value_type = _infer_expression_type(
            expression,
            local_types=local_types,
            diagnostics=diagnostics,
        )
        if (
            isinstance(statement, AssertStatement)
            and value_type.is_known()
            and value_type is not IXValueType.BOOLEAN
        ):
            diagnostics.append(
                LanguageDiagnostic.create(
                    code="typing.assertion-not-boolean",
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        "Assert expression must be Boolean, "
                        f"not {value_type.value}."
                    ),
                    span=statement.expression.span,
                    hint="Use a comparison or Boolean expression after 'assert'.",
                )
            )


def check_ix_program_types(
    program: Program,
    *,
    context: IXTypeContext | None = None,
) -> IXTypeReport:
    """Return static type analysis for one typed IX program."""
    return IXTypeChecker(context=context or IXTypeContext()).check(program)


def require_typed_ix_program(
    program: Program,
    *,
    context: IXTypeContext | None = None,
) -> IXTypeReport:
    """Check one IX program and raise its first static type error."""
    return check_ix_program_types(program, context=context).require_valid()


def infer_ix_expression_type(
    expression: Expression,
    *,
    local_types: Iterable[IXTypeBinding] = (),
) -> IXValueType:
    """Infer one expression type without returning diagnostics."""
    diagnostics: list[LanguageDiagnostic] = []
    return _infer_expression_type(
        expression,
        local_types=_binding_map(
            _normalize_bindings(local_types, field_name="local_types")
        ),
        diagnostics=diagnostics,
    )


def _infer_expression_type(
    expression: Expression,
    *,
    local_types: dict[str, IXValueType],
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Infer one expression type and append operator diagnostics."""
    if isinstance(expression, LiteralExpression):
        return _literal_type(expression.value)

    if isinstance(expression, NameExpression):
        return local_types.get(expression.name, IXValueType.UNKNOWN)

    if isinstance(expression, GroupExpression):
        return _infer_expression_type(
            expression.expression,
            local_types=local_types,
            diagnostics=diagnostics,
        )

    if isinstance(expression, UnaryExpression):
        operand_type = _infer_expression_type(
            expression.operand,
            local_types=local_types,
            diagnostics=diagnostics,
        )
        return _unary_result_type(
            expression,
            operand_type=operand_type,
            diagnostics=diagnostics,
        )

    if isinstance(expression, BinaryExpression):
        left_type = _infer_expression_type(
            expression.left,
            local_types=local_types,
            diagnostics=diagnostics,
        )
        right_type = _infer_expression_type(
            expression.right,
            local_types=local_types,
            diagnostics=diagnostics,
        )
        return _binary_result_type(
            expression,
                  left_type=left_type,
            right_type=right_type,
            diagnostics=diagnostics,
        )

    raise FoundationError(
        f"unsupported IX expression type for static analysis: "
        f"{type(expression).__name__}"
    )


def _unary_result_type(
    expression: UnaryExpression,
    *,
    operand_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the static result type for one unary expression."""
    if operand_type is IXValueType.UNKNOWN:
        return IXValueType.UNKNOWN

    if expression.operator in {UnaryOperator.POSITIVE, UnaryOperator.NEGATE}:
        if operand_type.is_numeric():
            return operand_type
        _append_operator_diagnostic(
            expression=expression,
            diagnostics=diagnostics,
            message=(
                f"Unary operator {expression.operator.value!r} requires a numeric "
                f"operand, not {operand_type.value}."
            ),
        )
        return IXValueType.UNKNOWN

    if operand_type is IXValueType.BOOLEAN:
        return IXValueType.BOOLEAN
    _append_operator_diagnostic(
        expression=expression,
        diagnostics=diagnostics,
        message=(
            "Unary operator 'not' requires a Boolean operand, "
            f"not {operand_type.value}."
        ),
    )
    return IXValueType.UNKNOWN


def _binary_result_type(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the static result type for one binary expression."""
    if IXValueType.UNKNOWN in {left_type, right_type}:
        return IXValueType.UNKNOWN

    operator = expression.operator
    if operator in {BinaryOperator.AND, BinaryOperator.OR}:
        return _logical_result_type(
            expression,
            left_type=left_type,
            right_type=right_type,
            diagnostics=diagnostics,
        )
    if operator in {BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL}:
        return _equality_result_type(
            expression,
            left_type=left_type,
            right_type=right_type,
            diagnostics=diagnostics,
        )
    if operator in {
        BinaryOperator.GREATER,
        BinaryOperator.GREATER_EQUAL,
        BinaryOperator.LESS,
        BinaryOperator.LESS_EQUAL,
    }:
        return _ordered_result_type(
            expression,
            left_type=left_type,
            right_type=right_type,
            diagnostics=diagnostics,
        )
    if operator is BinaryOperator.ADD:
        return _addition_result_type(
            expression,
            left_type=left_type,
            right_type=right_type,
            diagnostics=diagnostics,
        )
    return _numeric_result_type(
        expression,
        left_type=left_type,
        right_type=right_type,
        diagnostics=diagnostics,
    )


def _logical_result_type(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the result type for one Boolean binary operation."""
    if left_type is right_type is IXValueType.BOOLEAN:
        return IXValueType.BOOLEAN
    return _invalid_binary_result(
        expression,
        left_type=left_type,
        right_type=right_type,
        diagnostics=diagnostics,
        expected="Boolean operands",
    )


def _equality_result_type(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the result type for one equality operation."""
    if _equality_compatible(left_type, right_type):
        return IXValueType.BOOLEAN
    return _invalid_binary_result(
        expression,
        left_type=left_type,
        right_type=right_type,
        diagnostics=diagnostics,
        expected="matching or numeric operands",
    )


def _ordered_result_type(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the result type for one ordered comparison."""
    if _ordered_compatible(left_type, right_type):
        return IXValueType.BOOLEAN
    return _invalid_binary_result(
        expression,
        left_type=left_type,
        right_type=right_type,
        diagnostics=diagnostics,
        expected="two numeric operands or two strings",
    )


def _addition_result_type(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the result type for IX addition or string concatenation."""
    if left_type.is_numeric() and right_type.is_numeric():
        return _promoted_numeric_type(left_type, right_type)
    if left_type is right_type is IXValueType.STRING:
        return IXValueType.STRING
    return _invalid_binary_result(
          expression,
        left_type=left_type,
        right_type=right_type,
        diagnostics=diagnostics,
        expected="two numeric operands or two strings",
    )


def _numeric_result_type(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
) -> IXValueType:
    """Return the result type for subtraction, multiplication, or division."""
    if not left_type.is_numeric() or not right_type.is_numeric():
        return _invalid_binary_result(
            expression,
            left_type=left_type,
            right_type=right_type,
            diagnostics=diagnostics,
            expected="numeric operands",
        )
    if expression.operator is BinaryOperator.DIVIDE:
        return IXValueType.FLOAT
    return _promoted_numeric_type(left_type, right_type)


def _invalid_binary_result(
    expression: BinaryExpression,
    *,
    left_type: IXValueType,
    right_type: IXValueType,
    diagnostics: list[LanguageDiagnostic],
    expected: str,
) -> IXValueType:
    """Append one binary-operator diagnostic and return unknown."""
    _append_operator_diagnostic(
        expression=expression,
        diagnostics=diagnostics,
        message=(
            f"Operator {expression.operator.value!r} requires {expected}; "
            f"received {left_type.value} and {right_type.value}."
        ),
    )
    return IXValueType.UNKNOWN


def _append_operator_diagnostic(
    *,
    expression: UnaryExpression | BinaryExpression,
    diagnostics: list[LanguageDiagnostic],
    message: str,
) -> None:
    """Append one structured invalid-operator diagnostic."""
    diagnostics.append(
        LanguageDiagnostic.create(
            code="typing.invalid-operator-operands",
            severity=DiagnosticSeverity.ERROR,
            message=message,
            span=expression.span,
            hint="Use operands compatible with the IX operator contract.",
        )
    )


def _literal_type(value: str | int | float | bool | None) -> IXValueType:
    """Return the exact static type for one literal value."""
    if value is None:
        return IXValueType.NULL
    if isinstance(value, bool):
        return IXValueType.BOOLEAN
    if isinstance(value, int):
        return IXValueType.INTEGER
    if isinstance(value, float):
        return IXValueType.FLOAT
    return IXValueType.STRING


def _promoted_numeric_type(
    left_type: IXValueType,
    right_type: IXValueType,
) -> IXValueType:
    """Return the deterministic result of IX numeric promotion."""
    if IXValueType.FLOAT in {left_type, right_type}:
        return IXValueType.FLOAT
    return IXValueType.INTEGER


def _equality_compatible(
    left_type: IXValueType,
    right_type: IXValueType,
) -> bool:
    """Return whether two types may be compared for equality."""
    return (
        left_type is right_type
        or left_type.is_numeric()
        and right_type.is_numeric()
        or IXValueType.NULL in {left_type, right_type}
    )


def _ordered_compatible(
    left_type: IXValueType,
    right_type: IXValueType,
) -> bool:
    """Return whether two types support ordered comparison."""
    return (
        left_type.is_numeric()
        and right_type.is_numeric()
        or left_type is right_type is IXValueType.STRING
    )


def _statement_expression(statement: Statement) -> Expression:
    """Return the expression owned by a supported expression statement."""
    if isinstance(
        statement,
        (PrintStatement, ReplyStatement, AssertStatement, TraceStatement),
    ):
        return statement.expression
    raise FoundationError(
        f"unsupported IX statement type for static analysis: "
        f"{type(statement).__name__}"
    )


def _normalize_bindings(
    bindings: Iterable[IXTypeBinding],
    *,
    field_name: str,
) -> tuple[IXTypeBinding, ...]:
    """Validate, deduplicate, and sort one type-binding collection."""
    by_name: dict[str, IXTypeBinding] = {}
    for binding in bindings:
        if not isinstance(binding, IXTypeBinding):
            raise FoundationError(
                f"IX type context {field_name} must contain IXTypeBinding values"
            )
        existing = by_name.get(binding.name)
        if existing is not None and existing.value_type is not binding.value_type:
            raise FoundationError(
                f"IX type context {field_name} contains conflicting types for "
                f"{binding.name!r}"
            )
        by_name[binding.name] = binding
    return tuple(by_name[name] for name in sorted(by_name))


def _binding_map(bindings: Iterable[IXTypeBinding]) -> dict[str, IXValueType]:
    """Return a mutable type environment from deterministic bindings."""
    return {binding.name: binding.value_type for binding in bindings}


def _bindings_from_map(
    values: dict[str, IXValueType],
) -> tuple[IXTypeBinding, ...]:
    """Return deterministic bindings from one mutable type environment."""
    return tuple(
        IXTypeBinding(name=name, value_type=values[name])
        for name in sorted(values)
    )


def _binding_type(
    bindings: tuple[IXTypeBinding, ...],
    *,
    name: str,
) -> IXValueType | None:
    """Return one binding type by name."""
    for binding in bindings:
        if binding.name == name:
            return binding.value_type
    return None
