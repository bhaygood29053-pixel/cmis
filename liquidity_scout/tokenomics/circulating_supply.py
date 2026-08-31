"""Deterministic circulating-supply arithmetic for verified exclusion evidence.

This module does not discover non-circulating accounts and does not infer
circulation from burn history. It accepts only an independently verified,
complete exclusion contract for one exact mint and reconciles that evidence
against CMIS' verified current on-chain total supply.
"""

from decimal import Decimal, localcontext

from .activity import scale_raw_amount


CIRCULATION_CONTRACT = "verified_excluded_token_accounts_v1"


def _text(value):
    text = str(value or "").strip()
    return text or None


def _strict_nonnegative_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _ratio_text(numerator, denominator):
    with localcontext() as ctx:
        ctx.prec = 40
        value = Decimal(numerator) / Decimal(denominator)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _unavailable(
    reason,
    *,
    mint=None,
    decimals=None,
    current_total_supply_verified=False,
    current_total_raw=None,
    current_total_source=None,
):
    total_raw = (
        str(current_total_raw)
        if current_total_supply_verified and current_total_raw is not None
        else None
    )
    total_supply = (
        scale_raw_amount(current_total_raw, decimals)
        if (
            current_total_supply_verified
            and current_total_raw is not None
            and decimals is not None
        )
        else None
    )
    return {
        "available": False,
        "status": "unavailable",
        "reason": reason,
        "mint": mint,
        "decimals": decimals,
        "contract": CIRCULATION_CONTRACT,
        "contract_verified": False,
        "exclusion_universe_complete": False,
        "current_total_supply_verified": current_total_supply_verified is True,
        "current_total_supply_reconciled": False,
        "current_total_source": _text(current_total_source),
        "total_supply_raw": total_raw,
        "total_supply": total_supply,
        "excluded_supply_raw": None,
        "excluded_supply": None,
        "circulating_supply_raw": None,
        "circulating_supply": None,
        "circulating_supply_verified": False,
        "circulating_to_total_supply_ratio": None,
        "ratio_state": "UNAVAILABLE",
        "observation_slot": None,
        "observed_at": None,
        "observation_time_verified": False,
        "exclusions": [],
        "sources": [],
    }


