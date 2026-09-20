"""Bounded representation invention and semantic promotion.

This module goes beyond selecting weights inside one fixed linear representation. Sally
constructs candidate *feature languages* from raw channels (atomic values, sums,
differences, products, absolute differences, minima, and maxima), measures whether the
existing atomic vocabulary is insufficient, and promotes a validated invented feature
into an opaque reusable semantic primitive.

The grammar is deliberately finite per deliberation. This is experimental representation
synthesis, not a claim of unrestricted mathematical invention.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import pairwise
from math import isfinite

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


class FeatureOperator(StrEnum):
    """Operators Sally may combine to create an alternative representation."""

    ATOMIC = "atomic"
    SUM = "sum"
    DIFFERENCE = "difference"
    PRODUCT = "product"
    ABS_DIFFERENCE = "abs_difference"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class RepresentationObservation:
    """Raw sensory channels plus one observed binary consequence."""

    observation_id: str
    channels: tuple[float, ...]
    consequence: bool

    def __post_init__(self) -> None:
        require_text(self.observation_id, field_name="observation_id")
        if not self.channels:
            raise FoundationError("representation observation requires channels")
        if not all(isfinite(value) for value in self.channels):
            raise FoundationError("representation channels must be finite")

    def to_payload(self) -> JsonObject:
        return {
            "observation_id": self.observation_id,
            "channels": list(self.channels),
            "consequence": self.consequence,
        }


@dataclass(frozen=True, slots=True)
class InventedRepresentation:
    """A machine-created feature that makes a previously poor distinction usable."""

    representation_id: str
    operator: FeatureOperator
    left_index: int
    right_index: int | None
    threshold: float
    polarity: int
    training_accuracy: float
    atomic_baseline_accuracy: float
    training_observations: tuple[RepresentationObservation, ...]
    validation_observations: tuple[RepresentationObservation, ...] = ()
    validation_accuracy: float | None = None
    origin: str = "sally-representation-invention"

    def __post_init__(self) -> None:
        require_text(self.representation_id, field_name="representation_id")
        if self.left_index < 0:
            raise FoundationError("left_index must not be negative")
        if self.right_index is not None and self.right_index < 0:
            raise FoundationError("right_index must not be negative")
        if self.polarity not in {-1, 1}:
            raise FoundationError("representation polarity must be -1 or 1")
        if not isfinite(self.threshold):
            raise FoundationError("representation threshold must be finite")
        for name, value in (
            ("training_accuracy", self.training_accuracy),
            ("atomic_baseline_accuracy", self.atomic_baseline_accuracy),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")
        if self.validation_accuracy is not None and not 0.0 <= self.validation_accuracy <= 1.0:
            raise FoundationError("validation_accuracy must be between zero and one")

    @property
    def is_non_atomic(self) -> bool:
        return self.operator is not FeatureOperator.ATOMIC

    def feature_value(self, channels: tuple[float, ...]) -> float:
        """Evaluate the invented representation for one raw observation."""
        if self.left_index >= len(channels):
            raise FoundationError("left representation index is outside observation arity")
        left = channels[self.left_index]
        if self.operator is FeatureOperator.ATOMIC:
            return left
        if self.right_index is None or self.right_index >= len(channels):
            raise FoundationError("binary representation operator requires a valid right index")
        right = channels[self.right_index]
        if self.operator is FeatureOperator.SUM:
            return left + right
        if self.operator is FeatureOperator.DIFFERENCE:
            return left - right
        if self.operator is FeatureOperator.PRODUCT:
            return left * right
        if self.operator is FeatureOperator.ABS_DIFFERENCE:
            return abs(left - right)
        if self.operator is FeatureOperator.MINIMUM:
            return min(left, right)
        if self.operator is FeatureOperator.MAXIMUM:
            return max(left, right)
        raise FoundationError(f"unsupported representation operator: {self.operator.value}")

    def activates(self, channels: tuple[float, ...]) -> bool:
        """Return the operational meaning of this opaque learned semantic."""
        return self.polarity * self.feature_value(channels) >= self.polarity * self.threshold

    def to_payload(self) -> JsonObject:
        training: JsonArray = [item.to_payload() for item in self.training_observations]
        validation: JsonArray = [item.to_payload() for item in self.validation_observations]
        return {
            "representation_id": self.representation_id,
            "operator": self.operator.value,
            "left_index": self.left_index,
            "right_index": self.right_index,
            "threshold": self.threshold,
            "polarity": self.polarity,
            "training_accuracy": self.training_accuracy,
            "atomic_baseline_accuracy": self.atomic_baseline_accuracy,
            "validation_accuracy": self.validation_accuracy,
            "training_observations": training,
            "validation_observations": validation,
            "origin": self.origin,
            "human_semantic_label": None,
        }

    def digest(self) -> DigestRecord:
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SemanticPrimitive:
    """Validated invented representation promoted into Sally's usable ontology."""

    primitive_id: str
    representation: InventedRepresentation

    def __post_init__(self) -> None:
        require_text(self.primitive_id, field_name="primitive_id")
        if self.representation.validation_accuracy != 1.0:
            raise FoundationError("semantic primitive requires perfect holdout validation")

    def evaluate(self, channels: tuple[float, ...]) -> bool:
        return self.representation.activates(channels)

    def to_payload(self) -> JsonObject:
        return {
            "primitive_id": self.primitive_id,
            "representation_digest": {
                "algorithm": self.representation.digest().algorithm,
                "value": self.representation.digest().value,
            },
            "origin": "sally-invented-semantic-primitive",
            "human_semantic_label": None,
        }


