"""Read-only Jupiter source adapters for Solana discovery and price evidence.

The adapter preserves Jupiter's source semantics without promoting them to CMIS
truth. Price V3 ``createdAt`` is token creation metadata, not a price observation
time. ``blockId`` is retained as provenance but does not by itself prove CMIS
freshness. Tokens V2 verification/organic labels remain provider opinions.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import math
import os
from typing import Any, Callable

import requests

CHAIN = "solana"
SOURCE_PRICE = "jupiter_price_v3"
SOURCE_TOKENS = "jupiter_tokens_v2"
DEFAULT_BASE_URL = "https://api.jup.ag"


class JupiterSourceError(RuntimeError):
    """Raised when a Jupiter response cannot satisfy the declared source contract."""


class JupiterNotConfigured(JupiterSourceError):
    """Raised when the current Jupiter API key contract is not configured."""


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JupiterSourceError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _nonnegative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise JupiterSourceError(f"{field} must be a non-negative integer")
    return value


def _u8(value: object, *, field: str) -> int:
    parsed = _nonnegative_int(value, field=field)
    if parsed > 255:
        raise JupiterSourceError(f"{field} must fit in u8")
    return parsed


def _decimal_text(
    value: object,
    *,
    field: str,
    allow_zero: bool = True,
    allow_negative: bool = False,
) -> str:
    if value is None or isinstance(value, bool):
        raise JupiterSourceError(f"{field} must be a finite numeric value")
    if isinstance(value, float) and not math.isfinite(value):
        raise JupiterSourceError(f"{field} must be a finite numeric value")
    if not isinstance(value, (int, float, str, Decimal)):
        raise JupiterSourceError(f"{field} must be a finite numeric value")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise JupiterSourceError(f"{field} must be a finite numeric value") from exc
    if not parsed.is_finite():
        raise JupiterSourceError(f"{field} must be a finite numeric value")
    if not allow_negative and parsed < 0:
        raise JupiterSourceError(f"{field} must not be negative")
    if not allow_zero and parsed <= 0:
        raise JupiterSourceError(f"{field} must be greater than zero")
    text = format(parsed, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _optional_decimal_text(
    value: object,
    *,
    field: str,
    allow_negative: bool = False,
) -> str | None:
    if value is None:
        return None
    return _decimal_text(value, field=field, allow_negative=allow_negative)


class JupiterSourceProvider:
    """Narrow Jupiter Price V3 + Tokens V2 source client.

    Current Jupiter Developer Platform documentation requires the ``x-api-key``
    header for Price V3 requests. This adapter therefore requires an explicit
    ``JUPITER_API_KEY`` (or constructor key) and fails closed when absent. The
    key is never included in returned provenance or error messages.
    """

    chain = CHAIN

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: int = 20,
        get: Callable[..., Any] = requests.get,
    ) -> None:
        self._base_url = _text(base_url, field="Jupiter base URL").rstrip("/")
        configured_key = api_key if api_key is not None else os.getenv("JUPITER_API_KEY")
        if not isinstance(configured_key, str) or not configured_key.strip():
            raise JupiterNotConfigured("JUPITER_API_KEY is required for Jupiter API access")
        self._api_key = configured_key.strip()
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        self.timeout = timeout
        self._get = get

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "x-api-key": self._api_key,
        }

    def _request(self, path: str, *, params: Mapping[str, object]) -> Any:
        path = _text(path, field="Jupiter path")
        transport_error_type: str | None = None
        try:
            response = self._get(
                f"{self._base_url}{path}",
                params=dict(params),
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except JupiterSourceError:
            raise
        except Exception as exc:
            # Capture only the exception class while inside the handler. The
            # original exception may contain a keyed URL, headers, or provider
            # response text, so it must not remain attached as cause/context.
            transport_error_type = type(exc).__name__

        raise JupiterSourceError(
            f"Jupiter request failed ({transport_error_type})"
        ) from None

    def get_price(self, mint: str) -> dict[str, Any]:
        """Return one Price V3 source observation or explicit unavailability."""

        mint = _text(mint, field="mint")
        body = self._request("/price/v3", params={"ids": mint})
        if not isinstance(body, Mapping):
            raise JupiterSourceError("Price V3 response must be an object")
        if mint not in body or body.get(mint) is None:
            return {
                "chain": CHAIN,
                "source": SOURCE_PRICE,
                "mint": mint,
                "price_available": False,
                "reason": "jupiter_price_unavailable",
                "freshness_verified": False,
            }

        entry = body.get(mint)
        if not isinstance(entry, Mapping):
            raise JupiterSourceError("Price V3 mint entry must be an object")

        price = _decimal_text(
            entry.get("usdPrice"),
            field="usdPrice",
            allow_zero=False,
        )
        block_id = _nonnegative_int(entry.get("blockId"), field="blockId")
        decimals = _u8(entry.get("decimals"), field="decimals")
        token_created_at = _optional_text(entry.get("createdAt"), field="createdAt")
        liquidity = _optional_decimal_text(entry.get("liquidity"), field="liquidity")
        price_change_24h = _optional_decimal_text(
            entry.get("priceChange24h"),
            field="priceChange24h",
            allow_negative=True,
        )

        return {
            "chain": CHAIN,
            "source": SOURCE_PRICE,
            "mint": mint,
            "price_available": True,
            "usd_price": price,
            "currency": "USD",
            "block_id": block_id,
            "decimals": decimals,
            "token_created_at": token_created_at,
            "liquidity_usd_source_value": liquidity,
            "price_change_24h_percent_source_value": price_change_24h,
            "scope": "jupiter_price_v3",
            "observed_at": None,
            "freshness_verified": False,
        }

    def get_token_by_mint(self, mint: str) -> dict[str, Any]:
        """Return one exact-mint Tokens V2 record without trusting source labels."""

        mint = _text(mint, field="mint")
        body = self._request("/tokens/v2/search", params={"query": mint})
        if not isinstance(body, list):
            raise JupiterSourceError("Tokens V2 search response must be an array")

        exact = [item for item in body if isinstance(item, Mapping) and item.get("id") == mint]
        if not exact:
            return {
                "chain": CHAIN,
                "source": SOURCE_TOKENS,
                "mint": mint,
                "token_available": False,
                "reason": "jupiter_token_not_found",
                "identity_verified": False,
            }
        if len(exact) != 1:
            raise JupiterSourceError("Tokens V2 returned duplicate exact mint records")

        item = exact[0]
        decimals = _u8(item.get("decimals"), field="token decimals")
        name = _optional_text(item.get("name"), field="token name")
        symbol = _optional_text(item.get("symbol"), field="token symbol")
        is_verified = item.get("isVerified")
        if is_verified is not None and not isinstance(is_verified, bool):
            raise JupiterSourceError("isVerified must be a boolean or null")
        holder_count = item.get("holderCount")
        if holder_count is not None:
            holder_count = _nonnegative_int(holder_count, field="holderCount")
        organic_score = _optional_decimal_text(item.get("organicScore"), field="organicScore")
        organic_label = _optional_text(item.get("organicScoreLabel"), field="organicScoreLabel")
        usd_price = _optional_decimal_text(item.get("usdPrice"), field="usdPrice")
        liquidity = _optional_decimal_text(item.get("liquidity"), field="liquidity")
        market_cap = _optional_decimal_text(item.get("mcap"), field="mcap")
        tags = item.get("tags")
        if tags is None:
            clean_tags: list[str] = []
        elif isinstance(tags, list) and all(isinstance(tag, str) and tag.strip() for tag in tags):
            clean_tags = list(dict.fromkeys(tag.strip() for tag in tags))
        else:
            raise JupiterSourceError("tags must be an array of non-empty strings or null")

        return {
            "chain": CHAIN,
            "source": SOURCE_TOKENS,
            "mint": mint,
            "token_available": True,
            "identity_verified": True,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "provider_is_verified": is_verified,
            "provider_organic_score": organic_score,
            "provider_organic_score_label": organic_label,
            "indexed_holder_count_candidate": holder_count,
            "holder_count_semantics_verified": False,
            "usd_price_source_value": usd_price,
            "liquidity_usd_source_value": liquidity,
            "market_cap_usd_source_value": market_cap,
            "tags": clean_tags,
            "provider_opinion_only": True,
        }


__all__ = [
    "CHAIN",
    "DEFAULT_BASE_URL",
    "JupiterNotConfigured",
    "JupiterSourceError",
    "JupiterSourceProvider",
    "SOURCE_PRICE",
    "SOURCE_TOKENS",
]
