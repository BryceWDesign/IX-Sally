

from __future__ import annotations

import pytest
from ix_sally.digest import DigestRecord, stable_digest, stable_json
from ix_sally.foundation import FoundationError


def test_stable_json_sorts_keys_and_removes_spacing() -> None:
    payload = {
        "zeta": "last",
        "alpha": {
            "b": 2,
            "a": 1,
        },
    }

    assert stable_json(payload) == '{"alpha":{"a":1,"b":2},"zeta":"last"}'


def test_stable_digest_is_repeatable_for_equivalent_payloads() -> None:
    left = {
        "agent": "verity",
        "claim": "output is not evidence",
        "cycle": 3,
    }
    right = {
        "cycle": 3,
        "claim": "output is not evidence",
        "agent": "verity",
    }

    assert stable_digest(left) == stable_digest(right)


def test_digest_record_uses_sha256() -> None:
    record = DigestRecord.from_payload({"event": "claim_blocked"})

    assert record.algorithm == "sha256"
    assert len(record.value) == 64


def test_digest_record_accepts_expected_algorithm_case_insensitively() -> None:
    record = DigestRecord.from_payload({"event": "claim_blocked"})

    record.require_algorithm("SHA256")


def test_digest_record_rejects_unexpected_algorithm() -> None:
    record = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        record.require_algorithm("sha256")
