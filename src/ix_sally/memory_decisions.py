"""IX-Mnemosyne memory decision packets for governed learning control."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text
from ix_sally.memory import MemoryStatus


class MemoryDecisionAction(StrEnum):
    """Actions IX-Mnemosyne may take over a memory candidate."""

    STAGE_CANDIDATE = "stage_candidate"
    KEEP_PENDING = "keep_pending"
    VERIFY = "verify"
    MARK_STALE = "mark_stale"
    MARK_CONTRADICTED = "mark_contradicted"
    QUARANTINE = "quarantine"
    REJECT = "reject"


_ACTION_RESULT_STATUS: dict[MemoryDecisionAction, MemoryStatus] = {
    MemoryDecisionAction.STAGE_CANDIDATE: MemoryStatus.CANDIDATE,
    MemoryDecisionAction.KEEP_PENDING: MemoryStatus.PENDING_EVIDENCE,
    MemoryDecisionAction.VERIFY: MemoryStatus.VERIFIED,
    MemoryDecisionAction.MARK_STALE: MemoryStatus.STALE,
    MemoryDecisionAction.MARK_CONTRADICTED: MemoryStatus.CONTRADICTED,
    MemoryDecisionAction.QUARANTINE: MemoryStatus.QUARANTINED,
    MemoryDecisionAction.REJECT: MemoryStatus.REJECTED,
}


@dataclass(frozen=True, slots=True)
class MnemosyneMemoryDecision:
    """A governed decision about whether a memory may be retained, learned, or blocked."""

    decision_id: CanonicalKey
    cycle: int
    memory_digest: DigestRecord
    action: MemoryDecisionAction
    resulting_status: MemoryStatus
    rationale: str
    evidence_digests: tuple[DigestRecord, ...] = field(default_factory=tuple)
    boundary_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        memory_digest: DigestRecord,
        action: MemoryDecisionAction,
        rationale: str,
        evidence_digests: Iterable[DigestRecord] = (),
        boundary_note: str | None = None,
        decision_id: CanonicalKey | None = None,
    ) -> MnemosyneMemoryDecision:
        """Create a normalized IX-Mnemosyne memory decision."""
        if cycle < 0:
            raise FoundationError("memory decision cycle must not be negative")

        memory_digest.require_algorithm("sha256")
        normalized_evidence = tuple(evidence_digests)
        for evidence_digest in normalized_evidence:
            evidence_digest.require_algorithm("sha256")

        resulting_status = _ACTION_RESULT_STATUS[action]
        normalized_rationale = require_text(rationale, field_name="rationale")
        normalized_boundary_note = require_optional_text(
            boundary_note,
            field_name="boundary_note",
        )

        if resulting_status is MemoryStatus.VERIFIED and not normalized_evidence:
            raise FoundationError("verified memory decisions require evidence digests")

        if resulting_status in {
            MemoryStatus.CONTRADICTED,
            MemoryStatus.QUARANTINED,
            MemoryStatus.REJECTED,
        } and normalized_boundary_note is None:
            raise FoundationError("blocking memory decisions require a boundary note")

        return cls(
            decision_id=decision_id
            or CanonicalKey.from_text(
                f"ix-mnemosyne-{cycle}-{action.value}-{normalized_rationale}",
                field_name="decision_id",
            ),
            cycle=cycle,
            memory_digest=memory_digest,
            action=action,
            resulting_status=resulting_status,
            rationale=normalized_rationale,
            evidence_digests=normalized_evidence,
            boundary_note=normalized_boundary_note,
        )

    def writes_verified_memory(self) -> bool:
        """Return whether this decision authorizes verified memory status."""
        return self.resulting_status is MemoryStatus.VERIFIED

    def blocks_memory(self) -> bool:
        """Return whether this decision prevents the memory from being treated as truth."""
        return self.resulting_status in {
            MemoryStatus.CONTRADICTED,
            MemoryStatus.QUARANTINED,
            MemoryStatus.REJECTED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible memory decision representation."""
        evidence_payload: JsonArray = []
        for evidence_digest in self.evidence_digests:
            evidence_payload.append(
                {
                    "algorithm": evidence_digest.algorithm,
                    "value": evidence_digest.value,
                }
            )

        return {
            "decision_id": self.decision_id.value,
            "cycle": self.cycle,
            "memory_digest": {
                "algorithm": self.memory_digest.algorithm,
                "value": self.memory_digest.value,
            },
            "action": self.action.value,
            "resulting_status": self.resulting_status.value,
            "rationale": self.rationale,
            "evidence_digests": evidence_payload,
            "boundary_note": self.boundary_note,
            "writes_verified_memory": self.writes_verified_memory(),
            "blocks_memory": self.blocks_memory(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this memory decision."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class MnemosyneMemoryDecisionPacket:
    """Structured IX-Mnemosyne packet containing governed memory decisions."""

    packet_id: CanonicalKey
    cycle: int
    memory_review_summary: str
    decisions: tuple[MnemosyneMemoryDecision, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        memory_review_summary: str,
        decisions: Iterable[MnemosyneMemoryDecision],
        packet_id: CanonicalKey | None = None,
    ) -> MnemosyneMemoryDecisionPacket:
        """Create a normalized IX-Mnemosyne memory decision packet."""
        if cycle < 0:
            raise FoundationError("memory decision packet cycle must not be negative")

        normalized_summary = require_text(
            memory_review_summary,
            field_name="memory_review_summary",
        )
        normalized_decisions = tuple(decisions)

        if not normalized_decisions:
            raise FoundationError("memory decision packet requires at least one decision")

        for decision in normalized_decisions:
            if decision.cycle != cycle:
                raise FoundationError("memory decisions must match packet cycle")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-mnemosyne-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            memory_review_summary=normalized_summary,
            decisions=normalized_decisions,
        )

    def verified_count(self) -> int:
        """Return the number of decisions authorizing verified memory."""
        return sum(1 for decision in self.decisions if decision.writes_verified_memory())

    def blocked_count(self) -> int:
        """Return the number of decisions blocking memory use."""
        return sum(1 for decision in self.decisions if decision.blocks_memory())

    def has_blocker(self) -> bool:
        """Return whether this packet contains a blocking memory decision."""
        return self.blocked_count() > 0

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.MNEMOSYNE,
            kind=AgentArtifactKind.MEMORY_DECISION,
            summary=f"IX-Mnemosyne issued {len(self.decisions)} memory decision(s).",
            referenced_digests=tuple(decision.digest() for decision in self.decisions),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible memory decision packet representation."""
        decisions_payload: JsonArray = []
        for decision in self.decisions:
            decisions_payload.append(decision.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "memory_review_summary": self.memory_review_summary,
            "decisions": decisions_payload,
            "verified_count": self.verified_count(),
            "blocked_count": self.blocked_count(),
            "has_blocker": self.has_blocker(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this memory decision packet."""
        return DigestRecord.from_payload(self.to_payload())
