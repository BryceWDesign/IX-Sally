"""Runtime event records for IX-Sally chamber transcripts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class RuntimeEventType(StrEnum):
    """Canonical event types emitted by IX-Sally runtime cycles."""

    CHAMBER_OPENED = "chamber_opened"
    CYCLE_STARTED = "cycle_started"
    AGENT_ARTIFACT_RECORDED = "agent_artifact_recorded"
    JURISDICTION_DECIDED = "jurisdiction_decided"
    EVIDENCE_RECORDED = "evidence_recorded"
    MEMORY_DECIDED = "memory_decided"
    BOUNDARY_BLOCKED = "boundary_blocked"
    CYCLE_STOPPED = "cycle_stopped"
    CHAMBER_CLOSED = "chamber_closed"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """A deterministic transcript event emitted by an IX-Sally run."""

    sequence: int
    cycle: int
    event_type: RuntimeEventType
    actor: AgentRole | None
    summary: str
    payload: JsonObject

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        cycle: int,
        event_type: RuntimeEventType,
        summary: str,
        payload: JsonObject | None = None,
        actor: AgentRole | None = None,
    ) -> RuntimeEvent:
        """Create a validated runtime event."""
        if sequence < 1:
            raise FoundationError("event sequence must be at least 1")
        if cycle < 0:
            raise FoundationError("event cycle must not be negative")

        return cls(
            sequence=sequence,
            cycle=cycle,
            event_type=event_type,
            actor=actor,
            summary=require_text(summary, field_name="summary"),
            payload=payload or {},
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible event representation."""
        return {
            "sequence": self.sequence,
            "cycle": self.cycle,
            "event_type": self.event_type.value,
            "actor": self.actor.value if self.actor is not None else None,
            "summary": self.summary,
            "payload": self.payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this event."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class RuntimeTranscript:
    """Ordered runtime transcript with strict event sequencing."""

    events: tuple[RuntimeEvent, ...]

    @classmethod
    def create(cls, events: tuple[RuntimeEvent, ...]) -> RuntimeTranscript:
        """Create a transcript and reject non-contiguous event sequences."""
        expected_sequence = 1
        previous_cycle = 0

        for event in events:
            if event.sequence != expected_sequence:
                raise FoundationError(
                    f"event sequence must be contiguous: expected {expected_sequence}, "
                    f"got {event.sequence}"
                )
            if event.cycle < previous_cycle:
                raise FoundationError("event cycles must not move backward")

            expected_sequence += 1
            previous_cycle = event.cycle

        return cls(events=events)

    def append(self, event: RuntimeEvent) -> RuntimeTranscript:
        """Return a new transcript with an appended event."""
        return RuntimeTranscript.create((*self.events, event))

    def next_sequence(self) -> int:
        """Return the next event sequence number."""
        return len(self.events) + 1

    def count_by_type(self, event_type: RuntimeEventType) -> int:
        """Return the number of events matching a type."""
        return sum(1 for event in self.events if event.event_type is event_type)

    def actor_counts(self) -> dict[AgentRole, int]:
        """Return event counts by agent actor."""
        counts: dict[AgentRole, int] = {}
        for event in self.events:
            if event.actor is None:
                continue
            counts[event.actor] = counts.get(event.actor, 0) + 1
        return counts

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible transcript representation."""
        return {
            "events": [event.to_payload() for event in self.events],
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this transcript."""
        return DigestRecord.from_payload(self.to_payload())


def event_payload_with_reference(
    *,
    reference_type: str,
    reference_digest: DigestRecord,
) -> JsonObject:
    """Return a payload that links an event to another signed runtime record."""
    key = CanonicalKey.from_text(reference_type, field_name="reference_type")
    reference_digest.require_algorithm("sha256")

    payload: dict[str, JsonValue] = {
        "reference_type": key.value,
        "reference_digest": reference_digest.value,
        "reference_algorithm": reference_digest.algorithm,
    }
    return payload
