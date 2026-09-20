"""Persistent online meta-learning across task surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from ix_sally.digest import JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class TaskFingerprint:
    """Domain-neutral measured properties of a learning problem."""

    dimensions: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.dimensions:
            raise FoundationError("task fingerprint requires dimensions")
        if any(not 0.0 <= value <= 1.0 for value in self.dimensions):
            raise FoundationError("task fingerprint values must be between zero and one")

    def distance(self, other: "TaskFingerprint") -> float:
        if len(self.dimensions) != len(other.dimensions):
            raise FoundationError("task fingerprints must have equal arity")
        return sqrt(sum((a - b) ** 2 for a, b in zip(self.dimensions, other.dimensions, strict=True)))

    def to_payload(self) -> JsonArray:
        return list(self.dimensions)


@dataclass(frozen=True, slots=True)
class StrategyExperience:
    strategy_id: str
    fingerprint: TaskFingerprint
    score: float
    samples_used: int

    def __post_init__(self) -> None:
        require_text(self.strategy_id, field_name="strategy_id")
        if not 0.0 <= self.score <= 1.0 or self.samples_used < 1:
            raise FoundationError("strategy experience metrics are invalid")

    def to_payload(self) -> JsonObject:
        return {
            "strategy_id": self.strategy_id,
            "fingerprint": self.fingerprint.to_payload(),
            "score": self.score,
            "samples_used": self.samples_used,
        }


@dataclass(frozen=True, slots=True)
class OnlineMetaDecision:
    strategy_id: str
    expected_score: float
    evidence_weight: float
    used_cross_domain_evidence: bool


@dataclass(frozen=True, slots=True)
class OnlineMetaProfile:
    """Persistent evidence about which learning methods work for which problem structures."""

    experiences: tuple[StrategyExperience, ...] = ()

    def record(self, experience: StrategyExperience) -> "OnlineMetaProfile":
        if self.experiences and len(experience.fingerprint.dimensions) != len(self.experiences[0].fingerprint.dimensions):
            raise FoundationError("online meta profile fingerprint arity mismatch")
        return OnlineMetaProfile((*self.experiences, experience))

    def choose(
        self,
        *,
        fingerprint: TaskFingerprint,
        candidate_strategies: Iterable[str],
        exploration_prior: float = 0.50,
    ) -> OnlineMetaDecision:
        candidates = tuple(sorted({require_text(item, field_name="strategy_id") for item in candidate_strategies}))
        if not candidates:
            raise FoundationError("online meta-learning requires candidate strategies")
        scored: list[tuple[float, float, str, bool]] = []
        for strategy in candidates:
            relevant = [item for item in self.experiences if item.strategy_id == strategy]
            if not relevant:
                scored.append((exploration_prior, 0.0, strategy, False))
                continue
            weighted_score = 0.0
            weight_total = 0.0
            cross_domain = False
            for item in relevant:
                distance = fingerprint.distance(item.fingerprint)
                weight = 1.0 / (1.0 + 4.0 * distance)
                # Prefer strategies that reached strong scores using less evidence.
                efficiency = item.score / (1.0 + item.samples_used / 20.0)
                weighted_score += weight * (0.8 * item.score + 0.2 * efficiency)
                weight_total += weight
                cross_domain = cross_domain or distance > 0.05
            expected = weighted_score / weight_total
            scored.append((expected, weight_total, strategy, cross_domain))
        expected, weight, strategy, cross_domain = max(scored, key=lambda item: (item[0], item[1], tuple(-ord(ch) for ch in item[2])))
        return OnlineMetaDecision(
            strategy_id=strategy,
            expected_score=round(expected, 12),
            evidence_weight=round(weight, 12),
            used_cross_domain_evidence=cross_domain,
        )

    def to_payload(self) -> JsonObject:
        return {"experiences": [item.to_payload() for item in self.experiences]}
