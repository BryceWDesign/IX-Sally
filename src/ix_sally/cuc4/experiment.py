"""CUC-4: autonomous semantic formation and open-ended internal goal genesis."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.instrumental_goals import InstrumentalGoalKind
from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.cognition.open_goals import GeneratedGoal, OpenGoalGenesis
from ix_sally.cognition.semantic_genesis import (
    InventedSemantic,
    SemanticGenesisEngine,
    SemanticObservation,
)
from ix_sally.digest import JsonObject


def _semantic_training() -> tuple[SemanticObservation, ...]:
    # The consequence depends on a relation between raw channels, not either channel alone.
    return (
        SemanticObservation("train-1", (1.0, 0.0), True),
        SemanticObservation("train-2", (2.0, 1.0), True),
        SemanticObservation("train-3", (1.0, 2.0), False),
        SemanticObservation("train-4", (3.0, 4.0), False),
        SemanticObservation("train-5", (4.0, 3.0), True),
        SemanticObservation("train-6", (0.0, 1.0), False),
    )


def _semantic_holdout() -> tuple[SemanticObservation, ...]:
    return (
        SemanticObservation("holdout-1", (10.0, 9.0), True),
        SemanticObservation("holdout-2", (4.0, 8.0), False),
        SemanticObservation("holdout-3", (-2.0, -3.0), True),
        SemanticObservation("holdout-4", (-5.0, -1.0), False),
    )


def _goal_primitives() -> tuple[ActionPrimitive, ...]:
    return (
        ActionPrimitive("increment", lambda value: value + 1, cost=0.1),
        ActionPrimitive("double", lambda value: value * 2, cost=0.2),
        ActionPrimitive("negate", lambda value: -value, cost=0.2),
    )


@dataclass(frozen=True, slots=True)
class CUC4Report:
    semantic: InventedSemantic
    first_goal: GeneratedGoal
    second_goal: GeneratedGoal

    @property
    def semantic_genesis_demonstrated(self) -> bool:
        return (
            self.semantic.origin == "sally-semantic-genesis"
            and self.semantic.relation_arity >= 2
            and self.semantic.training_accuracy == 1.0
            and self.semantic.validation_accuracy == 1.0
            and self.semantic.training_accuracy > self.semantic.atomic_baseline_accuracy
        )

    @property
    def open_goal_genesis_demonstrated(self) -> bool:
        fixed_goal_kinds = {kind.value for kind in InstrumentalGoalKind}
        return (
            self.first_goal.origin == "sally-open-goal-genesis"
            and self.second_goal.origin == "sally-open-goal-genesis"
            and self.first_goal.goal.goal_id != self.second_goal.goal.goal_id
            and self.first_goal.target_state != self.second_goal.target_state
            and self.first_goal.goal.goal_id.value not in fixed_goal_kinds
            and self.second_goal.goal.goal_id.value not in fixed_goal_kinds
            and self.first_goal.target_state not in {2, 3, 4, -2}
        )

    def to_payload(self) -> JsonObject:
        return {
            "experiment": "CUC-4-semantic-genesis-open-goals",
            "semantic": self.semantic.to_payload(),
            "semantic_genesis_demonstrated": self.semantic_genesis_demonstrated,
            "first_self_generated_goal": self.first_goal.to_payload(),
            "second_self_generated_goal": self.second_goal.to_payload(),
            "open_goal_genesis_demonstrated": self.open_goal_genesis_demonstrated,
            "agi_certified": False,
            "claim_boundary": (
                "Demonstrates bounded autonomous formation of an opaque predictive semantic "
                "distinction from raw relations and runtime generation of novel internal goal "
                "targets without a fixed goal-kind catalog. It does not establish AGI, "
                "consciousness, unrestricted ontology creation, or unilateral external agency."
            ),
        }


def run_cuc4_experiment() -> CUC4Report:
    engine = SemanticGenesisEngine()
    semantic = engine.invent(observations=_semantic_training(), max_abs_weight=2)
    semantic = engine.validate(semantic, observations=_semantic_holdout())

    goal_engine = OpenGoalGenesis()
    primitives = _goal_primitives()
    known = {2, 3, 4, -2}
    first = goal_engine.generate(
        initial_state=2,
        primitives=primitives,
        known_states=known,
        max_depth=3,
        max_programs=128,
        state_bound=64,
    )
    known.add(first.target_state)
    second = goal_engine.generate(
        initial_state=first.target_state,
        primitives=primitives,
        known_states=known,
        max_depth=3,
        max_programs=128,
        state_bound=64,
    )
    return CUC4Report(semantic=semantic, first_goal=first, second_goal=second)
