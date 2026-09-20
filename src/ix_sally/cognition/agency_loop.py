"""Continuous reality-coupled cognitive agency around the existing Sally runtime."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.assumption_ledger import AssumptionDiagnosis, AssumptionLedger
from ix_sally.cognition.authority_envelope import AuthorityEnvelope, EpistemicAuthorityEnvelope
from ix_sally.cognition.autobiographical_trace import AutobiographicalEpistemicTrace, TraceKind
from ix_sally.cognition.cognitive_recovery import (
    CognitiveRecoveryController,
    RecoveryDecision,
    RecoveryStage,
)
from ix_sally.cognition.counterfactual_goals import (
    BlockedCondition,
    CounterfactualGoalGenerator,
    EpistemicGoal,
    GoalSource,
)
from ix_sally.cognition.epistemic_pressure import (
    CognitiveDirective,
    CognitiveOperationSelector,
    EpistemicPressure,
)
from ix_sally.cognition.perception_quorum import (
    PerceptionChannelObservation,
    PerceptionQuorum,
    PerceptionQuorumReport,
)
from ix_sally.cognition.perspectives import (
    PerspectiveEnsemble,
    PerspectivePrediction,
    PerspectiveReport,
)
from ix_sally.cognition.reality_coupling import (
    RealityComparator,
    RealityDelta,
    RealityObservation,
    RealityPrediction,
)
from ix_sally.foundation import FoundationError


@dataclass(frozen=True, slots=True)
class CognitiveContextSignals:
    """Additional state not derivable from one prediction/observation pair."""

    novelty: float = 0.0
    staleness: float = 0.0
    focus_omission: float = 0.0
    goal_drift: float = 0.0
    representation_failure: float = 0.0
    causal_failure: float = 0.0
    evidence_gap: float = 0.0
    revalidation_need: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("novelty", self.novelty),
            ("staleness", self.staleness),
            ("focus_omission", self.focus_omission),
            ("goal_drift", self.goal_drift),
            ("representation_failure", self.representation_failure),
            ("causal_failure", self.causal_failure),
            ("evidence_gap", self.evidence_gap),
            ("revalidation_need", self.revalidation_need),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class AgencyCycleResult:
    delta: RealityDelta
    quorum: PerceptionQuorumReport
    perspectives: PerspectiveReport
    pressure: EpistemicPressure
    directive: CognitiveDirective
    recovery: RecoveryDecision
    assumption_diagnosis: AssumptionDiagnosis
    authority: AuthorityEnvelope
    generated_goal: EpistemicGoal | None


class RealityCoupledAgencyLoop:
    """Make unresolved relationships with reality generate the next cognitive operation.

    This layer intentionally does not execute consequential external actions. It returns
    bounded directives and proposal scope while Sally's existing governance retains authority.
    """

    def __init__(self, *, assumptions: AssumptionLedger | None = None) -> None:
        self.assumptions = assumptions if assumptions is not None else AssumptionLedger()
        self.trace = AutobiographicalEpistemicTrace()
        self._comparator = RealityComparator()
        self._quorum = PerceptionQuorum()
        self._perspectives = PerspectiveEnsemble()
        self._selector = CognitiveOperationSelector()
        self._recovery = CognitiveRecoveryController()
        self._authority = EpistemicAuthorityEnvelope()
        self._goal_generator = CounterfactualGoalGenerator()
        self._cycle = 0

    def reconcile(
        self,
        *,
        prediction: RealityPrediction,
        channels: tuple[PerceptionChannelObservation, ...],
        perspectives: tuple[PerspectivePrediction, ...],
        signals: CognitiveContextSignals | None = None,
        comparison_scale: float = 1.0,
        disagreement_scale: float = 1.0,
        external_action_requested: bool = False,
    ) -> AgencyCycleResult:
        """Run one prediction/reality reconciliation cycle and choose what cognition does next."""
        if signals is None:
            signals = CognitiveContextSignals()
        self._cycle += 1
        prefix = f"cycle-{self._cycle}"
        prediction_trace = self.trace.append(
            kind=TraceKind.PREDICTION,
            object_id=f"{prefix}:prediction:{prediction.prediction_id}",
            description="prediction issued before reality observation",
        )
        quorum = self._quorum.assess(channels, disagreement_scale=disagreement_scale)
        observation = RealityObservation(
            observation_id=f"{prefix}:quorum",
            values=quorum.fused_values,
            reliability=quorum.reliability,
            context="multi-channel",
        )
        observation_trace = self.trace.append(
            kind=TraceKind.OBSERVATION,
            object_id=f"{prefix}:observation",
            description=(
                "independent perception quorum observation"
                if quorum.quorum_satisfied
                else "perception channels retained with unresolved disagreement"
            ),
        )
        delta = self._comparator.compare(prediction, observation, scale=comparison_scale)
        delta_trace = self.trace.append(
            kind=TraceKind.DELTA,
            object_id=f"{prefix}:delta",
            description=f"normalized_error={delta.normalized_error}; surprise={delta.surprise}",
            parent_ids=(prediction_trace.object_id, observation_trace.object_id),
        )
        perspective_report = self._perspectives.assess(
            perspectives,
            scale=disagreement_scale,
        )
        diagnosis = self.assumptions.diagnose(delta)
        assumption_risk = max(
            (self.assumptions.get(identifier).risk for identifier in diagnosis.assumption_ids),
            default=0.0,
        )
        contradiction = 1.0 if delta.strong_contradiction else 0.0
        pressure = EpistemicPressure(
            prediction_error=delta.normalized_error,
            perceptual_uncertainty=max(1.0 - quorum.reliability, quorum.disagreement),
            model_disagreement=perspective_report.disagreement,
            unresolved_contradiction=contradiction,
            novelty=signals.novelty,
            assumption_risk=assumption_risk,
            staleness=signals.staleness,
            focus_omission=signals.focus_omission,
            goal_drift=signals.goal_drift,
            representation_failure=signals.representation_failure,
            causal_failure=signals.causal_failure,
            evidence_gap=signals.evidence_gap,
            revalidation_need=max(
                signals.revalidation_need,
                1.0 if diagnosis.revalidation_required else 0.0,
            ),
        )
        recovery = self._recovery.observe(delta)
        directive = self._selector.choose(
            pressure,
            external_action_requested=(
                external_action_requested and recovery.stage is RecoveryStage.NORMAL
            ),
        )
        authority = self._authority.evaluate(
            pressure,
            perception_quorum_satisfied=quorum.quorum_satisfied,
        )
        goal = self._goal_from_state(
            delta=delta,
            quorum=quorum,
            perspectives=perspective_report,
            diagnosis=diagnosis,
            signals=signals,
        )
        directive_trace = self.trace.append(
            kind=TraceKind.DIRECTIVE,
            object_id=f"{prefix}:directive",
            description=f"{directive.operation.value} because {directive.cause}",
            parent_ids=(delta_trace.object_id,),
        )
        if goal is not None:
            self.trace.append(
                kind=TraceKind.GOAL,
                object_id=f"{prefix}:goal",
                description=goal.description,
                parent_ids=(directive_trace.object_id,),
            )
        if recovery.stage is not RecoveryStage.NORMAL:
            self.trace.append(
                kind=TraceKind.RECOVERY,
                object_id=f"{prefix}:recovery",
                description=recovery.reason,
                parent_ids=(delta_trace.object_id,),
            )
        return AgencyCycleResult(
            delta=delta,
            quorum=quorum,
            perspectives=perspective_report,
            pressure=pressure,
            directive=directive,
            recovery=recovery,
            assumption_diagnosis=diagnosis,
            authority=authority,
            generated_goal=goal,
        )

    def advance_recovery(self) -> RecoveryDecision:
        """Advance the explicit cognitive recovery state machine by one stage."""
        return self._recovery.advance()

    def _goal_from_state(
        self,
        *,
        delta: RealityDelta,
        quorum: PerceptionQuorumReport,
        perspectives: PerspectiveReport,
        diagnosis: AssumptionDiagnosis,
        signals: CognitiveContextSignals,
    ) -> EpistemicGoal | None:
        blocked: BlockedCondition | None = None
        if delta.strong_contradiction:
            blocked = BlockedCondition(
                condition_id=delta.prediction_id,
                description="explain reliable contradiction of a high-confidence prediction",
                source=GoalSource.CONTRADICTION,
                severity=delta.surprise,
            )
        elif not quorum.quorum_satisfied:
            blocked = BlockedCondition(
                condition_id="perception-quorum",
                description="resolve disagreement or low reliability across perception channels",
                source=GoalSource.MISSING_EVIDENCE,
                severity=max(quorum.disagreement, 1.0 - quorum.reliability),
            )
        elif perspectives.disagreement >= 0.25:
            blocked = BlockedCondition(
                condition_id="perspective-disagreement",
                description="find evidence that discriminates competing interpretations",
                source=GoalSource.MODEL_DISAGREEMENT,
                severity=perspectives.disagreement,
            )
        elif diagnosis.revalidation_required:
            blocked = BlockedCondition(
                condition_id="assumption-revalidation",
                description="revalidate assumptions implicated by reality delta",
                source=GoalSource.STALE_ASSUMPTION,
                severity=max(delta.surprise, 0.5),
            )
        elif signals.representation_failure >= 0.25:
            blocked = BlockedCondition(
                condition_id="representation-failure",
                description="invent a representation that explains unresolved structure",
                source=GoalSource.REPRESENTATION_FAILURE,
                severity=signals.representation_failure,
            )
        if blocked is None:
            return None
        return self._goal_generator.generate(blocked)
