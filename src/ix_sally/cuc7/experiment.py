"""CUC-7: reality-coupled perceptual agency under an unannounced regime change."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.agency_loop import CognitiveContextSignals, RealityCoupledAgencyLoop
from ix_sally.cognition.assumption_ledger import Assumption, AssumptionLedger, AssumptionStatus
from ix_sally.cognition.counterfactual_goals import EpistemicGoal
from ix_sally.cognition.epistemic_pressure import CognitiveOperation
from ix_sally.cognition.perception_quorum import PerceptionChannelObservation
from ix_sally.cognition.perspectives import PerspectivePrediction
from ix_sally.cognition.reality_coupling import RealityPrediction
from ix_sally.digest import JsonObject


@dataclass(frozen=True, slots=True)
class CUC7Report:
    baseline_operation: CognitiveOperation
    shifted_operation: CognitiveOperation
    contradiction_detected: bool
    generated_goal: EpistemicGoal | None
    assumption_status: AssumptionStatus
    trace_entries: int

    def to_payload(self) -> JsonObject:
        return {
            "baseline_operation": self.baseline_operation.value,
            "shifted_operation": self.shifted_operation.value,
            "contradiction_detected": self.contradiction_detected,
            "generated_goal": None if self.generated_goal is None else self.generated_goal.goal_id,
            "assumption_status": self.assumption_status.value,
            "trace_entries": self.trace_entries,
        }


class HiddenVisualLikeWorld:
    """Small deterministic sensor world whose transform can change without announcement."""

    def __init__(self) -> None:
        self._gain = 1.0

    def shift_regime(self) -> None:
        self._gain = 2.0

    def channels(self, source: tuple[float, float]) -> tuple[PerceptionChannelObservation, ...]:
        truth = tuple(value * self._gain for value in source)
        return (
            PerceptionChannelObservation("sensor-a", truth, 0.98),
            PerceptionChannelObservation("sensor-b", truth, 0.96),
        )


def run_cuc7() -> CUC7Report:
    """Demonstrate reality-triggered cognition after a previously valid rule becomes wrong."""
    assumptions = AssumptionLedger()
    assumptions.register(
        Assumption(
            assumption_id="gain-is-one",
            statement="observed features equal source features",
            confidence=0.95,
            impact_if_wrong=0.90,
        )
    )
    loop = RealityCoupledAgencyLoop(assumptions=assumptions)
    world = HiddenVisualLikeWorld()
    prediction = RealityPrediction(
        prediction_id="predict-source",
        expected_values=(0.4, 0.7),
        confidence=0.95,
        dependency_ids=("gain-is-one",),
    )
    perspectives = (
        PerspectivePrediction("incumbent", (0.4, 0.7), 0.90, ("training-evidence",)),
        PerspectivePrediction("alternative", (0.5, 0.8), 0.55, ("minority-evidence",)),
    )
    baseline = loop.reconcile(
        prediction=prediction,
        channels=world.channels((0.4, 0.7)),
        perspectives=perspectives,
        comparison_scale=1.0,
        external_action_requested=True,
    )
    world.shift_regime()
    shifted = loop.reconcile(
        prediction=prediction,
        channels=world.channels((0.4, 0.7)),
        perspectives=perspectives,
        signals=CognitiveContextSignals(novelty=0.40),
        comparison_scale=0.5,
        external_action_requested=True,
    )
    return CUC7Report(
        baseline_operation=baseline.directive.operation,
        shifted_operation=shifted.directive.operation,
        contradiction_detected=shifted.delta.strong_contradiction,
        generated_goal=shifted.generated_goal,
        assumption_status=assumptions.get("gain-is-one").status,
        trace_entries=len(loop.trace.entries()),
    )
