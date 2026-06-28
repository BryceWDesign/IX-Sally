"""Memory records for IX-Sally learning, quarantine, and truth-boundary control."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class MemoryStatus(StrEnum):
    """Status assigned to a memory candidate inside IX-Sally."""

    CANDIDATE = "candidate"
    PENDING_EVIDENCE = "pending_evidence"
    VERIFIED = "verified"
    STALE = "stale"
    CONTRADICTED = "contradicted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A memory candidate that cannot become truth without evidence discipline."""

    memory_id: CanonicalKey
    cycle: int
    proposed_by: AgentRole
    content: str
    status: MemoryStatus = MemoryStatus.CANDIDATE
    evidence_digests: tuple[DigestRecord, ...] = field(default_factory=tuple)
    reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        proposed_by: AgentRole,
        content: str,
        status: MemoryStatus = MemoryStatus.CANDIDATE,
        evidence_digests: Iterable[DigestRecord] = (),
        reason: str | None = None,
        memory_id: CanonicalKey | None = None,
    ) -> MemoryRecord:
        """Create a normalized memory record."""
        if cycle < 0:
            raise FoundationError("memory cycle must not be negative")

        normalized_content = require_text(content, field_name="content")
        normalized_evidence = tuple(evidence_digests)
        for evidence_digest in normalized_evidence:
            evidence_digest.require_algorithm("sha256")

        if status is MemoryStatus.VERIFIED and not normalized_evidence:
            raise FoundationError("verified memory requires at least one evidence digest")

        if status in {MemoryStatus.CONTRADICTED, MemoryStatus.QUARANTINED, MemoryStatus.REJECTED}:
            require_text(reason or "", field_name="reason")

        normalized_reason = reason
        if normalized_reason is not None:
            normalized_reason = require_text(normalized_reason, field_name="reason")

        return cls(
            memory_id=memory_id
            or CanonicalKey.from_text(
                f"{proposed_by.value}-{cycle}-{normalized_content}",
                field_name="memory_id",
            ),
            cycle=cycle,
            proposed_by=proposed_by,
            content=normalized_content,
            status=status,
            evidence_digests=normalized_evidence,
            reason=normalized_reason,
        )

    def with_status(
        self,
        status: MemoryStatus,
        *,
        evidence_digests: Iterable[DigestRecord] | None = None,
        reason: str | None = None,
    ) -> MemoryRecord:
        """Return this memory record with a new status."""
        return MemoryRecord.create(
            memory_id=self.memory_id,
            cycle=self.cycle,
            proposed_by=self.proposed_by,
            content=self.content,
            status=status,
            evidence_digests=self.evidence_digests
            if evidence_digests is None
            else evidence_digests,
            reason=self.reason if reason is None else reason,
        )

    @property
    def is_truth_claim(self) -> bool:
        """Return whether this memory may be treated as verified runtime knowledge."""
        return self.status is MemoryStatus.VERIFIED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible memory representation."""
        evidence_payload: JsonArray = []
        for evidence_digest in self.evidence_digests:
            evidence_payload.append(
                {
                    "algorithm": evidence_digest.algorithm,
                    "value": evidence_digest.value,
                }
            )

        return {
            "memory_id": self.memory_id.value,
            "cycle": self.cycle,
            "proposed_by": self.proposed_by.value,
            "content": self.content,
            "status": self.status.value,
            "evidence_digests": evidence_payload,
            "reason": self.reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this memory record."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class MemoryLedger:
    """Immutable memory ledger for IX-Sally memory-law decisions."""

    records: tuple[MemoryRecord, ...]

    @classmethod
    def create(cls, records: Iterable[MemoryRecord]) -> MemoryLedger:
        """Create a memory ledger and reject duplicate memory identifiers."""
        normalized = tuple(records)
        seen: set[str] = set()

        for record in normalized:
            if record.memory_id.value in seen:
                raise FoundationError(f"duplicate memory id: {record.memory_id.value}")
            seen.add(record.memory_id.value)

        return cls(records=normalized)

    def append(self, record: MemoryRecord) -> MemoryLedger:
        """Return a new ledger with an appended memory record."""
        return MemoryLedger.create((*self.records, record))

    def require_memory(self, memory_id: str) -> MemoryRecord:
        """Return a memory record by identifier or raise a construction error."""
        requested = CanonicalKey.from_text(memory_id, field_name="memory_id")
        for record in self.records:
            if record.memory_id == requested:
                return record
        raise FoundationError(f"unknown memory id: {requested.value}")

    def by_status(self, status: MemoryStatus) -> tuple[MemoryRecord, ...]:
        """Return all memory records matching the requested status."""
        return tuple(record for record in self.records if record.status is status)

    def truth_claims(self) -> tuple[MemoryRecord, ...]:
        """Return verified memory records only."""
        return tuple(record for record in self.records if record.is_truth_claim)

    def blocked_records(self) -> tuple[MemoryRecord, ...]:
        """Return records that must not be treated as runtime truth."""
        blocked_statuses = {
            MemoryStatus.CONTRADICTED,
            MemoryStatus.QUARANTINED,
            MemoryStatus.REJECTED,
        }
        return tuple(record for record in self.records if record.status in blocked_statuses)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible memory ledger representation."""
        records_payload: JsonArray = []
        for record in self.records:
            records_payload.append(record.to_payload())

        return {
            "records": records_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this memory ledger."""
        return DigestRecord.from_payload(self.to_payload())
