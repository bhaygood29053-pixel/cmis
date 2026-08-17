"""Transport-free Solana total-supply cross-source verification.

Compares canonical Solana RPC total supply with Helius DAS indexed supply after
both source contracts have established the same base-unit semantics. Callers
must supply the maximum acceptable index-slot lag explicitly; there is no hidden
default.

A stale indexed source cannot manufacture a conflict: value disagreement outside
the accepted slot window remains INSUFFICIENT_EVIDENCE. Even agreement is not
CMIS-promotable here because absolute/wall-clock freshness and service promotion
remain separate deterministic decisions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE

VERSION = "1.0"
CHAIN = "solana"
RPC_SOURCE = "solana_rpc"
HELIUS_SOURCE = "helius_das"
TOKEN_BASE_UNITS = "TOKEN_BASE_UNITS"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _raw_amount(value: Any) -> str | None:
    if not isinstance(value, str) or not value or not value.isdigit():
        return None
    return value.lstrip("0") or "0"


def _u8(value: Any) -> int | None:
    parsed = _nonnegative_int(value)
    if parsed is None or parsed > 255:
        return None
    return parsed


def _lag(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("max_index_slot_lag must be an explicit non-negative integer")
    return value


def _insufficient(*reasons: str) -> dict[str, Any]:
    return {
        "service": "solana_supply_crosscheck",
        "version": VERSION,
        "chain": CHAIN,
        "status": INSUFFICIENT_EVIDENCE,
        "cmis_promotable": False,
        "identity_verified": False,
        "semantics_verified": False,
        "relative_recency_verified": False,
        "freshness_verified": False,
        "rejection_reasons": list(dict.fromkeys(reason for reason in reasons if reason)),
    }


def verify_rpc_vs_helius_supply(
    rpc_supply: Mapping[str, Any],
    helius_asset: Mapping[str, Any],
    *,
    max_index_slot_lag: int,
) -> dict[str, Any]:
    """Cross-check canonical RPC supply against Helius indexed supply.

    ``max_index_slot_lag`` is mandatory. It constrains how far Helius'
    ``last_indexed_slot`` may be from the canonical RPC observation slot before
    supply differences become temporally ambiguous.

    Decimals are treated as identity/semantic structure rather than a volatile
    market field: a decimals mismatch is always a conflict once both source
    contracts pass validation.
    """

    if not isinstance(rpc_supply, Mapping) or not isinstance(helius_asset, Mapping):
        raise TypeError("supply cross-check inputs must be mappings")
    allowed_lag = _lag(max_index_slot_lag)

    reasons: list[str] = []
    if rpc_supply.get("chain") != CHAIN or helius_asset.get("chain") != CHAIN:
        reasons.append("wrong_chain")
    if rpc_supply.get("source") != RPC_SOURCE:
        reasons.append("rpc_source_mismatch")
    if helius_asset.get("source") != HELIUS_SOURCE:
        reasons.append("helius_source_mismatch")

    rpc_mint = _text(rpc_supply.get("mint"))
    helius_mint = _text(helius_asset.get("mint"))
    if rpc_mint is None or helius_mint is None:
        reasons.append("mint_missing")
    elif rpc_mint != helius_mint:
        reasons.append("mint_mismatch")

    if rpc_supply.get("method") != "getTokenSupply":
        reasons.append("rpc_method_mismatch")
    if rpc_supply.get("supply_verified") is not True:
        reasons.append("rpc_supply_unverified")
    if rpc_supply.get("coverage") != "total_token_supply":
        reasons.append("rpc_supply_coverage_unverified")
    if helius_asset.get("asset_available") is not True:
        reasons.append("helius_asset_unavailable")
    if helius_asset.get("identity_verified") is not True:
        reasons.append("helius_identity_unverified")
    if helius_asset.get("supply_semantics_verified") is not True:
        reasons.append("helius_supply_semantics_unverified")
    if helius_asset.get("supply_unit") != TOKEN_BASE_UNITS:
        reasons.append("helius_supply_unit_mismatch")

    rpc_amount = _raw_amount(rpc_supply.get("amount_raw"))
    rpc_decimals = _u8(rpc_supply.get("decimals"))
    rpc_slot = _nonnegative_int(rpc_supply.get("context_slot"))
    helius_supply = _nonnegative_int(helius_asset.get("indexed_supply_candidate"))
    helius_decimals = _u8(helius_asset.get("decimals"))
    helius_slot = _nonnegative_int(helius_asset.get("last_indexed_slot"))

    if rpc_amount is None:
        reasons.append("rpc_amount_invalid")
    if rpc_decimals is None:
        reasons.append("rpc_decimals_invalid")
    if rpc_slot is None:
        reasons.append("rpc_slot_invalid")
    if helius_supply is None:
        reasons.append("helius_supply_invalid")
    if helius_decimals is None:
        reasons.append("helius_decimals_invalid")
    if helius_slot is None:
        reasons.append("helius_slot_invalid")

    if reasons:
        result = _insufficient(*reasons)
        result["max_index_slot_lag"] = allowed_lag
        return result

    assert rpc_mint is not None
    assert rpc_amount is not None and rpc_decimals is not None and rpc_slot is not None
    assert helius_supply is not None and helius_decimals is not None and helius_slot is not None

    slot_gap = abs(rpc_slot - helius_slot)
    relative_recency_verified = slot_gap <= allowed_lag
    decimals_match = rpc_decimals == helius_decimals
    supply_match = rpc_amount == str(helius_supply)

    if not decimals_match:
        status = CONFLICT
        decision_reason = "decimals_conflict"
    elif not relative_recency_verified:
        status = INSUFFICIENT_EVIDENCE
        decision_reason = "index_slot_lag_exceeds_limit"
    elif supply_match:
        status = AGREEMENT
        decision_reason = "independent_supply_agreement"
    else:
        status = CONFLICT
        decision_reason = "supply_conflict_within_slot_window"

    warnings: list[str] = ["absolute_freshness_not_verified"]
    if not relative_recency_verified:
        warnings.append("helius_index_slot_outside_configured_window")

    return {
        "service": "solana_supply_crosscheck",
        "version": VERSION,
        "chain": CHAIN,
        "status": status,
        "cmis_promotable": False,
        "mint": rpc_mint,
        "fact_type": "token_total_supply_base_units",
        "unit": TOKEN_BASE_UNITS,
        "identity_verified": True,
        "semantics_verified": True,
        "relative_recency_verified": relative_recency_verified,
        "freshness_verified": False,
        "max_index_slot_lag": allowed_lag,
        "rpc_context_slot": rpc_slot,
        "helius_last_indexed_slot": helius_slot,
        "slot_gap": slot_gap,
        "rpc_supply": rpc_amount,
        "helius_supply": str(helius_supply),
        "rpc_decimals": rpc_decimals,
        "helius_decimals": helius_decimals,
        "supply_match": supply_match,
        "decimals_match": decimals_match,
        "independent_source_count": 2,
        "decision_reason": decision_reason,
        "rejection_reasons": [] if status != INSUFFICIENT_EVIDENCE else [decision_reason],
        "warnings": warnings,
    }


__all__ = [
    "CHAIN",
    "HELIUS_SOURCE",
    "RPC_SOURCE",
    "TOKEN_BASE_UNITS",
    "VERSION",
    "verify_rpc_vs_helius_supply",
]
