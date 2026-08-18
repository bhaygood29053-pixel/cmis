"""Deterministic route-evidence validation for CMIS pre-trade analysis.

This module does not collect provider data. It accepts evidence only after an
internal CMIS producer has resolved one explicit route and passes that evidence
through exact chain/route/input-amount, freshness, semantic, value-shape, and
proof-basis gates.

A symbol, asset mint, or route identity alone is never enough to bind
amount-sensitive route evidence. The trade must name token-in, token-out, pool,
AMM config, and the exact positive input amount explicitly. Missing, stale,
mismatched, semantically incompatible, or weakly-proven evidence is reported as
unusable instead of being converted into a guessed execution estimate.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional


VERSION = "1.2"
SCHEMA_VERSION = 2
ROUTE_FIELDS = (
    "token_in_mint",
    "token_out_mint",
    "pool",
    "amm_config",
)
_ROUTE_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "source",
        "chain",
        "route",
        "token_in_amount",
        "observed_at",
        "capabilities",
    }
)
_CAPABILITY_FIELDS = frozenset({"status", "semantic", "value", "unit", "proof_basis"})
_ACCEPTED_SOURCES = frozenset({"cmis_xdex_route_resolver"})

# These semantic labels are intentionally narrower than the public capability
# names. In particular, XDEX's user slippage tolerance / minimum-received
# parameter is not an expected execution-slippage estimate and therefore does
# not satisfy the generic ``slippage`` capability.
_ACCEPTED_SEMANTICS = {
    "slippage": "expected_execution_slippage_percent",
    "price_impact": "route_price_impact_percent",
    "fees": "route_execution_fee_estimate",
}
_EXPECTED_UNITS = {
    "slippage": "percent",
    "price_impact": "percent",
    "fees": "structured",
}
_REQUIRED_PROOF_BASIS = {
    "slippage": frozenset(
        {
            "verified_expected_execution_slippage_semantics",
            "verified_route_execution_slippage_observation",
        }
    ),
    "price_impact": frozenset(
        {
            "verified_direct_cp_route",
            "verified_active_output_reserve",
            "verified_zero_slippage_quote_output",
            "verified_integer_rounded_output_reserve_price_impact_semantics",
        }
    ),
    "fees": frozenset(
        {
            "verified_amm_config_trade_fee_rate",
            "bounded_historical_execution_corroboration",
        }
    ),
}
_FEE_VALUE_FIELDS = frozenset(
    {
        "amm_trade_fee_rate_percent",
        "bounded_historical_execution_model_fee_percent",
    }
)


def _text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text != value:
        return None
    return text


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def normalize_token_in_amount(value: Any) -> Optional[str]:
    """Return one canonical positive decimal string without float coercion.

    ``None`` means the amount was not supplied. Any other invalid value raises
    ``ValueError`` so a malformed amount can never silently become an unscoped
    route-evidence request.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("token_in_amount must be a positive finite decimal when supplied")
    if isinstance(value, str):
        text = value.strip()
        if not text or text != value:
            raise ValueError("token_in_amount must be a normalized positive finite decimal when supplied")
    else:
        text = str(value)
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("token_in_amount must be a positive finite decimal when supplied") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("token_in_amount must be a positive finite decimal when supplied")
    canonical = format(amount.normalize(), "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    return canonical


def _epoch(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = _number(value)
        return number if number is not None and number >= 0 else None
    if not isinstance(value, str):
        return None

    text = _text(value)
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    epoch = parsed.timestamp()
    return epoch if epoch >= 0 else None


def _unknown_keys(value: Mapping[str, Any], allowed: frozenset[str], field: str) -> None:
    non_string = [key for key in value if not isinstance(key, str)]
    if non_string:
        raise ValueError(f"{field} keys must be strings")
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ValueError(f"unknown {field} fields: " + ", ".join(unknown))


def normalize_trade_route(
    route: Any,
    *,
    asset_mint: Any,
    side: Any,
) -> Optional[Dict[str, str]]:
    """Normalize an optional explicit route without inferring missing identity."""
    if route is None:
        return None
    if not isinstance(route, Mapping):
        raise ValueError("trade route must be a mapping when supplied")

    _unknown_keys(route, frozenset(ROUTE_FIELDS), "trade route")

    normalized: Dict[str, str] = {}
    for field in ROUTE_FIELDS:
        value = _text(route.get(field))
        if not value:
            raise ValueError(
                "trade route requires normalized string token_in_mint, token_out_mint, pool, and amm_config"
            )
        normalized[field] = value

    mint = _text(asset_mint)
    side_name = (_text(side) or "").lower()
    if mint:
        if side_name == "buy" and normalized["token_out_mint"] != mint:
            raise ValueError(
                "buy trade route token_out_mint must match the proposed asset mint"
            )
        if side_name == "sell" and normalized["token_in_mint"] != mint:
            raise ValueError(
                "sell trade route token_in_mint must match the proposed asset mint"
            )
    return normalized


def _normalize_evidence_route(value: Any) -> Dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("route_evidence.route must be a mapping")
    _unknown_keys(value, frozenset(ROUTE_FIELDS), "route_evidence route")
    result: Dict[str, str] = {}
    for field in ROUTE_FIELDS:
        text = _text(value.get(field))
        if not text:
            raise ValueError(
                "route_evidence.route requires normalized string token_in_mint, token_out_mint, pool, and amm_config"
            )
        result[field] = text
    return result


def _proof_basis(value: Any) -> Optional[frozenset[str]]:
    if not isinstance(value, list) or not value:
        return None
    result: list[str] = []
    for item in value:
        text = _text(item)
        if not text or text in result:
            return None
        result.append(text)
    return frozenset(result)


def _fee_value(value: Any) -> Optional[dict[str, float]]:
    if not isinstance(value, Mapping):
        return None
    if any(not isinstance(key, str) for key in value):
        return None
    if set(value) != set(_FEE_VALUE_FIELDS):
        return None

    amm_rate = _number(value.get("amm_trade_fee_rate_percent"))
    bounded_rate = _number(value.get("bounded_historical_execution_model_fee_percent"))
    if amm_rate is None or bounded_rate is None:
        return None
    if not (0 <= amm_rate < 100 and 0 <= bounded_rate < 100):
        return None
    if amm_rate != bounded_rate:
        return None
    return {
        "amm_trade_fee_rate_percent": amm_rate,
        "bounded_historical_execution_model_fee_percent": bounded_rate,
    }


def _capability_value(name: str, record: Mapping[str, Any]) -> Any:
    value = record.get("value")
    if name in {"slippage", "price_impact"}:
        number = _number(value)
        if number is None or number < 0:
            return None
        return number
    if name == "fees":
        return _fee_value(value)
    return None


def evaluate_route_evidence(
    route_evidence: Any,
    *,
    target_chain: str,
    trade_route: Optional[Mapping[str, Any]],
    trade_token_in_amount: Any = None,
    evaluated_at: Any,
    max_age_seconds: Any,
) -> Dict[str, Any]:
    """Return amount-and-route-scoped overrides plus a fail-closed audit record."""
    try:
        normalized_trade_amount = normalize_token_in_amount(trade_token_in_amount)
    except ValueError:
        normalized_trade_amount = None

    audit: Dict[str, Any] = {
        "contract_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "supplied": route_evidence is not None,
        "source": None,
        "chain": None,
        "route": None,
        "trade_route": dict(trade_route) if isinstance(trade_route, Mapping) else None,
        "route_match": False,
        "token_in_amount": None,
        "trade_token_in_amount": normalized_trade_amount,
        "amount_match": False,
        "scope_match": False,
        "observed_at": None,
        "evaluated_at": evaluated_at,
        "observed_at_epoch": None,
        "evaluated_at_epoch": _epoch(evaluated_at),
        "age_seconds": None,
        "max_age_seconds": None,
        "freshness_complete": False,
        "fresh": False,
        "usable_capabilities": [],
        "rejected_capabilities": {},
        "global_rejection_reason": None,
    }
    if route_evidence is None:
        return {"overrides": {}, "audit": audit}
    if not isinstance(route_evidence, Mapping):
        raise ValueError("route_evidence must be a mapping or None")

    _unknown_keys(route_evidence, _ROUTE_EVIDENCE_FIELDS, "route_evidence")

    schema_version = route_evidence.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != SCHEMA_VERSION:
        raise ValueError(f"route_evidence schema_version must be {SCHEMA_VERSION}")

    source = _text(route_evidence.get("source"))
    if not source:
        raise ValueError("route_evidence source must be a normalized non-empty string")
    if source not in _ACCEPTED_SOURCES:
        raise ValueError("route_evidence source is not accepted by this contract")
    audit["source"] = source

    evidence_chain = (_text(route_evidence.get("chain")) or "").lower()
    if not evidence_chain:
        raise ValueError("route_evidence chain must be a normalized non-empty string")
    audit["chain"] = evidence_chain

    evidence_route = _normalize_evidence_route(route_evidence.get("route"))
    audit["route"] = evidence_route
    evidence_amount = normalize_token_in_amount(route_evidence.get("token_in_amount"))
    if evidence_amount is None:
        raise ValueError("route_evidence token_in_amount is required")
    audit["token_in_amount"] = evidence_amount

    observed_at = route_evidence.get("observed_at")
    observed_epoch = _epoch(observed_at)
    audit["observed_at"] = observed_at
    audit["observed_at_epoch"] = observed_epoch

    max_age = _number(max_age_seconds)
    if max_age is not None and max_age > 0:
        audit["max_age_seconds"] = max_age
    else:
        max_age = None

    target = (_text(target_chain) or "").lower()
    if not target:
        raise ValueError("target_chain is required for route evidence validation")

    if trade_route is None:
        audit["global_rejection_reason"] = "explicit_trade_route_unavailable"
    elif evidence_chain != target:
        audit["global_rejection_reason"] = "route_evidence_chain_mismatch"
    elif dict(trade_route) != evidence_route:
        audit["global_rejection_reason"] = "route_evidence_scope_mismatch"
    else:
        audit["route_match"] = True
        if normalized_trade_amount is None:
            audit["global_rejection_reason"] = "explicit_trade_input_amount_unavailable"
        elif normalized_trade_amount != evidence_amount:
            audit["global_rejection_reason"] = "route_evidence_input_amount_mismatch"
        else:
            audit["amount_match"] = True
            audit["scope_match"] = True

    evaluated_epoch = audit["evaluated_at_epoch"]
    if audit["global_rejection_reason"] is None:
        if max_age is None:
            audit["global_rejection_reason"] = "route_evidence_freshness_policy_unconfigured"
        elif observed_epoch is None:
            audit["global_rejection_reason"] = "route_evidence_timestamp_unverified"
        elif evaluated_epoch is None:
            audit["global_rejection_reason"] = "route_evidence_evaluation_timestamp_unverified"
        elif observed_epoch > evaluated_epoch:
            audit["global_rejection_reason"] = "route_evidence_timestamp_after_evaluation"
        else:
            age = evaluated_epoch - observed_epoch
            audit["age_seconds"] = age
            audit["freshness_complete"] = True
            if age >= max_age:
                audit["global_rejection_reason"] = "route_evidence_stale"
            else:
                audit["fresh"] = True

    capabilities = route_evidence.get("capabilities")
    if not isinstance(capabilities, Mapping):
        raise ValueError("route_evidence capabilities must be a mapping")
    if any(not isinstance(name, str) for name in capabilities):
        raise ValueError("route_evidence capability names must be strings")

    unknown_capabilities = sorted(set(capabilities) - set(_ACCEPTED_SEMANTICS))
    if unknown_capabilities:
        raise ValueError(
            "unsupported route_evidence capabilities: " + ", ".join(unknown_capabilities)
        )

    overrides: Dict[str, Any] = {}
    for name, raw_record in capabilities.items():
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"route_evidence capability '{name}' must be a mapping")
        _unknown_keys(raw_record, _CAPABILITY_FIELDS, f"route_evidence capability '{name}'")

        reason = audit["global_rejection_reason"]
        status = (_text(raw_record.get("status")) or "").lower()
        semantic = (_text(raw_record.get("semantic")) or "").lower()
        proof = _proof_basis(raw_record.get("proof_basis"))
        unit = _text(raw_record.get("unit"))
        value = _capability_value(name, raw_record)

        if reason is None and status != "verified":
            reason = "route_evidence_capability_not_verified"
        if reason is None and semantic != _ACCEPTED_SEMANTICS[name]:
            reason = "route_evidence_semantic_not_accepted"
        if reason is None and proof != _REQUIRED_PROOF_BASIS[name]:
            reason = "route_evidence_proof_basis_not_accepted"
        if reason is None and value is None:
            reason = "route_evidence_value_invalid"
        if reason is None and unit != _EXPECTED_UNITS[name]:
            reason = "route_evidence_unit_not_accepted"

        if reason is not None:
            audit["rejected_capabilities"][name] = {
                "reason_code": reason,
                "status": status or None,
                "semantic": semantic or None,
            }
            continue

        overrides[name] = {
            "status": "ok",
            "value": value,
            "unit": unit,
            "reason_code": "verified_route_evidence_available",
            "route_evidence": {
                "contract_version": VERSION,
                "schema_version": SCHEMA_VERSION,
                "source": source,
                "chain": evidence_chain,
                "route": deepcopy(evidence_route),
                "token_in_amount": evidence_amount,
                "observed_at": observed_at,
                "age_seconds": audit["age_seconds"],
                "max_age_seconds": max_age,
                "semantic": semantic,
                "proof_basis": sorted(proof),
            },
        }
        audit["usable_capabilities"].append(name)

    return {"overrides": overrides, "audit": audit}


__all__ = [
    "ROUTE_FIELDS",
    "SCHEMA_VERSION",
    "VERSION",
    "evaluate_route_evidence",
    "normalize_token_in_amount",
    "normalize_trade_route",
]
