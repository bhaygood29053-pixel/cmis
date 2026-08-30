"""Correlate unexplained X1.Ninja catalog updates with exact vault activity.

This evidence layer follows #352 and #354. It looks only at the conservative
between-snapshot slot interval:

    BEFORE snapshot after-slot < transaction.slot <= AFTER snapshot before-slot

For each exact wrapped-XNT pool it queries both verified vault addresses,
deduplicates signatures, verifies transaction-level vault deltas, and compares
the sum of those deltas with X1.Ninja pooledBase/pooledQuote changes.

The accepted #341 reserve-field mapping is used exactly:

    pooledBase  -> decoded vault_1
    pooledQuote -> decoded vault_0

Transactions are classified conservatively. A direct-token-transfer label
requires a parsed Token Program transfer involving one exact vault and no
recognized XDEX AMM invocation. Same-sign two-vault XDEX mutations are only
called add/remove-liquidity-like because this module does not decode the AMM
instruction discriminator.

No causal/provider-source claim follows from timing correlation alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE as PRICE_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE as PRICE_RELATIVE_TOLERANCE,
)
from liquidity_scout.providers.x1.ninja_pooled_reserve_semantics import (
    DEFAULT_ABSOLUTE_TOLERANCE as RESERVE_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE as RESERVE_RELATIVE_TOLERANCE,
    DIRECT_MAPPING,
)
from liquidity_scout.providers.x1.program_accounts import (
    RECOGNIZED_AMM_PROGRAM_IDS,
)
from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    get_signatures_for_address,
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
DEFAULT_SIGNATURE_LIMIT = 100
ACCEPTED_POOLED_RESERVE_MAPPING = DIRECT_MAPPING


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _decimal(value: Any, *, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


def _nonnegative(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _compare(
    observed: Decimal,
    expected: Decimal,
    *,
    relative: Decimal,
    absolute: Decimal,
) -> dict[str, Any]:
    error = abs(observed - expected)
    scale = abs(expected)
    relative_error = (
        error / scale
        if scale != 0
        else (Decimal(0) if error == 0 else None)
    )
    allowed = max(absolute, scale * relative)
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
    lower_row = before_bracket.get("after")
    upper_row = after_bracket.get("before")
    lower_row = lower_row if isinstance(lower_row, Mapping) else {}
    upper_row = upper_row if isinstance(upper_row, Mapping) else {}
    lower = lower_row.get("slot")
    upper = upper_row.get("slot")
    if (
        isinstance(lower, bool)
        or not isinstance(lower, int)
        or isinstance(upper, bool)
        or not isinstance(upper, int)
        or upper <= lower
    ):
        raise ValueError("safe between-snapshot slot window unavailable")
    return lower, upper


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


def _verified_pool_structure(
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
            report = structural_verifier(
                account=pool_address,
                target_mint=WXNT_MINT,
                program_id=program_id,
                rpc_url=rpc_url,
                signature_limit=1,
            )
        except Exception:
            continue

        if report.get("summary", {}).get(
            "pool_state_structural_role_verified"
        ) is not True:
            continue
        decoded = report.get("decoded_state")
        decoded = decoded if isinstance(decoded, Mapping) else {}

        mint0 = _text(decoded.get("mint_0"))
        mint1 = _text(decoded.get("mint_1"))
        vault0 = _text(decoded.get("vault_0"))
        vault1 = _text(decoded.get("vault_1"))
        owner = _text(report.get("shared_vault_authority"))
        if not all((mint0, mint1, vault0, vault1, owner)):
            continue
        if vault0 == vault1 or mint0 == mint1:
            continue

        if mint0 == WXNT_MINT and mint1 != WXNT_MINT:
            asset_mint = mint1
            asset_vault = vault1
            counter_mint = mint0
            counter_vault = vault0
            xnt_slot = 0
        elif mint1 == WXNT_MINT and mint0 != WXNT_MINT:
            asset_mint = mint0
            asset_vault = vault0
            counter_mint = mint1
            counter_vault = vault1
            xnt_slot = 1
        else:
            continue

        return ({
            "chain": "x1",
            "pool_address": pool_address,
            "mint_0": mint0,
            "mint_1": mint1,
            "vault_0": vault0,
            "vault_1": vault1,
            "asset_mint": asset_mint,
            "asset_vault": asset_vault,
            "counter_mint": counter_mint,
            "counter_vault": counter_vault,
            "shared_owner": owner,
            "xnt_slot": xnt_slot,
            "identity_verified": True,
        }, program_id)

    raise ValueError("exact wrapped-XNT pool structure unverified")


def _vault_delta(
    report: VerificationReport,
    *,
    account: str,
    mint: str,
):
    rows = [
        row
        for row in report.token_deltas
        if row.account == account and row.mint == mint
    ]
    if len(rows) > 1:
        raise ValueError("duplicate exact vault token delta")
    return rows[0] if rows else None


def _instruction_rows(transaction: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    raw_tx = transaction.get("transaction")
    raw_tx = raw_tx if isinstance(raw_tx, Mapping) else {}
    message = raw_tx.get("message")
    message = message if isinstance(message, Mapping) else {}
    top = message.get("instructions")
    if isinstance(top, Sequence) and not isinstance(top, (str, bytes)):
        rows.extend(row for row in top if isinstance(row, Mapping))

    meta = transaction.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    inner = meta.get("innerInstructions")
    if isinstance(inner, Sequence) and not isinstance(inner, (str, bytes)):
        for group in inner:
            if not isinstance(group, Mapping):
                continue
            instructions = group.get("instructions")
            if isinstance(instructions, Sequence) and not isinstance(
                instructions, (str, bytes)
            ):
                rows.extend(
                    row for row in instructions if isinstance(row, Mapping)
                )
    return rows


def _parsed_vault_transfer_evidence(
    transaction: Mapping[str, Any],
    *,
    vaults: set[str],
) -> list[dict[str, Any]]:
    evidence = []
    for row in _instruction_rows(transaction):
        parsed = row.get("parsed")
        if not isinstance(parsed, Mapping):
            continue
        transfer_type = _text(parsed.get("type"))
        if transfer_type not in {"transfer", "transferChecked"}:
            continue
        info = parsed.get("info")
        if not isinstance(info, Mapping):
            continue
        source = _text(info.get("source"))
        destination = _text(info.get("destination"))
        touched = sorted(
            vault for vault in vaults if vault in {source, destination}
        )
        if not touched:
            continue
        evidence.append({
            "type": transfer_type,
            "source": source,
            "destination": destination,
            "vaults_touched": touched,
        })
    return evidence


def _classify_vault_transaction(
    *,
    transaction: Mapping[str, Any],
    report: VerificationReport,
    identity: Mapping[str, Any],
    membership_prover: Callable[..., Mapping[str, Any]],
) -> dict[str, Any]:
    asset = _vault_delta(
        report,
        account=identity["asset_vault"],
        mint=identity["asset_mint"],
    )
    counter = _vault_delta(
        report,
        account=identity["counter_vault"],
        mint=identity["counter_mint"],
    )

    asset_delta = asset.delta_ui if asset is not None else Decimal(0)
    counter_delta = counter.delta_ui if counter is not None else Decimal(0)
    asset_changed = asset_delta != 0
    counter_changed = counter_delta != 0

    if not asset_changed and not counter_changed:
        raise ValueError("transaction does not mutate either exact vault")

    transfer_evidence = _parsed_vault_transfer_evidence(
        transaction,
        vaults={
            identity["asset_vault"],
            identity["counter_vault"],
        },
    )

    membership = None
    if asset_changed and counter_changed and (
        report.xdex_amm_invoked or report.xendex_amm_invoked
    ):
        try:
            membership = membership_prover(
                verification_report=report,
                pool_identity=identity,
                transaction=transaction,
            )
        except Exception:
            membership = None

    exact_pool_amm = bool(
        isinstance(membership, Mapping)
        and membership.get("transaction_pool_membership_verified") is True
        and membership.get("recognized_amm_instruction_count") == 1
        and membership.get("selected_pool_instruction_count") == 1
    )

    execution_price = None
    classification = "other_or_ambiguous_vault_mutation"

    if exact_pool_amm:
        if asset_delta < 0 and counter_delta > 0:
            classification = "exact_xdex_swap"
            execution_price = abs(counter_delta) / abs(asset_delta)
        elif asset_delta > 0 and counter_delta < 0:
            classification = "exact_xdex_swap"
            execution_price = abs(counter_delta) / abs(asset_delta)
        elif asset_delta > 0 and counter_delta > 0:
            classification = "xdex_add_liquidity_like"
        elif asset_delta < 0 and counter_delta < 0:
            classification = "xdex_remove_liquidity_like"
    elif (
        asset_changed != counter_changed
        and not report.xdex_amm_invoked
        and not report.xendex_amm_invoked
        and transfer_evidence
    ):
        classification = "direct_token_transfer"
    elif asset_changed and counter_changed and not (
        report.xdex_amm_invoked or report.xendex_amm_invoked
    ):
        classification = "non_amm_two_vault_mutation"

    return {
        "classification": classification,
        "asset_vault_delta": format(asset_delta, "f"),
        "counter_vault_delta": format(counter_delta, "f"),
        "asset_vault_mutated": asset_changed,
        "counter_vault_mutated": counter_changed,
        "execution_price_native": (
            format(execution_price, "f")
            if execution_price is not None
            else None
        ),
        "parsed_transfer_evidence": transfer_evidence,
        "recognized_amm_invoked": bool(
            report.xdex_amm_invoked or report.xendex_amm_invoked
        ),
        "exact_pool_amm_membership_verified": exact_pool_amm,
        "membership": dict(membership) if isinstance(membership, Mapping) else None,
    }


def _history_window(
    address: str,
    *,
    lower: int,
    upper: int,
    limit: int,
    rpc_url: str,
    signature_fetcher: Callable[..., Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = signature_fetcher(address, limit=limit, rpc_url=rpc_url)
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("vault signature history unavailable")

    normalized = [row for row in rows if isinstance(row, Mapping)]
    slots = [
        row.get("slot")
        for row in normalized
        if isinstance(row.get("slot"), int)
        and not isinstance(row.get("slot"), bool)
    ]
    complete = bool(
        len(normalized) < limit
        or (slots and min(slots) <= lower)
    )

    in_window = []
    for row in normalized:
        if row.get("err") is not None:
            continue
        slot = row.get("slot")
        signature = _text(row.get("signature"))
        if (
            signature
            and isinstance(slot, int)
            and not isinstance(slot, bool)
            and lower < slot <= upper
        ):
            in_window.append({
                "signature": signature,
                "slot": slot,
                "block_time": row.get("block_time"),
                "confirmation_status": row.get("confirmation_status"),
            })

    return {
        "address": address,
        "history_complete_for_window": complete,
        "returned_row_count": len(normalized),
        "in_window": in_window,
    }


def verify_vault_activity_transition(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    pool_address: str,
    signature_limit: int = DEFAULT_SIGNATURE_LIMIT,
    rpc_url: str = DEFAULT_X1_RPC_URL,
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
    reserve_relative_tolerance: Any = RESERVE_RELATIVE_TOLERANCE,
    reserve_absolute_tolerance: Any = RESERVE_ABSOLUTE_TOLERANCE,
    price_relative_tolerance: Any = PRICE_RELATIVE_TOLERANCE,
    price_absolute_tolerance: Any = PRICE_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    """Correlate one unexplained catalog transition with both exact vaults."""

    pool_address = _text(pool_address)
    if not pool_address:
        raise ValueError("pool_address is required")
    if isinstance(signature_limit, bool) or not isinstance(signature_limit, int):
        raise ValueError("signature_limit must be an integer")
    if not 1 <= signature_limit <= DEFAULT_SIGNATURE_LIMIT:
        raise ValueError("signature_limit must be from 1 to 100")
    if ACCEPTED_POOLED_RESERVE_MAPPING != (
        "pooledBase_to_vault1__pooledQuote_to_vault0"
    ):
        raise ValueError("accepted pooled-reserve mapping changed unexpectedly")

    before_row = _provider_row(before, pool_address)
    after_row = _provider_row(after, pool_address)
    if not isinstance(before_row, Mapping) or not isinstance(after_row, Mapping):
        raise ValueError("pool missing from BEFORE/AFTER snapshots")
    if before_row.get("status") != "ok" or after_row.get("status") != "ok":
        raise ValueError("pool snapshot status is not ok")

    before_provider = before_row.get("provider")
    after_provider = after_row.get("provider")
    if not isinstance(before_provider, Mapping) or not isinstance(
        after_provider, Mapping
    ):
        raise ValueError("provider row data unavailable")

    before_price = _nonnegative(
        before_provider.get("priceNative"),
        name="BEFORE priceNative",
    )
    after_price = _nonnegative(
        after_provider.get("priceNative"),
        name="AFTER priceNative",
    )
    before_base = _nonnegative(
        before_provider.get("pooledBase"),
        name="BEFORE pooledBase",
    )
    after_base = _nonnegative(
        after_provider.get("pooledBase"),
        name="AFTER pooledBase",
    )
    before_quote = _nonnegative(
        before_provider.get("pooledQuote"),
        name="BEFORE pooledQuote",
    )
    after_quote = _nonnegative(
        after_provider.get("pooledQuote"),
        name="AFTER pooledQuote",
    )

    price_changed = before_price != after_price
    provider_base_delta = after_base - before_base
    provider_quote_delta = after_quote - before_quote
    provider_reserve_changed = bool(
        provider_base_delta != 0 or provider_quote_delta != 0
    )

    lower, upper = _safe_slot_window(before, after)
    identity, program_id = _verified_pool_structure(
        pool_address,
        structural_verifier=structural_verifier,
        recognized_program_ids=recognized_program_ids,
        rpc_url=rpc_url,
    )

    vault0_history = _history_window(
        identity["vault_0"],
        lower=lower,
        upper=upper,
        limit=signature_limit,
        rpc_url=rpc_url,
        signature_fetcher=signature_fetcher,
    )
    vault1_history = _history_window(
        identity["vault_1"],
        lower=lower,
        upper=upper,
        limit=signature_limit,
        rpc_url=rpc_url,
        signature_fetcher=signature_fetcher,
    )

    history_complete = bool(
        vault0_history["history_complete_for_window"]
        and vault1_history["history_complete_for_window"]
    )
    if not history_complete:
        return {
            "service": "x1_ninja_vault_activity_transition",
            "version": VERSION,
            "chain": "x1",
            "status": "unavailable",
            "pool_address": pool_address,
            "price_changed": price_changed,
            "provider_reserve_changed": provider_reserve_changed,
            "vault_history_complete_for_window": False,
            "vault_activity_correlated": False,
            "provider_reserve_delta_matches_vault_delta": False,
            "price_only_update_observed": False,
            "catalog_price_execution_link_verified": False,
            "catalog_price_reserve_ratio_link_verified": False,
            "catalog_price_active_reserve_link_verified": False,
            "provider_fact_time_verified": False,
            "update_source_semantics_verified": False,
            "freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
            "warnings": ["vault_history_does_not_cover_safe_slot_window"],
        }

    signatures: dict[str, dict[str, Any]] = {}
    for source_name, history in (
        ("vault_0", vault0_history),
        ("vault_1", vault1_history),
    ):
        for row in history["in_window"]:
            signature = row["signature"]
            record = signatures.setdefault(signature, {
                "signature": signature,
                "slot": row["slot"],
                "block_time": row.get("block_time"),
                "seen_on": [],
            })
            if record["slot"] != row["slot"]:
                raise ValueError("same signature has inconsistent vault-history slot")
            record["seen_on"].append(source_name)

    transactions = []
    rejections = []
    sum_vault0 = Decimal(0)
    sum_vault1 = Decimal(0)

    for signature, history_row in sorted(
        signatures.items(),
        key=lambda item: item[1]["slot"],
    ):
        try:
            tx = transaction_fetcher(signature, rpc_url=rpc_url)
            if not isinstance(tx, Mapping):
                raise ValueError("transaction unavailable")
            report = transaction_verifier(
                tx,
                signature=signature,
                rpc_url=rpc_url,
            )
            if report.found is not True or report.succeeded is not True:
                raise ValueError("transaction not found/successful")
            if report.slot != history_row["slot"]:
                raise ValueError("vault-history slot mismatches transaction slot")

            vault0 = _vault_delta(
                report,
                account=identity["vault_0"],
                mint=identity["mint_0"],
            )
            vault1 = _vault_delta(
                report,
                account=identity["vault_1"],
                mint=identity["mint_1"],
            )
            vault0_delta = (
                vault0.delta_ui if vault0 is not None else Decimal(0)
            )
            vault1_delta = (
                vault1.delta_ui if vault1 is not None else Decimal(0)
            )
            if vault0_delta == 0 and vault1_delta == 0:
                raise ValueError("history signature has no exact vault delta")

            classified = _classify_vault_transaction(
                transaction=tx,
                report=report,
                identity=identity,
                membership_prover=membership_prover,
            )
            sum_vault0 += vault0_delta
            sum_vault1 += vault1_delta
            transactions.append({
                "signature": signature,
                "slot": report.slot,
                "block_time": report.block_time,
                "seen_on": sorted(set(history_row["seen_on"])),
                "program_ids": list(report.program_ids),
                **classified,
            })
        except Exception as exc:
            rejections.append({
                "signature": signature,
                "slot": history_row["slot"],
                "error": f"{type(exc).__name__}: {exc}",
            })

    reserve_relative = _nonnegative(
        reserve_relative_tolerance,
        name="reserve_relative_tolerance",
    )
    reserve_absolute = _nonnegative(
        reserve_absolute_tolerance,
        name="reserve_absolute_tolerance",
    )
    price_relative = _nonnegative(
        price_relative_tolerance,
        name="price_relative_tolerance",
    )
    price_absolute = _nonnegative(
        price_absolute_tolerance,
        name="price_absolute_tolerance",
    )

    # Accepted #341 mapping:
    # pooledBase -> vault_1; pooledQuote -> vault_0.
    base_delta_comparison = _compare(
        provider_base_delta,
        sum_vault1,
        relative=reserve_relative,
        absolute=reserve_absolute,
    )
    quote_delta_comparison = _compare(
        provider_quote_delta,
        sum_vault0,
        relative=reserve_relative,
        absolute=reserve_absolute,
    )
    reserve_delta_match = bool(
        base_delta_comparison["within_tolerance"]
        and quote_delta_comparison["within_tolerance"]
    )

    vault_mutation_observed = bool(
        sum_vault0 != 0 or sum_vault1 != 0 or transactions
    )
    vault_activity_correlated = bool(
        vault_mutation_observed and reserve_delta_match
    )
    price_only_update = bool(
        price_changed
        and not provider_reserve_changed
        and not vault_mutation_observed
        and not rejections
    )

    if identity["xnt_slot"] == 0:
        xnt_reserve = after_quote
        asset_reserve = after_base
    else:
        xnt_reserve = after_base
        asset_reserve = after_quote

    reserve_ratio_comparison = None
    reserve_ratio_link = False
    if asset_reserve > 0:
        gross_ratio = xnt_reserve / asset_reserve
        reserve_ratio_comparison = _compare(
            after_price,
            gross_ratio,
            relative=price_relative,
            absolute=price_absolute,
        )
        reserve_ratio_link = bool(
            reserve_ratio_comparison["within_tolerance"]
        )

    swap_matches = []
    for row in transactions:
        execution_raw = row.get("execution_price_native")
        if row.get("classification") != "exact_xdex_swap" or execution_raw is None:
            continue
        execution_price = _nonnegative(
            execution_raw,
            name="execution_price_native",
        )
        comparison = _compare(
            after_price,
            execution_price,
            relative=price_relative,
            absolute=price_absolute,
        )
        row["after_price_vs_execution_price"] = comparison
        if comparison["within_tolerance"]:
            swap_matches.append(row)

    execution_link = bool(len(swap_matches) == 1)

    classifications: dict[str, int] = {}
    for row in transactions:
        key = row["classification"]
        classifications[key] = classifications.get(key, 0) + 1

    return {
        "service": "x1_ninja_vault_activity_transition",
        "version": VERSION,
        "chain": "x1",
        "status": (
            "verified"
            if (
                vault_activity_correlated
                or price_only_update
                or execution_link
                or reserve_ratio_link
            )
            else ("partial" if transactions or price_changed else "unavailable")
        ),
        "pool_address": pool_address,
        "program_id": program_id,
        "identity": identity,
        "safe_slot_window": {
            "exclusive_lower_slot": lower,
            "inclusive_upper_slot": upper,
        },
        "accepted_pooled_reserve_mapping": ACCEPTED_POOLED_RESERVE_MAPPING,
        "before_provider": dict(before_provider),
        "after_provider": dict(after_provider),
        "price_changed": price_changed,
        "provider_reserve_changed": provider_reserve_changed,
        "provider_reserve_deltas": {
            "pooledBase": format(provider_base_delta, "f"),
            "pooledQuote": format(provider_quote_delta, "f"),
        },
        "vault_history_complete_for_window": history_complete,
        "vault_histories": {
            "vault_0": vault0_history,
            "vault_1": vault1_history,
        },
        "unique_vault_history_signature_count": len(signatures),
        "verified_vault_transaction_count": len(transactions),
        "transaction_classification_counts": classifications,
        "transactions": transactions,
        "rejections": rejections,
        "summed_exact_vault_deltas": {
            "vault_0": format(sum_vault0, "f"),
            "vault_1": format(sum_vault1, "f"),
        },
        "reserve_delta_comparisons": {
            "pooledBase_vs_vault_1_delta": base_delta_comparison,
            "pooledQuote_vs_vault_0_delta": quote_delta_comparison,
        },
        "vault_activity_correlated": vault_activity_correlated,
        "provider_reserve_delta_matches_vault_delta": reserve_delta_match,
        "price_only_update_observed": price_only_update,
        "catalog_price_execution_link_verified": execution_link,
        "catalog_price_execution_match_count": len(swap_matches),
        "catalog_price_reserve_ratio_link_verified": reserve_ratio_link,
        "catalog_price_reserve_ratio_comparison": reserve_ratio_comparison,
        "catalog_price_active_reserve_link_verified": False,
        "active_reserve_model_available": False,
        "provider_timestamp_candidates": {
            "before_lastSyncedAt_raw": before_provider.get("lastSyncedAt_raw"),
            "after_lastSyncedAt_raw": after_provider.get("lastSyncedAt_raw"),
            "before_global_lastUpdated_raw": (
                before.get("provider_timestamp_candidates", {}).get(
                    "global_lastUpdated_raw"
                )
                if isinstance(before.get("provider_timestamp_candidates"), Mapping)
                else None
            ),
            "after_global_lastUpdated_raw": (
                after.get("provider_timestamp_candidates", {}).get(
                    "global_lastUpdated_raw"
                )
                if isinstance(after.get("provider_timestamp_candidates"), Mapping)
                else None
            ),
        },
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "universal_catalog_price_semantics_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_vault_activity_evidence(
    events: Sequence[Mapping[str, Any]],
    *,
    minimum_events: int = 5,
) -> dict[str, Any]:
    """Aggregate unexplained catalog-transition vault evidence."""

    if isinstance(minimum_events, bool) or not isinstance(minimum_events, int):
        raise ValueError("minimum_events must be an integer")
    if minimum_events < 5:
        raise ValueError("minimum_events must be at least 5")

    rows = [dict(row) for row in events if isinstance(row, Mapping)]
    correlated = [row for row in rows if row.get("vault_activity_correlated") is True]
    reserve_matches = [
        row
        for row in rows
        if row.get("provider_reserve_delta_matches_vault_delta") is True
    ]
    price_only = [
        row for row in rows if row.get("price_only_update_observed") is True
    ]
    execution_links = [
        row
        for row in rows
        if row.get("catalog_price_execution_link_verified") is True
    ]
    reserve_ratio_links = [
        row
        for row in rows
        if row.get("catalog_price_reserve_ratio_link_verified") is True
    ]

    enough = len(rows) >= minimum_events
    all_complete = bool(
        rows
        and all(
            row.get("vault_history_complete_for_window") is True
            for row in rows
        )
    )

    return {
        "service": "x1_ninja_vault_activity_evidence",
        "version": VERSION,
        "chain": "x1",
        "status": (
            "verified"
            if enough and all_complete
            else ("partial" if rows else "unavailable")
        ),
        "event_count": len(rows),
        "minimum_event_count": minimum_events,
        "all_vault_histories_complete": all_complete,
        "vault_activity_correlated_event_count": len(correlated),
        "provider_reserve_delta_match_event_count": len(reserve_matches),
        "price_only_update_event_count": len(price_only),
        "catalog_execution_link_event_count": len(execution_links),
        "catalog_reserve_ratio_link_event_count": len(reserve_ratio_links),
        "vault_activity_correlated": bool(enough and correlated),
        "provider_reserve_delta_matches_vault_delta": bool(
            enough and reserve_matches
        ),
        "price_only_update_observed": bool(price_only),
        "catalog_price_execution_link_verified": False,
        "catalog_price_reserve_ratio_link_verified": False,
        "catalog_price_active_reserve_link_verified": False,
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
    "ACCEPTED_POOLED_RESERVE_MAPPING",
    "DEFAULT_SIGNATURE_LIMIT",
    "VERSION",
    "aggregate_vault_activity_evidence",
    "verify_vault_activity_transition",
]
