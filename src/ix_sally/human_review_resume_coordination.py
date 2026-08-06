"""Coordinated certification and ledgering of IX-Sally human-review resumes."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.human_review_resume import (
    HumanReviewResumeCoordinator,
    HumanReviewResumeResult,
)
from ix_sally.human_review_resume_ledger import (
    HumanReviewResumeLedger,
    HumanReviewResumeLedgerEntry,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewResumeCoordinationReceipt:
    """Compact receipt for a certified and ledgered human-review resume."""

    receipt_id: CanonicalKey
    before_ledger_digest: DigestRecord
    after_ledger_digest: DigestRecord
    resume_result_digest: DigestRecord
    ledger_entry_digest: DigestRecord
    certificate_digest: DigestRecord
    reviewed_state_digest: DigestRecord
    resumed_state_digest: DigestRecord
    resumed_stage: RunStage
    authority_note: str
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        before_ledger_digest: DigestRecord,
        after_ledger_digest: DigestRecord,
        resume_result_digest: DigestRecord,
        ledger_entry_digest: DigestRecord,
        certificate_digest: DigestRecord,
        reviewed_state_digest: DigestRecord,
        resumed_state_digest: DigestRecord,
        resumed_stage: RunStage,
        authority_note: str,
        rationale: str,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewResumeCoordinationReceipt:
        """Create a normalized human-review resume coordination receipt."""
        if resumed_stage is RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review resume coordination cannot resume to human_review")

        before_ledger_digest.require_algorithm("sha256")
        after_ledger_digest.require_algorithm("sha256")
        resume_result_digest.require_algorithm("sha256")
        ledger_entry_digest.require_algorithm("sha256")
        certificate_digest.require_algorithm("sha256")
        reviewed_state_digest.require_algorithm("sha256")
        resumed_state_digest.require_algorithm("sha256")

        normalized_authority_note = require_text(
            authority_note,
            field_name="authority_note",
        )
        normalized_rationale = require_text(rationale, field_name="rationale")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-resume-coordination-"
                f"{certificate_digest.value[:16]}-{ledger_entry_digest.value[:16]}",
                field_name="receipt_id",
            ),
            before_ledger_digest=before_ledger_digest,
            after_ledger_digest=after_ledger_digest,
            resume_result_digest=resume_result_digest,
            ledger_entry_digest=ledger_entry_digest,
            certificate_digest=certificate_digest,
            reviewed_state_digest=reviewed_state_digest,
            resumed_state_digest=resumed_state_digest,
            resumed_stage=resumed_stage,
            authority_note=normalized_authority_note,
            rationale=normalized_rationale,
        )

    @classmethod
    def from_coordination(
        cls,
        *,
        before_ledger: HumanReviewResumeLedger,
        after_ledger: HumanReviewResumeLedger,
        resume_result: HumanReviewResumeResult,
        entry: HumanReviewResumeLedgerEntry,
    ) -> HumanReviewResumeCoordinationReceipt:
        """Create a coordination receipt from a resume result and ledger entry."""
        return cls.create(
            before_ledger_digest=before_ledger.digest(),
            after_ledger_digest=after_ledger.digest(),
            resume_result_digest=resume_result.digest(),
            ledger_entry_digest=entry.digest(),
            certificate_digest=resume_result.certificate.digest(),
            reviewed_state_digest=resume_result.assessment.bundle.snapshot.state_digest,
            resumed_state_digest=resume_result.resumed_state.digest(),
            resumed_stage=resume_result.next_stage(),
            authority_note=resume_result.certificate.authority_note,
            rationale=resume_result.certificate.rationale,
        )

    def changed_ledger(self) -> bool:
        """Return whether this coordination changed the resume ledger."""
        return self.before_ledger_digest != self.after_ledger_digest

    def cleared_to_resume(self) -> bool:
        """Return whether this coordination records a cleared resume."""
        return True

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible resume coordination receipt."""
        return {
            "receipt_id": self.receipt_id.value,
            "before_ledger_digest": {
                "algorithm": self.before_ledger_digest.algorithm,
                "value": self.before_ledger_digest.value,
            },
            "after_ledger_digest": {
                "algorithm": self.after_ledger_digest.algorithm,
                "value": self.after_ledger_digest.value,
            },
            "resume_result_digest": {
                "algorithm": self.resume_result_digest.algorithm,
                "value": self.resume_result_digest.value,
            },
            "ledger_entry_digest": {
                "algorithm": self.ledger_entry_digest.algorithm,
                "value": self.ledger_entry_digest.value,
            },
            "certificate_digest": {
                "algorithm": self.certificate_digest.algorithm,
                "value": self.certificate_digest.value,
            },
            "reviewed_state_digest": {
                "algorithm": self.reviewed_state_digest.algorithm,
                "value": self.reviewed_state_digest.value,
            },
            "resumed_state_digest": {
                "algorithm": self.resumed_state_digest.algorithm,
                "value": self.resumed_state_digest.value,
            },
            "resumed_stage": self.resumed_stage.value,
            "authority_note": self.authority_note,
            "rationale": self.rationale,
            "changed_ledger": self.changed_ledger(),
            "cleared_to_resume": self.cleared_to_resume(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this resume coordination receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewResumeCoordinationResult:
    """Result of certifying and ledgering a human-review resume."""

    resume_result: HumanReviewResumeResult
    before_ledger: HumanReviewResumeLedger
    after_ledger: HumanReviewResumeLedger
    ledger_entry: HumanReviewResumeLedgerEntry
    receipt: HumanReviewResumeCoordinationReceipt

    @property
    def state(self) -> NinefoldRunState:
        """Return the run state after the certified human-review resume."""
        return self.resume_result.resumed_state

    def latest_entry(self) -> HumanReviewResumeLedgerEntry:
        """Return the ledger entry produced by this coordination."""
        latest = self.after_ledger.latest()
        if latest is None:
            raise FoundationError("human-review resume ledger has no latest entry")
        return latest

    def next_stage(self) -> RunStage:
        """Return the stage from which orchestration may resume."""
        return self.resume_result.next_stage()

    def cleared_to_resume(self) -> bool:
        """Return whether this result authorizes staged orchestration resume."""
        return self.resume_result.cleared_to_resume()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible resume coordination result."""
        return {
            "state_digest": self.state.digest().value,
            "resume_result_digest": self.resume_result.digest().value,
            "before_ledger_digest": self.before_ledger.digest().value,
            "after_ledger_digest": self.after_ledger.digest().value,
            "ledger_entry_digest": self.ledger_entry.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "latest_entry_digest": self.latest_entry().digest().value,
            "certificate_digest": self.resume_result.certificate.digest().value,
            "next_stage": self.next_stage().value,
            "changed_ledger": self.receipt.changed_ledger(),
            "cleared_to_resume": self.cleared_to_resume(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this resume coordination result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewResumeLedgerCoordinator:
    """Certifies human-review resumes and records certificates in a resume ledger."""

    resume_coordinator: HumanReviewResumeCoordinator

    @classmethod
    def create(cls) -> HumanReviewResumeLedgerCoordinator:
        """Create a standard human-review resume ledger coordinator."""
        return cls(resume_coordinator=HumanReviewResumeCoordinator())

    def certify_and_record(
        self,
        *,
        assessment: HumanReviewClearanceAssessment,
        resumed_state: NinefoldRunState,
        ledger: HumanReviewResumeLedger,
        rationale: str = (
            "Human-review clearance is complete; IX-Sally may resume staged "
            "orchestration from the resumed state."
        ),
    ) -> HumanReviewResumeCoordinationResult:
        """Certify a cleared resume and append it to the provided resume ledger."""
        resume_result = self.resume_coordinator.certify(
            assessment=assessment,
            resumed_state=resumed_state,
            rationale=rationale,
        )
        after_ledger = ledger.append_result(resume_result)
        entry = after_ledger.latest()
        if entry is None:
            raise FoundationError("human-review resume coordination failed to append ledger entry")

        receipt = HumanReviewResumeCoordinationReceipt.from_coordination(
            before_ledger=ledger,
            after_ledger=after_ledger,
            resume_result=resume_result,
            entry=entry,
        )

        return HumanReviewResumeCoordinationResult(
            resume_result=resume_result,
            before_ledger=ledger,
            after_ledger=after_ledger,
            ledger_entry=entry,
            receipt=receipt,
        )