class RepresentationInventor:
    """Search alternative feature representations when atomic channels fail."""

    def invent_binary(
        self,
        *,
        observations: Iterable[RepresentationObservation],
        minimum_improvement: float = 0.15,
    ) -> InventedRepresentation:
        training = tuple(observations)
        self._validate(training)
        if not 0.0 <= minimum_improvement <= 1.0:
            raise FoundationError("minimum_improvement must be between zero and one")
        atomic = self._best(training, operators=(FeatureOperator.ATOMIC,))
        operators = (
            FeatureOperator.SUM,
            FeatureOperator.DIFFERENCE,
            FeatureOperator.PRODUCT,
            FeatureOperator.ABS_DIFFERENCE,
            FeatureOperator.MINIMUM,
            FeatureOperator.MAXIMUM,
        )
        invented = self._best(training, operators=operators)
        if invented is None or atomic is None:
            raise FoundationError("representation search produced no candidate")
        if invented[0] < atomic[0] + minimum_improvement:
            raise FoundationError(
                "no alternative representation materially improves atomic features"
            )
        accuracy, operator, left, right, threshold, polarity = invented
        identity = DigestRecord.from_payload(
            {
                "operator": operator.value,
                "left": left,
                "right": right,
                "threshold": threshold,
                "polarity": polarity,
                "training": [item.to_payload() for item in training],
            }
        )
        return InventedRepresentation(
            representation_id=f"representation-{identity.value[:16]}",
            operator=operator,
            left_index=left,
            right_index=right,
            threshold=threshold,
            polarity=polarity,
            training_accuracy=accuracy,
            atomic_baseline_accuracy=atomic[0],
            training_observations=training,
        )

    def validate(
        self,
        representation: InventedRepresentation,
        *,
        observations: Iterable[RepresentationObservation],
    ) -> InventedRepresentation:
        validation = tuple(observations)
        self._validate(
            validation, expected_arity=len(representation.training_observations[0].channels)
        )
        correct = sum(
            representation.activates(item.channels) is item.consequence for item in validation
        )
        return replace(
            representation,
            validation_observations=validation,
            validation_accuracy=correct / len(validation),
        )

    def promote(self, representation: InventedRepresentation) -> SemanticPrimitive:
        if representation.training_accuracy != 1.0 or representation.validation_accuracy != 1.0:
            raise FoundationError(
                "semantic promotion requires perfect train and holdout performance"
            )
        return SemanticPrimitive(
            primitive_id=f"semantic-{representation.digest().value[:16]}",
            representation=representation,
        )

    def _best(
        self,
        observations: tuple[RepresentationObservation, ...],
        *,
        operators: tuple[FeatureOperator, ...],
    ) -> tuple[float, FeatureOperator, int, int | None, float, int] | None:
        arity = len(observations[0].channels)
        best: tuple[float, FeatureOperator, int, int | None, float, int] | None = None
        index_pairs: list[tuple[int, int | None]]
        for operator in operators:
            if operator is FeatureOperator.ATOMIC:
                index_pairs = [(index, None) for index in range(arity)]
            else:
                index_pairs = [
                    (left, right) for left in range(arity) for right in range(left + 1, arity)
                ]
            for left, right in index_pairs:
                values = tuple(
                    self._evaluate(operator, left, right, item.channels) for item in observations
                )
                for threshold in self._thresholds(values):
                    for polarity in (-1, 1):
                        correct = sum(
                            (polarity * value >= polarity * threshold) is item.consequence
                            for value, item in zip(values, observations, strict=True)
                        )
                        accuracy = correct / len(observations)
                        candidate = (accuracy, operator, left, right, threshold, polarity)
                        if best is None or self._rank(candidate) > self._rank(best):
                            best = candidate
        return best

    @staticmethod
    def _rank(
        item: tuple[float, FeatureOperator, int, int | None, float, int],
    ) -> tuple[float, int, int, int, float, int]:
        accuracy, operator, left, right, threshold, polarity = item
        operator_order = list(FeatureOperator).index(operator)
        return (
            accuracy,
            -operator_order,
            -left,
            -(right if right is not None else -1),
            -abs(threshold),
            polarity,
        )

    @staticmethod
    def _evaluate(
        operator: FeatureOperator,
        left_index: int,
        right_index: int | None,
        channels: tuple[float, ...],
    ) -> float:
        left = channels[left_index]
        if operator is FeatureOperator.ATOMIC:
            return left
        if right_index is None:
            raise FoundationError("binary operator missing right channel")
        right = channels[right_index]
        if operator is FeatureOperator.SUM:
            return left + right
        if operator is FeatureOperator.DIFFERENCE:
            return left - right
        if operator is FeatureOperator.PRODUCT:
            return left * right
        if operator is FeatureOperator.ABS_DIFFERENCE:
            return abs(left - right)
        if operator is FeatureOperator.MINIMUM:
            return min(left, right)
        if operator is FeatureOperator.MAXIMUM:
            return max(left, right)
        raise FoundationError("unsupported feature operator")

    @staticmethod
    def _thresholds(values: tuple[float, ...]) -> tuple[float, ...]:
        ordered = sorted(set(values))
        if not ordered:
            return (0.0,)
        candidates = [ordered[0] - 1.0, ordered[-1] + 1.0, *ordered]
        candidates.extend((left + right) / 2.0 for left, right in pairwise(ordered))
        return tuple(sorted(set(candidates)))

    @staticmethod
    def _validate(
        observations: tuple[RepresentationObservation, ...],
        *,
        expected_arity: int | None = None,
    ) -> None:
        if not observations:
            raise FoundationError("representation invention requires observations")
        arity = len(observations[0].channels)
        if expected_arity is not None and arity != expected_arity:
            raise FoundationError("representation validation arity mismatch")
        if any(len(item.channels) != arity for item in observations):
            raise FoundationError("representation observations must share one arity")
        if len({item.consequence for item in observations}) < 2:
            raise FoundationError("representation invention requires both consequence classes")
