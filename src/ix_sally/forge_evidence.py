"""Forge evidence adapter for IX-Sally execution-result evidence records."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.forge_results import ForgeResultRecord
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class ForgeEvidenceRecord:
    """Links a Forge result to the evidence record derived from it."""

    forge_result_digest: DigestRecord
    evidence_record: EvidenceRecord
    evidence_summary: str

    @classmethod
    def create(
        cls,
        *,
        forge_result: ForgeResultRecord,
        evidence_record: EvidenceRecord,
        evidence_summary: str,
    ) -> ForgeEvidenceRecord:
        """Create a normalized Forge evidence link."""
        forge_result.digest().require_algorithm("sha256")
        evidence_record.digest().require_algorithm("sha256")

        if evidence_record.cycle != forge_result.cycle:
            raise FoundationError("Forge evidence cycle must match Forge result cycle")

        if evidence_record.produced_by is not AgentRole.FORGE:
            raise FoundationError("Forge evidence records must be produced by IX-Forge")

        if evidence_record.status is not EvidenceStatus.RECORDED:
            raise FoundationError("Forge evidence records must be recorded evidence")

        return cls(
            forge_result_digest=forge_result.digest(),
            evidence_record=evidence_record,
            evidence_summary=evidence_summary.strip(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge evidence representation."""
        return {
            "forge_result_digest": {
                "algorithm": self.forge_result_digest.algorithm,
                "value": self.forge_result_digest.value,
            },
            "evidence_record_digest": self.evidence_record.digest().value,
            "evidence_summary": self.evidence_summary,
            "evidence_status": self.evidence_record.status.value,
            "evidence_kind": self.evidence_record.kind.value,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge evidence link."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeEvidenceProcessingResult:
    """Result of converting Forge results into evidence records."""

    state: NinefoldRunState
    evidence_records: tuple[ForgeEvidenceRecord, ...]

    def evidence_count(self) -> int:
        """Return the number of Forge evidence records created."""
        return len(self.evidence_records)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge evidence processing result."""
        evidence_payload: JsonArray = []
        for record in self.evidence_records:
            evidence_payload.append(record.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "evidence_count": self.evidence_count(),
            "evidence_records": evidence_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge evidence processing result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeEvidenceAdapter:
    """Converts Forge results into evidence ledger records."""

    recorder: StateRecorder

    def evidence_from_result(self, result: ForgeResultRecord) -> EvidenceRecord:
        """Create an evidence record from one Forge result."""
        return EvidenceRecord.create(
            cycle=result.cycle,
            produced_by=AgentRole.FORGE,
            kind=EvidenceKind.OBSERVATION,
            status=EvidenceStatus.RECORDED,
            summary=self._summary_for_result(result),
        )

    def record_result_evidence(
        self,
        *,
        state: NinefoldRunState,
        result: ForgeResultRecord,
    ) -> ForgeEvidenceProcessingResult:
        """Convert one Forge result into evidence and record it."""
        evidence = self.evidence_from_result(result)
        forge_evidence = ForgeEvidenceRecord.create(
            forge_result=result,
            evidence_record=evidence,
            evidence_summary=evidence.summary,
        )
        updated = self.recorder.record_evidence(state, evidence)

        return ForgeEvidenceProcessingResult(
            state=updated,
            evidence_records=(forge_evidence,),
        )

    def record_all_result_evidence(
        self,
        *,
        state: NinefoldRunState,
    ) -> ForgeEvidenceProcessingResult:
        """Record evidence for every Forge result that has not already been evidenced."""
        current = state
        records: list[ForgeEvidenceRecord] = []

        for result in state.forge_results.results:
            if self._has_existing_evidence_for_result(state=current, result=result):
                continue

            processed = self.record_result_evidence(state=current, result=result)
            current = processed.state
            records.extend(processed.evidence_records)

        return ForgeEvidenceProcessingResult(
            state=current,
            evidence_records=tuple(records),
        )

    def _summary_for_result(self, result: ForgeResultRecord) -> str:
        """Return a receipt-grade evidence summary for a Forge result."""
        if result.observed_output is not None:
            return f"Forge result {result.status.value}: {result.summary} Output: {result.observed_output}"

        if result.failure_reason is not None:
            return f"Forge result {result.status.value}: {result.summary} Reason: {result.failure_reason}"

        if result.boundary_note is not None:
            return f"Forge result {result.status.value}: {result.summary} Boundary: {result.boundary_note}"

        return f"Forge result {result.status.value}: {result.summary}"

    def _has_existing_evidence_for_result(
        self,
        *,
        state: NinefoldRunState,
        result: ForgeResultRecord,
    ) -> bool:
        """Return whether evidence already references the Forge result summary."""
        expected_summary = self._summary_for_result(result)
        return any(
            evidence.produced_by is AgentRole.FORGE and evidence.summary == expected_summary
            for evidence in state.evidence.records
        )
