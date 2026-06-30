# IX-Sally

IX-Sally is a source-available, evaluation-only governed AI operating architecture for controlled proposal intake, evidence handling, staged execution, human review, certified resume, audited reentry, and closeout reporting.

The core rule is simple:

**AI proposes. Humans decide. Evidence governs what may proceed.**

IX-Sally is not an autonomous agent framework, not a deployment bot, not a compliance certification engine, and not an AGI claim. It is a receipt-driven control-plane architecture for proving that proposals, execution readiness, human decisions, reentry, and closeout status were handled under explicit authority boundaries.

## Purpose

Modern AI systems can produce confident outputs that look actionable before they are grounded, reviewed, authorized, or safe to execute. IX-Sally is built around the opposite assumption:

- Output is not evidence.
- Proposal is not permission.
- Capability is not authority.
- Human review is not optional ceremony.
- Resume after human review must be certified.
- Reentry after resume must be audited.
- Closeout must be ledgered and exportable.

The system is designed to make every meaningful transition inspectable through deterministic records, digests, receipts, ledgers, reports, and control-plane snapshots.

## What IX-Sally does

IX-Sally models a governed workflow for AI-assisted operations:

1. Establish a bounded contract and run state.
2. Accept proposals only through explicit intake and gateway structures.
3. Evaluate evidence and support before action is treated as ready.
4. Gate staged orchestration through readiness checks.
5. Dispatch only bounded execution candidates.
6. Process Forge results through structured result gateways.
7. Route human-boundary actions into human review.
8. Record human review handoffs, packets, dockets, bundles, and decisions.
9. Certify cleared resume after human authority is recorded.
10. Reenter orchestration after resume with explicit receipts.
11. Audit reentry before treating it as accepted.
12. Record complete reentry and closeout.
13. Export closeout evidence packets for downstream review.

The emphasis is not on making an AI act faster. The emphasis is on making it harder for unearned authority, unsupported claims, or skipped review to pass unnoticed.

## Current capability

IX-Sally now includes a complete governed control-plane path from proposal intake through final human-review reentry closeout export.

Major capabilities include:

- Deterministic digest records and canonical payloads.
- Doctrine and boundary primitives.
- Runtime contracts and bounded run state.
- Proposal intake, proposal gateway, and Sally proposal routing.
- Evidence records, evidence support records, and evidence support processing.
- Stage readiness, stage gates, stage advance receipts, and staged orchestration.
- One-step orchestration and loop-runner support.
- Execution queues, execution planning, execution dispatch, and Forge result processing.
- Forge evidence, Forge result records, Forge result gateway, and Forge result processing.
- Human-review gateway, docket, packets, operator bundle, and bundle ledger.
- Human-review handoff coordination.
- Human-review decision ledger and decision coordination.
- Human-review resolution audit and clearance reporting.
- Human-review resume certificate, resume ledger, and resume coordination.
- Human-review control-plane state, coordinator, status, snapshot, and report.
- Human-review workflow kit for handoff, decision, clearance, resume, reentry, audit, complete reentry, and closeout.
- Certified human-review reentry runner.
- Reentry result ledger.
- Reentry audit report and audit ledger.
- Audited reentry coordination and ledger.
- Complete reentry coordination and ledger.
- Complete reentry closeout report and closeout ledger.
- Complete reentry closeout coordination and coordination ledger.
- Complete reentry closeout export packet.

## Human-review control plane

The human-review control plane is the center of the repository.

It records and reports:

- Handoffs.
- Human decisions.
- Resume certificates.
- Reentry results.
- Reentry audits.
- Audited reentries.
- Complete reentries.
- Complete reentry closeouts.
- Complete reentry closeout coordination results.

The control plane is intentionally ledger-driven. Each update creates a new immutable state instead of mutating prior records. This gives the runtime a stable basis for asking:

- What was handed off?
- Who decided?
- Was resume cleared?
- Did reentry actually advance state?
- Did the reentry audit pass?
- Was the complete reentry recorded?
- Was closeout accepted, waiting, or blocked?
- Can the result be exported without operator attention?

## Complete reentry closeout path

