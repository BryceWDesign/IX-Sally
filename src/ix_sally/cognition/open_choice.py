"""Generative open-choice machinery for constructing actions beyond an offered menu.

The module intentionally separates *primitive capabilities* from *complete actions*.
A complete action can be synthesized as a novel composition of primitives, so the
agent is not restricted to selecting one item from a pre-enumerated action list.
Every concrete deliberation remains bounded by explicit search limits.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ix_sally.foundation import FoundationError, require_text

State = int
GoalTest = Callable[[State], bool]


@dataclass(frozen=True, slots=True)
class ActionPrimitive:
    """One reusable transformation that can participate in invented programs."""

    primitive_id: str
    operation: Callable[[State], State]
    cost: float = 1.0

    def __post_init__(self) -> None:
        require_text(self.primitive_id, field_name="primitive_id")
        if self.cost < 0.0:
            raise FoundationError("primitive cost must not be negative")

    def apply(self, state: State) -> State:
        """Apply this primitive to one state."""
        return self.operation(state)


@dataclass(frozen=True, slots=True)
class ConstructedAction:
    """A complete action authored by composing one or more primitives."""

    primitive_ids: tuple[str, ...]
    result_state: State
    total_cost: float
    origin: str = "constructed"

    def __post_init__(self) -> None:
        if not self.primitive_ids:
            raise FoundationError("constructed action requires at least one primitive")
        if self.total_cost < 0.0:
            raise FoundationError("constructed action cost must not be negative")

    @property
    def action_id(self) -> str:
        """Return a stable human-readable identity for the composed action."""
        return "compose:" + ">".join(self.primitive_ids)


@dataclass(frozen=True, slots=True)
class OpenChoiceResult:
    """Evidence that the agent considered offered actions and authored an alternative."""

    offered_action_ids: tuple[str, ...]
    selected: ConstructedAction
    constructed_outside_offered_menu: bool
    explored_programs: int


@dataclass(frozen=True, slots=True)
class DeliberationSignals:
    """Signals that can reopen deliberation instead of blindly executing a habit."""

    surprise: float = 0.0
    context_shift: float = 0.0
    conflict: float = 0.0
    novel_alternative_value: float = 0.0
    skill_confidence: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("surprise", self.surprise),
            ("context_shift", self.context_shift),
            ("conflict", self.conflict),
            ("novel_alternative_value", self.novel_alternative_value),
            ("skill_confidence", self.skill_confidence),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class DeliberationPolicy:
    """Policy for reopening choice when reality gives a reason to reconsider."""

    surprise_threshold: float = 0.25
    context_shift_threshold: float = 0.35
    conflict_threshold: float = 0.20
    alternative_advantage_threshold: float = 0.10
    automatic_skill_confidence: float = 0.98

    def should_reopen(self, signals: DeliberationSignals) -> bool:
        """Return True when habit execution should yield to renewed deliberation."""
        return (
            signals.surprise >= self.surprise_threshold
            or signals.context_shift >= self.context_shift_threshold
            or signals.conflict >= self.conflict_threshold
            or signals.novel_alternative_value >= self.alternative_advantage_threshold
            or signals.skill_confidence < self.automatic_skill_confidence
        )


class OpenChoiceSynthesizer:
    """Construct complete actions from primitives instead of selecting only presets."""

    def synthesize(
        self,
        *,
        initial_state: State,
        goal_test: GoalTest,
        primitives: Iterable[ActionPrimitive],
        offered_actions: Iterable[ConstructedAction] = (),
        max_depth: int = 8,
        max_programs: int = 4096,
    ) -> OpenChoiceResult:
        """Search a generative program space for a goal-satisfying novel action.

        Breadth-first construction prefers shorter programs. The grammar itself can
        compose primitives to arbitrary depth; this invocation is deliberately bounded.
        """
        if max_depth < 1:
            raise FoundationError("max_depth must be positive")
        if max_programs < 1:
            raise FoundationError("max_programs must be positive")
        primitive_tuple = tuple(primitives)
        if not primitive_tuple:
            raise FoundationError("open choice requires at least one primitive")
        identifiers = [item.primitive_id for item in primitive_tuple]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("primitive identifiers must be unique")

        offered_tuple = tuple(offered_actions)
        offered_ids = tuple(item.action_id for item in offered_tuple)
        queue: deque[tuple[State, tuple[str, ...], float]] = deque([(initial_state, (), 0.0)])
        explored = 0
        visited_depth: dict[State, int] = {initial_state: 0}

        while queue and explored < max_programs:
            state, program, cost = queue.popleft()
            if len(program) >= max_depth:
                continue
            for primitive in primitive_tuple:
                explored += 1
                next_state = primitive.apply(state)
                next_program = (*program, primitive.primitive_id)
                next_cost = cost + primitive.cost
                candidate = ConstructedAction(
                    primitive_ids=next_program,
                    result_state=next_state,
                    total_cost=next_cost,
                )
                if goal_test(next_state):
                    return OpenChoiceResult(
                        offered_action_ids=offered_ids,
                        selected=candidate,
                        constructed_outside_offered_menu=candidate.action_id not in offered_ids,
                        explored_programs=explored,
                    )
                depth = len(next_program)
                prior_depth = visited_depth.get(next_state)
                if prior_depth is None or depth < prior_depth:
                    visited_depth[next_state] = depth
                    queue.append((next_state, next_program, next_cost))
                if explored >= max_programs:
                    break

        raise FoundationError("no satisfying constructed action found within search bounds")

    def minimize(
        self,
        *,
        initial_state: State,
        action: ConstructedAction,
        primitives: Iterable[ActionPrimitive],
        goal_test: GoalTest,
    ) -> ConstructedAction:
        """Remove unnecessary steps while preserving independently tested success.

        This is constructive constraint-breaking: a step survives only when deleting it
        would make the result fail the goal test.
        """
        primitive_map = {item.primitive_id: item for item in primitives}
        program = list(action.primitive_ids)

        def execute(candidate_program: list[str]) -> tuple[State, float]:
            state = initial_state
            cost = 0.0
            for primitive_id in candidate_program:
                primitive = primitive_map.get(primitive_id)
                if primitive is None:
                    raise FoundationError(
                        f"unknown primitive in constructed action: {primitive_id}"
                    )
                state = primitive.apply(state)
                cost += primitive.cost
            return state, cost

        changed = True
        while changed and len(program) > 1:
            changed = False
            for index in range(len(program)):
                trial = program[:index] + program[index + 1 :]
                state, _ = execute(trial)
                if goal_test(state):
                    program = trial
                    changed = True
                    break
        result_state, total_cost = execute(program)
        return ConstructedAction(
            primitive_ids=tuple(program),
            result_state=result_state,
            total_cost=total_cost,
            origin="constructed-minimized",
        )
