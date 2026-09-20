"""Tests for recursive cognition and the v0.6 missing-capability integration."""

from __future__ import annotations

import json

import pytest

from ix_sally.cli import main
from ix_sally.cognition import (
    ActionPrimitive,
    ActivePerceptionPlanner,
    AdaptiveSearchPolicy,
    BlindChallenge,
    BlindEvaluatorHarness,
    CapabilityMeasure,
    CausalDiscoveryEngine,
    CausalObservation,
    CounterfactualAction,
    CounterfactualSimulator,
    DomainAdapter,
    FailureObservation,
    GoalArbiter,
    GoalEvidence,
    GoalGraph,
    GoalRevisionEngine,
    GoalSpec,
    GoalStatus,
    ImprovementBenchmark,
    KnowledgeItem,
    LearningStrategyTrial,
    LifelongKnowledgeStore,
    MetaLearningController,
    OntologyRestructurer,
    PerceptionProbe,
    PredictionResidual,
    PredictionSignature,
    RawSignal,
    RawSignalGrounder,
    RepresentationInventor,
    RepresentationObservation,
    SallyCognitiveSystem,
    SearchOperatorTrial,
    SelfDiagnostic,
    SelfDirectedCurriculum,
    SelfImprovementLab,
    SelfModel,
    StructuralAnalogyEngine,
    ToolValidationCase,
    UnknownUnknownDetector,
)
from ix_sally.cognition.long_horizon import HorizonAction, LongHorizonController
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern
from ix_sally.cuc5 import run_cuc5_experiment
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _rep_training() -> tuple[RepresentationObservation, ...]:
    return (
        RepresentationObservation("1", (2.0, 3.0), True),
        RepresentationObservation("2", (-2.0, -1.0), True),
        RepresentationObservation("3", (2.0, -3.0), False),
        RepresentationObservation("4", (-2.0, 3.0), False),
        RepresentationObservation("5", (4.0, 1.0), True),
        RepresentationObservation("6", (-4.0, -1.0), True),
        RepresentationObservation("7", (4.0, -1.0), False),
        RepresentationObservation("8", (-4.0, 1.0), False),
    )


def _rep_holdout() -> tuple[RepresentationObservation, ...]:
    return (
        RepresentationObservation("h1", (8.0, 2.0), True),
        RepresentationObservation("h2", (-8.0, -2.0), True),
        RepresentationObservation("h3", (8.0, -2.0), False),
        RepresentationObservation("h4", (-8.0, 2.0), False),
    )


def test_cuc5_integrated_report_demonstrates_all_bounded_mechanisms() -> None:
    report = run_cuc5_experiment()

    assert report.bootstrap.recursive_growth_demonstrated
    assert report.demonstrated_count == 22
    assert all(report.to_payload()["capabilities"].values())
    assert report.to_payload()["agi_certified"] is False


def test_representation_invention_changes_feature_language_and_survives_holdout() -> None:
    inventor = RepresentationInventor()
    learned = inventor.invent_binary(observations=_rep_training())
    validated = inventor.validate(learned, observations=_rep_holdout())

    assert learned.is_non_atomic
    assert learned.training_accuracy == 1.0
    assert learned.atomic_baseline_accuracy < 1.0
    assert validated.validation_accuracy == 1.0
    primitive = inventor.promote(validated)
    assert primitive.evaluate((3.0, 4.0))
    assert not primitive.evaluate((3.0, -4.0))


def test_representation_invention_negative_control_refuses_unneeded_novelty() -> None:
    observations = (
        RepresentationObservation("1", (0.0, 8.0), False),
        RepresentationObservation("2", (1.0, 7.0), False),
        RepresentationObservation("3", (5.0, 1.0), True),
        RepresentationObservation("4", (6.0, 0.0), True),
    )

    with pytest.raises(FoundationError, match="materially improves"):
        RepresentationInventor().invent_binary(observations=observations)


