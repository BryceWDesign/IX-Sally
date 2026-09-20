"""Reality-coupled cognition primitives.

This module keeps independently observed reality separate from Sally's predictions.
It produces typed deltas rather than allowing beliefs to overwrite observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class RealityObservation:
    """One independently acquired observation of the environment."""

    observation_id: str
    values: tuple[float, ...]
    reliability: float
    context: str = "default"

    def __post_init__(self) -> None:
        require_text(self.observation_id, field_name="observation_id")
        require_text(self.context, field_name="context")
        if not self.values:
            raise FoundationError("reality observation requires at least one value")
        if not 0.0 <= self.reliability <= 1.0:
            raise FoundationError("observation reliability must be between zero and one")


@dataclass(frozen=True, slots=True)
class RealityPrediction:
    """One falsifiable prediction issued before an observation is consumed."""

    prediction_id: str
    expected_values: tuple[float, ...]
    confidence: float
    dependency_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.prediction_id, field_name="prediction_id")
        if not self.expected_values:
            raise FoundationError("reality prediction requires expected values")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("prediction confidence must be between zero and one")
        if len(self.dependency_ids) != len(set(self.dependency_ids)):
            raise FoundationError("prediction dependency identifiers must be unique")


@dataclass(frozen=True, slots=True)
class RealityDelta:
    """Immutable difference between a prediction and independently observed reality."""

    prediction_id: str
    observation_id: str
    residuals: tuple[float, ...]
    normalized_error: float
    surprise: float
    observation_reliability: float
    prediction_confidence: float
    dependency_ids: tuple[str, ...]

    @property
    def strong_contradiction(self) -> bool:
        """Return whether reliable evidence strongly contradicts a confident prediction."""
        return (
            self.normalized_error >= 0.55
            and self.observation_reliability >= 0.75
            and self.prediction_confidence >= 0.75
        )


class RealityComparator:
    """Compare predictions with observations without mutating either source."""

    def compare(
        self,
        prediction: RealityPrediction,
        observation: RealityObservation,
        *,
        scale: float = 1.0,
    ) -> RealityDelta:
        """Return a bounded residual and surprise estimate.

        ``scale`` represents the domain's meaningful unit of discrepancy. Errors at or
        above that scale saturate normalized error at 1.0.
        """
        if scale <= 0.0:
            raise FoundationError("reality comparison scale must be positive")
        if len(prediction.expected_values) != len(observation.values):
            raise FoundationError("prediction and observation dimensions must match")
        residuals = tuple(
            actual - expected
            for actual, expected in zip(
                observation.values,
                prediction.expected_values,
                strict=True,
            )
        )
        rms = sqrt(sum(value * value for value in residuals) / len(residuals))
        normalized = min(1.0, rms / scale)
        surprise = normalized * prediction.confidence * observation.reliability
        return RealityDelta(
            prediction_id=prediction.prediction_id,
            observation_id=observation.observation_id,
            residuals=tuple(round(value, 12) for value in residuals),
            normalized_error=round(normalized, 12),
            surprise=round(surprise, 12),
            observation_reliability=observation.reliability,
            prediction_confidence=prediction.confidence,
            dependency_ids=prediction.dependency_ids,
        )
