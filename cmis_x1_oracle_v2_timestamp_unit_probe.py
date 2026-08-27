#!/usr/bin/env python3
"""Read-only Oracle V2 timestamp-unit evidence probe for CMIS issue #283.

The probe samples successful historical X1 transactions for the verified Oracle
V2 state PDA, decodes the pinned-source batch_submit_prices instruction and its
Ed25519 signed message, and compares the raw signed timestamp with the verified
X1 block time of the same transaction.

No correlation tolerance is invented. Without an explicit tolerance and
provenance the probe reports raw candidate Unix-ms differences only and keeps
timestamp_unit_verified=false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

from liquidity_scout.providers.x1.oracle_v2_policy import (
    assess_unix_ms_block_time_correlation,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, X1RPCProvider


SERVICE = "x1_oracle_v2_timestamp_unit_probe"
VERSION = "0.1.0"
CHAIN = "x1"

ORACLE_V2_REPOSITORY = "jacklevin74/oracle-v2"
ORACLE_V2_PINNED_COMMIT = "97177f772689e44ca4eed9bb95be32ffdf0c5e66"
PROGRAM_ID = "9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2"
STATE_PDA = "8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf"
ED25519_PROGRAM_ID = "Ed25519SigVerify111111111111111111111111111"
BATCH_SUBMIT_PRICES_DISCRIMINATOR = bytes.fromhex("116224b954f96553")
NUM_ASSETS = 6
NUM_RELAY_SLOTS = 5
DEFAULT_HISTORY_LIMIT = 25

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_U16_CURRENT_INSTRUCTION = 0xFFFF


class OracleV2TimestampProbeError(RuntimeError):
    """Raised when candidate timestamp evidence violates the bounded contract."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _int(value: Any, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool):
        raise OracleV2TimestampProbeError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise OracleV2TimestampProbeError(f"{name} must be an integer") from exc
    if str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise OracleV2TimestampProbeError(f"{name} must be an integer")
    if minimum is not None and parsed < minimum:
        raise OracleV2TimestampProbeError(f"{name} must be >= {minimum}")
    return parsed


def _b58decode(value: Any) -> bytes:
    text = _text(value)
    if text is None:
        raise OracleV2TimestampProbeError("base58 data is required")

    number = 0
    for character in text:
        try:
            digit = _B58_ALPHABET.index(character)
        except ValueError as exc:
            raise OracleV2TimestampProbeError("invalid base58 data") from exc
        number = number * 58 + digit

    raw = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeroes = len(text) - len(text.lstrip("1"))
    return b"\x00" * leading_zeroes + raw


def batch_submit_prices_discriminator() -> bytes:
    return hashlib.sha256(b"global:batch_submit_prices").digest()[:8]


def _instruction_program_id(instruction: Mapping[str, Any]) -> str | None:
    return _text(instruction.get("programId"))


def _instruction_accounts(instruction: Mapping[str, Any]) -> list[str]:
    raw = instruction.get("accounts")
    if not isinstance(raw, list):
        return []

    accounts = []
    for item in raw:
        if isinstance(item, Mapping):
            value = _text(item.get("pubkey"))
        else:
            value = _text(item)
        if value is None:
            return []
        accounts.append(value)
    return accounts


def _instruction_data(instruction: Mapping[str, Any]) -> bytes:
    raw = instruction.get("data")
    return _b58decode(raw)


def parse_batch_signed_message(message: bytes) -> dict[str, Any]:
    """Parse the exact pinned-source BATCH signed-message shape."""
    try:
        text = bytes(message).decode("ascii")
    except UnicodeDecodeError as exc:
        raise OracleV2TimestampProbeError(
            "batch signed message is not ASCII"
        ) from exc

    parts = text.split(":")
    if len(parts) != 9 or parts[0] != "BATCH":
        raise OracleV2TimestampProbeError(
            "batch signed message must contain exactly 9 colon fields"
        )

    relay_index = _int(parts[1], name="relay_index", minimum=1)
    if relay_index > NUM_RELAY_SLOTS:
        raise OracleV2TimestampProbeError("relay_index must be <= 5")

    prices = []
    for asset_index, raw_price in enumerate(parts[2:8], start=1):
        price = _int(raw_price, name=f"price_{asset_index}")
        if price < 0:
            raise OracleV2TimestampProbeError(
                "batch signed prices must be non-negative"
            )
        prices.append(price)

    timestamp_raw = _int(parts[8], name="timestamp_raw", minimum=1)

    return {
        "message_text": text,
        "message_sha256": hashlib.sha256(message).hexdigest(),
        "relay_index": relay_index,
        "prices_raw": prices,
        "timestamp_raw": timestamp_raw,
    }