def test_unknown_unknown_detector_requires_structured_high_confidence_failure() -> None:
    detector = UnknownUnknownDetector()
    signal = detector.detect(
        (
            PredictionResidual("1", 0.95, True, False, (9, 9)),
            PredictionResidual("2", 0.90, True, False, (9, 9)),
            PredictionResidual("3", 0.92, True, True, (1, 1)),
        )
    )
    control = detector.detect(
        (
            PredictionResidual("a", 0.60, True, False, (9, 9)),
            PredictionResidual("b", 0.55, False, True, (9, 9)),
            PredictionResidual("c", 0.95, True, True, (1, 1)),
        )
    )

    assert signal.detected
    assert signal.dominant_context == (9, 9)
    assert not control.detected


def test_active_perception_prefers_discriminating_measurement() -> None:
    choice = ActivePerceptionPlanner().choose(
        priors=(0.5, 0.5),
        probes=(
            PerceptionProbe("weak", (0.6, 0.4)),
            PerceptionProbe("strong", (0.95, 0.05), cost=0.05),
        ),
    )

    assert choice.probe_id == "strong"
    assert choice.expected_information_gain > 0.5


def test_causal_discovery_distinguishes_intervention_and_regime_change() -> None:
    samples = (
        CausalObservation("o1", True, True, False),
        CausalObservation("o2", True, True, False),
        CausalObservation("o3", False, False, False),
        CausalObservation("o4", False, False, False),
        CausalObservation("i1", True, True, True, "r1"),
        CausalObservation("i2", True, True, True, "r1"),
        CausalObservation("i3", False, False, True, "r1"),
        CausalObservation("i4", False, False, True, "r1"),
        CausalObservation("j1", True, False, True, "r2"),
        CausalObservation("j2", True, False, True, "r2"),
        CausalObservation("j3", False, True, True, "r2"),
        CausalObservation("j4", False, True, True, "r2"),
    )
    report = CausalDiscoveryEngine().discover(samples)

    assert report.regime_change_suspected
    assert report.confounding_gap >= 0.5


def test_long_horizon_controller_replans_after_reality_disagrees() -> None:
    action = HorizonAction(
        "advance",
        model_transition=lambda state: state + 1,
        world_transition=lambda state, step: state if step == 1 else state + 1,
    )
    result = LongHorizonController().pursue(
        initial_state=0,
        goal_test=lambda state: state == 4,
        actions=(action,),
        max_steps=8,
        max_plan_depth=6,
    )

    assert result.success
    assert result.replans >= 1
    assert any(step.model_surprise for step in result.steps)
    assert result.subgoals


def test_structural_rule_transfers_across_surface_domains() -> None:
    numbers = DomainAdapter("numbers", int, int)
    letters = DomainAdapter(
        "letters",
        encode=lambda value: ord(str(value)) - ord("A"),
        decode=lambda value: chr(ord("A") + value),
    )
    engine = StructuralAnalogyEngine()
    rule = engine.learn_affine(examples=((1, 3), (2, 5), (3, 7)), adapter=numbers)

    assert (
        engine.evaluate_transfer(
            rule,
            examples=(("A", "B"), ("B", "D"), ("C", "F")),
            adapter=letters,
        )
        == 1.0
    )


def test_lifelong_store_persists_revises_and_restructures_knowledge() -> None:
    a = KnowledgeItem("a", DigestRecord.from_payload({"a": 1}), 0.8, 0.8)
    b = KnowledgeItem("b", DigestRecord.from_payload({"b": 1}), 0.8, 0.8)
    store = LifelongKnowledgeStore().integrate(a).integrate(b)
    store = store.record_use("a", successful=True).advance_generation().consolidate()
    abstraction = OntologyRestructurer().restructure(
        (
            PredictionSignature("a", (True, False)),
            PredictionSignature("b", (True, False)),
        )
    )[0]
    restructured = OntologyRestructurer().apply_to_store(store, abstraction)

    assert restructured.items
    assert any(item.concept_id == abstraction.concept_id for item in restructured.items)
    assert all(
        item.superseded_by == abstraction.concept_id
        for item in restructured.items
        if item.concept_id in {"a", "b"}
    )


