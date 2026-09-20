"""Epistemic authority envelope for bounding proposal strength under uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.epistemic_pressure import EpistemicPressure


class ProposalScope(StrEnum):
    INFORMATION_GATHERING_ONLY = "information-gathering-only"
    REVERSIBLE_EXPERIMENT = "reversible-experiment"
    BOUNDED_ACTION_PROPOSAL = "bounded-action-proposal"


@dataclass(frozen=True, slots=True)
class AuthorityEnvelope:
    scope: ProposalScope
    reason: str
    human_authority_required: bool = True


class EpistemicAuthorityEnvelope:
    """Shrink what Sally may propose as uncertainty and contradiction increase."""

    def evaluate(
        self,
        pressure: EpistemicPressure,
        *,
        perception_quorum_satisfied: bool,
    ) -> AuthorityEnvelope:
        if not perception_quorum_satisfied or pressure.maximum >= 0.60:
            return AuthorityEnvelope(
                ProposalScope.INFORMATION_GATHERING_ONLY,
                "uncertainty or perception disagreement is too high for an action proposal",
            )
        if pressure.maximum >= 0.25:
            return AuthorityEnvelope(
                ProposalScope.REVERSIBLE_EXPERIMENT,
                "remaining epistemic pressure permits only reversible experimentation",
            )
        return AuthorityEnvelope(
            ProposalScope.BOUNDED_ACTION_PROPOSAL,
            "epistemic pressure is low enough to form a bounded proposal for human governance",
        )
