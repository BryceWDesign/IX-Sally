"""Outcome-driven skill learning, retention, curriculum, and transfer evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class OutcomeStatus(StrEnum):
    """Observed outcome class used by the learning system."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class LearningOutcome:
    """One evidence-bound result from attempting a task with a skill."""

    outcome_id: CanonicalKey
    skill_id: CanonicalKey
    task_family: CanonicalKey
    status: OutcomeStatus
    score: float
    evidence_digest: DigestRecord
    notes: str

    @classmethod
    def create(
        cls,
        *,
        outcome_id: str,
        skill_id: str,
        task_family: str,
        status: OutcomeStatus,
        score: float,
        evidence_digest: DigestRecord,
        notes: str,
    ) -> LearningOutcome:
        """Create an outcome without treating an unevidenced score as learning."""
        if not 0.0 <= score <= 1.0:
            raise FoundationError("learning outcome score must be between 0 and 1")
        evidence_digest.require_algorithm("sha256")
        return cls(
            outcome_id=CanonicalKey.from_text(outcome_id, field_name="outcome_id"),
            skill_id=CanonicalKey.from_text(skill_id, field_name="skill_id"),
            task_family=CanonicalKey.from_text(
                task_family,
                field_name="task_family",
            ),
            status=status,
            score=score,
            evidence_digest=evidence_digest,
            notes=require_text(notes, field_name="notes"),
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical learning-outcome payload."""
        return {
            "outcome_id": self.outcome_id.value,
            "skill_id": self.skill_id.value,
            "task_family": self.task_family.value,
            "status": self.status.value,
            "score": self.score,
            "evidence_digest": {
                "algorithm": self.evidence_digest.algorithm,
                "value": self.evidence_digest.value,
            },
            "notes": self.notes,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic outcome identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SkillProfile:
    """Evidence-based competence estimate for one reusable skill."""

    skill_id: CanonicalKey
    attempts: int = 0
    successes: int = 0
    mean_score: float = 0.0
    confidence: float = 0.0
    last_outcome_digest: DigestRecord | None = None

    @classmethod
    def new(cls, skill_id: str) -> SkillProfile:
        """Create an untested skill profile."""
        return cls(CanonicalKey.from_text(skill_id, field_name="skill_id"))

    def __post_init__(self) -> None:
        """Require counters and estimates to remain coherent."""
        if self.attempts < 0 or self.successes < 0 or self.successes > self.attempts:
            raise FoundationError("skill profile counters are inconsistent")
        if not 0.0 <= self.mean_score <= 1.0:
            raise FoundationError("skill mean_score must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("skill confidence must be between 0 and 1")
        if self.last_outcome_digest is not None:
            self.last_outcome_digest.require_algorithm("sha256")

    def learn(self, outcome: LearningOutcome) -> SkillProfile:
        """Return a profile updated by one outcome for the same skill."""
        if outcome.skill_id != self.skill_id:
            raise FoundationError("learning outcome skill does not match profile")
        attempts = self.attempts + 1
        mean_score = ((self.mean_score * self.attempts) + outcome.score) / attempts
        successes = self.successes + int(outcome.status is OutcomeStatus.SUCCESS)
        confidence = min(1.0, attempts / 12.0) * (0.5 + 0.5 * mean_score)
        return SkillProfile(
            skill_id=self.skill_id,
            attempts=attempts,
            successes=successes,
            mean_score=round(mean_score, 12),
            confidence=round(confidence, 12),
            last_outcome_digest=outcome.digest(),
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical skill-profile payload."""
        digest_payload: JsonValue = None
        if self.last_outcome_digest is not None:
            digest_payload = {
                "algorithm": self.last_outcome_digest.algorithm,
                "value": self.last_outcome_digest.value,
            }
        return {
            "skill_id": self.skill_id.value,
            "attempts": self.attempts,
            "successes": self.successes,
            "mean_score": self.mean_score,
            "confidence": self.confidence,
            "last_outcome_digest": digest_payload,
        }


@dataclass(frozen=True, slots=True)
class LearningLedger:
    """Immutable outcomes and skill profiles with deterministic updates."""

    outcomes: tuple[LearningOutcome, ...] = ()
    profiles: tuple[SkillProfile, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate outcome and skill identifiers."""
        outcome_ids = [outcome.outcome_id.value for outcome in self.outcomes]
        skill_ids = [profile.skill_id.value for profile in self.profiles]
        if len(outcome_ids) != len(set(outcome_ids)):
            raise FoundationError("learning ledger contains duplicate outcomes")
        if len(skill_ids) != len(set(skill_ids)):
            raise FoundationError("learning ledger contains duplicate profiles")

    def record(self, outcome: LearningOutcome) -> LearningLedger:
        """Return a ledger with the outcome and updated profile."""
        if any(existing.outcome_id == outcome.outcome_id for existing in self.outcomes):
            raise FoundationError(f"learning outcome already exists: {outcome.outcome_id.value}")
        profiles = list(self.profiles)
        for index, profile in enumerate(profiles):
            if profile.skill_id == outcome.skill_id:
                profiles[index] = profile.learn(outcome)
                break
        else:
            profiles.append(SkillProfile.new(outcome.skill_id.value).learn(outcome))
        return LearningLedger(
            outcomes=(*self.outcomes, outcome),
            profiles=tuple(sorted(profiles, key=lambda item: item.skill_id.value)),
        )

    def require_profile(self, skill_id: str) -> SkillProfile:
        """Return one skill profile by canonical identifier."""
        requested = CanonicalKey.from_text(skill_id, field_name="skill_id")
        for profile in self.profiles:
            if profile.skill_id == requested:
                return profile
        raise FoundationError(f"unknown skill profile: {requested.value}")

    def retention_score(self, skill_id: str, *, recent_window: int = 5) -> float:
        """Return mean recent performance for transparent retention tracking."""
        if recent_window <= 0:
            raise FoundationError("retention recent_window must be positive")
        requested = CanonicalKey.from_text(skill_id, field_name="skill_id")
        relevant = [outcome.score for outcome in self.outcomes if outcome.skill_id == requested][
            -recent_window:
        ]
        if not relevant:
            return 0.0
        return round(sum(relevant) / len(relevant), 12)

    def to_payload(self) -> JsonObject:
        """Return a canonical learning-ledger payload."""
        outcomes: JsonArray = [outcome.to_payload() for outcome in self.outcomes]
        profiles: JsonArray = [profile.to_payload() for profile in self.profiles]
        return {
            "outcome_count": len(self.outcomes),
            "profile_count": len(self.profiles),
            "outcomes": outcomes,
            "profiles": profiles,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic learning-ledger identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class TransferEvaluation:
    """Measured performance across familiar and held-out task families."""

    skill_id: CanonicalKey
    familiar_score: float
    novel_score: float
    retention_score: float
    evidence_digests: tuple[DigestRecord, ...]

    @classmethod
    def create(
        cls,
        *,
        skill_id: str,
        familiar_score: float,
        novel_score: float,
        retention_score: float,
        evidence_digests: Iterable[DigestRecord],
    ) -> TransferEvaluation:
        """Create a transfer result with explicit supporting evidence."""
        for name, value in {
            "familiar_score": familiar_score,
            "novel_score": novel_score,
            "retention_score": retention_score,
        }.items():
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"transfer {name} must be between 0 and 1")
        evidence = tuple(evidence_digests)
        if not evidence:
            raise FoundationError("transfer evaluation requires evidence")
        for digest in evidence:
            digest.require_algorithm("sha256")
        return cls(
            skill_id=CanonicalKey.from_text(skill_id, field_name="skill_id"),
            familiar_score=familiar_score,
            novel_score=novel_score,
            retention_score=retention_score,
            evidence_digests=evidence,
        )

    def generalization_gap(self) -> float:
        """Return familiar minus novel performance."""
        return round(self.familiar_score - self.novel_score, 12)

    def passes(self, *, minimum_novel_score: float = 0.7, maximum_gap: float = 0.2) -> bool:
        """Return whether the measured transfer meets declared thresholds."""
        return (
            self.novel_score >= minimum_novel_score
            and self.retention_score >= minimum_novel_score
            and self.generalization_gap() <= maximum_gap
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical transfer-evaluation payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        return {
            "skill_id": self.skill_id.value,
            "familiar_score": self.familiar_score,
            "novel_score": self.novel_score,
            "retention_score": self.retention_score,
            "generalization_gap": self.generalization_gap(),
            "passes": self.passes(),
            "evidence_digests": evidence,
        }
