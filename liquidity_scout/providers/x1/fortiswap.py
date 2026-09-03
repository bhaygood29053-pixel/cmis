"""Bounded read-only FortiSwap X1 provider evidence for CMIS.

FortiSwap is a third-party execution/router provider.  This module only:
- captures its free x402 discovery catalogue;
- enforces an explicit read-only observation allowlist; and
- normalizes already-obtained token, volume, and quote responses.

It does not implement x402 payment, API-key management, transaction building,
signing, broadcasting, custody, swaps, or bridge execution.  FortiSwap trust,
confidence, safety, and warning fields remain provider assertions and never
become CMIS verification or risk truth by themselves.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlsplit

import requests


CHAIN = "x1"
NETWORK = "x1-mainnet"
FORTISWAP_BASE_URL = "https://app.fortiblox.com"
FORTISWAP_SOURCE = "app.fortiblox.com"
FORTISWAP_HOST = "app.fortiblox.com"
FORTISWAP_DISCOVERY_PATH = "/api/x402/discovery"

READ_ONLY_ROUTE_TEMPLATES = frozenset(
    {
        ("GET", "/api/tokens"),
        ("GET", "/api/token/:mint"),
        ("GET", "/api/router/volume"),
        ("POST", "/api/quote"),
    }
)
EXECUTION_ROUTE_TEMPLATES = frozenset(
    {
        ("POST", "/api/tx/build"),
        ("POST", "/api/tx/send"),
        ("POST", "/api/tx/status"),
    }
)

_TOKEN_DETAIL_RE = re.compile(r"^/api/token/[^/?#]+$")


class FortiSwapAPIError(RuntimeError):
    """Raised when FortiSwap evidence cannot be safely normalized."""


def _require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FortiSwapAPIError(f"{label} must be a JSON object.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise FortiSwapAPIError(f"{label} must be a JSON list.")
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _finite_number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return parsed


def _raw_amount(value: Any, *, field: str, required: bool = False) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise FortiSwapAPIError(f"{field} is required.")
        return None
    if not text.isdigit():
        raise FortiSwapAPIError(f"{field} must be a non-negative raw-unit integer string.")
    return text


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _normalize_method(value: Any) -> str | None:
    method = _text(value)
    return method.upper() if method else None


def _route_template_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    path = parsed.path
    if path == "/api/tokens":
        return path
    if path == "/api/router/volume":
        return path
    if path == "/api/quote":
        return path
    if path == "/api/tx/build":
        return path
    if path == "/api/tx/send":
        return path
    if path == "/api/tx/status":
        return path
    if _TOKEN_DETAIL_RE.match(path):
        return "/api/token/:mint"
    return path or None


def _discovery_field(item: Mapping[str, Any], key: str) -> Any:
    if key in item:
        return item.get(key)
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping) and key in metadata:
        return metadata.get(key)
    bazaar = item.get("bazaar")
    if isinstance(bazaar, Mapping) and key in bazaar:
        return bazaar.get(key)
    extensions = item.get("extensions")
    if isinstance(extensions, Mapping):
        bazaar_ext = extensions.get("bazaar")
        if isinstance(bazaar_ext, Mapping):
            info = bazaar_ext.get("info")
            if isinstance(info, Mapping) and key in info:
                return info.get(key)
    return None


def classify_route(method: Any, route_or_url: Any) -> dict[str, Any]:
    """Classify one FortiSwap route under the CMIS read-only boundary."""

    normalized_method = _normalize_method(method)
    route_text = _text(route_or_url)
    route_template = _route_template_from_url(route_text)
    if route_text and route_text.startswith("/") and ":" in route_text:
        route_template = route_text

    key = (normalized_method or "", route_template or "")
    if key in READ_ONLY_ROUTE_TEMPLATES:
        return {
            "method": normalized_method,
            "route_template": route_template,
            "status": "allowed_read_only",
            "analysis_only": True,
            "execution_authorized": False,
        }
    if key in EXECUTION_ROUTE_TEMPLATES:
        return {
            "method": normalized_method,
            "route_template": route_template,
            "status": "blocked_execution",
            "analysis_only": True,
            "execution_authorized": False,
        }
    return {
        "method": normalized_method,
        "route_template": route_template,
        "status": "unqualified",
        "analysis_only": True,
        "execution_authorized": False,
    }


def require_read_only_route(method: Any, route_or_url: Any) -> dict[str, Any]:
    result = classify_route(method, route_or_url)
    if result["status"] != "allowed_read_only":
        raise FortiSwapAPIError(
            "FortiSwap route is not in the CMIS read-only observation allowlist: "
            f"{result['method']} {result['route_template']}"
        )
    return result


def normalize_discovery_catalog(payload: Any) -> dict[str, Any]:
    """Normalize the provider-owned x402 discovery catalogue.

    Unknown/new routes are retained but remain unqualified.  A new route never
    becomes callable merely because it appears in FortiSwap discovery.
    """

    payload = _require_object(payload, "FortiSwap discovery response")
    items_value = payload.get("items")
    if items_value is None:
        items_value = payload.get("resources")
    items = _require_list(items_value, "FortiSwap discovery items")

    normalized: list[dict[str, Any]] = []
    for raw_item in items:
        item = _require_object(raw_item, "FortiSwap discovery item")
        method = _discovery_field(item, "method")
        route_template = _text(_discovery_field(item, "routeTemplate"))

        resource_value = item.get("resource")
        if isinstance(resource_value, Mapping):
            resource_url = _text(resource_value.get("url"))
        else:
            resource_url = _text(resource_value)

        if not route_template:
            route_template = _route_template_from_url(resource_url)

        resource_host_verified = False
        if resource_url:
            parsed_resource = urlsplit(resource_url)
            resource_host_verified = (
                parsed_resource.scheme.casefold() == "https"
                and (parsed_resource.hostname or "").casefold() == FORTISWAP_HOST
            )

        route_policy = classify_route(method, route_template or resource_url)
        qualification = route_policy["status"]
        if qualification == "allowed_read_only" and not resource_host_verified:
            qualification = "unqualified"

        accepts = item.get("accepts")
        if accepts is not None and not isinstance(accepts, list):
            raise FortiSwapAPIError("FortiSwap discovery accepts must be a JSON list.")

        normalized.append(
            {
                "method": route_policy["method"],
                "route_template": route_policy["route_template"],
                "resource_url": resource_url,
                "qualification": qualification,
                "resource_host_verified": resource_host_verified,
                "analysis_only": True,
                "execution_authorized": False,
                "accepts": list(accepts or []),
                "schema_hash_sha256": _canonical_hash(
                    {
                        "method": method,
                        "routeTemplate": route_template,
                        "inputSchema": _discovery_field(item, "inputSchema"),
                        "outputSchema": _discovery_field(item, "outputSchema"),
                        "bodySchema": _discovery_field(item, "bodySchema"),
                    }
                ),
                "provider_item_hash_sha256": _canonical_hash(dict(item)),
                "raw": dict(item),
            }
        )

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "source": FORTISWAP_SOURCE,
        "scope": "fortiswap_x402_discovery",
        "x402_version": payload.get("x402Version"),
        "catalog_hash_sha256": _canonical_hash(dict(payload)),
        "items": normalized,
        "allowed_read_only_count": sum(
            1 for item in normalized if item["qualification"] == "allowed_read_only"
        ),
        "execution_authorized": False,
        "analysis_only": True,
        "bridge_semantics_verified": False,
    }


def _normalize_token(record: Any) -> dict[str, Any]:
    record = _require_object(record, "FortiSwap token record")
    mint = _text(record.get("mint"))
    if not mint:
        raise FortiSwapAPIError("FortiSwap token record is missing mint.")
    decimals = _nonnegative_int(record.get("decimals"))
    if decimals is None:
        raise FortiSwapAPIError("FortiSwap token record is missing valid decimals.")

    return {
        "mint": mint,
        "symbol": _text(record.get("symbol")),
        "name": _text(record.get("name")),
        "decimals": decimals,
        "price_usd": _finite_number(record.get("priceUsd")),
        "volume_24h_usd": _finite_number(record.get("volume24hUsd")),
        "market_cap_usd": _finite_number(record.get("marketCapUsd")),
        "fdv_usd": _finite_number(record.get("fdvUsd")),
        "change_1h_pct": _finite_number(record.get("change1h")),
        "change_1d_pct": _finite_number(record.get("change1d")),
        "sources": list(record.get("sources") or [])
        if isinstance(record.get("sources"), list)
        else [],
        "provider_trust_claim": _text(record.get("trust")),
        "cmis_verified": False,
        "raw": dict(record),
    }


def normalize_tokens_response(payload: Any) -> dict[str, Any]:
    payload = _require_object(payload, "FortiSwap tokens response")
    tokens = [_normalize_token(item) for item in _require_list(payload.get("tokens"), "FortiSwap tokens")]
    updated_at = _nonnegative_int(payload.get("updatedAt"))
    if updated_at is None:
        raise FortiSwapAPIError("FortiSwap tokens response is missing valid updatedAt.")

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "source": FORTISWAP_SOURCE,
        "scope": "fortiswap_token_universe_observation",
        "provider_updated_at_ms": updated_at,
        "refreshing": payload.get("refreshing") if isinstance(payload.get("refreshing"), bool) else None,
        "warming": payload.get("warming") if isinstance(payload.get("warming"), bool) else None,
        "tokens": tokens,
        "errors": list(payload.get("errors") or [])
        if isinstance(payload.get("errors"), list)
        else [],
        "cmis_verified": False,
        "execution_authorized": False,
        "analysis_only": True,
    }


def normalize_token_detail_response(payload: Any) -> dict[str, Any]:
    payload = _require_object(payload, "FortiSwap token detail response")
    mint = _text(payload.get("mint"))
    if not mint:
        raise FortiSwapAPIError("FortiSwap token detail response is missing mint.")

    stats = payload.get("stats")
    if stats is not None and not isinstance(stats, Mapping):
        raise FortiSwapAPIError("FortiSwap token detail stats must be a JSON object.")
    pools = _require_list(payload.get("pools") or [], "FortiSwap token detail pools")
    updated_at = _nonnegative_int(payload.get("updatedAt"))
    if updated_at is None:
        raise FortiSwapAPIError("FortiSwap token detail response is missing valid updatedAt.")

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "source": FORTISWAP_SOURCE,
        "scope": "fortiswap_token_detail_observation",
        "mint": mint,
        "listed": payload.get("listed") if isinstance(payload.get("listed"), bool) else None,
        "symbol": _text(payload.get("symbol")),
        "name": _text(payload.get("name")),
        "decimals": _nonnegative_int(payload.get("decimals")),
        "price_usd": _finite_number(payload.get("priceUsd")),
        "change_24h_pct": _finite_number(payload.get("change24hPct")),
        "provider_trust_claim": _text(payload.get("trust")),
        "stats": dict(stats or {}),
        "about": dict(payload.get("about") or {})
        if isinstance(payload.get("about"), Mapping)
        else {},
        "pools": [dict(_require_object(pool, "FortiSwap pool record")) for pool in pools],
        "provider_updated_at_ms": updated_at,
        "cmis_verified": False,
        "execution_authorized": False,
        "analysis_only": True,
        "raw": dict(payload),
    }


def normalize_router_volume_response(payload: Any) -> dict[str, Any]:
    payload = _require_object(payload, "FortiSwap router volume response")
    if payload.get("ok") is not True:
        raise FortiSwapAPIError("FortiSwap router volume response is not ok.")

    days = _nonnegative_int(payload.get("days"))
    if days is None or not 1 <= days <= 365:
        raise FortiSwapAPIError("FortiSwap router volume days must be between 1 and 365.")

    buckets = [
        dict(_require_object(item, "FortiSwap router volume bucket"))
        for item in _require_list(payload.get("buckets"), "FortiSwap router volume buckets")
    ]
    totals = _require_object(payload.get("totals"), "FortiSwap router volume totals")
    updated_at = _nonnegative_int(payload.get("updatedAt"))
    if updated_at is None:
        raise FortiSwapAPIError("FortiSwap router volume response is missing valid updatedAt.")

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "source": FORTISWAP_SOURCE,
        "scope": "fortiblox_router_indexer_observation",
        "days": days,
        "from": _text(payload.get("from")),
        "to": _text(payload.get("to")),
        "buckets": buckets,
        "totals": dict(totals),
        "provider_updated_at_ms": updated_at,
        "provider_scope_note": "FortiBlox Router swaps observed by FortiBlox's own X1 indexer",
        "cmis_verified": False,
        "execution_authorized": False,
        "analysis_only": True,
    }


def normalize_quote_response(payload: Any) -> dict[str, Any]:
    payload = _require_object(payload, "FortiSwap quote response")
    input_mint = _text(payload.get("inputMint"))
    output_mint = _text(payload.get("outputMint"))
    if not input_mint or not output_mint:
        raise FortiSwapAPIError("FortiSwap quote is missing inputMint or outputMint.")

    mode = _text(payload.get("mode"))
    if mode not in {"exactIn", "exactOut"}:
        raise FortiSwapAPIError("FortiSwap quote mode must be exactIn or exactOut.")

    route_records = _require_list(payload.get("route"), "FortiSwap quote route")
    if not route_records:
        raise FortiSwapAPIError("FortiSwap quote route must contain at least one leg.")
    route: list[dict[str, Any]] = []
    for raw_leg in route_records:
        leg = _require_object(raw_leg, "FortiSwap quote route leg")
        route.append(
            {
                "venue": _text(leg.get("venue")),
                "pool_address": _text(leg.get("address")),
                "input_mint": _text(leg.get("inMint")),
                "output_mint": _text(leg.get("outMint")),
                "fee_ppm": _nonnegative_int(leg.get("feePpm")),
                "price_impact_pct": _finite_number(leg.get("priceImpactPct")),
                "amount_in_raw": _raw_amount(leg.get("amountIn"), field="route.amountIn"),
                "amount_out_raw": _raw_amount(leg.get("amountOut"), field="route.amountOut"),
                "raw": dict(leg),
            }
        )

    confidence = payload.get("confidence")
    safety = payload.get("safety")
    fee = payload.get("fee")
    if confidence is not None and not isinstance(confidence, Mapping):
        raise FortiSwapAPIError("FortiSwap quote confidence must be a JSON object.")
    if safety is not None and not isinstance(safety, Mapping):
        raise FortiSwapAPIError("FortiSwap quote safety must be a JSON object.")
    if fee is not None and not isinstance(fee, Mapping):
        raise FortiSwapAPIError("FortiSwap quote fee must be a JSON object.")

    return {
        "chain": CHAIN,
        "network": NETWORK,
        "source": FORTISWAP_SOURCE,
        "scope": "fortiswap_swap_quote_observation",
        "mode": mode,
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_in_raw": _raw_amount(payload.get("amountIn"), field="amountIn", required=mode == "exactIn"),
        "amount_out_raw": _raw_amount(
            payload.get("amountOut"),
            field="amountOut",
            required=mode == "exactOut",
        ),
        "amount_out_net_raw": _raw_amount(payload.get("amountOutNet"), field="amountOutNet"),
        "minimum_amount_out_raw": _raw_amount(payload.get("minimumAmountOut"), field="minimumAmountOut"),
        "slippage_bps": _nonnegative_int(payload.get("slippageBps")),
        "slippage_dynamic": payload.get("slippageDynamic")
        if isinstance(payload.get("slippageDynamic"), bool)
        else None,
        "price_impact_pct": _finite_number(payload.get("priceImpactPct")),
        "hops": _nonnegative_int(payload.get("hops")),
        "route": route,
        "fee_preview": dict(fee or {}),
        "provider_confidence_claim": dict(confidence or {}),
        "provider_safety_claim": dict(safety or {}),
        "provider_warnings": list(payload.get("warnings") or [])
        if isinstance(payload.get("warnings"), list)
        else [],
        "provider_high_impact_claim": payload.get("highImpact")
        if isinstance(payload.get("highImpact"), bool)
        else None,
        "provider_thin_liquidity_claim": payload.get("thinLiquidity")
        if isinstance(payload.get("thinLiquidity"), bool)
        else None,
        "as_of_slot": _nonnegative_int(payload.get("asOfSlot")),
        "valid_until_slot": _nonnegative_int(payload.get("validUntilSlot")),
        "ttl_ms": _nonnegative_int(payload.get("ttlMs")),
        "expires_at_ms": _nonnegative_int(payload.get("expiresAt")),
        "cmis_verified": False,
        "cmis_risk_promoted": False,
        "execution_authorized": False,
        "transaction_build_allowed": False,
        "analysis_only": True,
        "raw": dict(payload),
    }


def fetch_discovery(
    *,
    base_url: str = FORTISWAP_BASE_URL,
    timeout: int = 15,
    get=requests.get,
) -> dict[str, Any]:
    """Fetch only the free discovery catalogue; never a priced endpoint."""

    normalized_base = (_text(base_url) or "").rstrip("/")
    if not normalized_base:
        raise ValueError("FortiSwap base URL is required.")

    try:
        response = get(
            normalized_base + FORTISWAP_DISCOVERY_PATH,
            headers={"accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        return normalize_discovery_catalog(response.json())
    except FortiSwapAPIError:
        raise
    except Exception as exc:
        raise FortiSwapAPIError(f"FortiSwap discovery request failed: {exc}") from exc


class FortiSwapReadOnlyProvider:
    """CMIS facade for free discovery plus deterministic response normalization."""

    chain = CHAIN
    source = FORTISWAP_SOURCE

    def __init__(
        self,
        *,
        base_url: str = FORTISWAP_BASE_URL,
        timeout: int = 15,
        get=requests.get,
    ) -> None:
        self.base_url = (_text(base_url) or "").rstrip("/")
        self.timeout = timeout
        self.get = get
        if not self.base_url:
            raise ValueError("FortiSwap base URL is required.")

    def get_discovery(self) -> dict[str, Any]:
        return fetch_discovery(
            base_url=self.base_url,
            timeout=self.timeout,
            get=self.get,
        )

    @staticmethod
    def normalize_tokens(payload: Any) -> dict[str, Any]:
        return normalize_tokens_response(payload)

    @staticmethod
    def normalize_token_detail(payload: Any) -> dict[str, Any]:
        return normalize_token_detail_response(payload)

    @staticmethod
    def normalize_router_volume(payload: Any) -> dict[str, Any]:
        return normalize_router_volume_response(payload)

    @staticmethod
    def normalize_quote(payload: Any) -> dict[str, Any]:
        return normalize_quote_response(payload)


__all__ = [
    "CHAIN",
    "NETWORK",
    "FORTISWAP_BASE_URL",
    "FORTISWAP_DISCOVERY_PATH",
    "FORTISWAP_SOURCE",
    "FORTISWAP_HOST",
    "READ_ONLY_ROUTE_TEMPLATES",
    "EXECUTION_ROUTE_TEMPLATES",
    "FortiSwapAPIError",
    "FortiSwapReadOnlyProvider",
    "classify_route",
    "require_read_only_route",
    "normalize_discovery_catalog",
    "normalize_tokens_response",
    "normalize_token_detail_response",
    "normalize_router_volume_response",
    "normalize_quote_response",
    "fetch_discovery",
]
