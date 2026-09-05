"""Extended read-only XDEX structured discovery.

This contract covers the three direct GET surfaces identified by
xdex_network_gap_registry/v1:

- frontend quote alias: api.xdex.xyz/api/xdex/swap/quote
- XDEX Oracle token price: oracle.xdex.xyz/api/v1/token/price
- XDEX Oracle sell quote: oracle.xdex.xyz/api/v1/token/sell-quote

It validates only URL/query syntax and maps candidates back to existing CMIS
XDEX evidence. It does not fetch, prepare, sign, broadcast, or execute.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlparse

from .base import DISCOVERED
from .xdex import XDEX_WEB_SOURCE


EXTENDED_STRUCTURED_CONTRACT = "xdex_extended_readonly_structured_discovery/v1"

FRONTEND_QUOTE_ALIAS_PATH = "/api/xdex/swap/quote"
ORACLE_TOKEN_PRICE_PATH = "/api/v1/token/price"
ORACLE_SELL_QUOTE_PATH = "/api/v1/token/sell-quote"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}


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
    if not text or _base58_decoded_length(text) != 32:
        return None
    return text


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
        "xdex_extended_route_verified": route_verified,
        "provider_response_verified": False,
        "frontend_alias_equivalence_verified": False,
        "oracle_price_semantics_verified": False,
        "oracle_sell_quote_semantics_verified": False,
        "route_config_verified": False,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
    }


def _unsupported(
    *,
    url: str,
    endpoint_type: str | None,
    reason: str,
    raw_query: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "contract": EXTENDED_STRUCTURED_CONTRACT,
        "supported": False,
        "reason": reason,
        "url": url,
        "endpoint_type": endpoint_type,
        "parameters": None,
        "raw_query": dict(raw_query or {}),
        "verification_handoff": [],
        "truth_state": _truth_state(route_verified=False),
        "read_only": True,
        "request_replay_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _handoff(endpoint_type: str) -> list[dict[str, Any]]:
    if endpoint_type == "frontend_quote_alias":
        return [
            {
                "target": "existing XDEX read-only quote transport/evidence",
                "purpose": "retrieve/compare frontend alias without creating a second quote engine",
                "required": True,
            },
            {
                "target": "tests/test_xdex_frontend_quote_route_live.py",
                "purpose": "scoped frontend-vs-research alias equivalence evidence",
                "required": True,
            },
            {
                "target": "existing XDEX route/config/reserve/quote semantic verification",
                "purpose": "verify route-scoped quote fields before promotion",
                "required": True,
            },
        ]

    if endpoint_type == "oracle_token_price":
        return [
            {
                "target": ".github/workflows/xdex-oracle-price-evidence.yml",
                "purpose": "existing bounded XDEX Oracle price contract evidence",
                "required": True,
            },
            {
                "target": "existing CMIS asset identity / price freshness gates",
                "purpose": "verify any fresh price fact before promotion",
                "required": True,
            },
        ]

    if endpoint_type == "oracle_sell_quote":
        return [
            {
                "target": "tests/test_xdex_output_slippage_semantics_live.py",
                "purpose": "scoped no-fee CP curve-reference evidence",
                "required": True,
            },
            {
                "target": "docs/XDEX_OUTPUT_SLIPPAGE_RESEARCH.md",
                "purpose": "preserve fee/slippage/execution limitations",
                "required": True,
            },
        ]

    raise ValueError(f"unsupported endpoint_type {endpoint_type!r}")


def _supported(
    *,
    url: str,
    endpoint_type: str,
    parameters: dict[str, Any],
    raw_query: dict[str, str],
) -> dict[str, Any]:
    return {
        "contract": EXTENDED_STRUCTURED_CONTRACT,
        "supported": True,
        "reason": None,
        "url": url,
        "endpoint_type": endpoint_type,
        "parameters": parameters,
        "raw_query": raw_query,
        "verification_handoff": _handoff(endpoint_type),
        "truth_state": _truth_state(route_verified=True),
        "read_only": True,
        "request_replay_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _validate_frontend_quote(
    query: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    required = {
        "network",
        "token_in",
        "token_out",
        "token_in_amount",
        "is_exact_amount_in",
    }
    optional = {"slippage", "amm_config_address"}

    if required - set(query):
        return None, "missing_required_query_parameter"
    if set(query) - (required | optional):
        return None, "unknown_query_parameter"
    if any(not str(query[key]).strip() for key in required):
        return None, "empty_required_query_parameter"

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

    params: dict[str, Any] = {
        "network": str(query["network"]).strip(),
        "token_in": token_in,
        "token_out": token_out,
        "token_in_amount": amount,
        "is_exact_amount_in": exact_in,
    }

    if "slippage" in query:
        raw_slippage = str(query["slippage"]).strip()
        if not raw_slippage:
            return None, "slippage_must_not_be_empty"
        params["slippage_raw"] = raw_slippage
        params["slippage_semantics_verified_by_extended_layer"] = False

    if "amm_config_address" in query:
        config = _valid_pubkey(query["amm_config_address"])
        if config is None:
            return None, "amm_config_address_must_decode_to_32_bytes"
        params["amm_config_address"] = config
        params["route_config_verified"] = False

    return params, None


def _validate_oracle_price(
    query: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    keys = set(query)

    if keys == {"token_address"}:
        token = _valid_pubkey(query["token_address"])
        if token is None:
            return None, "token_address_must_decode_to_32_bytes"
        return {
            "mode": "exact_token",
            "token_address": token,
        }, None

    if keys == {"all", "details"}:
        all_value = _boolean_text(query["all"])
        details_value = _boolean_text(query["details"])
        if all_value is not True or details_value is not True:
            return None, "oracle_all_details_mode_requires_true_true"
        return {
            "mode": "all_details",
            "all": True,
            "details": True,
        }, None

    if not keys:
        return None, "missing_required_query_parameter"

    if "token_address" in keys and ({"all", "details"} & keys):
        return None, "oracle_price_modes_are_mutually_exclusive"

    return None, "unsupported_oracle_price_query_shape"


def _validate_oracle_sell_quote(
    query: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    required = {"token_address", "amount_in"}
    if required - set(query):
        return None, "missing_required_query_parameter"
    if set(query) - required:
        return None, "unknown_query_parameter"

    token = _valid_pubkey(query["token_address"])
    if token is None:
        return None, "token_address_must_decode_to_32_bytes"

    amount = _positive_decimal(query["amount_in"])
    if amount is None:
        return None, "amount_in_must_be_positive_finite_decimal"

    return {
        "token_address": token,
        "amount_in": amount,
        "known_semantic_scope": "no_fee_cp_curve_reference_for_tested_cases_only",
        "fee_complete": False,
        "slippage_adjusted": False,
        "executable_quote": False,
        "route_optimality_verified": False,
        "fill_quality_verified": False,
    }, None


def parse_xdex_extended_readonly_url(url: str) -> dict[str, Any]:
    """Parse one extended XDEX direct read-only URL without fetching it."""

    normalized = XDEX_WEB_SOURCE.validate_url(url)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").casefold()
    path = parsed.path or "/"

    query, query_error = _query_map(parsed.query)
    if query_error is not None:
        return _unsupported(
            url=normalized,
            endpoint_type=None,
            reason=query_error,
            raw_query=query,
        )

    if host == "api.xdex.xyz" and path == FRONTEND_QUOTE_ALIAS_PATH:
        params, error = _validate_frontend_quote(query)
        if error is not None or params is None:
            return _unsupported(
                url=normalized,
                endpoint_type="frontend_quote_alias",
                reason=error or "invalid_frontend_quote_query",
                raw_query=query,
            )
        return _supported(
            url=normalized,
            endpoint_type="frontend_quote_alias",
            parameters=params,
            raw_query=query,
        )

    if host == "oracle.xdex.xyz" and path == ORACLE_TOKEN_PRICE_PATH:
        params, error = _validate_oracle_price(query)
        if error is not None or params is None:
            return _unsupported(
                url=normalized,
                endpoint_type="oracle_token_price",
                reason=error or "invalid_oracle_price_query",
                raw_query=query,
            )
        return _supported(
            url=normalized,
            endpoint_type="oracle_token_price",
            parameters=params,
            raw_query=query,
        )

    if host == "oracle.xdex.xyz" and path == ORACLE_SELL_QUOTE_PATH:
        params, error = _validate_oracle_sell_quote(query)
        if error is not None or params is None:
            return _unsupported(
                url=normalized,
                endpoint_type="oracle_sell_quote",
                reason=error or "invalid_oracle_sell_quote_query",
                raw_query=query,
            )
        return _supported(
            url=normalized,
            endpoint_type="oracle_sell_quote",
            parameters=params,
            raw_query=query,
        )

    return _unsupported(
        url=normalized,
        endpoint_type=None,
        reason="unsupported_xdex_extended_readonly_path",
        raw_query=query,
    )


__all__ = [
    "EXTENDED_STRUCTURED_CONTRACT",
    "FRONTEND_QUOTE_ALIAS_PATH",
    "ORACLE_SELL_QUOTE_PATH",
    "ORACLE_TOKEN_PRICE_PATH",
    "parse_xdex_extended_readonly_url",
]
