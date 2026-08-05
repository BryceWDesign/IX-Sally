"""Active multi-layer memory tests."""

from __future__ import annotations

import pytest
from ix_sally.cognition import (
    ActiveMemoryEntry,
    ActiveMemoryStatus,
    ActiveMemoryStore,
    MemoryLayer,
)
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _verified(identifier: str, content: str, sequence: int) -> ActiveMemoryEntry:
    return ActiveMemoryEntry.create(
        memory_id=identifier,
        layer=MemoryLayer.EPISODIC,
        content=content,
        confidence=0.9,
        status=ActiveMemoryStatus.VERIFIED,
        sequence=sequence,
        evidence_digests=(DigestRecord.from_payload({"id": identifier}),),
        tags=("test",),
    )


def test_verified_memory_requires_evidence() -> None:
    """A memory cannot become verified through status assignment alone."""
    with pytest.raises(FoundationError, match="requires evidence"):
        ActiveMemoryEntry.create(
            memory_id="unsupported",
            layer=MemoryLayer.SEMANTIC,
            content="Unsupported memory.",
            confidence=1.0,
            status=ActiveMemoryStatus.VERIFIED,
            sequence=1,
        )


def test_truth_only_retrieval_excludes_candidates() -> None:
    """Truth retrieval must omit unverified candidates even when lexical match is high."""
    verified = _verified("verified-blue", "The sky appears blue during daytime.", 1)
    candidate = ActiveMemoryEntry.create(
        memory_id="candidate-blue",
        layer=MemoryLayer.SEMANTIC,
        content="The sky is always blue in every condition.",
        confidence=1.0,
        status=ActiveMemoryStatus.CANDIDATE,
        sequence=2,
    )
    store = ActiveMemoryStore((verified, candidate))

    results = store.retrieve("sky blue", truth_only=True)

    assert tuple(result.entry.memory_id.value for result in results) == (
        "verified-blue",
    )


def test_retrieval_order_is_deterministic() -> None:
    """Equivalent stores must rank retrieval results identically."""
    first = _verified("first", "red blue green", 1)
    second = _verified("second", "red blue", 2)
    store = ActiveMemoryStore((first, second))

    one = store.retrieve("red blue", limit=2)
    two = store.retrieve("red blue", limit=2)

    assert one == two
    assert one[0].entry.memory_id.value == "second"


def test_memory_replacement_requires_later_sequence() -> None:
    """Memory history must not move backward or overwrite at the same sequence."""
    store = ActiveMemoryStore((_verified("entry", "Original.", 3),))
    replacement = _verified("entry", "Replacement.", 3)

    with pytest.raises(FoundationError, match="sequence must increase"):
        store.replace(replacement)


def test_consolidation_requires_verified_sources() -> None:
    """Semantic consolidation must not launder candidate memory into truth."""
    candidate = ActiveMemoryEntry.create(
        memory_id="candidate",
        layer=MemoryLayer.EPISODIC,
        content="Candidate episode.",
        confidence=0.8,
        status=ActiveMemoryStatus.CANDIDATE,
        sequence=1,
    )
    store = ActiveMemoryStore((candidate,))

    with pytest.raises(FoundationError, match="verified source"):
        store.consolidate(
            memory_id="semantic",
            source_ids=("candidate",),
            content="Consolidated claim.",
            evidence_digests=(DigestRecord.from_payload({"source": "candidate"}),),
            confidence=0.8,
        )


def test_consolidation_creates_verified_semantic_memory() -> None:
    """Verified source episodes may produce a provenance-linked semantic entry."""
    store = ActiveMemoryStore(
        (
            _verified("episode-one", "The test passed once.", 1),
            _verified("episode-two", "The test passed again.", 2),
        )
    )
    updated = store.consolidate(
        memory_id="repeated-success",
        source_ids=("episode-one", "episode-two"),
        content="The test passed in two observed episodes.",
        evidence_digests=(DigestRecord.from_payload({"review": "accepted"}),),
        confidence=0.9,
    )

    consolidated = updated.require("repeated-success")
    assert consolidated.layer is MemoryLayer.SEMANTIC
    assert consolidated.status is ActiveMemoryStatus.VERIFIED
    assert tuple(source.value for source in consolidated.source_ids) == (
        "episode-one",
        "episode-two",
    )
