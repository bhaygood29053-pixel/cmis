"""Warp message-counter closure evidence for #409 / #437.

This contract cross-checks three independently acquired views:
1. the provenance-approved official Warp config JSON;
2. exact on-chain Config account bytes;
3. the fully verified current OutgoingMsg/IncomingMsg account universes.

Exact counter equality is necessary evidence for historical completeness, but it
is not sufficient by itself.  This slice therefore keeps retention/window
coverage false until deletion/recycling semantics are independently accepted.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SOURCE_URL,
)
from liquidity_scout.providers.x1.warp_onchain_inventory import (
    SOLANA_RPC_URL,
    WARP_PROGRAM_ID,
    X1_RPC_URL,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as MESSAGE_STATE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_rare_account_capture import (
    CONTRACT as RARE_CAPTURE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_semantic_layout_discovery import (
    CONTRACT as LAYOUT_CONTRACT,
    classify_rare_account,
)

CONTRACT = "warp_message_retention_coverage/v1"
CONFIG_PDA = "48Po6qAHRJojbXH7KRqt6s5GfNfs9VEGccfqYEHmubEi"
REQUIRED_FLOW_LOOKBACK_SECONDS = 60 * 24 * 60 * 60


class WarpMessageRetentionCoverageError(RuntimeError):
    """Raised when counter-closure evidence cannot be established safely."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WarpMessageRetentionCoverageError(f"{field} must be a mapping")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise WarpMessageRetentionCoverageError(
            f"{field} must be a non-negative integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise WarpMessageRetentionCoverageError(
            f"{field} must be a non-negative integer"
        ) from None
    if parsed < 0:
        raise WarpMessageRetentionCoverageError(
            f"{field} must be a non-negative integer"
        )
    return parsed


