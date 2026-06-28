"""Event-linked state recording helpers for IX-Sally chamber runs."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.artifacts import AgentArtifact
from ix_sally.claims import ClaimRecord
from ix_sally.cycles import NinefoldCyclePacket
from ix_sally.events import RuntimeEvent, RuntimeEventType, event_payload_with_reference
from ix_sally.evidence import EvidenceRecord
from ix_sally.memory import MemoryRecord
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class StateRecorder:
    """Recorder that appends ledger records and matching transcript events."""

    def record_artifact(self, state: NinefoldRunState, artifact: AgentArtifact) -> NinefoldRunState:
        """Record an agent artifact and emit an artifact transcript event."""
        updated = state.with_artifact(artifact)
        event = RuntimeEvent.create(
            sequence=updated.next_event_sequence(),
            cycle=artifact.cycle,
            event_type=RuntimeEventType.AGENT_ARTIFACT_RECORDED,
            actor=artifact.role,
            summary=f"Recorded {artifact.role.value} artifact: {artifact.kind.value}.",
            payload=event_payload_with_reference(
                reference_type="agent-artifact",
                reference_digest=artifact.digest(),
            ),
        )
        return updated.with_event(event)

    def record_claim(self, state: NinefoldRunState, claim: ClaimRecord) -> NinefoldRunState:
        """Record a claim and emit a claim transcript event."""
        updated = state.with_claim(claim)
        event = RuntimeEvent.create(
            sequence=updated.next_event_sequence(),
            cycle=claim.cycle,
            event_type=RuntimeEventType.AGENT_ARTIFACT_RECORDED,
            actor=claim.author,
            summary=f"Recorded claim from {claim.author.value}: {claim.status.value}.",
            payload=event_payload_with_reference(
                reference_type="claim-record",
                reference_digest=claim.digest(),
            ),
        )
        return updated.with_event(event)

    def record_evidence(self, state: NinefoldRunState, evidence: EvidenceRecord) -> NinefoldRunState:
        """Record evidence and emit an evidence transcript event."""
        updated = state.with_evidence(evidence)
        event = RuntimeEvent.create(
            sequence=updated.next_event_sequence(),
            cycle=evidence.cycle,
            event_type=RuntimeEventType.EVIDENCE_RECORDED,
            actor=evidence.produced_by,
            summary=f"Recorded evidence from {evidence.produced_by.value}: {evidence.status.value}.",
            payload=event_payload_with_reference(
                reference_type="evidence-record",
                reference_digest=evidence.digest(),
            ),
        )
        return updated.with_event(event)

    def record_memory(self, state: NinefoldRunState, memory: MemoryRecord) -> NinefoldRunState:
        """Record a memory candidate or decision result and emit a memory transcript event."""
        updated = state.with_memory(memory)
        event = RuntimeEvent.create(
            sequence=updated.next_event_sequence(),
            cycle=memory.cycle,
            event_type=RuntimeEventType.MEMORY_DECIDED,
            actor=memory.proposed_by,
            summary=f"Recorded memory from {memory.proposed_by.value}: {memory.status.value}.",
            payload=event_payload_with_reference(
                reference_type="memory-record",
                reference_digest=memory.digest(),
            ),
        )
        return updated.with_event(event)

    def record_cycle(self, state: NinefoldRunState, cycle: NinefoldCyclePacket) -> NinefoldRunState:
        """Record a completed ninefold cycle and emit a cycle stop transcript event."""
        updated = state.with_cycle(cycle)
        event = RuntimeEvent.create(
            sequence=updated.next_event_sequence(),
            cycle=cycle.cycle,
            event_type=RuntimeEventType.CYCLE_STOPPED,
            summary=f"Recorded ninefold cycle: {cycle.status.value}.",
            payload=event_payload_with_reference(
                reference_type="ninefold-cycle",
                reference_digest=cycle.digest(),
            ),
        )
        return updated.with_event(event)

    def close_chamber(self, state: NinefoldRunState, *, summary: str) -> NinefoldRunState:
        """Emit a chamber-closed transcript event without changing ledgers."""
        event = RuntimeEvent.create(
            sequence=state.next_event_sequence(),
            cycle=state.completed_cycles(),
            event_type=RuntimeEventType.CHAMBER_CLOSED,
            summary=summary,
            payload={
                "state_digest": state.digest().value,
                "completed_cycles": state.completed_cycles(),
                "requires_human_review": state.requires_human_review(),
            },
        )
        return state.with_event(event)
