"""Exact current XDEX representation-pool universe evidence for CMIS #410.

The XDEX public pool-list response defines the provider-scoped candidate universe.
Each candidate containing the exact representation mint is promoted only after
the existing X1 RPC structural verifier proves the account is a pool state with
that exact mint.

This module does not interpret liquidity, volume, price, adoption, or execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.services.cmis_bridge_to_xdex_utilization import (
    POOL_UNIVERSE_CONTRACT,
)

SERVICE = "xdex_representation_pool_universe"
VERSION = "1.0"
SOURCE = "XDEX public API"
DEFAULT_NETWORK = "mainnet"


class XDEXRepresentationPoolUniverseError(ValueError):
    """Raised when exact XDEX representation-pool identity cannot be closed."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _epoch(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise XDEXRepresentationPoolUniverseError(
            f"{field} must be epoch seconds"
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise XDEXRepresentationPoolUniverseError(
            f"{field} must be epoch seconds"
        ) from exc
    if parsed <= 0:
        raise XDEXRepresentationPoolUniverseError(f"{field} must be positive")
    return parsed


def _pool_address(pool: Mapping[str, Any]) -> str | None:
    return _text(
        pool.get("address")
        or pool.get("poolAddress")
        or pool.get("pool_address")
        or pool.get("id")
    )


