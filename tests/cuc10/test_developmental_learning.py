"""Measured learning, counterexamples, checkpoint invariants and CLI exercises."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ix_sally.cognition.developmental_learning import (
    InductiveLearner,
    LearningEpisode,
    NumericExample,
    ResearchState,
)
from ix_sally.cognition.representation_programs import FeatureProgram, ProgramOperator
from ix_sally.cuc10 import available_worlds, run_developmental_experiment, run_world
from ix_sally.digest import stable_digest, stable_json
from ix_sally.foundation import FoundationError


def test_complete_curriculum_is_inductively_learned_and_scored_on_disjoint_holdouts() -> None:
    report, state = run_developmental_experiment(7)
    assert len(report.worlds) == len(available_worlds()) == 8
    assert len(state.episodes) == 8
    assert all(item.training_holdout_disjoint for item in report.worlds)
    assert all(item.holdout_cases == 32 for item in report.worlds)
    assert all(item.holdout_accuracy == 1.0 for item in report.worlds)
    assert all(item.baseline_holdout_accuracy == 1.0 for item in report.worlds)
    assert report.agi_demonstrated is False
    assert report.classification == "bounded-developmental-learning-experiment"
    assert report.retained_concepts == 8
    assert report.retention_accuracy == 1.0
    assert report.retention_cases == 256
    assert all(
        item.previous_digest == "0" * 64
        if index == 0
        else item.previous_digest == state.episodes[index - 1].digest
        for index, item in enumerate(state.episodes)
    )


def test_transfer_uses_fewer_probes_and_shift_requires_recovery() -> None:
    report, state = run_developmental_experiment(7)
    transfers = [row for row in report.worlds if row.selection == "transferred"]
    assert len(transfers) == 4
    assert report.transfer_probe_savings == sum(
        row.baseline_probes - row.probes for row in transfers
    )
    assert report.transfer_probe_savings > 0
    assert report.regime_recoveries >= 3
    assert state.concepts[-1].program.expression() == "abs((x0-x1))"


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 13])
def test_several_unseen_sampling_seeds_reach_extrapolation_accuracy(seed: int) -> None:
    report, _ = run_developmental_experiment(seed)
    assert report.mean_accuracy == 1.0
    assert report.mean_baseline_accuracy == 1.0
    assert report.retained_concepts == 8
    assert report.retention_accuracy == 1.0
    assert report.retention_cases == 256
    assert all(item.holdout_accuracy == 1.0 for item in report.worlds)


def test_repeatability_and_ablation_measurements() -> None:
    first, state = run_developmental_experiment(7)
    second, again = run_developmental_experiment(7)
    assert first.to_payload() == second.to_payload()
    assert state.to_json() == again.to_json()
    assert sum(item.passive_probes for item in first.worlds) > sum(
        item.baseline_probes for item in first.worlds
    )


def test_state_survives_canonical_restore_and_continues() -> None:
    state = ResearchState()
    state, outcome = run_world(state, available_worlds()[0])
    assert outcome.selection == "induced"
    restored = ResearchState.from_json(state.to_json())
    assert restored == state
    restored, next_outcome = run_world(restored, available_worlds()[1])
    assert next_outcome.selection == "transferred"
    assert next_outcome.holdout_accuracy == 1.0
    assert len(restored.episodes) == 2
    assert restored.episodes[1].previous_digest == restored.episodes[0].digest


def test_modified_checkpoint_digest_is_rejected() -> None:
    state, _ = run_world(ResearchState(), available_worlds()[0])
    raw = json.loads(state.to_json())
    raw["episodes"][0]["heldout_accuracy"] = 0.1
    with pytest.raises(FoundationError, match="digest"):
        ResearchState.from_json(stable_json(raw))


def test_rehashed_but_broken_evidence_chain_is_rejected() -> None:
    _, state = run_developmental_experiment(7)
    raw = json.loads(state.to_json())
    raw["episodes"][1]["previous_digest"] = "f" * 64
    raw["content_digest"] = stable_digest(
        {key: value for key, value in raw.items() if key != "content_digest"}
    )
    with pytest.raises(FoundationError, match="chain"):
        ResearchState.from_json(stable_json(raw))


def test_rehashed_unsupported_expression_is_rejected() -> None:
    state, _ = run_world(ResearchState(), available_worlds()[0])
    raw = json.loads(state.to_json())
    raw["episodes"][0]["program"]["operator"] = "python-eval"
    raw["content_digest"] = stable_digest(
        {key: value for key, value in raw.items() if key != "content_digest"}
    )
    with pytest.raises(FoundationError, match="expression"):
        ResearchState.from_json(stable_json(raw))


def test_rehashed_training_contradiction_is_rejected() -> None:
    state, _ = run_world(ResearchState(), available_worlds()[0])
    raw = json.loads(state.to_json())
    raw["episodes"][0]["examples"][0]["consequence"] += 1000
    raw["content_digest"] = stable_digest(
        {key: value for key, value in raw.items() if key != "content_digest"}
    )
    with pytest.raises(FoundationError, match="contradicts"):
        ResearchState.from_json(stable_json(raw))


def test_invalid_world_and_repeat_world_fail_closed() -> None:
    with pytest.raises(FoundationError, match="unknown"):
        run_world(ResearchState(), "unlisted-domain")
    state, _ = run_world(ResearchState(), available_worlds()[0])
    with pytest.raises(FoundationError, match="already"):
        run_world(state, available_worlds()[0])


def test_learning_abstains_on_unrepresentable_observation() -> None:
    learner = InductiveLearner()
    candidates = ((-2, 1), (1, 3), (2, -1), (3, -3))
    with pytest.raises(FoundationError, match="no hypothesis"):
        learner.infer(pool=candidates, observe=lambda _: 1_000_000, budget=4)


def test_learning_rejects_repeated_probe_inputs() -> None:
    learner = InductiveLearner()
    with pytest.raises(FoundationError, match="probe pool"):
        learner.infer(pool=((1, 2), (1, 2)), observe=lambda _: 3, budget=2)


def test_episode_rejects_fabricated_training_evidence() -> None:
    program = FeatureProgram(ProgramOperator.CHANNEL, channel_index=0)
    with pytest.raises(FoundationError, match="contradicts"):
        LearningEpisode(
            world_id="test",
            examples=(NumericExample((1, 2), 8),),
            program=program,
            selection="induced",
            candidates_remaining=1,
            heldout_accuracy=1.0,
            heldout_cases=5,
            previous_digest="0" * 64,
        )


def _invoke(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    return subprocess.run(
        [sys.executable, "-m", "ix_sally", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_cli_runs_benchmark_and_reports_measured_limits() -> None:
    process = _invoke("--cuc10-experiment", "--cuc10-seed", "7")
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["agi_demonstrated"] is False
    assert result["mean_accuracy"] == 1.0
    assert result["retained_concepts"] == 8


def test_cli_advances_persistent_learning_across_separate_processes(tmp_path: Path) -> None:
    checkpoint = tmp_path / "research-state.json"
    first = _invoke(
        "--cuc10-world",
        available_worlds()[0],
        "--cuc10-state",
        str(checkpoint),
    )
    assert first.returncode == 0, first.stderr
    second = _invoke(
        "--cuc10-world",
        available_worlds()[1],
        "--cuc10-state",
        str(checkpoint),
    )
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["selection"] == "transferred"
    assert len(ResearchState.from_json(checkpoint.read_text(encoding="utf-8")).episodes) == 2
    again = _invoke(
        "--cuc10-world",
        available_worlds()[1],
        "--cuc10-state",
        str(checkpoint),
    )
    assert again.returncode != 0
    assert len(ResearchState.from_json(checkpoint.read_text(encoding="utf-8")).episodes) == 2


def test_cli_refuses_corrupt_state_without_overwriting(tmp_path: Path) -> None:
    checkpoint = tmp_path / "research-state.json"
    checkpoint.write_text('{"schema":1,"episodes":[],"concepts":[]}', encoding="utf-8")
    original = checkpoint.read_text(encoding="utf-8")
    process = _invoke("--cuc10-world", available_worlds()[0], "--cuc10-state", str(checkpoint))
    assert process.returncode != 0
    assert checkpoint.read_text(encoding="utf-8") == original


def test_cli_declines_existing_checkpoint_lock(tmp_path: Path) -> None:
    checkpoint = tmp_path / "research-state.json"
    lock = tmp_path / "research-state.json.lock"
    lock.write_text("another writer", encoding="utf-8")
    process = _invoke(
        "--cuc10-world",
        available_worlds()[0],
        "--cuc10-state",
        str(checkpoint),
    )
    assert process.returncode != 0
    assert lock.read_text(encoding="utf-8") == "another writer"
    assert not checkpoint.exists()


def test_cli_initial_benchmark_checkpoint_is_create_only(tmp_path: Path) -> None:
    path = tmp_path / "experiment.json"
    first = _invoke("--cuc10-experiment", "--cuc10-state", str(path))
    assert first.returncode == 0, first.stderr
    original = path.read_text(encoding="utf-8")
    assert len(ResearchState.from_json(original).episodes) == len(available_worlds())
    again = _invoke("--cuc10-experiment", "--cuc10-state", str(path))
    assert again.returncode != 0
    assert path.read_text(encoding="utf-8") == original


def test_strategy_proposal_is_fully_measured_but_never_self_authorized() -> None:
    report, _ = run_developmental_experiment(7)
    assert report.strategy_holdouts == 8
    assert report.strategy_improvement > 0.05
    assert report.strategy_review_eligible
    assert not report.strategy_auto_promoted
