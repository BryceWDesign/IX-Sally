from ix_sally.cognition.agency_loop import CognitiveContextSignals, RealityCoupledAgencyLoop
from ix_sally.cognition.assumption_ledger import Assumption, AssumptionLedger, AssumptionStatus
from ix_sally.cognition.authority_envelope import ProposalScope
from ix_sally.cognition.cognitive_recovery import RecoveryStage
from ix_sally.cognition.epistemic_pressure import CognitiveOperation
from ix_sally.cognition.perception_quorum import PerceptionChannelObservation
from ix_sally.cognition.perspectives import PerspectivePrediction
from ix_sally.cognition.reality_coupling import RealityPrediction
from ix_sally.cuc7 import run_cuc7


def test_cuc7_unannounced_change_reopens_cognition_and_generates_goal() -> None:
    report = run_cuc7()
    assert report.baseline_operation is CognitiveOperation.ACT
    assert report.shifted_operation is CognitiveOperation.RECOVER
    assert report.contradiction_detected
    assert report.generated_goal is not None
    assert report.assumption_status is AssumptionStatus.CONTRADICTED
    assert report.trace_entries >= 9


def test_reality_loop_preserves_perception_disagreement() -> None:
    loop = RealityCoupledAgencyLoop()
    result = loop.reconcile(
        prediction=RealityPrediction("p", (0.5,), 0.70),
        channels=(
            PerceptionChannelObservation("vision", (0.0,), 0.90),
            PerceptionChannelObservation("touch", (1.0,), 0.90),
        ),
        perspectives=(PerspectivePrediction("model", (0.5,), 0.80),),
        disagreement_scale=0.5,
    )
    assert not result.quorum.quorum_satisfied
    assert result.quorum.disagreement > 0.45
    assert result.pressure.perceptual_uncertainty > 0.45
    assert result.directive.operation is CognitiveOperation.OBSERVE
    assert result.generated_goal is not None
    assert result.authority.scope is ProposalScope.INFORMATION_GATHERING_ONLY


def test_reliable_contradiction_enters_recovery_and_blocks_action() -> None:
    ledger = AssumptionLedger()
    ledger.register(Assumption("a", "stable rule", 0.95, 0.9))
    loop = RealityCoupledAgencyLoop(assumptions=ledger)
    result = loop.reconcile(
        prediction=RealityPrediction("p", (0.0,), 0.95, ("a",)),
        channels=(
            PerceptionChannelObservation("a", (1.0,), 0.99),
            PerceptionChannelObservation("b", (1.0,), 0.99),
        ),
        perspectives=(PerspectivePrediction("old", (0.0,), 0.95),),
        external_action_requested=True,
    )
    assert result.delta.strong_contradiction
    assert result.recovery.stage is RecoveryStage.COMMITMENT_HOLD
    assert not result.directive.external_action_permitted
    assert ledger.get("a").status is AssumptionStatus.CONTRADICTED


def test_representation_failure_can_become_next_cognitive_operation() -> None:
    loop = RealityCoupledAgencyLoop()
    result = loop.reconcile(
        prediction=RealityPrediction("p", (1.0,), 0.8),
        channels=(
            PerceptionChannelObservation("a", (1.0,), 0.95),
            PerceptionChannelObservation("b", (1.0,), 0.95),
        ),
        perspectives=(PerspectivePrediction("m", (1.0,), 0.9),),
        signals=CognitiveContextSignals(representation_failure=0.8),
    )
    assert result.directive.operation is CognitiveOperation.INVENT_REPRESENTATION
    assert result.generated_goal is not None
