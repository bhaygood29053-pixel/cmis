"""Read-only live proof for CMIS 1.12 AGI verified price-history backfill.

The probe uses production provider contracts but writes only to temporary
SQLite databases. It evaluates the production path and the direct/two-leg
provider paths independently so CMIS cannot mistake "a usable recent path" for
"the earliest defensible market observation".
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import historical_metrics

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_history import fetch_pool_ohlcv_raw
from liquidity_scout.providers.x1.xdex_price_history_import import (
    SOURCE,
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
    backfill_verified_xdex_usd_price_history,
)


AGI_MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"
AGI_SYMBOL = "AGI"
DEFAULT_LOOKBACK_DAYS = 300
DEFAULT_OUTPUT = "agi_verified_history_evidence.json"


def _iso(ts: Any) -> str | None:
    if ts is None or isinstance(ts, bool):
        return None
    try:
        value = int(ts)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _token_mint(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("mint", "address", "tokenAddress", "id"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
        return None
    text = str(value or "").strip()
    return text or None


def _pool_address(pool: dict[str, Any]) -> str | None:
    for key in ("address", "poolAddress", "pool_address", "id"):
        text = str(pool.get(key) or "").strip()
        if text:
            return text
    return None


def _pair(pool: dict[str, Any]) -> tuple[str | None, str | None]:
    return (
        _token_mint(pool.get("baseToken")),
        _token_mint(pool.get("quoteToken")),
    )


def _relevant_pools(pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = {
        (AGI_MINT, USDC_X_MINT),
        (AGI_MINT, WRAPPED_XNT_MINT),
        (WRAPPED_XNT_MINT, USDC_X_MINT),
    }
    result = []
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        pair = _pair(pool)
        if pair not in wanted:
            continue
        result.append(
            {
                "address": _pool_address(pool),
                "base_mint": pair[0],
                "quote_mint": pair[1],
                "liquidity": pool.get("liquidity"),
            }
        )
    return result


def _candidate_catalog(
    pools: list[dict[str, Any]],
    *,
    path: str,
) -> list[dict[str, Any]]:
    if path == "direct":
        wanted = {(AGI_MINT, USDC_X_MINT)}
    elif path == "two_leg":
        wanted = {
            (AGI_MINT, WRAPPED_XNT_MINT),
            (WRAPPED_XNT_MINT, USDC_X_MINT),
        }
    elif path == "production":
        return list(pools)
    else:
        raise ValueError(f"unsupported candidate path: {path}")
    return [
        pool
        for pool in pools
        if isinstance(pool, dict) and _pair(pool) in wanted
    ]


def _positive_days(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("lookback days must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("lookback days must be a positive integer") from exc
    if not 1 <= parsed <= 3650:
        raise ValueError("lookback days must be between 1 and 3650")
    return parsed


def _run_candidate(
    *,
    label: str,
    pools: list[dict[str, Any]],
    api_key: str,
    time_from: int,
    time_to: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"cmis-agi-{label}-") as tempdir:
        original_db = historical_metrics.DB_FILE
        historical_metrics.DB_FILE = str(Path(tempdir) / "history.db")
        try:
            result = backfill_verified_xdex_usd_price_history(
                AGI_MINT,
                AGI_SYMBOL,
                catalog_pools=pools,
                history_backend=historical_metrics,
                time_from=time_from,
                time_to=time_to,
                ninja_fetcher=lambda pool_address, **kwargs: fetch_pool_ohlcv_raw(
                    pool_address,
                    api_key=api_key,
                    **kwargs,
                ),
                imported_at=time_to,
            )
            summary = historical_metrics.verified_price_import_summary(AGI_MINT)
            series = historical_metrics.historical_series(AGI_MINT, "price")
            provenance = historical_metrics.verified_price_observations(AGI_MINT)
        finally:
            historical_metrics.DB_FILE = original_db

    return {
        "label": label,
        "catalog_pool_count": len(pools),
        "backfill_result": result,
        "stored_summary": summary,
        "usable_price_observation_count": len(series),
        "first_usable_price_observation": series[0] if series else None,
        "last_usable_price_observation": series[-1] if series else None,
        "first_usable_price_observed_at_iso": (
            _iso(series[0]["timestamp"]) if series else None
        ),
        "last_usable_price_observed_at_iso": (
            _iso(series[-1]["timestamp"]) if series else None
        ),
        "provenance_row_count": len(provenance),
        "provider_history_imported": result.get("provider_history_imported") is True,
        "full_asset_lifetime_verified": (
            result.get("full_asset_lifetime_verified") is True
        ),
        "continuous_coverage_verified": (
            result.get("continuous_coverage_verified") is True
        ),
        "provider_range_complete_verified": (
            result.get("provider_range_complete_verified") is True
        ),
        "source_independence_verified": (
            result.get("source_independence_verified") is True
        ),
    }


def _first_timestamp(candidate: dict[str, Any]) -> int | None:
    row = candidate.get("first_usable_price_observation")
    if not isinstance(row, dict):
        return None
    value = row.get("timestamp")
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def run_probe(
    *,
    api_key: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    output_path: str | Path = DEFAULT_OUTPUT,
    now: int | None = None,
) -> dict[str, Any]:
    key = str(api_key or "").strip()
    if not key:
        raise RuntimeError("X1_NINJA_API_KEY is required for the live AGI history probe")

    days = _positive_days(lookback_days)
    observed_at = int(time.time()) if now is None else int(now)
    time_from = max(1, observed_at - days * 86400)

    pools, xnt_price_usd = fetch_all_pools(api_key=key)
    candidates = {
        label: _run_candidate(
            label=label,
            pools=_candidate_catalog(pools, path=label),
            api_key=key,
            time_from=time_from,
            time_to=observed_at,
        )
        for label in ("production", "direct", "two_leg")
    }

    usable_candidates = [
        candidate
        for candidate in candidates.values()
        if _first_timestamp(candidate) is not None
    ]
    earliest_candidate = (
        min(usable_candidates, key=lambda item: _first_timestamp(item) or observed_at)
        if usable_candidates
        else None
    )
    production_first = _first_timestamp(candidates["production"])
    earliest_first = _first_timestamp(earliest_candidate or {})

    evidence = {
        "schema": "cmis_x1_agi_verified_price_backfill_probe.v2",
        "chain": "x1",
        "asset": {
            "symbol": AGI_SYMBOL,
            "mint": AGI_MINT,
        },
        "source": SOURCE,
        "lookback_days": days,
        "requested_time_from": time_from,
        "requested_time_from_iso": _iso(time_from),
        "requested_time_to": observed_at,
        "requested_time_to_iso": _iso(observed_at),
        "catalog_pool_count": len(pools),
        "catalog_xnt_price_usd": xnt_price_usd,
        "relevant_catalog_pools": _relevant_pools(pools),
        "candidate_paths": candidates,
        "earliest_defensible_candidate_path": (
            earliest_candidate.get("label") if earliest_candidate else None
        ),
        "earliest_defensible_observed_at": earliest_first,
        "earliest_defensible_observed_at_iso": _iso(earliest_first),
        "production_first_observed_at": production_first,
        "production_first_observed_at_iso": _iso(production_first),
        "production_reaches_earliest_defensible_observation": (
            production_first is not None
            and earliest_first is not None
            and production_first <= earliest_first
        ),
        "full_asset_lifetime_verified": False,
        "continuous_coverage_verified": False,
        "provider_range_complete_verified": False,
        "source_independence_verified": False,
        "limitations": [
            "imports_verified_price_only",
            "volume_and_liquidity_history_not_imported",
            "only_cross_provider_close_matched_bars_are_persisted",
            "provider_source_independence_not_verified",
            "provider_archive_completeness_not_verified",
            "configured_usd_stable_quote_does_not_prove_historical_one_dollar_peg",
            "no_claim_of_complete_asset_lifetime_history",
        ],
    }

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    production = candidates["production"]
    if production["provider_history_imported"] is not True:
        raise RuntimeError(
            "AGI production provider history was not imported; see evidence artifact"
        )
    if int(production["stored_summary"].get("usable_observation_count") or 0) < 2:
        raise RuntimeError(
            "AGI production backfill produced fewer than two usable verified observations"
        )
    if production["full_asset_lifetime_verified"] is True:
        raise RuntimeError("live probe must not promote complete AGI asset lifetime")
    if production["continuous_coverage_verified"] is True:
        raise RuntimeError("live probe must not promote continuous AGI coverage")
    if (
        production_first is not None
        and earliest_first is not None
        and production_first > earliest_first
    ):
        raise RuntimeError(
            "production importer stops after a newer usable path and misses an earlier "
            "verified AGI candidate path; see evidence artifact"
        )

    return evidence


def main() -> int:
    evidence = run_probe(
        api_key=os.getenv("X1_NINJA_API_KEY", ""),
        lookback_days=_positive_days(
            os.getenv("AGI_HISTORY_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS))
        ),
        output_path=os.getenv("AGI_HISTORY_EVIDENCE_PATH", DEFAULT_OUTPUT),
    )

    print("CMIS 1.12 AGI verified price-history probe")
    for label, candidate in evidence["candidate_paths"].items():
        print(
            f"{label}: method={candidate['backfill_result'].get('method')} "
            f"usable={candidate['usable_price_observation_count']} "
            f"first={candidate['first_usable_price_observed_at_iso']} "
            f"last={candidate['last_usable_price_observed_at_iso']}"
        )
    print(
        "earliest_defensible_candidate_path="
        f"{evidence['earliest_defensible_candidate_path']}"
    )
    print(
        "earliest_defensible_observation="
        f"{evidence['earliest_defensible_observed_at_iso']}"
    )
    print(
        "production_reaches_earliest_defensible_observation="
        f"{evidence['production_reaches_earliest_defensible_observation']}"
    )
    print(
        "full_asset_lifetime_verified="
        f"{evidence['full_asset_lifetime_verified']}"
    )
    print(
        "continuous_coverage_verified="
        f"{evidence['continuous_coverage_verified']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
