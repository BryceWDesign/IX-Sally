"""Minimal raw numeric signal grounding for bounded experiments.

This is intentionally not a vision/audio foundation model. It lets Sally derive events and
features from unlabelled numeric streams instead of requiring every input to arrive as a
clean symbolic fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class RawSignal:
    signal_id: str
    samples: tuple[float, ...]

    def __post_init__(self) -> None:
        require_text(self.signal_id, field_name="signal_id")
        if len(self.samples) < 3:
            raise FoundationError("raw signal requires at least three samples")


@dataclass(frozen=True, slots=True)
class GroundedSignal:
    signal_id: str
    mean: float
    variance: float
    slope: float
    change_points: tuple[int, ...]
    normalized: tuple[float, ...]


class RawSignalGrounder:
    """Derive continuous features and unsupervised change events from raw numeric samples."""

    def ground(self, signal: RawSignal, *, change_z: float = 1.5) -> GroundedSignal:
        samples = signal.samples
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / len(samples)
        std = sqrt(variance)
        normalized = tuple((value - mean) / std if std > 0.0 else 0.0 for value in samples)
        deltas = tuple(samples[index] - samples[index - 1] for index in range(1, len(samples)))
        delta_mean = sum(deltas) / len(deltas)
        delta_var = sum((value - delta_mean) ** 2 for value in deltas) / len(deltas)
        delta_std = sqrt(delta_var)
        changes = tuple(
            index + 1
            for index, value in enumerate(deltas)
            if delta_std > 0.0 and abs(value - delta_mean) / delta_std >= change_z
        )
        slope = (samples[-1] - samples[0]) / (len(samples) - 1)
        return GroundedSignal(
            signal_id=signal.signal_id,
            mean=round(mean, 12),
            variance=round(variance, 12),
            slope=round(slope, 12),
            change_points=changes,
            normalized=tuple(round(value, 12) for value in normalized),
        )
