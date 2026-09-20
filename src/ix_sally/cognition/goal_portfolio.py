"""Persistent multi-goal coherence under dependencies and finite attention."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.cognition.goal_reasoning import GoalEvidence
from ix_sally.cognition.goals import GoalSpec, GoalStatus
from ix_sally.foundation import FoundationError


@dataclass(frozen=True, slots=True)
class GoalPortfolioDecision:
    selected_goal_ids: tuple[str, ...]
    deferred_goal_ids: tuple[str, ...]
    abandoned_goal_ids: tuple[str, ...]
    total_attention_cost: float


class GoalPortfolioManager:
    """Choose a coherent set of goals while respecting premises, dependencies and attention."""

    def allocate(
        self,
        goals: Iterable[GoalSpec],
        *,
        evidence: Iterable[GoalEvidence],
        attention_budget: float = 1.0,
        per_goal_cost: dict[str, float] | None = None,
    ) -> GoalPortfolioDecision:
        if attention_budget <= 0.0:
            raise FoundationError("goal attention budget must be positive")
        candidates = tuple(goals)
        evidence_map = {item.goal_id: item for item in evidence}
        costs = per_goal_cost or {}
        abandoned: list[str] = []
        ranked: list[tuple[float, GoalSpec, float]] = []
        available_ids = {goal.goal_id.value for goal in candidates}
        for goal in candidates:
            goal_id = goal.goal_id.value
            if goal.status in {GoalStatus.SATISFIED, GoalStatus.ABANDONED}:
                abandoned.append(goal_id) if goal.status is GoalStatus.ABANDONED else None
                continue
            observed = evidence_map.get(goal_id, GoalEvidence(goal_id, 0.5, goal.utility, 0.0))
            if observed.premise_confidence < 0.20 or observed.current_utility < 0.10:
                abandoned.append(goal_id)
                continue
            dependencies = {item.value for item in goal.dependency_ids}
            if not dependencies.issubset(available_ids):
                abandoned.append(goal_id)
                continue
            cost = costs.get(goal_id, 0.25)
            if cost <= 0.0:
                raise FoundationError("goal attention cost must be positive")
            score = (
                0.25 * goal.priority
                + 0.30 * observed.current_utility
                + 0.25 * observed.premise_confidence
                + 0.20 * observed.information_value
                - 0.15 * goal.risk_limit
            ) / cost
            ranked.append((score, goal, cost))
        ranked.sort(key=lambda item: (-item[0], item[1].goal_id.value))
        selected: list[str] = []
        deferred: list[str] = []
        spent = 0.0
        selected_set: set[str] = set()
        pending = list(ranked)
        progress = True
        while pending and progress:
            progress = False
            next_pending: list[tuple[float, GoalSpec, float]] = []
            for score, goal, cost in pending:
                goal_id = goal.goal_id.value
                dependencies = {item.value for item in goal.dependency_ids}
                if dependencies and not dependencies.issubset(selected_set):
                    next_pending.append((score, goal, cost))
                    continue
                if spent + cost <= attention_budget + 1e-12:
                    selected.append(goal_id)
                    selected_set.add(goal_id)
                    spent += cost
                    progress = True
                else:
                    deferred.append(goal_id)
            pending = next_pending
        deferred.extend(goal.goal_id.value for _, goal, _ in pending)
        return GoalPortfolioDecision(
            selected_goal_ids=tuple(selected),
            deferred_goal_ids=tuple(sorted(set(deferred))),
            abandoned_goal_ids=tuple(sorted(set(abandoned))),
            total_attention_cost=round(spent, 12),
        )
