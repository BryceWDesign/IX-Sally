from __future__ import annotations

import json
import subprocess
import sys

from ix_sally.cli import main
from ix_sally.session_baseline import session_one_baseline_digest, session_one_baseline_payload


def test_cli_runtime_baseline_prints_stable_json(capsys: object) -> None:
    result = main(["--runtime-baseline"])
    captured = capsys.readouterr()

    assert result == 0
    payload = json.loads(captured.out)
    assert payload["package"] == "ix-sally"
    assert payload["version"] == "0.1.0"
    assert payload["baseline"] == "session-one"
    assert payload["session_one_complete"] is True
    assert payload["role_count"] == 9
    assert payload["doctrine_rule_count"] == 5
    assert captured.err == ""


def test_cli_baseline_digest_prints_sha256_digest(capsys: object) -> None:
    result = main(["--baseline-digest"])
    captured = capsys.readouterr()
    digest = session_one_baseline_digest()

    assert result == 0
    assert captured.out == f"sha256:{digest.value}\n"
    assert captured.err == ""


def test_module_runtime_baseline_matches_direct_payload() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "ix_sally", "--runtime-baseline"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == session_one_baseline_payload()
    assert completed.stderr == ""


def test_module_baseline_digest_is_sha256() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "ix_sally", "--baseline-digest"],
        check=True,
        capture_output=True,
        text=True,
    )

    prefix, value = completed.stdout.strip().split(":", maxsplit=1)

    assert prefix == "sha256"
    assert value == session_one_baseline_digest().value
    assert len(value) == 64
    assert completed.stderr == ""
