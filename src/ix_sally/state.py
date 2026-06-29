"""Ninefold run state aggregate for IX-Sally chamber execution."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.actions import BoundedActionLedger, BoundedActionRecord
from ix_sally.artifacts import AgentArtifact, AgentArtifactLedger
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionLedger
from ix_sally.claims import ClaimLedger, ClaimRecord
from ix_sally.cycles import NinefoldCycleLedger, NinefoldCyclePacket
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.events import RuntimeEvent, RuntimeTranscript
from ix_sally.evidence import EvidenceLedger, EvidenceRecord
from ix_sally.memory import MemoryLedger, MemoryRecord
from ix_sally.runtime import NinefoldRuntimeKit


@dataclass(frozen=True, slots=True)
class NinefoldRunState:
    """Immutable aggregate state for one governed IX-Sally chamber run."""

    runtime_kit: NinefoldRuntimeKit
    transcript: RuntimeTranscript
    artifacts: AgentArtifactLedger
    claims: ClaimLedger
    evidence: EvidenceLedger
    memory: MemoryLedger
    actions: BoundedActionLedger
    authority_decisions: AuthorityDecisionLedger
    cycles: NinefoldCycleLedger

    @classmethod
    def create(cls, *, runtime_kit: NinefoldRuntimeKit) -> NinefoldRunState:
        """Create a run state with a deterministic chamber-opening event."""
        opening_event = runtime_kit.opening_event(sequence=1)
        return cls(
            runtime_kit=runtime_kit,
            transcript=RuntimeTranscript.create((opening_event,)),
            artifacts=AgentArtifactLedger.create(()),
            claims=ClaimLedger.create(()),
            evidence=EvidenceLedger.create(()),
            memory=MemoryLedger.create(()),
            actions=BoundedActionLedger.create(()),
            authority_decisions=AuthorityDecisionLedger.create(()),
            cycles=NinefoldCycleLedger.create(()),
        )

    def next_event_sequence(self) -> int:
        """Return the next transcript sequence number."""
        return self.transcript.next_sequence()

    def completed_cycles(self) -> int:
        """Return the number of completed ninefold cycles."""
        return len(self.cycles.cycles)

    def with_event(self, event: RuntimeEvent) -> NinefoldRunState:
        """Return a new state with an appended transcript event."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript.append(event),
            artifacts=self.artifacts,
            claims=self.claims,
            evidence=self.evidence,
            memory=self.memory,
            actions=self.actions,
            authority_decisions=self.authority_decisions,
            cycles=self.cycles,
        )

    def with_artifact(self, artifact: AgentArtifact) -> NinefoldRunState:
        """Return a new state with an appended agent artifact."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts.append(artifact),
            claims=self.claims,
            evidence=self.evidence,
            memory=self.memory,
            actions=self.actions,
            authority_decisions=self.authority_decisions,
            cycles=self.cycles,
        )

    def with_claim(self, claim: ClaimRecord) -> NinefoldRunState:
        """Return a new state with an appended claim."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts,
            claims=self.claims.append(claim),
            evidence=self.evidence,
            memory=self.memory,
            actions=self.actions,
            authority_decisions=self.authority_decisions,
            cycles=self.cycles,
        )

    def with_evidence(self, evidence: EvidenceRecord) -> NinefoldRunState:
        """Return a new state with an appended evidence record."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts,
            claims=self.claims,
            evidence=self.evidence.append(evidence),
            memory=self.memory,
            actions=self.actions,
            authority_decisions=self.authority_decisions,
            cycles=self.cycles,
        )

    def with_memory(self, memory: MemoryRecord) -> NinefoldRunState:
        """Return a new state with an appended memory record."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts,
            claims=self.claims,
            evidence=self.evidence,
            memory=self.memory.append(memory),
            actions=self.actions,
            authority_decisions=self.authority_decisions,
            cycles=self.cycles,
        )

    def with_action(self, action: BoundedActionRecord) -> NinefoldRunState:
        """Return a new state with an appended bounded action record."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts,
            claims=self.claims,
            evidence=self.evidence,
            memory=self.memory,
            actions=self.actions.append(action),
            authority_decisions=self.authority_decisions,
            cycles=self.cycles,
        )

    def with_authority_decision(self, decision: AuthorityDecision) -> NinefoldRunState:
        """Return a new state with an appended authority decision."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts,
            claims=self.claims,
            evidence=self.evidence,
            memory=self.memory,
            actions=self.actions,
            authority_decisions=self.authority_decisions.append(decision),
            cycles=self.cycles,
        )

    def with_cycle(self, cycle: NinefoldCyclePacket) -> NinefoldRunState:
        """Return a new state with an appended completed ninefold cycle."""
        return NinefoldRunState(
            runtime_kit=self.runtime_kit,
            transcript=self.transcript,
            artifacts=self.artifacts,
            claims=self.claims,
            evidence=self.evidence,
            memory=self.memory,
            actions=self.actions,
            authority_decisions=self.authority_decisions,
            cycles=self.cycles.append(cycle),
        )

    def requires_human_review(self) -> bool:
        """Return whether the state contains any human-review action, decision, or cycle."""
        return bool(
            self.actions.human_review_actions()
            or self.authority_decisions.human_review_decisions()
            or self.cycles.human_review_cycles()
        )

    def denied_authority_count(self) -> int:
        """Return the number of denied authority decisions."""
        return len(self.authority_decisions.denied_decisions())

    def human_review_authority_count(self) -> int:
        """Return the number of authority decisions requiring human review."""
        return len(self.authority_decisions.human_review_decisions())

    def executable_action_count(self) -> int:
        """Return the number of bounded actions authorized for execution."""
        return len(self.actions.executable_actions())

    def blocked_action_count(self) -> int:
        """Return the number of bounded actions blocking autonomous continuation."""
        return len(self.actions.blocked_actions())

    def human_review_action_count(self) -> int:
        """Return the number of bounded actions waiting on human review."""
        return len(self.actions.human_review_actions())

    def stop_condition_payload(self) -> JsonObject:
        """Return the current chamber stop condition as stable payload data."""
        return self.runtime_kit.chamber.stop_for_cycle(self.completed_cycles()).to_payload()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible run-state representation."""
        return {
            "runtime_digest": self.runtime_kit.digest().value,
            "transcript_digest": self.transcript.digest().value,
            "artifact_ledger_digest": self.artifacts.digest().value,
            "claim_ledger_digest": self.claims.digest().value,
            "evidence_ledger_digest": self.evidence.digest().value,
            "memory_ledger_digest": self.memory.digest().value,
            "action_ledger_digest": self.actions.digest().value,
            "authority_decision_ledger_digest": self.authority_decisions.digest().value,
            "cycle_ledger_digest": self.cycles.digest().value,
            "event_count": len(self.transcript.events),
            "artifact_count": len(self.artifacts.artifacts),
            "claim_count": len(self.claims.claims),
            "evidence_count": len(self.evidence.records),
            "memory_count": len(self.memory.records),
            "action_count": len(self.actions.actions),
            "executable_action_count": self.executable_action_count(),
            "blocked_action_count": self.blocked_action_count(),
            "human_review_action_count": self.human_review_action_count(),
            "authority_decision_count": len(self.authority_decisions.decisions),
            "denied_authority_count": self.denied_authority_count(),
            "human_review_authority_count": self.human_review_authority_count(),
            "completed_cycles": self.completed_cycles(),
            "requires_human_review": self.requires_human_review(),
            "stop_condition": self.stop_condition_payload(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete run state."""
        return DigestRecord.from_payload(self.to_payload())
