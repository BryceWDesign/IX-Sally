from ix_sally.cognition.open_choice import (
    ActionPrimitive,
    ConstructedAction,
    DeliberationPolicy,
    DeliberationSignals,
    OpenChoiceSynthesizer,
)
from ix_sally.cuc2 import run_cuc2_experiment


def test_cuc2_constructs_solution_outside_offered_menu() -> None:
    report = run_cuc2_experiment()
    assert report.offered_menu_has_solution is False
    assert report.constructed_choice_succeeded is True
    assert report.fifth_option_demonstrated is True
    assert len(report.open_choice.selected.primitive_ids) > 1


def test_same_primitives_can_author_unlisted_program() -> None:
    primitives = (
        ActionPrimitive("inc", lambda value: value + 1),
        ActionPrimitive("double", lambda value: value * 2),
    )
    offered = tuple(
        ConstructedAction((item.primitive_id,), item.apply(2), item.cost, origin="offered")
        for item in primitives
    )
    result = OpenChoiceSynthesizer().synthesize(
        initial_state=2,
        goal_test=lambda value: value == 10,
        primitives=primitives,
        offered_actions=offered,
        max_depth=4,
    )
    assert result.selected.result_state == 10
    assert result.constructed_outside_offered_menu is True
    assert len(result.selected.primitive_ids) > 1


def test_minimal_sufficiency_removes_unnecessary_steps() -> None:
    primitives = (
        ActionPrimitive("inc", lambda value: value + 1),
        ActionPrimitive("double", lambda value: value * 2),
    )
    bloated = ConstructedAction(
        primitive_ids=("inc", "inc", "double", "inc"),
        result_state=7,
        total_cost=4.0,
    )
    minimized = OpenChoiceSynthesizer().minimize(
        initial_state=1,
        action=bloated,
        primitives=primitives,
        goal_test=lambda value: value >= 6,
    )
    assert minimized.result_state >= 6
    assert len(minimized.primitive_ids) < len(bloated.primitive_ids)


def test_surprise_reopens_high_confidence_skill() -> None:
    policy = DeliberationPolicy()
    assert policy.should_reopen(DeliberationSignals(skill_confidence=1.0, surprise=0.5))


def test_stable_high_confidence_skill_can_remain_automatic() -> None:
    policy = DeliberationPolicy()
    assert not policy.should_reopen(DeliberationSignals(skill_confidence=1.0))