def test_self_directed_curriculum_and_meta_learning_change_future_strategy() -> None:
    digest = DigestRecord.from_payload({"measurement": 1})
    model = SelfModel(
        (
            CapabilityMeasure.create(
                capability_id="search",
                score=0.2,
                evidence_digests=(digest,),
                limitation="Candidate explosion.",
            ),
            CapabilityMeasure.create(
                capability_id="planning",
                score=0.8,
                evidence_digests=(digest,),
                limitation="Bounded horizon.",
            ),
        )
    )
    curriculum = SelfDirectedCurriculum().choose(
        self_model=model,
        uncertainty={"search": 0.8},
        opportunity={"search": 0.9},
    )
    decision = MetaLearningController().select(
        (
            LearningStrategyTrial("default", "novel", 0.4, 20),
            LearningStrategyTrial("default", "novel", 0.5, 20),
            LearningStrategyTrial("residual", "novel", 0.9, 10),
            LearningStrategyTrial("residual", "novel", 0.8, 10),
        ),
        task_family="novel",
        default_strategy_id="default",
    )

    assert curriculum.capability_id == "search"
    assert decision.changed_strategy
    assert decision.selected_strategy_id == "residual"


def test_adaptive_search_budget_favors_evidenced_operator() -> None:
    allocation = AdaptiveSearchPolicy().allocate(
        (
            SearchOperatorTrial("good", True, 0.9, 0.1),
            SearchOperatorTrial("good", True, 0.8, 0.1),
            SearchOperatorTrial("poor", False, 0.1, 0.4),
            SearchOperatorTrial("poor", False, 0.1, 0.4),
        ),
        total_budget=30,
    )

    assert allocation.budget_for("good") > allocation.budget_for("poor")
    assert sum(value for _, value in allocation.allocations) == 30


def test_self_diagnostic_finds_blind_spot_and_improvement_remains_unauthorized() -> None:
    digest = DigestRecord.from_payload({"measurement": "search"})
    model = SelfModel(
        (
            CapabilityMeasure.create(
                capability_id="search",
                score=0.25,
                evidence_digests=(digest,),
                limitation="High branching factor.",
            ),
        )
    )
    diagnostic = SelfDiagnostic().diagnose(
        (
            FailureObservation("search", 0.9, False, "branching"),
            FailureObservation("search", 0.9, False, "branching"),
            FailureObservation("search", 0.9, True, "none"),
        )
    )[0]
    improvement = SelfImprovementLab().propose(
        self_model=model,
        target_capability="search",
        description="Use evidence-guided branch allocation.",
        benchmarks=(ImprovementBenchmark("b", 0.4, 0.8, 0.01),),
    )

    assert diagnostic.blind_spot_detected
    assert improvement.adoption_recommended
    assert improvement.authority_required
    assert not improvement.proposal.may_enter_validation()


def test_goal_conflict_can_defer_or_choose_and_goal_can_die() -> None:
    left = GoalSpec.create(
        goal_id="left",
        description="Reach left.",
        desired_state=FactPattern.create(
            subject="world", predicate="side", value=CognitiveValue.from_python("left")
        ),
        priority=0.5,
        utility=0.5,
        risk_limit=0.1,
    )
    right = GoalSpec.create(
        goal_id="right",
        description="Reach right.",
        desired_state=FactPattern.create(
            subject="world", predicate="side", value=CognitiveValue.from_python("right")
        ),
        priority=0.5,
        utility=0.5,
        risk_limit=0.1,
    )
    deferred = GoalArbiter().resolve(
        (left, right),
        evidence=(GoalEvidence("left", 0.5, 0.5), GoalEvidence("right", 0.5, 0.5)),
    )
    selected = GoalArbiter().resolve(
        (left, right),
        evidence=(GoalEvidence("left", 0.9, 0.9), GoalEvidence("right", 0.2, 0.2)),
    )
    revised = GoalRevisionEngine().revise(
        GoalGraph.create((left,)),
        evidence=(GoalEvidence("left", 0.05, 0.9),),
    )

    assert deferred.selected_goal_id is None
    assert selected.selected_goal_id == "left"
    assert revised.require("left").status is GoalStatus.ABANDONED


