"""IX-Butch falsification packets for adversarial challenge inside IX-Sally."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class FalsificationSeverity(StrEnum):
    """Severity assigned to an adversarial falsification finding."""

    OBSERVATION = "observation"
    CONCERN = "concern"
    BLOCKER = "blocker"


@dataclass(frozen=True, slots=True)
class FalsificationFinding:
    """A specific challenge raised against a proposal, claim, memory, or action."""

    finding_id: CanonicalKey
    cycle: int
    target_digest: DigestRecord
    severity: FalsificationSeverity
    summary: str
    doctrine_key: CanonicalKey | None = None
    suggested_repair: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        target_digest: DigestRecord,
        severity: FalsificationSeverity,
        summary: str,
        doctrine_key: str | None = None,
        suggested_repair: str | None = None,
        finding_id: CanonicalKey | None = None,
    ) -> FalsificationFinding:
        """Create a normalized falsification finding."""
        if cycle < 0:
            raise FoundationError("falsification cycle must not be negative")

        target_digest.require_algorithm("sha256")
        normalized_summary = require_text(summary, field_name="summary")
        normalized_doctrine_key = (
            CanonicalKey.from_text(doctrine_key, field_name="doctrine_key")
            if doctrine_key is not None
            else None
        )
        normalized_repair = require_optional_text(
            suggested_repair,
            field_name="suggested_repair",
        )

        if severity is FalsificationSeverity.BLOCKER and normalized_repair is None:
            raise FoundationError("blocker falsifications require a suggested repair")

        return cls(
            finding_id=finding_id
            or CanonicalKey.from_text(
                f"ix-butch-{cycle}-{severity.value}-{normalized_summary}",
                field_name="finding_id",
            ),
            cycle=cycle,
            target_digest=target_digest,
            severity=severity,
            summary=normalized_summary,
            doctrine_key=normalized_doctrine_key,
            suggested_repair=normalized_repair,
        )

    def blocks_progress(self) -> bool:
        """Return whether this finding blocks the current runtime path."""
        return self.severity is FalsificationSeverity.BLOCKER

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible finding representation."""
        return {
            "finding_id": self.finding_id.value,
            "cycle": self.cycle,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "severity": self.severity.value,
            "summary": self.summary,
            "doctrine_key": self.doctrine_key.value if self.doctrine_key is not None else None,
            "suggested_repair": self.suggested_repair,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this falsification finding."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ButchFalsificationPacket:
    """Structured IX-Butch packet that challenges a target without deciding truth."""

    packet_id: CanonicalKey
    cycle: int
    target_summary: str
    target_digest: DigestRecord
    findings: tuple[FalsificationFinding, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        target_summary: str,
        target_digest: DigestRecord,
        findings: Iterable[FalsificationFinding],
        packet_id: CanonicalKey | None = None,
    ) -> ButchFalsificationPacket:
        """Create a normalized falsification packet."""
        if cycle < 0:
            raise FoundationError("falsification packet cycle must not be negative")

        target_digest.require_algorithm("sha256")
        normalized_summary = require_text(target_summary, field_name="target_summary")
        normalized_findings = tuple(findings)

        if not normalized_findings:
            raise FoundationError("falsification packet requires at least one finding")

        for finding in normalized_findings:
            if finding.cycle != cycle:
                raise FoundationError("falsification findings must match packet cycle")
            if finding.target_digest != target_digest:
                raise FoundationError("falsification findings must target the packet digest")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-butch-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            target_summary=normalized_summary,
            target_digest=target_digest,
            findings=normalized_findings,
        )

    def has_blocker(self) -> bool:
        """Return whether any finding blocks the challenged path."""
        return any(finding.blocks_progress() for finding in self.findings)

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        referenced_digests = (self.target_digest, *(finding.digest() for finding in self.findings))
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.BUTCH,
            kind=AgentArtifactKind.FALSIFICATION,
            summary=f"IX-Butch raised {len(self.findings)} falsification finding(s).",
            referenced_digests=referenced_digests,
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible falsification packet representation."""
        findings_payload: JsonArray = []
        for finding in self.findings:
            findings_payload.append(finding.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "target_summary": self.target_summary,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "findings": findings_payload,
            "has_blocker": self.has_blocker(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this falsification packet."""
        return DigestRecord.from_payload(self.to_payload())
