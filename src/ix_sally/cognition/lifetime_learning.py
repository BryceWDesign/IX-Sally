"""Multi-episode lifelong learning with online meta-strategy selection.

The purpose is to measure whether later IX-Sally can solve structurally similar but
surface-different tasks with less strategy exploration because earlier experience changed
how it learns.  Tasks remain bounded and numeric, but the strategy history is persistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ix_sally.cognition.online_meta import OnlineMetaDecision, OnlineMetaProfile, StrategyExperience, TaskFingerprint
from ix_sally.cognition.representation import RepresentationInventor, RepresentationObservation
from ix_sally.cognition.representation_programs import RepresentationProgramInventor
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class LifetimeChallenge:
    challenge_id: str
    training: tuple[RepresentationObservation, ...]
    holdout: tuple[RepresentationObservation, ...]

    def __post_init__(self) -> None:
        require_text(self.challenge_id, field_name="challenge_id")
        if not self.training or not self.holdout:
            raise FoundationError("lifetime challenge requires training and holdout evidence")


@dataclass(frozen=True, slots=True)
class LifetimeEpisodeResult:
    challenge_id: str
    selected_strategy: str
    validation_accuracy: float
    effective_score: float
    strategies_evaluated: int
    used_prior_meta_experience: bool
    concept_digest: DigestRecord
    decision: OnlineMetaDecision | None

    def to_payload(self) -> JsonObject:
        return {
            "challenge_id": self.challenge_id,
            "selected_strategy": self.selected_strategy,
            "validation_accuracy": self.validation_accuracy,
            "effective_score": self.effective_score,
            "strategies_evaluated": self.strategies_evaluated,
            "used_prior_meta_experience": self.used_prior_meta_experience,
            "concept_digest": {"algorithm": self.concept_digest.algorithm, "value": self.concept_digest.value},
            "decision": None if self.decision is None else {
                "strategy_id": self.decision.strategy_id,
                "expected_score": self.decision.expected_score,
                "evidence_weight": self.decision.evidence_weight,
                "used_cross_domain_evidence": self.decision.used_cross_domain_evidence,
            },
        }


@dataclass(frozen=True, slots=True)
class LifetimeLearningReport:
    profile: OnlineMetaProfile
    episodes: tuple[LifetimeEpisodeResult, ...]

    @property
    def later_learning_is_more_selective(self) -> bool:
        if len(self.episodes) < 2:
            return False
        exploratory = [item for item in self.episodes if item.strategies_evaluated > 1]
        selective = [item for item in self.episodes if item.used_prior_meta_experience and item.strategies_evaluated == 1]
        return bool(exploratory and selective)


class LifetimeLearningEngine:
    """Run representation-learning episodes while retaining evidence about learning strategy."""

    STRATEGIES = ("shallow-relations", "compositional-programs")

    def fingerprint(self, challenge: LifetimeChallenge) -> TaskFingerprint:
        items = challenge.training
        arity = len(items[0].channels)
        class_balance = sum(item.consequence for item in items) / len(items)
        atomic_accuracy = self._best_atomic_accuracy(items)
        # Surface-neutral signals: arity, class balance, and failure of atomic semantics.
        return TaskFingerprint((min(1.0, arity / 6.0), class_balance, 1.0 - atomic_accuracy))

    def run_episode(
        self,
        *,
        profile: OnlineMetaProfile,
        challenge: LifetimeChallenge,
        explore: bool,
    ) -> tuple[OnlineMetaProfile, LifetimeEpisodeResult]:
        fingerprint = self.fingerprint(challenge)
        decision: OnlineMetaDecision | None = None
        if explore or not profile.experiences:
            strategies = self.STRATEGIES
        else:
            decision = profile.choose(fingerprint=fingerprint, candidate_strategies=self.STRATEGIES)
            strategies = (decision.strategy_id,)
        outcomes: list[tuple[float, float, str, DigestRecord]] = []
        updated = profile
        for strategy in strategies:
            accuracy, complexity, digest = self._execute(strategy, challenge)
            effective = max(0.0, accuracy - 0.02 * max(0, complexity - 1))
            outcomes.append((effective, accuracy, strategy, digest))
            updated = updated.record(
                StrategyExperience(
                    strategy_id=strategy,
                    fingerprint=fingerprint,
                    score=effective,
                    samples_used=len(challenge.training),
                )
            )
        effective, accuracy, selected, digest = max(outcomes, key=lambda item: (item[0], item[1], tuple(-ord(ch) for ch in item[2])))
        return updated, LifetimeEpisodeResult(
            challenge_id=challenge.challenge_id,
            selected_strategy=selected,
            validation_accuracy=accuracy,
            effective_score=round(effective, 12),
            strategies_evaluated=len(strategies),
            used_prior_meta_experience=decision is not None,
            concept_digest=digest,
            decision=decision,
        )

    def run_lifetime(
        self,
        *,
        profile: OnlineMetaProfile,
        challenges: Iterable[LifetimeChallenge],
        exploration_episodes: int = 2,
    ) -> LifetimeLearningReport:
        current = profile
        results: list[LifetimeEpisodeResult] = []
        for index, challenge in enumerate(challenges):
            current, result = self.run_episode(
                profile=current,
                challenge=challenge,
                explore=index < exploration_episodes,
            )
            results.append(result)
        return LifetimeLearningReport(current, tuple(results))

    def _execute(self, strategy: str, challenge: LifetimeChallenge) -> tuple[float, int, DigestRecord]:
        if strategy == "shallow-relations":
            try:
                inventor = RepresentationInventor()
                learned = inventor.invent_binary(observations=challenge.training, minimum_improvement=0.05)
                validated = inventor.validate(learned, observations=challenge.holdout)
                accuracy = validated.validation_accuracy or 0.0
                return accuracy, 2, validated.digest()
            except FoundationError:
                accuracy = self._best_atomic_accuracy(challenge.holdout)
                digest = DigestRecord.from_payload({"strategy": strategy, "fallback_accuracy": accuracy})
                return accuracy, 1, digest
        if strategy == "compositional-programs":
            try:
                inventor2 = RepresentationProgramInventor()
                learned2 = inventor2.invent(
                    observations=challenge.training,
                    max_depth=2,
                    minimum_improvement=0.05,
                )
                validated2 = inventor2.validate(learned2, observations=challenge.holdout)
                accuracy2 = validated2.validation_accuracy or 0.0
                return accuracy2, learned2.program.complexity, validated2.digest()
            except FoundationError:
                # A compositional strategy is allowed to fall back to a shallower learned relation.
                try:
                    inventor = RepresentationInventor()
                    learned = inventor.invent_binary(observations=challenge.training, minimum_improvement=0.05)
                    validated = inventor.validate(learned, observations=challenge.holdout)
                    accuracy = validated.validation_accuracy or 0.0
                    return accuracy, 3, validated.digest()
                except FoundationError:
                    accuracy = self._best_atomic_accuracy(challenge.holdout)
                    digest = DigestRecord.from_payload({"strategy": strategy, "fallback_accuracy": accuracy})
                    return accuracy, 3, digest
        raise FoundationError(f"unknown lifetime learning strategy: {strategy}")

    @staticmethod
    def _best_atomic_accuracy(items: tuple[RepresentationObservation, ...]) -> float:
        best = 0.0
        arity = len(items[0].channels)
        for index in range(arity):
            values = sorted(set(item.channels[index] for item in items))
            thresholds = [values[0] - 1.0, values[-1] + 1.0, *values]
            thresholds.extend((a + b) / 2.0 for a, b in zip(values, values[1:]))
            for threshold in thresholds:
                for polarity in (-1, 1):
                    correct = sum(
                        (polarity * item.channels[index] >= polarity * threshold) is item.consequence
                        for item in items
                    )
                    best = max(best, correct / len(items))
        return best
