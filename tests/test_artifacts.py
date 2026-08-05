

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind, AgentArtifactLedger
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError


def test_agent_artifact_normalizes_summary_and_generates_id() -> None:
    artifact = AgentArtifact.create(
        cycle=1,
        role=AgentRole.SALLY,
        kind=AgentArtifactKind.PROPOSAL,
        summary="  Sally proposed a bounded chamber action. ",
        data={"claim_count": 1},
    )

    assert artifact.artifact_id.value == (
        "ix-sally-1-proposal-sally-proposed-a-bounded-chamber-action"
    )
    assert artifact.summary == "Sally proposed a bounded chamber action."
    assert artifact.data == {"claim_count": 1}


def test_agent_artifact_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="artifact cycle must not be negative"):
        AgentArtifact.create(
            cycle=-1,
            role=AgentRole.SALLY,
            kind=AgentArtifactKind.PROPOSAL,
            summary="Invalid cycle.",
        )


def test_agent_artifact_rejects_non_sha256_reference_digest() -> None:
    digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        AgentArtifact.create(
            cycle=1,
            role=AgentRole.VERITY,
            kind=AgentArtifactKind.EVIDENCE_JUDGMENT,
            summary="Invalid digest reference.",
            referenced_digests=(digest,),
        )


def test_agent_artifact_payload_is_stable() -> None:
    digest = DigestRecord.from_payload({"claim": "supported"})
    artifact = AgentArtifact.create(
        artifact_id=CanonicalKey.from_text("artifact-one", field_name="artifact_id"),
        cycle=1,
        role=AgentRole.VERITY,
        kind=AgentArtifactKind.EVIDENCE_JUDGMENT,
        summary="Claim remains pending evidence.",
        referenced_digests=(digest,),
        data={"status": "pending_evidence"},
    )

    assert artifact.to_payload() == {
        "artifact_id": "artifact-one",
        "cycle": 1,
        "role": "ix-verity",
        "kind": "evidence_judgment",
        "summary": "Claim remains pending evidence.",
        "referenced_digests": [
            {
                "algorithm": "sha256",
                "value": digest.value,
            }
        ],
        "data": {"status": "pending_evidence"},
    }


def test_agent_artifact_ledger_rejects_duplicate_artifact_ids() -> None:
    artifact_id = CanonicalKey.from_text("same-artifact", field_name="artifact_id")
    first = AgentArtifact.create(
        artifact_id=artifact_id,
        cycle=1,
        role=AgentRole.SALLY,
        kind=AgentArtifactKind.PROPOSAL,
        summary="First artifact.",
    )
    second = AgentArtifact.create(
        artifact_id=artifact_id,
        cycle=1,
        role=AgentRole.BUTCH,
        kind=AgentArtifactKind.FALSIFICATION,
        summary="Second artifact.",
    )

    with pytest.raises(FoundationError, match="duplicate artifact id"):
        AgentArtifactLedger.create((first, second))


def test_agent_artifact_ledger_appends_and_requires_artifact() -> None:
    artifact = AgentArtifact.create(
        cycle=1,
        role=AgentRole.CLERK,
        kind=AgentArtifactKind.DOSSIER_ENTRY,
        summary="Cycle recorded.",
    )
    ledger = AgentArtifactLedger.create(()).append(artifact)

    assert ledger.require_artifact(artifact.artifact_id.value) == artifact

    with pytest.raises(FoundationError, match="unknown artifact id"):
        ledger.require_artifact("missing-artifact")


def test_agent_artifact_ledger_filters_by_role_and_kind() -> None:
    proposal = AgentArtifact.create(
        cycle=1,
        role=AgentRole.SALLY,
        kind=AgentArtifactKind.PROPOSAL,
        summary="Proposal emitted.",
    )
    falsification = AgentArtifact.create(
        cycle=1,
        role=AgentRole.BUTCH,
        kind=AgentArtifactKind.FALSIFICATION,
        summary="Falsification emitted.",
    )
    ledger = AgentArtifactLedger.create((proposal, falsification))

    assert ledger.by_role(AgentRole.SALLY) == (proposal,)
    assert ledger.by_kind(AgentArtifactKind.FALSIFICATION) == (falsification,)


def test_agent_artifact_ledger_digest_changes_when_artifact_changes() -> None:
    first = AgentArtifact.create(
        cycle=1,
        role=AgentRole.SALLY,
        kind=AgentArtifactKind.PROPOSAL,
        summary="Proposal one.",
    )
    second = AgentArtifact.create(
        cycle=1,
        role=AgentRole.SALLY,
        kind=AgentArtifactKind.PROPOSAL,
        summary="Proposal two.",
    )

    assert (
        AgentArtifactLedger.create((first,)).digest().value
        != AgentArtifactLedger.create((second,)).digest().value
    )
