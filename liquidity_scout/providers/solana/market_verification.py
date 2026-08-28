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
PYTH_SOURCE = "pyth_core_solana_push"
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


def verify_jupiter_vs_pyth_price(
    jupiter: Mapping[str, Any],
    pyth: Mapping[str, Any],
    *,
    max_relative_difference: Any,
    jupiter_fact_time_unix: Any,
) -> dict[str, Any]:
    """Compare exact-mint Jupiter and Pyth USD prices without time promotion.

    Both providers must independently prove exact subject/unit semantics. The
    provider fact times are preserved and their absolute delta is calculated,
    but this function intentionally has no hidden same-time threshold. A future
    policy must decide what time delta is compatible for current-price
    promotion.
    """

    if not isinstance(jupiter, Mapping) or not isinstance(pyth, Mapping):
        raise TypeError("Jupiter/Pyth price cross-check inputs must be mappings")
    tolerance = _tolerance(max_relative_difference)
    reasons: list[str] = []

    if jupiter.get("chain") != CHAIN or pyth.get("chain") != CHAIN:
        reasons.append("wrong_chain")
    if jupiter.get("source") != JUPITER_SOURCE:
        reasons.append("jupiter_source_mismatch")
    if pyth.get("source") != PYTH_SOURCE:
        reasons.append("pyth_source_mismatch")

    jupiter_mint = _text(jupiter.get("mint"))
    pyth_mint = _text(pyth.get("mint"))
    if jupiter_mint is None or pyth_mint is None:
        reasons.append("mint_missing")
    elif jupiter_mint != pyth_mint:
        reasons.append("mint_mismatch")

    if jupiter.get("price_available") is not True:
        reasons.append("jupiter_price_unavailable")
    if pyth.get("price_available") is not True:
        reasons.append("pyth_price_unavailable")
    if pyth.get("mapping_verified") is not True:
        reasons.append("pyth_mapping_unverified")
    if pyth.get("price_integrity_verified") is not True:
        reasons.append("pyth_price_integrity_unverified")
    if pyth.get("fact_time_verified") is not True:
        reasons.append("pyth_fact_time_unverified")
    if pyth.get("quote_symbol") != "USD":
        reasons.append("pyth_quote_not_usd")

    jupiter_price = _positive_decimal(jupiter.get("usd_price"))
    pyth_price = _positive_decimal(pyth.get("price_usd"))
    if jupiter_price is None:
        reasons.append("jupiter_price_invalid")
    if pyth_price is None:
        reasons.append("pyth_price_invalid")
    if jupiter.get("currency") != "USD":
        reasons.append("jupiter_currency_not_usd")

    try:
        jupiter_fact_time = Decimal(str(jupiter_fact_time_unix))
    except (InvalidOperation, ValueError, TypeError):
        jupiter_fact_time = None
    pyth_fact_raw = pyth.get("publish_time_unix")
    try:
        pyth_fact_time = Decimal(str(pyth_fact_raw))
    except (InvalidOperation, ValueError, TypeError):
        pyth_fact_time = None
    if (
        jupiter_fact_time is None
        or not jupiter_fact_time.is_finite()
        or jupiter_fact_time < 0
    ):
        reasons.append("jupiter_fact_time_unavailable")
    if (
        pyth_fact_time is None
        or not pyth_fact_time.is_finite()
        or pyth_fact_time < 0
    ):
        reasons.append("pyth_fact_time_invalid")

    if reasons:
        result = _insufficient(*reasons)
        result["service"] = "solana_jupiter_pyth_price_crosscheck"
        result["provider_pair"] = ["jupiter_price_v3", "pyth_core_solana_push"]
        result["time_identity_verified"] = False
        result["source_independence_verified"] = False
        return result

    assert (
        jupiter_mint is not None
        and jupiter_price is not None
        and pyth_price is not None
        and jupiter_fact_time is not None
        and pyth_fact_time is not None
    )
    difference = _relative_difference(jupiter_price, pyth_price)
    time_delta = abs(jupiter_fact_time - pyth_fact_time)
    status = AGREEMENT if difference <= tolerance else CONFLICT

    return {
        "service": "solana_jupiter_pyth_price_crosscheck",
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
        "jupiter_price": _canonical_decimal(jupiter_price),
        "pyth_price": _canonical_decimal(pyth_price),
        "relative_difference": _canonical_decimal(difference),
        "within_tolerance": difference <= tolerance,
        "jupiter_fact_time_unix": _canonical_decimal(jupiter_fact_time),
        "pyth_fact_time_unix": _canonical_decimal(pyth_fact_time),
        "fact_time_delta_seconds": _canonical_decimal(time_delta),
        "time_identity_policy_complete": False,
        "time_identity_verified": False,
        "freshness_verified": False,
        "source_independence_verified": False,
        "current_price_promotable": False,
        "execution_authorized": False,
        "rejection_reasons": [],
        "warnings": [
            "numerical_agreement_does_not_establish_time_identity",
            "no_cross_source_fact_time_delta_policy_is_accepted",
            "provider_count_does_not_establish_market_source_independence",
        ],
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
    "PYTH_SOURCE",
    "USD_PER_TOKEN",
    "VERSION",
    "verify_jupiter_vs_dexscreener_prices",
    "verify_jupiter_vs_pyth_price",
]
