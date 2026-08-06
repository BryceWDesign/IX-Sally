"""Stage-gated Sally proposal submission for IX-Sally orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text
from ix_sally.proposal_intake import SallyProposalIntake, SallyProposalIntakeResult
from ix_sally.proposals import SallyProposalPacket
from ix_sally.recording import StateRecorder
from ix_sally.stage_gate import RunStageGate, StageGateDecision
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class SallyProposalSubmissionReceipt:
    """Compact receipt for a stage-gated Sally proposal submission."""

    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    proposal_digest: DigestRecord
    proposal_artifact_digest: DigestRecord
    gate_decision_digest: DigestRecord
    intake_digest: DigestRecord
    action_count: int
    claim_count: int
    requires_human_review: bool
    detail: str

    @classmethod
    def create(
        cls,
        *,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        proposal_digest: DigestRecord,
        proposal_artifact_digest: DigestRecord,
        gate_decision_digest: DigestRecord,
        intake_digest: DigestRecord,
        action_count: int,
        claim_count: int,
        requires_human_review: bool,
        detail: str,
    ) -> SallyProposalSubmissionReceipt:
        """Create a normalized proposal submission receipt."""
        if action_count < 0:
            raise FoundationError("proposal submission action_count must not be negative")
        if claim_count < 0:
            raise FoundationError("proposal submission claim_count must not be negative")

        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        proposal_digest.require_algorithm("sha256")
        proposal_artifact_digest.require_algorithm("sha256")
        gate_decision_digest.require_algorithm("sha256")
        intake_digest.require_algorithm("sha256")

        return cls(
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            proposal_digest=proposal_digest,
            proposal_artifact_digest=proposal_artifact_digest,
            gate_decision_digest=gate_decision_digest,
            intake_digest=intake_digest,
            action_count=action_count,
            claim_count=claim_count,
            requires_human_review=requires_human_review,
            detail=require_text(detail, field_name="detail"),
        )

    @classmethod
    def from_intake(
        cls,
        *,
        before_state_digest: DigestRecord,
        proposal: SallyProposalPacket,
        gate_decision: StageGateDecision,
        intake_result: SallyProposalIntakeResult,
    ) -> SallyProposalSubmissionReceipt:
        """Create a proposal submission receipt from a proposal intake result."""
        return cls.create(
            before_state_digest=before_state_digest,
            after_state_digest=intake_result.state.digest(),
            proposal_digest=proposal.digest(),
            proposal_artifact_digest=intake_result.proposal_artifact.digest(),
            gate_decision_digest=gate_decision.digest(),
            intake_digest=intake_result.digest(),
            action_count=intake_result.action_count(),
            claim_count=intake_result.claim_count(),
            requires_human_review=intake_result.requires_human_review(),
            detail=("Accepted Sally proposal into run state after proposal-intake stage gate."),
        )

    def changed_state(self) -> bool:
        """Return whether this submission changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible proposal submission receipt."""
        return {
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "proposal_digest": {
                "algorithm": self.proposal_digest.algorithm,
                "value": self.proposal_digest.value,
            },
            "proposal_artifact_digest": {
                "algorithm": self.proposal_artifact_digest.algorithm,
                "value": self.proposal_artifact_digest.value,
            },
            "gate_decision_digest": {
                "algorithm": self.gate_decision_digest.algorithm,
                "value": self.gate_decision_digest.value,
            },
            "intake_digest": {
                "algorithm": self.intake_digest.algorithm,
                "value": self.intake_digest.value,
            },
            "action_count": self.action_count,
            "claim_count": self.claim_count,
            "requires_human_review": self.requires_human_review,
            "changed_state": self.changed_state(),
            "detail": self.detail,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this proposal submission receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SallyProposalSubmissionResult:
    """Result of submitting a Sally proposal through the stage gate."""

    state: NinefoldRunState
    before_snapshot: RunStageSnapshot
    gate_decision: StageGateDecision
    intake_result: SallyProposalIntakeResult
    receipt: SallyProposalSubmissionReceipt

    def next_snapshot(self) -> RunStageSnapshot:
        """Return the next stage snapshot after proposal intake."""
        return RunStageSnapshot.from_state(self.state)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible proposal submission result."""
        actions_payload: JsonArray = []
        for action in self.intake_result.bounded_actions:
            actions_payload.append(action.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "before_snapshot_digest": self.before_snapshot.digest().value,
            "before_stage": self.before_snapshot.stage.value,
            "next_snapshot_digest": self.next_snapshot().digest().value,
            "next_stage": self.next_snapshot().stage.value,
            "gate_decision_digest": self.gate_decision.digest().value,
            "intake_digest": self.intake_result.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "action_count": self.intake_result.action_count(),
            "claim_count": self.intake_result.claim_count(),
            "requires_human_review": self.intake_result.requires_human_review(),
            "bounded_actions": actions_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this proposal submission result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SallyProposalGateway:
    """Accepts Sally proposals only when the run state is at proposal intake."""

    gate: RunStageGate
    intake: SallyProposalIntake

    @classmethod
    def create(cls) -> SallyProposalGateway:
        """Create a proposal gateway with the standard IX-Sally recorder."""
        recorder = StateRecorder()
        return cls(
            gate=RunStageGate(),
            intake=SallyProposalIntake(recorder),
        )

    def submit(
        self,
        *,
        state: NinefoldRunState,
        proposal: SallyProposalPacket,
        tool_bindings: Mapping[str, str] | None = None,
    ) -> SallyProposalSubmissionResult:
        """Submit a Sally proposal if and only if proposal intake is the active stage."""
        before_snapshot = RunStageSnapshot.from_state(state)
        decision = self.gate.require(
            state=state,
            expected_stage=RunStage.PROPOSAL_INTAKE,
        )

        intake_result = self.intake.record(
            state=state,
            proposal=proposal,
            tool_bindings=tool_bindings,
        )
        receipt = SallyProposalSubmissionReceipt.from_intake(
            before_state_digest=before_snapshot.state_digest,
            proposal=proposal,
            gate_decision=decision,
            intake_result=intake_result,
        )

        return SallyProposalSubmissionResult(
            state=intake_result.state,
            before_snapshot=before_snapshot,
            gate_decision=decision,
            intake_result=intake_result,
            receipt=receipt,
        )
