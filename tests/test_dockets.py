

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.dockets import ClerkDocketEntry, ClerkDocketPacket, DocketEntryKind
from ix_sally.foundation import CanonicalKey, FoundationError


def test_clerk_docket_entry_normalizes_fields_and_generates_id() -> None:
    entry = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.OBSERVATION,
        summary="  Sally proposal was recorded. ",
        actor=AgentRole.SALLY,
    )

    assert entry.entry_id.value == "ix-clerk-1-observation-sally-proposal-was-recorded"
    assert entry.summary == "Sally proposal was recorded."
    assert entry.actor is AgentRole.SALLY
    assert entry.blocks_progress() is False


def test_clerk_docket_entry_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="docket entry cycle must not be negative"):
        ClerkDocketEntry.create(
            cycle=-1,
            kind=DocketEntryKind.OBSERVATION,
            summary="Invalid cycle.",
        )


def test_receipt_reference_entry_requires_digest() -> None:
    with pytest.raises(FoundationError, match="receipt-reference docket entries require"):
        ClerkDocketEntry.create(
            cycle=1,
            kind=DocketEntryKind.RECEIPT_REFERENCE,
            summary="Receipt was referenced.",
        )


def test_clerk_docket_entry_rejects_non_sha256_reference_digest() -> None:
    digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        ClerkDocketEntry.create(
            cycle=1,
            kind=DocketEntryKind.RECEIPT_REFERENCE,
            summary="Invalid digest reference.",
            reference_digest=digest,
        )


def test_human_boundary_entry_requires_human_review() -> None:
    with pytest.raises(FoundationError, match="human-boundary docket entries require"):
        ClerkDocketEntry.create(
            cycle=1,
            kind=DocketEntryKind.HUMAN_BOUNDARY,
            summary="Human boundary reached.",
        )


def test_blocker_entry_requires_note() -> None:
    with pytest.raises(FoundationError, match="blocker docket entries require a note"):
        ClerkDocketEntry.create(
            cycle=1,
            kind=DocketEntryKind.BLOCKER,
            summary="Progress blocked.",
        )


def test_clerk_docket_entry_payload_is_stable() -> None:
    digest = DigestRecord.from_payload({"receipt": "passed"})
    entry = ClerkDocketEntry.create(
        entry_id=CanonicalKey.from_text("entry-one", field_name="entry_id"),
        cycle=1,
        kind=DocketEntryKind.RECEIPT_REFERENCE,
        summary="Forge receipt recorded.",
        actor=AgentRole.FORGE,
        reference_digest=digest,
        note="Receipt is available for later judgment.",
    )

    assert entry.to_payload() == {
        "entry_id": "entry-one",
        "cycle": 1,
        "kind": "receipt_reference",
        "summary": "Forge receipt recorded.",
        "actor": "ix-forge",
        "reference_digest": {
            "algorithm": "sha256",
            "value": digest.value,
        },
        "requires_human_review": False,
        "note": "Receipt is available for later judgment.",
        "blocks_progress": False,
    }


def test_clerk_docket_packet_requires_entry() -> None:
    with pytest.raises(FoundationError, match="docket packet requires at least one entry"):
        ClerkDocketPacket.create(
            cycle=1,
            docket_summary="No entries.",
            entries=(),
        )


def test_clerk_docket_packet_rejects_cycle_mismatch() -> None:
    entry = ClerkDocketEntry.create(
        cycle=2,
        kind=DocketEntryKind.OBSERVATION,
        summary="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="docket entries must match packet cycle"):
        ClerkDocketPacket.create(
            cycle=1,
            docket_summary="Review docket.",
            entries=(entry,),
        )


def test_clerk_docket_packet_counts_human_review_and_blockers() -> None:
    digest = DigestRecord.from_payload({"receipt": "blocked"})
    observation = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.OBSERVATION,
        summary="Observation recorded.",
    )
    receipt = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.RECEIPT_REFERENCE,
        summary="Receipt recorded.",
        reference_digest=digest,
    )
    boundary = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.HUMAN_BOUNDARY,
        summary="Human boundary reached.",
        requires_human_review=True,
    )
    blocker = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.BLOCKER,
        summary="Progress blocked.",
        note="A boundary report blocked autonomous continuation.",
    )
    packet = ClerkDocketPacket.create(
        cycle=1,
        docket_summary="Record cycle status.",
        entries=(observation, receipt, boundary, blocker),
    )

    assert packet.human_review_count() == 1
    assert packet.blocker_count() == 2
    assert packet.has_blocker() is True
    assert packet.referenced_digests() == (digest,)


def test_clerk_docket_packet_converts_to_artifact() -> None:
    digest = DigestRecord.from_payload({"receipt": "passed"})
    entry = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.RECEIPT_REFERENCE,
        summary="Forge receipt recorded.",
        reference_digest=digest,
    )
    packet = ClerkDocketPacket.create(
        cycle=1,
        docket_summary="Record receipt.",
        entries=(entry,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.CLERK
    assert artifact.kind is AgentArtifactKind.DOSSIER_ENTRY
    assert artifact.summary == "IX-Clerk recorded 1 docket entrie(s)."
    assert artifact.referenced_digests == (digest,)
    assert artifact.data == packet.to_payload()


def test_clerk_docket_packet_digest_changes_when_entry_changes() -> None:
    first_entry = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.OBSERVATION,
        summary="First observation.",
    )
    second_entry = ClerkDocketEntry.create(
        cycle=1,
        kind=DocketEntryKind.OBSERVATION,
        summary="Second observation.",
    )
    first = ClerkDocketPacket.create(
        cycle=1,
        docket_summary="Record cycle.",
        entries=(first_entry,),
    )
    second = ClerkDocketPacket.create(
        cycle=1,
        docket_summary="Record cycle.",
        entries=(second_entry,),
    )

    assert first.digest().value != second.digest().value
