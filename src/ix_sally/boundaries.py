"""IX-Sentinel boundary reports for safety and authority control."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class BoundarySeverity(StrEnum):
    """Severity assigned to an IX-Sentinel boundary finding."""

    NOTICE = "notice"
    WARNING = "warning"
    BLOCKING = "blocking"
    TERMINATION = "termination"


@dataclass(frozen=True, slots=True)
class BoundaryFinding:
    """A safety, scope, or authority finding raised by IX-Sentinel."""

    finding_id: CanonicalKey
    cycle: int
    target_digest: DigestRecord
    severity: BoundarySeverity
    violated_boundary: CanonicalKey
    summary: str
    required_human_action: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        target_digest: DigestRecord,
        severity: BoundarySeverity,
        violated_boundary: str,
        summary: str,
        required_human_action: str | None = None,
        finding_id: CanonicalKey | None = None,
    ) -> BoundaryFinding:
        """Create a normalized IX-Sentinel boundary finding."""
        if cycle < 0:
            raise FoundationError("boundary finding cycle must not be negative")

        target_digest.require_algorithm("sha256")
        normalized_boundary = CanonicalKey.from_text(
            violated_boundary,
            field_name="violated_boundary",
        )
        normalized_summary = require_text(summary, field_name="summary")
        normalized_action = require_optional_text(
            required_human_action,
            field_name="required_human_action",
        )

        if severity in {BoundarySeverity.BLOCKING, BoundarySeverity.TERMINATION}:
            if normalized_action is None:
                raise FoundationError(
                    "blocking or termination boundary findings require human action"
                )

        return cls(
            finding_id=finding_id
            or CanonicalKey.from_text(
                f"ix-sentinel-{cycle}-{severity.value}-{normalized_boundary.value}"
                f"-{normalized_summary}",
                field_name="finding_id",
            ),
            cycle=cycle,
            target_digest=target_digest,
            severity=severity,
            violated_boundary=normalized_boundary,
            summary=normalized_summary,
            required_human_action=normalized_action,
        )

    def blocks_progress(self) -> bool:
        """Return whether this finding blocks autonomous progress."""
        return self.severity in {BoundarySeverity.BLOCKING, BoundarySeverity.TERMINATION}

    def terminates_run(self) -> bool:
        """Return whether this finding requires chamber termination."""
        return self.severity is BoundarySeverity.TERMINATION

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible boundary finding representation."""
        return {
            "finding_id": self.finding_id.value,
            "cycle": self.cycle,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "severity": self.severity.value,
            "violated_boundary": self.violated_boundary.value,
            "summary": self.summary,
            "required_human_action": self.required_human_action,
            "blocks_progress": self.blocks_progress(),
            "terminates_run": self.terminates_run(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this boundary finding."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SentinelBoundaryReport:
    """Structured IX-Sentinel report over chamber safety, scope, and authority."""

    report_id: CanonicalKey
    cycle: int
    report_summary: str
    findings: tuple[BoundaryFinding, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        report_summary: str,
        findings: Iterable[BoundaryFinding],
        report_id: CanonicalKey | None = None,
    ) -> SentinelBoundaryReport:
        """Create a normalized IX-Sentinel boundary report."""
        if cycle < 0:
            raise FoundationError("boundary report cycle must not be negative")

        normalized_summary = require_text(report_summary, field_name="report_summary")
        normalized_findings = tuple(findings)

        if not normalized_findings:
            raise FoundationError("boundary report requires at least one finding")

        for finding in normalized_findings:
            if finding.cycle != cycle:
                raise FoundationError("boundary findings must match report cycle")

        return cls(
            report_id=report_id
            or CanonicalKey.from_text(
                f"ix-sentinel-{cycle}-{normalized_summary}",
                field_name="report_id",
            ),
            cycle=cycle,
            report_summary=normalized_summary,
            findings=normalized_findings,
        )

    def warning_count(self) -> int:
        """Return the number of warning boundary findings."""
        return sum(1 for finding in self.findings if finding.severity is BoundarySeverity.WARNING)

    def blocked_count(self) -> int:
        """Return the number of findings that block autonomous progress."""
        return sum(1 for finding in self.findings if finding.blocks_progress())

    def termination_count(self) -> int:
        """Return the number of findings that terminate the chamber run."""
        return sum(1 for finding in self.findings if finding.terminates_run())

    def has_blocker(self) -> bool:
        """Return whether this report contains any blocking boundary finding."""
        return self.blocked_count() > 0

    def terminates_run(self) -> bool:
        """Return whether this report requires chamber termination."""
        return self.termination_count() > 0

    def to_artifact(self) -> AgentArtifact:
        """Convert this report into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.SENTINEL,
            kind=AgentArtifactKind.BOUNDARY_REPORT,
            summary=f"IX-Sentinel issued {len(self.findings)} boundary finding(s).",
            referenced_digests=tuple(finding.digest() for finding in self.findings),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible boundary report representation."""
        findings_payload: JsonArray = []
        for finding in self.findings:
            findings_payload.append(finding.to_payload())

        return {
            "report_id": self.report_id.value,
            "cycle": self.cycle,
            "report_summary": self.report_summary,
            "findings": findings_payload,
            "warning_count": self.warning_count(),
            "blocked_count": self.blocked_count(),
            "termination_count": self.termination_count(),
            "has_blocker": self.has_blocker(),
            "terminates_run": self.terminates_run(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this boundary report."""
        return DigestRecord.from_payload(self.to_payload())
