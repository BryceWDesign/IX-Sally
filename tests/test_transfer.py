from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.transfer import TransferStatus, TransferTrial, TransferTrialPacket


def test_transfer_trial_normalizes_fields_and_generates_id() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    trial = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="  New repository layout. ",
        invariant_under_test="  Evidence gates still precede truth claims. ",
    )

    assert trial.trial_id.value == (
        "ix-transfer-1-new-repository-layout-evidence-gates-still-precede-truth-claims"
    )
    assert trial.target_context == "New repository layout."
    assert trial.invariant_under_test == "Evidence gates still precede truth claims."
    assert trial.status is TransferStatus.PENDING
    assert trial.passed() is False
    assert trial.needs_repair() is False
    assert trial.blocks_progress() is False


def test_transfer_trial_rejects_negative_cycle() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})

    with pytest.raises(FoundationError, match="transfer trial cycle must not be negative"):
        TransferTrial.create(
            cycle=-1,
            source_digest=source,
            target_context="Invalid cycle.",
            invariant_under_test="Invalid.",
        )


def test_transfer_trial_rejects_non_sha256_source_digest() -> None:
    source = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        TransferTrial.create(
            cycle=1,
            source_digest=source,
            target_context="Invalid digest.",
            invariant_under_test="Invalid.",
        )


def test_resolved_transfer_trial_requires_observed_result() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})

    with pytest.raises(FoundationError, match="resolved transfer trials require"):
        TransferTrial.create(
            cycle=1,
            source_digest=source,
            target_context="New task.",
            invariant_under_test="Invariant holds.",
            status=TransferStatus.PASSED,
            evidence_digest=DigestRecord.from_payload({"evidence": "passed"}),
        )


def test_passed_transfer_trial_requires_evidence_digest() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})

    with pytest.raises(FoundationError, match="passed transfer trials require"):
        TransferTrial.create(
            cycle=1,
            source_digest=source,
            target_context="New task.",
            invariant_under_test="Invariant holds.",
            status=TransferStatus.PASSED,
            observed_result="Invariant held.",
        )


def test_partial_or_failed_transfer_trial_requires_failure_note() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})

    with pytest.raises(FoundationError, match="partial or failed transfer trials require"):
        TransferTrial.create(
            cycle=1,
            source_digest=source,
            target_context="New task.",
            invariant_under_test="Invariant holds.",
            status=TransferStatus.FAILED,
            observed_result="Invariant failed.",
        )


def test_blocked_transfer_trial_requires_boundary_note() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})

    with pytest.raises(FoundationError, match="blocked transfer trials require"):
        TransferTrial.create(
            cycle=1,
            source_digest=source,
            target_context="New task.",
            invariant_under_test="Invariant holds.",
            status=TransferStatus.BLOCKED,
            observed_result="Trial was blocked.",
        )


def test_transfer_trial_tracks_pass_repair_and_block_states() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    evidence = DigestRecord.from_payload({"trial": "passed"})
    passed = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="New task.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.PASSED,
        observed_result="Invariant held.",
        evidence_digest=evidence,
    )
    partial = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="New task variant.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.PARTIAL,
        observed_result="Invariant held only after repair.",
        failure_note="The pattern needed adaptation before it transferred.",
    )
    blocked = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="Unauthorized task.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.BLOCKED,
        observed_result="Trial was blocked by boundary policy.",
        boundary_note="The requested context exceeded the autonomy contract.",
    )

    assert passed.passed() is True
    assert partial.needs_repair() is True
    assert blocked.blocks_progress() is True


def test_transfer_trial_rejects_non_sha256_evidence_digest() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    evidence = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        TransferTrial.create(
            cycle=1,
            source_digest=source,
            target_context="New task.",
            invariant_under_test="Invariant holds.",
            status=TransferStatus.PASSED,
            observed_result="Invariant held.",
            evidence_digest=evidence,
        )


def test_transfer_trial_payload_is_stable() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    evidence = DigestRecord.from_payload({"trial": "passed"})
    trial = TransferTrial.create(
        trial_id=CanonicalKey.from_text("trial-one", field_name="trial_id"),
        cycle=1,
        source_digest=source,
        target_context="New task.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.PASSED,
        observed_result="Invariant held.",
        evidence_digest=evidence,
    )

    assert trial.to_payload() == {
        "trial_id": "trial-one",
        "cycle": 1,
        "source_digest": {
            "algorithm": "sha256",
            "value": source.value,
        },
        "target_context": "New task.",
        "invariant_under_test": "Invariant holds.",
        "status": "passed",
        "observed_result": "Invariant held.",
        "evidence_digest": {
            "algorithm": "sha256",
            "value": evidence.value,
        },
        "failure_note": None,
        "boundary_note": None,
        "passed": True,
        "needs_repair": False,
        "blocks_progress": False,
    }


def test_transfer_packet_requires_trial() -> None:
    with pytest.raises(FoundationError, match="transfer packet requires at least one trial"):
        TransferTrialPacket.create(
            cycle=1,
            transfer_summary="No trials.",
            trials=(),
        )


def test_transfer_packet_rejects_cycle_mismatch() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    trial = TransferTrial.create(
        cycle=2,
        source_digest=source,
        target_context="Wrong cycle.",
        invariant_under_test="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="transfer trials must match packet cycle"):
        TransferTrialPacket.create(
            cycle=1,
            transfer_summary="Review transfer.",
            trials=(trial,),
        )


def test_transfer_packet_counts_trial_outcomes() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    evidence = DigestRecord.from_payload({"trial": "passed"})
    passed = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="New task.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.PASSED,
        observed_result="Invariant held.",
        evidence_digest=evidence,
    )
    failed = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="Different task.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.FAILED,
        observed_result="Invariant failed.",
        failure_note="The learned rule did not generalize.",
    )
    blocked = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="Unauthorized task.",
        invariant_under_test="Invariant holds.",
        status=TransferStatus.BLOCKED,
        observed_result="Trial was blocked.",
        boundary_note="Scope exceeded contract.",
    )
    packet = TransferTrialPacket.create(
        cycle=1,
        transfer_summary="Review transfer outcomes.",
        trials=(passed, failed, blocked),
    )

    assert packet.passed_count() == 1
    assert packet.repair_count() == 1
    assert packet.blocked_count() == 1
    assert packet.has_blocker() is True


def test_transfer_packet_converts_to_artifact() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    trial = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="New task.",
        invariant_under_test="Invariant holds.",
    )
    packet = TransferTrialPacket.create(
        cycle=1,
        transfer_summary="Review transfer trial.",
        trials=(trial,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.TRANSFER
    assert artifact.kind is AgentArtifactKind.TRANSFER_RESULT
    assert artifact.summary == "IX-Transfer recorded 1 transfer trial(s)."
    assert artifact.referenced_digests == (trial.digest(),)
    assert artifact.data == packet.to_payload()


def test_transfer_packet_digest_changes_when_trial_changes() -> None:
    source = DigestRecord.from_payload({"memory": "pattern"})
    first_trial = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="First task.",
        invariant_under_test="Invariant holds.",
    )
    second_trial = TransferTrial.create(
        cycle=1,
        source_digest=source,
        target_context="Second task.",
        invariant_under_test="Invariant holds.",
    )
    first = TransferTrialPacket.create(
        cycle=1,
        transfer_summary="Review transfer trial.",
        trials=(first_trial,),
    )
    second = TransferTrialPacket.create(
        cycle=1,
        transfer_summary="Review transfer trial.",
        trials=(second_trial,),
    )

    assert first.digest().value != second.digest().value
