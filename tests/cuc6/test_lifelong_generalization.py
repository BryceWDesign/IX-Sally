"""Tests for v0.7 lifelong generalization and deeper representation invention."""

from __future__ import annotations

from itertools import product

import pytest

from ix_sally.cognition import (
    ContextualKnowledgeEvidence,
    GoalEvidence,
    GoalPortfolioManager,
    GoalSpec,
    KnowledgeItem,
    KnowledgeMaintenanceEngine,
    LifelongKnowledgeStore,
    OnlineMetaProfile,
    RelationalTransferEngine,
    RelationalWorld,
    RelationEdge,
    RepresentationObservation,
    RepresentationProgramInventor,
    SallyCognitiveSystem,
    TextOutcomeGrounder,
    TextOutcomeObservation,
)
from ix_sally.cognition.lifetime_learning import LifetimeChallenge, LifetimeLearningEngine
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern
from ix_sally.cuc6 import run_cuc6_experiment
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _deep(prefix: str, *, holdout: bool = False) -> tuple[RepresentationObservation, ...]:
    ab = (-4.0, -3.0, 3.0, 4.0) if holdout else (-2.0, -1.0, 1.0, 2.0)
    cs = (-20.0, -7.0, -2.0, 2.0, 7.0, 20.0) if holdout else (-6.0, -3.0, -1.0, 1.0, 3.0, 6.0)
    return tuple(
        RepresentationObservation(
            f"{prefix}-{i}",
            (a, b, c),
            a * b + c >= 0.0,
        )
        for i, (a, b, c) in enumerate(product(ab, ab, cs))
    )


def test_cuc6_integrated_report_demonstrates_nine_release_claims() -> None:
    report = run_cuc6_experiment()

    assert report.demonstrated_count == 9
    assert report.compositional_representation.program.depth >= 2
    assert report.compositional_representation.simple_baseline_accuracy < 1.0
    assert report.compositional_representation.validation_accuracy == 1.0
    assert report.lifetime_learning.later_learning_is_more_selective
    assert report.to_payload()["agi_certified"] is False


def test_compositional_representation_invents_multi_operation_expression() -> None:
    inventor = RepresentationProgramInventor()
    learned = inventor.invent(observations=_deep("train"), max_depth=2, minimum_improvement=0.10)
    validated = inventor.validate(learned, observations=_deep("holdout", holdout=True))

    assert learned.program.depth == 2
    assert learned.program.expression() == "((x0*x1)+x2)"
    assert learned.training_accuracy == 1.0
    assert learned.simple_baseline_accuracy <= 0.85
    assert validated.validation_accuracy == 1.0


def test_compositional_representation_refuses_novelty_when_shallow_language_is_enough() -> None:
    observations = tuple(
        RepresentationObservation(str(i), (float(x), float(y)), x >= 0)
        for i, (x, y) in enumerate(((-3, 8), (-2, -5), (2, 9), (3, -9)))
    )
    with pytest.raises(FoundationError, match="materially improves"):
        RepresentationProgramInventor().invent(observations=observations, minimum_improvement=0.10)


def test_lifelong_memory_splits_contextually_wrong_concept_instead_of_adding_exception() -> None:
    store = LifelongKnowledgeStore().integrate(
        KnowledgeItem(
            "rule",
            DigestRecord.from_payload({"rule": 1}),
            confidence=0.8,
            utility=0.8,
        )
    )
    report = KnowledgeMaintenanceEngine().reconcile(
        store,
        evidence=(
            ContextualKnowledgeEvidence("rule", "regime-a", True, True),
            ContextualKnowledgeEvidence("rule", "regime-a", True, True),
            ContextualKnowledgeEvidence("rule", "regime-b", True, False),
            ContextualKnowledgeEvidence("rule", "regime-b", True, False),
        ),
    )

    assert report.contradiction_resolved
    assert report.split_concepts == ("rule",)
    assert len(report.created_context_concepts) == 2
    original = next(item for item in report.store.items if item.concept_id == "rule")
    assert original.superseded_by is not None