def test_raw_signal_grounding_and_counterfactual_imagination_are_non_destructive() -> None:
    grounded = RawSignalGrounder().ground(RawSignal("raw", (0.0, 0.1, 0.2, 7.0, 7.1, 7.2)))
    futures = CounterfactualSimulator().imagine(
        initial_state=2,
        actions=(
            CounterfactualAction("inc", lambda value: value + 1, lambda value: value / 10),
            CounterfactualAction("double", lambda value: value * 2, lambda value: value / 10),
        ),
        depth=2,
    )

    assert grounded.change_points
    assert futures
    assert all(branch.states[0] == 2 for branch in futures)


def test_blind_evaluator_nonce_commitments_detect_tampering() -> None:
    challenges = (
        BlindChallenge("a", (1, 2), 3, "secret-a"),
        BlindChallenge("b", (2, 3), 5, "secret-b"),
    )
    commitments = tuple(item.commitment() for item in challenges)
    result = BlindEvaluatorHarness().evaluate(
        challenges=challenges,
        commitments=commitments,
        agent=sum,
    )

    assert result.accuracy == 1.0
    assert result.commitments_verified
    bad = (DigestRecord.from_payload({"tampered": True}), commitments[1])
    with pytest.raises(FoundationError, match="commitment"):
        BlindEvaluatorHarness().evaluate(
            challenges=challenges,
            commitments=bad,
            agent=sum,
        )


def test_system_persists_lifelong_knowledge_across_snapshot_restore() -> None:
    system = SallyCognitiveSystem.create()
    item = KnowledgeItem(
        "persisted-concept",
        DigestRecord.from_payload({"learned": True}),
        confidence=0.9,
        utility=0.8,
    )
    system.integrate_knowledge(item)
    snapshot = system.snapshot()
    restored = SallyCognitiveSystem.from_snapshot(snapshot)

    assert restored.lifelong_knowledge == system.lifelong_knowledge
    assert restored.state_payload() == system.state_payload()


def test_cli_cuc5_reports_integrated_capabilities(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["--cuc5-experiment"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert result == 0
    assert payload["demonstrated_count"] == 22
    assert payload["capabilities"]["recursive_cognitive_growth"] is True
    assert payload["agi_certified"] is False


def test_system_recursive_bootstrap_integrates_discoveries_into_persistent_state() -> None:
    system = SallyCognitiveSystem.create()
    primitives = (
        ActionPrimitive("increment", lambda value: value + 1, cost=0.1),
        ActionPrimitive("double", lambda value: value * 2, cost=0.2),
        ActionPrimitive("negate", lambda value: -value, cost=0.2),
    )
    second_training = (
        RepresentationObservation("s1", (1.0, 2.0), True),
        RepresentationObservation("s2", (3.0, 4.0), True),
        RepresentationObservation("s3", (-2.0, -1.0), True),
        RepresentationObservation("s4", (1.0, 6.0), False),
        RepresentationObservation("s5", (8.0, 2.0), False),
        RepresentationObservation("s6", (-7.0, 0.0), False),
    )
    second_holdout = (
        RepresentationObservation("sh1", (10.0, 11.0), True),
        RepresentationObservation("sh2", (-4.0, -3.0), True),
        RepresentationObservation("sh3", (10.0, 3.0), False),
        RepresentationObservation("sh4", (-8.0, 2.0), False),
    )
    report = system.run_recursive_bootstrap(
        representation_training=_rep_training(),
        representation_holdout=_rep_holdout(),
        initial_state=2,
        primitives=primitives,
        known_states=(2, 3, 4, -2),
        tool_validation_cases=(ToolValidationCase(1, 3), ToolValidationCase(3, 7)),
        residuals=(
            PredictionResidual("r1", 0.95, True, False, (9, 9)),
            PredictionResidual("r2", 0.95, True, False, (9, 9)),
            PredictionResidual("r3", 0.95, True, False, (9, 9)),
        ),
        second_representation_training=second_training,
        second_representation_holdout=second_holdout,
        max_goal_depth=3,
    )

    assert report.recursive_growth_demonstrated
    assert system.lifelong_knowledge == report.knowledge_store
    assert len(system.lifelong_knowledge.items) == 3
    restored = SallyCognitiveSystem.from_snapshot(system.snapshot())
    assert restored.lifelong_knowledge == system.lifelong_knowledge
