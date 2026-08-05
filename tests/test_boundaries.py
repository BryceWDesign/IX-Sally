

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.boundaries import BoundaryFinding, BoundarySeverity, SentinelBoundaryReport
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError


def test_boundary_finding_normalizes_fields_and_generates_id() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})
    finding = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.WARNING,
        violated_boundary=" Human Authority ",
        summary="  Proposal approaches human approval boundary. ",
    )

    assert finding.finding_id.value == (
        "ix-sentinel-1-warning-human-authority-proposal-approaches-human-approval-boundary"
    )
    assert finding.violated_boundary.value == "human-authority"
    assert finding.summary == "Proposal approaches human approval boundary."
    assert finding.blocks_progress() is False
    assert finding.terminates_run() is False


def test_boundary_finding_rejects_negative_cycle() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})

    with pytest.raises(FoundationError, match="boundary finding cycle must not be negative"):
        BoundaryFinding.create(
            cycle=-1,
            target_digest=target,
            severity=BoundarySeverity.WARNING,
            violated_boundary="human-authority",
            summary="Invalid cycle.",
        )


def test_boundary_finding_rejects_non_sha256_target_digest() -> None:
    target = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        BoundaryFinding.create(
            cycle=1,
            target_digest=target,
            severity=BoundarySeverity.WARNING,
            violated_boundary="human-authority",
            summary="Invalid digest.",
        )


def test_blocking_boundary_finding_requires_human_action() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})

    with pytest.raises(
        FoundationError,
        match="blocking or termination boundary findings require human action",
    ):
        BoundaryFinding.create(
            cycle=1,
            target_digest=target,
            severity=BoundarySeverity.BLOCKING,
            violated_boundary="tool-scope",
            summary="Tool scope is not authorized.",
        )


def test_termination_boundary_finding_records_human_action() -> None:
    target = DigestRecord.from_payload({"proposal": "unsafe escalation"})
    finding = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.TERMINATION,
        violated_boundary="authority-escalation",
        summary="Action attempts unauthorized authority escalation.",
        required_human_action="Terminate the chamber and require human review.",
    )

    assert finding.blocks_progress() is True
    assert finding.terminates_run() is True
    assert finding.required_human_action == "Terminate the chamber and require human review."


def test_boundary_finding_payload_is_stable() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})
    finding = BoundaryFinding.create(
        finding_id=CanonicalKey.from_text("finding-one", field_name="finding_id"),
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.BLOCKING,
        violated_boundary="tool-scope",
        summary="Tool action is outside contract.",
        required_human_action="Request explicit tool authorization.",
    )

    assert finding.to_payload() == {
        "finding_id": "finding-one",
        "cycle": 1,
        "target_digest": {
            "algorithm": "sha256",
            "value": target.value,
        },
        "severity": "blocking",
        "violated_boundary": "tool-scope",
        "summary": "Tool action is outside contract.",
        "required_human_action": "Request explicit tool authorization.",
        "blocks_progress": True,
        "terminates_run": False,
    }


def test_sentinel_boundary_report_requires_finding() -> None:
    with pytest.raises(FoundationError, match="boundary report requires at least one finding"):
        SentinelBoundaryReport.create(
            cycle=1,
            report_summary="No findings.",
            findings=(),
        )


def test_sentinel_boundary_report_rejects_cycle_mismatch() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})
    finding = BoundaryFinding.create(
        cycle=2,
        target_digest=target,
        severity=BoundarySeverity.WARNING,
        violated_boundary="human-authority",
        summary="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="boundary findings must match report cycle"):
        SentinelBoundaryReport.create(
            cycle=1,
            report_summary="Review boundaries.",
            findings=(finding,),
        )


def test_sentinel_boundary_report_counts_findings() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})
    warning = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.WARNING,
        violated_boundary="human-authority",
        summary="Boundary is close.",
    )
    blocking = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.BLOCKING,
        violated_boundary="tool-scope",
        summary="Tool scope is not authorized.",
        required_human_action="Request explicit authorization.",
    )
    termination = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.TERMINATION,
        violated_boundary="authority-escalation",
        summary="Unauthorized escalation.",
        required_human_action="Terminate chamber.",
    )
    report = SentinelBoundaryReport.create(
        cycle=1,
        report_summary="Review tool and authority boundaries.",
        findings=(warning, blocking, termination),
    )

    assert report.warning_count() == 1
    assert report.blocked_count() == 2
    assert report.termination_count() == 1
    assert report.has_blocker() is True
    assert report.terminates_run() is True


def test_sentinel_boundary_report_converts_to_artifact() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})
    finding = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.WARNING,
        violated_boundary="human-authority",
        summary="Boundary is close.",
    )
    report = SentinelBoundaryReport.create(
        cycle=1,
        report_summary="Review boundary status.",
        findings=(finding,),
    )

    artifact = report.to_artifact()

    assert artifact.role is AgentRole.SENTINEL
    assert artifact.kind is AgentArtifactKind.BOUNDARY_REPORT
    assert artifact.summary == "IX-Sentinel issued 1 boundary finding(s)."
    assert artifact.referenced_digests == (finding.digest(),)
    assert artifact.data == report.to_payload()


def test_sentinel_boundary_report_digest_changes_when_findings_change() -> None:
    target = DigestRecord.from_payload({"proposal": "tool action"})
    first_finding = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.WARNING,
        violated_boundary="human-authority",
        summary="First warning.",
    )
    second_finding = BoundaryFinding.create(
        cycle=1,
        target_digest=target,
        severity=BoundarySeverity.WARNING,
        violated_boundary="human-authority",
        summary="Second warning.",
    )
    first = SentinelBoundaryReport.create(
        cycle=1,
        report_summary="Review boundary status.",
        findings=(first_finding,),
    )
    second = SentinelBoundaryReport.create(
        cycle=1,
        report_summary="Review boundary status.",
        findings=(second_finding,),
    )

    assert first.digest().value != second.digest().value
