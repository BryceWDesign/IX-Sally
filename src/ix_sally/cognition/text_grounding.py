"""Minimal raw-text grounding by outcome-linked token discovery.

This is intentionally not an LLM or general language understanding system.  It provides a
real grounding step from unstructured text strings to empirically useful latent token
features, complementing IX-Sally's numeric signal grounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Iterable
import re

from ix_sally.foundation import FoundationError, require_text

_TOKEN = re.compile(r"[A-Za-z0-9_'-]+")


@dataclass(frozen=True, slots=True)
class TextOutcomeObservation:
    observation_id: str
    text: str
    outcome: bool

    def __post_init__(self) -> None:
        require_text(self.observation_id, field_name="observation_id")
        require_text(self.text, field_name="text")


@dataclass(frozen=True, slots=True)
class GroundedTextFeature:
    token: str
    information_gain: float
    positive_rate_when_present: float
    support: int


class TextOutcomeGrounder:
    """Discover text tokens whose presence reduces uncertainty about an observed outcome."""

    def discover(self, observations: Iterable[TextOutcomeObservation]) -> tuple[GroundedTextFeature, ...]:
        items = tuple(observations)
        if len(items) < 4:
            raise FoundationError("text grounding requires at least four observations")
        base_positive = sum(item.outcome for item in items) / len(items)
        base_entropy = self._entropy(base_positive)
        vocabulary = sorted({token for item in items for token in self._tokens(item.text)})
        features: list[GroundedTextFeature] = []
        for token in vocabulary:
            present = [item for item in items if token in self._tokens(item.text)]
            absent = [item for item in items if token not in self._tokens(item.text)]
            if len(present) < 2 or not absent:
                continue
            p_present = len(present) / len(items)
            pos_present = sum(item.outcome for item in present) / len(present)
            pos_absent = sum(item.outcome for item in absent) / len(absent)
            conditional = p_present * self._entropy(pos_present) + (1 - p_present) * self._entropy(pos_absent)
            gain = max(0.0, base_entropy - conditional)
            if gain > 1e-9:
                features.append(GroundedTextFeature(token, round(gain, 12), pos_present, len(present)))
        return tuple(sorted(features, key=lambda item: (-item.information_gain, -item.support, item.token)))

    @staticmethod
    def _tokens(text: str) -> frozenset[str]:
        return frozenset(match.group(0).lower() for match in _TOKEN.finditer(text))

    @staticmethod
    def _entropy(probability: float) -> float:
        if probability <= 0.0 or probability >= 1.0:
            return 0.0
        return -probability * log(probability, 2) - (1.0 - probability) * log(1.0 - probability, 2)
