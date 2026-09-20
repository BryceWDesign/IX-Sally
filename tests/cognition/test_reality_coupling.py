from ix_sally.cognition.assumption_ledger import Assumption, AssumptionLedger, AssumptionStatus
from ix_sally.cognition.authority_envelope import EpistemicAuthorityEnvelope, ProposalScope
from ix_sally.cognition.autobiographical_trace import AutobiographicalEpistemicTrace, TraceKind
from ix_sally.cognition.epistemic_pressure import (
    CognitiveOperation,
    CognitiveOperationSelector,
    EpistemicPressure,
)
from ix_sally.cognition.perspectives import PerspectiveEnsemble, PerspectivePrediction
from ix_sally.cognition.reality_coupling import (
    RealityComparator,
    RealityObservation,
    RealityPrediction,
)
from ix_sally.cognition.system import SallyCognitiveSystem


def test_reality_comparator_keeps_prediction_and_observation_independent() -> None:
    prediction = RealityPrediction("p", (0.0, 0.0), 0.9)
    observation = RealityObservation("o", (0.3, 0.4), 0.8)
    delta = RealityComparator().compare(prediction, observation, scale=1.0)

    assert prediction.expected_values == (0.0, 0.0)
    assert observation.values == (0.3, 0.4)
    assert delta.residuals == (0.3, 0.4)
    assert delta.normalized_error == 0.353553390593


def test_assumption_aging_triggers_revalidation_instead_of_silent_staleness() -> None:
    ledger = AssumptionLedger()
    ledger.register(Assumption("a", "rule remains valid", 0.8, 0.7, max_age=2))
    ledger.age(2)
    assert ledger.get("a").status is AssumptionStatus.REVALIDATION_REQUIRED

    ledger.validate("a", evidence_id="fresh-evidence")
    restored = ledger.get("a")
    assert restored.status is AssumptionStatus.VALIDATED
    assert restored.age == 0
    assert restored.evidence_ids == ("fresh-evidence",)


def test_epistemic_tie_prioritizes_contradiction_recovery() -> None:
    pressure = EpistemicPressure(prediction_error=1.0, unresolved_contradiction=1.0)
    directive = CognitiveOperationSelector().choose(pressure)
    assert directive.operation is CognitiveOperation.RECOVER


def test_authority_envelope_shrinks_to_information_gathering_under_pressure() -> None:
    envelope = EpistemicAuthorityEnvelope().evaluate(
        EpistemicPressure(model_disagreement=0.7),
        perception_quorum_satisfied=True,
    )
    assert envelope.scope is ProposalScope.INFORMATION_GATHERING_ONLY
    assert envelope.human_authority_required


def test_perspective_ensemble_preserves_minority_evidence() -> None:
    report = PerspectiveEnsemble().assess(
        (
            PerspectivePrediction("majority", (0.0,), 0.95, ("e-majority",)),
            PerspectivePrediction("minority", (1.0,), 0.60, ("e-minority",)),
        ),
        scale=1.0,
    )
    assert report.disagreement > 0.0
    assert "minority" in report.dissent_ids
    assert report.preserved_evidence_ids == ("e-minority",)


def test_autobiographical_trace_preserves_causal_lineage() -> None:
    trace = AutobiographicalEpistemicTrace()
    trace.append(kind=TraceKind.OBSERVATION, object_id="o", description="observed")
    trace.append(
        kind=TraceKind.PREDICTION,
        object_id="p",
        description="predicted",
        parent_ids=("o",),
    )
    trace.append(
        kind=TraceKind.DELTA,
        object_id="d",
        description="mismatch",
        parent_ids=("p",),
    )
    assert tuple(item.object_id for item in trace.lineage("d")) == ("o", "p", "d")


def test_existing_sally_system_exposes_composed_reality_loop_without_state_migration() -> None:
    system = SallyCognitiveSystem.create()
    before = system.state_payload()
    loop = system.reality_coupled_loop()
    after = system.state_payload()

    assert loop.trace.entries() == ()
    assert before == after
