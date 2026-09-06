"""Fact-time USD valuation evidence for nonzero X1 rolling 24h volume.

Issue #504 requires nonzero wrapped-XNT quote volume to be valued at the
transaction fact time rather than with a current provider price. This module
keeps the three valuation legs explicit and fail-closed:

1. reconstruct the exact XNT/USDC.X reference-pool reserve ratio at the X1
   transaction slot from X1 RPC vault history;
2. reconstruct historical USDC.X reserve sufficiency from exact current Warp
   reserve/supply observations plus the accepted retained message lifecycle;
3. bind canonical USDC to USD with a bounded public Kraken USDC/USD trade
   observation at or immediately before the X1 transaction time.

No X1.Ninja USD price or volume field is used as a price source here. The
provider value may be compared with the reconstruction only after all three
legs verify independently.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.transaction_semantics import (
    USDC_X_MINT,
    WXNT_MINT,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    account_key_info,
    fetch_transaction,
)
from liquidity_scout.providers.x1.usdcx_destination_parity import (
    SOLANA_USDC_MINT,
    WARP_USDC_ROUTE_ID,
    X1_USDC_X_MINT,
)
from liquidity_scout.providers.x1.warp_message_interval_retention import (
    CONTRACT as INTERVAL_RETENTION_CONTRACT,
)
from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT as LIFECYCLE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as TRANSFER_CONTRACT,
)

CONTRACT = "x1_trade_time_usd_valuation/v1"
REFERENCE_POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
KRAKEN_POST_TRADE_URL = "https://api.kraken.com/0/public/PostTrade"
KRAKEN_POST_TRADE_DOCS = (
    "https://docs.kraken.com/api/docs/rest-api/get-post-trade"
)

POOL_SPACE = 637
VAULT_0_OFFSET = 72
VAULT_1_OFFSET = 104
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200
DEFAULT_REFERENCE_LOOKBACK_SECONDS = 7 * 86400
DEFAULT_MAX_REFERENCE_SIGNATURES = 20000
DEFAULT_KRAKEN_MAX_AGE_SECONDS = 120


class TradeTimeUsdValuationError(RuntimeError):
    """Raised when a fact-time valuation leg cannot be verified safely."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _epoch(value: Any, field: str) -> int:
    if value is None or isinstance(value, bool):
        raise TradeTimeUsdValuationError(f"{field} must be epoch seconds")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise TradeTimeUsdValuationError(
            f"{field} must be epoch seconds"
        ) from None
    if parsed <= 0:
        raise TradeTimeUsdValuationError(f"{field} must be positive")
    return parsed


def _nonnegative_int(value: Any, field: str) -> int:
    if value is None or isinstance(value, bool):
        raise TradeTimeUsdValuationError(f"{field} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise TradeTimeUsdValuationError(
            f"{field} must be a non-negative integer"
        ) from None
    if parsed < 0:
        raise TradeTimeUsdValuationError(f"{field} must be non-negative")
    return parsed


