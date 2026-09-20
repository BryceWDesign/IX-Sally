"""Competing perspectives with explicit dissent preservation."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class PerspectivePrediction:
    perspective_id: str
    values: tuple[float, ...]
    confidence: float
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.perspective_id, field_name="perspective_id")
        if not self.values:
            raise FoundationError("perspective prediction requires values")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("perspective confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class PerspectiveReport:
    disagreement: float
    majority_id: str
    dissent_ids: tuple[str, ...]
    preserved_evidence_ids: tuple[str, ...]


class PerspectiveEnsemble:
    """Measure disagreement without deleting minority hypotheses."""

    def assess(
        self,
        perspectives: tuple[PerspectivePrediction, ...],
        *,
        scale: float = 1.0,
    ) -> PerspectiveReport:
        if not perspectives:
            raise FoundationError("perspective ensemble requires predictions")
        if scale <= 0.0:
            raise FoundationError("perspective disagreement scale must be positive")
        dimension = len(perspectives[0].values)
        if any(len(item.values) != dimension for item in perspectives):
            raise FoundationError("perspective dimensions must match")
        weights = tuple(max(item.confidence, 1e-12) for item in perspectives)
        total = sum(weights)
        center = tuple(
            sum(
                item.values[index] * weight
                for item, weight in zip(perspectives, weights, strict=True)
            )
            / total
            for index in range(dimension)
        )
        distances = {
            item.perspective_id: (
                sum((item.values[index] - center[index]) ** 2 for index in range(dimension))
                / dimension
            )
            ** 0.5
            for item in perspectives
        }
        disagreement = min(1.0, sum(distances.values()) / len(distances) / scale)
        majority = max(perspectives, key=lambda item: (item.confidence, item.perspective_id))
        dissent = tuple(
            sorted(
                item.perspective_id
                for item in perspectives
                if item.perspective_id != majority.perspective_id
                and distances[item.perspective_id] >= scale * 0.25
            )
        )
        preserved = tuple(
            dict.fromkeys(
                evidence_id
                for item in perspectives
                if item.perspective_id in dissent
                for evidence_id in item.evidence_ids
            )
        )
        return PerspectiveReport(
            disagreement=round(disagreement, 12),
            majority_id=majority.perspective_id,
            dissent_ids=dissent,
            preserved_evidence_ids=preserved,
        )
