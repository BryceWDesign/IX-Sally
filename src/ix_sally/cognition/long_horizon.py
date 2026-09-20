"""Persistent long-horizon planning with observed failure and replanning."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class HorizonAction:
    """Action with a planning model and separately observed world transition."""

    action_id: str
    model_transition: Callable[[int], int]
    world_transition: Callable[[int, int], int]
    cost: float = 1.0

    def __post_init__(self) -> None:
        require_text(self.action_id, field_name="action_id")
        if self.cost < 0.0:
            raise FoundationError("horizon action cost must not be negative")


@dataclass(frozen=True, slots=True)
class HorizonStep:
    step_index: int
    action_id: str
    predicted_state: int
    observed_state: int
    model_surprise: bool


@dataclass(frozen=True, slots=True)
class LongHorizonResult:
    success: bool
    initial_state: int
    final_state: int
    steps: tuple[HorizonStep, ...]
    replans: int
    subgoals: tuple[int, ...]
    abandoned_plans: int


class LongHorizonController:
    """Plan, act, notice model error, and replan until success or a hard bound."""

    def pursue(
        self,
        *,
        initial_state: int,
        goal_test: Callable[[int], bool],
        actions: Iterable[HorizonAction],
        max_steps: int = 32,
        max_plan_depth: int = 12,
        state_bound: int = 512,
    ) -> LongHorizonResult:
        catalog = tuple(actions)
        if not catalog or max_steps < 1 or max_plan_depth < 1:
            raise FoundationError("long-horizon pursuit requires actions and positive bounds")
        state = initial_state
        steps: list[HorizonStep] = []
        replans = 0
        abandoned = 0
        subgoals: list[int] = []
        while len(steps) < max_steps and not goal_test(state):
            plan = self._plan(
                state=state,
                goal_test=goal_test,
                actions=catalog,
                max_depth=max_plan_depth,
                state_bound=state_bound,
            )
            if not plan:
                break
            # Intermediate predicted states become explicit subgoals/milestones.
            predicted = state
            predicted_states: list[int] = []
            for action in plan:
                predicted = action.model_transition(predicted)
                predicted_states.append(predicted)
            subgoals.extend(predicted_states[:-1])
            surprise = False
            for action in plan:
                if len(steps) >= max_steps:
                    break
                predicted_state = action.model_transition(state)
                observed_state = action.world_transition(state, len(steps))
                mismatch = predicted_state != observed_state
                steps.append(
                    HorizonStep(
                        step_index=len(steps),
                        action_id=action.action_id,
                        predicted_state=predicted_state,
                        observed_state=observed_state,
                        model_surprise=mismatch,
                    )
                )
                state = observed_state
                if goal_test(state):
                    break
                if mismatch:
                    surprise = True
                    abandoned += 1
                    replans += 1
                    break
            if not surprise and not goal_test(state):
                replans += 1
        return LongHorizonResult(
            success=goal_test(state),
            initial_state=initial_state,
            final_state=state,
            steps=tuple(steps),
            replans=replans,
            subgoals=tuple(subgoals),
            abandoned_plans=abandoned,
        )

    def _plan(
        self,
        *,
        state: int,
        goal_test: Callable[[int], bool],
        actions: tuple[HorizonAction, ...],
        max_depth: int,
        state_bound: int,
    ) -> tuple[HorizonAction, ...]:
        if goal_test(state):
            return ()
        queue: deque[tuple[int, tuple[HorizonAction, ...]]] = deque([(state, ())])
        visited = {state}
        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for action in sorted(actions, key=lambda item: (item.cost, item.action_id)):
                next_state = action.model_transition(current)
                if abs(next_state) > state_bound or next_state in visited:
                    continue
                next_path = (*path, action)
                if goal_test(next_state):
                    return next_path
                visited.add(next_state)
                queue.append((next_state, next_path))
        return ()
