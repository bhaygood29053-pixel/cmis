"""Verified-on-structure Warp message-state source for Bridge Flow Intelligence.

This module reads Warp-owned OutgoingMsg and IncomingMsg accounts directly from
Solana-compatible RPC.  Account TYPE identity is verified by exact owner, exact
Anchor discriminator, exact layout size, and PDA derivation.  Route pairing is
then verified by sequence, sender, amount, source timestamp, exact mints, and
expected native/wrapped operation topology.

It does not claim historical completeness merely because current program
accounts can be enumerated.  Coverage remains a separate gate.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Callable

import requests

from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
    WARP_CONFIG_SEMANTICS_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_inventory import (
    DEFAULT_COMMITMENT,
    SOLANA_RPC_URL,
    WARP_PROGRAM_ID,
    X1_RPC_URL,
)
from liquidity_scout.providers.x1.warp_semantic_layout_discovery import (
    anchor_account_discriminator,
    create_program_address,
)

CONTRACT = "warp_onchain_transfer_history/v1"
OUTGOING_ACCOUNT = "OutgoingMsg"
INCOMING_ACCOUNT = "IncomingMsg"
OUTGOING_SPACE = 106
INCOMING_SPACE = 116
LEGACY_INCOMING_SPACE = 107
OUTGOING_SEED = b"evt_out"
INCOMING_SEED = b"evt_in"
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class WarpOnchainTransferHistoryError(RuntimeError):
    """Raised when Warp transfer-state evidence fails closed."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _b58encode(raw: bytes) -> str:
    data = bytes(raw)
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58[remainder] + encoded
    pad = len(data) - len(data.lstrip(b"\x00"))
    return ("1" * pad) + encoded


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class _Reader:
    def __init__(self, raw: bytes, offset: int = 8):
        self.raw = raw
        self.offset = offset

    def take(self, count: int) -> bytes:
        end = self.offset + count
        if count < 0 or end > len(self.raw):
            raise WarpOnchainTransferHistoryError("account layout exceeds bytes")
        value = self.raw[self.offset:end]
        self.offset = end
        return value

    def u8(self) -> int:
        return self.take(1)[0]

    def bool(self) -> bool:
        value = self.u8()
        if value not in (0, 1):
            raise WarpOnchainTransferHistoryError("invalid Borsh bool")
        return bool(value)

    def u64(self) -> int:
        return int.from_bytes(self.take(8), "little")

    def i64(self) -> int:
        return int.from_bytes(self.take(8), "little", signed=True)

    def pubkey(self) -> str:
        return _b58encode(self.take(32))


def _verified_pda(*, pubkey: str, seed: bytes, seq: int, bump: int) -> bool:
    try:
        expected = create_program_address(
            [seed, int(seq).to_bytes(8, "little"), bytes([int(bump)])],
            WARP_PROGRAM_ID,
        )
    except Exception as exc:
        raise WarpOnchainTransferHistoryError(
            f"PDA derivation failed ({type(exc).__name__})"
        ) from None
    return expected == pubkey


