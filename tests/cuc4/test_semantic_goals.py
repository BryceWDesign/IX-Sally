from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.cognition.open_goals import OpenGoalGenesis
from ix_sally.cognition.semantic_genesis import SemanticGenesisEngine, SemanticObservation
from ix_sally.cuc4 import run_cuc4_experiment


def test_cuc4_invents_new_relational_semantic_and_transfers() -> None:
    report = run_cuc4_experiment()
    assert report.semantic_genesis_demonstrated is True
    assert report.semantic.relation_arity >= 2
    assert report.semantic.validation_accuracy == 1.0
    assert report.semantic.training_accuracy > report.semantic.atomic_baseline_accuracy


def test_semantic_token_is_opaque_and_not_a_supplied_human_label() -> None:
    engine = SemanticGenesisEngine()
    concept = engine.invent(
        observations=(
            SemanticObservation("a", (1.0, 0.0), True),
            SemanticObservation("b", (2.0, 1.0), True),
            SemanticObservation("c", (1.0, 2.0), False),
            SemanticObservation("d", (3.0, 4.0), False),
            SemanticObservation("e", (4.0, 3.0), True),
            SemanticObservation("f", (0.0, 1.0), False),
        )
    )
    payload = concept.to_payload()
    assert concept.concept_id.startswith("latent-")
    assert payload["human_semantic_label"] is None
    assert concept.activates((9.0, 8.0)) is True
    assert concept.activates((2.0, 7.0)) is False


def test_cuc4_generates_goal_targets_without_fixed_goal_catalog() -> None:
    report = run_cuc4_experiment()
    assert report.open_goal_genesis_demonstrated is True
    assert report.first_goal.goal.goal_id != report.second_goal.goal.goal_id
    assert report.first_goal.target_state != report.second_goal.target_state


def test_open_goal_engine_receives_no_target_and_authors_one() -> None:
    primitives = (
        ActionPrimitive("inc", lambda value: value + 1),
        ActionPrimitive("double", lambda value: value * 2),
        ActionPrimitive("negate", lambda value: -value),
    )
    generated = OpenGoalGenesis().generate(
        initial_state=2,
        primitives=primitives,
        known_states=(2, 3, 4, -2),
        max_depth=3,
        max_programs=128,
        state_bound=64,
    )
    assert generated.target_state not in {2, 3, 4, -2}
    assert generated.goal.authority_required is False
    assert generated.origin == "sally-open-goal-genesis"


def test_generated_goals_remain_internal_and_do_not_grant_external_authority() -> None:
    report = run_cuc4_experiment()
    first_payload = report.first_goal.to_payload()
    second_payload = report.second_goal.to_payload()
    assert first_payload["external_authority_granted"] is False
    assert second_payload["external_authority_granted"] is False


def test_sally_system_exposes_semantic_and_goal_genesis() -> None:
    from ix_sally.cognition.system import SallyCognitiveSystem

    system = SallyCognitiveSystem.create()
    semantic = system.invent_semantic(
        observations=(
            SemanticObservation("a", (1.0, 0.0), True),
            SemanticObservation("b", (2.0, 1.0), True),
            SemanticObservation("c", (1.0, 2.0), False),
            SemanticObservation("d", (3.0, 4.0), False),
            SemanticObservation("e", (4.0, 3.0), True),
            SemanticObservation("f", (0.0, 1.0), False),
        )
    )
    assert semantic.relation_arity >= 2

    goal = system.generate_open_goal(
        initial_state=2,
        primitives=(
            ActionPrimitive("inc", lambda value: value + 1),
            ActionPrimitive("double", lambda value: value * 2),
            ActionPrimitive("negate", lambda value: -value),
        ),
        known_states=(2, 3, 4, -2),
        max_depth=3,
        max_programs=128,
        state_bound=64,
    )
    assert goal.target_state not in {2, 3, 4, -2}
