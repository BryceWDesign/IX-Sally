"""Immutable ledger for IX-Sally human-review resume certificates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_resume import HumanReviewResumeResult
from ix_sally.stage_readiness import RunStage


@dataclass(frozen=True, slots=True)
class HumanReviewResumeLedgerEntry:
    """One immutable ledger entry for a cleared human-review resume certificate."""

    entry_id: CanonicalKey
    sequence: int
    certificate_digest: DigestRecord
    assessment_digest: DigestRecord
    clearance_report_digest: DigestRecord
    reviewed_state_digest: DigestRecord
    resumed_state_digest: DigestRecord
    resumed_snapshot_digest: DigestRecord
    resumed_stage: RunStage
    authority_note: str
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        certificate_digest: DigestRecord,
        assessment_digest: DigestRecord,
        clearance_report_digest: DigestRecord,
        reviewed_state_digest: DigestRecord,
        resumed_state_digest: DigestRecord,
        resumed_snapshot_digest: DigestRecord,
        resumed_stage: RunStage,
        authority_note: str,
        rationale: str,
        entry_id: CanonicalKey | None = None,
    ) -> HumanReviewResumeLedgerEntry:
        """Create a normalized human-review resume ledger entry."""
        if sequence <= 0:
            raise FoundationError("human-review resume ledger sequence must be positive")
        if resumed_stage is RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review resume ledger cannot resume to human_review")

        certificate_digest.require_algorithm("sha256")
        assessment_digest.require_algorithm("sha256")
        clearance_report_digest.require_algorithm("sha256")
        reviewed_state_digest.require_algorithm("sha256")
        resumed_state_digest.require_algorithm("sha256")
        resumed_snapshot_digest.require_algorithm("sha256")

        normalized_authority_note = require_text(
            authority_note,
            field_name="authority_note",
        )
        normalized_rationale = require_text(rationale, field_name="rationale")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"human-review-resume-ledger-{sequence}-"
                f"{certificate_digest.value[:16]}-{resumed_state_digest.value[:16]}",
                field_name="entry_id",
            ),
            sequence=sequence,
            certificate_digest=certificate_digest,
            assessment_digest=assessment_digest,
            clearance_report_digest=clearance_report_digest,
            reviewed_state_digest=reviewed_state_digest,
            resumed_state_digest=resumed_state_digest,
            resumed_snapshot_digest=resumed_snapshot_digest,
            resumed_stage=resumed_stage,
            authority_note=normalized_authority_note,
            rationale=normalized_rationale,
        )

    @classmethod
    def from_result(
        cls,
        *,
        sequence: int,
        result: HumanReviewResumeResult,
    ) -> HumanReviewResumeLedgerEntry:
        """Create a resume ledger entry from a certified resume result."""
        if not result.cleared_to_resume():
            raise FoundationError("human-review resume ledger requires cleared result")

        return cls.create(
            sequence=sequence,
            certificate_digest=result.certificate.digest(),
            assessment_digest=result.assessment.digest(),
            clearance_report_digest=result.assessment.clearance_report.digest(),
            reviewed_state_digest=result.assessment.bundle.snapshot.state_digest,
            resumed_state_digest=result.resumed_state.digest(),
            resumed_snapshot_digest=result.resumed_snapshot.digest(),
            resumed_stage=result.next_stage(),
            authority_note=result.certificate.authority_note,
            rationale=result.certificate.rationale,
        )

    def cleared_to_resume(self) -> bool:
        """Return whether this entry records a cleared resume authorization."""
        return True

    def resumed_to(self, stage: RunStage) -> bool:
        """Return whether this entry resumes orchestration at the requested stage."""
        return self.resumed_stage is stage

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible resume ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "certificate_digest": {
                "algorithm": self.certificate_digest.algorithm,
                "value": self.certificate_digest.value,
            },
            "assessment_digest": {
                "algorithm": self.assessment_digest.algorithm,
                "value": self.assessment_digest.value,
            },
            "clearance_report_digest": {
                "algorithm": self.clearance_report_digest.algorithm,
                "value": self.clearance_report_digest.value,
            },
            "reviewed_state_digest": {
                "algorithm": self.reviewed_state_digest.algorithm,
                "value": self.reviewed_state_digest.value,
            },
            "resumed_state_digest": {
                "algorithm": self.resumed_state_digest.algorithm,
                "value": self.resumed_state_digest.value,
            },
            "resumed_snapshot_digest": {
                "algorithm": self.resumed_snapshot_digest.algorithm,
                "value": self.resumed_snapshot_digest.value,
            },
            "resumed_stage": self.resumed_stage.value,
            "authority_note": self.authority_note,
            "rationale": self.rationale,
            "cleared_to_resume": self.cleared_to_resume(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this resume ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewResumeLedger:
    """Immutable ledger of cleared human-review resume certificates."""

    entries: tuple[HumanReviewResumeLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[HumanReviewResumeLedgerEntry],
    ) -> HumanReviewResumeLedger:
        """Create a resume ledger and reject duplicate or out-of-order entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_certificate_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate human-review resume ledger sequence: {entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate human-review resume ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.certificate_digest.value in seen_certificate_digests:
                raise FoundationError(
                    f"duplicate human-review resume certificate digest: "
                    f"{entry.certificate_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "human-review resume ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_certificate_digests.add(entry.certificate_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: HumanReviewResumeLedgerEntry,
    ) -> HumanReviewResumeLedger:
        """Return a new ledger with an appended resume entry."""
        return HumanReviewResumeLedger.create((*self.entries, entry))

    def append_result(
        self,
        result: HumanReviewResumeResult,
    ) -> HumanReviewResumeLedger:
        """Return a new ledger with a resume result recorded at the next sequence."""
        return self.append(
            HumanReviewResumeLedgerEntry.from_result(
                sequence=self.next_sequence(),
                result=result,
            )
        )

    def latest(self) -> HumanReviewResumeLedgerEntry | None:
        """Return the latest resume entry, if any."""
        if not self.entries:
            return None
        return self.entries[-1]

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[HumanReviewResumeLedgerEntry, ...]:
        """Return resume entries that resume at the requested stage."""
        return tuple(entry for entry in self.entries if entry.resumed_to(stage))

    def cleared_entries(self) -> tuple[HumanReviewResumeLedgerEntry, ...]:
        """Return entries that certify cleared resume authorization."""
        return tuple(entry for entry in self.entries if entry.cleared_to_resume())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review resume ledger."""
        entry_payload: JsonArray = []
        for entry in self.entries:
            entry_payload.append(entry.to_payload())

        latest = self.latest()

        return {
            "entries": entry_payload,
            "entry_count": len(self.entries),
            "next_sequence": self.next_sequence(),
            "latest_entry_digest": latest.digest().value if latest is not None else None,
            "cleared_entry_count": len(self.cleared_entries()),
            "execution_planning_resume_count": len(
                self.entries_for_stage(RunStage.EXECUTION_PLANNING)
            ),
            "proposal_intake_resume_count": len(
                self.entries_for_stage(RunStage.PROPOSAL_INTAKE)
            ),
            "chamber_close_resume_count": len(
                self.entries_for_stage(RunStage.CHAMBER_CLOSE_READY)
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review resume ledger."""
        return DigestRecord.from_payload(self.to_payload())
