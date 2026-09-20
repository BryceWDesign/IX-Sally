"""Evidence-driven invention of hypotheses and reusable cognitive primitives.

The module teaches IX-Sally a compact invention loop:

A. Detect insufficiency: do not assume an existing hypothesis catalog is complete.
B. Build candidates: compose known operations into candidate explanatory programs.
C. Check reality: retain only candidates that explain training evidence and survive holdout tests.
D. Abstract: promote a validated explanatory program into a reusable invented primitive.

This is bounded program synthesis, not unrestricted code generation. It expands the
agent's vocabulary by creating validated abstractions from experience while keeping
all concrete searches resource bounded and inspectable.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace

from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class TransformationExample:
    """One observed input/output relation used to invent or validate a hypothesis."""

    input_state: int
    output_state: int

    def to_payload(self) -> JsonObject:
        """Return an inspectable example payload."""
        return {"input_state": self.input_state, "output_state": self.output_state}


@dataclass(frozen=True, slots=True)
class InventedHypothesis:
    """A candidate transformation program synthesized from evidence, not a preset catalog."""

    hypothesis_id: str
    primitive_ids: tuple[str, ...]
    training_examples: tuple[TransformationExample, ...]
    training_accuracy: float
    validation_examples: tuple[TransformationExample, ...] = ()
    validation_accuracy: float | None = None
    origin: str = "sally-synthesized"

    def __post_init__(self) -> None:
        require_text(self.hypothesis_id, field_name="hypothesis_id")
        if not self.primitive_ids:
            raise FoundationError("invented hypothesis requires at least one primitive")
        if not self.training_examples:
            raise FoundationError("invented hypothesis requires training evidence")
        if not 0.0 <= self.training_accuracy <= 1.0:
            raise FoundationError("training accuracy must be between zero and one")
        if self.validation_accuracy is not None and not 0.0 <= self.validation_accuracy <= 1.0:
            raise FoundationError("validation accuracy must be between zero and one")

    def apply(self, state: int, primitives: Iterable[ActionPrimitive]) -> int:
        """Apply the synthesized explanatory program to one state."""
        primitive_map = {item.primitive_id: item for item in primitives}
        current = state
        for primitive_id in self.primitive_ids:
            primitive = primitive_map.get(primitive_id)
            if primitive is None:
                raise FoundationError(f"hypothesis references unknown primitive: {primitive_id}")
            current = primitive.apply(current)
        return current

    def to_payload(self) -> JsonObject:
        """Return canonical evidence describing the invented hypothesis."""
        training: JsonArray = [item.to_payload() for item in self.training_examples]
        validation: JsonArray = [item.to_payload() for item in self.validation_examples]
        return {
            "hypothesis_id": self.hypothesis_id,
            "primitive_ids": list(self.primitive_ids),
            "training_examples": training,
            "training_accuracy": self.training_accuracy,
            "validation_examples": validation,
            "validation_accuracy": self.validation_accuracy,
            "origin": self.origin,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic identity for this hypothesis and its evidence."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class InventedPrimitive:
    """A validated learned abstraction promoted into Sally's reusable action vocabulary."""

    primitive_id: str
    primitive_ids: tuple[str, ...]
    hypothesis_digest: DigestRecord
    validation_accuracy: float
    description: str
    origin: str = "sally-invented-abstraction"

    def __post_init__(self) -> None:
        require_text(self.primitive_id, field_name="primitive_id")
        require_text(self.description, field_name="description")
        if not self.primitive_ids:
            raise FoundationError("invented primitive requires a non-empty learned program")
        self.hypothesis_digest.require_algorithm("sha256")
        if not 0.0 <= self.validation_accuracy <= 1.0:
            raise FoundationError("primitive validation accuracy must be between zero and one")

    def apply(self, state: int, primitives: Iterable[ActionPrimitive]) -> int:
        """Execute this learned abstraction using the grounded primitives beneath it."""
        primitive_map = {item.primitive_id: item for item in primitives}
        current = state
        for primitive_id in self.primitive_ids:
            primitive = primitive_map.get(primitive_id)
            if primitive is None:
                raise FoundationError(
                    f"invented primitive references unknown primitive: {primitive_id}"
                )
            current = primitive.apply(current)
        return current

    def as_action_primitive(self, primitives: Iterable[ActionPrimitive]) -> ActionPrimitive:
        """Expose the invented abstraction as one reusable action primitive."""
        base = tuple(primitives)
        return ActionPrimitive(
            self.primitive_id,
            lambda state: self.apply(state, base),
            cost=1.0,
        )

    def to_payload(self) -> JsonObject:
        """Return an evidence-bound representation of the new abstraction."""
        return {
            "primitive_id": self.primitive_id,
            "primitive_ids": list(self.primitive_ids),
            "hypothesis_digest": {
                "algorithm": self.hypothesis_digest.algorithm,
                "value": self.hypothesis_digest.value,
            },
            "validation_accuracy": self.validation_accuracy,
            "description": self.description,
            "origin": self.origin,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic identity for the learned primitive."""
        return DigestRecord.from_payload(self.to_payload())


class ConceptInventor:
    """Invent explanatory programs from examples and promote validated abstractions."""

    def invent_hypothesis(
        self,
        *,
        examples: Iterable[TransformationExample],
        primitives: Iterable[ActionPrimitive],
        max_depth: int = 6,
        max_programs: int = 4096,
    ) -> InventedHypothesis:
        """Synthesize the shortest program that explains all supplied observations.

        No hypothesis catalog is supplied. Candidate hypotheses are generated by
        composing the available primitive operations and testing the resulting program
        against every training example.
        """
        training = tuple(examples)
        primitive_tuple = tuple(primitives)
        if not training:
            raise FoundationError("hypothesis invention requires at least one example")
        if not primitive_tuple:
            raise FoundationError("hypothesis invention requires grounded primitives")
        if max_depth < 1 or max_programs < 1:
            raise FoundationError("hypothesis search bounds must be positive")
        identifiers = tuple(item.primitive_id for item in primitive_tuple)
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("primitive identifiers must be unique")

        queue: deque[tuple[str, ...]] = deque([()])
        explored = 0
        while queue and explored < max_programs:
            program = queue.popleft()
            if len(program) >= max_depth:
                continue
            for primitive in primitive_tuple:
                candidate = (*program, primitive.primitive_id)
                explored += 1
                accuracy = self._accuracy(candidate, training, primitive_tuple)
                if accuracy == 1.0:
                    identity_payload: JsonObject = {
                        "program": list(candidate),
                        "examples": [item.to_payload() for item in training],
                    }
                    digest = DigestRecord.from_payload(identity_payload)
                    return InventedHypothesis(
                        hypothesis_id=f"invented-{digest.value[:16]}",
                        primitive_ids=candidate,
                        training_examples=training,
                        training_accuracy=accuracy,
                    )
                queue.append(candidate)
                if explored >= max_programs:
                    break
        raise FoundationError("no explanatory hypothesis found within search bounds")

    def validate_hypothesis(
        self,
        hypothesis: InventedHypothesis,
        *,
        examples: Iterable[TransformationExample],
        primitives: Iterable[ActionPrimitive],
    ) -> InventedHypothesis:
        """Evaluate an invented hypothesis on evidence not used to create it."""
        validation = tuple(examples)
        if not validation:
            raise FoundationError("hypothesis validation requires holdout examples")
        primitive_tuple = tuple(primitives)
        accuracy = self._accuracy(hypothesis.primitive_ids, validation, primitive_tuple)
        return replace(
            hypothesis,
            validation_examples=validation,
            validation_accuracy=accuracy,
        )

    def promote_primitive(
        self,
        hypothesis: InventedHypothesis,
        *,
        primitive_id: str,
        description: str,
    ) -> InventedPrimitive:
        """Promote a holdout-validated explanatory program into a new reusable primitive."""
        if hypothesis.training_accuracy < 1.0:
            raise FoundationError("only fully explanatory hypotheses may become primitives")
        if hypothesis.validation_accuracy != 1.0:
            raise FoundationError("primitive promotion requires perfect holdout validation")
        return InventedPrimitive(
            primitive_id=require_text(primitive_id, field_name="primitive_id"),
            primitive_ids=hypothesis.primitive_ids,
            hypothesis_digest=hypothesis.digest(),
            validation_accuracy=hypothesis.validation_accuracy,
            description=require_text(description, field_name="description"),
        )

    @staticmethod
    def _accuracy(
        program: tuple[str, ...],
        examples: tuple[TransformationExample, ...],
        primitives: tuple[ActionPrimitive, ...],
    ) -> float:
        primitive_map = {item.primitive_id: item for item in primitives}
        correct = 0
        for example in examples:
            state = example.input_state
            for primitive_id in program:
                primitive = primitive_map.get(primitive_id)
                if primitive is None:
                    raise FoundationError(f"unknown primitive during invention: {primitive_id}")
                state = primitive.apply(state)
            if state == example.output_state:
                correct += 1
        return correct / len(examples)
