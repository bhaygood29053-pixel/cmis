"""Accepted Oracle V2 timestamp-unit evidence.

This module exposes the narrow verified timestamp-unit fact promoted by
#293/#294. It is reusable by downstream freshness analysis without reasserting
or reconstructing the promotion decision.
"""

from __future__ import annotations

from .oracle_v2_policy import (
    TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
    TIMESTAMP_UNIT_UNIX_MS,
    normalize_timestamp_unit_evidence,
)


VERSION = "1.0"

PROMOTION_ISSUE = 293
PROMOTION_PR = 294
PROMOTION_MERGE_COMMIT = "3345ce9d8498b3024edcb09f795ef3b56fe0330c"
PROMOTION_WORKFLOW_RUN_ID = 33038921907
PROMOTION_ARTIFACT_ID = 9633092384
PROMOTION_ARTIFACT_SHA256 = (
    "32ec5e8d46326900d881da4162177b29b68b829e1ca82337db22f6a5bd94ad07"
)
PROMOTION_POLICY_SHA256 = (
    "0a91fbc4a6d4b8befe728419e661e9eea4ad189a48b746a2ea7f18c5f86d05ab"
)
PROMOTION_EVIDENCE_SHA256 = (
    "984f3208ae17043880407cdc85964e87ee42cee54d50c322ac065d0fb135c135"
)


def accepted_oracle_v2_timestamp_unit_evidence():
    """Return the exact accepted timestamp-unit evidence for policy use."""
    evidence = {
        "timestamp_unit": TIMESTAMP_UNIT_UNIX_MS,
        "method": TIMESTAMP_UNIT_METHOD_X1_BLOCK_TIME,
        "verified": True,
        "provenance": (
            "Oracle V2 timestamp-unit promotion #293/#294; "
            f"merge_commit={PROMOTION_MERGE_COMMIT}; "
            f"workflow_run={PROMOTION_WORKFLOW_RUN_ID}; "
            f"artifact_id={PROMOTION_ARTIFACT_ID}; "
            f"artifact_sha256={PROMOTION_ARTIFACT_SHA256}; "
            f"policy_sha256={PROMOTION_POLICY_SHA256}; "
            f"evidence_sha256={PROMOTION_EVIDENCE_SHA256}"
        ),
        "promotion_issue": PROMOTION_ISSUE,
        "promotion_pr": PROMOTION_PR,
        "promotion_merge_commit": PROMOTION_MERGE_COMMIT,
        "promotion_workflow_run_id": PROMOTION_WORKFLOW_RUN_ID,
        "promotion_artifact_id": PROMOTION_ARTIFACT_ID,
        "promotion_artifact_sha256": PROMOTION_ARTIFACT_SHA256,
        "promotion_policy_sha256": PROMOTION_POLICY_SHA256,
        "promotion_evidence_sha256": PROMOTION_EVIDENCE_SHA256,
        # Scope boundaries preserved from the accepted promotion.
        "freshness_verified": False,
        "price_correctness_verified": False,
        "source_independence_verified": False,
        "current_price_use_authorized": False,
        "cmis_provider_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }

    normalized = normalize_timestamp_unit_evidence(evidence)
    if not normalized["accepted_for_policy"]:
        raise RuntimeError(
            "accepted Oracle V2 timestamp-unit evidence is not policy-eligible"
        )
    return evidence


__all__ = [
    "PROMOTION_ARTIFACT_ID",
    "PROMOTION_ARTIFACT_SHA256",
    "PROMOTION_EVIDENCE_SHA256",
    "PROMOTION_ISSUE",
    "PROMOTION_MERGE_COMMIT",
    "PROMOTION_POLICY_SHA256",
    "PROMOTION_PR",
    "PROMOTION_WORKFLOW_RUN_ID",
    "VERSION",
    "accepted_oracle_v2_timestamp_unit_evidence",
]
