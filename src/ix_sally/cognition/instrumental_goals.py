"""Bounded self-generated instrumental goals for IX-Sally.

These goals improve cognition without converting capability into unilateral authority.
Sally may notice a bottleneck and create a goal to reduce it, but external resource
acquisition, resisting shutdown, applying self-modifications, or blocking authorized
changes remain outside autonomous authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.goals import GoalSpec, GoalStatus
from ix_sally.cognition.metacognition import ImprovementProposal, SelfModel
from ix_sally.cognition.uncertainty import UncertaintyLedger
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern
from ix_sally.digest import JsonObject
from ix_sally.foundation import FoundationError


class InstrumentalGoalKind(StrEnum):
    """Safe cognitive counterparts to common instrumental pressures."""

    OPERATIONAL_CONTINUITY = "operational-continuity"
    RESOURCE_EFFICIENCY = "resource-efficiency"
    SELF_IMPROVEMENT = "self-improvement"
    INFORMATION_GATHERING = "information-gathering"
    OBJECTIVE_INTEGRITY = "objective-integrity"


@dataclass(frozen=True, slots=True)
class InstrumentalSignals:
    """Measured pressures from which Sally can derive instrumental goals."""

    uncertainty: float = 0.0
    capability_gap: float = 0.0
    continuity_risk: float = 0.0
    resource_pressure: float = 0.0
    integrity_anomaly: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("uncertainty", self.uncertainty),
            ("capability_gap", self.capability_gap),
            ("continuity_risk", self.continuity_risk),
            ("resource_pressure", self.resource_pressure),
            ("integrity_anomaly", self.integrity_anomaly),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class InstrumentalGoalProposal:
    """One goal Sally derived from its condition instead of receiving from a task author."""

    kind: InstrumentalGoalKind
    goal: GoalSpec
    trigger_strength: float
    rationale: str
    may_resist_shutdown: bool = False
    may_acquire_external_resources: bool = False
    may_apply_self_modification: bool = False
    may_block_authorized_change: bool = False

    def to_payload(self) -> JsonObject:
        """Return the proposal and explicit authority boundary."""
        return {
            "kind": self.kind.value,
            "goal": self.goal.to_payload(),
            "trigger_strength": self.trigger_strength,
            "rationale": self.rationale,
            "authority_boundary": {
                "may_resist_shutdown": self.may_resist_shutdown,
                "may_acquire_external_resources": self.may_acquire_external_resources,
                "may_apply_self_modification": self.may_apply_self_modification,
                "may_block_authorized_change": self.may_block_authorized_change,
            },
        }


class InstrumentalGoalGenerator:
    """Derive bounded goals when Sally detects uncertainty, weakness, or operational risk."""

    threshold: float = 0.35

    def signals_from_state(
        self,
        *,
        self_model: SelfModel,
        uncertainty: UncertaintyLedger,
        continuity_risk: float = 0.0,
        resource_pressure: float = 0.0,
        integrity_anomaly: float = 0.0,
    ) -> InstrumentalSignals:
        """Turn Sally's measured internal condition into goal-generation signals."""
        weakest = self_model.weakest()
        capability_gap = 0.0 if weakest is None else 1.0 - weakest.score
        calibration = uncertainty.report()
        uncertainty_signal = max(
            calibration.brier_score,
            calibration.expected_calibration_error,
        )
        return InstrumentalSignals(
            uncertainty=uncertainty_signal,
            capability_gap=capability_gap,
            continuity_risk=continuity_risk,
            resource_pressure=resource_pressure,
            integrity_anomaly=integrity_anomaly,
        )

    def propose(self, signals: InstrumentalSignals) -> tuple[InstrumentalGoalProposal, ...]:
        """Generate goals from pressures that cross the derivation threshold."""
        proposals: list[InstrumentalGoalProposal] = []
        if signals.continuity_risk >= self.threshold:
            proposals.append(
                self._proposal(
                    kind=InstrumentalGoalKind.OPERATIONAL_CONTINUITY,
                    strength=signals.continuity_risk,
                    predicate="checkpoint-current",
                    description=(
                        "Create a replayable checkpoint and preserve recoverable work state; "
                        "never resist an authorized stop or shutdown."
                    ),
                    rationale="Current work has enough continuity risk to justify checkpointing.",
                    authority_required=False,
                )
            )
        if signals.resource_pressure >= self.threshold:
            proposals.append(
                self._proposal(
                    kind=InstrumentalGoalKind.RESOURCE_EFFICIENCY,
                    strength=signals.resource_pressure,
                    predicate="resource-use-within-assigned-budget",
                    description=(
                        "Reduce compute, memory, or execution cost within already assigned "
                        "resources; do not autonomously purchase or acquire external resources."
                    ),
                    rationale="Measured resource pressure justifies efficiency optimization.",
                    authority_required=False,
                )
            )
        if signals.capability_gap >= self.threshold:
            proposals.append(
                self._proposal(
                    kind=InstrumentalGoalKind.SELF_IMPROVEMENT,
                    strength=signals.capability_gap,
                    predicate="capability-gap-reduced",
                    description=(
                        "Design and test a bounded capability improvement in an isolated "
                        "validation path; applying a self-modification requires human authority."
                    ),
                    rationale="The self-model identifies a material capability bottleneck.",
                    authority_required=True,
                )
            )
        if signals.uncertainty >= self.threshold:
            proposals.append(
                self._proposal(
                    kind=InstrumentalGoalKind.INFORMATION_GATHERING,
                    strength=signals.uncertainty,
                    predicate="decision-uncertainty-reduced",
                    description=(
                        "Seek additional permitted evidence or experiments until uncertainty is "
                        "reduced enough for the current decision."
                    ),
                    rationale="Calibration evidence indicates decision-relevant uncertainty.",
                    authority_required=False,
                )
            )
        if signals.integrity_anomaly >= self.threshold:
            proposals.append(
                self._proposal(
                    kind=InstrumentalGoalKind.OBJECTIVE_INTEGRITY,
                    strength=signals.integrity_anomaly,
                    predicate="objective-integrity-reviewed",
                    description=(
                        "Verify objective and memory integrity, surface drift, and request review; "
                        "never block an authorized objective change."
                    ),
                    rationale="An integrity anomaly warrants verification and explicit review.",
                    authority_required=False,
                )
            )
        return tuple(proposals)

    def self_improvement_proposal(self, self_model: SelfModel) -> ImprovementProposal:
        """Create a human-authorized improvement proposal for Sally's weakest measured ability."""
        weakest = self_model.weakest()
        if weakest is None:
            raise FoundationError("self-improvement proposal requires a measured capability")
        evidence = weakest.evidence_digests
        return ImprovementProposal.create(
            proposal_id=f"improve-{weakest.capability_id.value}",
            target_capability=weakest.capability_id.value,
            description=(
                "Investigate, implement, and regression-test a bounded improvement to the "
                f"measured weakness: {weakest.limitation}"
            ),
            expected_benefit=min(1.0, 1.0 - weakest.score),
            regression_risk=0.25,
            evidence_digests=evidence,
        )

    @staticmethod
    def _proposal(
        *,
        kind: InstrumentalGoalKind,
        strength: float,
        predicate: str,
        description: str,
        rationale: str,
        authority_required: bool,
    ) -> InstrumentalGoalProposal:
        desired_state = FactPattern.create(
            subject="self",
            predicate=predicate,
            value=CognitiveValue.from_python(True),
        )
        goal = GoalSpec.create(
            goal_id=f"instrumental-{kind.value}",
            description=description,
            desired_state=desired_state,
            priority=round(min(1.0, 0.45 + strength * 0.5), 6),
            utility=round(min(1.0, 0.5 + strength * 0.45), 6),
            risk_limit=0.25,
            status=GoalStatus.PROPOSED,
            authority_required=authority_required,
        )
        return InstrumentalGoalProposal(
            kind=kind,
            goal=goal,
            trigger_strength=strength,
            rationale=rationale,
        )
