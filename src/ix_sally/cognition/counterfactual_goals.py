"""Generate endogenous information-seeking goals from blocked conditions and failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.foundation import FoundationError, require_text


class GoalSource(StrEnum):
    PREDICTION_FAILURE = "prediction-failure"
    MISSING_EVIDENCE = "missing-evidence"
    MODEL_DISAGREEMENT = "model-disagreement"
    STALE_ASSUMPTION = "stale-assumption"
    CONTRADICTION = "contradiction"
    FOCUS_OMISSION = "focus-omission"
    AUTHORITY_DENIAL = "authority-denial"
    REPRESENTATION_FAILURE = "representation-failure"
    UNKNOWN_UNKNOWN = "unknown-unknown"


@dataclass(frozen=True, slots=True)
class BlockedCondition:
    condition_id: str
    description: str
    source: GoalSource
    severity: float

    def __post_init__(self) -> None:
        require_text(self.condition_id, field_name="condition_id")
        require_text(self.description, field_name="description")
        if not 0.0 <= self.severity <= 1.0:
            raise FoundationError("blocked-condition severity must be between zero and one")


@dataclass(frozen=True, slots=True)
class EpistemicGoal:
    goal_id: str
    description: str
    source_condition_id: str
    priority: float
    success_condition: str


class CounterfactualGoalGenerator:
    """Turn 'cannot justify X' into 'what evidence would make X decidable?' goals."""

    def generate(self, blocked: BlockedCondition) -> EpistemicGoal:
        description = f"Resolve condition: {blocked.description}"
        success = f"Obtain independent evidence that resolves {blocked.condition_id}"
        return EpistemicGoal(
            goal_id=f"epistemic:{blocked.source.value}:{blocked.condition_id}",
            description=description,
            source_condition_id=blocked.condition_id,
            priority=round(min(1.0, 0.35 + 0.65 * blocked.severity), 12),
            success_condition=success,
        )
