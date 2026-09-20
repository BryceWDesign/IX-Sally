# IX-Sally v0.8.0 Validation Report

This report records the final locally verified state of IX-Sally v0.8.0 after the Reality-Coupled Cognition upgrade and release cleanup.

## Release identity

- Package: `ix-sally`
- Version: `0.8.0`
- Python requirement: `>=3.11`
- Runtime dependencies: none
- Governing doctrine: **AI proposes. Humans decide. Evidence governs what may proceed.**

## v0.8.0 additions

The release adds:

- reality/prediction separation with immutable deltas;
- independent perception quorum with disagreement retention;
- multidimensional epistemic pressure;
- choice over cognitive operation;
- first-class assumption aging, diagnosis, contradiction, and revalidation;
- counterfactual goal generation from blocked conditions and failures;
- explicit cognitive recovery;
- disagreement-preserving perspective ensembles;
- epistemic authority envelopes that shrink proposal scope under uncertainty;
- autobiographical epistemic traces with causal lineage;
- shadow cognitive-strategy evaluation with human-review-only promotion;
- CUC-7 reality-coupled perceptual agency;
- CUC-8 autonomous epistemic recovery;
- CUC-9 cognitive strategy evolution.

## Final local release verification

The complete repository quality gate was executed successfully on the final v0.8.0 working tree:

```
python check_green.py
```

Observed final results:

```
Ruff format:
354 files already formatted

Ruff lint:
All checks passed

MyPy strict:
Success: no issues found in 332 source files

Cross-platform repository integrity:
333 source/test files
0 violations

Runtime dependency graph:
178 modules
895 imports
0 cycles

Runtime architecture boundaries:
178 modules
895 imports
0 boundary violations

Pytest:
1053 passed

Installed wheel smoke test:
passed

Overall:
All selected quality gates passed
```

## MyPy environment isolation

IX-Sally retains Python 3.11 as its declared compatibility floor:

```
python_version = "3.11"
strict = true
no_site_packages = true
mypy_path = "src"
```

`no_site_packages = true` prevents unrelated packages installed in the user's ambient Python environment from contaminating IX-Sally's strict type-checking gate.

This became necessary because an unrelated globally installed NumPy package exposed Python 3.12+ typing syntax while MyPy was intentionally validating IX-Sally against its Python 3.11 compatibility target.

The final isolated strict type check completed successfully:

```
Success: no issues found in 332 source files
```

## Repository integrity

The final repository integrity check reported:

```
IX-Sally repository integrity passed:
333 source/test files
0 violations
```

Generated Python bytecode and development caches are excluded from version control through `.gitignore`.

Ignored generated artifacts include:

```
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.venv/
venv/
.env
```

## Runtime dependency graph

The dependency checker reported:

```
IX-Sally runtime dependency graph passed:
178 modules
895 imports
0 cycles
```

This verifies that the runtime module graph remains acyclic under the repository's dependency rules.

## Runtime architecture boundaries

The architecture checker reported:

```
IX-Sally runtime architecture passed:
178 modules
895 imports
0 boundary violations
```

This confirms that the v0.8.0 additions did not violate the repository's declared architectural boundaries.

## Test suite

The complete pytest suite executed successfully:

```
1053 passed
```

The suite includes existing IX-Sally behavior plus the v0.8.0 Reality-Coupled Cognition additions and CUC-7 through CUC-9 coverage.

## Installed wheel smoke test

The installed-package smoke test completed successfully:

```
Installed IX-Sally wheel smoke test passed.
```

This verifies that IX-Sally operates correctly as an installed package rather than only from the repository source tree.

## CUC-7 through CUC-9 observations

The v0.8.0 experimental suites exercise the new reality-coupled cognition mechanisms.

Observed bounded experiment behavior includes:

```
CUC-7:
baseline=act
shifted=recover
contradiction=true
generated_goal=epistemic:contradiction:predict-source
dependent_assumption=contradicted

CUC-8:
commitment-hold
-> retract
-> reassess
-> revalidate
-> normal

CUC-9:
candidate improvement=0.25 across 3 holdouts
eligible_for_human_review=true
auto_promoted=false
```

### CUC-7

CUC-7 exercises reality-coupled perceptual agency.

The experiment demonstrates that a previously acceptable operating state can encounter contradictory evidence and cause subsequent cognition to change.

The bounded experiment verifies mechanisms for:

- prediction/reality comparison;
- contradiction detection;
- assumption invalidation;
- epistemic pressure generation;
- cognitive-operation selection;
- recovery behavior;
- endogenous information-seeking goal generation.

### CUC-8

CUC-8 exercises autonomous epistemic recovery.

The observed recovery path is:

```
commitment-hold
-> retract
-> reassess
-> revalidate
-> normal
```

This verifies that the architecture can suspend continued commitment after contradiction, revisit implicated assumptions, perform revalidation, and return to normal operation after the bounded recovery conditions are satisfied.

### CUC-9

CUC-9 exercises cognitive-strategy comparison.

The bounded experiment produced:

```
candidate improvement=0.25 across 3 holdouts
eligible_for_human_review=true
auto_promoted=false
```

The important authority property is that successful experimental cognitive strategies do not automatically promote themselves.

Evidence may make a candidate eligible for review, but promotion remains outside autonomous authority.

## Reproducible quality gates

Run the complete quality gate with:

```
python check_green.py
```

Individual gates remain available:

```
python check_green.py --gate format
python check_green.py --gate lint
python check_green.py --gate type-check
python check_green.py --gate repository
python check_green.py --gate dependencies
python check_green.py --gate architecture
python check_green.py --gate test
python check_green.py --gate package
```

The final full run reported:

```
All selected quality gates passed.
```

## Validation scope

This report validates repository behavior and the implemented mechanisms under the repository's test conditions.

The successful quality gates establish that:

- the source tree is formatted according to the configured Ruff formatter;
- Ruff reports no lint violations;
- MyPy strict type checking passes;
- repository integrity checks pass;
- the runtime dependency graph contains no detected cycles;
- architecture-boundary checks pass;
- all 1,053 collected tests pass;
- the installed wheel passes its smoke test.

These results do not establish that every possible external environment, workload, or open-ended cognitive setting has been tested.

## AGI claim boundary

IX-Sally v0.8.0 is an experimental cognitive architecture investigating mechanisms that may be relevant to general intelligence.

The current results do **not** establish:

- AGI;
- consciousness;
- sentience;
- unrestricted autonomy;
- independent self-replication;
- open-ended general intelligence;
- human-equivalent cognition;
- autonomous authority over consequential actions.

CUC-7 through CUC-9 are bounded experiments.

They test whether mechanisms involving prediction error, independent observations, disagreement, contradiction, assumption revalidation, information-seeking goals, recovery, and cognitive-strategy comparison can cause later cognition to change in an evidence-linked manner.

The appropriate claim is therefore:

> IX-Sally v0.8.0 implements and tests a reality-coupled experimental cognitive architecture with evidence-linked recovery, uncertainty-sensitive cognitive selection, assumption revalidation, and bounded cognitive-strategy evaluation.

It should not be described as a demonstrated AGI system.

## Final verification status

Final locally verified release state:

```
Version: 0.8.0

Ruff format: PASS
Ruff lint: PASS
MyPy strict: PASS
Repository integrity: PASS
Dependency graph: PASS
Architecture boundaries: PASS
Pytest: 1053 passed
Installed wheel smoke: PASS

Overall:
All selected quality gates passed.
```