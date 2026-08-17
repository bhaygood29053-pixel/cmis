"""Fail-closed contract for an independently observed total X1 token-account count.

This module deliberately does not perform an RPC scan. It validates evidence from a
future bounded read-only collector before that evidence can enter the holder-count
cross-check. A partial page, truncated provider result, largest-account list, or
unverified mint filter must never be relabeled as total coverage.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CHAIN = "x1"
FACT_TYPE = "total_token_account_count"


def _text(value: Any) -> str:
    return str(value or "").strip()


def validate_total_token_account_observation(observation: Any, *, expected_mint: Any) -> dict[str, Any]:
    """Validate a claimed complete token-account population observation.

    The caller must supply evidence that the transport verified the exact mint filter,
    exhausted all result pages/range partitions, detected no truncation, and counted
    token accounts rather than wallets/beneficial owners. This validator never infers
    those properties from a count or method name.
    """
    mint = _text(expected_mint)
    if not mint:
        raise ValueError("expected_mint must not be empty")
    if not isinstance(observation, Mapping):
        return _reject(mint, "observation_not_mapping")

    if _text(observation.get("chain")).lower() != CHAIN:
        return _reject(mint, "wrong_chain")
    source = _text(observation.get("source"))
    if not source:
        return _reject(mint, "source_missing")
    if _text(observation.get("mint")) != mint:
        return _reject(mint, "mint_mismatch", source=source)
    if _text(observation.get("fact_type")) != FACT_TYPE:
        return _reject(mint, "fact_type_mismatch", source=source)
    if _text(observation.get("counted_entity")) != "token_accounts":
        return _reject(mint, "counted_entity_not_token_accounts", source=source)
    if _text(observation.get("coverage")) != "total":
        return _reject(mint, "coverage_not_total", source=source)

    count = observation.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return _reject(mint, "count_invalid", source=source)

    required_true = (
        "mint_identity_verified",
        "mint_filter_verified",
        "enumeration_complete",
        "truncation_absent_verified",
        "token_account_semantics_verified",
    )
    for field in required_true:
        if observation.get(field) is not True:
            return _reject(mint, f"{field}_required", source=source)

    method = _text(observation.get("method"))
    if method == "getTokenLargestAccounts":
        return _reject(mint, "largest_accounts_not_total_coverage", source=source)

    return {
        "chain": CHAIN,
        "source": source,
        "method": method or None,
        "fact_type": FACT_TYPE,
        "mint": mint,
        "counted_entity": "token_accounts",
        "coverage": "total",
        "count": count,
        "mint_identity_verified": True,
        "coverage_verified": True,
        "token_account_semantics_verified": True,
        "verification_status": "verified_total_token_account_observation",
        "cmis_promotable": False,
        "rejection_reasons": [],
    }


def _reject(mint: str, reason: str, *, source: str | None = None) -> dict[str, Any]:
    return {
        "chain": CHAIN,
        "source": source,
        "fact_type": FACT_TYPE,
        "mint": mint,
        "counted_entity": "token_accounts",
        "coverage": "unverified",
        "count": None,
        "mint_identity_verified": False,
        "coverage_verified": False,
        "token_account_semantics_verified": False,
        "verification_status": "insufficient_evidence",
        "cmis_promotable": False,
        "rejection_reasons": [reason],
    }


__all__ = ["CHAIN", "FACT_TYPE", "validate_total_token_account_observation"]
