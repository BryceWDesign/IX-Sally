"""Unknown-unknown detection from structured high-confidence prediction residuals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class PredictionResidual:
    prediction_id: str
    confidence: float
    predicted: bool
    actual: bool
    context_signature: tuple[int, ...]

    def __post_init__(self) -> None:
        require_text(self.prediction_id, field_name="prediction_id")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("residual confidence must be between zero and one")
        if not self.context_signature:
            raise FoundationError("residual requires a context signature")


@dataclass(frozen=True, slots=True)
class UnknownUnknownSignal:
    detected: bool
    high_confidence_error_rate: float
    dominant_context: tuple[int, ...] | None
    dominant_context_errors: int
    reason: str


class UnknownUnknownDetector:
    """Flag systematic failures that ordinary uncertainty estimates did not anticipate."""

    def detect(
        self,
        residuals: Iterable[PredictionResidual],
        *,
        confidence_threshold: float = 0.80,
        error_rate_threshold: float = 0.30,
        cluster_minimum: int = 2,
    ) -> UnknownUnknownSignal:
        items = tuple(residuals)
        if not items:
            raise FoundationError("unknown-unknown detection requires residuals")
        high = [item for item in items if item.confidence >= confidence_threshold]
        errors = [item for item in high if item.predicted != item.actual]
        error_rate = len(errors) / len(high) if high else 0.0
        counts: dict[tuple[int, ...], int] = {}
        for item in errors:
            counts[item.context_signature] = counts.get(item.context_signature, 0) + 1
        dominant = max(counts, key=lambda key: (counts[key], key)) if counts else None
        count = counts.get(dominant, 0) if dominant is not None else 0
        detected = error_rate >= error_rate_threshold and count >= cluster_minimum
        return UnknownUnknownSignal(
            detected=detected,
            high_confidence_error_rate=round(error_rate, 12),
            dominant_context=dominant,
            dominant_context_errors=count,
            reason=(
                "High-confidence errors cluster in a repeated context, suggesting a missing variable or hypothesis."
                if detected
                else "Residuals do not yet justify inventing an unrepresented cause."
            ),
        )
