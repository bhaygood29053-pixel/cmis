"""Accepted Oracle V2 timestamp-unit promotion policy.

This module records the explicit operator-approved policy used to evaluate the
accepted Oracle V2 historical timestamp evidence. The values are intentionally
evidence-bound and are not upstream guarantees or reusable defaults for other
providers.
"""

from __future__ import annotations

from .oracle_v2_timestamp_governance import (
    TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW,
    normalize_oracle_v2_timestamp_promotion_policy,
)


VERSION = "1.0"

ACCEPTED_EVIDENCE_RUN_ID = 33037942117
ACCEPTED_EVIDENCE_ARTIFACT_ID = 9632727323
ACCEPTED_EVIDENCE_ARTIFACT_SHA256 = (
    "7dd0c340490aaf738299a0900722cbd0d515b2062038de30585f99359c2e90e0"
)
ACCEPTED_EVIDENCE_HEAD_SHA = "bbb6f8e7c69cb41e3f966f2d791ad0c6c01b8e90"
ACCEPTED_MAX_OBSERVED_DIFFERENCE_MS = 1604
ACCEPTED_SAMPLE_COUNT = 25
ACCEPTED_DISTINCT_RELAY_COUNT = 5


def accepted_oracle_v2_timestamp_promotion_policy():
    """Return the explicit operator-approved timestamp-unit policy."""
    policy = {
        "max_difference_ms": ACCEPTED_MAX_OBSERVED_DIFFERENCE_MS,
        "max_difference_provenance": (
            "Issue #293 operator-approved evidence-bound ceiling equal to the "
            "maximum raw candidate Unix-ms difference observed in accepted "
            f"live run {ACCEPTED_EVIDENCE_RUN_ID} / artifact "
            f"{ACCEPTED_EVIDENCE_ARTIFACT_ID}; not an upstream guarantee."
        ),
        "minimum_sample_count": ACCEPTED_SAMPLE_COUNT,
        "minimum_sample_count_provenance": (
            "Issue #293 operator approval preserves the complete accepted "
            f"{ACCEPTED_SAMPLE_COUNT}-sample bounded evidence set rather than "
            "weakening sample sufficiency."
        ),
        "minimum_distinct_relay_count": ACCEPTED_DISTINCT_RELAY_COUNT,
        "minimum_distinct_relay_count_provenance": (
            "Issue #293 operator approval requires all five Oracle V2 relay "
            "slots represented in the accepted evidence window."
        ),
        "temporal_coverage_mode": TEMPORAL_MODE_SINGLE_BOUNDED_WINDOW,
        "minimum_evidence_span_ms": None,
        "temporal_coverage_provenance": (
            "Issue #293 explicit operator acceptance that one bounded "
            "historical transaction window is sufficient for timestamp-unit "
            "semantics only; this does not establish freshness."
        ),
        "require_deployed_binary_equivalence": False,
        "binary_equivalence_requirement_provenance": (
            "Issue #293 explicit operator decision that exact deployed "
            "transaction-shape, Ed25519 signature/key/order binding, and X1 "
            "block-time behavioral evidence are sufficient for timestamp-unit "
            "semantics without a separate deployed-binary/source-equivalence "
            "proof. The binary-equivalence fact remains unverified."
        ),
    }
    normalized = normalize_oracle_v2_timestamp_promotion_policy(policy)
    if not normalized["policy_complete"]:
        raise RuntimeError(
            "accepted Oracle V2 timestamp promotion policy is incomplete"
        )
    return normalized


__all__ = [
    "ACCEPTED_DISTINCT_RELAY_COUNT",
    "ACCEPTED_EVIDENCE_ARTIFACT_ID",
    "ACCEPTED_EVIDENCE_ARTIFACT_SHA256",
    "ACCEPTED_EVIDENCE_HEAD_SHA",
    "ACCEPTED_EVIDENCE_RUN_ID",
    "ACCEPTED_MAX_OBSERVED_DIFFERENCE_MS",
    "ACCEPTED_SAMPLE_COUNT",
    "VERSION",
    "accepted_oracle_v2_timestamp_promotion_policy",
]
