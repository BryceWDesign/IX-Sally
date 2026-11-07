# IX-Sally 0.9.3 Release Validation

## Verified locally (Python 3.13)

- Pytest: all 1,091 collected tests completed successfully (exit code 0).
- Installed wheel smoke: built, installed into a clean environment and verified
  package identity, command-line execution and the CUC-10 experiment.
- Research gate: passed for seeds 7, 13 and 29; its mean strategy improvement
  over the fresh passive-query baseline was 0.055 under the documented metric.
- Repository-integrity validation: zero violations.
- Internal dependency graph: zero cycles.
- Architecture-boundary validation: zero violations.
- Python bytecode compilation: passed.
- CUC-10 state persistence, input separation, replay, corrupt-checkpoint refusal,
  source-independent perception and holdout-only comparison: tested.

## Not independently verified here

- Ruff formatting and lint checks, and strict Mypy checks: their executables
  were unavailable in this network-restricted environment. The GitHub Actions
  workflow retains these gates and must run them on all configured Python
  versions before the remote revision can be called fully green.
- GitHub-hosted Actions execution: not performed. The release has not been
  pushed or verified on the remote repository.
- Independent external evaluation or human-level/AGI performance: not performed.

## Research claims

`agi_demonstrated=false`; classification is
`bounded-developmental-learning-experiment`.

The numeric worlds are transparent and deterministic with supplied expression
operators. Their results verify the narrow experimental behavior; they are not
proof of open-world intelligence, broad autonomous discovery or recursively
improving general competence. The governed action boundaries remain in place.

Reproduce locally after installing development dependencies:

```bash
python check_green.py
python -m ix_sally --cuc10-experiment
python -m research_gate
```

The machine-readable experiment outputs, checkpoint format, measured baselines,
and scientific limitations are documented in
`docs/V093_DEVELOPMENTAL_RESEARCH.md`.
