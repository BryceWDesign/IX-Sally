"""Status values for complete IX-Sally human-review reentry closeout."""

from enum import StrEnum


class CompleteHumanReviewReentryCloseoutStatus(StrEnum):
    """Closeout status for a complete human-review reentry result."""

    ACCEPTED = "accepted"
    WAITING_FOR_EXTERNAL_INPUT = "waiting_for_external_input"
    BLOCKED = "blocked"
