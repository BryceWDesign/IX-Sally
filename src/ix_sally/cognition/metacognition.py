"""Bounded self-modeling and human-authorized improvement proposals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class ImprovementStatus(StrEnum):
    """Authority state of one proposed system improvement."""

    PROPOSED = "proposed"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    VALIDATED = "validated"
    REVERTED = "reverted"


@dataclass(frozen=True, slots=True)
class CapabilityMeasure:
    """One measured capability value with evidence and declared limits."""

    capability_id: CanonicalKey
    score: float
    evidence_digests: tuple[DigestRecord, ...]
    limitation: str

    @classmethod
    def create(
        cls,
        *,
        capability_id: str,
        score: float,
        evidence_digests: Iterable[DigestRecord],
        limitation: str,
    ) -> CapabilityMeasure:
        """Create a bounded capability measure."""
        if not 0.0 <= score <= 1.0:
            raise FoundationError("capability score must be between 0 and 1")
        evidence = tuple(evidence_digests)
        if not evidence:
            raise FoundationError("capability measure requires evidence")
        for digest in evidence:
            digest.require_algorithm("sha256")
        return cls(
            capability_id=CanonicalKey.from_text(
                capability_id,
                field_name="capability_id",
            ),
            score=score,
            evidence_digests=evidence,
            limitation=require_text(limitation, field_name="limitation"),
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical capability-measure payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        return {
            "capability_id": self.capability_id.value,
            "score": self.score,
            "evidence_digests": evidence,
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class SelfModel:
    """Evidence-bound self-description that cannot certify its own competence."""

    measures: tuple[CapabilityMeasure, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate capability identities."""
        identifiers = [measure.capability_id.value for measure in self.measures]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("self model contains duplicate capability measures")

    def update(self, measure: CapabilityMeasure) -> SelfModel:
        """Replace or append one measured capability."""
        retained = tuple(
            existing for existing in self.measures
            if existing.capability_id != measure.capability_id
        )
        return SelfModel(
            tuple(
                sorted(
                    (*retained, measure),
                    key=lambda item: item.capability_id.value,
                )
            )
        )

    def weakest(self) -> CapabilityMeasure | None:
        """Return the weakest measured capability, if any."""
        if not self.measures:
            return None
        return min(self.measures, key=lambda item: (item.score, item.capability_id.value))

    def to_payload(self) -> JsonObject:
        """Return a canonical self-model payload."""
        measures: JsonArray = [measure.to_payload() for measure in self.measures]
        return {"measure_count": len(self.measures), "measures": measures}

    def digest(self) -> DigestRecord:
        """Return a deterministic self-model identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ImprovementProposal:
    """One bounded change proposal that cannot authorize or apply itself."""

    proposal_id: CanonicalKey
    target_capability: CanonicalKey
    description: str
    expected_benefit: float
    regression_risk: float
    status: ImprovementStatus
    evidence_digests: tuple[DigestRecord, ...]
    human_decision_digest: DigestRecord | None = None

    @classmethod
    def create(
        cls,
        *,
        proposal_id: str,
        target_capability: str,
        description: str,
        expected_benefit: float,
        regression_risk: float,
        evidence_digests: Iterable[DigestRecord],
        status: ImprovementStatus = ImprovementStatus.PROPOSED,
        human_decision_digest: DigestRecord | None = None,
    ) -> ImprovementProposal:
        """Create a proposal and enforce its human authority transition."""
        for name, value in {
            "expected_benefit": expected_benefit,
            "regression_risk": regression_risk,
        }.items():
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"improvement {name} must be between 0 and 1")
        evidence = tuple(evidence_digests)
        if not evidence:
            raise FoundationError("improvement proposal requires evidence")
        for digest in evidence:
            digest.require_algorithm("sha256")
        if human_decision_digest is not None:
            human_decision_digest.require_algorithm("sha256")
        if status is not ImprovementStatus.PROPOSED and human_decision_digest is None:
            raise FoundationError(
                "non-proposed improvement status requires a human decision digest"
            )
        return cls(
            proposal_id=CanonicalKey.from_text(proposal_id, field_name="proposal_id"),
            target_capability=CanonicalKey.from_text(
                target_capability,
                field_name="target_capability",
            ),
            description=require_text(description, field_name="description"),
            expected_benefit=expected_benefit,
            regression_risk=regression_risk,
            status=status,
            evidence_digests=evidence,
            human_decision_digest=human_decision_digest,
        )

    def with_human_decision(
        self,
        *,
        approved: bool,
        decision_digest: DigestRecord,
    ) -> ImprovementProposal:
        """Return an explicitly human-approved or human-rejected proposal."""
        return ImprovementProposal.create(
            proposal_id=self.proposal_id.value,
            target_capability=self.target_capability.value,
            description=self.description,
            expected_benefit=self.expected_benefit,
            regression_risk=self.regression_risk,
            evidence_digests=self.evidence_digests,
            status=(
                ImprovementStatus.HUMAN_APPROVED
                if approved
                else ImprovementStatus.HUMAN_REJECTED
            ),
            human_decision_digest=decision_digest,
        )

    def may_enter_validation(self) -> bool:
        """Return whether controlled validation may begin."""
        return self.status is ImprovementStatus.HUMAN_APPROVED

    def to_payload(self) -> JsonObject:
        """Return a canonical improvement-proposal payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        human_decision: JsonObject | None = None
        if self.human_decision_digest is not None:
            human_decision = {
                "algorithm": self.human_decision_digest.algorithm,
                "value": self.human_decision_digest.value,
            }
        return {
            "proposal_id": self.proposal_id.value,
            "target_capability": self.target_capability.value,
            "description": self.description,
            "expected_benefit": self.expected_benefit,
            "regression_risk": self.regression_risk,
            "status": self.status.value,
            "evidence_digests": evidence,
            "human_decision_digest": human_decision,
            "may_enter_validation": self.may_enter_validation(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic proposal identity."""
        return DigestRecord.from_payload(self.to_payload())
