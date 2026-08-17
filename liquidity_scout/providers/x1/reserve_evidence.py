"""Build comparable CMIS reserve evidence only from already-proven inputs.

This adapter does not fetch data or discover semantics. It accepts the output of
``validate_reserve_semantic_proof`` plus a raw X1 RPC token-account balance and
constructs same-identity CMIS evidence only when the provider contract explicitly
declares a supported unit contract with decimals matching the RPC token account.

Supported provider unit contracts are explicit integer ``token_base_units`` and
explicit decimal ``token_units``. Neither contract is inferred from field names,
value shape, ordering, or token decimals.

Freshness is deliberately caller-controlled and defaults closed. A provider
observation and an RPC slot are not assumed contemporaneous merely because they
were collected near each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.cmis.evidence import build_evidence_observation


VERSION = "1.0"
BASE_UNITS = "token_base_units"
TOKEN_UNITS = "token_units"
SUPPORTED_UNITS = {BASE_UNITS, TOKEN_UNITS}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _places(decimals: Any) -> int | None:
    if isinstance(decimals, bool):
        return None
    try:
        places = int(decimals)
    except (TypeError, ValueError):
        return None
    return places if places >= 0 else None


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _base_units_to_token_units(value: Any, decimals: Any) -> str | None:
    if isinstance(value, bool):
        return None
    text = _text(value)
    places = _places(decimals)
    if text is None or not text.isdigit() or places is None:
        return None
    try:
        normalized = Decimal(text) / (Decimal(10) ** places)
    except (InvalidOperation, ValueError):
        return None
    return _canonical_decimal(normalized)


def _token_units_to_canonical(value: Any, decimals: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = _text(value)
    places = _places(decimals)
    if text is None or places is None:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None

    scale = Decimal(10) ** places
    scaled = parsed * scale
    if scaled != scaled.to_integral_value():
        return None
    return _canonical_decimal(parsed)


def build_x1_reserve_evidence_pair(
    semantic_proof: Mapping[str, Any],
    rpc_balance: Mapping[str, Any],
    *,
    role: str,
    observed_at: Any,
    freshness_verified: bool = False,
) -> dict[str, Any]:
    """Build provider/RPC evidence for one reserve role, failing closed.

    ``role`` must be ``asset`` or ``counter``. The semantic proof must already
    bind the provider field to the same vault/mint queried through RPC and must
    explicitly declare either ``token_base_units`` or ``token_units``.
    """
    if not isinstance(semantic_proof, Mapping) or not isinstance(rpc_balance, Mapping):
        raise TypeError("reserve evidence inputs must be mappings")
    if role not in {"asset", "counter"}:
        raise ValueError("role must be asset or counter")

    reasons: list[str] = []
    if semantic_proof.get("chain") != "x1" or rpc_balance.get("chain") != "x1":
        reasons.append("wrong_chain")
    if semantic_proof.get("semantic_contract_verified") is not True:
        reasons.append("semantic_contract_unverified")
    if semantic_proof.get("identity_binding_verified") is not True:
        reasons.append("identity_binding_unverified")

    roles = semantic_proof.get("roles")
    spec = roles.get(role) if isinstance(roles, Mapping) else None
    if not isinstance(spec, Mapping):
        reasons.append("role_binding_missing")
        spec = {}

    pool = _text(semantic_proof.get("pool_address"))
    mint = _text(spec.get("mint"))
    vault = _text(spec.get("vault"))
    field_path = _text(spec.get("field_path"))
    unit = _text(spec.get("unit"))
    decimals = spec.get("decimals")
    provider_raw = spec.get("raw_value")

    if not pool or not mint or not vault or not field_path:
        reasons.append("identity_incomplete")
    if unit not in SUPPORTED_UNITS:
        reasons.append("provider_unit_unsupported")
    if _text(rpc_balance.get("account")) != vault:
        reasons.append("rpc_vault_mismatch")
    if rpc_balance.get("method") != "getTokenAccountBalance":
        reasons.append("rpc_method_mismatch")
    if rpc_balance.get("decimals") != decimals:
        reasons.append("decimal_mismatch")

    if unit == BASE_UNITS:
        provider_normalized = _base_units_to_token_units(provider_raw, decimals)
        if provider_normalized is None:
            reasons.append("provider_base_units_invalid")
    elif unit == TOKEN_UNITS:
        provider_normalized = _token_units_to_canonical(provider_raw, decimals)
        if provider_normalized is None:
            reasons.append("provider_token_units_invalid")
    else:
        provider_normalized = None

    rpc_normalized = _base_units_to_token_units(
        rpc_balance.get("amount"), rpc_balance.get("decimals")
    )
    if rpc_normalized is None:
        reasons.append("rpc_base_units_invalid")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return {
            "service": "x1_reserve_evidence_adapter",
            "version": VERSION,
            "role": role,
            "evidence_ready": False,
            "cmis_promotable": False,
            "provider": None,
            "rpc": None,
            "rejection_reasons": reasons,
        }

    subject_id = f"pool:{pool}:vault:{vault}:mint:{mint}"
    common = {
        "chain": "x1",
        "fact_type": "pool_reserve",
        "subject_id": subject_id,
        "observed_at": observed_at,
        "unit": "TOKEN_UNITS",
        "calculation_version": f"x1-reserve-evidence-{VERSION}",
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": bool(freshness_verified),
    }
    provider = build_evidence_observation(
        **common,
        source="X1.Ninja",
        source_role="market_provider",
        raw_identifier=field_path,
        raw_value=provider_raw,
        normalized_value=provider_normalized,
        warnings=[] if freshness_verified else ["freshness_not_verified"],
    )
    rpc = build_evidence_observation(
        **common,
        source="X1 RPC",
        source_role="onchain_verifier",
        block_slot=rpc_balance.get("slot"),
        raw_identifier=vault,
        raw_value=rpc_balance.get("amount"),
        normalized_value=rpc_normalized,
        warnings=[] if freshness_verified else ["freshness_not_verified"],
    )
    return {
        "service": "x1_reserve_evidence_adapter",
        "version": VERSION,
        "role": role,
        "evidence_ready": True,
        "cmis_promotable": False,
        "provider": provider,
        "rpc": rpc,
        "rejection_reasons": [],
    }


__all__ = [
    "BASE_UNITS",
    "TOKEN_UNITS",
    "VERSION",
    "build_x1_reserve_evidence_pair",
]
