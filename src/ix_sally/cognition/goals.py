"""Goal graphs, dependency resolution, and explicit executive-state transitions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.world_model import FactPattern, WorldModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class GoalStatus(StrEnum):
    """Lifecycle state of one cognitive goal."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    BLOCKED = "blocked"
    SATISFIED = "satisfied"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class GoalSpec:
    """One bounded goal with dependencies, utility, risk, and authority metadata."""

    goal_id: CanonicalKey
    description: str
    desired_state: FactPattern
    priority: float
    utility: float
    risk_limit: float
    status: GoalStatus
    dependency_ids: tuple[CanonicalKey, ...] = ()
    authority_required: bool = False
    evidence_digests: tuple[DigestRecord, ...] = ()
    status_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        goal_id: str,
        description: str,
        desired_state: FactPattern,
        priority: float,
        utility: float,
        risk_limit: float,
        status: GoalStatus = GoalStatus.PROPOSED,
        dependency_ids: Iterable[str] = (),
        authority_required: bool = False,
        evidence_digests: Iterable[DigestRecord] = (),
        status_reason: str | None = None,
    ) -> GoalSpec:
        """Create a goal without inferring authority or satisfaction."""
        for field_name, value in (
            ("priority", priority),
            ("utility", utility),
            ("risk_limit", risk_limit),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"goal {field_name} must be between 0 and 1")
        evidence = tuple(evidence_digests)
        for digest in evidence:
            digest.require_algorithm("sha256")
        reason = require_optional_text(status_reason, field_name="status_reason")
        if status in {GoalStatus.BLOCKED, GoalStatus.ABANDONED} and reason is None:
            raise FoundationError("blocked or abandoned goals require a status reason")
        dependencies = tuple(
            sorted(
                {
                    CanonicalKey.from_text(item, field_name="dependency_id")
                    for item in dependency_ids
                },
                key=lambda item: item.value,
            )
        )
        canonical_id = CanonicalKey.from_text(goal_id, field_name="goal_id")
        if canonical_id in dependencies:
            raise FoundationError("goal must not depend on itself")
        return cls(
            goal_id=canonical_id,
            description=require_text(description, field_name="description"),
            desired_state=desired_state,
            priority=priority,
            utility=utility,
            risk_limit=risk_limit,
            status=status,
            dependency_ids=dependencies,
            authority_required=authority_required,
            evidence_digests=evidence,
            status_reason=reason,
        )

    def with_status(self, status: GoalStatus, *, reason: str | None = None) -> GoalSpec:
        """Return the same goal with an explicit lifecycle transition."""
        return GoalSpec.create(
            goal_id=self.goal_id.value,
            description=self.description,
            desired_state=self.desired_state,
            priority=self.priority,
            utility=self.utility,
            risk_limit=self.risk_limit,
            status=status,
            dependency_ids=(item.value for item in self.dependency_ids),
            authority_required=self.authority_required,
            evidence_digests=self.evidence_digests,
            status_reason=reason,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical goal payload."""
        evidence: JsonArray = [
            {"algorithm": item.algorithm, "value": item.value} for item in self.evidence_digests
        ]
        dependencies: JsonArray = [item.value for item in self.dependency_ids]
        return {
            "goal_id": self.goal_id.value,
            "description": self.description,
            "desired_state": self.desired_state.to_payload(),
            "priority": self.priority,
            "utility": self.utility,
            "risk_limit": self.risk_limit,
            "status": self.status.value,
            "dependency_ids": dependencies,
            "authority_required": self.authority_required,
            "evidence_digests": evidence,
            "status_reason": self.status_reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic identity for this goal state."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class GoalGraph:
    """Immutable dependency graph for bounded cognitive goals."""

    goals: tuple[GoalSpec, ...] = ()

    @classmethod
    def create(cls, goals: Iterable[GoalSpec] = ()) -> GoalGraph:
        """Create a graph and reject missing dependencies or dependency cycles."""
        normalized = tuple(sorted(goals, key=lambda item: item.goal_id.value))
        identifiers = [item.goal_id.value for item in normalized]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("goal graph contains duplicate identifiers")
        known = set(identifiers)
        for goal in normalized:
            missing = sorted(
                dependency.value
                for dependency in goal.dependency_ids
                if dependency.value not in known
            )
            if missing:
                raise FoundationError(
                    f"goal {goal.goal_id.value} has unknown dependencies: {', '.join(missing)}"
                )
        graph = cls(normalized)
        graph._require_acyclic()
        return graph

    def _require_acyclic(self) -> None:
        """Reject dependency cycles with deterministic diagnostics."""
        by_id = {goal.goal_id.value: goal for goal in self.goals}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(goal_id: str, trail: tuple[str, ...]) -> None:
            if goal_id in visited:
                return
            if goal_id in visiting:
                cycle = " -> ".join((*trail, goal_id))
                raise FoundationError(f"goal dependency cycle detected: {cycle}")
            visiting.add(goal_id)
            goal = by_id[goal_id]
            for dependency in goal.dependency_ids:
                visit(dependency.value, (*trail, goal_id))
            visiting.remove(goal_id)
            visited.add(goal_id)

        for goal_id in sorted(by_id):
            visit(goal_id, ())

    def require(self, goal_id: str) -> GoalSpec:
        """Return one goal by canonical identifier."""
        requested = CanonicalKey.from_text(goal_id, field_name="goal_id")
        for goal in self.goals:
            if goal.goal_id == requested:
                return goal
        raise FoundationError(f"unknown goal id: {requested.value}")

    def add(self, goal: GoalSpec) -> GoalGraph:
        """Return a graph with one unique goal added."""
        return GoalGraph.create((*self.goals, goal))

    def update_status(
        self,
        goal_id: str,
        status: GoalStatus,
        *,
        reason: str | None = None,
    ) -> GoalGraph:
        """Return a graph with one explicit goal-state transition."""
        requested = self.require(goal_id)
        updated = requested.with_status(status, reason=reason)
        return GoalGraph.create(updated if goal == requested else goal for goal in self.goals)

    def dependencies_satisfied(self, goal: GoalSpec) -> bool:
        """Return whether all dependency goals are explicitly satisfied."""
        by_id = {item.goal_id: item for item in self.goals}
        return all(
            by_id[dependency].status is GoalStatus.SATISFIED for dependency in goal.dependency_ids
        )

    def selectable(self, world_model: WorldModel) -> tuple[GoalSpec, ...]:
        """Return goals eligible for executive selection in stable priority order."""
        state = world_model.state()
        candidates = []
        for goal in self.goals:
            if goal.status not in {GoalStatus.PROPOSED, GoalStatus.ACTIVE}:
                continue
            if goal.desired_state.matches(state):
                continue
            if not self.dependencies_satisfied(goal):
                continue
            candidates.append(goal)
        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    -item.priority,
                    -item.utility,
                    item.goal_id.value,
                ),
            )
        )

    def select(self, world_model: WorldModel) -> GoalSpec | None:
        """Return the highest-priority currently selectable goal."""
        candidates = self.selectable(world_model)
        return candidates[0] if candidates else None

    def reconcile(self, world_model: WorldModel) -> GoalGraph:
        """Mark goals satisfied only when their desired state is present."""
        state = world_model.state()
        reconciled = tuple(
            goal.with_status(GoalStatus.SATISFIED)
            if goal.status not in {GoalStatus.ABANDONED, GoalStatus.SATISFIED}
            and goal.desired_state.matches(state)
            else goal
            for goal in self.goals
        )
        return GoalGraph.create(reconciled)

    def to_payload(self) -> JsonObject:
        """Return a canonical goal-graph payload."""
        goals: JsonArray = [goal.to_payload() for goal in self.goals]
        return {"goals": goals}

    def digest(self) -> DigestRecord:
        """Return a deterministic graph identity."""
        return DigestRecord.from_payload(self.to_payload())