def _positive_decimal(value: Any, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise TradeTimeUsdValuationError(f"{field} must be decimal") from None
    if not parsed.is_finite() or parsed <= 0:
        raise TradeTimeUsdValuationError(f"{field} must be positive and finite")
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _parse_iso_epoch(value: Any, field: str) -> float:
    text = _text(value)
    if not text:
        raise TradeTimeUsdValuationError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise TradeTimeUsdValuationError(f"{field} must be ISO-8601") from None
    if parsed.tzinfo is None:
        raise TradeTimeUsdValuationError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def _pool_layout(
    *,
    pool_address: str = REFERENCE_POOL,
    state_fetcher: Callable[[str], Mapping[str, Any]] = fetch_account_state,
) -> dict[str, str]:
    state = state_fetcher(pool_address)
    if not isinstance(state, Mapping):
        raise TradeTimeUsdValuationError("reference pool account state unavailable")
    data = state.get("data")
    if not isinstance(data, bytes) or len(data) != POOL_SPACE:
        raise TradeTimeUsdValuationError(
            "reference pool is not the accepted 637-byte XDEX pool layout"
        )

    layout = {
        "pool_address": pool_address,
        "program_id": _text(state.get("owner")),
        "vault_0": extract_pubkey_at(data, VAULT_0_OFFSET),
        "vault_1": extract_pubkey_at(data, VAULT_1_OFFSET),
        "mint_0": extract_pubkey_at(data, MINT_0_OFFSET),
        "mint_1": extract_pubkey_at(data, MINT_1_OFFSET),
    }
    if layout["program_id"] != XDEX_MAINNET_OBSERVED_PROGRAM_ID:
        raise TradeTimeUsdValuationError(
            "reference pool owner is not the accepted mainnet-observed XDEX program"
        )
    if set((layout["mint_0"], layout["mint_1"])) != {WXNT_MINT, USDC_X_MINT}:
        raise TradeTimeUsdValuationError(
            "reference pool exact mint pair is not wrapped-XNT / USDC.X"
        )
    if not all(
        _text(layout[field])
        for field in ("program_id", "vault_0", "vault_1", "mint_0", "mint_1")
    ):
        raise TradeTimeUsdValuationError("reference pool layout is incomplete")
    return layout


def _transaction_post_token_balance(
    tx: Mapping[str, Any],
    *,
    account: str,
    mint: str,
) -> tuple[int, int]:
    keys, _signers = account_key_info(dict(tx))
    try:
        account_index = keys.index(account)
    except ValueError:
        raise TradeTimeUsdValuationError(
            "anchor transaction does not contain exact vault account"
        ) from None

    rows = (tx.get("meta") or {}).get("postTokenBalances") or []
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("accountIndex") == account_index
        and _text(row.get("mint")) == mint
    ]
    if len(matches) != 1:
        raise TradeTimeUsdValuationError(
            "anchor transaction does not expose one exact vault post-token balance"
        )
    amount = (matches[0].get("uiTokenAmount") or {}).get("amount")
    decimals = (matches[0].get("uiTokenAmount") or {}).get("decimals")
    return (
        _nonnegative_int(amount, "vault post amount"),
        _nonnegative_int(decimals, "vault decimals"),
    )


def _latest_vault_balance_at_fact(
    *,
    account: str,
    mint: str,
    fact_time: int,
    fact_slot: int,
    lookback_seconds: int,
    max_signatures: int,
    history_scanner: Callable[..., Mapping[str, Any]],
    transaction_fetcher: Callable[..., Mapping[str, Any] | None],
) -> dict[str, Any]:
    scan = history_scanner(
        account,
        start_epoch=fact_time - lookback_seconds,
        end_epoch=fact_time,
        max_signatures=max_signatures,
    )
    if not isinstance(scan, Mapping):
        raise TradeTimeUsdValuationError("vault history scan unavailable")
    if scan.get("range_proven") is not True or scan.get("integrity_verified") is not True:
        raise TradeTimeUsdValuationError(
            "vault history did not prove the bounded fact-time range"
        )

    entries = scan.get("entries")
    if not isinstance(entries, Sequence) or isinstance(
        entries, (str, bytes, bytearray)
    ):
        raise TradeTimeUsdValuationError("vault history entries unavailable")

    eligible = []
    for row in entries:
        if not isinstance(row, Mapping) or row.get("err") is not None:
            continue
        block_time = row.get("block_time")
        slot = row.get("slot")
        signature = _text(row.get("signature"))
        if (
            block_time is None
            or isinstance(block_time, bool)
            or not isinstance(block_time, (int, float))
            or isinstance(slot, bool)
            or not isinstance(slot, int)
            or not signature
        ):
            continue
        if block_time < fact_time or (
            int(block_time) == fact_time and slot <= fact_slot
        ):
            eligible.append((float(block_time), slot, signature))

    if not eligible:
        raise TradeTimeUsdValuationError(
            "no successful vault anchor transaction was found before the fact slot"
        )

    eligible.sort(reverse=True)
    anchor_time, anchor_slot, signature = eligible[0]
    tx = transaction_fetcher(signature)
    if not isinstance(tx, Mapping):
        raise TradeTimeUsdValuationError("vault anchor transaction unavailable")
    if (tx.get("meta") or {}).get("err") is not None:
        raise TradeTimeUsdValuationError("vault anchor transaction failed")
    if tx.get("slot") != anchor_slot or tx.get("blockTime") != int(anchor_time):
        raise TradeTimeUsdValuationError(
            "vault anchor transaction identity/time mismatch"
        )

    raw_amount, decimals = _transaction_post_token_balance(
        tx,
        account=account,
        mint=mint,
    )
    return {
        "account": account,
        "mint": mint,
        "anchor_signature": signature,
        "anchor_slot": anchor_slot,
        "anchor_block_time": int(anchor_time),
        "raw_amount": raw_amount,
        "decimals": decimals,
        "history_range_proven": True,
        "history_integrity_verified": True,
        "fact_time": fact_time,
        "fact_slot": fact_slot,
        "fact_time_verified": True,
    }


