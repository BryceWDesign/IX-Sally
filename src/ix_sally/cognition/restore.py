"""Strict restoration of a complete IX-Sally cognitive system snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.active_memory import (
    ActiveMemoryEntry,
    ActiveMemoryStatus,
    ActiveMemoryStore,
    MemoryLayer,
)
from ix_sally.cognition.curriculum import (
    Curriculum,
    CurriculumLedger,
    CurriculumSplit,
    CurriculumTask,
    CurriculumTrial,
    TrialStatus,
)
from ix_sally.cognition.episodes import (
    CognitiveEpisode,
    EpisodeLedger,
    EpisodeStep,
    EpisodeStepKind,
    EpisodeStepStatus,
)
from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.cognition.learning import (
    LearningLedger,
    LearningOutcome,
    OutcomeStatus,
    SkillProfile,
)
from ix_sally.cognition.metacognition import CapabilityMeasure, SelfModel
from ix_sally.cognition.persistence import CognitiveSnapshot
from ix_sally.cognition.planning import ActionSpec, FactEffect
from ix_sally.cognition.primitives import (
    PrimitiveKind,
    PrimitiveOperation,
    PrimitiveRegistry,
    PrimitiveSpec,
    PrimitiveStatus,
)
from ix_sally.cognition.uncertainty import (
    CalibrationObservation,
    UncertaintyLedger,
)
from ix_sally.cognition.values import CognitiveValue, value_from_payload
from ix_sally.cognition.workspace import (
    CognitiveWorkspace,
    WorkspaceItem,
    WorkspaceItemKind,
    WorkspaceItemStatus,
)
from ix_sally.cognition.world_model import (
    CausalRule,
    FactPattern,
    FactStatus,
    WorldFact,
    WorldModel,
)
from ix_sally.digest import DigestRecord, JsonArray, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError


@dataclass(frozen=True, slots=True)
class RestoredCognitiveState:
    """Fully validated component state reconstructed from a snapshot."""

    workspace: CognitiveWorkspace
    active_memory: ActiveMemoryStore
    world_model: WorldModel
    action_catalog: tuple[ActionSpec, ...]
    learning: LearningLedger
    self_model: SelfModel
    goals: GoalGraph
    uncertainty: UncertaintyLedger
    episodes: EpisodeLedger
    curriculum: CurriculumLedger | None
    primitive_registry: PrimitiveRegistry
    runtime_memories: dict[str, CognitiveValue]
    execution_count: int
    cycle_count: int


def _object(value: JsonValue, *, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise FoundationError(f"snapshot {field} must be an object")
    return value


def _array(value: JsonValue, *, field: str) -> JsonArray:
    if not isinstance(value, list):
        raise FoundationError(f"snapshot {field} must be an array")
    return value


def _text(value: JsonValue, *, field: str) -> str:
    if not isinstance(value, str):
        raise FoundationError(f"snapshot {field} must be text")
    return value


def _integer(value: JsonValue, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise FoundationError(f"snapshot {field} must be an integer")
    return value


def _number(value: JsonValue, *, field: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise FoundationError(f"snapshot {field} must be numeric")
    return float(value)


def _boolean(value: JsonValue, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise FoundationError(f"snapshot {field} must be Boolean")
    return value


def _optional_text(value: JsonValue, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _digest(value: JsonValue, *, field: str) -> DigestRecord:
    payload = _object(value, field=field)
    return DigestRecord(
        algorithm=_text(payload.get("algorithm"), field=f"{field}.algorithm"),
        value=_text(payload.get("value"), field=f"{field}.value"),
    )


def _digests(value: JsonValue, *, field: str) -> tuple[DigestRecord, ...]:
    return tuple(
        _digest(item, field=f"{field}[{index}]")
        for index, item in enumerate(_array(value, field=field))
    )


def _texts(value: JsonValue, *, field: str) -> tuple[str, ...]:
    return tuple(
        _text(item, field=f"{field}[{index}]")
        for index, item in enumerate(_array(value, field=field))
    )


def _restore_pattern(value: JsonValue, *, field: str) -> FactPattern:
    payload = _object(value, field=field)
    return FactPattern.create(
        subject=_text(payload.get("subject"), field=f"{field}.subject"),
        predicate=_text(payload.get("predicate"), field=f"{field}.predicate"),
        value=value_from_payload(payload.get("value")),
    )


def _restore_workspace(value: JsonValue) -> CognitiveWorkspace:
    payload = _object(value, field="workspace")
    items = tuple(
        WorkspaceItem.create(
            item_id=_text(item_payload.get("item_id"), field="workspace.item_id"),
            kind=WorkspaceItemKind(
                _text(item_payload.get("kind"), field="workspace.kind")
            ),
            content=_text(item_payload.get("content"), field="workspace.content"),
            confidence=_number(
                item_payload.get("confidence"),
                field="workspace.confidence",
            ),
            salience=_number(item_payload.get("salience"), field="workspace.salience"),
            status=WorkspaceItemStatus(
                _text(item_payload.get("status"), field="workspace.status")
            ),
            evidence_digests=_digests(
                item_payload.get("evidence_digests"),
                field="workspace.evidence_digests",
            ),
            parent_ids=_texts(
                item_payload.get("parent_ids"),
                field="workspace.parent_ids",
            ),
        )
        for item_payload in (
            _object(item, field="workspace.items[]")
            for item in _array(payload.get("items"), field="workspace.items")
        )
    )
    return CognitiveWorkspace(
        items=items,
        capacity=_integer(payload.get("capacity"), field="workspace.capacity"),
    )


def _restore_memory(value: JsonValue) -> ActiveMemoryStore:
    payload = _object(value, field="active_memory")
    entries = tuple(
        ActiveMemoryEntry.create(
            memory_id=_text(item.get("memory_id"), field="memory.memory_id"),
            layer=MemoryLayer(_text(item.get("layer"), field="memory.layer")),
            content=_text(item.get("content"), field="memory.content"),
            confidence=_number(item.get("confidence"), field="memory.confidence"),
            status=ActiveMemoryStatus(
                _text(item.get("status"), field="memory.status")
            ),
            sequence=_integer(item.get("sequence"), field="memory.sequence"),
            evidence_digests=_digests(
                item.get("evidence_digests"),
                field="memory.evidence_digests",
            ),
            source_ids=_texts(item.get("source_ids"), field="memory.source_ids"),
            tags=_texts(item.get("tags"), field="memory.tags"),
            reason=_optional_text(item.get("reason"), field="memory.reason"),
        )
        for item in (
            _object(entry, field="active_memory.entries[]")
            for entry in _array(payload.get("entries"), field="active_memory.entries")
        )
    )
    return ActiveMemoryStore(entries)


def _restore_world(value: JsonValue) -> WorldModel:
    payload = _object(value, field="world_model")
    facts = tuple(
        WorldFact.create(
            fact_id=_text(item.get("fact_id"), field="world.fact_id"),
            subject=_text(item.get("subject"), field="world.subject"),
            predicate=_text(item.get("predicate"), field="world.predicate"),
            value=value_from_payload(item.get("value")),
            status=FactStatus(_text(item.get("status"), field="world.status")),
            confidence=_number(item.get("confidence"), field="world.confidence"),
            evidence_digests=_digests(
                item.get("evidence_digests"),
                field="world.evidence_digests",
            ),
            derived_from=_texts(
                item.get("derived_from"),
                field="world.derived_from",
            ),
        )
        for item in (
            _object(fact, field="world_model.facts[]")
            for fact in _array(payload.get("facts"), field="world_model.facts")
        )
    )
    rules = tuple(
        CausalRule.create(
            rule_id=_text(item.get("rule_id"), field="world.rule_id"),
            conditions=tuple(
                _restore_pattern(condition, field="world.rule.conditions[]")
                for condition in _array(
                    item.get("conditions"),
                    field="world.rule.conditions",
                )
            ),
            effect_subject=_text(
                item.get("effect_subject"),
                field="world.effect_subject",
            ),
            effect_predicate=_text(
                item.get("effect_predicate"),
                field="world.effect_predicate",
            ),
            effect_value=value_from_payload(item.get("effect_value")),
            confidence=_number(item.get("confidence"), field="world.rule.confidence"),
            evidence_digests=_digests(
                item.get("evidence_digests"),
                field="world.rule.evidence_digests",
            ),
        )
        for item in (
            _object(rule, field="world_model.rules[]")
            for rule in _array(payload.get("rules"), field="world_model.rules")
        )
    )
    return WorldModel(facts=facts, rules=rules)


def _restore_actions(value: JsonValue) -> tuple[ActionSpec, ...]:
    return tuple(
        ActionSpec.create(
            action_id=_text(item.get("action_id"), field="action.action_id"),
            description=_text(item.get("description"), field="action.description"),
            preconditions=tuple(
                _restore_pattern(condition, field="action.preconditions[]")
                for condition in _array(
                    item.get("preconditions"),
                    field="action.preconditions",
                )
            ),
            effects=tuple(
                FactEffect.create(
                    subject=_text(effect.get("subject"), field="effect.subject"),
                    predicate=_text(
                        effect.get("predicate"),
                        field="effect.predicate",
                    ),
                    value=value_from_payload(effect.get("value")),
                )
                for effect in (
                    _object(raw, field="action.effects[]")
                    for raw in _array(item.get("effects"), field="action.effects")
                )
            ),
            cost=_number(item.get("cost"), field="action.cost"),
            risk=_number(item.get("risk"), field="action.risk"),
            authority_required=_boolean(
                item.get("authority_required"),
                field="action.authority_required",
            ),
        )
        for item in (
            _object(action, field="action_catalog[]")
            for action in _array(value, field="action_catalog")
        )
    )


def _restore_learning(value: JsonValue) -> LearningLedger:
    payload = _object(value, field="learning")
    outcomes = tuple(
        LearningOutcome.create(
            outcome_id=_text(item.get("outcome_id"), field="learning.outcome_id"),
            skill_id=_text(item.get("skill_id"), field="learning.skill_id"),
            task_family=_text(
                item.get("task_family"),
                field="learning.task_family",
            ),
            status=OutcomeStatus(
                _text(item.get("status"), field="learning.status")
            ),
            score=_number(item.get("score"), field="learning.score"),
            evidence_digest=_digest(
                item.get("evidence_digest"),
                field="learning.evidence_digest",
            ),
            notes=_text(item.get("notes"), field="learning.notes"),
        )
        for item in (
            _object(outcome, field="learning.outcomes[]")
            for outcome in _array(payload.get("outcomes"), field="learning.outcomes")
        )
    )
    profiles = tuple(
        SkillProfile(
            skill_id=CanonicalKey.from_text(
                _text(item.get("skill_id"), field="learning.profile.skill_id"),
                field_name="skill_id",
            ),
            attempts=_integer(
                item.get("attempts"),
                field="learning.profile.attempts",
            ),
            successes=_integer(
                item.get("successes"),
                field="learning.profile.successes",
            ),
            mean_score=_number(
                item.get("mean_score"),
                field="learning.profile.mean_score",
            ),
            confidence=_number(
                item.get("confidence"),
                field="learning.profile.confidence",
            ),
            last_outcome_digest=(
                None
                if item.get("last_outcome_digest") is None
                else _digest(
                    item.get("last_outcome_digest"),
                    field="learning.profile.last_outcome_digest",
                )
            ),
        )
        for item in (
            _object(profile, field="learning.profiles[]")
            for profile in _array(payload.get("profiles"), field="learning.profiles")
        )
    )
    return LearningLedger(outcomes=outcomes, profiles=profiles)


def _restore_self_model(value: JsonValue) -> SelfModel:
    payload = _object(value, field="self_model")
    return SelfModel(
        tuple(
            CapabilityMeasure.create(
                capability_id=_text(
                    item.get("capability_id"),
                    field="self_model.capability_id",
                ),
                score=_number(item.get("score"), field="self_model.score"),
                evidence_digests=_digests(
                    item.get("evidence_digests"),
                    field="self_model.evidence_digests",
                ),
                limitation=_text(
                    item.get("limitation"),
                    field="self_model.limitation",
                ),
            )
            for item in (
                _object(measure, field="self_model.measures[]")
                for measure in _array(
                    payload.get("measures"),
                    field="self_model.measures",
                )
            )
        )
    )


def _restore_goals(value: JsonValue) -> GoalGraph:
    payload = _object(value, field="goals")
    goals = tuple(
        GoalSpec.create(
            goal_id=_text(item.get("goal_id"), field="goals.goal_id"),
            description=_text(
                item.get("description"),
                field="goals.description",
            ),
            desired_state=_restore_pattern(
                item.get("desired_state"),
                field="goals.desired_state",
            ),
            priority=_number(item.get("priority"), field="goals.priority"),
            utility=_number(item.get("utility"), field="goals.utility"),
            risk_limit=_number(
                item.get("risk_limit"),
                field="goals.risk_limit",
            ),
            status=GoalStatus(_text(item.get("status"), field="goals.status")),
            dependency_ids=_texts(
                item.get("dependency_ids"),
                field="goals.dependency_ids",
            ),
            authority_required=_boolean(
                item.get("authority_required"),
                field="goals.authority_required",
            ),
            evidence_digests=_digests(
                item.get("evidence_digests"),
                field="goals.evidence_digests",
            ),
            status_reason=_optional_text(
                item.get("status_reason"),
                field="goals.status_reason",
            ),
        )
        for item in (
            _object(goal, field="goals.goals[]")
            for goal in _array(payload.get("goals"), field="goals.goals")
        )
    )
    return GoalGraph.create(goals)


def _restore_uncertainty(value: JsonValue) -> UncertaintyLedger:
    payload = _object(value, field="uncertainty")
    observations = tuple(
        CalibrationObservation.create(
            observation_id=_text(
                item.get("observation_id"),
                field="uncertainty.observation_id",
            ),
            capability_id=_text(
                item.get("capability_id"),
                field="uncertainty.capability_id",
            ),
            predicted_probability=_number(
                item.get("predicted_probability"),
                field="uncertainty.predicted_probability",
            ),
            observed=_boolean(
                item.get("observed"),
                field="uncertainty.observed",
            ),
            evidence_digest=_digest(
                item.get("evidence_digest"),
                field="uncertainty.evidence_digest",
            ),
            context=_text(item.get("context"), field="uncertainty.context"),
        )
        for item in (
            _object(observation, field="uncertainty.observations[]")
            for observation in _array(
                payload.get("observations"),
                field="uncertainty.observations",
            )
        )
    )
    return UncertaintyLedger.create(observations)


def _restore_episodes(value: JsonValue) -> EpisodeLedger:
    payload = _object(value, field="episodes")
    episodes = tuple(
        CognitiveEpisode.create(
            episode_id=_text(item.get("episode_id"), field="episodes.episode_id"),
            sequence=_integer(item.get("sequence"), field="episodes.sequence"),
            task=_text(item.get("task"), field="episodes.task"),
            initial_state_digest=_digest(
                item.get("initial_state_digest"),
                field="episodes.initial_state_digest",
            ),
            final_state_digest=_digest(
                item.get("final_state_digest"),
                field="episodes.final_state_digest",
            ),
            steps=tuple(
                EpisodeStep.create(
                    index=_integer(step.get("index"), field="episodes.step.index"),
                    kind=EpisodeStepKind(
                        _text(step.get("kind"), field="episodes.step.kind")
                    ),
                    status=EpisodeStepStatus(
                        _text(step.get("status"), field="episodes.step.status")
                    ),
                    detail=_text(
                        step.get("detail"),
                        field="episodes.step.detail",
                    ),
                    input_digests=_digests(
                        step.get("input_digests"),
                        field="episodes.step.input_digests",
                    ),
                    output_digests=_digests(
                        step.get("output_digests"),
                        field="episodes.step.output_digests",
                    ),
                )
                for step in (
                    _object(raw_step, field="episodes.steps[]")
                    for raw_step in _array(
                        item.get("steps"),
                        field="episodes.steps",
                    )
                )
            ),
            previous_episode_digest=(
                None
                if item.get("previous_episode_digest") is None
                else _digest(
                    item.get("previous_episode_digest"),
                    field="episodes.previous_episode_digest",
                )
            ),
        )
        for item in (
            _object(episode, field="episodes.episodes[]")
            for episode in _array(payload.get("episodes"), field="episodes.episodes")
        )
    )
    return EpisodeLedger.create(episodes)


def _restore_curriculum(value: JsonValue) -> CurriculumLedger | None:
    if value is None:
        return None
    payload = _object(value, field="curriculum")
    curriculum_payload = _object(
        payload.get("curriculum"),
        field="curriculum.curriculum",
    )
    tasks = tuple(
        CurriculumTask.create(
            task_id=_text(item.get("task_id"), field="curriculum.task_id"),
            family=_text(item.get("family"), field="curriculum.family"),
            description=_text(
                item.get("description"),
                field="curriculum.description",
            ),
            difficulty=_integer(
                item.get("difficulty"),
                field="curriculum.difficulty",
            ),
            split=CurriculumSplit(
                _text(item.get("split"), field="curriculum.split")
            ),
            prerequisite_ids=_texts(
                item.get("prerequisite_ids"),
                field="curriculum.prerequisite_ids",
            ),
            required_capabilities=_texts(
                item.get("required_capabilities"),
                field="curriculum.required_capabilities",
            ),
            pass_threshold=_number(
                item.get("pass_threshold"),
                field="curriculum.pass_threshold",
            ),
        )
        for item in (
            _object(task, field="curriculum.tasks[]")
            for task in _array(
                curriculum_payload.get("tasks"),
                field="curriculum.tasks",
            )
        )
    )
    curriculum = Curriculum.create(tasks)
    trials = tuple(
        CurriculumTrial.create(
            trial_id=_text(item.get("trial_id"), field="curriculum.trial_id"),
            task_id=_text(item.get("task_id"), field="curriculum.trial_task_id"),
            sequence=_integer(
                item.get("sequence"),
                field="curriculum.trial_sequence",
            ),
            score=_number(item.get("score"), field="curriculum.trial_score"),
            status=TrialStatus(
                _text(item.get("status"), field="curriculum.trial_status")
            ),
            evidence_digest=_digest(
                item.get("evidence_digest"),
                field="curriculum.trial_evidence",
            ),
            notes=_text(item.get("notes"), field="curriculum.trial_notes"),
        )
        for item in (
            _object(trial, field="curriculum.trials[]")
            for trial in _array(payload.get("trials"), field="curriculum.trials")
        )
    )
    return CurriculumLedger(curriculum, trials)


def _restore_primitives(value: JsonValue) -> PrimitiveRegistry:
    payload = _object(value, field="primitive_registry")
    return PrimitiveRegistry.create(
        PrimitiveSpec.create(
            primitive_id=_text(item.get("primitive_id"), field="primitive.id"),
            kind=PrimitiveKind(_text(item.get("kind"), field="primitive.kind")),
            operation=PrimitiveOperation(
                _text(item.get("operation"), field="primitive.operation")
            ),
            arity=_integer(item.get("arity"), field="primitive.arity"),
            status=PrimitiveStatus(
                _text(item.get("status"), field="primitive.status")
            ),
            description=_text(
                item.get("description"),
                field="primitive.description",
            ),
            grounding_digests=_digests(
                item.get("grounding_digests"),
                field="primitive.grounding_digests",
            ),
            validation_digests=_digests(
                item.get("validation_digests"),
                field="primitive.validation_digests",
            ),
            reason=_optional_text(item.get("reason"), field="primitive.reason"),
        )
        for item in (
            _object(primitive, field="primitive_registry.primitives[]")
            for primitive in _array(
                payload.get("primitives"),
                field="primitive_registry.primitives",
            )
        )
    )


def restore_system_state(snapshot: CognitiveSnapshot) -> RestoredCognitiveState:
    """Restore and revalidate every serialized IX-Sally cognitive subsystem."""
    state = snapshot.state
    if _text(state.get("repository"), field="repository") != "IX-Sally":
        raise FoundationError("snapshot state repository mismatch")
    runtime_memories: dict[str, CognitiveValue] = {}
    for raw in _array(state.get("runtime_memories"), field="runtime_memories"):
        item = _object(raw, field="runtime_memories[]")
        name = _text(item.get("name"), field="runtime_memories.name")
        if name in runtime_memories:
            raise FoundationError(f"duplicate runtime memory name: {name}")
        runtime_memories[name] = value_from_payload(item.get("value"))
    return RestoredCognitiveState(
        workspace=_restore_workspace(state.get("workspace")),
        active_memory=_restore_memory(state.get("active_memory")),
        world_model=_restore_world(state.get("world_model")),
        action_catalog=_restore_actions(state.get("action_catalog")),
        learning=_restore_learning(state.get("learning")),
        self_model=_restore_self_model(state.get("self_model")),
        goals=_restore_goals(state.get("goals")),
        uncertainty=_restore_uncertainty(state.get("uncertainty")),
        episodes=_restore_episodes(state.get("episodes")),
        curriculum=_restore_curriculum(state.get("curriculum")),
        primitive_registry=_restore_primitives(state.get("primitive_registry")),
        runtime_memories=runtime_memories,
        execution_count=_integer(
            state.get("execution_count"),
            field="execution_count",
        ),
        cycle_count=_integer(state.get("cycle_count"), field="cycle_count"),
    )
