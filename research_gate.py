"""Measured CUC-10 research gate: learning, retention and evaluation integrity."""

from __future__ import annotations

import sys

from ix_sally.cognition.developmental_learning import ResearchState
from ix_sally.cuc10 import available_worlds, run_developmental_experiment
from ix_sally.digest import JsonArray, JsonObject, stable_json


def main() -> int:
    """Fail on regressions, unverifiable checkpoints or unauthorized promotions."""
    records: JsonArray = []
    failures: list[str] = []
    measured_improvements: list[float] = []
    for seed in (7, 13, 29):
        report, state = run_developmental_experiment(seed)
        restored = ResearchState.from_json(state.to_json())
        checks = (
            len(report.worlds) == len(available_worlds()),
            len(restored.episodes) == len(available_worlds()),
            all(row.training_holdout_disjoint for row in report.worlds),
            all(row.holdout_cases >= 32 for row in report.worlds),
            report.mean_accuracy >= 0.95,
            report.transfer_probe_savings > 0,
            report.regime_recoveries >= 2,
            report.retention_accuracy >= 0.95,
            report.retention_cases == 256,
            report.strategy_holdouts >= 5,
            report.strategy_improvement >= 0.0,
            not report.strategy_auto_promoted,
            not report.agi_demonstrated,
        )
        measured_improvements.append(report.strategy_improvement)
        if not all(checks):
            failing = [index for index, passed in enumerate(checks) if not passed]
            failures.append(f"seed {seed}: failed checks {failing}")
        item: JsonObject = {
            "seed": seed,
            "world_count": len(report.worlds),
            "holdout_accuracy": report.mean_accuracy,
            "transfer_probe_savings": report.transfer_probe_savings,
            "strategy_improvement": report.strategy_improvement,
            "evidence_digest": report.state_digest,
            "all_checks_passed": all(checks),
        }
        records.append(item)
    mean_improvement = sum(measured_improvements) / len(measured_improvements)
    if mean_improvement < 0.05:
        failures.append("average held-out strategy improvement is below 0.05")
    result: JsonObject = {
        "gate": "bounded-developmental-learning",
        "results": records,
        "mean_strategy_improvement": round(mean_improvement, 12),
        "passed": not failures,
        "agi_demonstrated": False,
    }
    sys.stdout.write(f"{stable_json(result)}\n")
    if failures:
        sys.stderr.write("\n".join(failures) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
