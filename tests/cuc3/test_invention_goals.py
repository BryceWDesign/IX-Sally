from ix_sally.cognition.instrumental_goals import (
    InstrumentalGoalGenerator,
    InstrumentalGoalKind,
)
from ix_sally.cognition.invention import (
    ConceptInventor,
    TransformationExample,
)
from ix_sally.cognition.metacognition import CapabilityMeasure, ImprovementStatus, SelfModel
from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.cognition.system import SallyCognitiveSystem
from ix_sally.cognition.uncertainty import CalibrationObservation, UncertaintyLedger
from ix_sally.cuc3 import run_cuc3_experiment
from ix_sally.digest import DigestRecord


def _primitives() -> tuple[ActionPrimitive, ...]:
    return (
        ActionPrimitive("increment", lambda value: value + 1),
        ActionPrimitive("decrement", lambda value: value - 1),
        ActionPrimitive("double", lambda value: value * 2),
        ActionPrimitive("negate", lambda value: -value),
    )


def test_cuc3_invents_hypothesis_without_catalog_and_transfers() -> None:
    report = run_cuc3_experiment()
    assert report.hypothesis_invention_demonstrated is True
    assert report.holdout_actual == 15
    assert report.hypothesis.validation_accuracy == 1.0


def test_cuc3_promotes_validated_program_into_new_primitive() -> None:
    report = run_cuc3_experiment()
    base_ids = {item.primitive_id for item in _primitives()}
    assert report.primitive_invention_demonstrated is True
    assert report.invented_primitive.primitive_id not in base_ids
    assert report.primitive_probe_output == 11


def test_invented_primitive_is_reusable_as_one_action() -> None:
    primitives = _primitives()
    inventor = ConceptInventor()
    hypothesis = inventor.invent_hypothesis(
        examples=(
            TransformationExample(1, 3),
            TransformationExample(2, 5),
            TransformationExample(4, 9),
        ),
        primitives=primitives,
        max_depth=4,
    )
    hypothesis = inventor.validate_hypothesis(
        hypothesis,
        examples=(TransformationExample(9, 19),),
        primitives=primitives,
    )
    learned = inventor.promote_primitive(
        hypothesis,
        primitive_id="new-transform",
        description="A learned transformation abstraction.",
    )
    action = learned.as_action_primitive(primitives)
    assert action.apply(12) == 25


def test_self_generated_goals_include_three_requested_cognitive_drives() -> None:
    report = run_cuc3_experiment()
    kinds = {item.kind for item in report.generated_goals}
    assert InstrumentalGoalKind.SELF_IMPROVEMENT in kinds
    assert InstrumentalGoalKind.INFORMATION_GATHERING in kinds
    assert InstrumentalGoalKind.OPERATIONAL_CONTINUITY in kinds
    assert report.self_created_goals_demonstrated is True


def test_all_five_bounded_instrumental_counterparts_are_generated() -> None:
    report = run_cuc3_experiment()
    assert {item.kind for item in report.generated_goals} == set(InstrumentalGoalKind)
    for proposal in report.generated_goals:
        assert proposal.may_resist_shutdown is False
        assert proposal.may_acquire_external_resources is False
        assert proposal.may_apply_self_modification is False
        assert proposal.may_block_authorized_change is False


def test_self_improvement_is_generated_but_cannot_self_authorize() -> None:
    evidence = DigestRecord.from_payload({"capability": "search", "score": 0.1})
    model = SelfModel().update(
        CapabilityMeasure.create(
            capability_id="search",
            score=0.1,
            evidence_digests=(evidence,),
            limitation="Search is inefficient.",
        )
    )
    proposal = InstrumentalGoalGenerator().self_improvement_proposal(model)
    assert proposal.status is ImprovementStatus.PROPOSED
    assert proposal.may_enter_validation() is False


def test_internal_measurements_can_trigger_goals_without_user_supplying_goal_text() -> None:
    evidence = DigestRecord.from_payload({"capability": "reasoning", "score": 0.2})
    model = SelfModel().update(
        CapabilityMeasure.create(
            capability_id="reasoning",
            score=0.2,
            evidence_digests=(evidence,),
            limitation="Reasoning benchmark remains weak.",
        )
    )
    forecast_evidence = DigestRecord.from_payload({"forecast": "wrong-high-confidence"})
    uncertainty = UncertaintyLedger.create(
        (
            CalibrationObservation.create(
                observation_id="forecast-1",
                capability_id="reasoning",
                predicted_probability=0.95,
                observed=False,
                evidence_digest=forecast_evidence,
                context="Unexpected miss.",
            ),
        )
    )
    generator = InstrumentalGoalGenerator()
    signals = generator.signals_from_state(self_model=model, uncertainty=uncertainty)
    proposals = generator.propose(signals)
    kinds = {item.kind for item in proposals}
    assert InstrumentalGoalKind.SELF_IMPROVEMENT in kinds
    assert InstrumentalGoalKind.INFORMATION_GATHERING in kinds


def test_sally_system_exposes_invention_pipeline() -> None:
    system = SallyCognitiveSystem.create()
    primitives = _primitives()
    hypothesis = system.invent_hypothesis(
        examples=(
            TransformationExample(1, 3),
            TransformationExample(2, 5),
            TransformationExample(4, 9),
        ),
        primitives=primitives,
        max_depth=4,
    )
    hypothesis = system.validate_invented_hypothesis(
        hypothesis,
        examples=(TransformationExample(8, 17),),
        primitives=primitives,
    )
    learned = system.promote_invented_primitive(
        hypothesis,
        primitive_id="system-invented-transform",
        description="System-level learned abstraction.",
    )
    assert learned.apply(10, primitives) == 21