def decode_batch_submit_prices_instruction(
    instruction: Mapping[str, Any],
) -> dict[str, Any]:
    """Decode exact Anchor/Borsh batch_submit_prices instruction arguments."""
    if not isinstance(instruction, Mapping):
        raise OracleV2TimestampProbeError("instruction is not an object")
    if _instruction_program_id(instruction) != PROGRAM_ID:
        raise OracleV2TimestampProbeError("instruction program ID mismatch")

    accounts = _instruction_accounts(instruction)
    if len(accounts) < 3 or accounts[0] != STATE_PDA:
        raise OracleV2TimestampProbeError(
            "batch instruction does not target expected Oracle state PDA"
        )

    data = _instruction_data(instruction)
    minimum_size = 8 + 1 + 4 + NUM_ASSETS * 8 + 8 + 64 + 4
    if len(data) < minimum_size:
        raise OracleV2TimestampProbeError("batch instruction data is too short")

    if data[:8] != BATCH_SUBMIT_PRICES_DISCRIMINATOR:
        raise OracleV2TimestampProbeError(
            "batch_submit_prices discriminator mismatch"
        )

    offset = 8
    relay_index = data[offset]
    offset += 1
    if relay_index < 1 or relay_index > NUM_RELAY_SLOTS:
        raise OracleV2TimestampProbeError("batch relay index is out of range")

    price_count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if price_count != NUM_ASSETS:
        raise OracleV2TimestampProbeError(
            "batch price vector must contain exactly six prices"
        )

    prices_raw = list(
        struct.unpack_from(f"<{NUM_ASSETS}q", data, offset)
    )
    offset += NUM_ASSETS * 8
    if any(price < 0 for price in prices_raw):
        raise OracleV2TimestampProbeError(
            "batch instruction contains a negative price"
        )

    timestamp_raw = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    if timestamp_raw <= 0:
        raise OracleV2TimestampProbeError(
            "batch instruction timestamp must be positive"
        )

    signature = data[offset : offset + 64]
    if len(signature) != 64:
        raise OracleV2TimestampProbeError(
            "batch instruction signature field is truncated"
        )
    offset += 64

    if offset + 4 > len(data):
        raise OracleV2TimestampProbeError(
            "batch instruction message length is missing"
        )
    message_size = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    message_end = offset + message_size
    if message_end != len(data):
        raise OracleV2TimestampProbeError(
            "batch instruction message length/trailing bytes mismatch"
        )

    message = data[offset:message_end]
    parsed_message = parse_batch_signed_message(message)

    if parsed_message["relay_index"] != relay_index:
        raise OracleV2TimestampProbeError(
            "batch instruction relay index does not match signed message"
        )
    if parsed_message["prices_raw"] != prices_raw:
        raise OracleV2TimestampProbeError(
            "batch instruction prices do not match signed message"
        )
    if parsed_message["timestamp_raw"] != timestamp_raw:
        raise OracleV2TimestampProbeError(
            "batch instruction timestamp does not match signed message"
        )

    return {
        "relay_index": relay_index,
        "prices_raw": prices_raw,
        "timestamp_raw": timestamp_raw,
        "instruction_signature_sha256": hashlib.sha256(signature).hexdigest(),
        "message": message,
        "message_text": parsed_message["message_text"],
        "message_sha256": parsed_message["message_sha256"],
        "accounts": accounts,
        "source_contract_timestamp_unit": "unix_ms",
        "deployed_binary_source_equivalence_verified": False,
    }


