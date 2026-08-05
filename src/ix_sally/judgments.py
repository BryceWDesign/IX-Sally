"""IX-Verity evidence judgment packets for claim support control."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class EvidenceJudgmentStatus(StrEnum):
    """Statuses IX-Verity may assign to a claim after evidence review."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PENDING_EVIDENCE = "pending_evidence"
    CONTRADICTED = "contradicted"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class VerityEvidenceJudgment:
    """A single IX-Verity judgment over a claim digest and its evidence."""

    judgment_id: CanonicalKey
    cycle: int
    claim_digest: DigestRecord
    status: EvidenceJudgmentStatus
    rationale: str
    evidence_digests: tuple[DigestRecord, ...] = field(default_factory=tuple)
    doctrine_key: CanonicalKey | None = None
    boundary_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        claim_digest: DigestRecord,
        status: EvidenceJudgmentStatus,
        rationale: str,
        evidence_digests: Iterable[DigestRecord] = (),
        doctrine_key: str | None = None,
        boundary_note: str | None = None,
        judgment_id: CanonicalKey | None = None,
    ) -> VerityEvidenceJudgment:
        """Create a normalized IX-Verity evidence judgment."""
        if cycle < 0:
            raise FoundationError("evidence judgment cycle must not be negative")

        claim_digest.require_algorithm("sha256")
        normalized_evidence = tuple(evidence_digests)
        for evidence_digest in normalized_evidence:
            evidence_digest.require_algorithm("sha256")

        if status is EvidenceJudgmentStatus.SUPPORTED and not normalized_evidence:
            raise FoundationError("supported evidence judgments require evidence digests")

        if status is EvidenceJudgmentStatus.BLOCKED and boundary_note is None:
            raise FoundationError("blocked evidence judgments require a boundary note")

        normalized_rationale = require_text(rationale, field_name="rationale")
        normalized_doctrine_key = (
            CanonicalKey.from_text(doctrine_key, field_name="doctrine_key")
            if doctrine_key is not None
            else None
        )
        normalized_boundary_note = require_optional_text(
            boundary_note,
            field_name="boundary_note",
        )

        return cls(
            judgment_id=judgment_id
            or CanonicalKey.from_text(
                f"ix-verity-{cycle}-{status.value}-{normalized_rationale}",
                field_name="judgment_id",
            ),
            cycle=cycle,
            claim_digest=claim_digest,
            status=status,
            rationale=normalized_rationale,
            evidence_digests=normalized_evidence,
            doctrine_key=normalized_doctrine_key,
            boundary_note=normalized_boundary_note,
        )

    def supports_claim(self) -> bool:
        """Return whether this judgment supports the reviewed claim."""
        return self.status is EvidenceJudgmentStatus.SUPPORTED

    def blocks_claim(self) -> bool:
        """Return whether this judgment blocks the reviewed claim."""
        return self.status in {
            EvidenceJudgmentStatus.CONTRADICTED,
            EvidenceJudgmentStatus.BLOCKED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible evidence judgment representation."""
        evidence_payload: JsonArray = []
        for evidence_digest in self.evidence_digests:
            evidence_payload.append(
                {
                    "algorithm": evidence_digest.algorithm,
                    "value": evidence_digest.value,
                }
            )

        return {
            "judgment_id": self.judgment_id.value,
            "cycle": self.cycle,
            "claim_digest": {
                "algorithm": self.claim_digest.algorithm,
                "value": self.claim_digest.value,
            },
            "status": self.status.value,
            "rationale": self.rationale,
            "evidence_digests": evidence_payload,
            "doctrine_key": self.doctrine_key.value if self.doctrine_key is not None else None,
            "boundary_note": self.boundary_note,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this evidence judgment."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class VerityJudgmentPacket:
    """Structured IX-Verity packet that adjudicates claim support without acting."""

    packet_id: CanonicalKey
    cycle: int
    review_summary: str
    judgments: tuple[VerityEvidenceJudgment, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        review_summary: str,
        judgments: Iterable[VerityEvidenceJudgment],
        packet_id: CanonicalKey | None = None,
    ) -> VerityJudgmentPacket:
        """Create a normalized IX-Verity judgment packet."""
        if cycle < 0:
            raise FoundationError("evidence judgment packet cycle must not be negative")

        normalized_summary = require_text(review_summary, field_name="review_summary")
        normalized_judgments = tuple(judgments)

        if not normalized_judgments:
            raise FoundationError("evidence judgment packet requires at least one judgment")

        for judgment in normalized_judgments:
            if judgment.cycle != cycle:
                raise FoundationError("evidence judgments must match packet cycle")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-verity-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            review_summary=normalized_summary,
            judgments=normalized_judgments,
        )

    def supported_count(self) -> int:
        """Return the number of supported judgments in this packet."""
        return sum(1 for judgment in self.judgments if judgment.supports_claim())

    def blocked_count(self) -> int:
        """Return the number of blocking judgments in this packet."""
        return sum(1 for judgment in self.judgments if judgment.blocks_claim())

    def has_blocker(self) -> bool:
        """Return whether this packet contains any blocking judgment."""
        return self.blocked_count() > 0

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.VERITY,
            kind=AgentArtifactKind.EVIDENCE_JUDGMENT,
            summary=f"IX-Verity issued {len(self.judgments)} evidence judgment(s).",
            referenced_digests=tuple(judgment.digest() for judgment in self.judgments),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible judgment packet representation."""
        judgments_payload: JsonArray = []
        for judgment in self.judgments:
            judgments_payload.append(judgment.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "review_summary": self.review_summary,
            "judgments": judgments_payload,
            "supported_count": self.supported_count(),
            "blocked_count": self.blocked_count(),
            "has_blocker": self.has_blocker(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this judgment packet."""
        return DigestRecord.from_payload(self.to_payload())
