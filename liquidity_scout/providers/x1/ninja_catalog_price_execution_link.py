"""Verify X1.Ninja pool-catalog priceNative updates against exact XDEX swaps.

The verifier uses a conservative temporal window:

    before_snapshot.rpc_slot_bracket.after.slot
        < transaction.slot <=
    after_snapshot.rpc_slot_bracket.before.slot

A transaction in that interval is known to have happened after the completed
"before" provider observation and no later than the start of the "after"
provider observation.

Only exact RPC-verified XDEX pool transactions with both verified vaults
mutated in opposite directions are eligible. The post-update catalog
priceNative is linked only when exactly one eligible latest swap price matches
within the accepted Decimal tolerance.

This proves bounded event linkage. It does not assign semantic meaning to
lastSyncedAt/lastUpdated, prove the provider's internal update source, verify a
freshness policy, priceUsd, USD liquidity, TVL, source independence, or any
execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import time
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.ninja_pool_catalog import (
    fetch_pool_catalog_raw,
)
from liquidity_scout.providers.x1.program_accounts import (
    RECOGNIZED_AMM_PROGRAM_IDS,
)
from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    get_block_time,
    get_signatures_for_address,
    rpc_request,
)
from liquidity_scout.providers.x1.transaction_pool_membership import (
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    WXNT_MINT,
    VerificationReport,
    fetch_transaction,
    verify_transaction,
)


VERSION = "1.0"
DEFAULT_CATALOG_LIMIT = 100
DEFAULT_SIGNATURE_LIMIT = 20


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _decimal(value: Any, *, name: str, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative: Decimal,
    absolute: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    relative_error = (
        error / abs(expected)
        if expected != 0
        else (Decimal(0) if error == 0 else None)
    )
    allowed = max(absolute, abs(expected) * relative)
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "relative_error": (
            format(relative_error, "e")
            if relative_error is not None
            else None
        ),
        "allowed_absolute_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def _slot_record(
    *,
    requester: Callable[..., Any],
    block_time_fetcher: Callable[..., Mapping[str, Any]],
    rpc_url: str,
) -> dict[str, Any]:
    slot = requester(
        "getSlot",
        [{"commitment": "confirmed"}],
        rpc_url=rpc_url,
    )
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise ValueError("X1 RPC getSlot returned malformed data")
    block = block_time_fetcher(slot, rpc_url=rpc_url)
    return {
        "slot": slot,
        "block_time": (
            block.get("block_time")
            if isinstance(block, Mapping)
            else None
        ),
        "block_time_verified": bool(
            isinstance(block, Mapping)
            and block.get("block_time_verified") is True
        ),
    }


def _row_address(row: Mapping[str, Any]) -> str | None:
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


def _token_addresses(row: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("baseToken", "quoteToken"):
        token = row.get(key)
        if not isinstance(token, Mapping):
            continue
        for field in ("address", "mint", "tokenAddress", "mintAddress"):
            value = _text(token.get(field))
            if value:
                values.add(value)
    return values


def select_bounded_xnt_catalog_pools(
    catalog_rows: Sequence[Mapping[str, Any]],
    *,
    maximum_pools: int = 30,
) -> list[str]:
    """Select exact wrapped-XNT pool addresses; txns1h is only a sampling hint."""

    if isinstance(maximum_pools, bool) or not isinstance(maximum_pools, int):
        raise ValueError("maximum_pools must be an integer")
    if maximum_pools < 1:
        raise ValueError("maximum_pools must be positive")

    candidates = []
    for index, row in enumerate(catalog_rows):
        if not isinstance(row, Mapping):
            continue
        address = _row_address(row)
        if not address or WXNT_MINT not in _token_addresses(row):
            continue
        raw_activity = row.get("txns1h")
        try:
            activity = Decimal(str(raw_activity))
            if not activity.is_finite():
                activity = Decimal("-1")
        except Exception:
            activity = Decimal("-1")
        candidates.append((activity, -index, address))

    candidates.sort(reverse=True)
    return [address for _, _, address in candidates[:maximum_pools]]


def collect_ninja_catalog_price_snapshot(
    *,
    pool_addresses: Sequence[str],
    catalog_limit: int = DEFAULT_CATALOG_LIMIT,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    catalog_fetcher: Callable[..., Mapping[str, Any]] = fetch_pool_catalog_raw,
    requester: Callable[..., Any] = rpc_request,
    block_time_fetcher: Callable[..., Mapping[str, Any]] = get_block_time,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Collect one bounded provider snapshot bracketed by X1 RPC time."""

    addresses = []
    seen = set()
    for raw in pool_addresses:
        address = _text(raw)
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)
    if not addresses:
        raise ValueError("at least one pool address is required")

    before = _slot_record(
        requester=requester,
        block_time_fetcher=block_time_fetcher,
        rpc_url=rpc_url,
    )
    observed_at_start = clock()
    catalog = catalog_fetcher(limit=catalog_limit)
    observed_at_end = clock()
    after = _slot_record(
        requester=requester,
        block_time_fetcher=block_time_fetcher,
        rpc_url=rpc_url,
    )

    raw = catalog.get("raw_response") if isinstance(catalog, Mapping) else None
    if not isinstance(raw, Mapping):
        raise ValueError("catalog raw response unavailable")
    rows = raw.get("pools")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("catalog pools are unavailable")

    by_address = {
        _row_address(row): row
        for row in rows
        if isinstance(row, Mapping) and _row_address(row)
    }

    pools = []
    for address in addresses:
        row = by_address.get(address)
        if not isinstance(row, Mapping):
            pools.append({
                "pool_address": address,
                "status": "unavailable",
                "error": "pool_missing_from_bounded_catalog_page",
            })
            continue
        pools.append({
            "pool_address": address,
            "status": "ok",
            "provider": {
                "priceNative": row.get("priceNative"),
                "pooledBase": row.get("pooledBase"),
                "pooledQuote": row.get("pooledQuote"),
                "lastSyncedAt_raw": row.get("lastSyncedAt"),
                "txns1h_raw": row.get("txns1h"),
            },
        })

    return {
        "service": "x1_ninja_catalog_price_snapshot",
        "version": VERSION,
        "chain": "x1",
        "status": (
            "ok"
            if all(row.get("status") == "ok" for row in pools)
            else "partial"
        ),
        "observed_at_start": observed_at_start,
        "observed_at_end": observed_at_end,
        "rpc_slot_bracket": {
            "before": before,
            "after": after,
        },
        "provider_timestamp_candidates": {
            "global_lastUpdated_raw": raw.get("lastUpdated"),
            "row_lastSyncedAt_semantics_verified": False,
            "global_lastUpdated_semantics_verified": False,
            "timestamp_units_verified": False,
        },
        "pools": pools,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _provider_row(
    snapshot: Mapping[str, Any],
    pool_address: str,
) -> Mapping[str, Any] | None:
    rows = snapshot.get("pools")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None
    for row in rows:
        if (
            isinstance(row, Mapping)
            and _text(row.get("pool_address")) == pool_address
        ):
            return row
    return None


def _identity(
    pool_address: str,
    *,
    structural_verifier: Callable[..., Mapping[str, Any]],
    recognized_program_ids: Sequence[str],
    rpc_url: str,
) -> tuple[dict[str, Any], str]:
    for raw_program in recognized_program_ids:
        program_id = _text(raw_program)
        if not program_id:
            continue
        try:
            structural = structural_verifier(
                account=pool_address,
                target_mint=WXNT_MINT,
                program_id=program_id,
                rpc_url=rpc_url,
                signature_limit=1,
            )
        except Exception:
            continue
        if structural.get("summary", {}).get(
            "pool_state_structural_role_verified"
        ) is not True:
            continue

        decoded = structural.get("decoded_state")
        decoded = decoded if isinstance(decoded, Mapping) else {}
        mint0 = _text(decoded.get("mint_0"))
        mint1 = _text(decoded.get("mint_1"))
        vault0 = _text(decoded.get("vault_0"))
        vault1 = _text(decoded.get("vault_1"))
        owner = _text(structural.get("shared_vault_authority"))
        if not all((mint0, mint1, vault0, vault1, owner)):
            continue

        if mint0 == WXNT_MINT and mint1 != WXNT_MINT:
            quote_mint, quote_vault = mint0, vault0
            asset_mint, asset_vault = mint1, vault1
        elif mint1 == WXNT_MINT and mint0 != WXNT_MINT:
            quote_mint, quote_vault = mint1, vault1
            asset_mint, asset_vault = mint0, vault0
        else:
            continue

        return ({
            "chain": "x1",
            "pool_address": pool_address,
            "asset_mint": asset_mint,
            "asset_vault": asset_vault,
            "counter_mint": quote_mint,
            "counter_vault": quote_vault,
            "shared_owner": owner,
            "identity_verified": True,
        }, program_id)

    raise ValueError("exact wrapped-XNT pool identity is unverified")


def _vault_delta(report: VerificationReport, account: str, mint: str):
    rows = [
        row
        for row in report.token_deltas
        if row.account == account and row.mint == mint
    ]
    if len(rows) != 1:
        raise ValueError("exact pool-vault delta unavailable or ambiguous")
    return rows[0]


def _safe_slot_window(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> tuple[int, int]:
    before_bracket = before.get("rpc_slot_bracket")
    after_bracket = after.get("rpc_slot_bracket")
    before_bracket = (
        before_bracket if isinstance(before_bracket, Mapping) else {}
    )
    after_bracket = after_bracket if isinstance(after_bracket, Mapping) else {}

    lower = (
        before_bracket.get("after", {}).get("slot")
        if isinstance(before_bracket.get("after"), Mapping)
        else None
    )
    upper = (
        after_bracket.get("before", {}).get("slot")
        if isinstance(after_bracket.get("before"), Mapping)
        else None
    )
    if (
        isinstance(lower, bool)
        or not isinstance(lower, int)
        or isinstance(upper, bool)
        or not isinstance(upper, int)
        or upper <= lower
    ):
        raise ValueError("safe RPC slot window is unavailable")
    return lower, upper


def verify_catalog_price_transition(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    pool_address: str,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    signature_limit: int = DEFAULT_SIGNATURE_LIMIT,
    structural_verifier: Callable[..., Mapping[str, Any]] = (
        verify_candidate_pool_role
    ),
    signature_fetcher: Callable[..., Sequence[Mapping[str, Any]]] = (
        get_signatures_for_address
    ),
    transaction_fetcher: Callable[..., Mapping[str, Any] | None] = (
        fetch_transaction
    ),
    transaction_verifier: Callable[..., VerificationReport] = (
        verify_transaction
    ),
    membership_prover: Callable[..., Mapping[str, Any]] = (
        prove_transaction_pool_membership
    ),
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    relative_tolerance: Any = DEFAULT_RELATIVE_TOLERANCE,
    absolute_tolerance: Any = DEFAULT_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    """Link one observed catalog price change to exact in-window XDEX swaps."""

    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")

    before_row = _provider_row(before, pool_address)
    after_row = _provider_row(after, pool_address)
    if not isinstance(before_row, Mapping) or not isinstance(after_row, Mapping):
        raise ValueError("pool is missing from before/after snapshots")
    if before_row.get("status") != "ok" or after_row.get("status") != "ok":
        raise ValueError("pool snapshot status is not ok")

    before_provider = before_row.get("provider")
    after_provider = after_row.get("provider")
    if not isinstance(before_provider, Mapping) or not isinstance(
        after_provider, Mapping
    ):
        raise ValueError("provider row data unavailable")

    before_price = _decimal(
        before_provider.get("priceNative"),
        name="before priceNative",
        positive=True,
    )
    after_price = _decimal(
        after_provider.get("priceNative"),
        name="after priceNative",
        positive=True,
    )
    price_changed = before_price != after_price
    reserve_changed = (
        before_provider.get("pooledBase") != after_provider.get("pooledBase")
        or before_provider.get("pooledQuote") != after_provider.get("pooledQuote")
    )
    if not price_changed:
        return {
            "service": "x1_ninja_catalog_price_transition",
            "version": VERSION,
            "chain": "x1",
            "status": "not_applicable",
            "pool_address": pool_address,
            "price_changed": False,
            "reserve_changed": reserve_changed,
            "catalog_price_execution_link_verified": False,
            "event_ordering_verified": False,
            "provider_fact_time_verified": False,
            "update_source_semantics_verified": False,
            "freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
            "errors": [],
        }

    relative = _decimal(relative_tolerance, name="relative_tolerance")
    absolute = _decimal(absolute_tolerance, name="absolute_tolerance")
    if relative < 0 or absolute < 0 or (relative == 0 and absolute == 0):
        raise ValueError("comparison tolerances invalid")

    lower, upper = _safe_slot_window(before, after)
    identity, program_id = _identity(
        pool_address,
        structural_verifier=structural_verifier,
        recognized_program_ids=recognized_program_ids,
        rpc_url=rpc_url,
    )

    history = signature_fetcher(
        pool_address,
        limit=signature_limit,
        rpc_url=rpc_url,
    )
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        raise ValueError("signature history unavailable")

    signatures = []
    for row in history:
        if not isinstance(row, Mapping) or row.get("err") is not None:
            continue
        slot = row.get("slot")
        signature = _text(row.get("signature"))
        if (
            signature
            and not isinstance(slot, bool)
            and isinstance(slot, int)
            and lower < slot <= upper
        ):
            signatures.append((slot, signature))

    candidates = []
    rejections = []
    for slot, signature in signatures:
        try:
            tx = transaction_fetcher(signature, rpc_url=rpc_url)
            if not isinstance(tx, Mapping):
                raise ValueError("transaction unavailable")
            report = transaction_verifier(
                tx,
                signature=signature,
                rpc_url=rpc_url,
            )
            membership = membership_prover(
                verification_report=report,
                pool_identity=identity,
                transaction=tx,
            )
            if membership.get(
                "transaction_pool_membership_verified"
            ) is not True:
                raise ValueError("exact pool membership unverified")

            asset = _vault_delta(
                report,
                identity["asset_vault"],
                identity["asset_mint"],
            )
            quote = _vault_delta(
                report,
                identity["counter_vault"],
                identity["counter_mint"],
            )

            if asset.delta_ui < 0 and quote.delta_ui > 0:
                side = "BUY"
            elif asset.delta_ui > 0 and quote.delta_ui < 0:
                side = "SELL"
            else:
                raise ValueError("vault deltas are not one two-sided swap")

            asset_amount = abs(asset.delta_ui)
            quote_amount = abs(quote.delta_ui)
            if asset_amount <= 0 or quote_amount <= 0:
                raise ValueError("swap amounts must be positive")
            execution_price = quote_amount / asset_amount
            comparison = _compare(
                after_price,
                execution_price,
                relative=relative,
                absolute=absolute,
            )
            candidates.append({
                "signature": signature,
                "slot": report.slot,
                "block_time": report.block_time,
                "onchain_side": side,
                "asset_amount": format(asset_amount, "f"),
                "quote_amount": format(quote_amount, "f"),
                "execution_price_native": format(execution_price, "f"),
                "after_catalog_price_comparison": comparison,
                "transaction_pool_membership_verified": True,
            })
        except Exception as exc:
            rejections.append({
                "signature": signature,
                "slot": slot,
                "error": f"{type(exc).__name__}: {exc}",
            })

    matching = [
        row
        for row in candidates
        if row.get("after_catalog_price_comparison", {}).get(
            "within_tolerance"
        ) is True
    ]
    max_slot = max(
        (row.get("slot") for row in candidates if isinstance(row.get("slot"), int)),
        default=None,
    )
    latest = [
        row
        for row in candidates
        if max_slot is not None and row.get("slot") == max_slot
    ]
    unique_latest_match = bool(
        len(matching) == 1
        and len(latest) == 1
        and matching[0].get("signature") == latest[0].get("signature")
    )

    return {
        "service": "x1_ninja_catalog_price_transition",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if unique_latest_match else (
            "partial" if candidates else "unavailable"
        ),
        "pool_address": pool_address,
        "program_id": program_id,
        "price_changed": True,
        "reserve_changed": reserve_changed,
        "before_provider": dict(before_provider),
        "after_provider": dict(after_provider),
        "safe_slot_window": {
            "exclusive_lower_slot": lower,
            "inclusive_upper_slot": upper,
            "ordering_rule": (
                "before.after.slot < transaction.slot <= after.before.slot"
            ),
        },
        "eligible_signature_count": len(signatures),
        "verified_swap_candidate_count": len(candidates),
        "matching_execution_price_count": len(matching),
        "latest_verified_swap_count": len(latest),
        "matched_transaction": matching[0] if unique_latest_match else None,
        "candidates": candidates,
        "rejections": rejections,
        "catalog_price_execution_link_verified": unique_latest_match,
        "event_ordering_verified": unique_latest_match,
        "provider_timestamp_units_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "errors": [],
    }


def aggregate_catalog_price_links(
    events: Sequence[Mapping[str, Any]],
    *,
    minimum_verified_events: int = 5,
) -> dict[str, Any]:
    """Aggregate bounded catalog-price execution-link evidence."""

    if isinstance(minimum_verified_events, bool) or not isinstance(
        minimum_verified_events, int
    ):
        raise ValueError("minimum_verified_events must be an integer")
    if minimum_verified_events < 5:
        raise ValueError("minimum_verified_events must be at least 5")

    rows = [dict(row) for row in events if isinstance(row, Mapping)]
    verified = [
        row
        for row in rows
        if row.get("catalog_price_execution_link_verified") is True
        and row.get("event_ordering_verified") is True
    ]
    signatures = {
        row.get("matched_transaction", {}).get("signature")
        for row in verified
        if isinstance(row.get("matched_transaction"), Mapping)
    }
    signatures.discard(None)

    passed = bool(
        len(verified) >= minimum_verified_events
        and len(verified) == len(rows)
        and len(signatures) == len(verified)
    )

    return {
        "service": "x1_ninja_catalog_price_execution_link",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if passed else (
            "partial" if rows else "unavailable"
        ),
        "event_count": len(rows),
        "verified_event_count": len(verified),
        "minimum_verified_events": minimum_verified_events,
        "distinct_pool_count": len({
            row.get("pool_address")
            for row in verified
            if row.get("pool_address")
        }),
        "distinct_transaction_count": len(signatures),
        "catalog_price_execution_link_verified": passed,
        "event_ordering_verified": passed,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "events": rows,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "DEFAULT_CATALOG_LIMIT",
    "DEFAULT_SIGNATURE_LIMIT",
    "VERSION",
    "aggregate_catalog_price_links",
    "collect_ninja_catalog_price_snapshot",
    "select_bounded_xnt_catalog_pools",
    "verify_catalog_price_transition",
]
