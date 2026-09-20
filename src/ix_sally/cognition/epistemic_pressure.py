"""Multidimensional epistemic pressure and choice-over-cognition policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_sally.foundation import FoundationError


class CognitiveOperation(StrEnum):
    """Kinds of cognitive work Sally may choose before proposing an external action."""

    OBSERVE = "observe"
    DISCRIMINATE = "discriminate"
    GENERATE_HYPOTHESIS = "generate-hypothesis"
    INVENT_REPRESENTATION = "invent-representation"
    REVALIDATE = "revalidate"
    RECONSIDER_GOAL = "reconsider-goal"
    INSPECT_ASSUMPTIONS = "inspect-assumptions"
    SHADOW_STRATEGY = "shadow-strategy"
    RECOVER = "recover"
    ACT = "act"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class EpistemicPressure:
    """Keep distinct reasons for uncertainty instead of collapsing them to one score."""

    prediction_error: float = 0.0
    perceptual_uncertainty: float = 0.0
    model_disagreement: float = 0.0
    unresolved_contradiction: float = 0.0
    novelty: float = 0.0
    assumption_risk: float = 0.0
    staleness: float = 0.0
    focus_omission: float = 0.0
    goal_drift: float = 0.0
    representation_failure: float = 0.0
    causal_failure: float = 0.0
    evidence_gap: float = 0.0
    revalidation_need: float = 0.0

    def __post_init__(self) -> None:
        for name, value in self.as_pairs():
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} pressure must be between zero and one")

    def as_pairs(self) -> tuple[tuple[str, float], ...]:
        """Return stable pressure dimensions for traceability and deterministic policy."""
        return (
            ("prediction_error", self.prediction_error),
            ("perceptual_uncertainty", self.perceptual_uncertainty),
            ("model_disagreement", self.model_disagreement),
            ("unresolved_contradiction", self.unresolved_contradiction),
            ("novelty", self.novelty),
            ("assumption_risk", self.assumption_risk),
            ("staleness", self.staleness),
            ("focus_omission", self.focus_omission),
            ("goal_drift", self.goal_drift),
            ("representation_failure", self.representation_failure),
            ("causal_failure", self.causal_failure),
            ("evidence_gap", self.evidence_gap),
            ("revalidation_need", self.revalidation_need),
        )

    def dominant(self) -> tuple[str, float]:
        """Return the strongest reason cognition should continue.

        Exact ties use a safety-oriented deterministic priority so a strong
        contradiction cannot be masked by the prediction error that caused it.
        """
        priority = {
            "unresolved_contradiction": 13,
            "perceptual_uncertainty": 12,
            "model_disagreement": 11,
            "representation_failure": 10,
            "causal_failure": 9,
            "prediction_error": 8,
            "revalidation_need": 7,
            "assumption_risk": 6,
            "evidence_gap": 5,
            "focus_omission": 4,
            "staleness": 3,
            "goal_drift": 2,
            "novelty": 1,
        }
        return max(self.as_pairs(), key=lambda item: (item[1], priority[item[0]]))

    @property
    def maximum(self) -> float:
        """Return only the maximum intensity, never a lossy aggregate."""
        return self.dominant()[1]


@dataclass(frozen=True, slots=True)
class CognitiveDirective:
    """One explainable choice of what kind of thinking should happen next."""

    operation: CognitiveOperation
    cause: str
    pressure: float
    external_action_permitted: bool


class CognitiveOperationSelector:
    """Choose cognition from the *type* of ignorance rather than one confidence scalar."""

    _MAPPING: ClassVar[dict[str, CognitiveOperation]] = {
        "prediction_error": CognitiveOperation.INSPECT_ASSUMPTIONS,
        "perceptual_uncertainty": CognitiveOperation.OBSERVE,
        "model_disagreement": CognitiveOperation.DISCRIMINATE,
        "unresolved_contradiction": CognitiveOperation.RECOVER,
        "novelty": CognitiveOperation.GENERATE_HYPOTHESIS,
        "assumption_risk": CognitiveOperation.INSPECT_ASSUMPTIONS,
        "staleness": CognitiveOperation.REVALIDATE,
        "focus_omission": CognitiveOperation.OBSERVE,
        "goal_drift": CognitiveOperation.RECONSIDER_GOAL,
        "representation_failure": CognitiveOperation.INVENT_REPRESENTATION,
        "causal_failure": CognitiveOperation.GENERATE_HYPOTHESIS,
        "evidence_gap": CognitiveOperation.OBSERVE,
        "revalidation_need": CognitiveOperation.REVALIDATE,
    }

    def choose(
        self,
        pressure: EpistemicPressure,
        *,
        external_action_requested: bool = False,
        act_threshold: float = 0.20,
    ) -> CognitiveDirective:
        """Choose an epistemically appropriate operation.

        Low epistemic pressure permits an *internal recommendation* to act. Actual
        consequential execution remains outside this module and under Sally governance.
        """
        if not 0.0 <= act_threshold <= 1.0:
            raise FoundationError("act threshold must be between zero and one")
        cause, value = pressure.dominant()
        if value < act_threshold:
            operation = (
                CognitiveOperation.ACT if external_action_requested else CognitiveOperation.HOLD
            )
            return CognitiveDirective(
                operation=operation,
                cause="epistemic-pressure-low",
                pressure=round(value, 12),
                external_action_permitted=external_action_requested,
            )
        operation = self._MAPPING[cause]
        return CognitiveDirective(
            operation=operation,
            cause=cause,
            pressure=round(value, 12),
            external_action_permitted=False,
        )
