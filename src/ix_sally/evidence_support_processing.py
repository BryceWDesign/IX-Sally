"""Evidence support processing flow for IX-Sally claim grounding."""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_sally.claims import ClaimRecord
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.evidence_support import EvidenceSupportFinding, VerityEvidenceSupportReview
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class EvidenceSupportProcessingResult:
    """Result of reviewing and recording one claim support finding."""

    state: NinefoldRunState
    claim: ClaimRecord
    finding: EvidenceSupportFinding

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible support processing result."""
        return {
            "state_digest": self.state.digest().value,
            "claim_digest": self.claim.digest().value,
            "finding_digest": self.finding.digest().value,
            "finding_status": self.finding.status.value,
            "supports_claim": self.finding.supports_claim(),
            "requires_human_review": self.finding.requires_human_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this support processing result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class EvidenceSupportBatchProcessingResult:
    """Result of reviewing and recording all pending claim support findings."""

    state: NinefoldRunState
    processed: tuple[EvidenceSupportProcessingResult, ...]

    def processed_count(self) -> int:
        """Return how many claims were reviewed."""
        return len(self.processed)

    def supported_count(self) -> int:
        """Return how many reviewed claims were supported."""
        return sum(1 for result in self.processed if result.finding.supports_claim())

    def human_review_count(self) -> int:
        """Return how many reviewed claims require human review."""
        return sum(1 for result in self.processed if result.finding.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible support batch result."""
        processed_payload: JsonArray = []
        for result in self.processed:
            processed_payload.append(result.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "processed_count": self.processed_count(),
            "supported_count": self.supported_count(),
            "human_review_count": self.human_review_count(),
            "processed": processed_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this support batch result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class EvidenceSupportProcessor:
    """Runs IX-Verity support reviews and records findings into run state."""

    recorder: StateRecorder
    reviewer: VerityEvidenceSupportReview = field(default_factory=VerityEvidenceSupportReview)

    def process_claim(
        self,
        *,
        state: NinefoldRunState,
        claim: ClaimRecord,
    ) -> EvidenceSupportProcessingResult:
        """Review one claim against current evidence and record the support finding."""
        try:
            existing = state.claims.require_claim(claim.claim_id.value)
        except FoundationError as error:
            if state.claims.claims:
                raise FoundationError("claim does not match state ledger") from error
            raise

        if existing != claim:
            raise FoundationError("claim does not match state ledger")

        if self._claim_already_reviewed(state=state, claim=claim):
            raise FoundationError("claim already has an evidence support finding")

        finding = self.reviewer.review_claim(
            claim=claim,
            evidence_records=state.evidence.records,
        )
        updated = self.recorder.record_evidence_support_finding(state, finding)

        return EvidenceSupportProcessingResult(
            state=updated,
            claim=claim,
            finding=finding,
        )

    def process_all_unreviewed(
        self,
        *,
        state: NinefoldRunState,
    ) -> EvidenceSupportBatchProcessingResult:
        """Review every claim that does not already have an evidence support finding."""
        current = state
        processed: list[EvidenceSupportProcessingResult] = []

        for claim in state.claims.claims:
            if self._claim_already_reviewed(state=current, claim=claim):
                continue

            result = self.process_claim(state=current, claim=claim)
            current = result.state
            processed.append(result)

        return EvidenceSupportBatchProcessingResult(
            state=current,
            processed=tuple(processed),
        )

    def _claim_already_reviewed(
        self,
        *,
        state: NinefoldRunState,
        claim: ClaimRecord,
    ) -> bool:
        """Return whether a support finding already references this claim digest."""
        claim_digest = claim.digest()
        return any(
            finding.claim_digest == claim_digest for finding in state.evidence_support.findings
        )
