"""Replayable cognitive episodes with an append-only digest chain."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class EpisodeStepKind(StrEnum):
    """Closed step categories recorded during a cognitive episode."""

    INPUT = "input"
    ATTENTION = "attention"
    RETRIEVAL = "retrieval"
    INFERENCE = "inference"
    PLANNING = "planning"
    AUTHORITY = "authority"
    EXECUTION = "execution"
    LEARNING = "learning"
    OUTPUT = "output"


class EpisodeStepStatus(StrEnum):
    """Result status for one episode step."""

    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class EpisodeStep:
    """One ordered, digest-bound event within a cognitive episode."""

    index: int
    kind: EpisodeStepKind
    status: EpisodeStepStatus
    detail: str
    input_digests: tuple[DigestRecord, ...] = ()
    output_digests: tuple[DigestRecord, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        index: int,
        kind: EpisodeStepKind,
        status: EpisodeStepStatus,
        detail: str,
        input_digests: Iterable[DigestRecord] = (),
        output_digests: Iterable[DigestRecord] = (),
    ) -> EpisodeStep:
        """Create one non-negative episode step with SHA-256 references."""
        if index < 0:
            raise FoundationError("episode step index must not be negative")
        inputs = tuple(input_digests)
        outputs = tuple(output_digests)
        for digest in (*inputs, *outputs):
            digest.require_algorithm("sha256")
        return cls(
            index=index,
            kind=kind,
            status=status,
            detail=require_text(detail, field_name="detail"),
            input_digests=inputs,
            output_digests=outputs,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical step payload."""
        inputs: JsonArray = [
            {"algorithm": item.algorithm, "value": item.value} for item in self.input_digests
        ]
        outputs: JsonArray = [
            {"algorithm": item.algorithm, "value": item.value} for item in self.output_digests
        ]
        return {
            "index": self.index,
            "kind": self.kind.value,
            "status": self.status.value,
            "detail": self.detail,
            "input_digests": inputs,
            "output_digests": outputs,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic step identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CognitiveEpisode:
    """One complete cognitive episode linked to the prior episode digest."""

    episode_id: CanonicalKey
    sequence: int
    task: str
    initial_state_digest: DigestRecord
    final_state_digest: DigestRecord
    steps: tuple[EpisodeStep, ...]
    previous_episode_digest: DigestRecord | None = None

    @classmethod
    def create(
        cls,
        *,
        episode_id: str,
        sequence: int,
        task: str,
        initial_state_digest: DigestRecord,
        final_state_digest: DigestRecord,
        steps: Iterable[EpisodeStep],
        previous_episode_digest: DigestRecord | None = None,
    ) -> CognitiveEpisode:
        """Create a replayable episode with contiguous step indexes."""
        if sequence < 0:
            raise FoundationError("episode sequence must not be negative")
        initial_state_digest.require_algorithm("sha256")
        final_state_digest.require_algorithm("sha256")
        if previous_episode_digest is not None:
            previous_episode_digest.require_algorithm("sha256")
        normalized_steps = tuple(steps)
        expected_indexes = tuple(range(len(normalized_steps)))
        actual_indexes = tuple(step.index for step in normalized_steps)
        if actual_indexes != expected_indexes:
            raise FoundationError("episode step indexes must be contiguous from zero")
        return cls(
            episode_id=CanonicalKey.from_text(episode_id, field_name="episode_id"),
            sequence=sequence,
            task=require_text(task, field_name="task"),
            initial_state_digest=initial_state_digest,
            final_state_digest=final_state_digest,
            steps=normalized_steps,
            previous_episode_digest=previous_episode_digest,
        )

    def completed(self) -> bool:
        """Return whether every recorded step completed successfully."""
        return all(step.status is EpisodeStepStatus.COMPLETED for step in self.steps)

    def to_payload(self) -> JsonObject:
        """Return a canonical episode payload."""
        steps: JsonArray = [step.to_payload() for step in self.steps]
        previous: JsonObject | None = None
        if self.previous_episode_digest is not None:
            previous = {
                "algorithm": self.previous_episode_digest.algorithm,
                "value": self.previous_episode_digest.value,
            }
        return {
            "episode_id": self.episode_id.value,
            "sequence": self.sequence,
            "task": self.task,
            "initial_state_digest": {
                "algorithm": self.initial_state_digest.algorithm,
                "value": self.initial_state_digest.value,
            },
            "final_state_digest": {
                "algorithm": self.final_state_digest.algorithm,
                "value": self.final_state_digest.value,
            },
            "steps": steps,
            "previous_episode_digest": previous,
            "completed": self.completed(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic episode identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class EpisodeLedger:
    """Immutable, append-only chain of complete cognitive episodes."""

    episodes: tuple[CognitiveEpisode, ...] = ()

    @classmethod
    def create(cls, episodes: Iterable[CognitiveEpisode] = ()) -> EpisodeLedger:
        """Create and verify an episode chain."""
        normalized = tuple(episodes)
        identifiers = [item.episode_id.value for item in normalized]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("episode ledger contains duplicate identifiers")
        for index, episode in enumerate(normalized):
            if episode.sequence != index:
                raise FoundationError("episode sequence must be contiguous from zero")
            expected_previous = None if index == 0 else normalized[index - 1].digest()
            if episode.previous_episode_digest != expected_previous:
                raise FoundationError("episode previous digest does not match ledger head")
        return cls(normalized)

    def append(self, episode: CognitiveEpisode) -> EpisodeLedger:
        """Append an episode only when its sequence and chain link are exact."""
        return EpisodeLedger.create((*self.episodes, episode))

    def next_sequence(self) -> int:
        """Return the sequence number required by the next episode."""
        return len(self.episodes)

    def head_digest(self) -> DigestRecord | None:
        """Return the current episode-chain head."""
        return self.episodes[-1].digest() if self.episodes else None

    def to_payload(self) -> JsonObject:
        """Return a canonical ledger payload."""
        episodes: JsonArray = [episode.to_payload() for episode in self.episodes]
        return {"episodes": episodes}

    def digest(self) -> DigestRecord:
        """Return a deterministic ledger identity."""
        return DigestRecord.from_payload(self.to_payload())
