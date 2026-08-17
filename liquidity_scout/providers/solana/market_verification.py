"""Transport-free cross-source Solana market verification primitives.

This layer compares already-collected Jupiter Price V3 and DEX Screener pair
observations. It does not fetch data, pick a preferred pair, average prices, or
invent a tolerance. Callers must provide the maximum relative difference
explicitly.

Because the current source contracts do not yet establish a shared observation
time/scope, even numerical agreement remains non-promotable until a separate
freshness/scope rule is proven.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE

VERSION = "1.0"
CHAIN = "solana"
JUPITER_SOURCE = "jupiter_price_v3"
DEXSCREENER_SOURCE = "dexscreener_token_pairs_v1"
USD_PER_TOKEN = "USD_PER_TOKEN"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _positive_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _tolerance(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("max_relative_difference must be supplied explicitly")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("max_relative_difference must be finite numeric data") from exc
    if not parsed.is_finite() or parsed < 0 or parsed > 1:
        raise ValueError("max_relative_difference must be between 0 and 1 inclusive")
    return parsed


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _relative_difference(left: Decimal, right: Decimal) -> Decimal:
    denominator = max(abs(left), abs(right))
    if denominator == 0:  # pragma: no cover - positive prices are required
        return Decimal(0)
    return abs(left - right) / denominator


def _insufficient(*reasons: str) -> dict[str, Any]:
    return {
        "service": "solana_price_crosscheck",
        "version": VERSION,
        "chain": CHAIN,
        "status": INSUFFICIENT_EVIDENCE,
        "cmis_promotable": False,
        "identity_verified": False,
        "semantics_verified": False,
        "freshness_verified": False,
        "observation_scope_verified": False,
        "comparisons": [],
        "rejection_reasons": list(dict.fromkeys(reason for reason in reasons if reason)),
    }


def verify_jupiter_vs_dexscreener_prices(
    jupiter: Mapping[str, Any],
    dexscreener: Mapping[str, Any],
    *,
    max_relative_difference: Any,
) -> dict[str, Any]:
    """Compare one Jupiter token price with all eligible DEX Screener pair prices.

    ``max_relative_difference`` is a unitless fraction in ``[0, 1]``. For
    example ``0.01`` means a maximum 1% symmetric relative difference. There is
    intentionally no default.

    DEX Screener prices are eligible only when the source adapter explicitly
    proved that the requested mint is the pair's base token and therefore the
    subject of ``priceUsd``. Legitimate quote-side pairs are simply ineligible;
    malformed or duplicate source records invalidate the cross-check.
    """

    if not isinstance(jupiter, Mapping) or not isinstance(dexscreener, Mapping):
        raise TypeError("price cross-check inputs must be mappings")
    tolerance = _tolerance(max_relative_difference)

    reasons: list[str] = []
    if jupiter.get("chain") != CHAIN or dexscreener.get("chain") != CHAIN:
        reasons.append("wrong_chain")
    if jupiter.get("source") != JUPITER_SOURCE:
        reasons.append("jupiter_source_mismatch")
    if dexscreener.get("source") != DEXSCREENER_SOURCE:
        reasons.append("dexscreener_source_mismatch")

    jupiter_mint = _text(jupiter.get("mint"))
    dex_mint = _text(dexscreener.get("mint"))
    if jupiter_mint is None or dex_mint is None:
        reasons.append("mint_missing")
    elif jupiter_mint != dex_mint:
        reasons.append("mint_mismatch")

    if jupiter.get("price_available") is not True:
        reasons.append("jupiter_price_unavailable")
    if dexscreener.get("pairs_available") is not True:
        reasons.append("dexscreener_pairs_unavailable")

    jupiter_price = _positive_decimal(jupiter.get("usd_price"))
    if jupiter.get("price_available") is True and jupiter_price is None:
        reasons.append("jupiter_price_invalid")
    if jupiter.get("currency") != "USD":
        reasons.append("jupiter_currency_not_usd")

    pairs = dexscreener.get("pairs")
    if dexscreener.get("pairs_available") is True and not isinstance(pairs, list):
        reasons.append("dexscreener_pairs_invalid")
        pairs = []
    elif not isinstance(pairs, list):
        pairs = []

    if reasons:
        return _insufficient(*reasons)

    assert jupiter_mint is not None and jupiter_price is not None

    comparisons: list[dict[str, Any]] = []
    pair_rejections: list[dict[str, str]] = []
    structural_rejections: list[dict[str, str]] = []
    seen_pairs: set[str] = set()

    for index, pair in enumerate(pairs):
        if not isinstance(pair, Mapping):
            structural_rejections.append({"pair": str(index), "reason": "pair_not_mapping"})
            continue
        pair_address = _text(pair.get("pair_address"))
        if pair_address is None:
            structural_rejections.append({"pair": str(index), "reason": "pair_address_missing"})
            continue
        if pair_address in seen_pairs:
            structural_rejections.append({"pair": pair_address, "reason": "duplicate_pair_address"})
            continue
        seen_pairs.add(pair_address)

        if pair.get("requested_mint_role") != "base":
            pair_rejections.append({"pair": pair_address, "reason": "requested_mint_not_base"})
            continue
        if pair.get("price_is_for_requested_mint") is not True:
            pair_rejections.append({"pair": pair_address, "reason": "price_subject_unverified"})
            continue
        if _text(pair.get("price_subject_address")) != jupiter_mint:
            pair_rejections.append({"pair": pair_address, "reason": "price_subject_mismatch"})
            continue

        dex_price = _positive_decimal(pair.get("price_usd"))
        if dex_price is None:
            pair_rejections.append({"pair": pair_address, "reason": "pair_price_unavailable"})
            continue

        difference = _relative_difference(jupiter_price, dex_price)
        comparisons.append(
            {
                "pair_address": pair_address,
                "dex_id": _text(pair.get("dex_id")),
                "subject_id": jupiter_mint,
                "unit": USD_PER_TOKEN,
                "jupiter_price": _canonical_decimal(jupiter_price),
                "dexscreener_price": _canonical_decimal(dex_price),
                "relative_difference": _canonical_decimal(difference),
                "within_tolerance": difference <= tolerance,
            }
        )

    if structural_rejections:
        result = _insufficient("dexscreener_pair_contract_invalid")
        result["pair_rejections"] = pair_rejections
        result["structural_rejections"] = structural_rejections
        result["mint"] = jupiter_mint
        result["max_relative_difference"] = _canonical_decimal(tolerance)
        return result

    if not comparisons:
        result = _insufficient("no_eligible_dexscreener_base_pair_price")
        result["pair_rejections"] = pair_rejections
        result["structural_rejections"] = []
        result["mint"] = jupiter_mint
        result["max_relative_difference"] = _canonical_decimal(tolerance)
        return result

    status = AGREEMENT if all(item["within_tolerance"] is True for item in comparisons) else CONFLICT

    return {
        "service": "solana_price_crosscheck",
        "version": VERSION,
        "chain": CHAIN,
        "status": status,
        "cmis_promotable": False,
        "mint": jupiter_mint,
        "fact_type": "token_usd_price",
        "unit": USD_PER_TOKEN,
        "max_relative_difference": _canonical_decimal(tolerance),
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": False,
        "observation_scope_verified": False,
        "jupiter_block_id": jupiter.get("block_id"),
        "eligible_pair_count": len(comparisons),
        "comparisons": comparisons,
        "pair_rejections": pair_rejections,
        "structural_rejections": [],
        "rejection_reasons": [],
        "warnings": [
            "shared_observation_scope_not_verified",
            "freshness_not_verified",
            "numerical_agreement_does_not_imply_cmis_promotion",
        ],
    }


__all__ = [
    "CHAIN",
    "DEXSCREENER_SOURCE",
    "JUPITER_SOURCE",
    "USD_PER_TOKEN",
    "VERSION",
    "verify_jupiter_vs_dexscreener_prices",
]
