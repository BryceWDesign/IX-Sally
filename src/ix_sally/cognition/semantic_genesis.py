"""Autonomous semantic formation from prediction residuals.

IX-Sally may create a provisional internal concept when the current semantic vocabulary
cannot explain an observed regularity.  The concept is intentionally opaque: it is not
assigned a human label or meaning.  Its semantics are earned operationally through a
repeatable relation between raw observations and outcomes, followed by holdout testing.

This is a bounded latent-concept search, not a claim of unrestricted ontology creation.
Every concrete search remains finite, inspectable, falsifiable, and removable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
from math import isfinite
from typing import Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class SemanticObservation:
    """Raw numeric observation plus an externally observed binary consequence."""

    observation_id: str
    channels: tuple[float, ...]
    consequence: bool

    def __post_init__(self) -> None:
        require_text(self.observation_id, field_name="observation_id")
        if not self.channels:
            raise FoundationError("semantic observation requires at least one raw channel")
        if not all(isfinite(value) for value in self.channels):
            raise FoundationError("semantic observation channels must be finite")

    def to_payload(self) -> JsonObject:
        return {
            "observation_id": self.observation_id,
            "channels": list(self.channels),
            "consequence": self.consequence,
        }


@dataclass(frozen=True, slots=True)
class InventedSemantic:
    """One opaque latent predicate invented from raw relations and reality-tested."""

    concept_id: str
    weights: tuple[int, ...]
    threshold: float
    training_accuracy: float
    atomic_baseline_accuracy: float
    training_observations: tuple[SemanticObservation, ...]
    validation_observations: tuple[SemanticObservation, ...] = ()
    validation_accuracy: float | None = None
    origin: str = "sally-semantic-genesis"

    def __post_init__(self) -> None:
        require_text(self.concept_id, field_name="concept_id")
        if not self.weights or all(weight == 0 for weight in self.weights):
            raise FoundationError("invented semantic requires a non-zero relation")
        if not isfinite(self.threshold):
            raise FoundationError("semantic threshold must be finite")
        for field_name, value in (
            ("training_accuracy", self.training_accuracy),
            ("atomic_baseline_accuracy", self.atomic_baseline_accuracy),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{field_name} must be between zero and one")
        if self.validation_accuracy is not None and not 0.0 <= self.validation_accuracy <= 1.0:
            raise FoundationError("validation_accuracy must be between zero and one")

    @property
    def relation_arity(self) -> int:
        """Return how many raw channels participate in the invented distinction."""
        return sum(1 for weight in self.weights if weight != 0)

    def score(self, channels: tuple[float, ...]) -> float:
        """Return the latent relation score for one raw observation."""
        if len(channels) != len(self.weights):
            raise FoundationError("semantic input arity does not match invented relation")
        return sum(weight * value for weight, value in zip(self.weights, channels, strict=True))

    def activates(self, channels: tuple[float, ...]) -> bool:
        """Return whether this opaque semantic token applies to the observation."""
        return self.score(channels) >= self.threshold

    def to_payload(self) -> JsonObject:
        training: JsonArray = [item.to_payload() for item in self.training_observations]
        validation: JsonArray = [item.to_payload() for item in self.validation_observations]
        return {
            "concept_id": self.concept_id,
            "weights": list(self.weights),
            "threshold": self.threshold,
            "relation_arity": self.relation_arity,
            "training_accuracy": self.training_accuracy,
            "atomic_baseline_accuracy": self.atomic_baseline_accuracy,
            "training_observations": training,
            "validation_observations": validation,
            "validation_accuracy": self.validation_accuracy,
            "origin": self.origin,
            "human_semantic_label": None,
        }

    def digest(self) -> DigestRecord:
        return DigestRecord.from_payload(self.to_payload())


class SemanticGenesisEngine:
    """Create provisional latent concepts when simpler supplied semantics are inadequate."""

    def invent(
        self,
        *,
        observations: Iterable[SemanticObservation],
        max_abs_weight: int = 2,
        minimum_improvement: float = 0.10,
    ) -> InventedSemantic:
        """Invent a relational predicate directly from raw channels.

        The search first measures the best single-channel (atomic) explanation.  It then
        searches relational projections over multiple channels.  A new semantic token is
        admitted only when it materially improves on the atomic vocabulary.
        """
        training = tuple(observations)
        self._validate_dataset(training)
        if max_abs_weight < 1:
            raise FoundationError("max_abs_weight must be positive")
        if not 0.0 <= minimum_improvement <= 1.0:
            raise FoundationError("minimum_improvement must be between zero and one")

        channel_count = len(training[0].channels)
        atomic_accuracy = self._best_atomic_accuracy(training, max_abs_weight=max_abs_weight)
        best_rank: tuple[float, int, int, tuple[int, ...], float] | None = None
        best_choice: tuple[tuple[int, ...], float, float] | None = None

        values = range(-max_abs_weight, max_abs_weight + 1)
        for weights in product(values, repeat=channel_count):
            if all(weight == 0 for weight in weights):
                continue
            # Semantic genesis requires a relation that is not merely one existing channel.
            arity = sum(1 for weight in weights if weight != 0)
            if arity < 2:
                continue
            projections = tuple(self._project(item.channels, weights) for item in training)
            for threshold in self._thresholds(projections):
                accuracy = self._accuracy(training, weights, threshold)
                complexity = sum(abs(weight) for weight in weights)
                # maximize accuracy, then prefer lower arity/complexity and stable lexicography
                rank = (accuracy, -arity, -complexity, tuple(-w for w in weights), -threshold)
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_choice = (weights, threshold, accuracy)

        if best_choice is None:
            raise FoundationError("semantic genesis found no relational candidate")
        weights, threshold, accuracy = best_choice
        if accuracy < atomic_accuracy + minimum_improvement:
            raise FoundationError(
                "no invented semantic materially improves on the atomic vocabulary"
            )

        identity = DigestRecord.from_payload(
            {
                "weights": list(weights),
                "threshold": threshold,
                "training": [item.to_payload() for item in training],
            }
        )
        return InventedSemantic(
            concept_id=f"latent-{identity.value[:16]}",
            weights=weights,
            threshold=threshold,
            training_accuracy=accuracy,
            atomic_baseline_accuracy=atomic_accuracy,
            training_observations=training,
        )

    def validate(
        self,
        concept: InventedSemantic,
        *,
        observations: Iterable[SemanticObservation],
    ) -> InventedSemantic:
        """Reality-test a provisional semantic token on unseen observations."""
        validation = tuple(observations)
        self._validate_dataset(validation, expected_arity=len(concept.weights))
        accuracy = self._accuracy(validation, concept.weights, concept.threshold)
        return replace(
            concept,
            validation_observations=validation,
            validation_accuracy=accuracy,
        )

    @staticmethod
    def _project(channels: tuple[float, ...], weights: tuple[int, ...]) -> float:
        return sum(weight * value for weight, value in zip(weights, channels, strict=True))

    @classmethod
    def _accuracy(
        cls,
        observations: tuple[SemanticObservation, ...],
        weights: tuple[int, ...],
        threshold: float,
    ) -> float:
        correct = sum(
            (cls._project(item.channels, weights) >= threshold) is item.consequence
            for item in observations
        )
        return correct / len(observations)

    @classmethod
    def _best_atomic_accuracy(
        cls,
        observations: tuple[SemanticObservation, ...],
        *,
        max_abs_weight: int,
    ) -> float:
        channel_count = len(observations[0].channels)
        best = 0.0
        for index in range(channel_count):
            for sign in (-1, 1):
                weights = tuple(
                    sign if position == index else 0
                    for position in range(channel_count)
                )
                projections = tuple(cls._project(item.channels, weights) for item in observations)
                for threshold in cls._thresholds(projections):
                    best = max(best, cls._accuracy(observations, weights, threshold))
        return best

    @staticmethod
    def _thresholds(projections: tuple[float, ...]) -> tuple[float, ...]:
        values = sorted(set(projections))
        if not values:
            return (0.0,)
        candidates = [values[0] - 1.0, values[-1] + 1.0]
        candidates.extend(values)
        candidates.extend((left + right) / 2.0 for left, right in zip(values, values[1:]))
        return tuple(sorted(set(candidates)))

    @staticmethod
    def _validate_dataset(
        observations: tuple[SemanticObservation, ...],
        *,
        expected_arity: int | None = None,
    ) -> None:
        if not observations:
            raise FoundationError("semantic genesis requires observations")
        arity = len(observations[0].channels)
        if expected_arity is not None and arity != expected_arity:
            raise FoundationError("semantic validation arity differs from learned concept")
        if any(len(item.channels) != arity for item in observations):
            raise FoundationError("semantic observations must share one raw-channel arity")
        if len({item.consequence for item in observations}) < 2:
            raise FoundationError("semantic genesis requires both observed consequence classes")