def fetch_official_warp_config(
    *,
    timeout: int = 20,
    get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Fetch the already provenance-approved official Warp config endpoint."""

    try:
        response = get(
            WARP_CONFIG_SOURCE_URL,
            headers={
                "accept": "application/json",
                "user-agent": "CMIS-Warp-Counter-Closure/1.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "")
        payload = response.json()
    except Exception as exc:
        raise WarpMessageRetentionCoverageError(
            f"official config fetch failed ({type(exc).__name__})"
        ) from None
    if "json" not in content_type.casefold():
        raise WarpMessageRetentionCoverageError(
            "official config response is not JSON"
        )
    if not isinstance(payload, Mapping):
        raise WarpMessageRetentionCoverageError(
            "official config response is not an object"
        )
    return dict(payload)


def _rpc_get_account_info(
    *,
    rpc_url: str,
    timeout: int = 30,
    post: Callable[..., Any] = requests.post,
) -> Mapping[str, Any]:
    try:
        response = post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    CONFIG_PDA,
                    {
                        "encoding": "base64",
                        "commitment": "confirmed",
                    },
                ],
            },
            headers={
                "content-type": "application/json",
                "user-agent": "CMIS-Warp-Counter-Closure/1.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise WarpMessageRetentionCoverageError(
            f"getAccountInfo transport failed ({type(exc).__name__})"
        ) from None
    if not isinstance(body, Mapping) or body.get("error") is not None:
        raise WarpMessageRetentionCoverageError(
            "getAccountInfo returned an invalid JSON-RPC response"
        )
    result = body.get("result")
    if not isinstance(result, Mapping):
        raise WarpMessageRetentionCoverageError(
            "getAccountInfo result is missing"
        )
    value = result.get("value")
    if not isinstance(value, Mapping):
        raise WarpMessageRetentionCoverageError(
            "Warp Config account is missing"
        )
    return value


def fetch_classified_warp_config_account(
    *,
    chain: str,
    rpc_url: str | None = None,
    timeout: int = 30,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Fetch and classify the exact Warp Config PDA on one chain."""

    chain_value = str(chain or "").strip().casefold()
    if chain_value not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    resolved_rpc = rpc_url or (
        SOLANA_RPC_URL if chain_value == "solana" else X1_RPC_URL
    )
    account = _rpc_get_account_info(
        rpc_url=resolved_rpc,
        timeout=timeout,
        post=post,
    )
    if account.get("owner") != WARP_PROGRAM_ID:
        raise WarpMessageRetentionCoverageError(
            "Config account owner is not the exact Warp program"
        )
    if account.get("executable") is not False:
        raise WarpMessageRetentionCoverageError(
            "Config account must be non-executable"
        )
    data = account.get("data")
    if (
        not isinstance(data, list)
        or len(data) != 2
        or not isinstance(data[0], str)
        or data[1] != "base64"
    ):
        raise WarpMessageRetentionCoverageError(
            "Config account base64 data is missing"
        )
    try:
        raw = base64.b64decode(data[0], validate=True)
    except Exception:
        raise WarpMessageRetentionCoverageError(
            "Config account base64 is invalid"
        ) from None
    capture = {
        "contract": RARE_CAPTURE_CONTRACT,
        "chain": chain_value,
        "pubkey": CONFIG_PDA,
        "program_id": WARP_PROGRAM_ID,
        "owner_verified": True,
        "data_length_verified": len(raw) == 321,
        "non_executable_verified": True,
        "inventory_space": len(raw),
        "data_base64": data[0],
    }
    classified = classify_rare_account(capture)
    if classified.get("contract") != LAYOUT_CONTRACT:
        raise WarpMessageRetentionCoverageError(
            "Config classification contract mismatch"
        )
    if classified.get("account_name") != "Config":
        raise WarpMessageRetentionCoverageError(
            "exact Config PDA did not classify as Config"
        )
    return classified


def _official_counters(config_response: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    counters: dict[str, dict[str, int]] = {}
    for chain in ("solana", "x1"):
        chain_block = _mapping(config_response.get(chain), f"{chain}")
        config = _mapping(chain_block.get("config"), f"{chain}.config")
        if str(config.get("programId") or "").strip() != WARP_PROGRAM_ID:
            raise WarpMessageRetentionCoverageError(
                f"{chain}.config.programId is not exact Warp"
            )
        counters[chain] = {
            "out": _nonnegative_int(
                config.get("outSeqCounter"),
                f"{chain}.config.outSeqCounter",
            ),
            "in": _nonnegative_int(
                config.get("inSeqCounter"),
                f"{chain}.config.inSeqCounter",
            ),
        }
    return counters


def _onchain_config_counters(
    classified_configs: Mapping[str, Any],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for chain in ("solana", "x1"):
        item = _mapping(classified_configs.get(chain), f"classified_configs.{chain}")
        if item.get("contract") != LAYOUT_CONTRACT:
            raise WarpMessageRetentionCoverageError(
                f"{chain} Config layout contract mismatch"
            )
        if item.get("account_name") != "Config":
            raise WarpMessageRetentionCoverageError(
                f"{chain} classified account is not Config"
            )
        if item.get("account_type_identity_verified") is not True:
            raise WarpMessageRetentionCoverageError(
                f"{chain} Config type identity is not verified"
            )
        if item.get("pda_identity_verified") is not True:
            raise WarpMessageRetentionCoverageError(
                f"{chain} Config PDA identity is not verified"
            )
        fields = _mapping(item.get("decoded_fields"), f"{chain}.decoded_fields")
        result[chain] = {
            "out": _nonnegative_int(
                fields.get("out_seq_counter_candidate"),
                f"{chain}.out_seq_counter_candidate",
            ),
            "in": _nonnegative_int(
                fields.get("in_seq_counter_candidate"),
                f"{chain}.in_seq_counter_candidate",
            ),
        }
    return result


def _message_side(
    message_state: Mapping[str, Any],
    *,
    chain: str,
    side: str,
) -> tuple[list[Mapping[str, Any]], int, int | None, int | None]:
    chain_block = _mapping(message_state.get(chain), chain)
    block = _mapping(chain_block.get(side), f"{chain}.{side}")
    if block.get("account_type_identity_verified") is not True:
        raise WarpMessageRetentionCoverageError(
            f"{chain}.{side} account type identity is not verified"
        )
    if block.get("all_pda_identities_verified") is not True:
        raise WarpMessageRetentionCoverageError(
            f"{chain}.{side} PDA identities are not verified"
        )
    rows_raw = block.get("accounts")
    if not isinstance(rows_raw, list):
        raise WarpMessageRetentionCoverageError(
            f"{chain}.{side}.accounts must be a list"
        )
    rows: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    earliest: int | None = None
    latest: int | None = None
    for raw in rows_raw:
        row = _mapping(raw, f"{chain}.{side}.account")
        key_name = "seq" if side == "outgoing" else "source_seq"
        seq = _nonnegative_int(row.get(key_name), f"{chain}.{side}.{key_name}")
        if seq in seen:
            raise WarpMessageRetentionCoverageError(
                f"{chain}.{side} contains duplicate sequence {seq}"
            )
        seen.add(seq)
        ts_name = "timestamp" if side == "outgoing" else "source_timestamp"
        timestamp = _nonnegative_int(
            row.get(ts_name),
            f"{chain}.{side}.{ts_name}",
        )
        earliest = timestamp if earliest is None else min(earliest, timestamp)
        latest = timestamp if latest is None else max(latest, timestamp)
        rows.append(row)
    reported_count = _nonnegative_int(
        block.get("decoded_account_count", len(rows)),
        f"{chain}.{side}.decoded_account_count",
    )
    if reported_count != len(rows):
        raise WarpMessageRetentionCoverageError(
            f"{chain}.{side} reported count does not match rows"
        )
    return rows, len(seen), earliest, latest


def evaluate_warp_message_counter_closure(
    *,
    config_response: Any,
    classified_configs: Any,
    message_state: Any,
) -> dict[str, Any]:
    """Evaluate counter/account closure without over-promoting retention."""

    official = _official_counters(_mapping(config_response, "config_response"))
    onchain = _onchain_config_counters(
        _mapping(classified_configs, "classified_configs")
    )
    state = _mapping(message_state, "message_state")
    if state.get("contract") != MESSAGE_STATE_CONTRACT:
        raise WarpMessageRetentionCoverageError(
            f"message_state must use {MESSAGE_STATE_CONTRACT}"
        )

    per_chain: dict[str, Any] = {}
    all_official_onchain_match = True
    all_counter_count_match = True
    earliest_all: int | None = None
    latest_all: int | None = None

    for chain in ("solana", "x1"):
        outgoing, outgoing_unique, out_earliest, out_latest = _message_side(
            state,
            chain=chain,
            side="outgoing",
        )
        incoming, incoming_unique, in_earliest, in_latest = _message_side(
            state,
            chain=chain,
            side="incoming",
        )
        official_match = official[chain] == onchain[chain]
        out_count_match = official[chain]["out"] == len(outgoing)
        in_count_match = official[chain]["in"] == len(incoming)
        all_official_onchain_match = (
            all_official_onchain_match and official_match
        )
        all_counter_count_match = (
            all_counter_count_match and out_count_match and in_count_match
        )

        timestamps = [
            value
            for value in (out_earliest, in_earliest, out_latest, in_latest)
            if value is not None
        ]
        if timestamps:
            chain_earliest = min(
                value for value in (out_earliest, in_earliest)
                if value is not None
            )
            chain_latest = max(
                value for value in (out_latest, in_latest)
                if value is not None
            )
            earliest_all = (
                chain_earliest
                if earliest_all is None
                else min(earliest_all, chain_earliest)
            )
            latest_all = (
                chain_latest
                if latest_all is None
                else max(latest_all, chain_latest)
            )
        else:
            chain_earliest = None
            chain_latest = None

        per_chain[chain] = {
            "official_config_counters": official[chain],
            "onchain_config_counters": onchain[chain],
            "official_onchain_counter_values_match": official_match,
            "outgoing_account_count": len(outgoing),
            "incoming_account_count": len(incoming),
            "outgoing_unique_sequence_count": outgoing_unique,
            "incoming_unique_source_sequence_count": incoming_unique,
            "outgoing_counter_matches_account_count": out_count_match,
            "incoming_counter_matches_account_count": in_count_match,
            "earliest_message_source_timestamp": chain_earliest,
            "latest_message_source_timestamp": chain_latest,
        }

    counter_closure = (
        all_official_onchain_match and all_counter_count_match
    )
    return {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "per_chain": per_chain,
        "official_onchain_counter_values_match": all_official_onchain_match,
        "counter_account_closure_verified": counter_closure,
        "current_message_universe_count_closed": counter_closure,
        "observed_earliest_message_source_timestamp": earliest_all,
        "observed_latest_message_source_timestamp": latest_all,
        "required_flow_lookback_seconds": REQUIRED_FLOW_LOOKBACK_SECONDS,
        "retention_deletion_semantics_verified": False,
        "historical_retention_complete_verified": False,
        "requested_window_coverage_verified": False,
        "coverage_complete_verified": False,
        "missing_history_zero_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONFIG_PDA",
    "CONTRACT",
    "REQUIRED_FLOW_LOOKBACK_SECONDS",
    "WarpMessageRetentionCoverageError",
    "evaluate_warp_message_counter_closure",
    "fetch_classified_warp_config_account",
    "fetch_official_warp_config",
]