def test_relational_transfer_ignores_surface_names_and_relation_words() -> None:
    source = RelationalWorld(
        "factory",
        (
            RelationEdge("sensor", "signals", "controller"),
            RelationEdge("controller", "drives", "actuator"),
            RelationEdge("backup", "feeds", "actuator"),
        ),
    )
    target = RelationalWorld(
        "software",
        (
            RelationEdge("request", "calls", "adapter"),
            RelationEdge("adapter", "invokes", "renderer"),
            RelationEdge("cache", "warms", "renderer"),
        ),
    )
    engine = RelationalTransferEngine()
    schema = engine.learn(world=source, effective_node="controller")
    inference = engine.transfer(schema, world=target)

    assert inference.structural_match
    assert inference.inferred_node == "adapter"


def test_text_grounding_extracts_empirically_predictive_feature_from_raw_strings() -> None:
    features = TextOutcomeGrounder().discover(
        (
            TextOutcomeObservation("1", "quiet glint corridor", True),
            TextOutcomeObservation("2", "glint signal appears", True),
            TextOutcomeObservation("3", "flat corridor dark", False),
            TextOutcomeObservation("4", "quiet matte signal", False),
            TextOutcomeObservation("5", "glint matte corridor", True),
            TextOutcomeObservation("6", "dark flat signal", False),
        )
    )

    assert features[0].token == "glint"
    assert features[0].information_gain > 0.5


def test_goal_portfolio_respects_dependency_and_kills_collapsed_premise() -> None:
    base = GoalSpec.create(
        goal_id="map",
        description="Map world.",
        desired_state=FactPattern.create(
            subject="w", predicate="mapped", value=CognitiveValue.from_python(True)
        ),
        priority=0.9,
        utility=0.9,
        risk_limit=0.1,
    )
    child = GoalSpec.create(
        goal_id="solve",
        description="Use map.",
        desired_state=FactPattern.create(
            subject="w", predicate="solved", value=CognitiveValue.from_python(True)
        ),
        priority=0.8,
        utility=0.9,
        risk_limit=0.1,
        dependency_ids=("map",),
    )
    stale = GoalSpec.create(
        goal_id="stale",
        description="No longer warranted.",
        desired_state=FactPattern.create(
            subject="w", predicate="old", value=CognitiveValue.from_python(True)
        ),
        priority=1.0,
        utility=0.9,
        risk_limit=0.1,
    )
    decision = GoalPortfolioManager().allocate(
        (base, child, stale),
        evidence=(
            GoalEvidence("map", 0.9, 0.9, 0.8),
            GoalEvidence("solve", 0.9, 0.9, 0.2),
            GoalEvidence("stale", 0.05, 0.9, 0.0),
        ),
        attention_budget=0.6,
        per_goal_cost={"map": 0.3, "solve": 0.3, "stale": 0.3},
    )
    assert decision.selected_goal_ids == ("map", "solve")
    assert decision.abandoned_goal_ids == ("stale",)


def test_online_meta_profile_persists_through_full_system_snapshot() -> None:
    challenge = LifetimeChallenge("a", _deep("train"), _deep("holdout", holdout=True))
    system = SallyCognitiveSystem.create()
    report = system.run_lifetime_learning(
        challenges=(challenge, challenge, challenge), exploration_episodes=1
    )

    assert report.later_learning_is_more_selective
    assert len(system.online_meta_profile.experiences) >= 4
    restored = SallyCognitiveSystem.from_snapshot(system.snapshot())
    assert restored.online_meta_profile == system.online_meta_profile
    assert restored.state_payload() == system.state_payload()


def test_later_sally_uses_prior_learning_to_reduce_strategy_search() -> None:
    challenges = tuple(
        LifetimeChallenge(
            f"world-{i}",
            _deep(f"train-{i}"),
            _deep(f"holdout-{i}", holdout=True),
        )
        for i in range(4)
    )
    report = LifetimeLearningEngine().run_lifetime(
        profile=OnlineMetaProfile(),
        challenges=challenges,
        exploration_episodes=1,
    )

    assert report.episodes[0].strategies_evaluated == 2
    assert all(item.strategies_evaluated == 1 for item in report.episodes[1:])
    assert all(item.validation_accuracy == 1.0 for item in report.episodes)
    assert report.later_learning_is_more_selective
