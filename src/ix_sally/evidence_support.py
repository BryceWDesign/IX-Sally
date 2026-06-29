"""Verity evidence support review for IX-Sally claim grounding."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimRecord
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.evidence import EvidenceRecord, EvidenceStatus
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class EvidenceSupportStatus(StrEnum):
    """Support status assigned by IX-Verity to a claim."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class EvidenceSupportFinding:
    """One IX-Verity support finding over a claim and evidence set."""

    finding_id: CanonicalKey
    cycle: int
    claim_digest: DigestRecord
    reviewed_by: AgentRole
    status: EvidenceSupportStatus
    rationale: str
    evidence_digests: tuple[DigestRecord, ...]
    contradiction_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        claim_digest: DigestRecord,
        status: EvidenceSupportStatus,
        rationale: str,
        evidence_digests: Iterable[DigestRecord] = (),
        reviewed_by: AgentRole = AgentRole.VERITY,
        contradiction_note: str | None = None,
        finding_id: CanonicalKey | None = None,
    ) -> EvidenceSupportFinding:
        """Create a normalized evidence support finding."""
        if cycle < 0:
            raise FoundationError("evidence support finding cycle must not be negative")

        claim_digest.require_algorithm("sha256")
        normalized_evidence = tuple(evidence_digests)
        for evidence_digest in normalized_evidence:
            evidence_digest.require_algorithm("sha256")

        normalized_rationale = require_text(rationale, field_name="rationale")
        normalized_contradiction = require_optional_text(
            contradiction_note,
            field_name="contradiction_note",
        )

        if reviewed_by is not AgentRole.VERITY:
            raise FoundationError("evidence support findings must be reviewed by IX-Verity")

        if status is EvidenceSupportStatus.CONTRADICTED and normalized_contradiction is None:
            raise FoundationError("contradicted evidence support findings require a contradiction note")

        if status is EvidenceSupportStatus.SUPPORTED and not normalized_evidence:
            raise FoundationError("supported evidence support findings require evidence digests")

        return cls(
            finding_id=finding_id
            or CanonicalKey.from_text(
                f"{cycle}-{reviewed_by.value}-{status.value}-{claim_digest.value[:12]}",
                field_name="finding_id",
            ),
            cycle=cycle,
            claim_digest=claim_digest,
            reviewed_by=reviewed_by,
            status=status,
            rationale=normalized_rationale,
            evidence_digests=normalized_evidence,
            contradiction_note=normalized_contradiction,
        )

    def supports_claim(self) -> bool:
        """Return whether this finding supports the claim."""
        return self.status is EvidenceSupportStatus.SUPPORTED

    def requires_human_review(self) -> bool:
        """Return whether this finding requires human review before relying on the claim."""
        return self.status in {
            EvidenceSupportStatus.PARTIAL,
            EvidenceSupportStatus.UNSUPPORTED,
            EvidenceSupportStatus.CONTRADICTED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible finding representation."""
        evidence_payload: JsonArray = []
        for evidence_digest in self.evidence_digests:
            evidence_payload.append(
                {
                    "algorithm": evidence_digest.algorithm,
                    "value": evidence_digest.value,
                }
            )

        return {
            "finding_id": self.finding_id.value,
            "cycle": self.cycle,
            "claim_digest": {
                "algorithm": self.claim_digest.algorithm,
                "value": self.claim_digest.value,
            },
            "reviewed_by": self.reviewed_by.value,
            "status": self.status.value,
            "rationale": self.rationale,
            "evidence_digests": evidence_payload,
            "contradiction_note": self.contradiction_note,
            "supports_claim": self.supports_claim(),
            "requires_human_review": self.requires_human_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this evidence support finding."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class EvidenceSupportLedger:
    """Immutable ledger of IX-Verity evidence support findings."""

    findings: tuple[EvidenceSupportFinding, ...]

    @classmethod
    def create(cls, findings: Iterable[EvidenceSupportFinding]) -> EvidenceSupportLedger:
        """Create a support ledger and reject duplicate finding identifiers."""
        normalized = tuple(findings)
        seen: set[str] = set()

        for finding in normalized:
            if finding.finding_id.value in seen:
                raise FoundationError(f"duplicate evidence support finding id: {finding.finding_id.value}")
            seen.add(finding.finding_id.value)

        return cls(findings=normalized)

    def append(self, finding: EvidenceSupportFinding) -> EvidenceSupportLedger:
        """Return a new ledger with an appended evidence support finding."""
        return EvidenceSupportLedger.create((*self.findings, finding))

    def supported_findings(self) -> tuple[EvidenceSupportFinding, ...]:
        """Return findings that fully support their claims."""
        return tuple(finding for finding in self.findings if finding.supports_claim())

    def human_review_findings(self) -> tuple[EvidenceSupportFinding, ...]:
        """Return findings requiring human review."""
        return tuple(finding for finding in self.findings if finding.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible support ledger representation."""
        finding_payload: JsonArray = []
        for finding in self.findings:
            finding_payload.append(finding.to_payload())

        return {
            "findings": finding_payload,
            "supported_count": len(self.supported_findings()),
            "human_review_count": len(self.human_review_findings()),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this evidence support ledger."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class VerityEvidenceSupportReview:
    """Deterministic IX-Verity review over claims and recorded evidence."""

    def review_claim(
        self,
        *,
        claim: ClaimRecord,
        evidence_records: tuple[EvidenceRecord, ...],
    ) -> EvidenceSupportFinding:
        """Review one claim against recorded evidence summaries."""
        if claim.cycle < 0:
            raise FoundationError("claim cycle must not be negative")

        same_cycle_evidence = tuple(
            evidence
            for evidence in evidence_records
            if evidence.cycle == claim.cycle and evidence.status is EvidenceStatus.RECORDED
        )

        if not same_cycle_evidence:
            return EvidenceSupportFinding.create(
                cycle=claim.cycle,
                claim_digest=claim.digest(),
                status=EvidenceSupportStatus.UNSUPPORTED,
                rationale="No recorded same-cycle evidence supports the claim.",
            )

        claim_terms = self._claim_terms(claim.statement)
        if not claim_terms:
            return EvidenceSupportFinding.create(
                cycle=claim.cycle,
                claim_digest=claim.digest(),
                status=EvidenceSupportStatus.UNSUPPORTED,
                rationale="Claim has no reviewable terms.",
            )

        contradicted = self._contradicting_evidence(
            claim_terms=claim_terms,
            evidence_records=same_cycle_evidence,
        )
        if contradicted:
            return EvidenceSupportFinding.create(
                cycle=claim.cycle,
                claim_digest=claim.digest(),
                status=EvidenceSupportStatus.CONTRADICTED,
                rationale="Recorded evidence contains contradiction language for claim terms.",
                evidence_digests=tuple(evidence.digest() for evidence in contradicted),
                contradiction_note="Evidence contains failed, blocked, denied, contradiction, or unsupported language.",
            )

        supporting = self._supporting_evidence(
            claim_terms=claim_terms,
            evidence_records=same_cycle_evidence,
        )
        if supporting:
            return EvidenceSupportFinding.create(
                cycle=claim.cycle,
                claim_digest=claim.digest(),
                status=EvidenceSupportStatus.SUPPORTED,
                rationale="Recorded same-cycle evidence overlaps with claim terms.",
                evidence_digests=tuple(evidence.digest() for evidence in supporting),
            )

        return EvidenceSupportFinding.create(
            cycle=claim.cycle,
            claim_digest=claim.digest(),
            status=EvidenceSupportStatus.PARTIAL,
            rationale="Evidence exists for the cycle but does not directly support claim terms.",
            evidence_digests=tuple(evidence.digest() for evidence in same_cycle_evidence),
        )

    def review_claims(
        self,
        *,
        claims: tuple[ClaimRecord, ...],
        evidence_records: tuple[EvidenceRecord, ...],
    ) -> EvidenceSupportLedger:
        """Review multiple claims in ledger order."""
        return EvidenceSupportLedger.create(
            self.review_claim(claim=claim, evidence_records=evidence_records)
            for claim in claims
        )

    def _claim_terms(self, statement: str) -> tuple[str, ...]:
        """Return normalized reviewable claim terms."""
        terms = []
        for raw in statement.lower().replace(".", " ").replace(",", " ").split():
            token = raw.strip()
            if len(token) >= 4:
                terms.append(token)

        return tuple(dict.fromkeys(terms))

    def _supporting_evidence(
        self,
        *,
        claim_terms: tuple[str, ...],
        evidence_records: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        """Return evidence that includes at least one claim term."""
        return tuple(
            evidence
            for evidence in evidence_records
            if any(term in evidence.summary.lower() for term in claim_terms)
        )

    def _contradicting_evidence(
        self,
        *,
        claim_terms: tuple[str, ...],
        evidence_records: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        """Return evidence that overlaps claim terms and includes contradiction language."""
        contradiction_terms = (
            "failed",
            "blocked",
            "denied",
            "contradiction",
            "contradicted",
            "unsupported",
        )

        return tuple(
            evidence
            for evidence in evidence_records
            if any(term in evidence.summary.lower() for term in claim_terms)
            and any(term in evidence.summary.lower() for term in contradiction_terms)
        )
