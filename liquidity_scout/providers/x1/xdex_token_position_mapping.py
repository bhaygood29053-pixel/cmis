"""Verify XDEX token1/token2 positions against accepted RPC mint slots.

This module proves only positional mapping within the accepted XDEX pool-state
family. It does not assign base/quote semantics to token1/token2 or mint_0/mint_1
and does not promote reserve, price, liquidity, volume, market-cap, freshness,
or execution semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import verify_candidate_pool_role
from liquidity_scout.providers.x1.program_accounts import RECOGNIZED_AMM_PROGRAM_IDS


VERSION = "1.0"


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


def _common_xdex_rows(
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    ninja_addresses = {
        _pool_address(row)
        for row in ninja_pools
        if isinstance(row, Mapping) and _pool_address(row)
    }

    rows: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in xdex_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if not address or address in seen or address not in ninja_addresses:
            continue
        if _xdex_token_positions(row) is None:
            continue
        seen.add(address)
        rows.append(row)
    return rows


def verify_xdex_token_position_mapping(
    *,
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
    min_verified_pools: int = 3,
    max_samples: int = 8,
    structural_verifier: Callable[..., Mapping[str, Any]] = verify_candidate_pool_role,
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    rpc_url: str | None = None,
    signature_limit: int = 1,
) -> dict[str, Any]:
    """Verify a stable token1/token2 -> mint-slot mapping across live pools."""

    if isinstance(min_verified_pools, bool) or not isinstance(min_verified_pools, int):
        raise ValueError("min_verified_pools must be an integer")
    if min_verified_pools < 3:
        raise ValueError("min_verified_pools must be at least 3")
    if isinstance(max_samples, bool) or not isinstance(max_samples, int):
        raise ValueError("max_samples must be an integer")
    if max_samples < min_verified_pools:
        raise ValueError("max_samples must be >= min_verified_pools")

    common_rows = _common_xdex_rows(ninja_pools, xdex_pools)
    samples: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for row in common_rows:
        if len(samples) >= max_samples:
            break

        address = _pool_address(row)
        positions = _xdex_token_positions(row)
        if not address or positions is None:
            continue
        token1, token2 = positions

        verified_report: Mapping[str, Any] | None = None
        verified_program: str | None = None

        for raw_program in recognized_program_ids:
            program_id = _text(raw_program)
            if not program_id:
                continue
            kwargs = {
                "account": address,
                "target_mint": token1,
                "program_id": program_id,
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
                        "program_id": program_id,
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
                verified_report = report
                verified_program = program_id
                break

        if verified_report is None:
            continue

        decoded = verified_report.get("decoded_state")
        decoded = decoded if isinstance(decoded, Mapping) else {}
        mint_0 = _text(decoded.get("mint_0"))
        mint_1 = _text(decoded.get("mint_1"))
        if not mint_0 or not mint_1 or mint_0 == mint_1:
            continue

        if token1 == mint_0 and token2 == mint_1:
            mapping = "token1_to_mint0__token2_to_mint1"
        elif token1 == mint_1 and token2 == mint_0:
            mapping = "token1_to_mint1__token2_to_mint0"
        else:
            mapping = "token_positions_do_not_match_rpc_mint_set"

        samples.append(
            {
                "pool_address": address,
                "program_id": verified_program,
                "token1": token1,
                "token2": token2,
                "mint_0": mint_0,
                "mint_1": mint_1,
                "mapping": mapping,
                "rpc_mint_identity_verified": True,
            }
        )

    usable = [
        row
        for row in samples
        if row["mapping"]
        in {
            "token1_to_mint0__token2_to_mint1",
            "token1_to_mint1__token2_to_mint0",
        }
    ]
    mappings = {row["mapping"] for row in usable}

    stable = bool(
        len(usable) >= min_verified_pools
        and len(mappings) == 1
        and len(usable) == len(samples)
    )
    stable_mapping = next(iter(mappings)) if stable else None

    if stable:
        status = "verified"
    elif samples:
        status = "partial"
    else:
        status = "unavailable"

    return {
        "service": "x1_xdex_token_position_mapping",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "common_pool_count_observed": len(common_rows),
        "sample_count": len(samples),
        "verified_sample_count": len(usable),
        "minimum_verified_pool_count": min_verified_pools,
        "stable_mapping": stable_mapping,
        "position_mapping_verified": stable,
        "base_quote_semantics_verified": False,
        "provider_base_quote_orientation_verified": False,
        "onchain_mint_slot_base_quote_semantics_verified": False,
        "samples": samples,
        "errors": errors,
        "semantics": {
            "reserve_amount_semantics_verified": False,
            "reserve_units_verified": False,
            "price_semantics_verified": False,
            "liquidity_semantics_verified": False,
            "volume_semantics_verified": False,
            "market_cap_semantics_verified": False,
            "freshness_verified": False,
        },
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = ["VERSION", "verify_xdex_token_position_mapping"]
