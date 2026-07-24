"""Status values for IX-Sally human-review reentry runs."""

from enum import StrEnum


class HumanReviewReentryStatus(StrEnum):
    """Outcome status for a human-review reentry run."""

    ADVANCED = "advanced"
    WAITING_FOR_EXTERNAL_INPUT = "waiting_for_external_input"
    CHAMBER_CLOSE_ATTEMPTED = "chamber_close_attempted"
    STEP_LIMIT_REACHED = "step_limit_reached"
