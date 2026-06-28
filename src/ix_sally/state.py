"""Ninefold run state aggregate for IX-Sally chamber execution."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.artifacts import AgentArtifact, AgentArtifactLedger
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
            cycles=self.cycles.append(cycle),
        )

    def requires_human_review(self) -> bool:
        """Return whether the state contains any human-review cycle."""
        return bool(self.cycles.human_review_cycles())

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
            "cycle_ledger_digest": self.cycles.digest().value,
            "event_count": len(self.transcript.events),
            "artifact_count": len(self.artifacts.artifacts),
            "claim_count": len(self.claims.claims),
            "evidence_count": len(self.evidence.records),
            "memory_count": len(self.memory.records),
            "completed_cycles": self.completed_cycles(),
            "requires_human_review": self.requires_human_review(),
            "stop_condition": self.stop_condition_payload(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete run state."""
        return DigestRecord.from_payload(self.to_payload())
