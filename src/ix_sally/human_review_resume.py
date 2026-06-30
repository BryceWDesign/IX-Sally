"""Resume certificates for cleared IX-Sally human-review handoffs."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewResumeCertificate:
    """Certificate proving a cleared human-review handoff may resume orchestration."""

    certificate_id: CanonicalKey
    reviewed_state_digest: DigestRecord
    resumed_state_digest: DigestRecord
    bundle_digest: DigestRecord
    decision_ledger_digest: DigestRecord
    clearance_report_digest: DigestRecord
    resumed_snapshot_digest: DigestRecord
    resumed_stage: RunStage
    authority_note: str
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        reviewed_state_digest: DigestRecord,
        resumed_state_digest: DigestRecord,
        bundle_digest: DigestRecord,
        decision_ledger_digest: DigestRecord,
        clearance_report_digest: DigestRecord,
        resumed_snapshot_digest: DigestRecord,
        resumed_stage: RunStage,
        authority_note: str,
        rationale: str,
        certificate_id: CanonicalKey | None = None,
    ) -> HumanReviewResumeCertificate:
        """Create a normalized human-review resume certificate."""
        reviewed_state_digest.require_algorithm("sha256")
        resumed_state_digest.require_algorithm("sha256")
        bundle_digest.require_algorithm("sha256")
        decision_ledger_digest.require_algorithm("sha256")
        clearance_report_digest.require_algorithm("sha256")
        resumed_snapshot_digest.require_algorithm("sha256")

        if resumed_stage is RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review resume certificate cannot resume to human_review")

        normalized_authority_note = require_text(
            authority_note,
            field_name="authority_note",
        )
        normalized_rationale = require_text(rationale, field_name="rationale")

        return cls(
            certificate_id=certificate_id
            or CanonicalKey.from_text(
                f"human-review-resume-{reviewed_state_digest.value[:16]}-"
                f"{resumed_state_digest.value[:16]}-{clearance_report_digest.value[:16]}",
                field_name="certificate_id",
            ),
            reviewed_state_digest=reviewed_state_digest,
            resumed_state_digest=resumed_state_digest,
            bundle_digest=bundle_digest,
            decision_ledger_digest=decision_ledger_digest,
            clearance_report_digest=clearance_report_digest,
            resumed_snapshot_digest=resumed_snapshot_digest,
            resumed_stage=resumed_stage,
            authority_note=normalized_authority_note,
            rationale=normalized_rationale,
        )

    @classmethod
    def from_assessment(
        cls,
        *,
        assessment: HumanReviewClearanceAssessment,
        resumed_state: NinefoldRunState,
        rationale: str = (
            "Human-review clearance is complete; IX-Sally may resume staged "
            "orchestration from the resumed state."
        ),
    ) -> HumanReviewResumeCertificate:
        """Create a resume certificate from a cleared assessment and resumed state."""
        if not assessment.cleared_to_resume():
            raise FoundationError("human-review clearance is not cleared to resume")

        reviewed_state_digest = assessment.bundle.snapshot.state_digest
        resumed_snapshot = RunStageSnapshot.from_state(resumed_state)

        if resumed_snapshot.state_digest == reviewed_state_digest:
            raise FoundationError("human-review resume requires a post-decision run state")
        if resumed_snapshot.stage is RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review resume state is still in human_review")

        return cls.create(
            reviewed_state_digest=reviewed_state_digest,
            resumed_state_digest=resumed_state.digest(),
            bundle_digest=assessment.bundle.digest(),
            decision_ledger_digest=assessment.decision_ledger.digest(),
            clearance_report_digest=assessment.clearance_report.digest(),
            resumed_snapshot_digest=resumed_snapshot.digest(),
            resumed_stage=resumed_snapshot.stage,
            authority_note=assessment.bundle.packet.authority_note,
            rationale=rationale,
        )

    def cleared_to_resume(self) -> bool:
        """Return whether this certificate authorizes orchestration resume."""
        return True

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible resume certificate."""
        return {
            "certificate_id": self.certificate_id.value,
            "reviewed_state_digest": {
                "algorithm": self.reviewed_state_digest.algorithm,
                "value": self.reviewed_state_digest.value,
            },
            "resumed_state_digest": {
                "algorithm": self.resumed_state_digest.algorithm,
                "value": self.resumed_state_digest.value,
            },
            "bundle_digest": {
                "algorithm": self.bundle_digest.algorithm,
                "value": self.bundle_digest.value,
            },
            "decision_ledger_digest": {
                "algorithm": self.decision_ledger_digest.algorithm,
                "value": self.decision_ledger_digest.value,
            },
            "clearance_report_digest": {
                "algorithm": self.clearance_report_digest.algorithm,
                "value": self.clearance_report_digest.value,
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
        """Return a deterministic digest for this resume certificate."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewResumeResult:
    """Result of certifying a cleared human-review handoff for resumption."""

    assessment: HumanReviewClearanceAssessment
    resumed_state: NinefoldRunState
    resumed_snapshot: RunStageSnapshot
    certificate: HumanReviewResumeCertificate

    @classmethod
    def create(
        cls,
        *,
        assessment: HumanReviewClearanceAssessment,
        resumed_state: NinefoldRunState,
        certificate: HumanReviewResumeCertificate,
    ) -> HumanReviewResumeResult:
        """Create a normalized resume result from validated parts."""
        resumed_snapshot = RunStageSnapshot.from_state(resumed_state)

        if not assessment.cleared_to_resume():
            raise FoundationError("human-review resume result requires cleared assessment")
        if certificate.reviewed_state_digest != assessment.bundle.snapshot.state_digest:
            raise FoundationError("human-review resume certificate reviewed state mismatch")
        if certificate.resumed_state_digest != resumed_state.digest():
            raise FoundationError("human-review resume certificate resumed state mismatch")
        if certificate.bundle_digest != assessment.bundle.digest():
            raise FoundationError("human-review resume certificate bundle mismatch")
        if certificate.decision_ledger_digest != assessment.decision_ledger.digest():
            raise FoundationError("human-review resume certificate decision ledger mismatch")
        if certificate.clearance_report_digest != assessment.clearance_report.digest():
            raise FoundationError("human-review resume certificate clearance report mismatch")
        if certificate.resumed_snapshot_digest != resumed_snapshot.digest():
            raise FoundationError("human-review resume certificate snapshot mismatch")
        if certificate.resumed_stage is not resumed_snapshot.stage:
            raise FoundationError("human-review resume certificate stage mismatch")

        return cls(
            assessment=assessment,
            resumed_state=resumed_state,
            resumed_snapshot=resumed_snapshot,
            certificate=certificate,
        )

    def next_stage(self) -> RunStage:
        """Return the stage from which orchestration may resume."""
        return self.resumed_snapshot.stage

    def cleared_to_resume(self) -> bool:
        """Return whether this result authorizes staged orchestration resume."""
        return self.certificate.cleared_to_resume()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible resume result."""
        return {
            "assessment_digest": self.assessment.digest().value,
            "resumed_state_digest": self.resumed_state.digest().value,
            "resumed_snapshot_digest": self.resumed_snapshot.digest().value,
            "certificate_digest": self.certificate.digest().value,
            "next_stage": self.next_stage().value,
            "cleared_to_resume": self.cleared_to_resume(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this resume result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewResumeCoordinator:
    """Issues resume certificates only after human-review clearance is complete."""

    def certify(
        self,
        *,
        assessment: HumanReviewClearanceAssessment,
        resumed_state: NinefoldRunState,
        rationale: str = (
            "Human-review clearance is complete; IX-Sally may resume staged "
            "orchestration from the resumed state."
        ),
    ) -> HumanReviewResumeResult:
        """Certify that the supplied post-decision state may resume orchestration."""
        certificate = HumanReviewResumeCertificate.from_assessment(
            assessment=assessment,
            resumed_state=resumed_state,
            rationale=rationale,
        )

        return HumanReviewResumeResult.create(
            assessment=assessment,
            resumed_state=resumed_state,
            certificate=certificate,
        )
