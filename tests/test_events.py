from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord
from ix_sally.events import (
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTranscript,
    event_payload_with_reference,
)
from ix_sally.foundation import FoundationError


def test_runtime_event_normalizes_summary() -> None:
    event = RuntimeEvent.create(
        sequence=1,
        cycle=0,
        event_type=RuntimeEventType.CHAMBER_OPENED,
        summary="  Chamber opened under human boundary authority.  ",
        payload={"mode": "observe"},
    )

    assert event.summary == "Chamber opened under human boundary authority."
    assert event.to_payload() == {
        "sequence": 1,
        "cycle": 0,
        "event_type": "chamber_opened",
        "actor": None,
        "summary": "Chamber opened under human boundary authority.",
        "payload": {"mode": "observe"},
    }


def test_runtime_event_rejects_invalid_sequence() -> None:
    with pytest.raises(FoundationError, match="event sequence must be at least 1"):
        RuntimeEvent.create(
            sequence=0,
            cycle=0,
            event_type=RuntimeEventType.CHAMBER_OPENED,
            summary="Opened.",
        )


def test_runtime_event_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="event cycle must not be negative"):
        RuntimeEvent.create(
            sequence=1,
            cycle=-1,
            event_type=RuntimeEventType.CYCLE_STARTED,
            summary="Started.",
        )


def test_runtime_transcript_requires_contiguous_sequences() -> None:
    first = RuntimeEvent.create(
        sequence=1,
        cycle=0,
        event_type=RuntimeEventType.CHAMBER_OPENED,
        summary="Opened.",
    )
    third = RuntimeEvent.create(
        sequence=3,
        cycle=1,
        event_type=RuntimeEventType.CYCLE_STARTED,
        summary="Started.",
    )

    with pytest.raises(FoundationError, match="event sequence must be contiguous"):
        RuntimeTranscript.create((first, third))


def test_runtime_transcript_rejects_backward_cycles() -> None:
    first = RuntimeEvent.create(
        sequence=1,
        cycle=2,
        event_type=RuntimeEventType.CYCLE_STARTED,
        summary="Started.",
    )
    second = RuntimeEvent.create(
        sequence=2,
        cycle=1,
        event_type=RuntimeEventType.CYCLE_STOPPED,
        summary="Stopped.",
    )

    with pytest.raises(FoundationError, match="event cycles must not move backward"):
        RuntimeTranscript.create((first, second))


def test_runtime_transcript_appends_events_and_counts_types() -> None:
    transcript = RuntimeTranscript.create(())
    opened = RuntimeEvent.create(
        sequence=transcript.next_sequence(),
        cycle=0,
        event_type=RuntimeEventType.CHAMBER_OPENED,
        summary="Opened.",
    )
    transcript = transcript.append(opened)
    artifact = RuntimeEvent.create(
        sequence=transcript.next_sequence(),
        cycle=1,
        event_type=RuntimeEventType.AGENT_ARTIFACT_RECORDED,
        actor=AgentRole.SALLY,
        summary="Sally proposed a bounded plan.",
    )
    transcript = transcript.append(artifact)

    assert transcript.next_sequence() == 3
    assert transcript.count_by_type(RuntimeEventType.AGENT_ARTIFACT_RECORDED) == 1
    assert transcript.actor_counts() == {AgentRole.SALLY: 1}


def test_transcript_digest_changes_when_event_payload_changes() -> None:
    first = RuntimeTranscript.create(
        (
            RuntimeEvent.create(
                sequence=1,
                cycle=0,
                event_type=RuntimeEventType.CHAMBER_OPENED,
                summary="Opened.",
                payload={"mode": "observe"},
            ),
        )
    )
    second = RuntimeTranscript.create(
        (
            RuntimeEvent.create(
                sequence=1,
                cycle=0,
                event_type=RuntimeEventType.CHAMBER_OPENED,
                summary="Opened.",
                payload={"mode": "research"},
            ),
        )
    )

    assert first.digest().value != second.digest().value


def test_event_payload_with_reference_normalizes_reference_type() -> None:
    digest = DigestRecord.from_payload({"claim": "output is not evidence"})

    payload = event_payload_with_reference(
        reference_type=" Evidence Judgment ",
        reference_digest=digest,
    )

    assert payload == {
        "reference_type": "evidence-judgment",
        "reference_digest": digest.value,
        "reference_algorithm": "sha256",
    }


def test_event_payload_with_reference_requires_sha256_digest() -> None:
    digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        event_payload_with_reference(
            reference_type="evidence-judgment",
            reference_digest=digest,
        )
