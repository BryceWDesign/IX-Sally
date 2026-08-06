"""Status values for IX-Sally human-review control-plane reports."""

from enum import StrEnum


class HumanReviewControlPlaneReportStatus(StrEnum):
    """Operator-facing status for human-review control-plane reporting."""

    NO_HANDOFFS = "no_handoffs"
    HANDOFF_OPEN = "handoff_open"
    DECISION_OPEN = "decision_open"
    RESUME_RECORDED = "resume_recorded"
    REENTRY_RECORDED = "reentry_recorded"
    REENTRY_WAITING_FOR_EXTERNAL_INPUT = "reentry_waiting_for_external_input"
    REENTRY_AUDIT_PASSED = "reentry_audit_passed"
    REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT = "reentry_audit_waiting_for_external_input"
    REENTRY_AUDIT_FAILED = "reentry_audit_failed"
    AUDITED_REENTRY_ACCEPTED = "audited_reentry_accepted"
    AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT = "audited_reentry_waiting_for_external_input"
    AUDITED_REENTRY_FAILED = "audited_reentry_failed"
    COMPLETE_REENTRY_ACCEPTED = "complete_reentry_accepted"
    COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT = "complete_reentry_waiting_for_external_input"
    COMPLETE_REENTRY_FAILED = "complete_reentry_failed"
    COMPLETE_REENTRY_CLOSEOUT_ACCEPTED = "complete_reentry_closeout_accepted"
    COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT = (
        "complete_reentry_closeout_waiting_for_external_input"
    )
    COMPLETE_REENTRY_CLOSEOUT_BLOCKED = "complete_reentry_closeout_blocked"
    REJECTION_BLOCKED = "rejection_blocked"
    DEFERRAL_OPEN = "deferral_open"
