"""Bounded direct-RPC observer for canonical Ethereum XONE ERC-20 events.

The observer is anchored to the exact XONE identity accepted under
ethereum_xone_identity/v1. It parses only canonical ERC-20
Transfer(address,address,uint256) logs emitted by that exact contract.

A transfer to the zero address is a directly observed XONE burn. A transfer to
a contract address is only a contract-recipient candidate; it does not prove a
lock, bridge, migration, deposit, snapshot, claim, or any X1-side consequence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .xone_identity import (
    CHAIN,
    CHAIN_ID,
    NETWORK,
    XONE_CONTRACT,
    XONE_DECIMALS,
)


CONTRACT_VERSION = "ethereum_xone_event_observer/v1"
TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa"
    "952ba7f163c4a11628f55a4df523b3ef"
)
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_MAX_BLOCKS = 5_000
DEFAULT_MAX_EVENTS = 2_000


class EthereumXoneEventError(RuntimeError):
    """Raised when bounded XONE event evidence cannot be verified safely."""


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _hex_hash(value: Any, *, field: str) -> str:
    text = _text(value)
    if text is None:
        raise EthereumXoneEventError(f"{field} is missing")
    lowered = text.casefold()
    if len(lowered) != 66 or not lowered.startswith("0x"):
        raise EthereumXoneEventError(f"{field} is not a 32-byte hash")
    try:
        int(lowered[2:], 16)
    except ValueError as exc:
        raise EthereumXoneEventError(f"{field} is not hexadecimal") from exc
    return lowered


def _address(value: Any, *, field: str) -> str:
    text = _text(value)
    if text is None:
        raise EthereumXoneEventError(f"{field} is missing")
    lowered = text.casefold()
    if len(lowered) != 42 or not lowered.startswith("0x"):
        raise EthereumXoneEventError(f"{field} is not a 20-byte address")
    try:
        int(lowered[2:], 16)
    except ValueError as exc:
        raise EthereumXoneEventError(f"{field} is not hexadecimal") from exc
    return lowered


def _topic_address(value: Any, *, field: str) -> str:
    topic = _hex_hash(value, field=field)
    payload = topic[2:]
    if payload[:24] != "0" * 24:
        raise EthereumXoneEventError(f"{field} is not a canonical indexed address")
    return "0x" + payload[-40:]


def _hex_quantity(value: Any, *, field: str) -> int:
    text = _text(value)
    if text is None or not text.startswith("0x"):
        raise EthereumXoneEventError(f"{field} is not a hex quantity")
    try:
        parsed = int(text, 16)
    except ValueError as exc:
        raise EthereumXoneEventError(f"{field} is malformed") from exc
    if parsed < 0:
        raise EthereumXoneEventError(f"{field} must be non-negative")
    return parsed


def _block_number(value: int | str, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer or hex quantity")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field} must not be empty")
        try:
            parsed = int(text, 16 if text.startswith("0x") else 10)
        except ValueError as exc:
            raise ValueError(f"{field} is invalid") from exc
    else:
        raise ValueError(f"{field} must be an integer or hex quantity")
    if parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def _format_units(value: int, decimals: int = XONE_DECIMALS) -> str:
    scale = 10 ** decimals
    whole, fractional = divmod(value, scale)
    if fractional == 0:
        return str(whole)
    return f"{whole}.{fractional:0{decimals}d}".rstrip("0")


def _event_truth(*, event_type: str) -> dict[str, Any]:
    return {
        "ethereum_event_verified": True,
        "xone_transfer_verified": True,
        "xone_burn_verified": event_type == "burn",
        "xone_mint_verified": event_type == "mint",
        "lock_or_migration_verified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


def parse_xone_transfer_log(
    log: Mapping[str, Any],
    *,
    block_timestamp: Optional[int] = None,
    recipient_current_code_present: Optional[bool] = None,
) -> dict[str, Any]:
    """Parse one canonical XONE Transfer log and fail closed on ambiguity."""

    if not isinstance(log, Mapping):
        raise EthereumXoneEventError("log must be a mapping")
    if log.get("removed") is True:
        raise EthereumXoneEventError("removed/reorged logs are not accepted")

    emitter = _address(log.get("address"), field="log address")
    if emitter != XONE_CONTRACT:
        raise EthereumXoneEventError("log emitter is not the exact XONE contract")

    topics = log.get("topics")
    if (
        not isinstance(topics, Sequence)
        or isinstance(topics, (str, bytes, bytearray))
        or len(topics) != 3
    ):
        raise EthereumXoneEventError("Transfer log must contain exactly three topics")

    topic0 = _hex_hash(topics[0], field="topic0")
    if topic0 != TRANSFER_TOPIC:
        raise EthereumXoneEventError("log topic0 is not ERC-20 Transfer")

    from_address = _topic_address(topics[1], field="from topic")
    to_address = _topic_address(topics[2], field="to topic")
    if from_address == ZERO_ADDRESS and to_address == ZERO_ADDRESS:
        raise EthereumXoneEventError("zero->zero Transfer is semantically ambiguous")

    data = _text(log.get("data"))
    if data is None or not data.startswith("0x") or len(data) != 66:
        raise EthereumXoneEventError("Transfer data must be exactly one 32-byte uint256")
    try:
        amount_raw = int(data, 16)
    except ValueError as exc:
        raise EthereumXoneEventError("Transfer data is malformed") from exc

    tx_hash = _hex_hash(log.get("transactionHash"), field="transactionHash")
    block_hash = _hex_hash(log.get("blockHash"), field="blockHash")
    block_number = _hex_quantity(log.get("blockNumber"), field="blockNumber")
    log_index = _hex_quantity(log.get("logIndex"), field="logIndex")

    if block_timestamp is not None:
        if isinstance(block_timestamp, bool) or not isinstance(block_timestamp, int):
            raise EthereumXoneEventError("block_timestamp must be an integer")
        if block_timestamp < 0:
            raise EthereumXoneEventError("block_timestamp must be non-negative")

    if to_address == ZERO_ADDRESS:
        event_type = "burn"
    elif from_address == ZERO_ADDRESS:
        event_type = "mint"
    else:
        event_type = "transfer"

    event_key = f"{CHAIN}|{XONE_CONTRACT}|{tx_hash}|{log_index}"
    event_id = sha256(event_key.encode("utf-8")).hexdigest()

    contract_candidate: Optional[bool]
    if to_address == ZERO_ADDRESS:
        contract_candidate = False
    else:
        contract_candidate = recipient_current_code_present

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "transfer_topic": TRANSFER_TOPIC,
        "event_id": event_id,
        "event_type": event_type,
        "transaction_hash": tx_hash,
        "block_hash": block_hash,
        "block_number": block_number,
        "block_number_hex": hex(block_number),
        "block_timestamp": block_timestamp,
        "log_index": log_index,
        "from_address": from_address,
        "to_address": to_address,
        "amount_base_units": str(amount_raw),
        "amount_xone": _format_units(amount_raw),
        "decimals": XONE_DECIMALS,
        "recipient_current_code_present": contract_candidate,
        "contract_recipient_candidate": contract_candidate is True,
        "lock_or_migration_candidate": contract_candidate is True,
        "read_only": True,
        **_event_truth(event_type=event_type),
    }


def observe_xone_transfer_events(
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    from_block: int | str,
    to_block: int | str,
    source_url: Optional[str] = None,
    max_blocks: int = DEFAULT_MAX_BLOCKS,
    max_events: int = DEFAULT_MAX_EVENTS,
    enrich_recipient_code: bool = False,
) -> dict[str, Any]:
    """Observe one bounded block window for exact XONE Transfer events."""

    start = _block_number(from_block, field="from_block")
    end = _block_number(to_block, field="to_block")
    if end < start:
        raise ValueError("to_block must be greater than or equal to from_block")
    if isinstance(max_blocks, bool) or not isinstance(max_blocks, int) or max_blocks < 1:
        raise ValueError("max_blocks must be a positive integer")
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("max_events must be a positive integer")
    block_count = end - start + 1
    if block_count > max_blocks:
        raise EthereumXoneEventError(
            f"requested window has {block_count} blocks; paginate at <= {max_blocks}"
        )

    chain_id = _text(rpc_call("eth_chainId", []))
    if chain_id is None or chain_id.casefold() != CHAIN_ID:
        raise EthereumXoneEventError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    query = {
        "address": XONE_CONTRACT,
        "fromBlock": hex(start),
        "toBlock": hex(end),
        "topics": [TRANSFER_TOPIC],
    }
    raw_logs = rpc_call("eth_getLogs", [query])
    if not isinstance(raw_logs, Sequence) or isinstance(
        raw_logs, (str, bytes, bytearray)
    ):
        raise EthereumXoneEventError("eth_getLogs did not return a list")
    if len(raw_logs) > max_events:
        raise EthereumXoneEventError(
            f"window returned {len(raw_logs)} events; paginate at <= {max_events} events"
        )

    block_timestamps: dict[int, int] = {}
    recipient_code: dict[str, Optional[bool]] = {}
    events: list[dict[str, Any]] = []

    def block_timestamp(block_number: int) -> int:
        cached = block_timestamps.get(block_number)
        if cached is not None:
            return cached
        header = rpc_call("eth_getBlockByNumber", [hex(block_number), False])
        if not isinstance(header, Mapping):
            raise EthereumXoneEventError(
                f"block header {hex(block_number)} was not returned"
            )
        header_number = _hex_quantity(header.get("number"), field="header number")
        if header_number != block_number:
            raise EthereumXoneEventError("block header number mismatch")
        timestamp = _hex_quantity(header.get("timestamp"), field="block timestamp")
        block_timestamps[block_number] = timestamp
        return timestamp

    for raw in raw_logs:
        if not isinstance(raw, Mapping):
            raise EthereumXoneEventError("each eth_getLogs row must be an object")
        block_number = _hex_quantity(raw.get("blockNumber"), field="blockNumber")
        if block_number < start or block_number > end:
            raise EthereumXoneEventError("RPC returned log outside requested block window")

        to_address: Optional[str] = None
        code_present: Optional[bool] = None
        topics = raw.get("topics")
        if (
            enrich_recipient_code
            and isinstance(topics, Sequence)
            and not isinstance(topics, (str, bytes, bytearray))
            and len(topics) == 3
        ):
            try:
                to_address = _topic_address(topics[2], field="to topic")
            except EthereumXoneEventError:
                to_address = None
            if to_address and to_address != ZERO_ADDRESS:
                if to_address not in recipient_code:
                    try:
                        code = _text(rpc_call("eth_getCode", [to_address, "finalized"]))
                        if code is None or not code.startswith("0x"):
                            recipient_code[to_address] = None
                        else:
                            recipient_code[to_address] = len(code) > 2
                    except Exception:
                        recipient_code[to_address] = None
                code_present = recipient_code[to_address]

        event = parse_xone_transfer_log(
            raw,
            block_timestamp=block_timestamp(block_number),
            recipient_current_code_present=code_present,
        )
        events.append(event)

    events.sort(
        key=lambda event: (
            event["block_number"],
            event["log_index"],
            event["transaction_hash"],
        )
    )

    event_ids = [event["event_id"] for event in events]
    burn_count = sum(1 for event in events if event["event_type"] == "burn")
    mint_count = sum(1 for event in events if event["event_type"] == "mint")
    transfer_count = sum(1 for event in events if event["event_type"] == "transfer")
    contract_candidate_count = sum(
        1 for event in events if event["contract_recipient_candidate"]
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "transfer_topic": TRANSFER_TOPIC,
        "from_block": start,
        "to_block": end,
        "block_count": block_count,
        "event_count": len(events),
        "burn_count": burn_count,
        "mint_count": mint_count,
        "transfer_count": transfer_count,
        "contract_recipient_candidate_count": contract_candidate_count,
        "event_ids": event_ids,
        "events": events,
        "source_url": source_url,
        "ethereum_log_window_verified": True,
        "ethereum_event_verified": bool(events),
        "xone_burn_verified": burn_count > 0,
        "lock_or_migration_verified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "lifetime_activity_complete": False,
        "zero_events_mean_only_no_matching_logs_in_window": len(events) == 0,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


def _canonical_event_view(event: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        event.get("event_id"),
        event.get("event_type"),
        event.get("transaction_hash"),
        event.get("block_hash"),
        event.get("block_number"),
        event.get("block_timestamp"),
        event.get("log_index"),
        event.get("from_address"),
        event.get("to_address"),
        event.get("amount_base_units"),
    )


def corroborate_xone_event_observations(
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require matching bounded XONE event observations from distinct transports."""

    if not isinstance(observations, Sequence) or isinstance(
        observations, (str, bytes, bytearray)
    ):
        raise EthereumXoneEventError("observations must be a sequence")
    if len(observations) < 2:
        raise EthereumXoneEventError("at least two RPC observations are required")

    hosts: set[str] = set()
    normalized: list[Mapping[str, Any]] = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise EthereumXoneEventError("each observation must be a mapping")
        if observation.get("ethereum_log_window_verified") is not True:
            raise EthereumXoneEventError("all observations must verify their log window")
        if observation.get("contract_address") != XONE_CONTRACT:
            raise EthereumXoneEventError("observation contract address mismatch")
        source_url = _text(observation.get("source_url"))
        if not source_url:
            raise EthereumXoneEventError("each observation requires source_url")
        host = (urlparse(source_url).hostname or "").casefold()
        if not host:
            raise EthereumXoneEventError("observation source_url is invalid")
        hosts.add(host)
        normalized.append(observation)

    if len(hosts) < 2:
        raise EthereumXoneEventError("two distinct RPC transport hosts are required")

    baseline = normalized[0]
    baseline_window = (baseline.get("from_block"), baseline.get("to_block"))
    baseline_events = tuple(
        _canonical_event_view(event)
        for event in baseline.get("events", [])
        if isinstance(event, Mapping)
    )

    for observation in normalized[1:]:
        if (observation.get("from_block"), observation.get("to_block")) != baseline_window:
            raise EthereumXoneEventError("RPC observations disagree on block window")
        events = observation.get("events")
        if not isinstance(events, Sequence) or isinstance(events, (str, bytes, bytearray)):
            raise EthereumXoneEventError("observation events must be a list")
        canonical = tuple(
            _canonical_event_view(event)
            for event in events
            if isinstance(event, Mapping)
        )
        if canonical != baseline_events:
            raise EthereumXoneEventError("RPC observations disagree on canonical events")

    events = [dict(event) for event in baseline.get("events", [])]
    burn_count = sum(1 for event in events if event.get("event_type") == "burn")
    mint_count = sum(1 for event in events if event.get("event_type") == "mint")
    transfer_count = sum(1 for event in events if event.get("event_type") == "transfer")

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "transfer_topic": TRANSFER_TOPIC,
        "from_block": baseline["from_block"],
        "to_block": baseline["to_block"],
        "event_count": len(events),
        "burn_count": burn_count,
        "mint_count": mint_count,
        "transfer_count": transfer_count,
        "event_ids": [event["event_id"] for event in events],
        "events": events,
        "rpc_proof_count": len(normalized),
        "rpc_transport_hosts": sorted(hosts),
        "multi_rpc_corroborated": True,
        "transport_provider_diversity_verified": True,
        "rpc_backend_source_independence_verified": False,
        "same_chain_consensus_is_not_cross_source_semantic_independence": True,
        "ethereum_log_window_verified": True,
        "ethereum_event_verified": bool(events),
        "xone_burn_verified": burn_count > 0,
        "lock_or_migration_verified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "lifetime_activity_complete": False,
        "matching_zero_event_window": len(events) == 0,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_MAX_BLOCKS",
    "DEFAULT_MAX_EVENTS",
    "EthereumXoneEventError",
    "TRANSFER_TOPIC",
    "ZERO_ADDRESS",
    "corroborate_xone_event_observations",
    "observe_xone_transfer_events",
    "parse_xone_transfer_log",
]
