"""Deterministic XDEX endpoint discovery beneath CMIS Web Discovery.

This module recognizes only the already accepted read-only XDEX API surfaces
and XDEX documentation host. It validates endpoint/query syntax and produces
explicit handoffs to existing CMIS XDEX provider/evidence code.

It does not fetch the endpoint, reinterpret provider fields, select routes,
prepare swaps, or promote a fresh provider response into CMIS truth.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, unquote, urlparse

from liquidity_scout.providers.x1.xdex import (
    POOL_LIST_URL,
    PRICE_HISTORY_URL,
    SWAP_QUOTE_URL,
    TOKEN_PRICE_URL,
    XDEX_NETWORK_X1_MAINNET,
    XDEX_POOL_NETWORK_MAINNET,
)

from .base import DISCOVERED
from .xdex import XDEX_WEB_SOURCE


STRUCTURED_CONTRACT = "xdex_structured_discovery/v1"

X1PAYS_CORROBORATION_REPOSITORY = "Xenian84/x1pays"
X1PAYS_CORROBORATION_REF = "main"
X1PAYS_CORROBORATION_COMMIT = "73497fbc5b44ff63c4712094f653fff440ec1b5c"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}

_ENDPOINTS = {
    urlparse(POOL_LIST_URL).path: "pool_list",
    urlparse(TOKEN_PRICE_URL).path: "token_price",
    urlparse(PRICE_HISTORY_URL).path: "price_history",
    urlparse(SWAP_QUOTE_URL).path: "swap_quote",
}

_REQUIRED_PARAMS = {
    "pool_list": frozenset({"network"}),
    "token_price": frozenset({"network", "token_address"}),
    "price_history": frozenset(
        {"network", "from_token", "to_token", "time_from", "time_to"}
    ),
    "swap_quote": frozenset(
        {
            "network",
            "token_in",
            "token_out",
            "token_in_amount",
            "is_exact_amount_in",
        }
    ),
}

_OPTIONAL_PARAMS = {
    "pool_list": frozenset(),
    "token_price": frozenset(),
    "price_history": frozenset(),
    "swap_quote": frozenset({"slippage"}),
}


class XDEXStructuredDiscoveryError(ValueError):
    """Raised when XDEX structured-discovery input is malformed."""


def _base58_decoded_length(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None

    number = 0
    leading_zeros = 0
    for index, char in enumerate(text):
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            return None
        if index == leading_zeros and char == "1":
            leading_zeros += 1
        number = number * 58 + digit

    payload_length = (number.bit_length() + 7) // 8 if number else 0
    return leading_zeros + payload_length


def _valid_pubkey(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if _base58_decoded_length(text) != 32:
        return None
    return text


def _positive_integer(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        return None
    parsed = int(text)
    return parsed if parsed > 0 else None


def _positive_decimal(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return format(parsed, "f")


def _boolean_text(value: Any) -> bool | None:
    text = str(value or "").strip().casefold()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def _query_map(query: str) -> tuple[dict[str, str], str | None]:
    pairs = parse_qsl(query, keep_blank_values=True)
    result: dict[str, str] = {}
    for key, value in pairs:
        normalized_key = str(key).strip()
        if not normalized_key:
            return {}, "empty_query_parameter_name"
        if normalized_key in result:
            return {}, "duplicate_query_parameter"
        result[normalized_key] = str(value)
    return result, None


def _truth_state(*, route_verified: bool) -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "xdex_route_verified": route_verified,
        "provider_response_verified": False,
        "pool_identity_verified": False,
        "quote_semantics_verified": False,
        "history_semantics_verified": False,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
    }


def _implementation_evidence() -> dict[str, Any]:
    return {
        "cmis_provider_contract": {
            "module": "liquidity_scout.providers.x1.xdex",
            "role": "accepted_cmis_read_only_transport",
            "fresh_response_semantics_verified": False,
        },
        "third_party_corroboration": {
            "repository": X1PAYS_CORROBORATION_REPOSITORY,
            "ref": X1PAYS_CORROBORATION_REF,
            "commit": X1PAYS_CORROBORATION_COMMIT,
            "role": "third_party_xdex_program_pool_layout_corroboration",
            "independent_market_data_source": False,
            "xdex_api_deployment_semantics_verified": False,
        },
    }


def _unsupported(
    *,
    url: str,
    reason: str,
    endpoint_type: str | None = None,
    raw_query: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": False,
        "reason": reason,
        "url": url,
        "endpoint_type": endpoint_type,
        "parameters": None,
        "raw_query": dict(raw_query or {}),
        "verification_handoff": [],
        "implementation_evidence": _implementation_evidence(),
        "truth_state": _truth_state(route_verified=False),
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _handoff(endpoint_type: str) -> list[dict[str, Any]]:
    if endpoint_type == "pool_list":
        return [
            {
                "target": "XDEXReadOnlyProvider.pool_list",
                "purpose": "fetch raw accepted XDEX pool-list response",
                "required": True,
            },
            {
                "target": "X1 RPC / accepted XDEX pool-program verification",
                "purpose": "verify exact pool/program/config/vault identity before promotion",
                "required": False,
            },
        ]
    if endpoint_type == "token_price":
        return [
            {
                "target": "XDEXReadOnlyProvider.token_price",
                "purpose": "fetch raw XDEX token-price payload",
                "required": True,
            },
            {
                "target": "existing CMIS price/evidence semantic gates",
                "purpose": "verify exact field identity/freshness before promotion",
                "required": True,
            },
        ]
    if endpoint_type == "price_history":
        return [
            {
                "target": "XDEXReadOnlyProvider.price_history",
                "purpose": "fetch raw compact XDEX history bars",
                "required": True,
            },
            {
                "target": "accepted XDEX history semantic evidence",
                "purpose": "apply scoped timestamp/OHLC/coverage limitations",
                "required": True,
            },
        ]
    if endpoint_type == "swap_quote":
        return [
            {
                "target": "XDEXReadOnlyProvider.swap_quote",
                "purpose": "fetch raw read-only XDEX quote",
                "required": True,
            },
            {
                "target": "existing XDEX route/config/reserve/quote semantic verification",
                "purpose": "verify exact route-scoped quote fields before promotion",
                "required": True,
            },
        ]
    if endpoint_type == "documentation":
        return [
            {
                "target": "CMIS Web Discovery XDEX documentation evidence",
                "purpose": "retain documentation statement as corroborating candidate only",
                "required": False,
            }
        ]
    raise XDEXStructuredDiscoveryError(
        f"unsupported endpoint_type {endpoint_type!r}"
    )


def _supported(
    *,
    url: str,
    endpoint_type: str,
    parameters: dict[str, Any],
    raw_query: dict[str, str],
) -> dict[str, Any]:
    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": True,
        "reason": None,
        "url": url,
        "endpoint_type": endpoint_type,
        "parameters": parameters,
        "raw_query": raw_query,
        "verification_handoff": _handoff(endpoint_type),
        "implementation_evidence": _implementation_evidence(),
        "truth_state": _truth_state(route_verified=True),
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _validate_endpoint_query(
    endpoint_type: str,
    query: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    required = _REQUIRED_PARAMS[endpoint_type]
    allowed = required | _OPTIONAL_PARAMS[endpoint_type]

    missing = sorted(required - set(query))
    if missing:
        return None, "missing_required_query_parameter"

    unknown = sorted(set(query) - allowed)
    if unknown:
        return None, "unknown_query_parameter"

    if any(not str(query[key]).strip() for key in required):
        return None, "empty_required_query_parameter"

    network = str(query["network"]).strip()
    parameters: dict[str, Any] = {
        "network": network,
        "recognized_network": network
        in {XDEX_NETWORK_X1_MAINNET, XDEX_POOL_NETWORK_MAINNET},
    }

    if endpoint_type == "pool_list":
        return parameters, None

    if endpoint_type == "token_price":
        token = _valid_pubkey(query["token_address"])
        if token is None:
            return None, "token_address_must_decode_to_32_bytes"
        parameters["token_address"] = token
        return parameters, None

    if endpoint_type == "price_history":
        from_token = _valid_pubkey(query["from_token"])
        to_token = _valid_pubkey(query["to_token"])
        if from_token is None:
            return None, "from_token_must_decode_to_32_bytes"
        if to_token is None:
            return None, "to_token_must_decode_to_32_bytes"
        if from_token == to_token:
            return None, "history_tokens_must_differ"

        time_from = _positive_integer(query["time_from"])
        time_to = _positive_integer(query["time_to"])
        if time_from is None or time_to is None:
            return None, "history_times_must_be_positive_integers"
        if time_to <= time_from:
            return None, "time_to_must_be_greater_than_time_from"

        parameters.update(
            {
                "from_token": from_token,
                "to_token": to_token,
                "time_from": time_from,
                "time_to": time_to,
            }
        )
        return parameters, None

    if endpoint_type == "swap_quote":
        token_in = _valid_pubkey(query["token_in"])
        token_out = _valid_pubkey(query["token_out"])
        if token_in is None:
            return None, "token_in_must_decode_to_32_bytes"
        if token_out is None:
            return None, "token_out_must_decode_to_32_bytes"
        if token_in == token_out:
            return None, "quote_tokens_must_differ"

        amount = _positive_decimal(query["token_in_amount"])
        if amount is None:
            return None, "token_in_amount_must_be_positive_finite_decimal"

        exact_in = _boolean_text(query["is_exact_amount_in"])
        if exact_in is None:
            return None, "is_exact_amount_in_must_be_boolean_text"

        parameters.update(
            {
                "token_in": token_in,
                "token_out": token_out,
                "token_in_amount": amount,
                "is_exact_amount_in": exact_in,
            }
        )

        if "slippage" in query:
            raw_slippage = str(query["slippage"]).strip()
            if not raw_slippage:
                return None, "slippage_must_not_be_empty"
            parameters["slippage_raw"] = raw_slippage
            parameters["slippage_semantics_verified_by_structured_layer"] = False

        return parameters, None

    raise XDEXStructuredDiscoveryError(
        f"unsupported endpoint_type {endpoint_type!r}"
    )


def parse_xdex_url(url: str) -> dict[str, Any]:
    """Classify one allowlisted XDEX API/docs URL without fetching it."""

    normalized = XDEX_WEB_SOURCE.validate_url(url)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").casefold()

    query, query_error = _query_map(parsed.query)
    if query_error is not None:
        return _unsupported(
            url=normalized,
            reason=query_error,
            raw_query=query,
        )

    if host == "xdexdocs.gitbook.io":
        if not parsed.path.startswith("/xdex"):
            return _unsupported(
                url=normalized,
                reason="unsupported_xdex_documentation_path",
                raw_query=query,
            )
        if query:
            return _unsupported(
                url=normalized,
                reason="documentation_query_parameters_not_supported",
                endpoint_type="documentation",
                raw_query=query,
            )
        return _supported(
            url=normalized,
            endpoint_type="documentation",
            parameters={
                "path": unquote(parsed.path),
                "documentation_semantics_verified": False,
            },
            raw_query={},
        )

    endpoint_type = _ENDPOINTS.get(parsed.path)
    if endpoint_type is None:
        return _unsupported(
            url=normalized,
            reason="unsupported_xdex_api_path",
            raw_query=query,
        )

    parameters, error = _validate_endpoint_query(endpoint_type, query)
    if error is not None or parameters is None:
        return _unsupported(
            url=normalized,
            reason=error or "invalid_xdex_query",
            endpoint_type=endpoint_type,
            raw_query=query,
        )

    return _supported(
        url=normalized,
        endpoint_type=endpoint_type,
        parameters=parameters,
        raw_query=query,
    )


__all__ = [
    "STRUCTURED_CONTRACT",
    "X1PAYS_CORROBORATION_COMMIT",
    "X1PAYS_CORROBORATION_REF",
    "X1PAYS_CORROBORATION_REPOSITORY",
    "XDEXStructuredDiscoveryError",
    "parse_xdex_url",
]
