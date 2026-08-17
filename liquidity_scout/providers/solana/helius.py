"""Read-only Helius DAS source adapter for Solana indexed evidence.

Helius is an indexed source, not canonical chain truth. ``last_indexed_slot`` is
preserved as coverage provenance. DAS price data is explicitly cached by Helius
(up to 600 seconds), so this adapter never marks it fresh automatically.
Token-account totals remain token-account counts and are never promoted to
unique holder counts.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import math
import os
from typing import Any, Callable
from urllib.parse import quote

import requests

CHAIN = "solana"
SOURCE = "helius_das"
DEFAULT_BASE_URL = "https://mainnet.helius-rpc.com/"
PRICE_CACHE_MAX_AGE_SECONDS = 600
TOKEN_BASE_UNITS = "TOKEN_BASE_UNITS"


class HeliusSourceError(RuntimeError):
    pass


class HeliusNotConfigured(HeliusSourceError):
    pass


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HeliusSourceError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _nonnegative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HeliusSourceError(f"{field} must be a non-negative integer")
    return value


def _u8(value: object, *, field: str) -> int:
    value = _nonnegative_int(value, field=field)
    if value > 255:
        raise HeliusSourceError(f"{field} must fit in u8")
    return value


def _optional_decimal(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise HeliusSourceError(f"{field} must be finite numeric data")
    if isinstance(value, float) and not math.isfinite(value):
        raise HeliusSourceError(f"{field} must be finite numeric data")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HeliusSourceError(f"{field} must be finite numeric data") from exc
    if not parsed.is_finite() or parsed < 0:
        raise HeliusSourceError(f"{field} must be finite non-negative numeric data")
    text = format(parsed, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class HeliusDASProvider:
    """Narrow Helius indexed-source client; requires an explicit API key."""

    chain = CHAIN

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 20,
        post: Callable[..., Any] = requests.post,
    ) -> None:
        configured = api_key if api_key is not None else os.getenv("HELIUS_API_KEY")
        if not isinstance(configured, str) or not configured.strip():
            raise HeliusNotConfigured("HELIUS_API_KEY is required for Helius DAS")
        self._api_key = configured.strip()
        self._base_url = _text(base_url, field="Helius base URL").rstrip("/") + "/"
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        self.timeout = timeout
        self._post = post
        self._request_id = 0

    def _request(self, method: str, params: Mapping[str, object]) -> Any:
        method = _text(method, field="Helius method")
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": str(self._request_id), "method": method, "params": dict(params)}
        url = f"{self._base_url}?api-key={quote(self._api_key, safe='')}"
        transport_error_type: str | None = None
        try:
            response = self._post(
                url,
                json=payload,
                headers={"content-type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            # The original exception may include the keyed RPC URL or provider
            # response text. Retain only its class and raise after the handler
            # exits so no secret-bearing cause/context survives.
            transport_error_type = type(exc).__name__
        if transport_error_type is not None:
            raise HeliusSourceError(
                f"Helius {method} transport failed ({transport_error_type})"
            ) from None
        if not isinstance(body, Mapping):
            raise HeliusSourceError(f"Helius {method} response must be an object")
        if body.get("error") is not None:
            error = body.get("error")
            code = error.get("code") if isinstance(error, Mapping) else None
            if code == -32004:
                return None
            raise HeliusSourceError(f"Helius {method} returned error code {code!r}")
        # DAS docs show getAsset wrapped in result, while getTokenAccounts examples
        # show the result object directly. Support only those two documented shapes.
        return body.get("result") if "result" in body else body

    def get_asset(self, mint: str) -> dict[str, Any]:
        mint = _text(mint, field="mint")
        result = self._request("getAsset", {"id": mint, "options": {"showFungible": True}})
        if result is None:
            return {"chain": CHAIN, "source": SOURCE, "mint": mint, "asset_available": False, "reason": "helius_asset_not_found"}
        if not isinstance(result, Mapping):
            raise HeliusSourceError("Helius getAsset result must be an object")
        if result.get("id") != mint:
            raise HeliusSourceError("Helius getAsset returned a different asset id")
        slot = _nonnegative_int(result.get("last_indexed_slot"), field="last_indexed_slot")
        token_info = result.get("token_info")
        if not isinstance(token_info, Mapping):
            raise HeliusSourceError("Helius getAsset token_info must be an object")
        supply = _nonnegative_int(token_info.get("supply"), field="token_info.supply")
        decimals = _u8(token_info.get("decimals"), field="token_info.decimals")
        token_program = _text(token_info.get("token_program"), field="token_info.token_program")
        mint_authority = _optional_text(token_info.get("mint_authority"), field="mint_authority")
        freeze_authority = _optional_text(token_info.get("freeze_authority"), field="freeze_authority")

        price_info = token_info.get("price_info")
        price: str | None = None
        currency: str | None = None
        if price_info is not None:
            if not isinstance(price_info, Mapping):
                raise HeliusSourceError("token_info.price_info must be an object or null")
            price = _optional_decimal(price_info.get("price_per_token"), field="price_per_token")
            currency = _optional_text(price_info.get("currency"), field="price currency")

        content = result.get("content")
        metadata = content.get("metadata") if isinstance(content, Mapping) else None
        name = _optional_text(metadata.get("name"), field="metadata.name") if isinstance(metadata, Mapping) else None
        symbol = _optional_text(metadata.get("symbol"), field="metadata.symbol") if isinstance(metadata, Mapping) else None
        if symbol is None:
            symbol = _optional_text(token_info.get("symbol"), field="token_info.symbol")
        mint_extensions = result.get("mint_extensions")
        if mint_extensions is None:
            extension_names: list[str] = []
        elif isinstance(mint_extensions, Mapping):
            extension_names = sorted(_text(key, field="mint extension name") for key in mint_extensions.keys())
        else:
            raise HeliusSourceError("mint_extensions must be an object or null")

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "mint": mint,
            "asset_available": True,
            "identity_verified": True,
            "last_indexed_slot": slot,
            "name": name,
            "symbol": symbol,
            "indexed_supply_candidate": supply,
            # Helius' fungible-token documentation calculates adjusted supply as
            # token_info.supply / 10**decimals, establishing raw base-unit semantics.
            # This verifies the field contract only; canonical RPC remains the
            # authority for current protocol state and freshness is not implied.
            "supply_unit": TOKEN_BASE_UNITS,
            "supply_semantics_verified": True,
            "decimals": decimals,
            "token_program": token_program,
            "mint_authority": mint_authority,
            "freeze_authority": freeze_authority,
            "mint_extension_names": extension_names,
            "cached_price_source_value": price,
            "cached_price_currency": currency,
            "price_cache_max_age_seconds": PRICE_CACHE_MAX_AGE_SECONDS,
            "price_freshness_verified": False,
        }

    def get_token_accounts_for_mint(
        self,
        mint: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        mint = _text(mint, field="mint")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        params: dict[str, object] = {"mint": mint, "limit": limit}
        if cursor is not None:
            params["cursor"] = _text(cursor, field="cursor")
        result = self._request("getTokenAccounts", params)
        if result is None:
            return {"chain": CHAIN, "source": SOURCE, "mint": mint, "accounts_available": False, "reason": "helius_token_accounts_not_found"}
        if not isinstance(result, Mapping):
            raise HeliusSourceError("Helius getTokenAccounts result must be an object")
        slot = _nonnegative_int(result.get("last_indexed_slot"), field="last_indexed_slot")
        total = _nonnegative_int(result.get("total"), field="token account total")
        accounts = result.get("token_accounts")
        if not isinstance(accounts, list):
            raise HeliusSourceError("token_accounts must be an array")
        clean: list[dict[str, Any]] = []
        for index, item in enumerate(accounts):
            if not isinstance(item, Mapping):
                raise HeliusSourceError(f"token account {index} must be an object")
            if item.get("mint") != mint:
                raise HeliusSourceError(f"token account {index} mint mismatch")
            address = _text(item.get("address"), field=f"token account {index} address")
            owner = _text(item.get("owner"), field=f"token account {index} owner")
            amount = _nonnegative_int(item.get("amount"), field=f"token account {index} amount")
            clean.append({"address": address, "owner": owner, "amount": amount})
        return {
            "chain": CHAIN,
            "source": SOURCE,
            "mint": mint,
            "accounts_available": True,
            "last_indexed_slot": slot,
            "token_account_count_candidate": total,
            "counted_entity": "token_accounts",
            "holder_count_semantics_verified": False,
            "accounts": clean,
            "cursor": result.get("cursor") if isinstance(result.get("cursor"), str) else None,
        }


__all__ = [
    "CHAIN",
    "DEFAULT_BASE_URL",
    "HeliusDASProvider",
    "HeliusNotConfigured",
    "HeliusSourceError",
    "PRICE_CACHE_MAX_AGE_SECONDS",
    "SOURCE",
    "TOKEN_BASE_UNITS",
]
