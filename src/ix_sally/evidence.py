"""Evidence records for IX-Sally claim support and execution receipts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class EvidenceKind(StrEnum):
    """Kinds of evidence that may support or reject runtime claims."""

    OBSERVATION = "observation"
    EXECUTION_RECEIPT = "execution_receipt"
    TEST_RESULT = "test_result"
    HUMAN_REVIEW = "human_review"
    SOURCE_RECORD = "source_record"


class EvidenceStatus(StrEnum):
    """Status assigned to an evidence record."""

    RECORDED = "recorded"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """A deterministic evidence item linked to a claim, action, or observation."""

    evidence_id: CanonicalKey
    cycle: int
    produced_by: AgentRole
    kind: EvidenceKind
    status: EvidenceStatus
    summary: str
    subject_claim_id: CanonicalKey | None = None
    data: JsonObject = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        produced_by: AgentRole,
        kind: EvidenceKind,
        status: EvidenceStatus,
        summary: str,
        subject_claim_id: str | None = None,
        data: JsonObject | None = None,
        evidence_id: CanonicalKey | None = None,
    ) -> EvidenceRecord:
        """Create a normalized evidence record."""
        if cycle < 0:
            raise FoundationError("evidence cycle must not be negative")

        normalized_summary = require_text(summary, field_name="summary")
        normalized_subject = (
            CanonicalKey.from_text(subject_claim_id, field_name="subject_claim_id")
            if subject_claim_id is not None
            else None
        )

        return cls(
            evidence_id=evidence_id
            or CanonicalKey.from_text(
                f"{produced_by.value}-{cycle}-{kind.value}-{normalized_summary}",
                field_name="evidence_id",
            ),
            cycle=cycle,
            produced_by=produced_by,
            kind=kind,
            status=status,
            summary=normalized_summary,
            subject_claim_id=normalized_subject,
            data=data or {},
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible evidence representation."""
        return {
            "evidence_id": self.evidence_id.value,
            "cycle": self.cycle,
            "produced_by": self.produced_by.value,
            "kind": self.kind.value,
            "status": self.status.value,
            "summary": self.summary,
            "subject_claim_id": (
                self.subject_claim_id.value if self.subject_claim_id is not None else None
            ),
            "data": self.data,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this evidence record."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class EvidenceLedger:
    """Immutable evidence ledger for a chamber run."""

    records: tuple[EvidenceRecord, ...]

    @classmethod
    def create(cls, records: Iterable[EvidenceRecord]) -> EvidenceLedger:
        """Create an evidence ledger and reject duplicate evidence identifiers."""
        normalized = tuple(records)
        seen: set[str] = set()

        for record in normalized:
            if record.evidence_id.value in seen:
                raise FoundationError(f"duplicate evidence id: {record.evidence_id.value}")
            seen.add(record.evidence_id.value)

        return cls(records=normalized)

    def append(self, record: EvidenceRecord) -> EvidenceLedger:
        """Return a new ledger with an appended evidence record."""
        return EvidenceLedger.create((*self.records, record))

    def require_evidence(self, evidence_id: str) -> EvidenceRecord:
        """Return an evidence record by identifier or raise a construction error."""
        requested = CanonicalKey.from_text(evidence_id, field_name="evidence_id")
        for record in self.records:
            if record.evidence_id == requested:
                return record
        raise FoundationError(f"unknown evidence id: {requested.value}")

    def by_status(self, status: EvidenceStatus) -> tuple[EvidenceRecord, ...]:
        """Return all evidence records matching the requested status."""
        return tuple(record for record in self.records if record.status is status)

    def for_claim(self, claim_id: str) -> tuple[EvidenceRecord, ...]:
        """Return all evidence records linked to a claim identifier."""
        requested = CanonicalKey.from_text(claim_id, field_name="claim_id")
        return tuple(record for record in self.records if record.subject_claim_id == requested)

    def passed_for_claim(self, claim_id: str) -> tuple[EvidenceRecord, ...]:
        """Return passed evidence records linked to a claim identifier."""
        return tuple(
            record for record in self.for_claim(claim_id) if record.status is EvidenceStatus.PASSED
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible evidence ledger representation."""
        records_payload: JsonArray = []
        for record in self.records:
            records_payload.append(record.to_payload())

        return {
            "records": records_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this evidence ledger."""
        return DigestRecord.from_payload(self.to_payload())
