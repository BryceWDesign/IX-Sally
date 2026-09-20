"""Typed contracts for the Choice Under Consequence experiment."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum, StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


def digest_payload(digest: DigestRecord) -> JsonObject:
    """Return the canonical payload form of a digest record."""
    return {"algorithm": digest.algorithm, "value": digest.value}


class Direction(IntEnum):
    """Four actions and visible cue directions in clockwise order."""

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    def rotated(self, quarter_turns: int) -> Direction:
        """Return this direction rotated clockwise."""
        return Direction((int(self) + quarter_turns) % len(Direction))


class OutcomeStatus(StrEnum):
    """Evaluator-owned result of one intervention."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class PublicObservation:
    """Agent-visible environment state with no answer or hidden-rule field."""

    observation_id: str
    family_id: str
    cue: Direction
    context: str
    available_actions: tuple[Direction, ...]
    evidence_digest: DigestRecord

    def __post_init__(self) -> None:
        """Validate public state and prevent an empty action surface."""
        require_text(self.observation_id, field_name="observation_id")
        require_text(self.family_id, field_name="family_id")
        require_text(self.context, field_name="context")
        if not self.available_actions:
            raise FoundationError("observation requires available actions")
        if len(set(self.available_actions)) != len(self.available_actions):
            raise FoundationError("observation actions must be unique")
        self.evidence_digest.require_algorithm("sha256")

    def to_payload(self) -> JsonObject:
        """Return the complete agent-visible payload."""
        actions: JsonArray = [action.name.lower() for action in self.available_actions]
        return {
            "observation_id": self.observation_id,
            "family_id": self.family_id,
            "cue": self.cue.name.lower(),
            "context": self.context,
            "available_actions": actions,
            "evidence_digest": digest_payload(self.evidence_digest),
        }


@dataclass(frozen=True, slots=True)
class Consequence:
    """Measured result emitted only after an agent intervention."""

    consequence_id: str
    observation_digest: DigestRecord
    selected_action: Direction
    status: OutcomeStatus
    reward: float
    terminal: bool
    evaluator_digest: DigestRecord

    def __post_init__(self) -> None:
        """Validate evaluator evidence and bounded reward."""
        require_text(self.consequence_id, field_name="consequence_id")
        self.observation_digest.require_algorithm("sha256")
        self.evaluator_digest.require_algorithm("sha256")
        if not -1.0 <= self.reward <= 1.0:
            raise FoundationError("consequence reward must be between -1 and 1")

    @property
    def succeeded(self) -> bool:
        """Return whether the intervention achieved the hidden transition."""
        return self.status is OutcomeStatus.SUCCESS

    def to_payload(self) -> JsonObject:
        """Return a canonical measured-consequence payload."""
        return {
            "consequence_id": self.consequence_id,
            "observation_digest": digest_payload(self.observation_digest),
            "selected_action": self.selected_action.name.lower(),
            "status": self.status.value,
            "reward": self.reward,
            "terminal": self.terminal,
            "evaluator_digest": digest_payload(self.evaluator_digest),
        }


