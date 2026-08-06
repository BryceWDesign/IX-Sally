"""Stage gates for deterministic IX-Sally run orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


class StageGateStatus(StrEnum):
    """Decision status for a run-stage gate check."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StageGateDecision:
    """Receipt-grade decision for whether a state may enter a requested stage."""

    expected_stage: RunStage
    observed_stage: RunStage
    status: StageGateStatus
    rationale: str
    snapshot_digest: DigestRecord
    state_digest: DigestRecord

    @classmethod
    def from_snapshot(
        cls,
        *,
        snapshot: RunStageSnapshot,
        expected_stage: RunStage,
    ) -> StageGateDecision:
        """Create a gate decision from an immutable stage snapshot."""
        if snapshot.stage is expected_stage:
            status = StageGateStatus.ALLOWED
            rationale = f"Expected stage is active: {expected_stage.value}."
        else:
            status = StageGateStatus.BLOCKED
            rationale = (
                f"Stage gate expected {expected_stage.value} but observed {snapshot.stage.value}."
            )

        return cls(
            expected_stage=expected_stage,
            observed_stage=snapshot.stage,
            status=status,
            rationale=rationale,
            snapshot_digest=snapshot.digest(),
            state_digest=snapshot.state_digest,
        )

    def allows_entry(self) -> bool:
        """Return whether the requested stage may proceed."""
        return self.status is StageGateStatus.ALLOWED

    def blocks_entry(self) -> bool:
        """Return whether the requested stage is blocked."""
        return self.status is StageGateStatus.BLOCKED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible stage gate decision."""
        return {
            "expected_stage": self.expected_stage.value,
            "observed_stage": self.observed_stage.value,
            "status": self.status.value,
            "rationale": self.rationale,
            "snapshot_digest": {
                "algorithm": self.snapshot_digest.algorithm,
                "value": self.snapshot_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "allows_entry": self.allows_entry(),
            "blocks_entry": self.blocks_entry(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this stage gate decision."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class RunStageGate:
    """Evaluates and enforces the next legal stage for a run state."""

    def evaluate(
        self,
        *,
        state: NinefoldRunState,
        expected_stage: RunStage,
    ) -> StageGateDecision:
        """Return a gate decision without mutating state or raising."""
        snapshot = RunStageSnapshot.from_state(state)
        return StageGateDecision.from_snapshot(
            snapshot=snapshot,
            expected_stage=expected_stage,
        )

    def require(
        self,
        *,
        state: NinefoldRunState,
        expected_stage: RunStage,
    ) -> StageGateDecision:
        """Return an allowed decision or raise when the state is at another stage."""
        decision = self.evaluate(state=state, expected_stage=expected_stage)
        if decision.blocks_entry():
            raise FoundationError(decision.rationale)
        return decision
