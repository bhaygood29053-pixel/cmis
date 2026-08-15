"""CMIS tokenomics envelope for chain-native assets.

This shared service composes already-collected native-network supply records.
It performs no network calls and does not reinterpret provider integer supply
representations as mint-account decimals. Mint/freeze authority fields are not
applicable to a chain-native asset and are never inferred from wrapped-token
metadata.
"""

from collections.abc import Mapping
from typing import Any, Optional

from .cmis_contract import PARTIAL, UNAVAILABLE, build_service_envelope


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _verified_supply(record: Any):
    if not isinstance(record, Mapping) or record.get("supply_verified") is not True:
        return None, False
    value = _text(record.get("supply"))
    if value is None:
        return None, False
    return value, True


def _source(record: Any, role: str):
    if not isinstance(record, Mapping):
        return None
    source = _text(record.get("source"))
    if not source:
        return None
    result = {"source": source, "role": role}
    observed_at = record.get("observed_at")
    if observed_at is not None:
        result["observed_at"] = observed_at
    return result


def _source_name(record: Any):
    if not isinstance(record, Mapping):
        return None
    return _text(record.get("source"))


def build_native_tokenomics_response(
    *,
    symbol: Any,
    name: Any,
    chain: str,
    total_supply_record: Any = None,
    circulating_supply_record: Any = None,
    observed_at: Any = None,
):
    """Build deterministic tokenomics for one chain-native asset.

    Current total and circulating supply are accepted only from independently
    verified provider records. Maximum supply and native issuance history remain
    unavailable unless separately verified by a future provider/service.

    Mint/freeze authority states are explicitly ``not_applicable`` for a native
    chain asset. Their verification flags are true because CMIS has verified the
    applicability state itself; no wrapped-token authority is being substituted.
    This lets shared deterministic risk logic distinguish "not applicable" from
    "unknown/unverified" without inventing a native mint account.
    """
    symbol_text = _text(symbol)
    name_text = _text(name) or symbol_text

    total_supply, total_verified = _verified_supply(total_supply_record)
    circulating_supply, circulating_verified = _verified_supply(
        circulating_supply_record
    )

    checks = {
        "total_supply_verified": total_verified,
        "circulating_supply_verified": circulating_verified,
        "maximum_supply_verified": False,
    }
    verified_checks = sum(1 for value in checks.values() if value)
    total_checks = len(checks)
    confidence = {
        "complete": verified_checks == total_checks,
        "verified_checks": verified_checks,
        "total_checks": total_checks,
        "verification_ratio": round(verified_checks / total_checks, 6),
        "checks": checks,
    }

    warnings = []
    if not total_verified:
        warnings.append({
            "code": "native_total_supply_unverified",
            "message": "Native network total supply is unavailable from verified data.",
        })
    if not circulating_verified:
        warnings.append({
            "code": "native_circulating_supply_unverified",
            "message": "Native circulating supply is unavailable from verified data.",
        })
    warnings.extend([
        {
            "code": "maximum_supply_unverified",
            "message": "Maximum supply is not independently verified by this service.",
        },
        {
            "code": "native_issuance_activity_unavailable",
            "message": (
                "Verified native-network issuance/burn activity was not supplied "
                "to this tokenomics request."
            ),
        },
    ])

    sources = []
    for record, role in (
        (total_supply_record, "tokenomics.network_total_supply"),
        (circulating_supply_record, "tokenomics.network_circulating_supply"),
    ):
        source = _source(record, role)
        if source and source not in sources:
            sources.append(source)

    status = PARTIAL if verified_checks else UNAVAILABLE
    return build_service_envelope(
        "tokenomics",
        chain,
        status,
        asset={
            "symbol": symbol_text,
            "name": name_text,
            "mint": None,
            "asset_type": "native",
        },
        data={
            "scope": "native_network",
            "asset_type": "native",
            "symbol": symbol_text,
            "name": name_text,
            "mint": None,
            "current_total_supply": total_supply,
            "supply_verified": total_verified,
            "circulating_supply": circulating_supply,
            "circulating_supply_verified": circulating_verified,
            "maximum_supply": None,
            "maximum_supply_verified": False,
            "decimals": None,
            "rpc_decimals_consistent": None,
            "mint_authority": None,
            "mint_authority_verified": True,
            "mint_authority_state": "not_applicable",
            "freeze_authority": None,
            "freeze_authority_verified": True,
            "freeze_authority_state": "not_applicable",
            "future_minting_possible": None,
            "token_activity": {
                "available": False,
                "activity_verified": False,
                "coverage_scope": None,
                "lifetime_coverage_verified": False,
                "net_issuance_verified": False,
                "net_issuance_tokens": None,
                "verification_reasons": ["native_issuance_activity_unavailable"],
            },
            # Preserve source names inside the data payload because the shared
            # deterministic risk wrapper receives tokenomics data rather than
            # the whole tokenomics envelope.
            "sources": {
                "network_total_supply": _source_name(total_supply_record),
                "network_circulating_supply": _source_name(
                    circulating_supply_record
                ),
            },
        },
        risk=None,
        confidence=confidence,
        sources=sources,
        observed_at=observed_at,
        warnings=warnings,
        errors=[],
    )


__all__ = ["build_native_tokenomics_response"]