def decode_ed25519_instruction(
    instruction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Decode self-contained Ed25519SigVerify entries, excluding raw secrets."""
    if not isinstance(instruction, Mapping):
        raise OracleV2TimestampProbeError("Ed25519 instruction is not an object")
    if _instruction_program_id(instruction) != ED25519_PROGRAM_ID:
        raise OracleV2TimestampProbeError("Ed25519 program ID mismatch")

    data = _instruction_data(instruction)
    if len(data) < 16:
        raise OracleV2TimestampProbeError("Ed25519 instruction data is too short")

    num_signatures = data[0]
    if num_signatures < 1:
        raise OracleV2TimestampProbeError(
            "Ed25519 instruction contains no signatures"
        )

    header_end = 2 + 14 * num_signatures
    if header_end > len(data):
        raise OracleV2TimestampProbeError(
            "Ed25519 signature-offset table is truncated"
        )

    decoded = []
    for entry_index in range(num_signatures):
        entry_offset = 2 + 14 * entry_index
        (
            sig_offset,
            sig_ix_index,
            pubkey_offset,
            pubkey_ix_index,
            msg_offset,
            msg_size,
            msg_ix_index,
        ) = struct.unpack_from("<7H", data, entry_offset)

        if (
            sig_ix_index != _U16_CURRENT_INSTRUCTION
            or pubkey_ix_index != _U16_CURRENT_INSTRUCTION
            or msg_ix_index != _U16_CURRENT_INSTRUCTION
        ):
            raise OracleV2TimestampProbeError(
                "cross-instruction Ed25519 offsets are unsupported"
            )

        sig_end = sig_offset + 64
        pubkey_end = pubkey_offset + 32
        msg_end = msg_offset + msg_size
        if (
            sig_offset < header_end
            or pubkey_offset < header_end
            or msg_offset < header_end
            or sig_end > len(data)
            or pubkey_end > len(data)
            or msg_end > len(data)
        ):
            raise OracleV2TimestampProbeError(
                "Ed25519 offsets are outside instruction data"
            )

        signature = data[sig_offset:sig_end]
        pubkey = data[pubkey_offset:pubkey_end]
        message = data[msg_offset:msg_end]

        decoded.append({
            "entry_index": entry_index,
            "message": message,
            "message_sha256": hashlib.sha256(message).hexdigest(),
            "signature_sha256": hashlib.sha256(signature).hexdigest(),
            "pubkey_sha256": hashlib.sha256(pubkey).hexdigest(),
            "message_size": msg_size,
        })

    return decoded


def _transaction_instructions(transaction: Mapping[str, Any]) -> list[Any]:
    raw_transaction = transaction.get("transaction")
    if not isinstance(raw_transaction, Mapping):
        return []

    message = raw_transaction.get("message")
    if not isinstance(message, Mapping):
        return []

    instructions = message.get("instructions")
    return instructions if isinstance(instructions, list) else []


def _transaction_logs(transaction: Mapping[str, Any]) -> list[str]:
    meta = transaction.get("meta")
    if not isinstance(meta, Mapping):
        return []
    logs = meta.get("logMessages")
    if not isinstance(logs, list):
        return []
    return [str(item) for item in logs if item is not None]


def _decode_candidate_from_transaction(
    *,
    history_row: Mapping[str, Any],
    transaction_record: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if history_row.get("err") is not None:
        return None, "history_transaction_failed"
    if transaction_record.get("transaction_available") is not True:
        return None, "transaction_unavailable"

    transaction = transaction_record.get("transaction")
    if not isinstance(transaction, Mapping):
        return None, "transaction_malformed"

    meta = transaction.get("meta")
    if not isinstance(meta, Mapping) or meta.get("err") is not None:
        return None, "transaction_meta_failed_or_missing"

    try:
        tx_slot = _int(transaction.get("slot"), name="transaction_slot", minimum=0)
        history_slot = _int(history_row.get("slot"), name="history_slot", minimum=0)
    except OracleV2TimestampProbeError:
        return None, "slot_invalid"
    if tx_slot != history_slot:
        return None, "transaction_history_slot_mismatch"

    instructions = _transaction_instructions(transaction)
    if not instructions:
        return None, "transaction_instructions_missing"

    batch_candidates = []
    ed25519_entries = []

    for instruction_index, instruction in enumerate(instructions):
        if not isinstance(instruction, Mapping):
            continue

        program_id = _instruction_program_id(instruction)
        if program_id == PROGRAM_ID:
            try:
                decoded = decode_batch_submit_prices_instruction(instruction)
            except OracleV2TimestampProbeError:
                continue
            batch_candidates.append({
                "instruction_index": instruction_index,
                **decoded,
            })
        elif program_id == ED25519_PROGRAM_ID:
            try:
                decoded_entries = decode_ed25519_instruction(instruction)
            except OracleV2TimestampProbeError:
                continue
            for decoded in decoded_entries:
                ed25519_entries.append({
                    "instruction_index": instruction_index,
                    **decoded,
                })

    if len(batch_candidates) != 1:
        return None, (
            "batch_instruction_not_found"
            if not batch_candidates
            else "multiple_batch_instructions_ambiguous"
        )

    batch = batch_candidates[0]
    matching_ed = [
        entry
        for entry in ed25519_entries
        if entry["message"] == batch["message"]
    ]
    if len(matching_ed) != 1:
        return None, (
            "matching_ed25519_message_not_found"
            if not matching_ed
            else "multiple_matching_ed25519_messages_ambiguous"
        )

    ed = matching_ed[0]

    tx_block_time = transaction.get("blockTime")
    if isinstance(tx_block_time, bool) or not isinstance(tx_block_time, (int, float)):
        return None, "transaction_block_time_missing_or_invalid"
    if tx_block_time < 0 or int(tx_block_time) != tx_block_time:
        return None, "transaction_block_time_not_integer_seconds"
    tx_block_time = int(tx_block_time)

    history_block_time = history_row.get("block_time")
    if history_block_time is not None:
        if (
            isinstance(history_block_time, bool)
            or not isinstance(history_block_time, (int, float))
            or history_block_time < 0
            or int(history_block_time) != history_block_time
        ):
            return None, "history_block_time_invalid"
        if int(history_block_time) != tx_block_time:
            return None, "transaction_history_block_time_mismatch"

    signature = _text(history_row.get("signature"))
    if signature is None or signature != _text(transaction_record.get("signature")):
        return None, "transaction_signature_mismatch"

    relay_log = (
        f"Batch prices submitted for relay slot {batch['relay_index']}"
    )
    source_contract_log_observed = any(
        relay_log in log for log in _transaction_logs(transaction)
    )

    return {
        "signature": signature,
        "slot": tx_slot,
        "transaction_block_time_seconds": tx_block_time,
        "history_block_time_seconds": (
            int(history_block_time)
            if history_block_time is not None
            else None
        ),
        "confirmation_status": history_row.get("confirmation_status"),
        "oracle_instruction_index": batch["instruction_index"],
        "ed25519_instruction_index": ed["instruction_index"],
        "relay_index": batch["relay_index"],
        "prices_raw": batch["prices_raw"],
        "timestamp_raw": batch["timestamp_raw"],
        "signed_message": batch["message_text"],
        "signed_message_sha256": batch["message_sha256"],
        "instruction_signature_sha256": batch[
            "instruction_signature_sha256"
        ],
        "ed25519_signature_sha256": ed["signature_sha256"],
        "ed25519_pubkey_sha256": ed["pubkey_sha256"],
        "source_contract_timestamp_unit": "unix_ms",
        "source_contract_log_observed": source_contract_log_observed,
        "deployed_binary_source_equivalence_verified": False,
    }, None


def _verify_block_time(
    *,
    provider: X1RPCProvider,
    sample: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        block_record = provider.get_block_time(sample["slot"])
    except Exception as exc:
        return None, f"getBlockTime_failed:{type(exc).__name__}"

    if not isinstance(block_record, Mapping):
        return None, "getBlockTime_result_malformed"
    if block_record.get("block_time_verified") is not True:
        return None, "getBlockTime_unverified"

    block_time = block_record.get("block_time")
    if (
        isinstance(block_time, bool)
        or not isinstance(block_time, (int, float))
        or block_time < 0
        or int(block_time) != block_time
    ):
        return None, "getBlockTime_value_invalid"
    block_time = int(block_time)

    if block_time != sample["transaction_block_time_seconds"]:
        return None, "getBlockTime_transaction_block_time_mismatch"

    enriched = dict(sample)
    enriched["verified_block_time_seconds"] = block_time
    enriched["verified_block_time_source"] = block_record.get("source")
    enriched["candidate_unix_ms_block_time"] = block_time * 1000
    enriched["candidate_unix_ms_difference_ms"] = abs(
        sample["timestamp_raw"] - block_time * 1000
    )
    return enriched, None


def _correlation_policy(
    *,
    max_difference_ms: Any,
    tolerance_provenance: Any,
) -> dict[str, Any]:
    if max_difference_ms is None and tolerance_provenance is None:
        return {
            "configured": False,
            "max_difference_ms": None,
            "tolerance_provenance": None,
        }
    if max_difference_ms is None or tolerance_provenance is None:
        raise OracleV2TimestampProbeError(
            "max_difference_ms and tolerance_provenance must be supplied together"
        )

    tolerance = _int(
        max_difference_ms,
        name="max_difference_ms",
        minimum=0,
    )
    provenance = _text(tolerance_provenance)
    if provenance is None:
        raise OracleV2TimestampProbeError(
            "tolerance_provenance must be non-empty"
        )

    return {
        "configured": True,
        "max_difference_ms": tolerance,
        "tolerance_provenance": provenance,
    }


def probe_timestamp_unit_evidence(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    rpc_provider: X1RPCProvider | None = None,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    max_difference_ms: Any = None,
    tolerance_provenance: Any = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Collect bounded live timestamp-unit evidence without hidden policy."""
    history_limit = _int(history_limit, name="history_limit", minimum=1)
    if history_limit > 1000:
        raise OracleV2TimestampProbeError("history_limit must be <= 1000")

    correlation_policy = _correlation_policy(
        max_difference_ms=max_difference_ms,
        tolerance_provenance=tolerance_provenance,
    )
    provider = rpc_provider or X1RPCProvider(rpc_url=rpc_url)
    observed_at = observed_at or datetime.now(timezone.utc)

    history = provider.get_signatures_for_address(
        STATE_PDA,
        limit=history_limit,
    )
    if not isinstance(history, list):
        raise OracleV2TimestampProbeError(
            "X1 signature history result is not a list"
        )

    successful_history = [
        row
        for row in history
        if isinstance(row, Mapping) and row.get("err") is None
    ]
    signatures = [
        row.get("signature")
        for row in successful_history
        if _text(row.get("signature"))
    ]

    transaction_records = (
        provider.get_parsed_transactions(signatures)
        if signatures
        else []
    )
    by_signature = {
        row["signature"]: row
        for row in successful_history
        if _text(row.get("signature"))
    }

    samples = []
    rejected = []

    for record in transaction_records:
        if not isinstance(record, Mapping):
            rejected.append({
                "signature": None,
                "reason": "transaction_record_malformed",
            })
            continue

        signature = _text(record.get("signature"))
        history_row = by_signature.get(signature)
        if history_row is None:
            rejected.append({
                "signature": signature,
                "reason": "history_row_missing_for_transaction",
            })
            continue

        candidate, reason = _decode_candidate_from_transaction(
            history_row=history_row,
            transaction_record=record,
        )
        if candidate is None:
            rejected.append({
                "signature": signature,
                "slot": history_row.get("slot"),
                "reason": reason,
            })
            continue

        verified, reason = _verify_block_time(
            provider=provider,
            sample=candidate,
        )
        if verified is None:
            rejected.append({
                "signature": signature,
                "slot": history_row.get("slot"),
                "reason": reason,
            })
            continue

        if correlation_policy["configured"]:
            correlation = assess_unix_ms_block_time_correlation(
                timestamp_raw=verified["timestamp_raw"],
                block_time_seconds=verified["verified_block_time_seconds"],
                max_difference_ms=correlation_policy["max_difference_ms"],
                tolerance_provenance=correlation_policy[
                    "tolerance_provenance"
                ],
            )
            verified["explicit_correlation_assessment"] = correlation
        else:
            verified["explicit_correlation_assessment"] = None

        samples.append(verified)

    differences = [
        sample["candidate_unix_ms_difference_ms"]
        for sample in samples
    ]
    per_sample_policy_results = [
        sample["explicit_correlation_assessment"]["verified"]
        for sample in samples
        if sample["explicit_correlation_assessment"] is not None
    ]

    status = "evidence_collected" if samples else "unavailable"

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": CHAIN,
        "status": status,
        "observed_at": observed_at.isoformat(),
        "source": {
            "rpc_url": rpc_url,
            "repository": ORACLE_V2_REPOSITORY,
            "pinned_commit": ORACLE_V2_PINNED_COMMIT,
            "program_id": PROGRAM_ID,
            "state_pda": STATE_PDA,
        },
        "contract": {
            "batch_submit_prices_discriminator_hex": (
                BATCH_SUBMIT_PRICES_DISCRIMINATOR.hex()
            ),
            "source_contract_timestamp_unit": "unix_ms",
            "deployed_binary_source_equivalence_verified": False,
        },
        "correlation_policy": correlation_policy,
        "samples": samples,
        "rejected_transactions": rejected,
        "summary": {
            "history_limit": history_limit,
            "history_rows": len(history),
            "successful_history_rows": len(successful_history),
            "transaction_records": len(transaction_records),
            "decoded_verified_batch_samples": len(samples),
            "candidate_unix_ms_min_difference_ms": (
                min(differences) if differences else None
            ),
            "candidate_unix_ms_max_difference_ms": (
                max(differences) if differences else None
            ),
            "explicit_correlation_policy_configured": correlation_policy[
                "configured"
            ],
            "all_samples_within_explicit_tolerance": (
                all(per_sample_policy_results)
                if per_sample_policy_results
                else None
            ),
            # #277 deliberately did not define how many successful samples are
            # sufficient for deployment-wide unit promotion. Keep this false.
            "timestamp_unit_verified": False,
            "timestamp_unit_sample_sufficiency_policy_defined": False,
            "freshness_verified": False,
            "price_correctness_verified": False,
            "source_independence_verified": False,
            "current_price_use_authorized": False,
            "cmis_provider_promoted": False,
        },
        "warnings": [
            (
                "candidate_unix_ms_difference_ms is raw correlation evidence, "
                "not timestamp-unit verification unless an explicit tolerance "
                "and provenance are supplied."
            ),
            (
                "Even when every sampled correlation passes an explicit "
                "tolerance, deployment-wide timestamp_unit_verified remains "
                "false because #277 defines no sample-sufficiency threshold."
            ),
            (
                "The pinned source contract labels batch timestamps Unix-ms, "
                "but deployed binary equivalence to the pinned source has not "
                "been independently verified."
            ),
            (
                "Timestamp-unit evidence does not prove freshness, price "
                "correctness, upstream source provenance, or source independence."
            ),
        ],
        "promotion": {
            "timestamp_unit_verified": False,
            "freshness_verified": False,
            "current_price_use_authorized": False,
            "cmis_provider_promoted": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        },
        "errors": [],
    }


def _write_output(result: Mapping[str, Any], output_path: str | None):
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rpc-url",
        default=os.getenv("X1_RPC_URL", DEFAULT_X1_RPC_URL),
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=DEFAULT_HISTORY_LIMIT,
    )
    parser.add_argument("--max-difference-ms", type=int)
    parser.add_argument("--tolerance-provenance")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        result = probe_timestamp_unit_evidence(
            rpc_url=args.rpc_url,
            history_limit=args.history_limit,
            max_difference_ms=args.max_difference_ms,
            tolerance_provenance=args.tolerance_provenance,
        )
    except Exception as exc:
        result = {
            "service": SERVICE,
            "version": VERSION,
            "chain": CHAIN,
            "status": "error",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "rpc_url": args.rpc_url,
                "program_id": PROGRAM_ID,
                "state_pda": STATE_PDA,
            },
            "promotion": {
                "timestamp_unit_verified": False,
                "freshness_verified": False,
                "current_price_use_authorized": False,
                "cmis_provider_promoted": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            },
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    _write_output(result, args.output)
    return 0 if result.get("status") == "evidence_collected" else 1


if __name__ == "__main__":
    sys.exit(main())
