"""Exact rolling 24h X1 market-activity evidence for CMIS #502.

This module reconstructs one pool's successful activity from X1 RPC address
history and exact transaction/pool membership evidence, then composes complete
pool windows against one X1.Ninja market report.

Important boundaries:
- one provider row is never assumed to equal one chain transaction;
- only unique successful exact-pool swap signatures count as transactions;
- liquidity events and unrelated pool-address activity do not count as swaps;
- nonzero USD volume requires verified historical quote/USD valuation for every
  reconstructed swap;
- exact zero swap volume is exactly zero in every quote currency and therefore
  needs no price conversion;
- collection time is not provider fact time;
- source independence and execution authority remain separate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.providers.x1.history_range import scan_address_history_range
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_pool_membership import (
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    fetch_transaction,
    verify_transaction,
)


CONTRACT_VERSION = "x1_rolling_24h_market_activity/v1"
POOL_WINDOW_CONTRACT = "x1_pool_24h_chain_activity/v1"
POOL_SCOPE_CONTRACT = "x1_ninja_current_pool_scope/v1"
WINDOW_SECONDS = Decimal("86400")
DEFAULT_RELATIVE_VOLUME_TOLERANCE = Decimal("0.01")
DEFAULT_ABSOLUTE_VOLUME_TOLERANCE_USD = Decimal("0.01")


class X1Rolling24hMarketActivityError(ValueError):
    pass


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise X1Rolling24hMarketActivityError(f"{name} must be a finite number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise X1Rolling24hMarketActivityError(
            f"{name} must be a finite number"
        ) from exc
    if not parsed.is_finite():
        raise X1Rolling24hMarketActivityError(f"{name} must be a finite number")
    return parsed


def _nonnegative_decimal(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise X1Rolling24hMarketActivityError(f"{name} must be non-negative")
    return parsed


def _nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise X1Rolling24hMarketActivityError(
            f"{name} must be a non-negative integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise X1Rolling24hMarketActivityError(
            f"{name} must be a non-negative integer"
        ) from exc
    if parsed < 0 or Decimal(str(value)) != Decimal(parsed):
        raise X1Rolling24hMarketActivityError(
            f"{name} must be a non-negative integer"
        )
    return parsed


def _comparison(
    observed: Decimal,
    expected: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    allowed = max(absolute_tolerance, abs(expected) * relative_tolerance)
    return {
        "observed": format(observed, "f"),
        "expected": format(expected, "f"),
        "absolute_error": format(error, "f"),
        "allowed_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def _field(report: Any, name: str) -> Any:
    if isinstance(report, Mapping):
        return report.get(name)
    return getattr(report, name, None)


def _delta_record(delta: Any) -> dict[str, Any] | None:
    if isinstance(delta, Mapping):
        account = _text(delta.get("account"))
        mint = _text(delta.get("mint"))
        owner = _text(delta.get("owner"))
        raw = delta.get("delta_raw")
        ui = delta.get("delta_ui")
    else:
        account = _text(getattr(delta, "account", None))
        mint = _text(getattr(delta, "mint", None))
        owner = _text(getattr(delta, "owner", None))
        raw = getattr(delta, "delta_raw", None)
        ui = getattr(delta, "delta_ui", None)
    if not account or not mint:
        return None
    try:
        raw_value = int(raw)
        ui_value = Decimal(str(ui))
    except (TypeError, ValueError, InvalidOperation):
        return None
    if not ui_value.is_finite():
        return None
    return {
        "account": account,
        "mint": mint,
        "owner": owner,
        "delta_raw": raw_value,
        "delta_ui": ui_value,
    }


def _report_token_delta(report: Any, account: str) -> dict[str, Any] | None:
    raw = _field(report, "token_deltas")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return None
    matches = []
    for item in raw:
        record = _delta_record(item)
        if record and record["account"] == account:
            matches.append(record)
    return matches[0] if len(matches) == 1 else None


def _default_fetcher(signature: str, *, rpc_url: str) -> Any:
    return fetch_transaction(signature, rpc_url=rpc_url)


def _default_verifier(
    transaction: Mapping[str, Any] | None,
    *,
    signature: str,
    rpc_url: str,
    asset_mint: str,
) -> Any:
    return verify_transaction(
        transaction,
        signature=signature,
        rpc_url=rpc_url,
        expected_mint=asset_mint,
    )


def _default_membership_prover(
    *,
    verification_report: Any,
    pool_identity: Mapping[str, Any],
    transaction: Mapping[str, Any],
) -> Mapping[str, Any]:
    return prove_transaction_pool_membership(
        verification_report=verification_report,
        pool_identity=pool_identity,
        transaction=transaction,
    )


def reconstruct_x1_pool_24h_chain_activity(
    *,
    pool_identity: Mapping[str, Any],
    start_epoch: Any,
    end_epoch: Any,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    page_size: int = 1000,
    max_signatures: int = 5000,
    scanner: Callable[..., Mapping[str, Any]] = scan_address_history_range,
    fetcher: Callable[..., Any] = _default_fetcher,
    verifier: Callable[..., Any] = _default_verifier,
    membership_prover: Callable[..., Mapping[str, Any]] = _default_membership_prover,
    usd_quote_resolver: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconstruct one exact pool's rolling-window swap count and quote volume."""

    if not isinstance(pool_identity, Mapping):
        raise TypeError("pool_identity must be a mapping")
    if pool_identity.get("chain") != "x1":
        raise X1Rolling24hMarketActivityError("pool_identity chain must be x1")
    if pool_identity.get("identity_verified") is not True:
        raise X1Rolling24hMarketActivityError("pool identity must be verified")

    pool_address = _text(pool_identity.get("pool_address"))
    asset_mint = _text(pool_identity.get("asset_mint"))
    asset_vault = _text(pool_identity.get("asset_vault"))
    counter_mint = _text(pool_identity.get("counter_mint"))
    counter_vault = _text(pool_identity.get("counter_vault"))
    shared_owner = _text(pool_identity.get("shared_owner"))
    if not all(
        [pool_address, asset_mint, asset_vault, counter_mint, counter_vault, shared_owner]
    ):
        raise X1Rolling24hMarketActivityError(
            "pool identity is missing exact pool/mint/vault/owner fields"
        )
    if asset_mint == counter_mint or asset_vault == counter_vault:
        raise X1Rolling24hMarketActivityError(
            "pool identity mints and vaults must be distinct"
        )

    start = _nonnegative_decimal(start_epoch, name="start_epoch")
    end = _nonnegative_decimal(end_epoch, name="end_epoch")
    if start >= end:
        raise X1Rolling24hMarketActivityError("start_epoch must be < end_epoch")
    duration = end - start
    if duration != WINDOW_SECONDS:
        raise X1Rolling24hMarketActivityError(
            "rolling market activity window must be exactly 86400 seconds"
        )

    raw_scan = scanner(
        pool_address,
        start_epoch=float(start),
        end_epoch=float(end),
        rpc_url=rpc_url,
        page_size=page_size,
        max_signatures=max_signatures,
    )
    if not isinstance(raw_scan, Mapping):
        raise X1Rolling24hMarketActivityError("scanner returned malformed result")
    scan = dict(raw_scan)
    entries = scan.pop("entries", [])
    if not isinstance(entries, Sequence) or isinstance(
        entries, (str, bytes, bytearray)
    ):
        raise X1Rolling24hMarketActivityError("scan entries must be a sequence")

    range_proven = scan.get("range_proven") is True
    integrity_verified = scan.get("integrity_verified") is True

    in_window = []
    for row in entries:
        if not isinstance(row, Mapping):
            continue
        block_time = row.get("block_time")
        if isinstance(block_time, bool) or not isinstance(block_time, (int, float)):
            continue
        if float(start) <= float(block_time) <= float(end):
            in_window.append(dict(row))

    successful_rows = [row for row in in_window if row.get("err") is None]
    failed_rows = [row for row in in_window if row.get("err") is not None]

    records: list[dict[str, Any]] = []
    fetch_unavailable = 0
    verification_errors = 0
    identity_conflicts = 0
    classification_ambiguities = 0
    swap_signatures: set[str] = set()
    quote_volume = Decimal(0)
    usd_volume = Decimal(0)
    usd_valued_swap_count = 0
    nonzero_usd_valuation_semantics_verified = True

    for row in successful_rows:
        signature = _text(row.get("signature"))
        if not signature:
            verification_errors += 1
            records.append(
                {"classification": "UNVERIFIED", "reason": "signature_missing"}
            )
            continue
        try:
            transaction = fetcher(signature, rpc_url=rpc_url)
        except Exception as exc:
            fetch_unavailable += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNVERIFIED",
                    "reason": f"fetch_failed:{type(exc).__name__}:{exc}",
                }
            )
            continue
        if not isinstance(transaction, Mapping):
            fetch_unavailable += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNVERIFIED",
                    "reason": "transaction_unavailable",
                }
            )
            continue

        try:
            report = verifier(
                transaction,
                signature=signature,
                rpc_url=rpc_url,
                asset_mint=asset_mint,
            )
        except Exception as exc:
            verification_errors += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNVERIFIED",
                    "reason": f"verification_failed:{type(exc).__name__}:{exc}",
                }
            )
            continue

        found = _field(report, "found") is True
        succeeded = _field(report, "succeeded") is True
        slot = _field(report, "slot")
        block_time = _field(report, "block_time")
        if not found or not succeeded:
            verification_errors += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNVERIFIED",
                    "reason": "successful_history_row_not_verified_successful",
                }
            )
            continue
        if slot != row.get("slot") or block_time is None or (
            float(block_time) != float(row.get("block_time"))
        ):
            identity_conflicts += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNVERIFIED",
                    "reason": "chain_identity_conflict",
                }
            )
            continue

        try:
            membership = membership_prover(
                verification_report=report,
                pool_identity=pool_identity,
                transaction=transaction,
            )
        except Exception as exc:
            classification_ambiguities += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNCLASSIFIED",
                    "reason": f"membership_proof_failed:{type(exc).__name__}:{exc}",
                }
            )
            continue
        if not isinstance(membership, Mapping):
            classification_ambiguities += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNCLASSIFIED",
                    "reason": "membership_proof_malformed",
                }
            )
            continue

        membership_verified = (
            membership.get("contract_version") == "x1_transaction_pool_membership/v3"
            and membership.get("transaction_signature") == signature
            and membership.get("pool_address") == pool_address
            and membership.get("transaction_pool_membership_verified") is True
        )

        recognized_amm = membership.get("recognized_amm_invoked") is True
        if not membership_verified:
            if recognized_amm:
                classification_ambiguities += 1
                classification = "UNCLASSIFIED_RECOGNIZED_AMM_ACTIVITY"
            else:
                classification = "NON_SWAP_POOL_ADDRESS_ACTIVITY"
            records.append(
                {
                    "signature": signature,
                    "slot": slot,
                    "block_time": float(block_time),
                    "classification": classification,
                    "membership_verified": False,
                    "rejection_reasons": list(
                        membership.get("rejection_reasons") or []
                    ),
                }
            )
            continue

        asset_delta = _report_token_delta(report, asset_vault)
        counter_delta = _report_token_delta(report, counter_vault)
        if asset_delta is None or counter_delta is None:
            classification_ambiguities += 1
            records.append(
                {
                    "signature": signature,
                    "classification": "UNCLASSIFIED",
                    "reason": "verified_pool_membership_without_unique_vault_deltas",
                }
            )
            continue

        opposite_signs = (
            asset_delta["delta_raw"] != 0
            and counter_delta["delta_raw"] != 0
            and (
                (asset_delta["delta_raw"] > 0 and counter_delta["delta_raw"] < 0)
                or (
                    asset_delta["delta_raw"] < 0
                    and counter_delta["delta_raw"] > 0
                )
            )
        )
        if not opposite_signs:
            records.append(
                {
                    "signature": signature,
                    "slot": slot,
                    "block_time": float(block_time),
                    "classification": "EXACT_POOL_LIQUIDITY_EVENT",
                    "membership_verified": True,
                    "asset_vault_delta_ui": format(
                        asset_delta["delta_ui"], "f"
                    ),
                    "counter_vault_delta_ui": format(
                        counter_delta["delta_ui"], "f"
                    ),
                }
            )
            continue

        swap_signatures.add(signature)
        quote_amount = abs(counter_delta["delta_ui"])
        quote_volume += quote_amount
        usd_value = None
        usd_evidence: Mapping[str, Any] = {}
        if usd_quote_resolver is not None:
            try:
                candidate = usd_quote_resolver(
                    block_time=float(block_time),
                    quote_mint=counter_mint,
                    quote_amount=quote_amount,
                    pool_identity=pool_identity,
                    transaction=transaction,
                    verification_report=report,
                )
            except Exception:
                candidate = {}
            if isinstance(candidate, Mapping):
                usd_evidence = candidate
                if (
                    candidate.get("historical_usd_value_verified") is True
                    and candidate.get("quote_mint") == counter_mint
                    and candidate.get("fact_time_verified") is True
                ):
                    try:
                        usd_value = _nonnegative_decimal(
                            candidate.get("usd_value"),
                            name="historical swap usd_value",
                        )
                    except X1Rolling24hMarketActivityError:
                        usd_value = None

        if usd_value is not None:
            usd_volume += usd_value
            usd_valued_swap_count += 1
        else:
            nonzero_usd_valuation_semantics_verified = False

        records.append(
            {
                "signature": signature,
                "slot": slot,
                "block_time": float(block_time),
                "classification": "EXACT_POOL_SWAP",
                "membership_verified": True,
                "asset_vault_delta_ui": format(asset_delta["delta_ui"], "f"),
                "counter_vault_delta_ui": format(
                    counter_delta["delta_ui"], "f"
                ),
                "quote_mint": counter_mint,
                "quote_volume": format(quote_amount, "f"),
                "historical_usd_value_verified": usd_value is not None,
                "usd_value": (
                    format(usd_value, "f") if usd_value is not None else None
                ),
                "usd_evidence": dict(usd_evidence),
            }
        )

    all_successful_transactions_verified = bool(
        fetch_unavailable == 0
        and verification_errors == 0
        and identity_conflicts == 0
        and len(records) == len(successful_rows)
    )
    all_activity_classified = bool(
        all_successful_transactions_verified and classification_ambiguities == 0
    )
    window_coverage_verified = bool(
        range_proven and integrity_verified and all_activity_classified
    )
    swap_count = len(swap_signatures)

    # Exact zero requires no exchange-rate assumption: 0 quote units == $0.
    if window_coverage_verified and swap_count == 0:
        usd_valuation_coverage_verified = True
        derived_volume_usd = Decimal(0)
        usd_basis = "exact_zero_swap_volume_requires_no_price_conversion"
        nonzero_usd_valuation_semantics_verified = False
    else:
        usd_valuation_coverage_verified = bool(
            window_coverage_verified
            and swap_count > 0
            and usd_valued_swap_count == swap_count
            and nonzero_usd_valuation_semantics_verified
        )
        derived_volume_usd = (
            usd_volume if usd_valuation_coverage_verified else None
        )
        usd_basis = (
            "verified_historical_quote_usd_value_per_exact_swap"
            if usd_valuation_coverage_verified
            else "historical_quote_usd_valuation_incomplete"
        )

    return {
        "contract_version": POOL_WINDOW_CONTRACT,
        "chain": "x1",
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "counter_mint": counter_mint,
        "requested_window": {
            "start_epoch": format(start, "f"),
            "end_epoch": format(end, "f"),
            "duration_seconds": format(duration, "f"),
            "membership_basis": (
                "X1_RPC_POOL_ADDRESS_HISTORY_PLUS_EXACT_AMM_POOL_VAULT_MEMBERSHIP"
            ),
        },
        "history_range_proven": range_proven,
        "history_integrity_verified": integrity_verified,
        "history_scan": scan,
        "window_signature_count": len(in_window),
        "successful_window_signature_count": len(successful_rows),
        "failed_window_signature_count": len(failed_rows),
        "transaction_fetch_unavailable_count": fetch_unavailable,
        "transaction_verification_error_count": verification_errors,
        "transaction_identity_conflict_count": identity_conflicts,
        "classification_ambiguity_count": classification_ambiguities,
        "all_successful_transactions_verified": all_successful_transactions_verified,
        "all_pool_relevant_transactions_classified": all_activity_classified,
        "transactions_24h_window_coverage_verified": window_coverage_verified,
        "transaction_count_definition": (
            "unique_successful_exact_pool_swap_transaction_signatures"
        ),
        "swap_count_semantics_verified": window_coverage_verified,
        "verified_transactions_24h": swap_count if window_coverage_verified else None,
        "quote_volume_semantics_verified": window_coverage_verified,
        "verified_quote_volume_24h": (
            format(quote_volume, "f") if window_coverage_verified else None
        ),
        "verified_quote_volume_unit": counter_mint if window_coverage_verified else None,
        "usd_valuation_coverage_verified": usd_valuation_coverage_verified,
        "nonzero_volume_usd_semantics_verified": (
            nonzero_usd_valuation_semantics_verified
            and usd_valuation_coverage_verified
        ),
        "usd_valuation_basis": usd_basis,
        "verified_volume_24h_usd": (
            format(derived_volume_usd, "f")
            if derived_volume_usd is not None
            else None
        ),
        "volume_24h_value_verified": bool(
            window_coverage_verified and derived_volume_usd is not None
        ),
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "read_only": True,
        "execution_authorized": False,
        "transactions": records,
    }