The final closeout path is the most complete human-review lifecycle currently represented in IX-Sally.

A cleared resume can be passed through:

1. Complete reentry coordination.
2. Reentry execution.
3. Reentry audit.
4. Audited reentry recording.
5. Complete reentry recording.
6. Closeout report creation.
7. Closeout workflow recording.
8. Closeout coordination ledgering.
9. Export packet creation.

The export packet links the major evidence layers:

- Coordination result.
- Coordination receipt.
- Closeout report.
- Closeout workflow operation.
- Final state.
- Final control plane.
- Closeout ledger.
- Closeout coordination ledger.

This makes the final state portable for review without implying automatic approval, certification, or production readiness.

## Repository shape

IX-Sally is a standalone modular-monolith Python repository. It is intentionally not a collection of repo-hopping integrations. The modules are small, explicit, testable units connected through typed records and deterministic payloads.

Core module families include:

- Foundation, digest, state, runtime, and recording.
- Doctrine, claims, boundaries, jurisdiction, and contracts.
- Proposals, proposal intake, and proposal gateways.
- Evidence, evidence support, and evidence processing.
- Stage readiness, stage gates, orchestration, and orchestration receipts.
- Execution planning, queueing, dispatch, and Forge result processing.
- Human review handoff, packets, dockets, bundles, decisions, clearance, resume, reentry, audit, closeout, and export.

## Design principles

IX-Sally follows these principles:

### 1. No self-approval

The system may create records, evaluate readiness, and prepare evidence. It may not convert its own output into authority.

### 2. Evidence before motion

Readiness and support are represented as records. Unsupported claims must not silently become executable steps.

### 3. Human authority remains explicit

Human-review boundaries are not hidden inside generic success paths. Handoffs, decisions, clearance, resume, and reentry are separate records.

### 4. Resume is certified

After human review, the system does not simply continue. It records a resume certificate and resumes from a traceable state.

### 5. Reentry is audited

A resumed workflow is not treated as clean merely because it advanced. Reentry is separately audited and reported.

### 6. Closeout is exportable

The final closeout state can be converted into a digest-linked export packet for inspection, review, or downstream evidence handling.

### 7. Determinism over theater

The repository favors small immutable records, stable JSON-compatible payloads, digest links, and tests over broad claims.

## What IX-Sally is not

IX-Sally is not:

- An AGI system.
- An autonomous operations platform.
- A production deployment tool.
- A certification authority.
- A substitute for human judgment.
- A legal, safety, security, or compliance guarantee.
- A system that grants AI independent authority.

It is an evaluation architecture for governed AI workflow control.

## Example use cases

IX-Sally may be useful for research and evaluation work involving:

- AI proposal governance.
- Human-in-the-loop execution control.
- AI evidence handling.
- Audit-oriented orchestration.
- Review-gated tool execution.
- Safety-case style workflow records.
- Receipt-driven agent evaluation.
- Control-plane design for AI-assisted engineering.
- Demonstrations of bounded AI authority.

## Development status

This repository is a research and evaluation build. It is structured around deterministic behavior, typed records, and tests. Interfaces may evolve as the control-plane model is refined.

Do not treat this repository as production-ready. Do not use it to authorize real-world execution without independent engineering, legal, security, safety, and human governance review.

## Running tests

Typical local development flow:

```
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
```
Depending on environment configuration, set PYTHONPATH=src before running tests.

PowerShell example:
```
$env:PYTHONPATH="src"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
```
License posture

IX-Sally is source-available for evaluation and review.

Public viewing and evaluation are allowed. Production use, commercial use, hosted use, derivative use, funded use, government or regulated operational use, redistribution, or ownership transfer require written permission and a paid commercial license from Bryce Lovell.

See the repository license file for the controlling terms.

Claim boundary

IX-Sally demonstrates a governed control-plane architecture for AI-assisted proposal, evidence, review, resume, reentry, audit, closeout, and export workflows.

It does not claim autonomous trustworthiness. It does not claim certification. It does not claim AGI.

The correct interpretation is:

IX-Sally is a receipt-driven governed AI workflow architecture where AI output remains subordinate to evidence, explicit authority, human review, and auditable control-plane state.
