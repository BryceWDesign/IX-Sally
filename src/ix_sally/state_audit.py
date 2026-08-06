"""Run state audit reports for IX-Sally chamber readiness."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.state import NinefoldRunState


class StateAuditSeverity(StrEnum):
    """Severity assigned to an IX-Sally run state audit finding."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class StateAuditFinding:
    """One deterministic finding from an IX-Sally run state audit."""

    finding_id: CanonicalKey
    severity: StateAuditSeverity
    summary: str
    detail: str
    reference: str

    @classmethod
    def create(
        cls,
        *,
        severity: StateAuditSeverity,
        summary: str,
        detail: str,
        reference: str,
        finding_id: CanonicalKey | None = None,
    ) -> StateAuditFinding:
        """Create a normalized state audit finding."""
        normalized_summary = require_text(summary, field_name="summary")
        normalized_detail = require_text(detail, field_name="detail")
        normalized_reference = require_text(reference, field_name="reference")

        return cls(
            finding_id=finding_id
            or CanonicalKey.from_text(
                f"{severity.value}-{normalized_reference}-{normalized_summary}",
                field_name="finding_id",
            ),
            severity=severity,
            summary=normalized_summary,
            detail=normalized_detail,
            reference=normalized_reference,
        )

    def blocks_chamber_close(self) -> bool:
        """Return whether this finding blocks autonomous chamber close."""
        return self.severity is StateAuditSeverity.BLOCKING

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audit finding representation."""
        return {
            "finding_id": self.finding_id.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "detail": self.detail,
            "reference": self.reference,
            "blocks_chamber_close": self.blocks_chamber_close(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audit finding."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class StateAuditReport:
    """Receipt-grade audit report over an IX-Sally run state."""

    state_digest: DigestRecord
    findings: tuple[StateAuditFinding, ...]

    @classmethod
    def create(
        cls,
        *,
        state_digest: DigestRecord,
        findings: Iterable[StateAuditFinding],
    ) -> StateAuditReport:
        """Create a state audit report and reject duplicate finding identifiers."""
        state_digest.require_algorithm("sha256")
        normalized = tuple(findings)
        seen: set[str] = set()

        for finding in normalized:
            if finding.finding_id.value in seen:
                raise FoundationError(
                    f"duplicate state audit finding id: {finding.finding_id.value}"
                )
            seen.add(finding.finding_id.value)

        return cls(
            state_digest=state_digest,
            findings=normalized,
        )

    def blocking_findings(self) -> tuple[StateAuditFinding, ...]:
        """Return findings that block autonomous chamber close."""
        return tuple(finding for finding in self.findings if finding.blocks_chamber_close())

    def warning_findings(self) -> tuple[StateAuditFinding, ...]:
        """Return warning findings."""
        return tuple(
            finding for finding in self.findings if finding.severity is StateAuditSeverity.WARNING
        )

    def info_findings(self) -> tuple[StateAuditFinding, ...]:
        """Return informational findings."""
        return tuple(
            finding for finding in self.findings if finding.severity is StateAuditSeverity.INFO
        )

    def ready_for_close(self) -> bool:
        """Return whether the chamber can close without blocking findings."""
        return not self.blocking_findings()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audit report representation."""
        finding_payload: JsonArray = []
        for finding in self.findings:
            finding_payload.append(finding.to_payload())

        return {
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "findings": finding_payload,
            "finding_count": len(self.findings),
            "blocking_count": len(self.blocking_findings()),
            "warning_count": len(self.warning_findings()),
            "info_count": len(self.info_findings()),
            "ready_for_close": self.ready_for_close(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this state audit report."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class StateAuditor:
    """Audits IX-Sally run state for unfinished work and review blockers."""

    def audit(self, state: NinefoldRunState) -> StateAuditReport:
        """Return a deterministic readiness report for a run state."""
        findings: list[StateAuditFinding] = []

        findings.extend(self._action_findings(state))
        findings.extend(self._execution_queue_findings(state))
        findings.extend(self._forge_result_findings(state))
        findings.extend(self._evidence_support_findings(state))

        if not findings:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.INFO,
                    summary="Run state has no audit blockers.",
                    detail=(
                        "No proposed actions, queued executions, failed results, "
                        "or unsupported claims remain."
                    ),
                    reference="state",
                )
            )

        return StateAuditReport.create(
            state_digest=state.digest(),
            findings=tuple(findings),
        )

    def _action_findings(self, state: NinefoldRunState) -> tuple[StateAuditFinding, ...]:
        """Return audit findings related to bounded actions."""
        findings: list[StateAuditFinding] = []

        if state.proposed_action_count() > 0:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.BLOCKING,
                    summary="Proposed actions still require authority processing.",
                    detail=f"{state.proposed_action_count()} bounded action(s) remain proposed.",
                    reference="actions.proposed",
                )
            )

        if state.human_review_action_count() > 0:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.BLOCKING,
                    summary="Bounded actions require human review.",
                    detail=(
                        f"{state.human_review_action_count()} bounded action(s) "
                        "require human review."
                    ),
                    reference="actions.human_review",
                )
            )

        if state.blocked_action_count() > 0:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.BLOCKING,
                    summary="Bounded actions block autonomous continuation.",
                    detail=(
                        f"{state.blocked_action_count()} bounded action(s) are denied or blocked."
                    ),
                    reference="actions.blocked",
                )
            )

        return tuple(findings)

    def _execution_queue_findings(self, state: NinefoldRunState) -> tuple[StateAuditFinding, ...]:
        """Return audit findings related to the execution queue."""
        findings: list[StateAuditFinding] = []

        if state.queued_execution_count() > 0:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.WARNING,
                    summary="Execution queue has items waiting for dispatch.",
                    detail=f"{state.queued_execution_count()} execution item(s) remain queued.",
                    reference="execution_queue.queued",
                )
            )

        if state.dispatched_execution_count() > len(state.forge_results.results):
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.WARNING,
                    summary="Dispatched executions may still need Forge results.",
                    detail=(
                        f"{state.dispatched_execution_count()} item(s) dispatched, "
                        f"but only {len(state.forge_results.results)} Forge result(s) recorded."
                    ),
                    reference="execution_queue.dispatched",
                )
            )

        return tuple(findings)

    def _forge_result_findings(self, state: NinefoldRunState) -> tuple[StateAuditFinding, ...]:
        """Return audit findings related to Forge results."""
        findings: list[StateAuditFinding] = []

        if state.failed_forge_result_count() > 0:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.BLOCKING,
                    summary="Forge results include failures.",
                    detail=f"{state.failed_forge_result_count()} Forge result(s) failed.",
                    reference="forge_results.failed",
                )
            )

        if state.blocked_forge_result_count() > 0:
            findings.append(
                StateAuditFinding.create(
                    severity=StateAuditSeverity.BLOCKING,
                    summary="Forge results include boundary blocks.",
                    detail=(
                        f"{state.blocked_forge_result_count()} Forge result(s) "
                        "were boundary-blocked."
                    ),
                    reference="forge_results.blocked",
                )
            )

        return tuple(findings)

    def _evidence_support_findings(self, state: NinefoldRunState) -> tuple[StateAuditFinding, ...]:
        """Return audit findings related to Verity evidence support review."""
        if state.human_review_evidence_finding_count() == 0:
            return ()

        return (
            StateAuditFinding.create(
                severity=StateAuditSeverity.BLOCKING,
                summary="Evidence support findings require human review.",
                detail=(
                    f"{state.human_review_evidence_finding_count()} evidence support "
                    "finding(s) are partial, unsupported, or contradicted."
                ),
                reference="evidence_support.human_review",
            ),
        )
