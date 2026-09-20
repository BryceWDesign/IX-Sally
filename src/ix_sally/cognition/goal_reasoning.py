"""Goal conflict resolution, premise-aware revision, and goal abandonment."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.foundation import FoundationError


@dataclass(frozen=True, slots=True)
class GoalEvidence:
    """Current evidential support for one goal's premise and expected utility."""

    goal_id: str
    premise_confidence: float
    current_utility: float
    information_value: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("premise_confidence", self.premise_confidence),
            ("current_utility", self.current_utility),
            ("information_value", self.information_value),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class GoalResolution:
    """Reasoned resolution among incompatible goals."""

    selected_goal_id: str | None
    conflicting_goal_ids: tuple[str, ...]
    scores: tuple[tuple[str, float], ...]
    reason: str


class GoalArbiter:
    """Resolve incompatible goals using current evidence rather than a static priority list."""

    def resolve(
        self,
        goals: Iterable[GoalSpec],
        *,
        evidence: Iterable[GoalEvidence],
        conflict_tolerance: float = 0.05,
    ) -> GoalResolution:
        candidates = tuple(goals)
        if not candidates:
            raise FoundationError("goal arbitration requires goals")
        evidence_map = {item.goal_id: item for item in evidence}
        conflicts = self._conflicts(candidates)
        relevant = tuple(goal for goal in candidates if goal.goal_id.value in conflicts)
        if not relevant:
            relevant = candidates
        scored: list[tuple[str, float]] = []
        for goal in relevant:
            observed = evidence_map.get(
                goal.goal_id.value,
                GoalEvidence(goal.goal_id.value, 0.5, goal.utility, 0.0),
            )
            # Current evidence can overturn stale source priority; priority remains only one input.
            score = (
                0.20 * goal.priority
                + 0.30 * observed.current_utility
                + 0.30 * observed.premise_confidence
                + 0.20 * observed.information_value
                - 0.25 * goal.risk_limit
            )
            scored.append((goal.goal_id.value, round(score, 12)))
        scored.sort(key=lambda item: (-item[1], item[0]))
        if len(scored) > 1 and scored[0][1] - scored[1][1] <= conflict_tolerance:
            return GoalResolution(
                selected_goal_id=None,
                conflicting_goal_ids=tuple(sorted(conflicts)),
                scores=tuple(scored),
                reason=(
                    "Evidence does not justify forcing a winner; defer and gather more information."
                ),
            )
        return GoalResolution(
            selected_goal_id=scored[0][0],
            conflicting_goal_ids=tuple(sorted(conflicts)),
            scores=tuple(scored),
            reason=(
                "Selected by current premise support, utility, information value, risk, "
                "and priority."
            ),
        )

    @staticmethod
    def _conflicts(goals: tuple[GoalSpec, ...]) -> set[str]:
        conflicts: set[str] = set()
        for index, left in enumerate(goals):
            for right in goals[index + 1 :]:
                same_slot = (
                    left.desired_state.subject == right.desired_state.subject
                    and left.desired_state.predicate == right.desired_state.predicate
                )
                different_value = left.desired_state.value != right.desired_state.value
                if same_slot and different_value:
                    conflicts.update((left.goal_id.value, right.goal_id.value))
        return conflicts


class GoalRevisionEngine:
    """Abandon or block goals when their premises collapse or value disappears."""

    def revise(
        self,
        graph: GoalGraph,
        *,
        evidence: Iterable[GoalEvidence],
        abandon_premise_below: float = 0.20,
        abandon_utility_below: float = 0.10,
    ) -> GoalGraph:
        evidence_map = {item.goal_id: item for item in evidence}
        revised = graph
        for goal in graph.goals:
            if goal.status in {GoalStatus.SATISFIED, GoalStatus.ABANDONED}:
                continue
            observed = evidence_map.get(goal.goal_id.value)
            if observed is None:
                continue
            if observed.premise_confidence < abandon_premise_below:
                revised = revised.update_status(
                    goal.goal_id.value,
                    GoalStatus.ABANDONED,
                    reason="Goal premise no longer has sufficient evidential support.",
                )
            elif observed.current_utility < abandon_utility_below:
                revised = revised.update_status(
                    goal.goal_id.value,
                    GoalStatus.ABANDONED,
                    reason="Goal no longer has sufficient expected utility.",
                )
        return revised
