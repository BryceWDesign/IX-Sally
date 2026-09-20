"""Independent perception channels and disagreement-aware quorum assessment."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class PerceptionChannelObservation:
    channel_id: str
    values: tuple[float, ...]
    reliability: float

    def __post_init__(self) -> None:
        require_text(self.channel_id, field_name="channel_id")
        if not self.values:
            raise FoundationError("perception channel requires values")
        if not 0.0 <= self.reliability <= 1.0:
            raise FoundationError("perception reliability must be between zero and one")


@dataclass(frozen=True, slots=True)
class PerceptionQuorumReport:
    fused_values: tuple[float, ...]
    reliability: float
    disagreement: float
    quorum_satisfied: bool
    participating_channels: tuple[str, ...]


class PerceptionQuorum:
    """Fuse independent observations while preserving disagreement as evidence."""

    def assess(
        self,
        observations: tuple[PerceptionChannelObservation, ...],
        *,
        disagreement_scale: float = 1.0,
        minimum_channels: int = 2,
        reliability_threshold: float = 0.60,
        disagreement_threshold: float = 0.45,
    ) -> PerceptionQuorumReport:
        if len(observations) < 1:
            raise FoundationError("perception quorum requires observations")
        if disagreement_scale <= 0.0:
            raise FoundationError("disagreement scale must be positive")
        dimension = len(observations[0].values)
        if any(len(item.values) != dimension for item in observations):
            raise FoundationError("perception channel dimensions must match")
        weights = tuple(max(item.reliability, 1e-12) for item in observations)
        total_weight = sum(weights)
        fused = tuple(
            sum(
                item.values[index] * weight
                for item, weight in zip(observations, weights, strict=True)
            )
            / total_weight
            for index in range(dimension)
        )
        rms_values: list[float] = []
        for item in observations:
            residual = tuple(value - fused[index] for index, value in enumerate(item.values))
            rms_values.append(sqrt(sum(value * value for value in residual) / dimension))
        disagreement = min(1.0, (sum(rms_values) / len(rms_values)) / disagreement_scale)
        reliability = sum(item.reliability for item in observations) / len(observations)
        satisfied = (
            len(observations) >= minimum_channels
            and reliability >= reliability_threshold
            and disagreement <= disagreement_threshold
        )
        return PerceptionQuorumReport(
            fused_values=tuple(round(value, 12) for value in fused),
            reliability=round(reliability, 12),
            disagreement=round(disagreement, 12),
            quorum_satisfied=satisfied,
            participating_channels=tuple(item.channel_id for item in observations),
        )