def _candidate_fields(token: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(token, Mapping):
        return set()
    values: set[str] = set()
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
            values.add(value)
    return values


def _pool_sides(pool: Mapping[str, Any]) -> dict[str, set[str]]:
    base = pool.get("baseToken")
    quote = pool.get("quoteToken")
    if isinstance(base, Mapping) and isinstance(quote, Mapping):
        return {
            "base": _candidate_fields(base),
            "quote": _candidate_fields(quote),
        }

    token1: set[str] = set()
    token2: set[str] = set()
    for key in ("token1_mint", "token1Mint", "token1_address", "token1Address"):
        value = _text(pool.get(key))
        if value:
            token1.add(value)
    for key in ("token2_mint", "token2Mint", "token2_address", "token2Address"):
        value = _text(pool.get(key))
        if value:
            token2.add(value)
    if token1 or token2:
        return {"token1": token1, "token2": token2}
    return {}


def select_representation_pool_candidates(
    xdex_pools: Any,
    *,
    representation_mint: str,
) -> dict[str, Any]:
    """Select exact-mint candidates from one already-fetched XDEX pool list."""

    representation = _text(representation_mint)
    if not representation:
        raise XDEXRepresentationPoolUniverseError(
            "representation_mint is required"
        )
    if not isinstance(xdex_pools, Sequence) or isinstance(
        xdex_pools, (str, bytes, bytearray)
    ):
        raise XDEXRepresentationPoolUniverseError(
            "xdex_pools must be a sequence"
        )

    candidates: list[str] = []
    unresolved: list[dict[str, Any]] = []
    seen_addresses: set[str] = set()

    for index, raw in enumerate(xdex_pools):
        if not isinstance(raw, Mapping):
            unresolved.append(
                {
                    "index": index,
                    "pool_address": None,
                    "reason": "non_mapping_pool_row",
                }
            )
            continue

        sides = _pool_sides(raw)
        matching_sides = sorted(
            side for side, values in sides.items() if representation in values
        )
        if not matching_sides:
            continue

        address = _pool_address(raw)
        if not address:
            unresolved.append(
                {
                    "index": index,
                    "pool_address": None,
                    "reason": "representation_pool_missing_address",
                }
            )
            continue
        if address in seen_addresses:
            unresolved.append(
                {
                    "index": index,
                    "pool_address": address,
                    "reason": "duplicate_representation_pool_address",
                }
            )
            continue
        seen_addresses.add(address)

        if len(matching_sides) != 1:
            unresolved.append(
                {
                    "index": index,
                    "pool_address": address,
                    "reason": "representation_mint_matches_multiple_pool_sides",
                }
            )
            continue
        candidates.append(address)

    return {
        "representation_mint": representation,
        "candidate_pool_addresses": sorted(candidates),
        "selection_unresolved": unresolved,
    }


def _structural_verified(
    report: Any,
    *,
    pool_address: str,
    representation_mint: str,
) -> tuple[bool, str | None]:
    if not isinstance(report, Mapping):
        return False, "missing_structural_pool_report"
    if report.get("service") != "candidate_pool_role_verification":
        return False, "wrong_structural_report_service"
    if _text(report.get("account")) != pool_address:
        return False, "structural_report_pool_address_mismatch"
    if _text(report.get("target_mint")) != representation_mint:
        return False, "structural_report_target_mint_mismatch"

    summary = report.get("summary")
    decoded = report.get("decoded_state")
    if not isinstance(summary, Mapping) or not isinstance(decoded, Mapping):
        return False, "structural_report_missing_summary"
    if summary.get("pool_state_structural_role_verified") is not True:
        return False, "pool_state_structural_role_unverified"
    if summary.get("pool_role_promoted") is not True:
        return False, "pool_role_not_promoted"
    if decoded.get("target_mint_present") is not True:
        return False, "target_mint_not_present_in_verified_pool_state"
    return True, None


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def build_xdex_representation_pool_universe(
    *,
    representation_mint: str,
    xdex_pools: Any,
    structural_reports_by_address: Any,
    observed_at: Any,
    network: str = DEFAULT_NETWORK,
) -> dict[str, Any]:
    """Close the current provider-scoped XDEX pool universe for one exact mint."""

    network_name = _text(network)
    if not network_name:
        raise XDEXRepresentationPoolUniverseError("network is required")
    observed = _epoch(observed_at, "observed_at")
    selection = select_representation_pool_candidates(
        xdex_pools,
        representation_mint=representation_mint,
    )
    representation = selection["representation_mint"]

    if not isinstance(structural_reports_by_address, Mapping):
        raise XDEXRepresentationPoolUniverseError(
            "structural_reports_by_address must be a mapping"
        )

    unresolved = list(selection["selection_unresolved"])
    verified_addresses: list[str] = []
    structural_evidence: list[dict[str, Any]] = []

    for address in selection["candidate_pool_addresses"]:
        report = structural_reports_by_address.get(address)
        verified, reason = _structural_verified(
            report,
            pool_address=address,
            representation_mint=representation,
        )
        if not verified:
            unresolved.append(
                {
                    "pool_address": address,
                    "reason": reason,
                }
            )
            continue
        verified_addresses.append(address)
        summary = report["summary"]
        structural_evidence.append(
            {
                "pool_address": address,
                "program_id": _text(report.get("program_id")),
                "account_space": report.get("account_space"),
                "target_mint_present": True,
                "pool_state_structural_role_verified": True,
                "pool_role_promoted": True,
                "state_integrity_verified": (
                    summary.get("state_integrity_verified") is True
                ),
                "program_owner_verified": (
                    summary.get("program_owner_verified") is True
                ),
                "both_vaults_verified": (
                    summary.get("both_vaults_verified") is True
                ),
                "shared_vault_authority_verified": (
                    summary.get("shared_vault_authority_verified") is True
                ),
            }
        )

    verified_addresses.sort()
    structural_evidence.sort(key=lambda row: row["pool_address"])
    unresolved.sort(
        key=lambda row: (
            str(row.get("pool_address") or ""),
            str(row.get("reason") or ""),
            int(row.get("index") or 0),
        )
    )

    candidate_count = len(selection["candidate_pool_addresses"])
    all_identities_verified = bool(
        not unresolved and len(verified_addresses) == candidate_count
    )
    enumeration_verified = all_identities_verified

    core = {
        "service": SERVICE,
        "version": VERSION,
        "contract": POOL_UNIVERSE_CONTRACT,
        "source": SOURCE,
        "network": network_name,
        "chain": "x1",
        "representation_mint": representation,
        "observed_at": observed,
        "provider_pool_row_count": (
            len(xdex_pools)
            if isinstance(xdex_pools, Sequence)
            and not isinstance(xdex_pools, (str, bytes, bytearray))
            else None
        ),
        "representation_candidate_pool_count": candidate_count,
        "pool_addresses": verified_addresses,
        "verified_pool_count": len(verified_addresses),
        "structural_evidence": structural_evidence,
        "unresolved_pools": unresolved,
        "enumeration_verified": enumeration_verified,
        "all_pool_identities_verified": all_identities_verified,
        "provider_catalog_scope_complete": enumeration_verified,
        "recognized_program_registry_globally_exhaustive": False,
        "global_onchain_pool_discovery_proven": False,
        "liquidity_semantics_verified": False,
        "volume_24h_semantics_verified": False,
        "market_freshness_verified": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }
    return {
        **core,
        "evidence_sha256": _canonical_sha256(core),
    }


def build_xdex_representation_pool_universe_from_program_set(
    *,
    program_pool_set: Any,
    observed_at: Any,
) -> dict[str, Any]:
    """Normalize one verified XDEX program-family pool set for #410.

    An empty set is accepted only when the upstream verifier explicitly records
    verified_zero_set=true. This distinguishes proved absence inside the exact
    verified XDEX program/account family from an unavailable or incomplete
    discovery result.
    """

    if not isinstance(program_pool_set, Mapping):
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set must be a mapping"
        )
    if program_pool_set.get("service") != "verified_program_asset_pool_set":
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set service is not accepted"
        )
    if program_pool_set.get("status") != (
        "recognized_program_asset_pool_set_structurally_verified"
    ):
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set is not structurally verified"
        )

    summary = program_pool_set.get("summary")
    if not isinstance(summary, Mapping):
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set summary is required"
        )
    if summary.get(
        "recognized_program_asset_pool_set_structurally_verified"
    ) is not True:
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set verification flag is false"
        )
    if summary.get("targeted_program_family_mint_filter_observed") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "mint-filtered program-family enumeration is unverified"
        )
    if summary.get("all_matching_accounts_structurally_verified") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "matching program accounts are not structurally closed"
        )

    representation = _text(program_pool_set.get("asset_mint"))
    program_id = _text(program_pool_set.get("program_id"))
    if not representation or not program_id:
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set identity is incomplete"
        )
    observed = _epoch(observed_at, "observed_at")

    rows = program_pool_set.get("pools")
    if not isinstance(rows, list):
        raise XDEXRepresentationPoolUniverseError(
            "program_pool_set pools must be a list"
        )

    addresses: list[str] = []
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise XDEXRepresentationPoolUniverseError(
                f"program_pool_set.pools[{index}] must be a mapping"
            )
        address = _text(row.get("pool_address"))
        if not address:
            raise XDEXRepresentationPoolUniverseError(
                f"program_pool_set.pools[{index}] address is missing"
            )
        if address in seen:
            raise XDEXRepresentationPoolUniverseError(
                f"duplicate verified program pool {address}"
            )
        seen.add(address)
        if row.get("pool_state_structural_role_verified") is not True:
            raise XDEXRepresentationPoolUniverseError(
                f"program pool {address} structural role is unverified"
            )
        mint_0 = _text(row.get("mint_0"))
        mint_1 = _text(row.get("mint_1"))
        if representation not in {mint_0, mint_1}:
            raise XDEXRepresentationPoolUniverseError(
                f"program pool {address} does not contain representation mint"
            )
        addresses.append(address)
        evidence.append(
            {
                "pool_address": address,
                "program_id": program_id,
                "mint_0": mint_0,
                "mint_1": mint_1,
                "catalog_listed": row.get("catalog_listed") is True,
                "pool_state_structural_role_verified": True,
            }
        )

    zero_set = not addresses
    if zero_set and summary.get("verified_zero_set") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "empty program pool set lacks explicit verified-zero evidence"
        )

    addresses.sort()
    evidence.sort(key=lambda row: row["pool_address"])
    core = {
        "service": SERVICE,
        "version": VERSION,
        "contract": POOL_UNIVERSE_CONTRACT,
        "source": "X1 RPC verified XDEX program-family pool set",
        "network": "X1 Mainnet",
        "chain": "x1",
        "scope": "verified_xdex_program_family",
        "program_id": program_id,
        "representation_mint": representation,
        "observed_at": observed,
        "representation_candidate_pool_count": len(addresses),
        "pool_addresses": addresses,
        "verified_pool_count": len(addresses),
        "structural_evidence": evidence,
        "unresolved_pools": [],
        "enumeration_verified": True,
        "all_pool_identities_verified": True,
        "verified_zero_set": zero_set,
        "zero_set_scope": (
            "verified_xdex_program_family" if zero_set else None
        ),
        "provider_catalog_scope_complete": (
            summary.get("all_catalog_asset_pools_recovered") is True
        ),
        "recognized_program_registry_globally_exhaustive": False,
        "global_onchain_pool_discovery_proven": False,
        "liquidity_semantics_verified": zero_set,
        "current_liquidity_zero_verified": zero_set,
        "volume_24h_semantics_verified": False,
        "volume_24h_window_coverage_verified": False,
        "market_freshness_verified": zero_set,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }
    return {
        **core,
        "evidence_sha256": _canonical_sha256(core),
    }