def _contributing_pool_addresses(market_envelope: Mapping[str, Any]) -> list[str]:
    data = _mapping(market_envelope.get("data"))
    raw = data.get("contributing_pools")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    result = []
    seen = set()
    for row in raw:
        if not isinstance(row, Mapping):
            return []
        address = _text(row.get("address"))
        if not address or address in seen:
            return []
        seen.add(address)
        result.append(address)
    return result


def evaluate_x1_rolling_24h_market_activity(
    *,
    market_envelope: Mapping[str, Any],
    pool_scope_evidence: Mapping[str, Any],
    pool_windows: Sequence[Mapping[str, Any]],
    evaluated_at: Any,
    relative_volume_tolerance: Any = DEFAULT_RELATIVE_VOLUME_TOLERANCE,
    absolute_volume_tolerance_usd: Any = DEFAULT_ABSOLUTE_VOLUME_TOLERANCE_USD,
) -> dict[str, Any]:
    """Compare complete exact-pool chain windows to Ninja rolling 24h fields."""

    if not isinstance(market_envelope, Mapping):
        raise TypeError("market_envelope must be a mapping")
    if not isinstance(pool_scope_evidence, Mapping):
        raise TypeError("pool_scope_evidence must be a mapping")
    if not isinstance(pool_windows, Sequence) or isinstance(
        pool_windows, (str, bytes, bytearray)
    ):
        raise TypeError("pool_windows must be a sequence")

    evaluated = _nonnegative_decimal(evaluated_at, name="evaluated_at")
    rel = _nonnegative_decimal(
        relative_volume_tolerance, name="relative_volume_tolerance"
    )
    abs_usd = _nonnegative_decimal(
        absolute_volume_tolerance_usd,
        name="absolute_volume_tolerance_usd",
    )

    data = _mapping(market_envelope.get("data"))
    completeness = _mapping(data.get("completeness"))
    asset = _mapping(market_envelope.get("asset"))
    asset_mint = _text(asset.get("mint") or data.get("mint"))
    addresses = _contributing_pool_addresses(market_envelope)

    failures: list[str] = []
    if not asset_mint:
        failures.append("market_asset_mint_unavailable")
    if completeness.get("volume_24h") is not True:
        failures.append("market_volume_24h_incomplete")
    if completeness.get("transactions_24h") is not True:
        failures.append("market_transactions_24h_incomplete")
    if not addresses:
        failures.append("market_contributing_pool_set_unavailable")

    scope = _mapping(pool_scope_evidence)
    scope_verified = bool(
        scope.get("contract_version") == POOL_SCOPE_CONTRACT
        and scope.get("provider_scoped_pool_universe_verified") is True
        and scope.get("global_xdex_pool_universe_verified") is False
        and scope.get("asset_mint") == asset_mint
        and set(scope.get("market_contributing_pool_addresses") or [])
        == set(addresses)
        and set(scope.get("current_catalog_exact_mint_pool_addresses") or [])
        == set(addresses)
        and scope.get("execution_authorized") is False
    )
    if not scope_verified:
        failures.append("provider_scoped_pool_universe_unverified")

    by_pool: dict[str, Mapping[str, Any]] = {}
    duplicate_pool = False
    for raw in pool_windows:
        if not isinstance(raw, Mapping):
            failures.append("pool_window_malformed")
            continue
        address = _text(raw.get("pool_address"))
        if not address:
            failures.append("pool_window_address_unavailable")
            continue
        if address in by_pool:
            duplicate_pool = True
            continue
        by_pool[address] = raw
    if duplicate_pool:
        failures.append("duplicate_pool_window")
    if set(by_pool) != set(addresses):
        failures.append("pool_window_set_mismatch")

    common_start = None
    common_end = None
    transaction_windows_verified = True
    volume_windows_verified = True
    chain_transaction_total = 0
    chain_volume_total = Decimal(0)
    nonzero_volume_usd_semantics_verified = True
    window_summaries = []

    for address in addresses:
        window = by_pool.get(address)
        if not isinstance(window, Mapping):
            transaction_windows_verified = False
            volume_windows_verified = False
            continue
        requested = _mapping(window.get("requested_window"))
        try:
            start = _nonnegative_decimal(
                requested.get("start_epoch"), name="pool window start_epoch"
            )
            end = _nonnegative_decimal(
                requested.get("end_epoch"), name="pool window end_epoch"
            )
            duration = _nonnegative_decimal(
                requested.get("duration_seconds"),
                name="pool window duration_seconds",
            )
        except X1Rolling24hMarketActivityError:
            start = end = duration = None

        valid_shape = bool(
            window.get("contract_version") == POOL_WINDOW_CONTRACT
            and window.get("chain") == "x1"
            and window.get("asset_mint") == asset_mint
            and duration == WINDOW_SECONDS
            and window.get("execution_authorized") is False
        )
        if not valid_shape:
            failures.append(f"pool_window_contract_invalid:{address}")
            transaction_windows_verified = False
            volume_windows_verified = False

        if start is not None and end is not None:
            if common_start is None:
                common_start = start
                common_end = end
            elif start != common_start or end != common_end:
                failures.append("pool_windows_not_time_aligned")
                transaction_windows_verified = False
                volume_windows_verified = False

        tx_window_ok = bool(
            valid_shape
            and window.get("history_range_proven") is True
            and window.get("history_integrity_verified") is True
            and window.get("all_successful_transactions_verified") is True
            and window.get("all_pool_relevant_transactions_classified") is True
            and window.get("transactions_24h_window_coverage_verified") is True
            and window.get("swap_count_semantics_verified") is True
        )
        if not tx_window_ok:
            transaction_windows_verified = False

        tx_count = window.get("verified_transactions_24h")
        if tx_window_ok:
            try:
                chain_transaction_total += _nonnegative_int(
                    tx_count, name="verified_transactions_24h"
                )
            except X1Rolling24hMarketActivityError:
                transaction_windows_verified = False

        volume_ok = bool(
            tx_window_ok
            and window.get("quote_volume_semantics_verified") is True
            and window.get("usd_valuation_coverage_verified") is True
            and window.get("volume_24h_value_verified") is True
        )
        if not volume_ok:
            volume_windows_verified = False
        if window.get("nonzero_volume_usd_semantics_verified") is not True:
            nonzero_volume_usd_semantics_verified = False

        if volume_ok:
            try:
                chain_volume_total += _nonnegative_decimal(
                    window.get("verified_volume_24h_usd"),
                    name="verified_volume_24h_usd",
                )
            except X1Rolling24hMarketActivityError:
                volume_windows_verified = False

        window_summaries.append(
            {
                "pool_address": address,
                "transactions_window_verified": tx_window_ok,
                "volume_window_verified": volume_ok,
                "verified_transactions_24h": tx_count if tx_window_ok else None,
                "verified_volume_24h_usd": (
                    window.get("verified_volume_24h_usd") if volume_ok else None
                ),
                "usd_valuation_basis": window.get("usd_valuation_basis"),
            }
        )

    exact_window_verified = bool(
        common_start is not None
        and common_end is not None
        and common_end - common_start == WINDOW_SECONDS
        and abs(common_end - evaluated) <= Decimal("120")
    )
    if not exact_window_verified:
        failures.append("rolling_window_not_current_exact_24h")

    transactions_window_coverage_verified = bool(
        scope_verified
        and exact_window_verified
        and transaction_windows_verified
        and len(addresses) == len(by_pool)
    )
    volume_window_coverage_verified = bool(
        transactions_window_coverage_verified and volume_windows_verified
    )

    try:
        provider_transactions = _nonnegative_int(
            data.get("transactions_24h"), name="provider transactions_24h"
        )
    except X1Rolling24hMarketActivityError:
        provider_transactions = None
        failures.append("provider_transactions_24h_unusable")

    transaction_count_matches = bool(
        transactions_window_coverage_verified
        and provider_transactions is not None
        and provider_transactions == chain_transaction_total
    )
    if transactions_window_coverage_verified and not transaction_count_matches:
        failures.append("provider_transactions_24h_does_not_match_chain_swap_count")

    transactions_semantics_verified = transaction_count_matches
    transactions_freshness_verified = bool(
        transactions_window_coverage_verified and transactions_semantics_verified
    )

    volume_comparison = None
    try:
        provider_volume = _nonnegative_decimal(
            data.get("volume_24h_usd"), name="provider volume_24h_usd"
        )
    except X1Rolling24hMarketActivityError:
        provider_volume = None
        failures.append("provider_volume_24h_usd_unusable")

    if volume_window_coverage_verified and provider_volume is not None:
        volume_comparison = _comparison(
            provider_volume,
            chain_volume_total,
            relative_tolerance=rel,
            absolute_tolerance=abs_usd,
        )
        if volume_comparison["within_tolerance"] is not True:
            failures.append("provider_volume_24h_does_not_match_chain_reconstruction")

    volume_semantics_verified = bool(
        volume_window_coverage_verified
        and volume_comparison is not None
        and volume_comparison.get("within_tolerance") is True
    )
    volume_freshness_verified = bool(
        volume_window_coverage_verified and volume_semantics_verified
    )

    status = (
        "verified"
        if volume_freshness_verified and transactions_freshness_verified
        else (
            "partial"
            if volume_freshness_verified or transactions_freshness_verified
            else "unverified"
        )
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": "x1",
        "status": status,
        "scope": "exact_market_report_contributing_pool_set_current_24h_window",
        "asset_mint": asset_mint,
        "evaluated_at": format(evaluated, "f"),
        "requested_window": {
            "start_epoch": (
                format(common_start, "f") if common_start is not None else None
            ),
            "end_epoch": (
                format(common_end, "f") if common_end is not None else None
            ),
            "duration_seconds": (
                format(common_end - common_start, "f")
                if common_start is not None and common_end is not None
                else None
            ),
        },
        "provider_scoped_pool_universe_verified": scope_verified,
        "pool_count": len(addresses),
        "pool_windows": window_summaries,
        "transactions_24h_count_definition": (
            "unique_successful_exact_pool_swap_transaction_signatures_summed_across_exact_contributing_pools"
        ),
        "transactions_24h_window_coverage_verified": (
            transactions_window_coverage_verified
        ),
        "transactions_24h_semantics_verified": transactions_semantics_verified,
        "provider_transactions_24h": provider_transactions,
        "reconstructed_transactions_24h": (
            chain_transaction_total
            if transactions_window_coverage_verified
            else None
        ),
        "transactions_24h_freshness_verified": transactions_freshness_verified,
        "volume_24h_window_coverage_verified": volume_window_coverage_verified,
        "volume_24h_semantics_verified": volume_semantics_verified,
        "provider_volume_24h_usd": (
            format(provider_volume, "f") if provider_volume is not None else None
        ),
        "reconstructed_volume_24h_usd": (
            format(chain_volume_total, "f")
            if volume_window_coverage_verified
            else None
        ),
        "volume_24h_comparison": volume_comparison,
        "volume_24h_freshness_verified": volume_freshness_verified,
        "nonzero_volume_usd_semantics_verified": (
            nonzero_volume_usd_semantics_verified
            and volume_window_coverage_verified
        ),
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "failures": list(dict.fromkeys(failures)),
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_ABSOLUTE_VOLUME_TOLERANCE_USD",
    "DEFAULT_RELATIVE_VOLUME_TOLERANCE",
    "POOL_WINDOW_CONTRACT",
    "WINDOW_SECONDS",
    "X1Rolling24hMarketActivityError",
    "evaluate_x1_rolling_24h_market_activity",
    "reconstruct_x1_pool_24h_chain_activity",
]
