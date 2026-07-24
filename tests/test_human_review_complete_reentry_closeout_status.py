"""Regression tests for the complete reentry closeout status boundary."""

from __future__ import annotations

import subprocess
import sys

from ix_sally.human_review_complete_reentry_closeout_status import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutStatus as LegacyStatus,
)
from tests.subprocess_support import repository_subprocess_environment


def test_closeout_status_remains_available_from_legacy_module() -> None:
    """Existing imports must resolve to the dependency-neutral status type."""
    assert LegacyStatus is CompleteHumanReviewReentryCloseoutStatus


def test_closeout_status_import_does_not_load_closeout_runtime() -> None:
    """Status-only consumers must not initialize the closeout execution graph."""
    statement = """
import sys
from ix_sally.human_review_complete_reentry_closeout_status import (
    CompleteHumanReviewReentryCloseoutStatus,
)

assert CompleteHumanReviewReentryCloseoutStatus.ACCEPTED.value == 'accepted'
forbidden = {
    'ix_sally.human_review_complete_reentry_report',
    'ix_sally.human_review_complete_reentry',
    'ix_sally.human_review_control_plane',
    'ix_sally.human_review_workflow',
}
loaded = sorted(forbidden.intersection(sys.modules))
if loaded:
    raise SystemExit(f'eagerly loaded modules: {loaded}')
"""
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        check=False,
        capture_output=True,
        text=True,
        env=repository_subprocess_environment(),
    )

    assert completed.returncode == 0, completed.stderr
