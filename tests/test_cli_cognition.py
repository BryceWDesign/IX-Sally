"""Command-line coverage for the integrated IX-Sally cognitive runtime."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ix_sally.cli import main


def test_cli_cognitive_evaluation_reports_observed_results(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI evaluation must expose actual results and preserve the AGI boundary."""
    result = main(["--cognitive-evaluation"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert result == 0
    assert payload["benchmark_count"] == 15
    assert payload["passed_count"] == 15
    assert payload["agi_certified"] is False
    assert payload["classification"] == "experimental-cognitive-architecture"
    assert captured.err == ""


def test_cli_executes_ix_file_and_returns_typed_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One UTF-8 IX program must compile and execute through the bounded VM."""
    source_path = tmp_path / "answer.ix"
    source_path.write_text(
        "let answer = 6 * 7\nprint answer\nassert answer == 42\n",
        encoding="utf-8",
    )

    result = main(["--execute-ix", str(source_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert result == 0
    assert payload["status"] == "halted"
    assert payload["outputs"] == [{"type": "integer", "value": 42}]
    assert payload["failure"] is None
    assert captured.err == ""


def test_cli_returns_failure_for_failed_ix_assertion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed IX assertion must produce a nonzero CLI result and a receipt."""
    source_path = tmp_path / "failure.ix"
    source_path.write_text("assert false\n", encoding="utf-8")

    result = main(["--execute-ix", str(source_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert result == 1
    assert payload["status"] == "failed"
    assert payload["failure"] is not None
    assert captured.err == ""


def test_cli_empty_snapshot_is_complete_and_named_ix_sally(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The clean snapshot must contain the complete integrated repository state."""
    result = main(["--empty-cognitive-snapshot"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert result == 0
    assert payload["repository"] == "IX-Sally"
    assert payload["schema_version"] == 1
    assert payload["state"]["repository"] == "IX-Sally"
    assert payload["state"]["goals"] == {"goals": []}
    assert payload["state"]["episodes"] == {"episodes": []}
    assert captured.err == ""
