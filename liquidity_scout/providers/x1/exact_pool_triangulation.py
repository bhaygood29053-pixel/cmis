"""Exact X1 pool identity triangulation across X1.Ninja, XDEX and X1 RPC.

This module is intentionally identity-only. It binds one provider-visible pool
address to an independently verified XDEX program-state account and checks that
both provider token-side records can be mapped to the two exact RPC-decoded
pool mints.

It does not interpret or promote price, liquidity, volume, market-cap, holder,
reserve-amount, timestamp, freshness, or execution semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.program_accounts import (
    RECOGNIZED_AMM_PROGRAM_IDS,
)


VERSION = "1.0"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pool_address(pool: Mapping[str, Any]) -> str | None:
    return _text(
        pool.get("address")
        or pool.get("poolAddress")
        or pool.get("pool_address")
        or pool.get("id")
    )


def _candidate_fields(token: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(token, Mapping):
        return {}

    result: dict[str, str] = {}
    for key in (
        "mint",
        "address",
        "tokenAddress",
        "token_address",
        "mintAddress",
        "mint_address",
    ):
        value = _text(token.get(key))
        if value:
            result[key] = value
    return result


def _nested_roles(pool: Mapping[str, Any]) -> dict[str, dict[str, str]] | None:
    base = pool.get("baseToken")
    quote = pool.get("quoteToken")
    if not isinstance(base, Mapping) or not isinstance(quote, Mapping):
        return None
    return {
        "base": _candidate_fields(base),
        "quote": _candidate_fields(quote),
    }


def _flat_xdex_roles(pool: Mapping[str, Any]) -> dict[str, dict[str, str]] | None:
    token1: dict[str, str] = {}
    token2: dict[str, str] = {}

    for key in ("token1_mint", "token1Mint"):
        value = _text(pool.get(key))
        if value:
            token1[key] = value
    for key in ("token1_address", "token1Address"):
        value = _text(pool.get(key))
        if value:
            token1[key] = value

    for key in ("token2_mint", "token2Mint"):
        value = _text(pool.get(key))
        if value:
            token2[key] = value
    for key in ("token2_address", "token2Address"):
        value = _text(pool.get(key))
        if value:
            token2[key] = value

    if not token1 or not token2:
        return None

    # Flat XDEX token1/token2 are provider positions only, not promoted
    # base/quote semantics.
    return {"token1": token1, "token2": token2}


def _provider_roles(
    pool: Mapping[str, Any],
    *,
    provider: str,
) -> tuple[dict[str, dict[str, str]], str]:
    nested = _nested_roles(pool)
    if nested is not None:
        return nested, "declared_base_quote"

    if provider == "xdex":
        flat = _flat_xdex_roles(pool)
        if flat is not None:
            return flat, "provider_token1_token2"

    return {}, "unavailable"


def _side_values(side: Mapping[str, str]) -> set[str]:
    return {value for value in side.values() if _text(value)}


def _all_candidate_values(roles: Mapping[str, Mapping[str, str]]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for side in roles.values():
        for value in side.values():
            value = _text(value)
            if value and value not in seen:
                seen.add(value)
                values.append(value)
    return values


def _match_roles_to_rpc_mints(
    roles: Mapping[str, Mapping[str, str]],
    rpc_mints: Sequence[str],
) -> dict[str, Any]:
    expected = {_text(value) for value in rpc_mints if _text(value)}
    if len(expected) != 2 or len(roles) != 2:
        return {
            "token_set_matches_rpc": False,
            "role_to_rpc_mint": {},
            "rejection_reasons": ["incomplete_role_or_rpc_mint_set"],
        }

    mapping: dict[str, str] = {}
    reasons: list[str] = []
    for role, fields in roles.items():
        matches = _side_values(fields) & expected
        if len(matches) != 1:
            reasons.append(f"{role}_does_not_map_uniquely_to_rpc_mint")
            continue
        mapping[role] = next(iter(matches))

    if len(mapping) == 2 and len(set(mapping.values())) != 2:
        reasons.append("provider_roles_map_to_same_rpc_mint")

    matched = bool(
        not reasons
        and len(mapping) == 2
        and set(mapping.values()) == expected
    )
    return {
        "token_set_matches_rpc": matched,
        "role_to_rpc_mint": mapping,
        "rejection_reasons": reasons,
    }


def _common_pool_rows(
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
) -> list[tuple[str, Mapping[str, Any], Mapping[str, Any]]]:
    ninja_index: dict[str, Mapping[str, Any]] = {}
    for row in ninja_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if address and address not in ninja_index:
            ninja_index[address] = row

    matches: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    seen: set[str] = set()
    for row in xdex_pools:
        if not isinstance(row, Mapping):
            continue
        address = _pool_address(row)
        if not address or address in seen or address not in ninja_index:
            continue
        seen.add(address)
        matches.append((address, ninja_index[address], row))
    return matches


def triangulate_exact_pool_identity(
    *,
    ninja_pools: Sequence[Mapping[str, Any]],
    xdex_pools: Sequence[Mapping[str, Any]],
    structural_verifier: Callable[..., Mapping[str, Any]] = verify_candidate_pool_role,
    recognized_program_ids: Sequence[str] = RECOGNIZED_AMM_PROGRAM_IDS,
    rpc_url: str | None = None,
    signature_limit: int = 1,
) -> dict[str, Any]:
    """Prove one exact common provider pool against the accepted RPC layout.

    Candidate provider fields are never assumed to be canonical mints. Instead
    each candidate value is tried only as a scope input to the accepted X1 RPC
    structural verifier. A result is accepted only when the verifier itself
    proves the pool state, two exact mints, two vault token accounts and shared
    authority.
    """

    common = _common_pool_rows(ninja_pools, xdex_pools)
    attempts: list[dict[str, Any]] = []

    for pool_address, ninja_row, xdex_row in common:
        ninja_roles, ninja_role_basis = _provider_roles(
            ninja_row,
            provider="ninja",
        )
        xdex_roles, xdex_role_basis = _provider_roles(
            xdex_row,
            provider="xdex",
        )
        candidate_values = []
        seen_values: set[str] = set()
        for value in (
            _all_candidate_values(ninja_roles)
            + _all_candidate_values(xdex_roles)
        ):
            if value not in seen_values:
                seen_values.add(value)
                candidate_values.append(value)

        for program_id in recognized_program_ids:
            program_id = _text(program_id)
            if not program_id:
                continue
            for target_mint in candidate_values:
                kwargs = {
                    "account": pool_address,
                    "target_mint": target_mint,
                    "program_id": program_id,
                    "signature_limit": signature_limit,
                }
                if rpc_url is not None:
                    kwargs["rpc_url"] = rpc_url

                try:
                    raw = structural_verifier(**kwargs)
                    report = dict(raw) if isinstance(raw, Mapping) else {}
                except Exception as exc:
                    attempts.append(
                        {
                            "pool_address": pool_address,
                            "program_id": program_id,
                            "target_mint_candidate": target_mint,
                            "structural_role_verified": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    continue

                structural_ok = (
                    report.get("summary", {}).get(
                        "pool_state_structural_role_verified"
                    )
                    is True
                )
                decoded = report.get("decoded_state")
                decoded = decoded if isinstance(decoded, Mapping) else {}
                rpc_mints = [
                    _text(decoded.get("mint_0")),
                    _text(decoded.get("mint_1")),
                ]
                rpc_mints = [value for value in rpc_mints if value]

                attempts.append(
                    {
                        "pool_address": pool_address,
                        "program_id": program_id,
                        "target_mint_candidate": target_mint,
                        "structural_role_verified": structural_ok,
                        "rpc_mints": rpc_mints,
                    }
                )

                if not structural_ok or len(set(rpc_mints)) != 2:
                    continue

                ninja_match = _match_roles_to_rpc_mints(
                    ninja_roles,
                    rpc_mints,
                )
                xdex_match = _match_roles_to_rpc_mints(
                    xdex_roles,
                    rpc_mints,
                )

                provider_role_orientation_agreement = False
                base_quote_orientation_verified = False
                if (
                    ninja_role_basis == "declared_base_quote"
                    and xdex_role_basis == "declared_base_quote"
                    and ninja_match["token_set_matches_rpc"]
                    and xdex_match["token_set_matches_rpc"]
                ):
                    ninja_map = ninja_match["role_to_rpc_mint"]
                    xdex_map = xdex_match["role_to_rpc_mint"]
                    provider_role_orientation_agreement = (
                        ninja_map.get("base") == xdex_map.get("base")
                        and ninja_map.get("quote") == xdex_map.get("quote")
                    )
                    # This verifies cross-provider declared base/quote roles
                    # are bound to the same exact RPC mints. It does not claim
                    # the binary mint_0/mint_1 slots themselves encode
                    # base/quote semantics.
                    base_quote_orientation_verified = (
                        provider_role_orientation_agreement
                    )

                pool_identity_verified = (
                    _text(report.get("account")) == pool_address
                    and structural_ok
                )
                rpc_mint_identity_verified = bool(
                    structural_ok
                    and report.get("summary", {}).get(
                        "both_vaults_verified"
                    )
                    is True
                )
                token_set_identity_verified = bool(
                    ninja_match["token_set_matches_rpc"]
                    and xdex_match["token_set_matches_rpc"]
                    and rpc_mint_identity_verified
                )

                verified = bool(
                    pool_identity_verified
                    and token_set_identity_verified
                    and base_quote_orientation_verified
                    and rpc_mint_identity_verified
                )

                return {
                    "service": "x1_exact_pool_identity_triangulation",
                    "version": VERSION,
                    "chain": "x1",
                    "status": "verified" if verified else "partial",
                    "pool_address": pool_address,
                    "program_id": program_id,
                    "rpc_mints": rpc_mints,
                    "rpc_vaults": [
                        _text(decoded.get("vault_0")),
                        _text(decoded.get("vault_1")),
                    ],
                    "provider_identity": {
                        "x1_ninja": {
                            "role_basis": ninja_role_basis,
                            "roles": ninja_roles,
                            "rpc_binding": ninja_match,
                        },
                        "xdex": {
                            "role_basis": xdex_role_basis,
                            "roles": xdex_roles,
                            "rpc_binding": xdex_match,
                        },
                    },
                    "identity": {
                        "pool_identity_verified": pool_identity_verified,
                        "token_set_identity_verified": token_set_identity_verified,
                        "provider_role_orientation_agreement": (
                            provider_role_orientation_agreement
                        ),
                        "base_quote_orientation_verified": (
                            base_quote_orientation_verified
                        ),
                        "onchain_mint_slot_base_quote_semantics_verified": False,
                        "rpc_mint_identity_verified": rpc_mint_identity_verified,
                    },
                    "semantics": {
                        "reserve_amount_semantics_verified": False,
                        "price_semantics_verified": False,
                        "liquidity_semantics_verified": False,
                        "volume_semantics_verified": False,
                        "market_cap_semantics_verified": False,
                        "freshness_verified": False,
                    },
                    "cmis_promotable": False,
                    "execution_authorized": False,
                    "common_pool_count_observed": len(common),
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                }

    return {
        "service": "x1_exact_pool_identity_triangulation",
        "version": VERSION,
        "chain": "x1",
        "status": "unavailable",
        "pool_address": None,
        "program_id": None,
        "rpc_mints": [],
        "rpc_vaults": [],
        "provider_identity": {},
        "identity": {
            "pool_identity_verified": False,
            "token_set_identity_verified": False,
            "provider_role_orientation_agreement": False,
            "base_quote_orientation_verified": False,
            "onchain_mint_slot_base_quote_semantics_verified": False,
            "rpc_mint_identity_verified": False,
        },
        "semantics": {
            "reserve_amount_semantics_verified": False,
            "price_semantics_verified": False,
            "liquidity_semantics_verified": False,
            "volume_semantics_verified": False,
            "market_cap_semantics_verified": False,
            "freshness_verified": False,
        },
        "cmis_promotable": False,
        "execution_authorized": False,
        "common_pool_count_observed": len(common),
        "attempt_count": len(attempts),
        "attempts": attempts,
    }


__all__ = [
    "VERSION",
    "triangulate_exact_pool_identity",
]
