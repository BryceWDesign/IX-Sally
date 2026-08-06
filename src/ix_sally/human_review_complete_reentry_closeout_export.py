"""Export packets for complete IX-Sally human-review reentry closeout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_complete_reentry_closeout_coordination_ledger import (
    CompleteHumanReviewReentryCloseoutCoordinationLedger,
)
from ix_sally.human_review_complete_reentry_report_ledger import (
    CompleteHumanReviewReentryCloseoutLedger,
)

if TYPE_CHECKING:
    from ix_sally.human_review_complete_reentry_closeout_coordination import (
        CompleteHumanReviewReentryCloseoutCoordinationResult,
    )


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutExportArtifact:
    """One exported artifact reference for complete reentry closeout evidence."""

    artifact_id: CanonicalKey
    label: str
    digest: DigestRecord
    required: bool = True

    @classmethod
    def create(
        cls,
        *,
        label: str,
        digest: DigestRecord,
        required: bool = True,
        artifact_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutExportArtifact:
        """Create a normalized complete reentry closeout export artifact."""
        normalized_label = require_text(label, field_name="label")
        digest.require_algorithm("sha256")

        return cls(
            artifact_id=artifact_id
            or CanonicalKey.from_text(
                f"complete-reentry-closeout-export-artifact-"
                f"{normalized_label[:48]}-{digest.value[:16]}",
                field_name="artifact_id",
            ),
            label=normalized_label,
            digest=digest,
            required=required,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible artifact reference."""
        return {
            "artifact_id": self.artifact_id.value,
            "label": self.label,
            "digest": {
                "algorithm": self.digest.algorithm,
                "value": self.digest.value,
            },
            "required": self.required,
        }

    def record_digest(self) -> DigestRecord:
        """Return a deterministic digest for this export artifact reference."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutExportPacket:
    """Portable export packet for complete human-review reentry closeout."""

    packet_id: CanonicalKey
    coordination_result_digest: DigestRecord
    coordination_receipt_digest: DigestRecord
    closeout_report_digest: DigestRecord
    closeout_workflow_operation_digest: DigestRecord
    final_state_digest: DigestRecord
    final_control_plane_digest: DigestRecord
    closeout_ledger_digest: DigestRecord
    coordination_ledger_digest: DigestRecord
    accepted: bool
    waiting_for_external_input: bool
    blocked: bool
    requires_operator_attention: bool
    artifacts: tuple[CompleteHumanReviewReentryCloseoutExportArtifact, ...]

    @classmethod
    def create(
        cls,
        *,
        coordination_result_digest: DigestRecord,
        coordination_receipt_digest: DigestRecord,
        closeout_report_digest: DigestRecord,
        closeout_workflow_operation_digest: DigestRecord,
        final_state_digest: DigestRecord,
        final_control_plane_digest: DigestRecord,
        closeout_ledger_digest: DigestRecord,
        coordination_ledger_digest: DigestRecord,
        accepted: bool,
        waiting_for_external_input: bool,
        blocked: bool,
        requires_operator_attention: bool,
        artifacts: tuple[CompleteHumanReviewReentryCloseoutExportArtifact, ...],
        packet_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutExportPacket:
        """Create a normalized complete reentry closeout export packet."""
        if accepted and blocked:
            raise FoundationError(
                "complete reentry closeout export cannot be both accepted and blocked"
            )
        if waiting_for_external_input and blocked:
            raise FoundationError(
                "complete reentry closeout export cannot be both waiting and blocked"
            )
        if blocked and not requires_operator_attention:
            raise FoundationError(
                "blocked complete reentry closeout export must require operator attention"
            )

        required_artifacts = tuple(artifact for artifact in artifacts if artifact.required)
        if len(required_artifacts) < 6:
            raise FoundationError(
                "complete reentry closeout export requires at least six required "
                "artifact references"
            )

        for digest in (
            coordination_result_digest,
            coordination_receipt_digest,
            closeout_report_digest,
            closeout_workflow_operation_digest,
            final_state_digest,
            final_control_plane_digest,
            closeout_ledger_digest,
            coordination_ledger_digest,
        ):
            digest.require_algorithm("sha256")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"complete-reentry-closeout-export-"
                f"{coordination_result_digest.value[:16]}-"
                f"{final_control_plane_digest.value[:16]}",
                field_name="packet_id",
            ),
            coordination_result_digest=coordination_result_digest,
            coordination_receipt_digest=coordination_receipt_digest,
            closeout_report_digest=closeout_report_digest,
            closeout_workflow_operation_digest=closeout_workflow_operation_digest,
            final_state_digest=final_state_digest,
            final_control_plane_digest=final_control_plane_digest,
            closeout_ledger_digest=closeout_ledger_digest,
            coordination_ledger_digest=coordination_ledger_digest,
            accepted=accepted,
            waiting_for_external_input=waiting_for_external_input,
            blocked=blocked,
            requires_operator_attention=requires_operator_attention,
            artifacts=artifacts,
        )

    @classmethod
    def from_result(
        cls,
        result: CompleteHumanReviewReentryCloseoutCoordinationResult,
    ) -> CompleteHumanReviewReentryCloseoutExportPacket:
        """Create a complete reentry closeout export packet from a coordination result."""
        closeout_ledger = CompleteHumanReviewReentryCloseoutLedger.create(()).append_report(
            result.closeout_report
        )
        coordination_ledger = CompleteHumanReviewReentryCloseoutCoordinationLedger.create(
            ()
        ).append_result(result)

        artifacts = (
            CompleteHumanReviewReentryCloseoutExportArtifact.create(
                label="complete reentry coordination result",
                digest=result.digest(),
            ),
            CompleteHumanReviewReentryCloseoutExportArtifact.create(
                label="complete reentry coordination receipt",
                digest=result.receipt.digest(),
            ),
            CompleteHumanReviewReentryCloseoutExportArtifact.create(
                label="complete reentry closeout report",
                digest=result.closeout_report.digest(),
            ),
            CompleteHumanReviewReentryCloseoutExportArtifact.create(
                label="complete reentry closeout workflow operation",
                digest=result.closeout_workflow_operation.digest(),
            ),
            CompleteHumanReviewReentryCloseoutExportArtifact.create(
                label="complete reentry closeout ledger",
                digest=closeout_ledger.digest(),
            ),
            CompleteHumanReviewReentryCloseoutExportArtifact.create(
                label="complete reentry closeout coordination ledger",
                digest=coordination_ledger.digest(),
            ),
        )

        return cls.create(
            coordination_result_digest=result.digest(),
            coordination_receipt_digest=result.receipt.digest(),
            closeout_report_digest=result.closeout_report.digest(),
            closeout_workflow_operation_digest=(result.closeout_workflow_operation.digest()),
            final_state_digest=result.state.digest(),
            final_control_plane_digest=result.control_plane.digest(),
            closeout_ledger_digest=closeout_ledger.digest(),
            coordination_ledger_digest=coordination_ledger.digest(),
            accepted=result.accepted(),
            waiting_for_external_input=result.waiting_for_external_input(),
            blocked=result.blocked(),
            requires_operator_attention=result.requires_operator_attention(),
            artifacts=artifacts,
        )

    def required_artifacts(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutExportArtifact, ...]:
        """Return required artifact references."""
        return tuple(artifact for artifact in self.artifacts if artifact.required)

    def missing_required_artifact_labels(self) -> tuple[str, ...]:
        """Return labels for required artifacts whose digest is empty."""
        return tuple(
            artifact.label for artifact in self.required_artifacts() if not artifact.digest.value
        )

    def complete(self) -> bool:
        """Return whether the export packet has all required artifact digests."""
        return len(self.missing_required_artifact_labels()) == 0

    def exportable_without_operator(self) -> bool:
        """Return whether the packet can be exported without operator attention."""
        return self.complete() and not self.requires_operator_attention

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible export packet."""
        artifact_payload: JsonArray = []
        for artifact in self.artifacts:
            artifact_payload.append(artifact.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "coordination_result_digest": {
                "algorithm": self.coordination_result_digest.algorithm,
                "value": self.coordination_result_digest.value,
            },
            "coordination_receipt_digest": {
                "algorithm": self.coordination_receipt_digest.algorithm,
                "value": self.coordination_receipt_digest.value,
            },
            "closeout_report_digest": {
                "algorithm": self.closeout_report_digest.algorithm,
                "value": self.closeout_report_digest.value,
            },
            "closeout_workflow_operation_digest": {
                "algorithm": self.closeout_workflow_operation_digest.algorithm,
                "value": self.closeout_workflow_operation_digest.value,
            },
            "final_state_digest": {
                "algorithm": self.final_state_digest.algorithm,
                "value": self.final_state_digest.value,
            },
            "final_control_plane_digest": {
                "algorithm": self.final_control_plane_digest.algorithm,
                "value": self.final_control_plane_digest.value,
            },
            "closeout_ledger_digest": {
                "algorithm": self.closeout_ledger_digest.algorithm,
                "value": self.closeout_ledger_digest.value,
            },
            "coordination_ledger_digest": {
                "algorithm": self.coordination_ledger_digest.algorithm,
                "value": self.coordination_ledger_digest.value,
            },
            "accepted": self.accepted,
            "waiting_for_external_input": self.waiting_for_external_input,
            "blocked": self.blocked,
            "requires_operator_attention": self.requires_operator_attention,
            "artifact_count": len(self.artifacts),
            "required_artifact_count": len(self.required_artifacts()),
            "missing_required_artifact_labels": list(self.missing_required_artifact_labels()),
            "complete": self.complete(),
            "exportable_without_operator": self.exportable_without_operator(),
            "artifacts": artifact_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry closeout export."""
        return DigestRecord.from_payload(self.to_payload())
