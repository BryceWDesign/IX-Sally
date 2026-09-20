"""End-to-end scientific-integrity tests for CUC-1."""

from __future__ import annotations

from ix_sally.cuc1 import run_cuc1_experiment


def test_default_experiment_acquires_competence() -> None:
    report = run_cuc1_experiment()
    assert report.acquired_competence
    assert report.classification == "causal-skill-acquisition-observed"


def test_report_never_certifies_agi() -> None:
    assert not run_cuc1_experiment().to_payload()["agi_certified"]


def test_counterfactual_uses_same_held_out_observation() -> None:
    report = run_cuc1_experiment()
    assert (
        report.counterfactual_proof.observation_digest
        == report.held_out_trial.observation.evidence_digest
    )
    assert report.counterfactual_proof.behavior_changed


def test_transfer_uses_skill_and_succeeds() -> None:
    report = run_cuc1_experiment()
    assert report.transfer_succeeded
    assert report.held_out_trial.choice.used_skill_id is not None


def test_every_training_outcome_changes_agent_state() -> None:
    report = run_cuc1_experiment()
    assert all(trial.changed_agent for trial in report.training_trials)


def test_experiment_is_deterministic() -> None:
    first = run_cuc1_experiment()
    second = run_cuc1_experiment()
    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()


def test_evaluator_commitment_matches_reveal() -> None:
    report = run_cuc1_experiment()
    assert (
        report.environment_commitment.value == report.evaluator_reveal["rule_commitment"]["value"]
    )


def test_report_contains_frozen_baselines() -> None:
    report = run_cuc1_experiment()
    assert {baseline.baseline_id for baseline in report.baselines} == {
        "uniform-random",
        "fixed-north",
    }
