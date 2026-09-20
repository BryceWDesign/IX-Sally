"""CUC-2 experiment: construct a successful fifth option from reusable primitives."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.open_choice import (
    ActionPrimitive,
    ConstructedAction,
    DeliberationPolicy,
    DeliberationSignals,
    OpenChoiceResult,
    OpenChoiceSynthesizer,
)
from ix_sally.digest import JsonObject


def _primitives() -> tuple[ActionPrimitive, ...]:
    return (
        ActionPrimitive("increment", lambda value: value + 1),
        ActionPrimitive("decrement", lambda value: value - 1),
        ActionPrimitive("double", lambda value: value * 2),
        ActionPrimitive("negate", lambda value: -value),
    )


def _offered_actions(initial: int) -> tuple[ConstructedAction, ...]:
    return tuple(
        ConstructedAction(
            primitive_ids=(primitive.primitive_id,),
            result_state=primitive.apply(initial),
            total_cost=primitive.cost,
            origin="offered",
        )
        for primitive in _primitives()
    )


@dataclass(frozen=True, slots=True)
class CUC2Report:
    """Evidence for generative action construction and reopened deliberation."""

    initial_state: int
    target_state: int
    offered_actions: tuple[ConstructedAction, ...]
    open_choice: OpenChoiceResult
    minimized_action: ConstructedAction
    skill_would_be_reopened: bool

    @property
    def offered_menu_has_solution(self) -> bool:
        return any(action.result_state == self.target_state for action in self.offered_actions)

    @property
    def constructed_choice_succeeded(self) -> bool:
        return self.open_choice.selected.result_state == self.target_state

    @property
    def fifth_option_demonstrated(self) -> bool:
        return (
            not self.offered_menu_has_solution
            and self.open_choice.constructed_outside_offered_menu
            and len(self.open_choice.selected.primitive_ids) > 1
            and self.constructed_choice_succeeded
        )

    def to_payload(self) -> JsonObject:
        return {
            "experiment": "CUC-2-generative-open-choice",
            "initial_state": self.initial_state,
            "target_state": self.target_state,
            "offered_actions": [action.action_id for action in self.offered_actions],
            "offered_results": [action.result_state for action in self.offered_actions],
            "offered_menu_has_solution": self.offered_menu_has_solution,
            "constructed_action": self.open_choice.selected.action_id,
            "constructed_result": self.open_choice.selected.result_state,
            "constructed_outside_offered_menu": (
                self.open_choice.constructed_outside_offered_menu
            ),
            "explored_programs": self.open_choice.explored_programs,
            "minimized_action": self.minimized_action.action_id,
            "minimized_result": self.minimized_action.result_state,
            "skill_would_be_reopened": self.skill_would_be_reopened,
            "fifth_option_demonstrated": self.fifth_option_demonstrated,
            "agi_certified": False,
            "claim_boundary": (
                "Demonstrates bounded generative action construction from reusable primitives; "
                "it does not demonstrate AGI, consciousness, or unbounded computation."
            ),
        }


def run_cuc2_experiment() -> CUC2Report:
    """Run a deterministic proof that no offered action works but a composed one can."""
    initial = 3
    target = 11
    primitives = _primitives()
    offered = _offered_actions(initial)
    synthesizer = OpenChoiceSynthesizer()
    open_choice = synthesizer.synthesize(
        initial_state=initial,
        goal_test=lambda value: value == target,
        primitives=primitives,
        offered_actions=offered,
        max_depth=6,
    )
    minimized = synthesizer.minimize(
        initial_state=initial,
        action=open_choice.selected,
        primitives=primitives,
        goal_test=lambda value: value == target,
    )
    reopen = DeliberationPolicy().should_reopen(
        DeliberationSignals(
            skill_confidence=0.995,
            surprise=0.4,
            context_shift=0.0,
            conflict=0.0,
            novel_alternative_value=0.0,
        )
    )
    return CUC2Report(
        initial_state=initial,
        target_state=target,
        offered_actions=offered,
        open_choice=open_choice,
        minimized_action=minimized,
        skill_would_be_reopened=reopen,
    )
