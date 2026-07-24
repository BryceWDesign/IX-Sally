"""Coordinated operations for IX-Sally human-review control-plane state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_decision_coordinator import (
    HumanReviewDecisionCoordinationResult,
    HumanReviewDecisionCoordinator,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_handoff import (
    HumanReviewHandoffCoordinator,
    HumanReviewHandoffResult,
)
from ix_sally.human_review_resume_coordination import (
    HumanReviewResumeCoordinationResult,
    HumanReviewResumeLedgerCoordinator,
)
from ix_sally.state import NinefoldRunState

if TYPE_CHECKING:
    from ix_sally.human_review_audited_reentry import AuditedHumanReviewReentryResult
    from ix_sally.human_review_complete_reentry import CompleteHumanReviewReentryResult
    from ix_sally.human_review_complete_reentry_report import (
        CompleteHumanReviewReentryCloseoutReport,
    )
    from ix_sally.human_review_reentry import HumanReviewReentryResult
    from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditReport


class HumanReviewControlPlaneOperationKind(StrEnum):
    """Supported human-review control-plane operation kinds."""

    HANDOFF_RECORDED = "handoff_recorded"
    DECISION_RECORDED = "decision_recorded"
    RESUME_RECORDED = "resume_recorded"
    REENTRY_RECORDED = "reentry_recorded"
    REENTRY_AUDIT_RECORDED = "reentry_audit_recorded"
    AUDITED_REENTRY_RECORDED = "audited_reentry_recorded"
    COMPLETE_REENTRY_RECORDED = "complete_reentry_recorded"
    COMPLETE_REENTRY_CLOSEOUT_RECORDED = "complete_reentry_closeout_recorded"


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneOperationReceipt:
    """Compact receipt for one human-review control-plane operation."""

    receipt_id: CanonicalKey
    operation_kind: HumanReviewControlPlaneOperationKind
    before_control_plane_digest: DigestRecord
    after_control_plane_digest: DigestRecord
    operation_digest: DigestRecord
    handoff_count: int
    decision_count: int
    resume_count: int
    reentry_count: int
    reentry_audit_count: int
    audited_reentry_count: int
    complete_reentry_count: int
    complete_reentry_closeout_count: int

    @classmethod
    def create(
        cls,
        *,
        operation_kind: HumanReviewControlPlaneOperationKind,
        before_control_plane_digest: DigestRecord,
        after_control_plane_digest: DigestRecord,
        operation_digest: DigestRecord,
        handoff_count: int,
        decision_count: int,
        resume_count: int,
        reentry_count: int = 0,
        reentry_audit_count: int = 0,
        audited_reentry_count: int = 0,
        complete_reentry_count: int = 0,
        complete_reentry_closeout_count: int = 0,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewControlPlaneOperationReceipt:
        """Create a normalized human-review control-plane operation receipt."""
        if handoff_count < 0:
            raise FoundationError(
                "human-review control-plane handoff_count must not be negative"
            )
        if decision_count < 0:
            raise FoundationError(
                "human-review control-plane decision_count must not be negative"
            )
        if resume_count < 0:
            raise FoundationError(
                "human-review control-plane resume_count must not be negative"
            )
        if reentry_count < 0:
            raise FoundationError(
                "human-review control-plane reentry_count must not be negative"
            )
        if reentry_audit_count < 0:
            raise FoundationError(
                "human-review control-plane reentry_audit_count must not be negative"
            )
        if audited_reentry_count < 0:
            raise FoundationError(
                "human-review control-plane audited_reentry_count must not be negative"
            )
        if complete_reentry_count < 0:
            raise FoundationError(
                "human-review control-plane complete_reentry_count must not be negative"
            )
        if complete_reentry_closeout_count < 0:
            raise FoundationError(
                "human-review control-plane complete_reentry_closeout_count "
                "must not be negative"
            )

        before_control_plane_digest.require_algorithm("sha256")
        after_control_plane_digest.require_algorithm("sha256")
        operation_digest.require_algorithm("sha256")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-control-plane-{operation_kind.value}-"
                f"{before_control_plane_digest.value[:16]}-"
                f"{after_control_plane_digest.value[:16]}",
                field_name="receipt_id",
            ),
            operation_kind=operation_kind,
            before_control_plane_digest=before_control_plane_digest,
            after_control_plane_digest=after_control_plane_digest,
            operation_digest=operation_digest,
            handoff_count=handoff_count,
            decision_count=decision_count,
            resume_count=resume_count,
            reentry_count=reentry_count,
            reentry_audit_count=reentry_audit_count,
            audited_reentry_count=audited_reentry_count,
            complete_reentry_count=complete_reentry_count,
            complete_reentry_closeout_count=complete_reentry_closeout_count,
        )

    def changed_control_plane(self) -> bool:
        """Return whether the operation changed control-plane state."""
        return self.before_control_plane_digest != self.after_control_plane_digest

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible operation receipt."""
        return {
            "receipt_id": self.receipt_id.value,
            "operation_kind": self.operation_kind.value,
            "before_control_plane_digest": {
                "algorithm": self.before_control_plane_digest.algorithm,
                "value": self.before_control_plane_digest.value,
            },
            "after_control_plane_digest": {
                "algorithm": self.after_control_plane_digest.algorithm,
                "value": self.after_control_plane_digest.value,
            },
            "operation_digest": {
                "algorithm": self.operation_digest.algorithm,
                "value": self.operation_digest.value,
            },
            "handoff_count": self.handoff_count,
            "decision_count": self.decision_count,
            "resume_count": self.resume_count,
            "reentry_count": self.reentry_count,
            "reentry_audit_count": self.reentry_audit_count,
            "audited_reentry_count": self.audited_reentry_count,
            "complete_reentry_count": self.complete_reentry_count,
            "complete_reentry_closeout_count": self.complete_reentry_closeout_count,
            "changed_control_plane": self.changed_control_plane(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this operation receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneOperationResult:
    """Result of applying one operation to human-review control-plane state."""

    before_control_plane: HumanReviewControlPlaneState
    after_control_plane: HumanReviewControlPlaneState
    receipt: HumanReviewControlPlaneOperationReceipt
    handoff_result: HumanReviewHandoffResult | None = None
    decision_result: HumanReviewDecisionCoordinationResult | None = None
    resume_result: HumanReviewResumeCoordinationResult | None = None
    reentry_result: HumanReviewReentryResult | None = None
    reentry_audit_report: HumanReviewReentryAuditReport | None = None
    audited_reentry_result: AuditedHumanReviewReentryResult | None = None
    complete_reentry_result: CompleteHumanReviewReentryResult | None = None
    complete_reentry_closeout_report: (
        CompleteHumanReviewReentryCloseoutReport | None
    ) = None

    def changed_control_plane(self) -> bool:
        """Return whether this operation changed control-plane state."""
        return self.receipt.changed_control_plane()

    def operation_kind(self) -> HumanReviewControlPlaneOperationKind:
        """Return the operation kind recorded by this result."""
        return self.receipt.operation_kind

    def require_handoff_result(self) -> HumanReviewHandoffResult:
        """Return the handoff result or raise if this was another operation kind."""
        if self.handoff_result is None:
            raise FoundationError("human-review control-plane result has no handoff result")
        return self.handoff_result

    def require_decision_result(self) -> HumanReviewDecisionCoordinationResult:
        """Return the decision result or raise if this was another operation kind."""
        if self.decision_result is None:
            raise FoundationError("human-review control-plane result has no decision result")
        return self.decision_result

    def require_resume_result(self) -> HumanReviewResumeCoordinationResult:
        """Return the resume result or raise if this was another operation kind."""
        if self.resume_result is None:
            raise FoundationError("human-review control-plane result has no resume result")
        return self.resume_result

    def require_reentry_result(self) -> HumanReviewReentryResult:
        """Return the reentry result or raise if this was another operation kind."""
        if self.reentry_result is None:
            raise FoundationError("human-review control-plane result has no reentry result")
        return self.reentry_result

    def require_reentry_audit_report(self) -> HumanReviewReentryAuditReport:
        """Return the reentry audit report or raise if this was another operation kind."""
        if self.reentry_audit_report is None:
            raise FoundationError(
                "human-review control-plane result has no reentry audit report"
            )
        return self.reentry_audit_report

    def require_audited_reentry_result(self) -> AuditedHumanReviewReentryResult:
        """Return the audited reentry result or raise if this was another operation kind."""
        if self.audited_reentry_result is None:
            raise FoundationError(
                "human-review control-plane result has no audited reentry result"
            )
        return self.audited_reentry_result

    def require_complete_reentry_result(self) -> CompleteHumanReviewReentryResult:
        """Return the complete reentry result or raise if this was another operation kind."""
        if self.complete_reentry_result is None:
            raise FoundationError(
                "human-review control-plane result has no complete reentry result"
            )
        return self.complete_reentry_result

    def require_complete_reentry_closeout_report(
        self,
    ) -> CompleteHumanReviewReentryCloseoutReport:
        """Return the complete reentry closeout report or raise."""
        if self.complete_reentry_closeout_report is None:
            raise FoundationError(
                "human-review control-plane result has no complete reentry "
                "closeout report"
            )
        return self.complete_reentry_closeout_report

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible control-plane operation result."""
        return {
            "before_control_plane_digest": self.before_control_plane.digest().value,
            "after_control_plane_digest": self.after_control_plane.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "operation_kind": self.operation_kind().value,
            "handoff_count": self.after_control_plane.handoff_count(),
            "decision_count": self.after_control_plane.decision_count(),
            "resume_count": self.after_control_plane.resume_count(),
            "reentry_count": self.after_control_plane.reentry_count(),
            "reentry_audit_count": self.after_control_plane.reentry_audit_count(),
            "audited_reentry_count": self.after_control_plane.audited_reentry_count(),
            "complete_reentry_count": self.after_control_plane.complete_reentry_count(),
            "complete_reentry_closeout_count": (
                self.after_control_plane.complete_reentry_closeout_count()
            ),
            "changed_control_plane": self.changed_control_plane(),
            "handoff_result_digest": (
                self.handoff_result.digest().value
                if self.handoff_result is not None
                else None
            ),
            "decision_result_digest": (
                self.decision_result.digest().value
                if self.decision_result is not None
                else None
            ),
            "resume_result_digest": (
                self.resume_result.digest().value
                if self.resume_result is not None
                else None
            ),
            "reentry_result_digest": (
                self.reentry_result.digest().value
                if self.reentry_result is not None
                else None
            ),
            "reentry_audit_report_digest": (
                self.reentry_audit_report.digest().value
                if self.reentry_audit_report is not None
                else None
            ),
            "audited_reentry_result_digest": (
                self.audited_reentry_result.digest().value
                if self.audited_reentry_result is not None
                else None
            ),
            "complete_reentry_result_digest": (
                self.complete_reentry_result.digest().value
                if self.complete_reentry_result is not None
                else None
            ),
            "complete_reentry_closeout_report_digest": (
                self.complete_reentry_closeout_report.digest().value
                if self.complete_reentry_closeout_report is not None
                else None
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this operation result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneCoordinator:
    """Applies human-review operations to control-plane state."""

    handoff_coordinator: HumanReviewHandoffCoordinator
    decision_coordinator: HumanReviewDecisionCoordinator
    resume_coordinator: HumanReviewResumeLedgerCoordinator

    @classmethod
    def create(cls) -> HumanReviewControlPlaneCoordinator:
        """Create a standard human-review control-plane coordinator."""
        return cls(
            handoff_coordinator=HumanReviewHandoffCoordinator.create(),
            decision_coordinator=HumanReviewDecisionCoordinator.create(),
            resume_coordinator=HumanReviewResumeLedgerCoordinator.create(),
        )

    def record_handoff(
        self,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        authority_note: str = (
            "Human authority is required before IX-Sally may treat these "
            "targets as resolved."
        ),
    ) -> HumanReviewControlPlaneOperationResult:
        """Assemble a human-review handoff and update the control-plane handoff ledger."""
        before_digest = control_plane.digest()
        handoff_result = self.handoff_coordinator.handoff(
            state=run_state,
            ledger=control_plane.handoff_ledger,
            authority_note=authority_note,
        )
        updated_control_plane = control_plane.with_handoff_ledger(
            handoff_result.after_ledger,
        )
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.HANDOFF_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=handoff_result.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            handoff_result=handoff_result,
        )

    def record_action_decision(
        self,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        action_id: str,
        reviewer: str,
        status: HumanReviewDecisionStatus,
        rationale: str,
    ) -> HumanReviewControlPlaneOperationResult:
        """Apply a human-review action decision and update the decision ledger."""
        before_digest = control_plane.digest()
        decision_result = self.decision_coordinator.decide_action(
            state=run_state,
            ledger=control_plane.decision_ledger,
            action_id=action_id,
            reviewer=reviewer,
            status=status,
            rationale=rationale,
        )
        updated_control_plane = control_plane.with_decision_ledger(
            decision_result.after_ledger,
        )
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.DECISION_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=decision_result.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            decision_result=decision_result,
        )

    def record_resume(
        self,
        *,
        assessment: HumanReviewClearanceAssessment,
        resumed_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        rationale: str = (
            "Human-review clearance is complete; IX-Sally may resume staged "
            "orchestration from the resumed state."
        ),
    ) -> HumanReviewControlPlaneOperationResult:
        """Certify a human-review resume and update the resume ledger."""
        before_digest = control_plane.digest()
        resume_result = self.resume_coordinator.certify_and_record(
            assessment=assessment,
            resumed_state=resumed_state,
            ledger=control_plane.resume_ledger,
            rationale=rationale,
        )
        updated_control_plane = control_plane.with_resume_ledger(
            resume_result.after_ledger,
        )
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.RESUME_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=resume_result.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            resume_result=resume_result,
        )

    def record_reentry(
        self,
        *,
        reentry_result: HumanReviewReentryResult,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneOperationResult:
        """Record a certified human-review reentry result in the reentry ledger."""
        if reentry_result.control_plane.digest() != control_plane.digest():
            raise FoundationError(
                "human-review control-plane reentry result must match current "
                "control-plane state"
            )

        before_digest = control_plane.digest()
        updated_ledger = control_plane.reentry_ledger.append_result(reentry_result)
        updated_control_plane = control_plane.with_reentry_ledger(updated_ledger)
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.REENTRY_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=reentry_result.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            reentry_result=reentry_result,
        )

    def record_reentry_audit(
        self,
        *,
        audit_report: HumanReviewReentryAuditReport,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneOperationResult:
        """Record a human-review reentry audit report in the audit ledger."""
        if audit_report.control_plane_digest != control_plane.digest():
            raise FoundationError(
                "human-review control-plane reentry audit must match current "
                "control-plane state"
            )

        before_digest = control_plane.digest()
        updated_ledger = control_plane.reentry_audit_ledger.append_report(audit_report)
        updated_control_plane = control_plane.with_reentry_audit_ledger(updated_ledger)
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.REENTRY_AUDIT_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=audit_report.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            reentry_audit_report=audit_report,
        )

    def record_audited_reentry(
        self,
        *,
        audited_reentry_result: AuditedHumanReviewReentryResult,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneOperationResult:
        """Record a fully audited human-review reentry result in the control plane."""
        if audited_reentry_result.control_plane.digest() != control_plane.digest():
            raise FoundationError(
                "human-review control-plane audited reentry must match current "
                "control-plane state"
            )

        before_digest = control_plane.digest()
        updated_ledger = control_plane.audited_reentry_ledger.append_result(
            audited_reentry_result
        )
        updated_control_plane = control_plane.with_audited_reentry_ledger(updated_ledger)
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.AUDITED_REENTRY_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=audited_reentry_result.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            audited_reentry_result=audited_reentry_result,
        )

    def record_complete_reentry(
        self,
        *,
        complete_reentry_result: CompleteHumanReviewReentryResult,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneOperationResult:
        """Record a complete human-review reentry result in the control plane."""
        if complete_reentry_result.control_plane.digest() != control_plane.digest():
            raise FoundationError(
                "human-review control-plane complete reentry must match current "
                "control-plane state"
            )

        before_digest = control_plane.digest()
        updated_ledger = control_plane.complete_reentry_ledger.append_result(
            complete_reentry_result
        )
        updated_control_plane = control_plane.with_complete_reentry_ledger(
            updated_ledger
        )
        receipt = self._receipt(
            operation_kind=HumanReviewControlPlaneOperationKind.COMPLETE_REENTRY_RECORDED,
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=complete_reentry_result.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            complete_reentry_result=complete_reentry_result,
        )

    def record_complete_reentry_closeout(
        self,
        *,
        closeout_report: CompleteHumanReviewReentryCloseoutReport,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneOperationResult:
        """Record a complete human-review reentry closeout report."""
        closeout_control_plane = control_plane

        if closeout_report.control_plane_digest != closeout_control_plane.digest():
            ledger_entry = closeout_report.complete_reentry_ledger_entry
            if ledger_entry is None:
                raise FoundationError(
                    "human-review control-plane complete reentry closeout must match "
                    "current control-plane state"
                )

            expected_sequence = (
                closeout_control_plane.complete_reentry_ledger.next_sequence()
            )
            if ledger_entry.sequence != expected_sequence:
                raise FoundationError(
                    "human-review control-plane complete reentry closeout must match "
                    "current control-plane state"
                )

            complete_reentry_ledger = (
                closeout_control_plane.complete_reentry_ledger.append(ledger_entry)
            )
            closeout_control_plane = (
                closeout_control_plane.with_complete_reentry_ledger(
                    complete_reentry_ledger
                )
            )

        if closeout_report.control_plane_digest != closeout_control_plane.digest():
            raise FoundationError(
                "human-review control-plane complete reentry closeout must match "
                "current control-plane state"
            )

        before_digest = closeout_control_plane.digest()
        updated_ledger = (
            closeout_control_plane.complete_reentry_closeout_ledger.append_report(
                closeout_report
            )
        )
        updated_control_plane = (
            closeout_control_plane.with_complete_reentry_closeout_ledger(updated_ledger)
        )
        receipt = self._receipt(
            operation_kind=(
                HumanReviewControlPlaneOperationKind.COMPLETE_REENTRY_CLOSEOUT_RECORDED
            ),
            before_digest=before_digest,
            after_control_plane=updated_control_plane,
            operation_digest=closeout_report.digest(),
        )

        return HumanReviewControlPlaneOperationResult(
            before_control_plane=closeout_control_plane,
            after_control_plane=updated_control_plane,
            receipt=receipt,
            complete_reentry_closeout_report=closeout_report,
        )

    def _receipt(
        self,
        *,
        operation_kind: HumanReviewControlPlaneOperationKind,
        before_digest: DigestRecord,
        after_control_plane: HumanReviewControlPlaneState,
        operation_digest: DigestRecord,
    ) -> HumanReviewControlPlaneOperationReceipt:
        """Create an operation receipt from the updated control-plane state."""
        return HumanReviewControlPlaneOperationReceipt.create(
            operation_kind=operation_kind,
            before_control_plane_digest=before_digest,
            after_control_plane_digest=after_control_plane.digest(),
            operation_digest=operation_digest,
            handoff_count=after_control_plane.handoff_count(),
            decision_count=after_control_plane.decision_count(),
            resume_count=after_control_plane.resume_count(),
            reentry_count=after_control_plane.reentry_count(),
            reentry_audit_count=after_control_plane.reentry_audit_count(),
            audited_reentry_count=after_control_plane.audited_reentry_count(),
            complete_reentry_count=after_control_plane.complete_reentry_count(),
            complete_reentry_closeout_count=(
                after_control_plane.complete_reentry_closeout_count()
            ),
        )
