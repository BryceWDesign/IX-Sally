"""Source-independent sensor quorum with explicit disagreement and reliability."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class PerceptionChannelObservation:
    channel_id: str
    values: tuple[float, ...]
    reliability: float
    source_id: str | None = None

    def __post_init__(self) -> None:
        require_text(self.channel_id, field_name="channel_id")
        if self.source_id is not None:
            require_text(self.source_id, field_name="source_id")
        if not self.values or not all(isfinite(value) for value in self.values):
            raise FoundationError("perception channel requires finite values")
        if not isfinite(self.reliability) or not 0.0 <= self.reliability <= 1.0:
            raise FoundationError("perception reliability must be finite and in [0, 1]")

    @property
    def independent_source(self) -> str:
        """Source identity is required for physically related sensor channels."""
        return self.channel_id if self.source_id is None else self.source_id


@dataclass(frozen=True, slots=True)
class PerceptionQuorumReport:
    fused_values: tuple[float, ...]
    reliability: float
    disagreement: float
    quorum_satisfied: bool
    participating_channels: tuple[str, ...]


class PerceptionQuorum:
    """Fuse observations only when independent source identities are unique."""

    def assess(
        self,
        observations: tuple[PerceptionChannelObservation, ...],
        *,
        disagreement_scale: float = 1.0,
        minimum_channels: int = 2,
        reliability_threshold: float = 0.60,
        disagreement_threshold: float = 0.45,
    ) -> PerceptionQuorumReport:
        if not observations:
            raise FoundationError("perception quorum requires observations")
        if not isfinite(disagreement_scale) or disagreement_scale <= 0.0:
            raise FoundationError("disagreement scale must be finite and positive")
        if minimum_channels < 1:
            raise FoundationError("minimum_channels must be positive")
        if (
            not isfinite(reliability_threshold)
            or not 0.0 <= reliability_threshold <= 1.0
            or not isfinite(disagreement_threshold)
            or not 0.0 <= disagreement_threshold <= 1.0
        ):
            raise FoundationError("perception thresholds must be finite and in [0, 1]")
        channels = tuple(item.channel_id for item in observations)
        sources = tuple(item.independent_source for item in observations)
        if len(set(channels)) != len(channels) or len(set(sources)) != len(sources):
            raise FoundationError("perception quorum rejects repeated channel or source identity")
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
        if not all(isfinite(value) for value in fused):
            raise FoundationError("perception fusion produced non-finite values")
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
            participating_channels=channels,
        )
