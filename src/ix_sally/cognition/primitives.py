"""Grounded cognitive primitive lifecycle and deterministic execution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.values import CognitiveValue
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class PrimitiveKind(StrEnum):
    """Closed classes of cognitive operations available to IX-Sally."""

    TRANSFORM = "transform"
    COMPARE = "compare"
    SELECT = "select"
    AGGREGATE = "aggregate"


class PrimitiveStatus(StrEnum):
    """Lifecycle state for a cognitive primitive."""

    CANDIDATE = "candidate"
    GROUNDED = "grounded"
    VALIDATED = "validated"
    QUARANTINED = "quarantined"
    RETIRED = "retired"


class PrimitiveOperation(StrEnum):
    """Dependency-free operations implemented by the primitive executor."""

    IDENTITY = "identity"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    EQUAL = "equal"
    GREATER = "greater"
    LESS = "less"
    ALL = "all"
    ANY = "any"
    FIRST = "first"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"


@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    """One immutable primitive with explicit grounding and validation evidence."""

    primitive_id: CanonicalKey
    kind: PrimitiveKind
    operation: PrimitiveOperation
    arity: int
    status: PrimitiveStatus
    description: str
    grounding_digests: tuple[DigestRecord, ...] = ()
    validation_digests: tuple[DigestRecord, ...] = ()
    reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        primitive_id: str,
        kind: PrimitiveKind,
        operation: PrimitiveOperation,
        arity: int,
        status: PrimitiveStatus,
        description: str,
        grounding_digests: Iterable[DigestRecord] = (),
        validation_digests: Iterable[DigestRecord] = (),
        reason: str | None = None,
    ) -> PrimitiveSpec:
        """Create and validate a primitive lifecycle record."""
        if arity <= 0:
            raise FoundationError("primitive arity must be positive")
        grounding = tuple(grounding_digests)
        validation = tuple(validation_digests)
        for digest in (*grounding, *validation):
            digest.require_algorithm("sha256")
        if status in {PrimitiveStatus.GROUNDED, PrimitiveStatus.VALIDATED} and not grounding:
            raise FoundationError("grounded primitive requires grounding evidence")
        if status is PrimitiveStatus.VALIDATED and not validation:
            raise FoundationError("validated primitive requires validation evidence")
        if status in {PrimitiveStatus.QUARANTINED, PrimitiveStatus.RETIRED} and not reason:
            raise FoundationError("inactive primitive requires a reason")
        return cls(
            primitive_id=CanonicalKey.from_text(
                primitive_id,
                field_name="primitive_id",
            ),
            kind=kind,
            operation=operation,
            arity=arity,
            status=status,
            description=require_text(description, field_name="description"),
            grounding_digests=grounding,
            validation_digests=validation,
            reason=require_text(reason, field_name="reason") if reason else None,
        )

    def is_executable(self) -> bool:
        """Return whether this primitive may run in the cognitive core."""
        return self.status is PrimitiveStatus.VALIDATED

    def to_payload(self) -> JsonObject:
        """Return a deterministic primitive representation."""
        grounding: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.grounding_digests
        ]
        validation: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.validation_digests
        ]
        return {
            "primitive_id": self.primitive_id.value,
            "kind": self.kind.value,
            "operation": self.operation.value,
            "arity": self.arity,
            "status": self.status.value,
            "description": self.description,
            "grounding_digests": grounding,
            "validation_digests": validation,
            "reason": self.reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic primitive identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class PrimitiveRegistry:
    """Immutable registry that rejects duplicate primitive identifiers."""

    primitives: tuple[PrimitiveSpec, ...]

    @classmethod
    def create(cls, primitives: Iterable[PrimitiveSpec]) -> PrimitiveRegistry:
        """Create a stable registry ordered by primitive identifier."""
        normalized = tuple(sorted(primitives, key=lambda item: item.primitive_id.value))
        identifiers = [item.primitive_id.value for item in normalized]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("primitive registry contains duplicate identifiers")
        return cls(normalized)

    def require(self, primitive_id: str) -> PrimitiveSpec:
        """Return a primitive by canonical identifier."""
        requested = CanonicalKey.from_text(primitive_id, field_name="primitive_id")
        for primitive in self.primitives:
            if primitive.primitive_id == requested:
                return primitive
        raise FoundationError(f"unknown primitive: {requested.value}")

    def executable(self) -> tuple[PrimitiveSpec, ...]:
        """Return validated primitives only."""
        return tuple(item for item in self.primitives if item.is_executable())

    def to_payload(self) -> JsonObject:
        """Return a canonical registry payload."""
        payload: JsonArray = [item.to_payload() for item in self.primitives]
        return {"count": len(self.primitives), "primitives": payload}

    def digest(self) -> DigestRecord:
        """Return a deterministic registry identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class PrimitiveExecution:
    """Receipt from one validated primitive invocation."""

    primitive_digest: DigestRecord
    inputs: tuple[CognitiveValue, ...]
    output: CognitiveValue

    def to_payload(self) -> JsonObject:
        """Return a deterministic execution receipt."""
        inputs: JsonArray = [value.to_payload() for value in self.inputs]
        return {
            "primitive_digest": {
                "algorithm": self.primitive_digest.algorithm,
                "value": self.primitive_digest.value,
            },
            "inputs": inputs,
            "output": self.output.to_payload(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic execution identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class PrimitiveExecutor:
    """Execute only enumerated validated primitives without dynamic callbacks."""

    registry: PrimitiveRegistry

    def execute(
        self,
        primitive_id: str,
        inputs: Iterable[CognitiveValue],
    ) -> PrimitiveExecution:
        """Execute one primitive and return an inspectable receipt."""
        primitive = self.registry.require(primitive_id)
        if not primitive.is_executable():
            raise FoundationError(
                f"primitive is not validated for execution: {primitive.primitive_id.value}"
            )
        normalized = tuple(inputs)
        if len(normalized) != primitive.arity:
            raise FoundationError(
                f"primitive {primitive.primitive_id.value} requires {primitive.arity} "
                f"inputs, got {len(normalized)}"
            )
        output = self._apply(primitive.operation, normalized)
        return PrimitiveExecution(
            primitive_digest=primitive.digest(),
            inputs=normalized,
            output=output,
        )

    def _apply(
        self,
        operation: PrimitiveOperation,
        inputs: tuple[CognitiveValue, ...],
    ) -> CognitiveValue:
        """Apply one closed primitive operation."""
        if operation is PrimitiveOperation.IDENTITY:
            return inputs[0]
        if operation is PrimitiveOperation.FIRST:
            return inputs[0]
        if operation in {PrimitiveOperation.ALL, PrimitiveOperation.ANY}:
            booleans = tuple(
                value.require_boolean(operation=operation.value) for value in inputs
            )
            result = all(booleans) if operation is PrimitiveOperation.ALL else any(booleans)
            return CognitiveValue.from_python(result)
        if operation is PrimitiveOperation.EQUAL:
            left, right = inputs
            return CognitiveValue.from_python(
                left.value_type is right.value_type and left.value == right.value
            )
        numeric = tuple(
            value.require_numeric(operation=operation.value) for value in inputs
        )
        if operation is PrimitiveOperation.ADD:
            return CognitiveValue.from_python(sum(numeric))
        if operation is PrimitiveOperation.SUBTRACT:
            return CognitiveValue.from_python(numeric[0] - numeric[1])
        if operation is PrimitiveOperation.MULTIPLY:
            result: int | float = 1
            for number in numeric:
                result *= number
            return CognitiveValue.from_python(result)
        if operation is PrimitiveOperation.GREATER:
            return CognitiveValue.from_python(numeric[0] > numeric[1])
        if operation is PrimitiveOperation.LESS:
            return CognitiveValue.from_python(numeric[0] < numeric[1])
        if operation is PrimitiveOperation.MAXIMUM:
            return CognitiveValue.from_python(max(numeric))
        if operation is PrimitiveOperation.MINIMUM:
            return CognitiveValue.from_python(min(numeric))
        raise FoundationError(f"unsupported primitive operation: {operation.value}")


def default_primitive_registry() -> PrimitiveRegistry:
    """Return a small validated kernel with explicit synthetic test evidence."""
    grounding = DigestRecord.from_payload(
        {"source": "IX-Sally built-in primitive semantics", "version": 1}
    )
    validation = DigestRecord.from_payload(
        {"suite": "built-in deterministic primitive conformance", "version": 1}
    )
    definitions: tuple[tuple[str, PrimitiveKind, PrimitiveOperation, int], ...] = (
        ("identity", PrimitiveKind.TRANSFORM, PrimitiveOperation.IDENTITY, 1),
        ("add-two", PrimitiveKind.AGGREGATE, PrimitiveOperation.ADD, 2),
        ("subtract", PrimitiveKind.TRANSFORM, PrimitiveOperation.SUBTRACT, 2),
        ("multiply-two", PrimitiveKind.AGGREGATE, PrimitiveOperation.MULTIPLY, 2),
        ("equal", PrimitiveKind.COMPARE, PrimitiveOperation.EQUAL, 2),
        ("greater", PrimitiveKind.COMPARE, PrimitiveOperation.GREATER, 2),
        ("less", PrimitiveKind.COMPARE, PrimitiveOperation.LESS, 2),
        ("all-two", PrimitiveKind.AGGREGATE, PrimitiveOperation.ALL, 2),
        ("any-two", PrimitiveKind.AGGREGATE, PrimitiveOperation.ANY, 2),
        ("maximum-two", PrimitiveKind.SELECT, PrimitiveOperation.MAXIMUM, 2),
        ("minimum-two", PrimitiveKind.SELECT, PrimitiveOperation.MINIMUM, 2),
    )
    return PrimitiveRegistry.create(
        PrimitiveSpec.create(
            primitive_id=identifier,
            kind=kind,
            operation=operation,
            arity=arity,
            status=PrimitiveStatus.VALIDATED,
            description=f"Built-in deterministic {operation.value} primitive.",
            grounding_digests=(grounding,),
            validation_digests=(validation,),
        )
        for identifier, kind, operation, arity in definitions
    )
