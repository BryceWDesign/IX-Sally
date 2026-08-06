# IX-Sally Validation Report

## Release identity

- Repository: `IX-Sally`
- Package: `ix-sally`
- Package version: `0.1.0`
- Delivery model: one complete source repository state
- Runtime dependency declaration: zero third-party packages
- Local validation interpreter: CPython 3.13.5

## Scope of this shipment

This repository combines the inherited IX-Sally governance control plane with a
new bounded experimental cognitive runtime. The delivered implementation
includes typed IX execution, deterministic bytecode, a bounded virtual machine,
grounded primitives, attention, active memory, replayable episodes, an
epistemically typed world model, causal inference, planning, goal selection,
calibrated uncertainty, curricula, learning, held-out transfer records,
metacognition, regression-aware adaptation, persistence, recovery, a functional
ninefold cycle, and integration into the existing human-authority proposal path.

This is a complete source shipment for those declared capabilities. It contains
no known TODO-only implementations, `pass` placeholders, `NotImplementedError`
paths, or intentionally empty subsystem stubs.

External foundation-model weights, training corpora, sensors, actuators,
network services, and proprietary benchmark data are not bundled. They are
explicit external system boundaries, not silently missing repository files.

## Baseline repair

The supplied source archive contained fourteen malformed indentation prefixes
across twelve source and test files. Those syntax defects were repaired without
changing the intended behavior. After repair, the inherited test baseline
passed all 889 collected tests.

## Final observed test inventory

Pytest collection after the cognitive implementation and release hardening
identified exactly **969 tests across 135 test files**.

The inventory was divided into four balanced deterministic file shards to avoid
allowing one long process to hide a slow tail:

| Shard | Tests | Result |
| --- | ---: | --- |
| 1 | 243 | Passed, process exit 0 |
| 2 | 242 | Passed, process exit 0 |
| 3 | 242 | Passed, process exit 0 |
| 4 | 242 | Passed, process exit 0 |
| **Total** | **969** | **Passed** |

No test failure, collection error, or skipped failure was observed in those
runs.

## Executed quality gates

The following gates were executed against the final working tree:

| Gate | Observed result |
| --- | --- |
| Python compilation | `src`, `tests`, and `examples` compiled successfully |
| Repository integrity | 263 clean Python source/test files, 0 violations |
| Runtime dependency graph | 123 modules, 655 imports, 0 cycles |
| Runtime architecture | 123 modules, 655 imports, 0 boundary violations |
| Installed wheel smoke test | Passed |
| Built-in cognitive evaluation | 15 of 15 observed benchmarks passed |
| IX example execution | Halted cleanly with a deterministic execution receipt |
| Empty complete snapshot | Canonical snapshot produced and validated |
| Integrated cognitive example | Completed and produced proposal/receipt output |
| Python source line limit | 0 lines over 100 characters in `src`, `tests`, and `examples` |
| Trailing whitespace | 0 findings in source, tests, examples, docs, and configuration |
| Incomplete implementation scan | 0 source TODO/FIXME/placeholder/`pass`/`NotImplementedError` findings |

The only occurrence of the word `placeholder` is in a parser test asserting
that blank lines and comments do not create placeholder statements.

## Built-in cognitive evaluation

`python -m ix_sally --cognitive-evaluation` observed all fifteen declared local
benchmarks passing:

1. typed IX arithmetic;
2. governed VM memory;
3. grounded primitive execution;
4. active-memory retrieval;
5. causal prediction;
6. bounded planning;
7. measured transfer;
8. functional ninefold coordination;
9. human-authority blocking;
10. calibrated uncertainty;
11. executive-to-governance bridging;
12. separated held-out curriculum evidence;
13. replayable episode chaining;
14. regression-aware adaptation;
15. exact complete-state restoration.

The report classifies the repository as an
`experimental-cognitive-architecture` and fixes `agi_certified` to `false`.
Passing these checks verifies implemented mechanisms; it does not establish
artificial general intelligence.

## Gates not executed locally

The following configured CI gates could not be executed in the available local
environment:

- Ruff formatting check;
- Ruff lint check;
- Mypy strict type check;
- CPython 3.11 execution;
- CPython 3.12 execution.

The environment contained CPython 3.13.5 and Pytest, but its package source did
not provide Ruff or Mypy, and Python 3.11/3.12 interpreters were not installed.
Those tools were not simulated and their results are not claimed.

The repository retains GitHub Actions configuration for Python 3.11, 3.12, and
3.13. That workflow installs the development tools and runs formatting, lint,
strict typing, repository, dependency, architecture, test, and installed-wheel
gates. A GitHub green status remains external evidence to obtain after upload;
this report does not fabricate it.

## Claim boundary

This shipment establishes a substantial governed experimental cognitive
runtime. It does not establish:

- AGI;
- human-level intelligence;
- open-world competence;
- production safety;
- autonomous authority;
- certification;
- legal, security, or regulatory compliance.

The controlling operating rule remains:

> AI proposes. Humans decide. Evidence governs what may proceed.
