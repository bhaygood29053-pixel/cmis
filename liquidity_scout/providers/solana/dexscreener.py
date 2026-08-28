"""Read-only DEX Screener pair source for independent Solana market evidence.

The token-pairs endpoint returns pair-scoped observations. This adapter does not
select a preferred pair, aggregate liquidity/volume, or claim Solana-wide market
coverage. DEX Screener pair ``priceUsd`` is explicitly bound to the pair's base
token; a requested mint on the quote side never inherits that price.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import math
import time
from typing import Any, Callable

import requests

CHAIN = "solana"
SOURCE = "dexscreener_token_pairs_v1"
DEFAULT_BASE_URL = "https://api.dexscreener.com"


class DexScreenerSourceError(RuntimeError):
    pass


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DexScreenerSourceError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _optional_decimal(value: object, *, field: str, allow_negative: bool = False) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise DexScreenerSourceError(f"{field} must be finite numeric data")
    if isinstance(value, float) and not math.isfinite(value):
        raise DexScreenerSourceError(f"{field} must be finite numeric data")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DexScreenerSourceError(f"{field} must be finite numeric data") from exc
    if not parsed.is_finite() or (not allow_negative and parsed < 0):
        raise DexScreenerSourceError(f"{field} must be valid numeric data")
    text = format(parsed, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _optional_nonnegative_int(value: object, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DexScreenerSourceError(f"{field} must be a non-negative integer")
    return value


def _token(item: object, *, field: str) -> dict[str, str | None]:
    if not isinstance(item, Mapping):
        raise DexScreenerSourceError(f"{field} must be an object")
    return {
        "address": _text(item.get("address"), field=f"{field}.address"),
        "name": _optional_text(item.get("name"), field=f"{field}.name"),
        "symbol": _optional_text(item.get("symbol"), field=f"{field}.symbol"),
    }


def _numeric_window_map(value: object, *, field: str, txn_counts: bool = False) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DexScreenerSourceError(f"{field} must be an object or null")
    result: dict[str, Any] = {}
    for raw_window, raw_value in value.items():
        window = _text(raw_window, field=f"{field} window")
        if txn_counts:
            if not isinstance(raw_value, Mapping):
                raise DexScreenerSourceError(f"{field}.{window} must be an object")
            buys = _optional_nonnegative_int(raw_value.get("buys"), field=f"{field}.{window}.buys")
            sells = _optional_nonnegative_int(raw_value.get("sells"), field=f"{field}.{window}.sells")
            result[window] = {"buys": buys, "sells": sells}
        else:
            result[window] = _optional_decimal(
                raw_value,
                field=f"{field}.{window}",
                allow_negative=field == "priceChange",
            )
    return result


class DexScreenerSolanaProvider:
    chain = CHAIN

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 20,
        get: Callable[..., Any] = requests.get,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._base_url = _text(base_url, field="DEX Screener base URL").rstrip("/")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        self.timeout = timeout
        self._get = get
        self._clock = clock

    def get_token_pairs(self, mint: str) -> dict[str, Any]:
        """Return all pair-scoped observations supplied for one Solana mint."""

        mint = _text(mint, field="mint")
        collection_started_at = float(self._clock())
        if not math.isfinite(collection_started_at) or collection_started_at < 0:
            raise DexScreenerSourceError("collection start time must be a finite non-negative timestamp")
        transport_error_type: str | None = None
        try:
            response = self._get(
                f"{self._base_url}/token-pairs/v1/solana/{mint}",
                headers={"accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except DexScreenerSourceError:
            raise
        except Exception as exc:
            # Provider exceptions may contain request URLs or response text.
            # Keep only the exception class and raise after the handler exits so
            # no secret- or payload-bearing cause/context survives.
            transport_error_type = type(exc).__name__
        if transport_error_type is not None:
            raise DexScreenerSourceError(
                f"DEX Screener request failed ({transport_error_type})"
            ) from None

        collection_completed_at = float(self._clock())
        if (
            not math.isfinite(collection_completed_at)
            or collection_completed_at < collection_started_at
        ):
            raise DexScreenerSourceError(
                "collection completion time must be finite and not precede start time"
            )

        if not isinstance(body, list):
            raise DexScreenerSourceError("token-pairs response must be an array")
        if not body:
            return {
                "chain": CHAIN,
                "source": SOURCE,
                "mint": mint,
                "pairs_available": False,
                "pairs": [],
                "pair_count_observed": 0,
                "reason": "dexscreener_pairs_unavailable",
                "collection_started_at_unix": collection_started_at,
                "collection_completed_at_unix": collection_completed_at,
                "collection_time_verified": True,
                "freshness_verified": False,
                "solana_wide_coverage_verified": False,
            }

        pairs: list[dict[str, Any]] = []
        seen_pairs: set[str] = set()
        for index, item in enumerate(body):
            if not isinstance(item, Mapping):
                raise DexScreenerSourceError(f"pair {index} must be an object")
            if item.get("chainId") != CHAIN:
                raise DexScreenerSourceError(f"pair {index} chainId mismatch")
            pair_address = _text(item.get("pairAddress"), field=f"pair {index} address")
            if pair_address in seen_pairs:
                raise DexScreenerSourceError("duplicate pair address")
            seen_pairs.add(pair_address)
            dex_id = _text(item.get("dexId"), field=f"pair {index} dexId")
            base = _token(item.get("baseToken"), field=f"pair {index} baseToken")
            quote = _token(item.get("quoteToken"), field=f"pair {index} quoteToken")
            if mint not in {base["address"], quote["address"]}:
                raise DexScreenerSourceError(f"pair {index} does not contain requested mint")
            requested_mint_role = "base" if base["address"] == mint else "quote"
            price_subject_address = base["address"]

            liquidity_obj = item.get("liquidity")
            if liquidity_obj is None:
                liquidity_usd = liquidity_base = liquidity_quote = None
            elif isinstance(liquidity_obj, Mapping):
                liquidity_usd = _optional_decimal(liquidity_obj.get("usd"), field=f"pair {index} liquidity.usd")
                liquidity_base = _optional_decimal(liquidity_obj.get("base"), field=f"pair {index} liquidity.base")
                liquidity_quote = _optional_decimal(liquidity_obj.get("quote"), field=f"pair {index} liquidity.quote")
            else:
                raise DexScreenerSourceError(f"pair {index} liquidity must be an object or null")

            pairs.append(
                {
                    "pair_address": pair_address,
                    "dex_id": dex_id,
                    "base_token": base,
                    "quote_token": quote,
                    "requested_mint_role": requested_mint_role,
                    "price_subject_address": price_subject_address,
                    "price_is_for_requested_mint": requested_mint_role == "base",
                    "price_usd": _optional_decimal(item.get("priceUsd"), field=f"pair {index} priceUsd"),
                    "price_native": _optional_text(item.get("priceNative"), field=f"pair {index} priceNative"),
                    "liquidity_usd": liquidity_usd,
                    "liquidity_base": liquidity_base,
                    "liquidity_quote": liquidity_quote,
                    "volume": _numeric_window_map(item.get("volume"), field="volume"),
                    "transactions": _numeric_window_map(item.get("txns"), field="txns", txn_counts=True),
                    "price_change": _numeric_window_map(item.get("priceChange"), field="priceChange"),
                    "fdv": _optional_decimal(item.get("fdv"), field=f"pair {index} fdv"),
                    "market_cap": _optional_decimal(item.get("marketCap"), field=f"pair {index} marketCap"),
                    "pair_created_at_ms": _optional_nonnegative_int(item.get("pairCreatedAt"), field=f"pair {index} pairCreatedAt"),
                }
            )

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "mint": mint,
            "pairs_available": True,
            "pairs": pairs,
            "pair_count_observed": len(pairs),
            "scope": "pair_scoped_dexscreener_observations",
            "collection_started_at_unix": collection_started_at,
            "collection_completed_at_unix": collection_completed_at,
            "collection_time_verified": True,
            "freshness_verified": False,
            "solana_wide_coverage_verified": False,
            "aggregate_price_selected": False,
            "aggregate_liquidity_calculated": False,
            "aggregate_volume_calculated": False,
        }


__all__ = [
    "CHAIN",
    "DEFAULT_BASE_URL",
    "DexScreenerSolanaProvider",
    "DexScreenerSourceError",
    "SOURCE",
]