def apply_verified_program_window_to_zero_universe(
    *,
    pool_universe: Any,
    program_window_activity: Any,
) -> dict[str, Any]:
    """Bind a complete zero-activity window to an already verified zero pool set.

    This helper is deliberately zero-set-only. Non-empty pool universes still
    require verified per-pool market metrics and are never collapsed through a
    program-wide absence shortcut.
    """

    if not isinstance(pool_universe, Mapping):
        raise XDEXRepresentationPoolUniverseError(
            "pool_universe must be a mapping"
        )
    if pool_universe.get("contract") != POOL_UNIVERSE_CONTRACT:
        raise XDEXRepresentationPoolUniverseError(
            "pool_universe contract is not accepted"
        )
    if pool_universe.get("scope") != "verified_xdex_program_family":
        raise XDEXRepresentationPoolUniverseError(
            "pool_universe must use verified XDEX program-family scope"
        )
    if pool_universe.get("enumeration_verified") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "pool_universe enumeration is unverified"
        )
    if pool_universe.get("all_pool_identities_verified") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "pool_universe identities are unverified"
        )
    if pool_universe.get("verified_zero_set") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "program-window zero binding requires verified_zero_set"
        )
    if pool_universe.get("current_liquidity_zero_verified") is not True:
        raise XDEXRepresentationPoolUniverseError(
            "current zero liquidity is unverified"
        )
    if pool_universe.get("pool_addresses") != []:
        raise XDEXRepresentationPoolUniverseError(
            "verified zero universe must have no pool addresses"
        )
    if pool_universe.get("unresolved_pools") != []:
        raise XDEXRepresentationPoolUniverseError(
            "verified zero universe cannot contain unresolved pools"
        )
    if pool_universe.get("execution_authorized") is not False:
        raise XDEXRepresentationPoolUniverseError(
            "pool_universe must remain read-only"
        )

    if not isinstance(program_window_activity, Mapping):
        raise XDEXRepresentationPoolUniverseError(
            "program_window_activity must be a mapping"
        )
    if program_window_activity.get("contract") != (
        "xdex_program_asset_window_activity/v1"
    ):
        raise XDEXRepresentationPoolUniverseError(
            "program_window_activity contract is not accepted"
        )
    if program_window_activity.get("program_id") != pool_universe.get("program_id"):
        raise XDEXRepresentationPoolUniverseError(
            "program-window program id does not match pool universe"
        )
    if program_window_activity.get("asset_mint") != (
        pool_universe.get("representation_mint")
    ):
        raise XDEXRepresentationPoolUniverseError(
            "program-window asset mint does not match representation mint"
        )
    requested = program_window_activity.get("requested_window")
    if not isinstance(requested, Mapping):
        raise XDEXRepresentationPoolUniverseError(
            "program-window requested_window is required"
        )
    duration = requested.get("duration_seconds")
    if isinstance(duration, bool):
        raise XDEXRepresentationPoolUniverseError(
            "program-window duration must be 24 hours"
        )
    try:
        duration_value = float(duration)
    except (TypeError, ValueError) as exc:
        raise XDEXRepresentationPoolUniverseError(
            "program-window duration must be 24 hours"
        ) from exc
    if abs(duration_value - 86400.0) > 1e-6:
        raise XDEXRepresentationPoolUniverseError(
            "program-window duration must be exactly 24 hours"
        )

    for field in (
        "program_signature_range_proven",
        "program_signature_integrity_verified",
        "all_successful_transactions_verified",
        "window_trace_complete_verified",
        "program_scoped_asset_activity_zero_verified",
        "volume_24h_window_coverage_verified",
        "volume_24h_semantics_verified",
    ):
        if program_window_activity.get(field) is not True:
            raise XDEXRepresentationPoolUniverseError(
                f"program_window_activity.{field} must be true"
            )
    if program_window_activity.get("verified_volume_24h_value") != "0":
        raise XDEXRepresentationPoolUniverseError(
            "verified program-window volume must be exact zero"
        )
    if program_window_activity.get("verified_volume_24h_unit") != "USD":
        raise XDEXRepresentationPoolUniverseError(
            "verified program-window volume unit must be USD"
        )
    if program_window_activity.get("target_mint_activity_transaction_count") != 0:
        raise XDEXRepresentationPoolUniverseError(
            "target-mint activity prevents zero-volume binding"
        )
    if program_window_activity.get("target_mint_delta_count") != 0:
        raise XDEXRepresentationPoolUniverseError(
            "target-mint deltas prevent zero-volume binding"
        )
    if program_window_activity.get("execution_authorized") is not False:
        raise XDEXRepresentationPoolUniverseError(
            "program-window evidence must remain read-only"
        )

    core = dict(pool_universe)
    core.pop("evidence_sha256", None)
    core.update(
        {
            "volume_24h_semantics_verified": True,
            "volume_24h_window_coverage_verified": True,
            "verified_volume_24h_value": "0",
            "verified_volume_24h_unit": "USD",
            "volume_24h_zero_authorization_basis": (
                program_window_activity.get("zero_authorization_basis")
            ),
            "volume_24h_window": dict(requested),
            "program_window_activity_contract": program_window_activity.get(
                "contract"
            ),
            "program_window_activity_signature_count": (
                program_window_activity.get("window_signature_count")
            ),
            "market_freshness_verified": True,
            "cmis_promotable": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }
    )
    return {
        **core,
        "evidence_sha256": _canonical_sha256(core),
    }


__all__ = [
    "DEFAULT_NETWORK",
    "SERVICE",
    "SOURCE",
    "VERSION",
    "XDEXRepresentationPoolUniverseError",
    "build_xdex_representation_pool_universe",
    "apply_verified_program_window_to_zero_universe",
    "build_xdex_representation_pool_universe_from_program_set",
    "select_representation_pool_candidates",
]
