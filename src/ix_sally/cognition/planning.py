"""Deterministic goal planning, authority gating, and simulated execution."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern, FactStatus, WorldFact, WorldModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text

StateKey = tuple[str, str]
StateMap = dict[StateKey, CognitiveValue]


class PlanStatus(StrEnum):
    """Outcome of bounded deterministic planning."""

    FOUND = "found"
    ALREADY_SATISFIED = "already_satisfied"
    NOT_FOUND = "not_found"
    SEARCH_LIMIT = "search_limit"


class ExecutionPermission(StrEnum):
    """Authority result for a simulated plan step."""

    ALLOWED = "allowed"
    REQUIRES_HUMAN = "requires_human"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class FactEffect:
    """One exact state change produced by a planning action."""

    subject: CanonicalKey
    predicate: CanonicalKey
    value: CognitiveValue

    @classmethod
    def create(
        cls,
        *,
        subject: str,
        predicate: str,
        value: CognitiveValue,
    ) -> FactEffect:
        """Create one canonical state effect."""
        return cls(
            subject=CanonicalKey.from_text(subject, field_name="subject"),
            predicate=CanonicalKey.from_text(predicate, field_name="predicate"),
            value=value,
        )

    def key(self) -> StateKey:
        """Return the affected state key."""
        return (self.subject.value, self.predicate.value)

    def to_payload(self) -> JsonObject:
        """Return a canonical effect payload."""
        return {
            "subject": self.subject.value,
            "predicate": self.predicate.value,
            "value": self.value.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """One declarative action with exact preconditions, effects, cost, and risk."""

    action_id: CanonicalKey
    description: str
    preconditions: tuple[FactPattern, ...]
    effects: tuple[FactEffect, ...]
    cost: float
    risk: float
    authority_required: bool = False

    @classmethod
    def create(
        cls,
        *,
        action_id: str,
        description: str,
        preconditions: Iterable[FactPattern],
        effects: Iterable[FactEffect],
        cost: float,
        risk: float,
        authority_required: bool = False,
    ) -> ActionSpec:
        """Create a planning action without executable side effects."""
        normalized_effects = tuple(effects)
        if not normalized_effects:
            raise FoundationError("planning action requires at least one effect")
        if cost < 0:
            raise FoundationError("planning action cost must not be negative")
        if not 0.0 <= risk <= 1.0:
            raise FoundationError("planning action risk must be between 0 and 1")
        return cls(
            action_id=CanonicalKey.from_text(action_id, field_name="action_id"),
            description=require_text(description, field_name="description"),
            preconditions=tuple(preconditions),
            effects=normalized_effects,
            cost=cost,
            risk=risk,
            authority_required=authority_required,
        )

    def applicable(self, state: Mapping[StateKey, CognitiveValue]) -> bool:
        """Return whether all exact preconditions hold in a plain planning state."""
        return all(
            state.get((condition.subject.value, condition.predicate.value))
            == condition.value
            for condition in self.preconditions
        )

    def apply(self, state: Mapping[StateKey, CognitiveValue]) -> StateMap:
        """Return a copied state with all declared effects applied."""
        if not self.applicable(state):
            raise FoundationError(
                f"action preconditions are not satisfied: {self.action_id.value}"
            )
        updated = dict(state)
        for effect in self.effects:
            updated[effect.key()] = effect.value
        return updated

    def to_payload(self) -> JsonObject:
        """Return a canonical action payload."""
        preconditions: JsonArray = [
            condition.to_payload() for condition in self.preconditions
        ]
        effects: JsonArray = [effect.to_payload() for effect in self.effects]
        return {
            "action_id": self.action_id.value,
            "description": self.description,
            "preconditions": preconditions,
            "effects": effects,
            "cost": self.cost,
            "risk": self.risk,
            "authority_required": self.authority_required,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic action identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class Plan:
    """One bounded plan and its complete search result."""

    status: PlanStatus
    goal: FactPattern
    actions: tuple[ActionSpec, ...]
    explored_states: int
    total_cost: float
    aggregate_risk: float
    reason: str

    def __post_init__(self) -> None:
        """Require plan metrics and status to remain coherent."""
        if self.explored_states < 0:
            raise FoundationError("plan explored_states must not be negative")
        if self.total_cost < 0:
            raise FoundationError("plan total_cost must not be negative")
        if not 0.0 <= self.aggregate_risk <= 1.0:
            raise FoundationError("plan aggregate_risk must be between 0 and 1")
        require_text(self.reason, field_name="reason")
        if self.status is PlanStatus.FOUND and not self.actions:
            raise FoundationError("found plan requires actions")
        if self.status is not PlanStatus.FOUND and self.actions:
            raise FoundationError("non-found plan must not contain actions")

    def requires_human_authority(self) -> bool:
        """Return whether any action crosses a human authority boundary."""
        return any(action.authority_required for action in self.actions)

    def to_payload(self) -> JsonObject:
        """Return a canonical plan receipt."""
        actions: JsonArray = [action.to_payload() for action in self.actions]
        return {
            "status": self.status.value,
            "goal": self.goal.to_payload(),
            "actions": actions,
            "explored_states": self.explored_states,
            "total_cost": self.total_cost,
            "aggregate_risk": self.aggregate_risk,
            "requires_human_authority": self.requires_human_authority(),
            "reason": self.reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic plan identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class DeterministicPlanner:
    """Breadth-first planner with stable ordering and an explicit search bound."""

    max_explored_states: int = 5_000
    max_depth: int = 24

    def __post_init__(self) -> None:
        """Require positive planning bounds."""
        if self.max_explored_states <= 0 or self.max_depth <= 0:
            raise FoundationError("planner bounds must be positive")

    def plan(
        self,
        *,
        world_model: WorldModel,
        actions: Iterable[ActionSpec],
        goal: FactPattern,
    ) -> Plan:
        """Search for the shortest action sequence satisfying an exact goal."""
        action_catalog = tuple(sorted(actions, key=lambda action: action.action_id.value))
        identifiers = [action.action_id.value for action in action_catalog]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("planner action catalog contains duplicate identifiers")
        initial = {
            key: fact.value
            for key, fact in world_model.state().items()
            if fact.status is not FactStatus.CONTRADICTED
        }
        if self._goal_satisfied(initial, goal):
            return Plan(
                status=PlanStatus.ALREADY_SATISFIED,
                goal=goal,
                actions=(),
                explored_states=0,
                total_cost=0.0,
                aggregate_risk=0.0,
                reason="Goal is already satisfied by the current world model.",
            )
        queue: deque[tuple[StateMap, tuple[ActionSpec, ...]]] = deque([(initial, ())])
        visited = {self._state_key(initial)}
        explored = 0
        while queue:
            state, path = queue.popleft()
            explored += 1
            if explored > self.max_explored_states:
                return Plan(
                    status=PlanStatus.SEARCH_LIMIT,
                    goal=goal,
                    actions=(),
                    explored_states=explored - 1,
                    total_cost=0.0,
                    aggregate_risk=0.0,
                    reason="Planner reached the configured state-search limit.",
                )
            if len(path) >= self.max_depth:
                continue
            for action in action_catalog:
                if not action.applicable(state):
                    continue
                next_state = action.apply(state)
                key = self._state_key(next_state)
                if key in visited:
                    continue
                visited.add(key)
                next_path = (*path, action)
                if self._goal_satisfied(next_state, goal):
                    return self._found_plan(
                        goal=goal,
                        path=next_path,
                        explored=explored,
                    )
                queue.append((next_state, next_path))
        return Plan(
            status=PlanStatus.NOT_FOUND,
            goal=goal,
            actions=(),
            explored_states=explored,
            total_cost=0.0,
            aggregate_risk=0.0,
            reason="No plan was found within the declared action model and bounds.",
        )

    def _found_plan(
        self,
        *,
        goal: FactPattern,
        path: tuple[ActionSpec, ...],
        explored: int,
    ) -> Plan:
        """Create a stable found-plan receipt."""
        total_cost = round(sum(action.cost for action in path), 12)
        survival = 1.0
        for action in path:
            survival *= 1.0 - action.risk
        aggregate_risk = round(1.0 - survival, 12)
        return Plan(
            status=PlanStatus.FOUND,
            goal=goal,
            actions=path,
            explored_states=explored,
            total_cost=total_cost,
            aggregate_risk=aggregate_risk,
            reason="A shortest deterministic plan was found.",
        )

    def _goal_satisfied(
        self,
        state: Mapping[StateKey, CognitiveValue],
        goal: FactPattern,
    ) -> bool:
        """Return whether the plain state exactly satisfies the goal."""
        return state.get((goal.subject.value, goal.predicate.value)) == goal.value

    def _state_key(
        self,
        state: Mapping[StateKey, CognitiveValue],
    ) -> tuple[tuple[str, str, str, object], ...]:
        """Return a stable hashable identity for one planning state."""
        return tuple(
            sorted(
                (
                    subject,
                    predicate,
                    value.value_type.value,
                    value.value,
                )
                for (subject, predicate), value in state.items()
            )
        )


@dataclass(frozen=True, slots=True)
class PlanExecutionReceipt:
    """Receipt from a simulated, authority-aware plan execution."""

    plan_digest: DigestRecord
    permission: ExecutionPermission
    applied_action_ids: tuple[CanonicalKey, ...]
    resulting_model: WorldModel
    reason: str

    def to_payload(self) -> JsonObject:
        """Return a canonical execution receipt."""
        actions: JsonArray = [action_id.value for action_id in self.applied_action_ids]
        return {
            "plan_digest": {
                "algorithm": self.plan_digest.algorithm,
                "value": self.plan_digest.value,
            },
            "permission": self.permission.value,
            "applied_action_ids": actions,
            "resulting_model_digest": {
                "algorithm": self.resulting_model.digest().algorithm,
                "value": self.resulting_model.digest().value,
            },
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PlanSimulator:
    """Apply plan effects only to a copied world model, never to the outside world."""

    def execute(
        self,
        plan: Plan,
        *,
        world_model: WorldModel,
        human_approved: bool = False,
    ) -> PlanExecutionReceipt:
        """Simulate a found plan with explicit human-boundary enforcement."""
        if plan.status is not PlanStatus.FOUND:
            return PlanExecutionReceipt(
                plan_digest=plan.digest(),
                permission=ExecutionPermission.DENIED,
                applied_action_ids=(),
                resulting_model=world_model,
                reason="Only a found plan may be simulated.",
            )
        if plan.requires_human_authority() and not human_approved:
            return PlanExecutionReceipt(
                plan_digest=plan.digest(),
                permission=ExecutionPermission.REQUIRES_HUMAN,
                applied_action_ids=(),
                resulting_model=world_model,
                reason="Plan crosses a declared human authority boundary.",
            )
        state = {
            key: fact.value
            for key, fact in world_model.state().items()
            if fact.status is not FactStatus.CONTRADICTED
        }
        model = world_model
        applied: list[CanonicalKey] = []
        for index, action in enumerate(plan.actions):
            state = action.apply(state)
            for effect_index, effect in enumerate(action.effects):
                model = model.observe(
                    WorldFact.create(
                        fact_id=(
                            f"simulated-{plan.digest().value[:12]}-"
                            f"{index}-{effect_index}"
                        ),
                        subject=effect.subject.value,
                        predicate=effect.predicate.value,
                        value=effect.value,
                        status=FactStatus.HYPOTHETICAL,
                        confidence=1.0 - action.risk,
                        evidence_digests=(action.digest(),),
                    )
                )
            applied.append(action.action_id)
        return PlanExecutionReceipt(
            plan_digest=plan.digest(),
            permission=ExecutionPermission.ALLOWED,
            applied_action_ids=tuple(applied),
            resulting_model=model,
            reason="Plan effects were applied to an isolated simulated world model.",
        )
