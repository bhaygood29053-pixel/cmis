"""Bounded tokenized-equity market activity contract for CMIS.

Binds market observations to accepted tokenized-equity provenance while keeping
liquidity, trade volume, trades, transfers, holders, price, and bridge flows
semantically separate. Structure/source/fact-time are validated; deployment,
adoption, risk, manipulation, legal effect, and execution are not promoted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from urllib.parse import urlparse

from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
)

TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT = "tokenized_equity_market_activity/v1"
DEFAULT_EXECUTION_AUTHORIZED = False
OBSERVATION_STATES = frozenset({"OBSERVED", "UNKNOWN", "NOT_APPLICABLE"})
SCOPE_KINDS = frozenset({"asset", "venue", "pool"})
DISALLOWED_ID_KINDS = frozenset({"symbol", "ticker", "name", "label"})
SOURCE_CLASSES = frozenset(
    {"onchain_rpc", "indexer", "venue_api", "bridge_api", "registry_api", "other"}
)
PRICE_SEMANTICS = frozenset(
    {"executed_trade_price", "quoted_price", "reference_price", "derived_price"}
)
REQUIRED_METRICS = (
    "liquidity_usd",
    "trade_volume_usd",
    "trade_count",
    "transfer_count",
    "holder_count",
    "price_usd",
    "bridge_inflow_units",
    "bridge_outflow_units",
)
WINDOW_METRICS = frozenset(
    {
        "trade_volume_usd",
        "trade_count",
        "transfer_count",
        "bridge_inflow_units",
        "bridge_outflow_units",
    }
)
METRIC_UNITS = {
    "liquidity_usd": "usd",
    "trade_volume_usd": "usd",
    "trade_count": "count",
    "transfer_count": "count",
    "holder_count": "count",
    "price_usd": "usd_per_token",
    "bridge_inflow_units": "token_units",
    "bridge_outflow_units": "token_units",
}
METRIC_SEMANTICS = {
    "liquidity_usd": "liquidity_snapshot",
    "trade_volume_usd": "executed_trade_volume",
    "trade_count": "executed_trade_count",
    "transfer_count": "token_transfer_count",
    "holder_count": "holder_snapshot",
    "bridge_inflow_units": "bridge_inflow",
    "bridge_outflow_units": "bridge_outflow",
}
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _timestamp(value: Any, field: str) -> datetime:
    text = _required_text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed


def _timestamp_text(value: Any, field: str) -> str:
    _timestamp(value, field)
    return _required_text(value, field)


def _nonnegative_decimal(value: Any, field: str) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative finite number") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field} must be a non-negative finite number")
    return format(parsed, "f")


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        parsed = int(value)
        original = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if parsed < 0 or original != Decimal(parsed):
        raise ValueError(f"{field} must be a non-negative integer")
    return parsed


def _token_endpoint(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    chain = _required_text(value.get("chain"), f"{field}.chain").casefold()
    asset_id = _required_text(value.get("asset_id"), f"{field}.asset_id")
    kind = _required_text(value.get("asset_id_kind"), f"{field}.asset_id_kind").casefold()
    if kind in DISALLOWED_ID_KINDS:
        raise ValueError(f"{field}.asset_id_kind cannot use label identity")
    return {"chain": chain, "asset_id": asset_id, "asset_id_kind": kind}


def _bind_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("tokenized_equity_provenance must be a mapping")
    if value.get("contract") != TOKENIZED_EQUITY_PROVENANCE_CONTRACT:
        raise ValueError(
            "tokenized_equity_provenance must use accepted tokenized_equity_provenance/v1"
        )
    if value.get("execution_authorized") is not False:
        raise ValueError("tokenized_equity_provenance must preserve execution_authorized=false")
    verification = value.get("verification")
    if not isinstance(verification, Mapping) or verification.get(
        "exact_token_identity_structurally_bound"
    ) is not True:
        raise ValueError("accepted tokenized-equity token identity must be structurally bound")
    return {
        "contract": TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
        "token": _token_endpoint(value.get("token"), "tokenized_equity_provenance.token"),
        "underlying_security": deepcopy(value.get("underlying_security")),
        "representation": deepcopy(value.get("representation")),
    }


def _scope(value: Any, *, token: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("scope must be a mapping")
    kind = _required_text(value.get("scope_kind"), "scope.scope_kind").casefold()
    if kind not in SCOPE_KINDS:
        raise ValueError("scope.scope_kind is not accepted")
    chain = _required_text(value.get("chain"), "scope.chain").casefold()
    if chain != token["chain"]:
        raise ValueError("scope.chain must equal tokenized-equity token chain")
    scope_id_kind = _required_text(value.get("scope_id_kind"), "scope.scope_id_kind").casefold()
    if scope_id_kind in DISALLOWED_ID_KINDS:
        raise ValueError("scope.scope_id_kind cannot use label identity")
    program_id = str(value.get("program_id") or "").strip() or None
    if kind in {"venue", "pool"} and program_id is None:
        raise ValueError("venue/pool scope requires exact program_id")
    return {
        "scope_kind": kind,
        "chain": chain,
        "scope_id": _required_text(value.get("scope_id"), "scope.scope_id"),
        "scope_id_kind": scope_id_kind,
        "program_id": program_id,
        "coverage_complete_for_scope": value.get("coverage_complete_for_scope") is True,
        "coverage_basis": _required_text(value.get("coverage_basis"), "scope.coverage_basis"),
    }


def _source(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    source_class = _required_text(value.get("source_class"), f"{field}.source_class").casefold()
    if source_class not in SOURCE_CLASSES:
        raise ValueError(f"{field}.source_class is not accepted")
    source_url = _required_text(value.get("source_url"), f"{field}.source_url")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field}.source_url must be an absolute https URL")
    digest = _required_text(value.get("content_sha256"), f"{field}.content_sha256").casefold()
    if not _HASH_RE.fullmatch(digest):
        raise ValueError(f"{field}.content_sha256 must be 64 lowercase hex characters")
    return {
        "provider_id": _required_text(value.get("provider_id"), f"{field}.provider_id"),
        "source_class": source_class,
        "source_url": source_url,
        "observation_id": _required_text(value.get("observation_id"), f"{field}.observation_id"),
        "retrieved_at": _timestamp_text(value.get("retrieved_at"), f"{field}.retrieved_at"),
        "content_sha256": digest,
        "transaction_id": str(value.get("transaction_id") or "").strip() or None,
    }


def _metric(
    value: Any,
    *,
    name: str,
    scope: Mapping[str, Any],
    evaluated_at: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"metrics.{name} must be a mapping")
    state = _required_text(value.get("state"), f"metrics.{name}.state").upper()
    if state not in OBSERVATION_STATES:
        raise ValueError(f"metrics.{name}.state is not accepted")
    semantic = _required_text(value.get("semantic"), f"metrics.{name}.semantic").casefold()
    if name == "price_usd":
        if semantic not in PRICE_SEMANTICS:
            raise ValueError("metrics.price_usd.semantic is not accepted")
    elif semantic != METRIC_SEMANTICS[name]:
        raise ValueError(f"metrics.{name}.semantic must be {METRIC_SEMANTICS[name]}")

    if state != "OBSERVED":
        if value.get("value") is not None or value.get("sources"):
            raise ValueError(f"metrics.{name} {state} state cannot carry observed value/sources")
        return {
            "metric": name,
            "state": state,
            "semantic": semantic,
            "value": None,
            "unit": METRIC_UNITS[name],
            "fact_time": None,
            "window": None,
            "sources": [],
            "freshness": {
                "state": "UNKNOWN",
                "age_seconds": None,
                "max_age_seconds": max_age_seconds,
            },
            "bounded_zero_observed": False,
        }

    metric_value: Any
    if name in {"trade_count", "transfer_count", "holder_count"}:
        metric_value = _nonnegative_int(value.get("value"), f"metrics.{name}.value")
    else:
        metric_value = _nonnegative_decimal(value.get("value"), f"metrics.{name}.value")

    raw_sources = value.get("sources")
    if (
        not isinstance(raw_sources, Sequence)
        or isinstance(raw_sources, (str, bytes))
        or not raw_sources
    ):
        raise ValueError(f"metrics.{name}.sources must be a non-empty sequence")
    sources = [
        _source(item, f"metrics.{name}.sources[{index}]")
        for index, item in enumerate(raw_sources)
    ]

    if name in WINDOW_METRICS:
        start_text = _timestamp_text(value.get("window_start"), f"metrics.{name}.window_start")
        end_text = _timestamp_text(value.get("window_end"), f"metrics.{name}.window_end")
        start = _timestamp(start_text, f"metrics.{name}.window_start")
        fact_dt = _timestamp(end_text, f"metrics.{name}.window_end")
        if start >= fact_dt:
            raise ValueError(f"metrics.{name} window_start must be before window_end")
        fact_time = end_text
        window = {
            "start": start_text,
            "end": end_text,
            "seconds": int((fact_dt - start).total_seconds()),
        }
    else:
        fact_time = _timestamp_text(value.get("fact_time"), f"metrics.{name}.fact_time")
        fact_dt = _timestamp(fact_time, f"metrics.{name}.fact_time")
        window = None

    if fact_dt > evaluated_at:
        raise ValueError(f"metrics.{name} fact time cannot be in the future")
    age = (evaluated_at - fact_dt).total_seconds()
    freshness_state = "FRESH" if age <= max_age_seconds else "STALE"

    if name == "price_usd" and semantic == "executed_trade_price":
        if not any(
            source["transaction_id"]
            and source["source_class"] in {"onchain_rpc", "indexer"}
            for source in sources
        ):
            raise ValueError(
                "executed_trade_price requires transaction-bound on-chain/indexer evidence"
            )

    is_zero = Decimal(str(metric_value)) == 0
    return {
        "metric": name,
        "state": state,
        "semantic": semantic,
        "value": metric_value,
        "unit": METRIC_UNITS[name],
        "fact_time": fact_time,
        "window": window,
        "sources": sources,
        "freshness": {
            "state": freshness_state,
            "age_seconds": age,
            "max_age_seconds": max_age_seconds,
        },
        "bounded_zero_observed": bool(
            is_zero and scope["coverage_complete_for_scope"]
        ),
    }


def build_tokenized_equity_market_activity(
    *,
    tokenized_equity_provenance: Any,
    scope: Any,
    metrics: Any,
    evaluated_at: Any,
    max_age_seconds: Any = 300,
) -> dict[str, Any]:
    """Build one bounded market-activity record for a tokenized equity."""

    provenance = _bind_provenance(tokenized_equity_provenance)
    exact_scope = _scope(scope, token=provenance["token"])
    evaluated = _timestamp(evaluated_at, "evaluated_at")
    max_age = _nonnegative_int(max_age_seconds, "max_age_seconds")
    if max_age == 0:
        raise ValueError("max_age_seconds must be greater than zero")
    if not isinstance(metrics, Mapping):
        raise ValueError("metrics must be a mapping")
    supplied, required = set(metrics.keys()), set(REQUIRED_METRICS)
    missing, extra = sorted(required - supplied), sorted(supplied - required)
    if missing:
        raise ValueError(f"metrics missing required entries: {', '.join(missing)}")
    if extra:
        raise ValueError(f"metrics contains unsupported entries: {', '.join(extra)}")

    observations = {
        name: _metric(
            metrics[name],
            name=name,
            scope=exact_scope,
            evaluated_at=evaluated,
            max_age_seconds=max_age,
        )
        for name in REQUIRED_METRICS
    }
    observed_count = sum(item["state"] == "OBSERVED" for item in observations.values())
    stale_count = sum(item["freshness"]["state"] == "STALE" for item in observations.values())

    return {
        "contract": TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
        "provenance": provenance,
        "scope": exact_scope,
        "metrics": observations,
        "summary": {
            "metric_count": len(REQUIRED_METRICS),
            "observed_metric_count": observed_count,
            "stale_metric_count": stale_count,
        },
        "verification": {
            "accepted_tokenized_equity_provenance_bound": True,
            "exact_scope_identity_bound": True,
            "metric_semantics_kept_separate": True,
            "scope_coverage_declared_complete": exact_scope["coverage_complete_for_scope"],
            "global_market_coverage_verified": False,
            "live_x1_equity_deployment_verified": False,
            "live_robinhood_x1_route_verified": False,
        },
        "boundaries": {
            "liquidity_equals_volume": False,
            "transfer_equals_trade": False,
            "bridge_flow_equals_exchange_volume": False,
            "bridge_flow_proves_adoption": False,
            "quoted_or_reference_price_equals_executed_price": False,
            "bounded_zero_equals_global_zero": False,
            "holder_count_proves_beneficial_owners": False,
            "market_activity_proves_shareholder_rights": False,
            "automatic_manipulation_conclusion_authorized": False,
            "automatic_insider_or_whale_conclusion_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "DEFAULT_EXECUTION_AUTHORIZED",
    "METRIC_SEMANTICS",
    "METRIC_UNITS",
    "OBSERVATION_STATES",
    "PRICE_SEMANTICS",
    "REQUIRED_METRICS",
    "SCOPE_KINDS",
    "SOURCE_CLASSES",
    "TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT",
    "build_tokenized_equity_market_activity",
]