@dataclass(frozen=True, slots=True)
class CausalHypothesis:
    """One competing hypothesis that maps cues to actions."""

    hypothesis_id: str
    quarter_turns: int
    probability: float

    def __post_init__(self) -> None:
        """Validate hypothesis identity, transform, and probability."""
        require_text(self.hypothesis_id, field_name="hypothesis_id")
        if self.quarter_turns not in range(len(Direction)):
            raise FoundationError("hypothesis quarter_turns must be in range 0..3")
        if not 0.0 <= self.probability <= 1.0 or not math.isfinite(self.probability):
            raise FoundationError("hypothesis probability must be finite and bounded")

    def predicts(self, cue: Direction) -> Direction:
        """Return the action predicted by this causal hypothesis."""
        return cue.rotated(self.quarter_turns)

    def to_payload(self) -> JsonObject:
        """Return a canonical hypothesis payload."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "quarter_turns": self.quarter_turns,
            "probability": self.probability,
        }


@dataclass(frozen=True, slots=True)
class ChoiceCandidate:
    """One action with a transparent multi-objective score vector."""

    action: Direction
    expected_success: float
    expected_information_gain: float
    novelty: float
    reversibility: float
    cost: float
    risk: float
    score: float

    def __post_init__(self) -> None:
        """Require finite bounded score components."""
        for name, value in {
            "expected_success": self.expected_success,
            "expected_information_gain": self.expected_information_gain,
            "novelty": self.novelty,
            "reversibility": self.reversibility,
            "cost": self.cost,
            "risk": self.risk,
        }.items():
            if not 0.0 <= value <= 1.0 or not math.isfinite(value):
                raise FoundationError(f"choice {name} must be finite and bounded")
        if not math.isfinite(self.score):
            raise FoundationError("choice score must be finite")

    def to_payload(self) -> JsonObject:
        """Return the complete Pareto-relevant score vector."""
        return {
            "action": self.action.name.lower(),
            "expected_success": self.expected_success,
            "expected_information_gain": self.expected_information_gain,
            "novelty": self.novelty,
            "reversibility": self.reversibility,
            "cost": self.cost,
            "risk": self.risk,
            "score": self.score,
        }


@dataclass(frozen=True, slots=True)
class ChoiceReceipt:
    """Auditable record of alternatives, predictions, and selected intervention."""

    choice_id: str
    observation_digest: DigestRecord
    candidates: tuple[ChoiceCandidate, ...]
    selected_action: Direction
    prior_entropy: float
    used_skill_id: str | None

    def __post_init__(self) -> None:
        """Require complete alternatives and a selected member."""
        require_text(self.choice_id, field_name="choice_id")
        self.observation_digest.require_algorithm("sha256")
        if not self.candidates:
            raise FoundationError("choice receipt requires candidates")
        if self.selected_action not in {candidate.action for candidate in self.candidates}:
            raise FoundationError("selected action must appear in choice candidates")
        if self.prior_entropy < 0.0 or not math.isfinite(self.prior_entropy):
            raise FoundationError("choice entropy must be finite and non-negative")

    def to_payload(self) -> JsonObject:
        """Return a canonical choice receipt."""
        candidates: JsonArray = [candidate.to_payload() for candidate in self.candidates]
        return {
            "choice_id": self.choice_id,
            "observation_digest": digest_payload(self.observation_digest),
            "candidates": candidates,
            "selected_action": self.selected_action.name.lower(),
            "prior_entropy": self.prior_entropy,
            "used_skill_id": self.used_skill_id,
        }

    def digest(self) -> DigestRecord:
        """Return the content-addressed choice identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class LearnedSkill:
    """Executable generalized cue transformation learned from consequences."""

    skill_id: str
    family_id: str
    quarter_turns: int
    confidence: float
    source_consequence_digests: tuple[DigestRecord, ...]
    validation_uses: int = 0
    validation_successes: int = 0

    def __post_init__(self) -> None:
        """Validate executable skill and its measured provenance."""
        require_text(self.skill_id, field_name="skill_id")
        require_text(self.family_id, field_name="family_id")
        if self.quarter_turns not in range(len(Direction)):
            raise FoundationError("skill quarter_turns must be in range 0..3")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("skill confidence must be bounded")
        if not self.source_consequence_digests:
            raise FoundationError("learned skill requires measured consequences")
        if self.validation_uses < 0 or not 0 <= self.validation_successes <= self.validation_uses:
            raise FoundationError("invalid skill validation counters")
        for digest in self.source_consequence_digests:
            digest.require_algorithm("sha256")

    def apply(self, cue: Direction) -> Direction:
        """Execute the learned transformation on a new cue."""
        return cue.rotated(self.quarter_turns)

    def to_payload(self) -> JsonObject:
        """Return a canonical executable-skill payload."""
        evidence: JsonArray = [digest_payload(digest) for digest in self.source_consequence_digests]
        return {
            "skill_id": self.skill_id,
            "family_id": self.family_id,
            "quarter_turns": self.quarter_turns,
            "confidence": self.confidence,
            "source_consequence_digests": evidence,
            "validation_uses": self.validation_uses,
            "validation_successes": self.validation_successes,
        }
