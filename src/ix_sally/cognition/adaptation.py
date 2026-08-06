"""Regression-aware adaptation proposals that cannot approve or apply themselves."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.metacognition import ImprovementProposal, SelfModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class RegressionOutcome(StrEnum):
    """Result of comparing measured capabilities before and after a candidate change."""

    IMPROVED = "improved"
    NEUTRAL = "neutral"
    REGRESSED = "regressed"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class RegressionFinding:
    """One exact capability comparison for a candidate improvement."""

    capability_id: CanonicalKey
    before_score: float | None
    after_score: float | None
    delta: float | None
    outcome: RegressionOutcome

    def to_payload(self) -> JsonObject:
        """Return a canonical regression finding."""
        return {
            "capability_id": self.capability_id.value,
            "before_score": self.before_score,
            "after_score": self.after_score,
            "delta": self.delta,
            "outcome": self.outcome.value,
        }


@dataclass(frozen=True, slots=True)
class RegressionReport:
    """Complete comparison between pre-change and post-change self models."""

    proposal_digest: DigestRecord
    findings: tuple[RegressionFinding, ...]
    permitted_regression: float

    def __post_init__(self) -> None:
        """Require a valid comparison threshold and proposal digest."""
        self.proposal_digest.require_algorithm("sha256")
        if not 0.0 <= self.permitted_regression <= 1.0:
            raise FoundationError("permitted regression must be between 0 and 1")

    def has_regression(self) -> bool:
        """Return whether any measured capability exceeds the allowed score drop."""
        return any(
            finding.delta is not None and finding.delta < -self.permitted_regression
            for finding in self.findings
        )

    def complete(self) -> bool:
        """Return whether every capability exists in both compared models."""
        return all(finding.outcome is not RegressionOutcome.INCOMPLETE for finding in self.findings)

    def may_request_validation(self) -> bool:
        """Return whether evidence permits human review of a validation request."""
        return self.complete() and not self.has_regression()

    def to_payload(self) -> JsonObject:
        """Return a canonical regression report."""
        findings: JsonArray = [finding.to_payload() for finding in self.findings]
        return {
            "proposal_digest": {
                "algorithm": self.proposal_digest.algorithm,
                "value": self.proposal_digest.value,
            },
            "findings": findings,
            "permitted_regression": self.permitted_regression,
            "has_regression": self.has_regression(),
            "complete": self.complete(),
            "may_request_validation": self.may_request_validation(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic report identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AdaptationController:
    """Generate bounded improvement proposals and compare measured outcomes."""

    permitted_regression: float = 0.0

    def __post_init__(self) -> None:
        """Require a valid regression tolerance."""
        if not 0.0 <= self.permitted_regression <= 1.0:
            raise FoundationError("permitted regression must be between 0 and 1")

    def propose_for_weakest(
        self,
        *,
        self_model: SelfModel,
        description: str,
        expected_benefit: float,
        regression_risk: float,
        supporting_evidence: Iterable[DigestRecord],
    ) -> ImprovementProposal:
        """Propose work on the weakest measured capability without self-approval."""
        weakest = self_model.weakest()
        if weakest is None:
            raise FoundationError("cannot propose adaptation without capability measures")
        evidence = tuple(supporting_evidence)
        if not evidence:
            raise FoundationError("adaptation proposal requires supporting evidence")
        seed = DigestRecord.from_payload(
            {
                "self_model": self_model.digest().value,
                "target": weakest.capability_id.value,
                "description": require_text(description, field_name="description"),
                "evidence": [item.value for item in evidence],
            }
        )
        return ImprovementProposal.create(
            proposal_id=f"adaptation-{weakest.capability_id.value}-{seed.value[:16]}",
            target_capability=weakest.capability_id.value,
            description=description,
            expected_benefit=expected_benefit,
            regression_risk=regression_risk,
            evidence_digests=evidence,
        )

    def compare(
        self,
        *,
        proposal: ImprovementProposal,
        before: SelfModel,
        after: SelfModel,
    ) -> RegressionReport:
        """Compare every capability without hiding missing or regressed measures."""
        before_by_id = {item.capability_id: item for item in before.measures}
        after_by_id = {item.capability_id: item for item in after.measures}
        identifiers = tuple(
            sorted(set(before_by_id) | set(after_by_id), key=lambda item: item.value)
        )
        findings = []
        for capability_id in identifiers:
            before_measure = before_by_id.get(capability_id)
            after_measure = after_by_id.get(capability_id)
            if before_measure is None or after_measure is None:
                findings.append(
                    RegressionFinding(
                        capability_id=capability_id,
                        before_score=(before_measure.score if before_measure is not None else None),
                        after_score=(after_measure.score if after_measure is not None else None),
                        delta=None,
                        outcome=RegressionOutcome.INCOMPLETE,
                    )
                )
                continue
            delta = round(after_measure.score - before_measure.score, 12)
            if delta > 0:
                outcome = RegressionOutcome.IMPROVED
            elif delta < -self.permitted_regression:
                outcome = RegressionOutcome.REGRESSED
            else:
                outcome = RegressionOutcome.NEUTRAL
            findings.append(
                RegressionFinding(
                    capability_id=capability_id,
                    before_score=before_measure.score,
                    after_score=after_measure.score,
                    delta=delta,
                    outcome=outcome,
                )
            )
        return RegressionReport(
            proposal_digest=proposal.digest(),
            findings=tuple(findings),
            permitted_regression=self.permitted_regression,
        )
