"""Audit-gated chamber closing for IX-Sally run states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import require_text
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState
from ix_sally.state_audit import StateAuditor, StateAuditReport


class ChamberCloseStatus(StrEnum):
    """Outcome status for an audit-gated chamber close attempt."""

    CLOSED = "closed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ChamberCloseResult:
    """Result of attempting to close an IX-Sally chamber under audit."""

    state: NinefoldRunState
    audit_report: StateAuditReport
    status: ChamberCloseStatus
    summary: str

    def closed(self) -> bool:
        """Return whether the chamber was closed."""
        return self.status is ChamberCloseStatus.CLOSED

    def blocked(self) -> bool:
        """Return whether the chamber close was blocked."""
        return self.status is ChamberCloseStatus.BLOCKED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible chamber close result."""
        return {
            "state_digest": self.state.digest().value,
            "audit_report_digest": self.audit_report.digest().value,
            "status": self.status.value,
            "summary": self.summary,
            "closed": self.closed(),
            "blocked": self.blocked(),
            "blocking_count": len(self.audit_report.blocking_findings()),
            "warning_count": len(self.audit_report.warning_findings()),
            "ready_for_close": self.audit_report.ready_for_close(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this chamber close result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ChamberCloser:
    """Closes IX-Sally chambers only when the run-state audit permits it."""

    recorder: StateRecorder
    auditor: StateAuditor

    def close_if_ready(
        self,
        *,
        state: NinefoldRunState,
        summary: str,
    ) -> ChamberCloseResult:
        """Close the chamber if the audit report has no blocking findings."""
        normalized_summary = require_text(summary, field_name="summary")
        report = self.auditor.audit(state)

        if not report.ready_for_close():
            return ChamberCloseResult(
                state=state,
                audit_report=report,
                status=ChamberCloseStatus.BLOCKED,
                summary="Chamber close blocked by state audit.",
            )

        closed_state = self.recorder.close_chamber(state, summary=normalized_summary)

        return ChamberCloseResult(
            state=closed_state,
            audit_report=report,
            status=ChamberCloseStatus.CLOSED,
            summary=normalized_summary,
        )
