"""Regression tests for the human-review reentry audit status boundary."""

from __future__ import annotations

import subprocess
import sys

from ix_sally.human_review_reentry_audit import (
    HumanReviewReentryAuditStatus as LegacyStatus,
)
from ix_sally.human_review_reentry_audit_status import HumanReviewReentryAuditStatus
from tests.subprocess_support import repository_subprocess_environment


def test_reentry_audit_status_remains_available_from_legacy_module() -> None:
    """Existing imports must resolve to the dependency-neutral status type."""
    assert LegacyStatus is HumanReviewReentryAuditStatus


def test_reentry_audit_status_import_does_not_load_audit_runtime() -> None:
    """Status-only consumers must not initialize the reentry audit graph."""
    statement = """
import sys
from ix_sally.human_review_reentry_audit_status import HumanReviewReentryAuditStatus

assert HumanReviewReentryAuditStatus.PASSED.value == 'passed'
forbidden = {
    'ix_sally.human_review_reentry_audit',
    'ix_sally.human_review_reentry_coordination',
    'ix_sally.human_review_workflow',
    'ix_sally.human_review_control_plane',
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