def capture_historical_xnt_usdcx_reference_rate(
    *,
    fact_time: Any,
    fact_slot: Any,
    pool_address: str = REFERENCE_POOL,
    lookback_seconds: int = DEFAULT_REFERENCE_LOOKBACK_SECONDS,
    max_signatures: int = DEFAULT_MAX_REFERENCE_SIGNATURES,
    state_fetcher: Callable[[str], Mapping[str, Any]] = fetch_account_state,
    history_scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    transaction_fetcher: Callable[..., Mapping[str, Any] | None] = fetch_transaction,
) -> dict[str, Any]:
    """Reconstruct exact reference-pool reserves at one X1 transaction fact."""

    fact_time_value = _epoch(fact_time, "fact_time")
    fact_slot_value = _nonnegative_int(fact_slot, "fact_slot")
    if isinstance(lookback_seconds, bool) or not isinstance(lookback_seconds, int):
        raise ValueError("lookback_seconds must be an integer")
    if lookback_seconds < 60 or lookback_seconds > 60 * 86400:
        raise ValueError("lookback_seconds must be between 60 seconds and 60 days")
    if isinstance(max_signatures, bool) or not isinstance(max_signatures, int):
        raise ValueError("max_signatures must be an integer")
    if max_signatures < 100 or max_signatures > 100000:
        raise ValueError("max_signatures must be between 100 and 100000")

    layout = _pool_layout(pool_address=pool_address, state_fetcher=state_fetcher)

    if layout["mint_0"] == WXNT_MINT:
        xnt_vault, usdcx_vault = layout["vault_0"], layout["vault_1"]
    else:
        xnt_vault, usdcx_vault = layout["vault_1"], layout["vault_0"]

    xnt = _latest_vault_balance_at_fact(
        account=xnt_vault,
        mint=WXNT_MINT,
        fact_time=fact_time_value,
        fact_slot=fact_slot_value,
        lookback_seconds=lookback_seconds,
        max_signatures=max_signatures,
        history_scanner=history_scanner,
        transaction_fetcher=transaction_fetcher,
    )
    usdcx = _latest_vault_balance_at_fact(
        account=usdcx_vault,
        mint=USDC_X_MINT,
        fact_time=fact_time_value,
        fact_slot=fact_slot_value,
        lookback_seconds=lookback_seconds,
        max_signatures=max_signatures,
        history_scanner=history_scanner,
        transaction_fetcher=transaction_fetcher,
    )

    if xnt["decimals"] != 9 or usdcx["decimals"] != 6:
        raise TradeTimeUsdValuationError(
            "reference vault token decimals do not match exact mints"
        )
    xnt_units = Decimal(xnt["raw_amount"]) / (Decimal(10) ** xnt["decimals"])
    usdcx_units = Decimal(usdcx["raw_amount"]) / (Decimal(10) ** usdcx["decimals"])
    if xnt_units <= 0 or usdcx_units <= 0:
        raise TradeTimeUsdValuationError("reference reserves must be positive")

    ratio = usdcx_units / xnt_units
    return {
        "contract": CONTRACT,
        "valuation_leg": "historical_xnt_usdcx_reference_rate",
        "pool_address": pool_address,
        "pool_program_id": layout["program_id"],
        "base_mint": WXNT_MINT,
        "quote_mint": USDC_X_MINT,
        "fact_time": fact_time_value,
        "fact_slot": fact_slot_value,
        "xnt_vault": xnt,
        "usdcx_vault": usdcx,
        "xnt_reserve": _decimal_text(xnt_units),
        "usdcx_reserve": _decimal_text(usdcx_units),
        "usdcx_per_xnt": _decimal_text(ratio),
        "unit": "USDC.X_per_XNT",
        "exact_mint_direction_verified": True,
        "fact_time_verified": True,
        "current_price_substitution_used": False,
        "provider_usd_price_used": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def evaluate_historical_usdcx_parity(
    *,
    fact_time: Any,
    current_backing_evidence: Mapping[str, Any],
    normalized_events: Mapping[str, Any],
    lifecycle_retention: Mapping[str, Any],
) -> dict[str, Any]:
    """Reconstruct USDC reserve and USDC.X supply at one historical fact time."""

    fact = _epoch(fact_time, "fact_time")
    if not isinstance(current_backing_evidence, Mapping):
        raise TypeError("current_backing_evidence must be a mapping")
    if not isinstance(normalized_events, Mapping):
        raise TypeError("normalized_events must be a mapping")
    if not isinstance(lifecycle_retention, Mapping):
        raise TypeError("lifecycle_retention must be a mapping")

    source = current_backing_evidence.get("source")
    destination = current_backing_evidence.get("destination")
    source = source if isinstance(source, Mapping) else {}
    destination = destination if isinstance(destination, Mapping) else {}

    exact_current_identity = bool(
        current_backing_evidence.get("route_id") == WARP_USDC_ROUTE_ID
        and source.get("chain") == "solana"
        and source.get("mint") == SOLANA_USDC_MINT
        and source.get("identity_verified") is True
        and destination.get("chain") == "x1"
        and destination.get("mint") == X1_USDC_X_MINT
        and destination.get("identity_verified") is True
        and current_backing_evidence.get("decimals_verified") is True
        and source.get("decimals") == 6
        and destination.get("decimals") == 6
        and current_backing_evidence.get("observation_time_compatible") is True
    )
    if not exact_current_identity:
        raise TradeTimeUsdValuationError(
            "exact current USDC / USDC.X Warp identity is not verified"
        )

    if normalized_events.get("contract") != TRANSFER_CONTRACT:
        raise TradeTimeUsdValuationError("accepted Warp transfer contract is required")
    if normalized_events.get("route_id") != WARP_USDC_ROUTE_ID:
        raise TradeTimeUsdValuationError("normalized USDC route identity mismatch")
    for field in (
        "pairing_semantics_verified",
        "settled_event_semantics_verified",
        "flow_event_normalization_authorized",
    ):
        if normalized_events.get(field) is not True:
            raise TradeTimeUsdValuationError(
                f"normalized_events.{field} must be true"
            )
    unresolved = normalized_events.get("unresolved_counts")
    if not isinstance(unresolved, Mapping):
        raise TradeTimeUsdValuationError("normalized unresolved counts are missing")
    unresolved_total = sum(
        _nonnegative_int(v, "unresolved count") for v in unresolved.values()
    )
    if unresolved_total != 0:
        raise TradeTimeUsdValuationError(
            "unresolved USDC route events prevent historical parity reconstruction"
        )

    lifecycle_contract = lifecycle_retention.get("contract")
    if lifecycle_contract == LIFECYCLE_CONTRACT:
        required_retention_field = "historical_retention_complete_verified"
    elif lifecycle_contract == INTERVAL_RETENTION_CONTRACT:
        required_retention_field = "interval_retention_complete_verified"
        if lifecycle_retention.get("sixty_day_bridge_flow_retention_promoted") is not False:
            raise TradeTimeUsdValuationError(
                "short interval retention must not be promoted as the 60-day gate"
            )
    else:
        raise TradeTimeUsdValuationError(
            "accepted Warp lifecycle or interval-retention contract is required"
        )
    for field in (
        required_retention_field,
        "requested_window_coverage_verified",
        "coverage_complete_verified",
        "missing_history_zero_authorized",
    ):
        if lifecycle_retention.get(field) is not True:
            raise TradeTimeUsdValuationError(
                f"lifecycle_retention.{field} must be true"
            )
    coverage_start = _epoch(
        lifecycle_retention.get("requested_start"), "lifecycle requested_start"
    )
    lifecycle_as_of = _epoch(
        lifecycle_retention.get("as_of"), "lifecycle as_of"
    )
    if not coverage_start <= fact <= lifecycle_as_of:
        raise TradeTimeUsdValuationError(
            "fact time is outside accepted lifecycle coverage"
        )

    source_observed_at = _epoch(source.get("observed_at"), "source observed_at")
    destination_observed_at = _epoch(
        destination.get("observed_at"), "destination observed_at"
    )
    if fact > source_observed_at or fact > destination_observed_at:
        raise TradeTimeUsdValuationError(
            "fact time must not follow current backing observations"
        )
    if source_observed_at > lifecycle_as_of or destination_observed_at > lifecycle_as_of:
        raise TradeTimeUsdValuationError(
            "current backing observations must fall inside lifecycle as_of coverage"
        )

    source_now = _nonnegative_int(source.get("amount_raw"), "source amount_raw")
    destination_now = _nonnegative_int(
        destination.get("raw_supply"), "destination raw_supply"
    )
    source_at_fact = source_now
    destination_at_fact = destination_now

    events = normalized_events.get("events")
    if not isinstance(events, Sequence) or isinstance(
        events, (str, bytes, bytearray)
    ):
        raise TradeTimeUsdValuationError("normalized event sequence is missing")

    source_reversed = 0
    destination_reversed = 0
    for event in events:
        if not isinstance(event, Mapping):
            raise TradeTimeUsdValuationError("normalized event row is invalid")
        if (
            event.get("route_id") != WARP_USDC_ROUTE_ID
            or event.get("settlement_verified") is not True
            or event.get("pairing_verified") is not True
            or event.get("lifecycle_state") != "settled"
            or event.get("decimals") != 6
        ):
            raise TradeTimeUsdValuationError(
                "normalized USDC event semantic mismatch"
            )
        amount = _nonnegative_int(event.get("amount_raw"), "event amount_raw")
        direction = event.get("direction")
        source_timestamp = _epoch(
            event.get("source_timestamp"), "event source_timestamp"
        )
        settled_at = _epoch(event.get("settled_at"), "event settled_at")

        if direction == "inflow":
            source_action_time = source_timestamp
            source_delta = amount
            destination_action_time = settled_at
            destination_delta = amount
        elif direction == "outflow":
            destination_action_time = source_timestamp
            destination_delta = -amount
            source_action_time = settled_at
            source_delta = -amount
        else:
            raise TradeTimeUsdValuationError("event direction is not inflow/outflow")

        if fact < source_action_time <= source_observed_at:
            source_at_fact -= source_delta
            source_reversed += 1
        if fact < destination_action_time <= destination_observed_at:
            destination_at_fact -= destination_delta
            destination_reversed += 1

    if source_at_fact < 0 or destination_at_fact < 0:
        raise TradeTimeUsdValuationError(
            "historical reserve/supply reconstruction produced negative state"
        )

    reserve_sufficient = source_at_fact >= destination_at_fact
    return {
        "contract": CONTRACT,
        "valuation_leg": "historical_usdcx_destination_parity",
        "proof_scope": "fact_time",
        "fact_time": fact,
        "route_id": WARP_USDC_ROUTE_ID,
        "source_chain": "solana",
        "source_mint": SOLANA_USDC_MINT,
        "destination_chain": "x1",
        "destination_mint": X1_USDC_X_MINT,
        "decimals": 6,
        "current_source_reserve_raw": source_now,
        "current_destination_supply_raw": destination_now,
        "source_observed_at": source_observed_at,
        "destination_observed_at": destination_observed_at,
        "source_actions_reversed": source_reversed,
        "destination_actions_reversed": destination_reversed,
        "historical_source_reserve_raw": source_at_fact,
        "historical_destination_supply_raw": destination_at_fact,
        "historical_reserve_surplus_raw": source_at_fact - destination_at_fact,
        "historical_source_reserve_gte_destination_supply": reserve_sufficient,
        "historical_usdcx_value_equivalence_verified": reserve_sufficient,
        "historical_value_equivalence_verified": reserve_sufficient,
        "lifecycle_coverage_verified": True,
        "all_route_events_resolved": True,
        "stable_name_one_dollar_assumption_used": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def _default_http_get(url: str, **kwargs: Any):
    return requests.get(url, **kwargs)


def capture_kraken_usdc_usd_fact_price(
    *,
    fact_time: Any,
    max_age_seconds: int = DEFAULT_KRAKEN_MAX_AGE_SECONDS,
    get: Callable[..., Any] = _default_http_get,
) -> dict[str, Any]:
    """Capture the last verified Kraken USDC/USD trade at/before fact time."""

    fact = _epoch(fact_time, "fact_time")
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int):
        raise ValueError("max_age_seconds must be an integer")
    if max_age_seconds < 1 or max_age_seconds > 300:
        raise ValueError("max_age_seconds must be between 1 and 300")

    start = datetime.fromtimestamp(
        fact - max_age_seconds, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    end = datetime.fromtimestamp(
        fact + 1, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")

    try:
        response = get(
            KRAKEN_POST_TRADE_URL,
            params={
                "symbol": "USDC/USD",
                "from_ts": start,
                "to_ts": end,
                "count": 1000,
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "CMIS-Trade-Time-USD/1.0",
            },
            timeout=20,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise TradeTimeUsdValuationError(
            f"Kraken USDC/USD fact-time read failed ({type(exc).__name__})"
        ) from None

    if not isinstance(body, Mapping):
        raise TradeTimeUsdValuationError("Kraken response must be an object")
    errors = body.get("error")
    if isinstance(errors, Sequence) and not isinstance(
        errors, (str, bytes, bytearray)
    ) and len(errors) > 0:
        raise TradeTimeUsdValuationError("Kraken response contains errors")

    result = body.get("result")
    if not isinstance(result, Mapping):
        raise TradeTimeUsdValuationError("Kraken response result is missing")
    trades = result.get("trades")
    if not isinstance(trades, Sequence) or isinstance(
        trades, (str, bytes, bytearray)
    ):
        raise TradeTimeUsdValuationError("Kraken trade list is missing")

    eligible = []
    rejected_identity = 0
    for row in trades:
        if not isinstance(row, Mapping):
            continue
        exact_identity = bool(
            row.get("symbol") == "USDC/USD"
            and row.get("base_asset") == "USDC"
            and row.get("quote_asset") == "USD"
        )
        if not exact_identity:
            rejected_identity += 1
            continue
        trade_time = _parse_iso_epoch(row.get("trade_ts"), "Kraken trade_ts")
        if trade_time > fact:
            continue
        age = Decimal(str(fact)) - Decimal(str(trade_time))
        if age < 0 or age > Decimal(max_age_seconds):
            continue
        price = _positive_decimal(row.get("price"), "Kraken trade price")
        quantity = _positive_decimal(row.get("quantity"), "Kraken trade quantity")
        eligible.append(
            {
                "trade_id": _text(row.get("trade_id")),
                "trade_ts": row.get("trade_ts"),
                "trade_time_epoch": trade_time,
                "age_seconds": age,
                "price": price,
                "quantity": quantity,
            }
        )

    if not eligible:
        raise TradeTimeUsdValuationError(
            "no exact Kraken USDC/USD trade satisfied the fact-time age policy"
        )
    eligible.sort(
        key=lambda row: (row["trade_time_epoch"], row["trade_id"] or ""),
        reverse=True,
    )
    selected = eligible[0]
    return {
        "contract": CONTRACT,
        "valuation_leg": "canonical_usdc_usd_fact_price",
        "source": "Kraken public PostTrade",
        "source_url": KRAKEN_POST_TRADE_URL,
        "source_contract": KRAKEN_POST_TRADE_DOCS,
        "symbol": "USDC/USD",
        "base_asset": "USDC",
        "quote_asset": "USD",
        "canonical_solana_usdc_mint": SOLANA_USDC_MINT,
        "fact_time": fact,
        "trade_id": selected["trade_id"],
        "trade_ts": selected["trade_ts"],
        "trade_time_epoch": selected["trade_time_epoch"],
        "observation_age_seconds": _decimal_text(selected["age_seconds"]),
        "max_age_seconds": max_age_seconds,
        "price_usd_per_usdc": _decimal_text(selected["price"]),
        "unit": "USD_per_USDC",
        "exact_pair_identity_verified": True,
        "fact_time_verified": True,
        "last_observation_policy_verified": True,
        "rejected_identity_count": rejected_identity,
        "stable_name_one_dollar_assumption_used": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def resolve_xnt_quote_usd_value(
    *,
    fact_time: Any,
    quote_mint: Any,
    quote_amount: Any,
    reference_rate_evidence: Mapping[str, Any],
    historical_usdcx_parity: Mapping[str, Any],
    canonical_usdc_usd_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose verified fact-time XNT/USD and value one exact XNT quote amount."""

    fact = _epoch(fact_time, "fact_time")
    quote_mint_text = _text(quote_mint)
    if quote_mint_text != WXNT_MINT:
        return {
            "historical_usd_value_verified": False,
            "fact_time_verified": False,
            "quote_mint": quote_mint_text,
            "reason": "unsupported_historical_quote_mint",
        }

    amount = _positive_decimal(quote_amount, "quote_amount")
    if not isinstance(reference_rate_evidence, Mapping):
        raise TypeError("reference_rate_evidence must be a mapping")
    if not isinstance(historical_usdcx_parity, Mapping):
        raise TypeError("historical_usdcx_parity must be a mapping")
    if not isinstance(canonical_usdc_usd_evidence, Mapping):
        raise TypeError("canonical_usdc_usd_evidence must be a mapping")

    reference_ok = bool(
        reference_rate_evidence.get("fact_time") == fact
        and reference_rate_evidence.get("base_mint") == WXNT_MINT
        and reference_rate_evidence.get("quote_mint") == USDC_X_MINT
        and reference_rate_evidence.get("unit") == "USDC.X_per_XNT"
        and reference_rate_evidence.get("fact_time_verified") is True
        and reference_rate_evidence.get("current_price_substitution_used") is False
        and reference_rate_evidence.get("provider_usd_price_used") is False
    )
    parity_ok = bool(
        historical_usdcx_parity.get("fact_time") == fact
        and historical_usdcx_parity.get("route_id") == WARP_USDC_ROUTE_ID
        and historical_usdcx_parity.get(
            "historical_usdcx_value_equivalence_verified"
        )
        is True
        and historical_usdcx_parity.get("historical_value_equivalence_verified")
        is True
        and historical_usdcx_parity.get("stable_name_one_dollar_assumption_used")
        is False
    )
    canonical_ok = bool(
        canonical_usdc_usd_evidence.get("fact_time") == fact
        and canonical_usdc_usd_evidence.get("canonical_solana_usdc_mint")
        == SOLANA_USDC_MINT
        and canonical_usdc_usd_evidence.get("unit") == "USD_per_USDC"
        and canonical_usdc_usd_evidence.get("exact_pair_identity_verified") is True
        and canonical_usdc_usd_evidence.get("fact_time_verified") is True
        and canonical_usdc_usd_evidence.get("stable_name_one_dollar_assumption_used")
        is False
    )

    if not (reference_ok and parity_ok and canonical_ok):
        return {
            "historical_usd_value_verified": False,
            "fact_time_verified": False,
            "quote_mint": quote_mint_text,
            "reason": "historical_quote_usd_evidence_incomplete",
            "reference_rate_verified": reference_ok,
            "historical_usdcx_parity_verified": parity_ok,
            "canonical_usdc_usd_verified": canonical_ok,
        }

    usdcx_per_xnt = _positive_decimal(
        reference_rate_evidence.get("usdcx_per_xnt"), "USDC.X per XNT"
    )
    usd_per_usdc = _positive_decimal(
        canonical_usdc_usd_evidence.get("price_usd_per_usdc"), "USD per USDC"
    )
    xnt_usd = usdcx_per_xnt * usd_per_usdc
    usd_value = amount * xnt_usd

    return {
        "contract": CONTRACT,
        "historical_usd_value_verified": True,
        "fact_time_verified": True,
        "fact_time": fact,
        "quote_mint": quote_mint_text,
        "quote_amount": _decimal_text(amount),
        "quote_amount_unit": "XNT",
        "historical_xnt_usd_price": _decimal_text(xnt_usd),
        "historical_xnt_usd_unit": "USD_per_XNT",
        "usd_value": _decimal_text(usd_value),
        "usd_value_unit": "USD",
        "reference_rate_verified": True,
        "historical_usdcx_parity_verified": True,
        "canonical_usdc_usd_verified": True,
        "valuation_basis": (
            "exact_fact_time_XNT_USDCX_RPC_reserves"
            "*historical_Warp_USDCX_reserve_sufficiency"
            "*bounded_Kraken_USDC_USD_trade"
        ),
        "current_price_substitution_used": False,
        "provider_usd_price_used": False,
        "stable_name_one_dollar_assumption_used": False,
        "source_independence_verified": False,
        "execution_authorized": False,
        "evidence": {
            "reference_rate": dict(reference_rate_evidence),
            "historical_usdcx_parity": dict(historical_usdcx_parity),
            "canonical_usdc_usd": dict(canonical_usdc_usd_evidence),
        },
    }


__all__ = [
    "CONTRACT",
    "DEFAULT_KRAKEN_MAX_AGE_SECONDS",
    "DEFAULT_MAX_REFERENCE_SIGNATURES",
    "DEFAULT_REFERENCE_LOOKBACK_SECONDS",
    "KRAKEN_POST_TRADE_DOCS",
    "KRAKEN_POST_TRADE_URL",
    "REFERENCE_POOL",
    "TradeTimeUsdValuationError",
    "capture_historical_xnt_usdcx_reference_rate",
    "capture_kraken_usdc_usd_fact_price",
    "evaluate_historical_usdcx_parity",
    "resolve_xnt_quote_usd_value",
]
