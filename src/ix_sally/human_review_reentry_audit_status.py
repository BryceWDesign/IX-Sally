"""Status values for IX-Sally human-review reentry audits."""

from enum import StrEnum


class HumanReviewReentryAuditStatus(StrEnum):
    """Overall status for a human-review reentry audit report."""

    PASSED = "passed"
    WAITING_FOR_EXTERNAL_INPUT = "waiting_for_external_input"
    FAILED = "failed"
