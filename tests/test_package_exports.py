"""Tests for the IX-Sally package-level public export boundary."""

from __future__ import annotations

import subprocess
import sys

import pytest

import ix_sally
from ix_sally.state import NinefoldRunState


def test_package_import_does_not_eagerly_load_runtime_modules() -> None:
    """Importing the package root must not initialize unrelated subsystems."""
    statement = """
import sys
import ix_sally

forbidden = {
    'ix_sally.human_review_control_plane',
    'ix_sally.human_review_control_plane_report',
    'ix_sally.human_review_complete_reentry',
    'ix_sally.state',
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
    )

    assert completed.returncode == 0, completed.stderr


def test_package_export_loads_and_caches_requested_symbol() -> None:
    """A public export must resolve to its source object and remain cached."""
    exported = ix_sally.NinefoldRunState

    assert exported is NinefoldRunState
    assert ix_sally.__dict__["NinefoldRunState"] is NinefoldRunState


def test_every_declared_package_export_resolves() -> None:
    """Every name declared in ``__all__`` must remain publicly available."""
    for name in ix_sally.__all__:
        assert getattr(ix_sally, name) is not None


def test_unknown_package_export_raises_attribute_error() -> None:
    """Unknown names must retain normal module attribute behavior."""
    missing_name = "not_an_ix_sally_export"

    with pytest.raises(AttributeError, match=missing_name):
        getattr(ix_sally, missing_name)
