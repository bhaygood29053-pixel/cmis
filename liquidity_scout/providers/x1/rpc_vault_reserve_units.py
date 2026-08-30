"""Verify X1 XDEX vault balances, decimals, and reserve-unit scaling.

This is an RPC-first reserve-unit gate. It builds only on already accepted XDEX
pool-state identity and token-position evidence:

    XDEX token1 -> RPC mint_0 -> vault_0
    XDEX token2 -> RPC mint_1 -> vault_1

For each selected current exact common pool, the module:
- re-verifies the pool's accepted XDEX structural role;
- reads each decoded vault through X1 RPC jsonParsed token-account data;
- preserves the raw integer balance;
- verifies the vault mint and decimals;
- scales raw amount / 10^decimals exactly as a decimal string.

Provider reserve/liquidity-looking fields are preserved only as raw candidate
evidence. This module does not assign base/quote roles, USD values, liquidity
formulae, price, volume, market-cap, freshness, source-independence, or
execution semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import verify_candidate_pool_role
from liquidity_scout.providers.x1.program_accounts import RECOGNIZED_AMM_PROGRAM_IDS
from liquidity_scout.providers.x1.rpc import get_token_account_info


VERSION = "1.0"

_RAW_CANDIDATE_KEYS = {
    "pooledbase",
    "pooledquote",
    "basereserve",
    "quotereserve",
    "reserve0",
    "reserve1",
    "reserve_0",
    "reserve_1",
    "amount1",
    "amount2",
    "tvl",
    "liquidity",
}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pool_address(row: Mapping[str, Any]) -> str | None:
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


def _xdex_token_positions(row: Mapping[str, Any]) -> tuple[str, str] | None:
    token1 = _text(
        row.get("token1_address")
        or row.get("token1Address")
        or row.get("token1_mint")
        or row.get("token1Mint")
    )
    token2 = _text(
        row.get("token2_address")
        or row.get("token2Address")
        or row.get("token2_mint")
        or row.get("token2Mint")
    )
    if not token1 or not token2 or token1 == token2:
        return None
    return token1, token2


def _common_rows(
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    ninja_index: dict[str, Mapping[str, Any]] = {}
    for row in ninja_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if address and address not in ninja_index:
            ninja_index[address] = row

    result: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    seen: set[str] = set()
    for row in xdex_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if (
            not address
            or address in seen
            or address not in ninja_index
            or _xdex_token_positions(row) is None
        ):
            continue
        seen.add(address)
        result.append((ninja_index[address], row))
    return result


def _exact_scaled_amount(raw_amount: Any, decimals: Any) -> str | None:
    if isinstance(decimals, bool):
        return None
    try:
        parsed_decimals = int(decimals)
    except (TypeError, ValueError):
        return None
    if parsed_decimals < 0:
        return None

    raw = _text(raw_amount)
    if raw is None or not raw.isdigit():
        return None

    digits = raw.lstrip("0") or "0"
    if parsed_decimals == 0:
        return digits

    digits = digits.rjust(parsed_decimals + 1, "0")
    whole = digits[:-parsed_decimals] or "0"
    fraction = digits[-parsed_decimals:].rstrip("0")
    return whole if not fraction else f"{whole}.{fraction}"


def _raw_provider_candidates(value: Any, *, prefix: str = "", depth: int = 0) -> dict[str, Any]:
    """Return bounded reserve/liquidity-looking provider fields without semantics."""

    if depth > 4:
        return {}

    found: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            lowered = key.casefold()
            candidate = (
                lowered in _RAW_CANDIDATE_KEYS
                or "reserve" in lowered
                or lowered.startswith("pooled")
            )
            if candidate and (
                child is None or isinstance(child, (str, int, float, bool))
            ):
                found[path] = child
            found.update(
                _raw_provider_candidates(
                    child,
                    prefix=path,
                    depth=depth + 1,
                )
            )
    elif isinstance(value, list):
        for index, child in enumerate(value[:10]):
            found.update(
                _raw_provider_candidates(
                    child,
                    prefix=f"{prefix}[{index}]",
                    depth=depth + 1,
                )
            )
    return found


def _fetch_vault_record(
    *,
    slot_index: int,
    vault: str,
    expected_mint: str,
    token_account_fetcher: Callable[..., Mapping[str, Any]],
    rpc_url: str | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if rpc_url is not None:
        kwargs["rpc_url"] = rpc_url

    try:
        raw = token_account_fetcher(vault, **kwargs)
        info = dict(raw) if isinstance(raw, Mapping) else {}
    except Exception as exc:
        return {
            "slot_index": slot_index,
            "vault": vault,
            "expected_mint": expected_mint,
            "verified": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    observed_mint = _text(info.get("mint"))
    raw_amount = _text(info.get("raw_amount"))
    decimals = info.get("decimals")
    scaled_amount = _exact_scaled_amount(raw_amount, decimals)

    verified = bool(
        info.get("account_exists") is True
        and info.get("identity_verified") is True
        and observed_mint == expected_mint
        and raw_amount is not None
        and scaled_amount is not None
        and isinstance(decimals, int)
        and not isinstance(decimals, bool)
        and decimals >= 0
    )

    return {
        "slot_index": slot_index,
        "vault": vault,
        "expected_mint": expected_mint,
        "observed_mint": observed_mint,
        "mint_matches_expected": observed_mint == expected_mint,
        "raw_amount": raw_amount,
        "decimals": decimals if isinstance(decimals, int) and not isinstance(decimals, bool) else None,
        "scaled_amount": scaled_amount,
        "rpc_ui_amount_string_raw": _text(info.get("ui_amount_string")),
        "token_authority": _text(info.get("token_authority")),
        "program_owner": _text(info.get("program_owner")),
        "identity_verified": info.get("identity_verified") is True,
        "verified": verified,
    }


def verify_rpc_vault_reserve_units(
    *,
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
    min_verified_pools: int = 3,
    max_samples: int = 5,
    structural_verifier: Callable[..., Mapping[str, Any]] = verify_candidate_pool_role,
    token_account_fetcher: Callable[..., Mapping[str, Any]] = get_token_account_info,
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    rpc_url: str | None = None,
    signature_limit: int = 1,
) -> dict[str, Any]:
    """Verify exact RPC vault balances/decimals for a current XDEX pool sample."""

    if isinstance(min_verified_pools, bool) or not isinstance(min_verified_pools, int):
        raise ValueError("min_verified_pools must be an integer")
    if min_verified_pools < 3:
        raise ValueError("min_verified_pools must be at least 3")
    if isinstance(max_samples, bool) or not isinstance(max_samples, int):
        raise ValueError("max_samples must be an integer")
    if max_samples < min_verified_pools:
        raise ValueError("max_samples must be >= min_verified_pools")

    common = _common_rows(ninja_pools, xdex_pools)
    selected = common[:max_samples]
    samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for ninja_row, xdex_row in selected:
        address = _pool_address(xdex_row)
        positions = _xdex_token_positions(xdex_row)
        if not address or positions is None:
            continue
        token1, token2 = positions

        structural: Mapping[str, Any] | None = None
        program_id: str | None = None
        for raw_program in recognized_program_ids:
            candidate_program = _text(raw_program)
            if not candidate_program:
                continue
            kwargs: dict[str, Any] = {
                "account": address,
                "target_mint": token1,
                "program_id": candidate_program,
                "signature_limit": signature_limit,
            }
            if rpc_url is not None:
                kwargs["rpc_url"] = rpc_url
            try:
                report = structural_verifier(**kwargs)
            except Exception as exc:
                errors.append(
                    {
                        "pool_address": address,
                        "stage": "structural_verification",
                        "program_id": candidate_program,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            if (
                isinstance(report, Mapping)
                and report.get("summary", {}).get(
                    "pool_state_structural_role_verified"
                )
                is True
            ):
                structural = report
                program_id = candidate_program
                break

        if structural is None:
            samples.append(
                {
                    "pool_address": address,
                    "verified": False,
                    "rejection_reasons": ["pool_structural_role_unverified"],
                }
            )
            continue

        decoded = structural.get("decoded_state")
        decoded = decoded if isinstance(decoded, Mapping) else {}
        mint_0 = _text(decoded.get("mint_0"))
        mint_1 = _text(decoded.get("mint_1"))
        vault_0 = _text(decoded.get("vault_0"))
        vault_1 = _text(decoded.get("vault_1"))

        reasons: list[str] = []
        if token1 != mint_0 or token2 != mint_1:
            reasons.append("xdex_token_position_to_rpc_mint_mapping_mismatch")
        if not mint_0 or not mint_1:
            reasons.append("rpc_mint_slots_missing")
        if not vault_0 or not vault_1:
            reasons.append("rpc_vault_slots_missing")

        vault_records: list[dict[str, Any]] = []
        if not reasons:
            vault_records = [
                _fetch_vault_record(
                    slot_index=0,
                    vault=vault_0,
                    expected_mint=mint_0,
                    token_account_fetcher=token_account_fetcher,
                    rpc_url=rpc_url,
                ),
                _fetch_vault_record(
                    slot_index=1,
                    vault=vault_1,
                    expected_mint=mint_1,
                    token_account_fetcher=token_account_fetcher,
                    rpc_url=rpc_url,
                ),
            ]
            for record in vault_records:
                if record.get("verified") is not True:
                    reasons.append(
                        f"vault_{record.get('slot_index')}_balance_or_unit_unverified"
                    )

        verified = not reasons and len(vault_records) == 2

        samples.append(
            {
                "pool_address": address,
                "program_id": program_id,
                "token1": token1,
                "token2": token2,
                "mint_0": mint_0,
                "mint_1": mint_1,
                "vault_0": vault_0,
                "vault_1": vault_1,
                "position_mapping_verified": token1 == mint_0 and token2 == mint_1,
                "vaults": vault_records,
                "provider_raw_candidates": {
                    "x1_ninja": _raw_provider_candidates(ninja_row),
                    "xdex": _raw_provider_candidates(xdex_row),
                },
                "provider_candidate_semantics_verified": False,
                "verified": verified,
                "rejection_reasons": list(dict.fromkeys(reasons)),
            }
        )

    verified_samples = [row for row in samples if row.get("verified") is True]
    all_selected_verified = bool(samples) and all(
        row.get("verified") is True for row in samples
    )
    reserve_units_verified = bool(
        len(verified_samples) >= min_verified_pools
        and all_selected_verified
    )

    if reserve_units_verified:
        status = "verified"
    elif samples:
        status = "partial"
    else:
        status = "unavailable"

    return {
        "service": "x1_rpc_vault_reserve_units",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "common_pool_count_observed": len(common),
        "selected_sample_count": len(samples),
        "verified_sample_count": len(verified_samples),
        "minimum_verified_pool_count": min_verified_pools,
        "all_selected_samples_verified": all_selected_verified,
        "position_mapping_verified": reserve_units_verified,
        "rpc_vault_balance_fields_verified": reserve_units_verified,
        "rpc_vault_decimals_verified": reserve_units_verified,
        "rpc_reserve_unit_scaling_verified": reserve_units_verified,
        "rpc_vault_reserve_amounts_verified": reserve_units_verified,
        "base_quote_semantics_verified": False,
        "provider_candidate_semantics_verified": False,
        "samples": samples,
        "errors": errors,
        "semantics": {
            "provider_reserve_amount_semantics_verified": False,
            "liquidity_semantics_verified": False,
            "usd_valuation_verified": False,
            "price_semantics_verified": False,
            "volume_semantics_verified": False,
            "market_cap_semantics_verified": False,
            "freshness_verified": False,
            "source_independence_verified": False,
        },
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = ["VERSION", "verify_rpc_vault_reserve_units"]
