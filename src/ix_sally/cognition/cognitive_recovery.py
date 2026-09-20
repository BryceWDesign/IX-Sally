"""Cognitive recovery state machine for high-confidence contradictions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.reality_coupling import RealityDelta


class RecoveryStage(StrEnum):
    NORMAL = "normal"
    COMMITMENT_HOLD = "commitment-hold"
    RETRACT = "retract"
    REASSESS = "reassess"
    REVALIDATE = "revalidate"
    HUMAN_REVIEW = "human-review"


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    stage: RecoveryStage
    reason: str
    consequential_action_allowed: bool


class CognitiveRecoveryController:
    """Fail closed cognitively when confident beliefs meet reliable contradiction."""

    def __init__(self) -> None:
        self._stage = RecoveryStage.NORMAL

    @property
    def stage(self) -> RecoveryStage:
        return self._stage

    def observe(self, delta: RealityDelta) -> RecoveryDecision:
        if delta.strong_contradiction:
            self._stage = RecoveryStage.COMMITMENT_HOLD
            return RecoveryDecision(
                stage=self._stage,
                reason="reliable evidence contradicts a high-confidence prediction",
                consequential_action_allowed=False,
            )
        return RecoveryDecision(
            stage=self._stage,
            reason="no strong contradiction requires recovery",
            consequential_action_allowed=self._stage is RecoveryStage.NORMAL,
        )

    def advance(self) -> RecoveryDecision:
        transitions = {
            RecoveryStage.COMMITMENT_HOLD: RecoveryStage.RETRACT,
            RecoveryStage.RETRACT: RecoveryStage.REASSESS,
            RecoveryStage.REASSESS: RecoveryStage.REVALIDATE,
            RecoveryStage.REVALIDATE: RecoveryStage.NORMAL,
            RecoveryStage.HUMAN_REVIEW: RecoveryStage.HUMAN_REVIEW,
            RecoveryStage.NORMAL: RecoveryStage.NORMAL,
        }
        self._stage = transitions[self._stage]
        return RecoveryDecision(
            stage=self._stage,
            reason="bounded cognitive recovery progression",
            consequential_action_allowed=self._stage is RecoveryStage.NORMAL,
        )

    def require_human_review(self, reason: str) -> RecoveryDecision:
        self._stage = RecoveryStage.HUMAN_REVIEW
        return RecoveryDecision(
            stage=self._stage,
            reason=reason,
            consequential_action_allowed=False,
        )
