"""Deterministic route-evidence validation for CMIS pre-trade analysis.

This module does not collect provider data. It accepts evidence only after an
internal CMIS producer has resolved one explicit route and passes that evidence
through exact chain/route, freshness, semantic, and proof-basis gates.

A symbol or asset mint alone is never enough to bind route evidence. The trade
must name token-in, token-out, pool, and AMM config explicitly. Missing,
stale, mismatched, or semantically incompatible evidence is reported as
unusable instead of being converted into a guessed execution estimate.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional


VERSION = "1.0"
SCHEMA_VERSION = 1
ROUTE_FIELDS = (
    "token_in_mint",
    "token_out_mint",
    "pool",
    "amm_config",
)

# These semantic labels are intentionally narrower than the public capability
# names. In particular, XDEX's user slippage tolerance / minimum-received
# parameter is not an expected execution-slippage estimate and therefore does
# not satisfy the generic ``slippage`` capability.
_ACCEPTED_SEMANTICS = {
    "slippage": frozenset({"expected_execution_slippage_percent"}),
    "price_impact": frozenset({"route_price_impact_percent"}),
    "fees": frozenset({"route_execution_fee_estimate"}),
}


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _epoch(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = _number(value)
        return number if number is not None and number >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    epoch = parsed.timestamp()
    return epoch if epoch >= 0 else None


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

    unknown = sorted(set(route) - set(ROUTE_FIELDS))
    if unknown:
        raise ValueError("unknown trade route fields: " + ", ".join(unknown))

    normalized: Dict[str, str] = {}
    for field in ROUTE_FIELDS:
        value = _text(route.get(field))
        if not value:
            raise ValueError(
                "trade route requires token_in_mint, token_out_mint, pool, and amm_config"
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
    unknown = sorted(set(value) - set(ROUTE_FIELDS))
    if unknown:
        raise ValueError("unknown route_evidence route fields: " + ", ".join(unknown))
    result: Dict[str, str] = {}
    for field in ROUTE_FIELDS:
        text = _text(value.get(field))
        if not text:
            raise ValueError(
                "route_evidence.route requires token_in_mint, token_out_mint, pool, and amm_config"
            )
        result[field] = text
    return result


def _proof_basis(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in result:
            result.append(text)
    return result


def _capability_value(name: str, record: Mapping[str, Any]) -> Any:
    value = record.get("value")
    if name in {"slippage", "price_impact"}:
        number = _number(value)
        if number is None or number < 0:
            return None
        return number
    if name == "fees":
        if not isinstance(value, Mapping) or not value:
            return None
        return deepcopy(dict(value))
    return None


def evaluate_route_evidence(
    route_evidence: Any,
    *,
    target_chain: str,
    trade_route: Optional[Mapping[str, Any]],
    evaluated_at: Any,
    max_age_seconds: Any,
) -> Dict[str, Any]:
    """Return route-scoped capability overrides plus a fail-closed audit record."""
    audit: Dict[str, Any] = {
        "contract_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "supplied": route_evidence is not None,
        "source": None,
        "chain": None,
        "route": None,
        "trade_route": dict(trade_route) if isinstance(trade_route, Mapping) else None,
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

    schema_version = route_evidence.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"route_evidence schema_version must be {SCHEMA_VERSION}"
        )

    source = _text(route_evidence.get("source"))
    if not source:
        raise ValueError("route_evidence source is required")
    audit["source"] = source

    evidence_chain = (_text(route_evidence.get("chain")) or "").lower()
    if not evidence_chain:
        raise ValueError("route_evidence chain is required")
    audit["chain"] = evidence_chain

    evidence_route = _normalize_evidence_route(route_evidence.get("route"))
    audit["route"] = evidence_route
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
        audit["scope_match"] = True

    evaluated_epoch = audit["evaluated_at_epoch"]
    if audit["global_rejection_reason"] is None:
        if max_age is None:
            audit["global_rejection_reason"] = (
                "route_evidence_freshness_policy_unconfigured"
            )
        elif observed_epoch is None:
            audit["global_rejection_reason"] = "route_evidence_timestamp_unverified"
        elif evaluated_epoch is None:
            audit["global_rejection_reason"] = (
                "route_evidence_evaluation_timestamp_unverified"
            )
        elif observed_epoch > evaluated_epoch:
            audit["global_rejection_reason"] = (
                "route_evidence_timestamp_after_evaluation"
            )
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

    unknown_capabilities = sorted(set(capabilities) - set(_ACCEPTED_SEMANTICS))
    if unknown_capabilities:
        raise ValueError(
            "unsupported route_evidence capabilities: "
            + ", ".join(unknown_capabilities)
        )

    overrides: Dict[str, Any] = {}
    for name, raw_record in capabilities.items():
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"route_evidence capability '{name}' must be a mapping")

        reason = audit["global_rejection_reason"]
        status = (_text(raw_record.get("status")) or "").lower()
        semantic = (_text(raw_record.get("semantic")) or "").lower()
        proof = _proof_basis(raw_record.get("proof_basis"))
        unit = _text(raw_record.get("unit"))
        value = _capability_value(name, raw_record)

        if reason is None and status != "verified":
            reason = "route_evidence_capability_not_verified"
        if reason is None and semantic not in _ACCEPTED_SEMANTICS[name]:
            reason = "route_evidence_semantic_not_accepted"
        if reason is None and not proof:
            reason = "route_evidence_proof_basis_unavailable"
        if reason is None and value is None:
            reason = "route_evidence_value_invalid"
        if reason is None and not unit:
            reason = "route_evidence_unit_unavailable"

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
                "observed_at": observed_at,
                "age_seconds": audit["age_seconds"],
                "max_age_seconds": max_age,
                "semantic": semantic,
                "proof_basis": proof,
            },
        }
        audit["usable_capabilities"].append(name)

    return {"overrides": overrides, "audit": audit}


__all__ = [
    "ROUTE_FIELDS",
    "SCHEMA_VERSION",
    "VERSION",
    "evaluate_route_evidence",
    "normalize_trade_route",
]