def build_circulating_supply_metrics(
    evidence,
    *,
    mint,
    decimals,
    current_total_raw,
    current_total_supply_verified,
    current_total_source=None,
):
    """Verify one exact-mint circulation/exclusion report.

    Contract semantics:

    circulating_supply = current_total_supply - verified_excluded_balances

    The exclusion universe must be independently proven complete. Every
    excluded token account must have exact-mint identity verification, balance
    verification at the same observation slot, and an independently verified
    circulation-exclusion classification. Current on-chain total supply already
    reflects canonical token burns, so burns are never subtracted again here.
    """
    mint = _text(mint)
    decimals = _strict_nonnegative_int(decimals)
    current_total_raw = _strict_nonnegative_int(current_total_raw)

    if not mint:
        return _unavailable("token_mint_required")
    if decimals is None:
        return _unavailable("verified_token_decimals_required", mint=mint)
    if current_total_supply_verified is not True or current_total_raw is None:
        return _unavailable(
            "current_total_supply_unverified",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=False,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if not isinstance(evidence, dict):
        return _unavailable(
            "circulating_supply_contract_not_supplied",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )

    evidence_mint = _text(evidence.get("mint"))
    evidence_decimals = _strict_nonnegative_int(evidence.get("decimals"))
    contract = _text(evidence.get("contract"))
    contract_verified = evidence.get("contract_verified") is True
    contract_source = _text(evidence.get("contract_source"))
    universe_complete = evidence.get("exclusion_universe_complete") is True
    universe_source = _text(evidence.get("exclusion_universe_source"))
    evidence_total_verified = evidence.get("total_supply_verified") is True
    evidence_total_raw = _strict_nonnegative_int(evidence.get("total_supply_raw"))
    total_supply_source = _text(evidence.get("total_supply_source"))
    observation_slot = _strict_nonnegative_int(evidence.get("observation_slot"))
    observed_at = _strict_nonnegative_int(evidence.get("observed_at"))
    observation_time_verified = evidence.get("observation_time_verified") is True
    source = _text(evidence.get("source"))

    if evidence_mint != mint:
        return _unavailable(
            "circulating_supply_mint_mismatch",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if evidence_decimals != decimals:
        return _unavailable(
            "circulating_supply_decimals_mismatch",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if contract != CIRCULATION_CONTRACT or not contract_verified or not contract_source:
        return _unavailable(
            "circulating_supply_contract_unverified",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if not universe_complete or not universe_source:
        return _unavailable(
            "circulating_supply_exclusion_universe_incomplete",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if (
        not evidence_total_verified
        or evidence_total_raw is None
        or not total_supply_source
    ):
        return _unavailable(
            "circulating_supply_total_supply_evidence_unverified",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if evidence_total_raw != current_total_raw:
        return _unavailable(
            "circulating_supply_total_supply_mismatch",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if observation_slot is None:
        return _unavailable(
            "circulating_supply_observation_slot_unverified",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if observation_time_verified and observed_at is None:
        return _unavailable(
            "circulating_supply_observation_time_malformed",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )
    if not observation_time_verified:
        observed_at = None
    if not source:
        return _unavailable(
            "circulating_supply_source_unverified",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )

    exclusions = evidence.get("exclusions")
    if not isinstance(exclusions, list):
        return _unavailable(
            "circulating_supply_exclusions_malformed",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )

    normalized = []
    seen_accounts = set()
    excluded_raw = 0

    for item in exclusions:
        if not isinstance(item, dict):
            return _unavailable(
                "circulating_supply_exclusion_malformed",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )

        account = _text(item.get("account"))
        item_mint = _text(item.get("mint"))
        raw_balance = _strict_nonnegative_int(item.get("raw_balance"))
        item_slot = _strict_nonnegative_int(item.get("observation_slot"))
        exclusion_reason = _text(item.get("exclusion_reason"))
        item_source = _text(item.get("source"))

        if not account or account in seen_accounts:
            return _unavailable(
                "circulating_supply_exclusion_account_invalid",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )
        if item_mint != mint or item.get("account_identity_verified") is not True:
            return _unavailable(
                "circulating_supply_exclusion_identity_unverified",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )
        if raw_balance is None or item.get("balance_verified") is not True:
            return _unavailable(
                "circulating_supply_exclusion_balance_unverified",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )
        if item_slot != observation_slot:
            return _unavailable(
                "circulating_supply_exclusion_slot_mismatch",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )
        if (
            not exclusion_reason
            or item.get("circulation_exclusion_verified") is not True
        ):
            return _unavailable(
                "circulating_supply_exclusion_semantics_unverified",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )
        if not item_source:
            return _unavailable(
                "circulating_supply_exclusion_source_unverified",
                mint=mint,
                decimals=decimals,
                current_total_supply_verified=True,
                current_total_raw=current_total_raw,
                current_total_source=current_total_source,
            )

        seen_accounts.add(account)
        excluded_raw += raw_balance
        normalized.append({
            "account": account,
            "mint": mint,
            "raw_balance": str(raw_balance),
            "balance": scale_raw_amount(raw_balance, decimals),
            "account_identity_verified": True,
            "balance_verified": True,
            "circulation_exclusion_verified": True,
            "exclusion_reason": exclusion_reason,
            "observation_slot": observation_slot,
            "source": item_source,
        })

    if excluded_raw > current_total_raw:
        return _unavailable(
            "circulating_supply_exclusions_exceed_total_supply",
            mint=mint,
            decimals=decimals,
            current_total_supply_verified=True,
            current_total_raw=current_total_raw,
            current_total_source=current_total_source,
        )

    circulating_raw = current_total_raw - excluded_raw
    if current_total_raw == 0:
        ratio = None
        ratio_state = "ZERO_TOTAL_SUPPLY"
    else:
        ratio = _ratio_text(circulating_raw, current_total_raw)
        ratio_state = "AVAILABLE"

    sources = []
    for candidate in (
        current_total_source,
        total_supply_source,
        contract_source,
        universe_source,
        source,
    ):
        candidate = _text(candidate)
        if candidate and candidate not in sources:
            sources.append(candidate)
    for item in normalized:
        candidate = item["source"]
        if candidate not in sources:
            sources.append(candidate)

    return {
        "available": True,
        "status": "ok",
        "reason": None,
        "mint": mint,
        "decimals": decimals,
        "contract": CIRCULATION_CONTRACT,
        "contract_verified": True,
        "contract_source": contract_source,
        "exclusion_universe_complete": True,
        "exclusion_universe_source": universe_source,
        "current_total_supply_verified": True,
        "current_total_supply_reconciled": True,
        "current_total_source": _text(current_total_source),
        "total_supply_raw": str(current_total_raw),
        "total_supply": scale_raw_amount(current_total_raw, decimals),
        "total_supply_source": total_supply_source,
        "excluded_supply_raw": str(excluded_raw),
        "excluded_supply": scale_raw_amount(excluded_raw, decimals),
        "circulating_supply_raw": str(circulating_raw),
        "circulating_supply": scale_raw_amount(circulating_raw, decimals),
        "circulating_supply_verified": True,
        "circulating_to_total_supply_ratio": ratio,
        "ratio_state": ratio_state,
        "observation_slot": observation_slot,
        "total_supply_observation_slot": observation_slot,
        "observed_at": observed_at,
        "observation_time_verified": observation_time_verified,
        "exclusions": normalized,
        "exclusion_count": len(normalized),
        "source": source,
        "sources": sources,
    }


__all__ = [
    "CIRCULATION_CONTRACT",
    "build_circulating_supply_metrics",
]
