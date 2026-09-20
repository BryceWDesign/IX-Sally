"""CUC-8: explicit cognitive recovery after reliable contradiction."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.cognitive_recovery import CognitiveRecoveryController, RecoveryStage
from ix_sally.cognition.reality_coupling import (
    RealityComparator,
    RealityObservation,
    RealityPrediction,
)
from ix_sally.digest import JsonObject


@dataclass(frozen=True, slots=True)
class CUC8Report:
    entered_hold: bool
    stages: tuple[RecoveryStage, ...]
    recovered_to_normal: bool

    def to_payload(self) -> JsonObject:
        return {
            "entered_hold": self.entered_hold,
            "stages": [stage.value for stage in self.stages],
            "recovered_to_normal": self.recovered_to_normal,
        }


def run_cuc8() -> CUC8Report:
    prediction = RealityPrediction("p", (0.0,), 0.95)
    observation = RealityObservation("o", (1.0,), 0.99)
    delta = RealityComparator().compare(prediction, observation, scale=1.0)
    recovery = CognitiveRecoveryController()
    first = recovery.observe(delta)
    stages = [first.stage]
    for _ in range(4):
        stages.append(recovery.advance().stage)
    return CUC8Report(
        entered_hold=first.stage is RecoveryStage.COMMITMENT_HOLD,
        stages=tuple(stages),
        recovered_to_normal=recovery.stage is RecoveryStage.NORMAL,
    )