def decode_outgoing_account(*, pubkey: str, raw: bytes) -> dict[str, Any]:
    if len(raw) != OUTGOING_SPACE:
        raise WarpOnchainTransferHistoryError("OutgoingMsg length mismatch")
    expected = anchor_account_discriminator(OUTGOING_ACCOUNT)
    if raw[:8] != expected:
        raise WarpOnchainTransferHistoryError("OutgoingMsg discriminator mismatch")

    r = _Reader(raw)
    seq = r.u64()
    sender = r.pubkey()
    token_mint = r.pubkey()
    amount = r.u64()
    timestamp = r.i64()
    fee_paid = r.u64()
    operation = r.u8()
    bump = r.u8()
    if r.offset != len(raw):
        raise WarpOnchainTransferHistoryError("OutgoingMsg trailing bytes")
    if operation not in (0, 1):
        raise WarpOnchainTransferHistoryError("OutgoingMsg operation is invalid")
    if not _verified_pda(pubkey=pubkey, seed=OUTGOING_SEED, seq=seq, bump=bump):
        raise WarpOnchainTransferHistoryError("OutgoingMsg PDA mismatch")

    return {
        "account_type": OUTGOING_ACCOUNT,
        "pubkey": pubkey,
        "space": len(raw),
        "seq": seq,
        "sender": sender,
        "token_mint": token_mint,
        "amount_raw": amount,
        "timestamp": timestamp,
        "fee_paid_lamports": fee_paid,
        "operation": operation,
        "bump": bump,
        "account_type_identity_verified": True,
        "pda_identity_verified": True,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def decode_incoming_account(*, pubkey: str, raw: bytes) -> dict[str, Any]:
    if len(raw) not in (INCOMING_SPACE, LEGACY_INCOMING_SPACE):
        raise WarpOnchainTransferHistoryError("IncomingMsg length mismatch")
    expected = anchor_account_discriminator(INCOMING_ACCOUNT)
    if raw[:8] != expected:
        raise WarpOnchainTransferHistoryError("IncomingMsg discriminator mismatch")

    r = _Reader(raw)
    source_seq = r.u64()
    sender = r.pubkey()
    token_mint = r.pubkey()
    amount = r.u64()
    source_timestamp = r.i64()
    executed_timestamp = r.i64()
    operation = r.u8()
    processed = r.bool()
    bump = r.u8()
    claimable_after = None
    claimed = None
    legacy_layout = len(raw) == LEGACY_INCOMING_SPACE
    if not legacy_layout:
        claimable_after = r.i64()
        claimed = r.bool()
    if r.offset != len(raw):
        raise WarpOnchainTransferHistoryError("IncomingMsg trailing bytes")
    if operation not in (0, 1):
        raise WarpOnchainTransferHistoryError("IncomingMsg operation is invalid")
    if not _verified_pda(
        pubkey=pubkey,
        seed=INCOMING_SEED,
        seq=source_seq,
        bump=bump,
    ):
        raise WarpOnchainTransferHistoryError("IncomingMsg PDA mismatch")

    return {
        "account_type": INCOMING_ACCOUNT,
        "pubkey": pubkey,
        "space": len(raw),
        "source_seq": source_seq,
        "sender": sender,
        "token_mint": token_mint,
        "amount_raw": amount,
        "source_timestamp": source_timestamp,
        "executed_timestamp": executed_timestamp,
        "operation": operation,
        "processed": processed,
        "bump": bump,
        "claimable_after": claimable_after,
        "claimed": claimed,
        "legacy_layout": legacy_layout,
        "account_type_identity_verified": True,
        "pda_identity_verified": True,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _rpc_request(
    method: str,
    params: list[Any],
    *,
    rpc_url: str,
    timeout: int = 45,
    post: Callable[..., Any] = requests.post,
) -> Any:
    try:
        response = post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
            headers={
                "content-type": "application/json",
                "user-agent": "CMIS-Warp-Transfer-History/1.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise WarpOnchainTransferHistoryError(
            f"{method} transport failed ({type(exc).__name__})"
        ) from None
    if not isinstance(body, Mapping):
        raise WarpOnchainTransferHistoryError("RPC returned non-object body")
    if body.get("error") is not None:
        error = body.get("error")
        code = error.get("code") if isinstance(error, Mapping) else None
        raise WarpOnchainTransferHistoryError(
            f"{method} returned JSON-RPC error code {code!r}"
        )
    if "result" not in body:
        raise WarpOnchainTransferHistoryError("RPC response missing result")
    return body.get("result")


def _parse_rpc_rows(
    result: Any,
    *,
    chain: str,
    account_type: str,
) -> dict[str, Any]:
    context_slot = None
    rows = result
    if isinstance(result, Mapping) and "value" in result:
        rows = result.get("value")
        context = result.get("context")
        if isinstance(context, Mapping):
            try:
                context_slot = int(context.get("slot"))
            except (TypeError, ValueError):
                context_slot = None
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise WarpOnchainTransferHistoryError("RPC result is not an account list")

    decoder = (
        decode_outgoing_account if account_type == OUTGOING_ACCOUNT
        else decode_incoming_account
    )
    decoded = []
    malformed = 0
    owner_mismatch = 0
    executable_mismatch = 0
    unsupported_space = 0
    for row in rows:
        if not isinstance(row, Mapping):
            malformed += 1
            continue
        pubkey = _text(row.get("pubkey"))
        account = row.get("account")
        if not pubkey or not isinstance(account, Mapping):
            malformed += 1
            continue
        if _text(account.get("owner")) != WARP_PROGRAM_ID:
            owner_mismatch += 1
            continue
        if account.get("executable") is not False:
            executable_mismatch += 1
            continue
        data = account.get("data")
        if (
            not isinstance(data, Sequence)
            or isinstance(data, (str, bytes, bytearray))
            or len(data) != 2
            or not isinstance(data[0], str)
            or data[1] != "base64"
        ):
            malformed += 1
            continue
        try:
            raw = base64.b64decode(data[0], validate=True)
        except (binascii.Error, ValueError):
            malformed += 1
            continue
        if account_type == OUTGOING_ACCOUNT and len(raw) != OUTGOING_SPACE:
            unsupported_space += 1
            continue
        if account_type == INCOMING_ACCOUNT and len(raw) not in (
            INCOMING_SPACE,
            LEGACY_INCOMING_SPACE,
        ):
            unsupported_space += 1
            continue
        decoded.append(decoder(pubkey=pubkey, raw=raw))

    decoded.sort(
        key=lambda item: (
            int(item.get("seq", item.get("source_seq", 0))),
            item["pubkey"],
        )
    )
    if malformed or owner_mismatch or executable_mismatch or unsupported_space:
        raise WarpOnchainTransferHistoryError(
            "message-account enumeration contained unresolved rows: "
            f"malformed={malformed}, owner={owner_mismatch}, "
            f"executable={executable_mismatch}, space={unsupported_space}"
        )

    fingerprint = [
        {
            "pubkey": item["pubkey"],
            "seq": item.get("seq", item.get("source_seq")),
            "token_mint": item["token_mint"],
            "amount_raw": item["amount_raw"],
            "timestamp": item.get("timestamp", item.get("source_timestamp")),
            "executed_timestamp": item.get("executed_timestamp"),
            "processed": item.get("processed"),
            "claimed": item.get("claimed"),
            "raw_sha256": item["raw_sha256"],
        }
        for item in decoded
    ]
    return {
        "contract": CONTRACT,
        "chain": chain,
        "account_type": account_type,
        "program_id": WARP_PROGRAM_ID,
        "context_slot": context_slot,
        "returned_row_count": len(rows),
        "decoded_account_count": len(decoded),
        "accounts": decoded,
        "account_type_identity_verified": True,
        "all_pda_identities_verified": all(
            item["pda_identity_verified"] for item in decoded
        ),
        "snapshot_sha256": _canonical_sha256(fingerprint),
        "read_only": True,
        "execution_authorized": False,
    }


def fetch_warp_message_accounts(
    *,
    chain: str,
    account_type: str,
    rpc_url: str | None = None,
    commitment: str = DEFAULT_COMMITMENT,
    timeout: int = 45,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    chain_value = str(chain or "").strip().casefold()
    if chain_value not in {"solana", "x1"}:
        raise ValueError("chain must be solana or x1")
    if account_type not in {OUTGOING_ACCOUNT, INCOMING_ACCOUNT}:
        raise ValueError("account_type must be OutgoingMsg or IncomingMsg")
    rpc = rpc_url or (SOLANA_RPC_URL if chain_value == "solana" else X1_RPC_URL)
    discriminator = anchor_account_discriminator(account_type)
    config = {
        "encoding": "base64",
        "commitment": commitment,
        "filters": [
            {
                "memcmp": {
                    "offset": 0,
                    "bytes": _b58encode(discriminator),
                }
            }
        ],
        "withContext": True,
    }
    result = requester(
        "getProgramAccounts",
        [WARP_PROGRAM_ID, config],
        rpc_url=rpc,
        timeout=timeout,
    )
    parsed = _parse_rpc_rows(
        result,
        chain=chain_value,
        account_type=account_type,
    )
    parsed.update(
        {
            "rpc_url": rpc,
            "commitment": commitment,
            "anchor_discriminator_hex": discriminator.hex(),
        }
    )
    return parsed


def capture_warp_message_state(
    *,
    solana_rpc_url: str = SOLANA_RPC_URL,
    x1_rpc_url: str = X1_RPC_URL,
    requester: Callable[..., Any] = _rpc_request,
) -> dict[str, Any]:
    snapshots = {}
    for chain, rpc in (("solana", solana_rpc_url), ("x1", x1_rpc_url)):
        snapshots[chain] = {
            "outgoing": fetch_warp_message_accounts(
                chain=chain,
                account_type=OUTGOING_ACCOUNT,
                rpc_url=rpc,
                requester=requester,
            ),
            "incoming": fetch_warp_message_accounts(
                chain=chain,
                account_type=INCOMING_ACCOUNT,
                rpc_url=rpc,
                requester=requester,
            ),
        }
    return {
        "contract": CONTRACT,
        "program_id": WARP_PROGRAM_ID,
        "solana": snapshots["solana"],
        "x1": snapshots["x1"],
        "current_program_account_enumeration_verified": True,
        "historical_retention_complete_verified": False,
        "coverage_complete_verified": False,
        "read_only": True,
        "execution_authorized": False,
    }


def _require_route_observation(route_observation: Any) -> dict[str, Any]:
    if not isinstance(route_observation, Mapping):
        raise ValueError("route_observation must be a mapping")
    if route_observation.get("contract") != WARP_CONFIG_SEMANTICS_CONTRACT:
        raise WarpOnchainTransferHistoryError(
            f"route observation must use {WARP_CONFIG_SEMANTICS_CONTRACT}"
        )
    if (
        route_observation.get("semantic_contract_id")
        != WARP_CONFIG_SEMANTIC_CONTRACT_ID
    ):
        raise WarpOnchainTransferHistoryError(
            "route observation semantic contract is not accepted"
        )
    source = route_observation.get("source")
    destination = route_observation.get("destination")
    if not isinstance(source, Mapping) or not isinstance(destination, Mapping):
        raise WarpOnchainTransferHistoryError("route endpoints are missing")
    if source.get("chain") != "solana" or destination.get("chain") != "x1":
        raise WarpOnchainTransferHistoryError(
            "v1 normalizer requires canonical solana -> x1 route orientation"
        )
    decimals = route_observation.get("route_decimals")
    if isinstance(decimals, bool):
        raise WarpOnchainTransferHistoryError("route decimals are invalid")
    try:
        decimals_value = int(decimals)
    except (TypeError, ValueError):
        raise WarpOnchainTransferHistoryError("route decimals are missing") from None
    if decimals_value < 0:
        raise WarpOnchainTransferHistoryError("route decimals are invalid")
    return {
        "route_id": _text(route_observation.get("route_id")),
        "source": {
            "chain": "solana",
            "asset_id": _text(source.get("asset_id")),
            "asset_id_kind": source.get("asset_id_kind"),
        },
        "destination": {
            "chain": "x1",
            "asset_id": _text(destination.get("asset_id")),
            "asset_id_kind": destination.get("asset_id_kind"),
        },
        "source_is_native": bool(route_observation.get("source_is_native")),
        "destination_is_native": bool(
            route_observation.get("destination_is_native")
        ),
        "decimals": decimals_value,
    }


def _accounts(snapshot: Any, chain: str, side: str) -> list[Mapping[str, Any]]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("message_state must be a mapping")
    chain_block = snapshot.get(chain)
    if not isinstance(chain_block, Mapping):
        raise WarpOnchainTransferHistoryError(f"{chain} snapshot is missing")
    block = chain_block.get(side)
    if not isinstance(block, Mapping):
        raise WarpOnchainTransferHistoryError(
            f"{chain}.{side} snapshot is missing"
        )
    if block.get("account_type_identity_verified") is not True:
        raise WarpOnchainTransferHistoryError(
            f"{chain}.{side} account type is not verified"
        )
    if block.get("all_pda_identities_verified") is not True:
        raise WarpOnchainTransferHistoryError(
            f"{chain}.{side} PDA identity is not verified"
        )
    rows = block.get("accounts")
    if not isinstance(rows, list):
        raise WarpOnchainTransferHistoryError(
            f"{chain}.{side}.accounts is invalid"
        )
    return rows


def normalize_warp_route_events(
    *,
    route_observation: Any,
    message_state: Any,
) -> dict[str, Any]:
    """Normalize real paired Warp message state into #409 settled-event records."""

    route = _require_route_observation(route_observation)
    if not route["route_id"] or not route["source"]["asset_id"] or not route["destination"]["asset_id"]:
        raise WarpOnchainTransferHistoryError("route identity is incomplete")
    if route["source"]["asset_id_kind"] != "mint" or route["destination"]["asset_id_kind"] != "mint":
        raise WarpOnchainTransferHistoryError("route asset ids must be exact mints")

    sol_out = _accounts(message_state, "solana", "outgoing")
    x1_out = _accounts(message_state, "x1", "outgoing")
    sol_in = _accounts(message_state, "solana", "incoming")
    x1_in = _accounts(message_state, "x1", "incoming")

    incoming_by_chain_seq = {
        "solana": {int(row["source_seq"]): row for row in sol_in},
        "x1": {int(row["source_seq"]): row for row in x1_in},
    }

    unresolved: dict[str, int] = {}
    events = []
    candidate_route_outgoing_count = 0

    def add_unresolved(reason: str) -> None:
        unresolved[reason] = unresolved.get(reason, 0) + 1

    directions = [
        {
            "actual_source_chain": "solana",
            "actual_destination_chain": "x1",
            "outgoing_rows": sol_out,
            "source_mint": route["source"]["asset_id"],
            "destination_mint": route["destination"]["asset_id"],
            "source_is_native": route["source_is_native"],
            "destination_is_native": route["destination_is_native"],
            "direction": "inflow",
        },
        {
            "actual_source_chain": "x1",
            "actual_destination_chain": "solana",
            "outgoing_rows": x1_out,
            "source_mint": route["destination"]["asset_id"],
            "destination_mint": route["source"]["asset_id"],
            "source_is_native": route["destination_is_native"],
            "destination_is_native": route["source_is_native"],
            "direction": "outflow",
        },
    ]

    for spec in directions:
        incoming_index = incoming_by_chain_seq[spec["actual_destination_chain"]]
        expected_out_operation = 1 if spec["source_is_native"] else 0
        expected_in_operation = 1 if spec["destination_is_native"] else 0

        for outgoing in spec["outgoing_rows"]:
            if outgoing.get("token_mint") != spec["source_mint"]:
                continue
            candidate_route_outgoing_count += 1
            seq = int(outgoing["seq"])
            incoming = incoming_index.get(seq)
            if incoming is None:
                add_unresolved("missing_destination_incoming")
                continue
            if incoming.get("token_mint") != spec["destination_mint"]:
                add_unresolved("destination_mint_mismatch")
                continue
            if incoming.get("sender") != outgoing.get("sender"):
                add_unresolved("sender_mismatch")
                continue
            if int(incoming.get("amount_raw", -1)) != int(outgoing.get("amount_raw", -2)):
                add_unresolved("amount_mismatch")
                continue
            if int(incoming.get("source_timestamp", -1)) != int(outgoing.get("timestamp", -2)):
                add_unresolved("source_timestamp_mismatch")
                continue
            if int(outgoing.get("operation", -1)) != expected_out_operation:
                add_unresolved("outgoing_operation_mismatch")
                continue
            if int(incoming.get("operation", -1)) != expected_in_operation:
                add_unresolved("incoming_operation_mismatch")
                continue
            if incoming.get("processed") is not True:
                add_unresolved("destination_not_processed")
                continue
            if incoming.get("legacy_layout") is True:
                add_unresolved("legacy_incoming_claim_semantics_unverified")
                continue

            claimable_after = int(incoming.get("claimable_after") or 0)
            claimed = incoming.get("claimed")
            if claimable_after > 0:
                if claimed is not True:
                    add_unresolved("delayed_transfer_not_claimed")
                else:
                    add_unresolved("delayed_claim_settlement_timestamp_unverified")
                continue

            settled_at = int(incoming.get("executed_timestamp") or 0)
            if settled_at <= 0:
                add_unresolved("executed_timestamp_missing")
                continue

            transfer_id = (
                f"warp:{spec['actual_source_chain']}:{seq}"
            )
            event_id = (
                f"{transfer_id}:{outgoing['pubkey']}:{incoming['pubkey']}"
            )
            events.append(
                {
                    "event_id": event_id,
                    "transfer_id": transfer_id,
                    "route_id": route["route_id"],
                    "direction": spec["direction"],
                    "amount_raw": int(outgoing["amount_raw"]),
                    "decimals": route["decimals"],
                    "settled_at": settled_at,
                    "source": dict(route["source"]),
                    "destination": dict(route["destination"]),
                    "lifecycle_state": "settled",
                    "settlement_verified": True,
                    "pairing_verified": True,
                    "actual_source_chain": spec["actual_source_chain"],
                    "actual_destination_chain": spec["actual_destination_chain"],
                    "seq": seq,
                    "outgoing_pubkey": outgoing["pubkey"],
                    "incoming_pubkey": incoming["pubkey"],
                    "source_timestamp": int(outgoing["timestamp"]),
                    "outgoing_operation": int(outgoing["operation"]),
                    "incoming_operation": int(incoming["operation"]),
                }
            )

    events.sort(key=lambda item: (item["settled_at"], item["transfer_id"]))
    coverage_start = min(
        (int(item["source_timestamp"]) for item in events),
        default=None,
    )
    coverage_end_observed = max(
        (int(item["settled_at"]) for item in events),
        default=None,
    )
    evidence_core = {
        "route_id": route["route_id"],
        "candidate_route_outgoing_count": candidate_route_outgoing_count,
        "accepted_settled_event_count": len(events),
        "unresolved_counts": dict(sorted(unresolved.items())),
        "events": events,
        "observed_coverage_start": coverage_start,
        "observed_latest_settlement": coverage_end_observed,
    }
    return {
        "contract": CONTRACT,
        **evidence_core,
        "evidence_sha256": _canonical_sha256(evidence_core),
        "current_program_account_enumeration_verified": True,
        "pairing_semantics_verified": True,
        "settled_event_semantics_verified": True,
        "historical_retention_complete_verified": False,
        "coverage_complete_verified": False,
        "flow_event_normalization_authorized": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "INCOMING_ACCOUNT",
    "INCOMING_SPACE",
    "LEGACY_INCOMING_SPACE",
    "OUTGOING_ACCOUNT",
    "OUTGOING_SPACE",
    "WarpOnchainTransferHistoryError",
    "capture_warp_message_state",
    "decode_incoming_account",
    "decode_outgoing_account",
    "fetch_warp_message_accounts",
    "normalize_warp_route_events",
]
