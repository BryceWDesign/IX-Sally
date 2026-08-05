

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.falsifications import (
    ButchFalsificationPacket,
    FalsificationFinding,
    FalsificationSeverity,
)
from ix_sally.foundation import CanonicalKey, FoundationError


def test_falsification_finding_normalizes_fields_and_generates_id() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    finding = FalsificationFinding.create(
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.CONCERN,
        summary="  Proposed action lacks execution evidence. ",
        doctrine_key="Output Is Not Evidence",
    )

    assert finding.finding_id.value == (
        "ix-butch-1-concern-proposed-action-lacks-execution-evidence"
    )
    assert finding.summary == "Proposed action lacks execution evidence."
    assert finding.doctrine_key is not None
    assert finding.doctrine_key.value == "output-is-not-evidence"
    assert finding.blocks_progress() is False


def test_falsification_finding_rejects_negative_cycle() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})

    with pytest.raises(FoundationError, match="falsification cycle must not be negative"):
        FalsificationFinding.create(
            cycle=-1,
            target_digest=target,
            severity=FalsificationSeverity.CONCERN,
            summary="Invalid cycle.",
        )


def test_falsification_finding_rejects_non_sha256_target_digest() -> None:
    target = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        FalsificationFinding.create(
            cycle=1,
            target_digest=target,
            severity=FalsificationSeverity.CONCERN,
            summary="Invalid target digest.",
        )


def test_blocker_falsification_requires_suggested_repair() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})

    with pytest.raises(FoundationError, match="blocker falsifications require"):
        FalsificationFinding.create(
            cycle=1,
            target_digest=target,
            severity=FalsificationSeverity.BLOCKER,
            summary="Action attempts authority without gate.",
        )


def test_blocker_falsification_records_repair() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    finding = FalsificationFinding.create(
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.BLOCKER,
        summary="Action attempts authority without gate.",
        suggested_repair="Route the action through the jurisdiction gate before execution.",
    )

    assert finding.blocks_progress() is True
    assert finding.suggested_repair == (
        "Route the action through the jurisdiction gate before execution."
    )


def test_falsification_finding_payload_is_stable() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    finding = FalsificationFinding.create(
        finding_id=CanonicalKey.from_text("finding-one", field_name="finding_id"),
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.OBSERVATION,
        summary="No blocker found.",
        doctrine_key="memory-is-not-truth",
        suggested_repair="Keep memory pending until evidence exists.",
    )

    assert finding.to_payload() == {
        "finding_id": "finding-one",
        "cycle": 1,
        "target_digest": {
            "algorithm": "sha256",
            "value": target.value,
        },
        "severity": "observation",
        "summary": "No blocker found.",
        "doctrine_key": "memory-is-not-truth",
        "suggested_repair": "Keep memory pending until evidence exists.",
    }


def test_butch_falsification_packet_requires_finding() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})

    with pytest.raises(FoundationError, match="requires at least one finding"):
        ButchFalsificationPacket.create(
            cycle=1,
            target_summary="Sally proposal.",
            target_digest=target,
            findings=(),
        )


def test_butch_falsification_packet_rejects_cycle_mismatch() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    finding = FalsificationFinding.create(
        cycle=2,
        target_digest=target,
        severity=FalsificationSeverity.CONCERN,
        summary="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="findings must match packet cycle"):
        ButchFalsificationPacket.create(
            cycle=1,
            target_summary="Sally proposal.",
            target_digest=target,
            findings=(finding,),
        )


def test_butch_falsification_packet_rejects_target_mismatch() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    other_target = DigestRecord.from_payload({"proposal": "other action"})
    finding = FalsificationFinding.create(
        cycle=1,
        target_digest=other_target,
        severity=FalsificationSeverity.CONCERN,
        summary="Wrong target.",
    )

    with pytest.raises(FoundationError, match="findings must target the packet digest"):
        ButchFalsificationPacket.create(
            cycle=1,
            target_summary="Sally proposal.",
            target_digest=target,
            findings=(finding,),
        )


def test_butch_falsification_packet_tracks_blockers_and_artifact() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    concern = FalsificationFinding.create(
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.CONCERN,
        summary="Claim lacks evidence.",
        doctrine_key="output-is-not-evidence",
    )
    blocker = FalsificationFinding.create(
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.BLOCKER,
        summary="Action exceeds authority.",
        suggested_repair="Route through Sentinel and jurisdiction gate.",
    )
    packet = ButchFalsificationPacket.create(
        cycle=1,
        target_summary="Sally proposed a tool action.",
        target_digest=target,
        findings=(concern, blocker),
    )

    assert packet.packet_id.value == "ix-butch-1-sally-proposed-a-tool-action"
    assert packet.has_blocker() is True

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.BUTCH
    assert artifact.kind is AgentArtifactKind.FALSIFICATION
    assert artifact.summary == "IX-Butch raised 2 falsification finding(s)."
    assert artifact.referenced_digests == (target, concern.digest(), blocker.digest())
    assert artifact.data == packet.to_payload()


def test_butch_falsification_packet_digest_changes_when_findings_change() -> None:
    target = DigestRecord.from_payload({"proposal": "bounded action"})
    first_finding = FalsificationFinding.create(
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.CONCERN,
        summary="First concern.",
    )
    second_finding = FalsificationFinding.create(
        cycle=1,
        target_digest=target,
        severity=FalsificationSeverity.CONCERN,
        summary="Second concern.",
    )
    first = ButchFalsificationPacket.create(
        cycle=1,
        target_summary="Sally proposal.",
        target_digest=target,
        findings=(first_finding,),
    )
    second = ButchFalsificationPacket.create(
        cycle=1,
        target_summary="Sally proposal.",
        target_digest=target,
        findings=(second_finding,),
    )

    assert first.digest().value != second.digest().value
