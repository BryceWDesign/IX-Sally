"""Deterministic curricula, held-out tasks, and progression evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class CurriculumSplit(StrEnum):
    """Task split used to distinguish practice from transfer evaluation."""

    TRAINING = "training"
    VALIDATION = "validation"
    HELD_OUT = "held_out"


class TrialStatus(StrEnum):
    """Observed result of one curriculum task attempt."""

    PASSED = "passed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CurriculumTask:
    """One bounded task with explicit prerequisites and evaluation split."""

    task_id: CanonicalKey
    family: CanonicalKey
    description: str
    difficulty: int
    split: CurriculumSplit
    prerequisite_ids: tuple[CanonicalKey, ...] = ()
    required_capabilities: tuple[CanonicalKey, ...] = ()
    pass_threshold: float = 0.8

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        family: str,
        description: str,
        difficulty: int,
        split: CurriculumSplit,
        prerequisite_ids: Iterable[str] = (),
        required_capabilities: Iterable[str] = (),
        pass_threshold: float = 0.8,
    ) -> CurriculumTask:
        """Create a curriculum task with measurable success criteria."""
        if not 1 <= difficulty <= 10:
            raise FoundationError("curriculum difficulty must be between 1 and 10")
        if not 0.0 <= pass_threshold <= 1.0:
            raise FoundationError("curriculum pass threshold must be between 0 and 1")
        canonical_id = CanonicalKey.from_text(task_id, field_name="task_id")
        prerequisites = tuple(
            sorted(
                {
                    CanonicalKey.from_text(item, field_name="prerequisite_id")
                    for item in prerequisite_ids
                },
                key=lambda item: item.value,
            )
        )
        if canonical_id in prerequisites:
            raise FoundationError("curriculum task must not depend on itself")
        capabilities = tuple(
            sorted(
                {
                    CanonicalKey.from_text(item, field_name="required_capability")
                    for item in required_capabilities
                },
                key=lambda item: item.value,
            )
        )
        return cls(
            task_id=canonical_id,
            family=CanonicalKey.from_text(family, field_name="family"),
            description=require_text(description, field_name="description"),
            difficulty=difficulty,
            split=split,
            prerequisite_ids=prerequisites,
            required_capabilities=capabilities,
            pass_threshold=pass_threshold,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical task payload."""
        prerequisites: JsonArray = [item.value for item in self.prerequisite_ids]
        capabilities: JsonArray = [item.value for item in self.required_capabilities]
        return {
            "task_id": self.task_id.value,
            "family": self.family.value,
            "description": self.description,
            "difficulty": self.difficulty,
            "split": self.split.value,
            "prerequisite_ids": prerequisites,
            "required_capabilities": capabilities,
            "pass_threshold": self.pass_threshold,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic task identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class Curriculum:
    """Immutable acyclic graph of measurable tasks."""

    tasks: tuple[CurriculumTask, ...]

    @classmethod
    def create(cls, tasks: Iterable[CurriculumTask]) -> Curriculum:
        """Create a curriculum and validate all prerequisites and splits."""
        normalized = tuple(sorted(tasks, key=lambda item: item.task_id.value))
        if not normalized:
            raise FoundationError("curriculum requires at least one task")
        identifiers = [item.task_id.value for item in normalized]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("curriculum contains duplicate task identifiers")
        known = set(identifiers)
        for task in normalized:
            missing = sorted(
                item.value for item in task.prerequisite_ids if item.value not in known
            )
            if missing:
                raise FoundationError(
                    f"task {task.task_id.value} has unknown prerequisites: {', '.join(missing)}"
                )
        curriculum = cls(normalized)
        curriculum._require_acyclic()
        return curriculum

    def _require_acyclic(self) -> None:
        """Reject task prerequisite cycles."""
        by_id = {task.task_id.value: task for task in self.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                raise FoundationError(f"curriculum dependency cycle detected at {task_id}")
            visiting.add(task_id)
            for dependency in by_id[task_id].prerequisite_ids:
                visit(dependency.value)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in sorted(by_id):
            visit(task_id)

    def require(self, task_id: str) -> CurriculumTask:
        """Return one task by canonical identifier."""
        requested = CanonicalKey.from_text(task_id, field_name="task_id")
        for task in self.tasks:
            if task.task_id == requested:
                return task
        raise FoundationError(f"unknown curriculum task: {requested.value}")

    def by_split(self, split: CurriculumSplit) -> tuple[CurriculumTask, ...]:
        """Return tasks assigned to one evaluation split."""
        return tuple(task for task in self.tasks if task.split is split)

    def to_payload(self) -> JsonObject:
        """Return a canonical curriculum payload."""
        tasks: JsonArray = [task.to_payload() for task in self.tasks]
        return {"tasks": tasks}

    def digest(self) -> DigestRecord:
        """Return a deterministic curriculum identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CurriculumTrial:
    """One evidence-bound observed attempt on a curriculum task."""

    trial_id: CanonicalKey
    task_id: CanonicalKey
    sequence: int
    score: float
    status: TrialStatus
    evidence_digest: DigestRecord
    notes: str

    @classmethod
    def create(
        cls,
        *,
        trial_id: str,
        task_id: str,
        sequence: int,
        score: float,
        status: TrialStatus,
        evidence_digest: DigestRecord,
        notes: str,
    ) -> CurriculumTrial:
        """Create a task trial from an observed result."""
        if sequence < 0:
            raise FoundationError("curriculum trial sequence must not be negative")
        if not 0.0 <= score <= 1.0:
            raise FoundationError("curriculum trial score must be between 0 and 1")
        evidence_digest.require_algorithm("sha256")
        return cls(
            trial_id=CanonicalKey.from_text(trial_id, field_name="trial_id"),
            task_id=CanonicalKey.from_text(task_id, field_name="task_id"),
            sequence=sequence,
            score=score,
            status=status,
            evidence_digest=evidence_digest,
            notes=require_text(notes, field_name="notes"),
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical trial payload."""
        return {
            "trial_id": self.trial_id.value,
            "task_id": self.task_id.value,
            "sequence": self.sequence,
            "score": self.score,
            "status": self.status.value,
            "evidence_digest": {
                "algorithm": self.evidence_digest.algorithm,
                "value": self.evidence_digest.value,
            },
            "notes": self.notes,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic trial identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CurriculumLedger:
    """Immutable curriculum trial history with progression and transfer queries."""

    curriculum: Curriculum
    trials: tuple[CurriculumTrial, ...] = ()

    def __post_init__(self) -> None:
        """Require known tasks, unique trials, and contiguous sequence numbers."""
        identifiers = [trial.trial_id.value for trial in self.trials]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("curriculum ledger contains duplicate trials")
        known = {task.task_id for task in self.curriculum.tasks}
        for index, trial in enumerate(self.trials):
            if trial.sequence != index:
                raise FoundationError("curriculum trial sequence must be contiguous")
            if trial.task_id not in known:
                raise FoundationError(f"trial references unknown task: {trial.task_id.value}")

    def record(self, trial: CurriculumTrial) -> CurriculumLedger:
        """Append one trial when its next sequence number is exact."""
        return CurriculumLedger(self.curriculum, (*self.trials, trial))

    def trials_for(self, task_id: str) -> tuple[CurriculumTrial, ...]:
        """Return all trials for one task."""
        task = self.curriculum.require(task_id)
        return tuple(trial for trial in self.trials if trial.task_id == task.task_id)

    def task_passed(self, task: CurriculumTask) -> bool:
        """Return whether any observed trial meets the task threshold and status."""
        return any(
            trial.status is TrialStatus.PASSED and trial.score >= task.pass_threshold
            for trial in self.trials
            if trial.task_id == task.task_id
        )

    def eligible_tasks(self) -> tuple[CurriculumTask, ...]:
        """Return incomplete tasks whose prerequisites are already passed."""
        by_id = {task.task_id: task for task in self.curriculum.tasks}
        eligible = []
        for task in self.curriculum.tasks:
            if self.task_passed(task):
                continue
            if all(self.task_passed(by_id[item]) for item in task.prerequisite_ids):
                eligible.append(task)
        return tuple(
            sorted(
                eligible,
                key=lambda item: (item.difficulty, item.task_id.value),
            )
        )

    def split_score(self, split: CurriculumSplit) -> float:
        """Return mean best-task score for one split, or zero when untested."""
        tasks = self.curriculum.by_split(split)
        scores = []
        for task in tasks:
            task_trials = self.trials_for(task.task_id.value)
            if task_trials:
                scores.append(max(trial.score for trial in task_trials))
        return round(sum(scores) / len(scores), 12) if scores else 0.0

    def transfer_gap(self) -> float:
        """Return validation-to-held-out score drop without hiding negative transfer."""
        return round(
            self.split_score(CurriculumSplit.VALIDATION)
            - self.split_score(CurriculumSplit.HELD_OUT),
            12,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical curriculum-ledger payload."""
        trials: JsonArray = [trial.to_payload() for trial in self.trials]
        return {
            "curriculum": self.curriculum.to_payload(),
            "trials": trials,
            "training_score": self.split_score(CurriculumSplit.TRAINING),
            "validation_score": self.split_score(CurriculumSplit.VALIDATION),
            "held_out_score": self.split_score(CurriculumSplit.HELD_OUT),
            "transfer_gap": self.transfer_gap(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic curriculum-ledger identity."""
        return DigestRecord.from_payload(self.to_payload())
