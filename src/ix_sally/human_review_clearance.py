"""Clearance reports for IX-Sally human-review resumption decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_bundle import HumanReviewOperatorBundle
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_resolution import HumanReviewResolutionAudit


class HumanReviewClearanceStatus(StrEnum):
    """Clearance status for an IX-Sally human-review bundle."""

    CLEARED_TO_RESUME = "cleared_to_resume"
    PENDING_GATEWAY_DECISION = "pending_gateway_decision"
    DEFERRED_DECISION_OPEN = "deferred_decision_open"
    REJECTED_DECISION_BLOCKED = "rejected_decision_blocked"
    MANUAL_INVESTIGATION_OPEN = "manual_investigation_open"
    BLOCKER_ACKNOWLEDGMENT_OPEN = "blocker_acknowledgment_open"


@dataclass(frozen=True, slots=True)
class HumanReviewClearanceReport:
    """Report explaining whether a human-review handoff is cleared to resume."""

    report_id: CanonicalKey
    bundle_digest: DigestRecord
    decision_ledger_digest: DigestRecord
    resolution_audit_digest: DigestRecord
    state_digest: DigestRecord
    status: HumanReviewClearanceStatus
    rationale: str
    card_count: int
    resolved_count: int
    pending_decision_count: int
    approved_decision_count: int
    rejected_decision_count: int
    deferred_decision_count: int
    manual_investigation_count: int
    blocker_acknowledgment_count: int

    @classmethod
    def create(
        cls,
        *,
        bundle_digest: DigestRecord,
        decision_ledger_digest: DigestRecord,
        resolution_audit_digest: DigestRecord,
        state_digest: DigestRecord,
        status: HumanReviewClearanceStatus,
        rationale: str,
        card_count: int,
        resolved_count: int,
        pending_decision_count: int,
        approved_decision_count: int,
        rejected_decision_count: int,
        deferred_decision_count: int,
        manual_investigation_count: int,
        blocker_acknowledgment_count: int,
        report_id: CanonicalKey | None = None,
    ) -> HumanReviewClearanceReport:
        """Create a normalized human-review clearance report."""
        if card_count <= 0:
            raise FoundationError("human-review clearance card_count must be positive")
        for field_name, value in {
            "resolved_count": resolved_count,
            "pending_decision_count": pending_decision_count,
            "approved_decision_count": approved_decision_count,
            "rejected_decision_count": rejected_decision_count,
            "deferred_decision_count": deferred_decision_count,
            "manual_investigation_count": manual_investigation_count,
            "blocker_acknowledgment_count": blocker_acknowledgment_count,
        }.items():
            if value < 0:
                raise FoundationError(f"human-review clearance {field_name} must not be negative")

        surfaced_count = (
            pending_decision_count
            + resolved_count
            + manual_investigation_count
            + blocker_acknowledgment_count
        )
        if surfaced_count != card_count:
            raise FoundationError("human-review clearance surfaced counts must equal card_count")

        decision_status_count = (
            approved_decision_count + rejected_decision_count + deferred_decision_count
        )
        if decision_status_count != resolved_count:
            raise FoundationError(
                "human-review clearance decision-status counts must equal resolved_count"
            )

        bundle_digest.require_algorithm("sha256")
        decision_ledger_digest.require_algorithm("sha256")
        resolution_audit_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        normalized_rationale = require_text(rationale, field_name="rationale")

        return cls(
            report_id=report_id
            or CanonicalKey.from_text(
                f"human-review-clearance-{bundle_digest.value[:16]}-"
                f"{decision_ledger_digest.value[:16]}-{status.value}",
                field_name="report_id",
            ),
            bundle_digest=bundle_digest,
            decision_ledger_digest=decision_ledger_digest,
            resolution_audit_digest=resolution_audit_digest,
            state_digest=state_digest,
            status=status,
            rationale=normalized_rationale,
            card_count=card_count,
            resolved_count=resolved_count,
            pending_decision_count=pending_decision_count,
            approved_decision_count=approved_decision_count,
            rejected_decision_count=rejected_decision_count,
            deferred_decision_count=deferred_decision_count,
            manual_investigation_count=manual_investigation_count,
            blocker_acknowledgment_count=blocker_acknowledgment_count,
        )

    @classmethod
    def from_audit(
        cls,
        *,
        audit: HumanReviewResolutionAudit,
    ) -> HumanReviewClearanceReport:
        """Create a clearance report from a human-review resolution audit."""
        approved_count = 0
        rejected_count = 0
        deferred_count = 0

        for resolution in audit.resolutions:
            if resolution.decision_status == HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION.value:
                approved_count += 1
            elif resolution.decision_status == HumanReviewDecisionStatus.REJECTED.value:
                rejected_count += 1
            elif resolution.decision_status == HumanReviewDecisionStatus.DEFERRED.value:
                deferred_count += 1

        status, rationale = _select_clearance_status(
            pending_decision_count=audit.pending_decision_count(),
            deferred_decision_count=deferred_count,
            rejected_decision_count=rejected_count,
            manual_investigation_count=audit.manual_investigation_count(),
            blocker_acknowledgment_count=audit.blocker_acknowledgment_count(),
        )

        return cls.create(
            bundle_digest=audit.bundle_digest,
            decision_ledger_digest=audit.decision_ledger_digest,
            resolution_audit_digest=audit.digest(),
            state_digest=audit.state_digest,
            status=status,
            rationale=rationale,
            card_count=len(audit.resolutions),
            resolved_count=audit.resolved_count(),
            pending_decision_count=audit.pending_decision_count(),
            approved_decision_count=approved_count,
            rejected_decision_count=rejected_count,
            deferred_decision_count=deferred_count,
            manual_investigation_count=audit.manual_investigation_count(),
            blocker_acknowledgment_count=audit.blocker_acknowledgment_count(),
        )

    def cleared_to_resume(self) -> bool:
        """Return whether the human-review packet is cleared for orchestration resume."""
        return self.status is HumanReviewClearanceStatus.CLEARED_TO_RESUME

    def requires_operator_attention(self) -> bool:
        """Return whether operator attention is still required."""
        return not self.cleared_to_resume()

    def has_blocking_decision(self) -> bool:
        """Return whether a human decision blocks or defers resumption."""
        return self.rejected_decision_count > 0 or self.deferred_decision_count > 0

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible clearance report."""
        return {
            "report_id": self.report_id.value,
            "bundle_digest": {
                "algorithm": self.bundle_digest.algorithm,
                "value": self.bundle_digest.value,
            },
            "decision_ledger_digest": {
                "algorithm": self.decision_ledger_digest.algorithm,
                "value": self.decision_ledger_digest.value,
            },
            "resolution_audit_digest": {
                "algorithm": self.resolution_audit_digest.algorithm,
                "value": self.resolution_audit_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "status": self.status.value,
            "rationale": self.rationale,
            "card_count": self.card_count,
            "resolved_count": self.resolved_count,
            "pending_decision_count": self.pending_decision_count,
            "approved_decision_count": self.approved_decision_count,
            "rejected_decision_count": self.rejected_decision_count,
            "deferred_decision_count": self.deferred_decision_count,
            "manual_investigation_count": self.manual_investigation_count,
            "blocker_acknowledgment_count": self.blocker_acknowledgment_count,
            "cleared_to_resume": self.cleared_to_resume(),
            "requires_operator_attention": self.requires_operator_attention(),
            "has_blocking_decision": self.has_blocking_decision(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this clearance report."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewClearanceAssessment:
    """Complete assessment tying a bundle, decision ledger, audit, and clearance report."""

    bundle: HumanReviewOperatorBundle
    decision_ledger: HumanReviewDecisionLedger
    resolution_audit: HumanReviewResolutionAudit
    clearance_report: HumanReviewClearanceReport

    @classmethod
    def create(
        cls,
        *,
        bundle: HumanReviewOperatorBundle,
        decision_ledger: HumanReviewDecisionLedger,
        resolution_audit: HumanReviewResolutionAudit,
        clearance_report: HumanReviewClearanceReport,
    ) -> HumanReviewClearanceAssessment:
        """Create a normalized clearance assessment from validated parts."""
        if resolution_audit.bundle_digest != bundle.digest():
            raise FoundationError("human-review clearance audit does not match bundle")
        if resolution_audit.decision_ledger_digest != decision_ledger.digest():
            raise FoundationError("human-review clearance audit does not match decision ledger")
        if clearance_report.bundle_digest != bundle.digest():
            raise FoundationError("human-review clearance report does not match bundle")
        if clearance_report.decision_ledger_digest != decision_ledger.digest():
            raise FoundationError("human-review clearance report does not match decision ledger")
        if clearance_report.resolution_audit_digest != resolution_audit.digest():
            raise FoundationError("human-review clearance report does not match resolution audit")

        return cls(
            bundle=bundle,
            decision_ledger=decision_ledger,
            resolution_audit=resolution_audit,
            clearance_report=clearance_report,
        )

    @classmethod
    def from_bundle(
        cls,
        *,
        bundle: HumanReviewOperatorBundle,
        decision_ledger: HumanReviewDecisionLedger,
    ) -> HumanReviewClearanceAssessment:
        """Create a clearance assessment from a bundle and decision ledger."""
        audit = HumanReviewResolutionAudit.from_bundle(
            bundle=bundle,
            decision_ledger=decision_ledger,
        )
        report = HumanReviewClearanceReport.from_audit(audit=audit)

        return cls.create(
            bundle=bundle,
            decision_ledger=decision_ledger,
            resolution_audit=audit,
            clearance_report=report,
        )

    def cleared_to_resume(self) -> bool:
        """Return whether orchestration may resume for the assessed bundle."""
        return self.clearance_report.cleared_to_resume()

    def requires_operator_attention(self) -> bool:
        """Return whether operator attention is still required."""
        return self.clearance_report.requires_operator_attention()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible clearance assessment."""
        return {
            "bundle_digest": self.bundle.digest().value,
            "decision_ledger_digest": self.decision_ledger.digest().value,
            "resolution_audit_digest": self.resolution_audit.digest().value,
            "clearance_report_digest": self.clearance_report.digest().value,
            "status": self.clearance_report.status.value,
            "cleared_to_resume": self.cleared_to_resume(),
            "requires_operator_attention": self.requires_operator_attention(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this clearance assessment."""
        return DigestRecord.from_payload(self.to_payload())


def _select_clearance_status(
    *,
    pending_decision_count: int,
    deferred_decision_count: int,
    rejected_decision_count: int,
    manual_investigation_count: int,
    blocker_acknowledgment_count: int,
) -> tuple[HumanReviewClearanceStatus, str]:
    """Select a deterministic clearance status from unresolved review counts."""
    if pending_decision_count > 0:
        return (
            HumanReviewClearanceStatus.PENDING_GATEWAY_DECISION,
            "At least one gateway-resolvable card still lacks a human decision.",
        )

    if deferred_decision_count > 0:
        return (
            HumanReviewClearanceStatus.DEFERRED_DECISION_OPEN,
            "At least one human decision deferred the target and kept review open.",
        )

    if rejected_decision_count > 0:
        return (
            HumanReviewClearanceStatus.REJECTED_DECISION_BLOCKED,
            "At least one human decision rejected the target and blocks resumption.",
        )

    if manual_investigation_count > 0:
        return (
            HumanReviewClearanceStatus.MANUAL_INVESTIGATION_OPEN,
            "At least one card requires manual investigation outside the gateway.",
        )

    if blocker_acknowledgment_count > 0:
        return (
            HumanReviewClearanceStatus.BLOCKER_ACKNOWLEDGMENT_OPEN,
            "At least one card documents a blocker that has not been resolved.",
        )

    return (
        HumanReviewClearanceStatus.CLEARED_TO_RESUME,
        "All gateway-resolvable cards are approved and no manual blockers remain.",
    )
