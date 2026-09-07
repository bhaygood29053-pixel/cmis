"""Ethereum XONE snapshot / registry discovery and deterministic reconstruction.

This module makes no assumption that a holder snapshot occurred at X1 launch,
October 6, a MoonParty date, or any other ecosystem event.  An "official
snapshot" is a separate truth state from a reconstructed holder ledger.

The direct-chain path can rebuild exact XONE balances at a specified historical
Ethereum block from canonical ERC-20 Transfer logs and cross-check the result
against historical totalSupply() and deterministic balanceOf() samples.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .xone_event_observer import (
    TRANSFER_TOPIC,
    ZERO_ADDRESS,
    parse_xone_transfer_log,
)
from .xone_identity import (
    CHAIN,
    CHAIN_ID,
    NETWORK,
    XONE_CONTRACT,
    XONE_DECIMALS,
)


CONTRACT_VERSION = "ethereum_xone_snapshot_registry/v1"
XONE_CREATION_BLOCK = 18_609_736
TOTAL_SUPPLY_SELECTOR = "0x18160ddd"
BALANCE_OF_SELECTOR = "0x70a08231"
DEFAULT_LOG_CHUNK_BLOCKS = 50_000
DEFAULT_BALANCE_SAMPLE_SIZE = 25

_AUTHORITATIVE_SOURCE_ROLES = {
    "faircrypto_source",
    "x1_labs_source",
    "x1_official",
    "jack_levin_direct",
}
_SECONDARY_SOURCE_ROLES = {"x1_report", "secondary_report"}

_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?\b")
_BLOCK_RE = re.compile(
    r"(?i)\b(?:ethereum\s+)?block(?:\s+(?:number|height))?\s*(?:#|:|=)?\s*"
    r"(0x[0-9a-f]+|\d{7,9})\b"
)
_HASH_RE = re.compile(r"0x[a-fA-F0-9]{64}")
_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_URL_RE = re.compile(r"https://[^\s\]\[<>()\"']+|ipfs://[A-Za-z0-9/_\-.]+", re.IGNORECASE)
_SNAPSHOT_TERMS = (
    "snapshot",
    "snapshotted",
    "holder list",
    "holder registry",
    "eligibility list",
    "registry",
)
_XNT_BINDING_TERMS = (
    "xnt",
    "allocation",
    "airdrop",
    "claim",
    "vesting",
    "unlock",
    "distribution",
)


class EthereumXoneSnapshotRegistryError(RuntimeError):
    """Raised when snapshot evidence or reconstruction cannot fail safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _hex_quantity(value: Any, *, field: str) -> int:
    text = _text(value)
    if not text.startswith("0x"):
        raise EthereumXoneSnapshotRegistryError(f"{field} is not a hex quantity")
    try:
        parsed = int(text, 16)
    except ValueError as exc:
        raise EthereumXoneSnapshotRegistryError(f"{field} is malformed") from exc
    if parsed < 0:
        raise EthereumXoneSnapshotRegistryError(f"{field} must be non-negative")
    return parsed


def _hash32(value: Any, *, field: str) -> str:
    text = _text(value).casefold()
    if len(text) != 66 or not text.startswith("0x"):
        raise EthereumXoneSnapshotRegistryError(f"{field} is not a 32-byte hash")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise EthereumXoneSnapshotRegistryError(f"{field} is not hexadecimal") from exc
    return text


def _address(value: Any, *, field: str) -> str:
    text = _text(value).casefold()
    if len(text) != 42 or not text.startswith("0x"):
        raise EthereumXoneSnapshotRegistryError(f"{field} is not a 20-byte address")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise EthereumXoneSnapshotRegistryError(f"{field} is not hexadecimal") from exc
    return text


def _block_number(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise EthereumXoneSnapshotRegistryError(f"{field} must be a block number")
    if isinstance(value, int):
        parsed = value
    else:
        text = _text(value)
        try:
            parsed = int(text, 16 if text.startswith("0x") else 10)
        except ValueError as exc:
            raise EthereumXoneSnapshotRegistryError(f"{field} is invalid") from exc
    if parsed < 0:
        raise EthereumXoneSnapshotRegistryError(f"{field} must be non-negative")
    return parsed


def _decode_uint256(value: Any, *, field: str) -> int:
    text = _text(value)
    if len(text) != 66 or not text.startswith("0x"):
        raise EthereumXoneSnapshotRegistryError(f"{field} must be one ABI uint256 word")
    try:
        return int(text, 16)
    except ValueError as exc:
        raise EthereumXoneSnapshotRegistryError(f"{field} is malformed") from exc


def _balance_of_calldata(address: str) -> str:
    normalized = _address(address, field="balanceOf address")
    return BALANCE_OF_SELECTOR + ("0" * 24) + normalized[2:]


def _format_xone(base_units: int) -> str:
    scale = 10 ** XONE_DECIMALS
    whole, fraction = divmod(base_units, scale)
    if fraction == 0:
        return str(whole)
    return f"{whole}.{fraction:0{XONE_DECIMALS}d}".rstrip("0")


def extract_xone_snapshot_claims(
    text: str,
    *,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    max_claims: int = 50,
) -> list[dict[str, Any]]:
    """Extract explicit XONE snapshot/registry statements from bounded text.

    The extractor is intentionally strict: the same bounded excerpt must mention
    XONE and a snapshot/registry term. XNT/allocation language is preserved as a
    claim attribute but never promoted to direct-chain truth.
    """

    if source_role not in _AUTHORITATIVE_SOURCE_ROLES | _SECONDARY_SOURCE_ROLES:
        raise ValueError(f"unsupported source_role {source_role!r}")
    if isinstance(max_claims, bool) or not isinstance(max_claims, int) or max_claims < 1:
        raise ValueError("max_claims must be a positive integer")

    normalized = re.sub(r"[\t\r ]+", " ", _text(text))
    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+|\n+", normalized)
        if segment.strip()
    ]
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, segment in enumerate(segments):
        lowered = segment.casefold()
        if "xone" not in lowered or not any(term in lowered for term in _SNAPSHOT_TERMS):
            continue

        excerpt_parts = [segment]
        if index > 0 and len(segments[index - 1]) < 700:
            excerpt_parts.insert(0, segments[index - 1])
        if index + 1 < len(segments) and len(segments[index + 1]) < 700:
            excerpt_parts.append(segments[index + 1])
        excerpt = re.sub(r"\s+", " ", " ".join(excerpt_parts)).strip()[:2_200]
        excerpt_lower = excerpt.casefold()

        blocks: list[int] = []
        for match in _BLOCK_RE.finditer(excerpt):
            try:
                block = int(match.group(1), 16 if match.group(1).startswith("0x") else 10)
            except ValueError:
                continue
            if block not in blocks:
                blocks.append(block)

        addresses = []
        for raw in _ADDRESS_RE.findall(excerpt):
            normalized_address = raw.casefold()
            if normalized_address not in addresses:
                addresses.append(normalized_address)

        snapshot_hashes: list[str] = []
        for match in _HASH_RE.finditer(excerpt):
            value = match.group(0).casefold()
            prefix = excerpt_lower[max(0, match.start() - 80):match.start()]
            if any(term in prefix for term in ("merkle", "root", "snapshot", "registry", "block hash")):
                if value not in snapshot_hashes:
                    snapshot_hashes.append(value)

        dates = []
        for regex in (_DATE_RE, _ISO_DATE_RE):
            for match in regex.finditer(excerpt):
                value = match.group(0)
                if value not in dates:
                    dates.append(value)

        urls = []
        for match in _URL_RE.finditer(excerpt):
            value = match.group(0).rstrip(".,;:")
            if value not in urls:
                urls.append(value)

        xnt_binding_claimed = (
            "xnt" in excerpt_lower
            and any(term in excerpt_lower for term in _XNT_BINDING_TERMS)
        )
        exact_xone_contract_mentioned = XONE_CONTRACT in excerpt_lower

        claim_id = sha256(
            f"{CONTRACT_VERSION}|{source_id}|{url}|{excerpt}".encode("utf-8")
        ).hexdigest()
        if claim_id in seen:
            continue
        seen.add(claim_id)

        claims.append(
            {
                "claim_id": claim_id,
                "source_id": _text(source_id),
                "source_role": source_role,
                "url": _text(url),
                "observed_at": observed_at,
                "excerpt": excerpt,
                "authoritative_source": source_role in _AUTHORITATIVE_SOURCE_ROLES,
                "snapshot_block_candidates": blocks,
                "date_candidates": dates,
                "hash_candidates": snapshot_hashes,
                "address_candidates": addresses,
                "artifact_url_candidates": urls,
                "exact_xone_contract_mentioned": exact_xone_contract_mentioned,
                "xnt_allocation_binding_claimed": xnt_binding_claimed,
                "snapshot_source_claim_discovered": True,
                "official_xone_snapshot_verified": False,
                "official_registry_artifact_verified": False,
                "xone_snapshot_eligibility_verified": False,
                "xone_snapshot_xnt_allocation_binding_verified": False,
                "xnt_issuance_verified": False,
                "xnt_vesting_or_unlock_verified": False,
                "october_6_unlock_applies_to_xone_verified": False,
                "xone_xnt_conversion_verified": False,
                "cross_chain_correlation_verified": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            }
        )
        if len(claims) >= max_claims:
            break

    return claims


def discover_official_snapshot_candidates(
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rank source claims that could identify an official XONE snapshot.

    A claim is only eligible for direct-chain reconstruction when an
    authoritative source gives an exact Ethereum block number. It remains a
    candidate until direct reconstruction and source-role checks both pass.
    """

    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ValueError("claims must be a sequence")

    candidates: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        if claim.get("snapshot_source_claim_discovered") is not True:
            continue
        blocks = claim.get("snapshot_block_candidates")
        if not isinstance(blocks, Sequence) or isinstance(blocks, (str, bytes, bytearray)):
            blocks = []
        authoritative = claim.get("authoritative_source") is True

        candidates.append(
            {
                "claim_id": claim.get("claim_id"),
                "source_id": claim.get("source_id"),
                "source_role": claim.get("source_role"),
                "url": claim.get("url"),
                "authoritative_source": authoritative,
                "snapshot_block_candidates": list(blocks),
                "date_candidates": list(claim.get("date_candidates") or []),
                "hash_candidates": list(claim.get("hash_candidates") or []),
                "artifact_url_candidates": list(claim.get("artifact_url_candidates") or []),
                "exact_xone_contract_mentioned":
                    claim.get("exact_xone_contract_mentioned") is True,
                "xnt_allocation_binding_claimed":
                    claim.get("xnt_allocation_binding_claimed") is True,
                "eligible_for_direct_registry_reconstruction":
                    authoritative and len(blocks) == 1,
                "official_xone_snapshot_verified": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            not row["authoritative_source"],
            not row["eligible_for_direct_registry_reconstruction"],
            not row["exact_xone_contract_mentioned"],
            str(row["source_id"]),
            str(row["claim_id"]),
        )
    )

    exact_blocks = sorted(
        {
            int(block)
            for row in candidates
            if row["authoritative_source"]
            for block in row["snapshot_block_candidates"]
        }
    )
    conflicting_authoritative_blocks = len(exact_blocks) > 1

    return {
        "contract_version": CONTRACT_VERSION,
        "official_snapshot_candidate_count": len(candidates),
        "candidates": candidates,
        "authoritative_exact_block_candidates": exact_blocks,
        "authoritative_block_conflict": conflicting_authoritative_blocks,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "zero_candidates_are_scoped_corpus_evidence_only": len(candidates) == 0,
        "zero_candidates_do_not_prove_no_private_snapshot": True,
        "execution_authorized": False,
    }


def _coverage_complete(
    ranges: Sequence[tuple[int, int]],
    *,
    start_block: int,
    end_block: int,
) -> bool:
    if not ranges:
        return False
    normalized = sorted(ranges)
    cursor = start_block
    for start, end in normalized:
        if start != cursor or end < start:
            return False
        cursor = end + 1
    return cursor == end_block + 1


def reconstruct_xone_registry(
    events: Sequence[Mapping[str, Any]],
    *,
    snapshot_block: int,
    snapshot_block_hash: str,
    snapshot_timestamp: int,
    coverage_ranges: Sequence[tuple[int, int]],
    total_supply_base_units: int,
) -> dict[str, Any]:
    """Rebuild exact XONE balances from canonical parsed Transfer events."""

    snapshot_block = _block_number(snapshot_block, field="snapshot_block")
    if snapshot_block < XONE_CREATION_BLOCK:
        raise EthereumXoneSnapshotRegistryError("snapshot block predates XONE creation")
    snapshot_block_hash = _hash32(snapshot_block_hash, field="snapshot_block_hash")
    if (
        isinstance(snapshot_timestamp, bool)
        or not isinstance(snapshot_timestamp, int)
        or snapshot_timestamp < 0
    ):
        raise EthereumXoneSnapshotRegistryError("snapshot_timestamp must be non-negative")
    if (
        isinstance(total_supply_base_units, bool)
        or not isinstance(total_supply_base_units, int)
        or total_supply_base_units < 0
    ):
        raise EthereumXoneSnapshotRegistryError(
            "total_supply_base_units must be non-negative"
        )
    if not _coverage_complete(
        coverage_ranges,
        start_block=XONE_CREATION_BLOCK,
        end_block=snapshot_block,
    ):
        raise EthereumXoneSnapshotRegistryError(
            "Transfer-log coverage is not contiguous from creation through snapshot"
        )

    balances: defaultdict[str, int] = defaultdict(int)
    event_ids: set[str] = set()
    ordered = sorted(
        events,
        key=lambda row: (
            int(row.get("block_number", -1)),
            int(row.get("log_index", -1)),
            str(row.get("transaction_hash", "")),
        ),
    )

    for event in ordered:
        if not isinstance(event, Mapping):
            raise EthereumXoneSnapshotRegistryError("event must be a mapping")
        if event.get("contract_address") != XONE_CONTRACT:
            raise EthereumXoneSnapshotRegistryError("event is not exact XONE")
        event_id = _text(event.get("event_id"))
        if not event_id:
            raise EthereumXoneSnapshotRegistryError("event_id is missing")
        if event_id in event_ids:
            raise EthereumXoneSnapshotRegistryError("duplicate XONE event identity")
        event_ids.add(event_id)

        block_number = event.get("block_number")
        if isinstance(block_number, bool) or not isinstance(block_number, int):
            raise EthereumXoneSnapshotRegistryError("event block_number is invalid")
        if block_number < XONE_CREATION_BLOCK or block_number > snapshot_block:
            raise EthereumXoneSnapshotRegistryError(
                "event falls outside snapshot coverage"
            )

        from_address = _address(event.get("from_address"), field="event from_address")
        to_address = _address(event.get("to_address"), field="event to_address")
        amount_text = _text(event.get("amount_base_units"))
        try:
            amount = int(amount_text, 10)
        except ValueError as exc:
            raise EthereumXoneSnapshotRegistryError(
                "event amount_base_units is invalid"
            ) from exc
        if amount < 0:
            raise EthereumXoneSnapshotRegistryError("event amount cannot be negative")

        if from_address != ZERO_ADDRESS:
            balances[from_address] -= amount
            if balances[from_address] < 0:
                raise EthereumXoneSnapshotRegistryError(
                    f"negative reconstructed balance for {from_address}"
                )
        if to_address != ZERO_ADDRESS:
            balances[to_address] += amount

    registry = [
        {
            "address": address,
            "balance_base_units": str(balance),
            "balance_xone": _format_xone(balance),
        }
        for address, balance in sorted(balances.items())
        if balance > 0
    ]
    reconstructed_supply = sum(
        int(row["balance_base_units"])
        for row in registry
    )
    if reconstructed_supply != total_supply_base_units:
        raise EthereumXoneSnapshotRegistryError(
            "reconstructed holder balances do not equal historical totalSupply"
        )

    canonical_lines = "".join(
        f"{row['address']},{row['balance_base_units']}\n"
        for row in registry
    )
    registry_digest = sha256(canonical_lines.encode("utf-8")).hexdigest()

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "snapshot_block": snapshot_block,
        "snapshot_block_hash": snapshot_block_hash,
        "snapshot_timestamp": snapshot_timestamp,
        "coverage_start_block": XONE_CREATION_BLOCK,
        "coverage_end_block": snapshot_block,
        "coverage_range_count": len(coverage_ranges),
        "transfer_event_count": len(event_ids),
        "holder_count": len(registry),
        "total_supply_base_units": str(total_supply_base_units),
        "total_supply_xone": _format_xone(total_supply_base_units),
        "reconstructed_supply_base_units": str(reconstructed_supply),
        "canonical_registry_format": "lowercase_address,balance_base_units\\n",
        "registry_sha256": registry_digest,
        "registry": registry,
        "reconstructed_registry_verified": True,
        "historical_total_supply_matches": True,
        "historical_balance_sample_verified": False,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


def _deterministic_sample(
    registry: Sequence[Mapping[str, Any]],
    *,
    block_hash: str,
    sample_size: int,
) -> list[Mapping[str, Any]]:
    if sample_size <= 0:
        return []
    ranked = sorted(
        registry,
        key=lambda row: sha256(
            f"{block_hash}|{row['address']}".encode("utf-8")
        ).digest(),
    )
    return ranked[: min(sample_size, len(ranked))]


def fetch_and_verify_xone_registry(
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    snapshot_block: int,
    source_url: Optional[str] = None,
    log_chunk_blocks: int = DEFAULT_LOG_CHUNK_BLOCKS,
    balance_sample_size: int = DEFAULT_BALANCE_SAMPLE_SIZE,
) -> dict[str, Any]:
    """Fetch complete historical XONE logs and verify a registry at one block.

    This function proves the ledger reconstruction at the supplied block. It
    intentionally does not assert that the block is the official XONE snapshot.
    """

    snapshot_block = _block_number(snapshot_block, field="snapshot_block")
    if snapshot_block < XONE_CREATION_BLOCK:
        raise EthereumXoneSnapshotRegistryError("snapshot block predates XONE creation")
    if (
        isinstance(log_chunk_blocks, bool)
        or not isinstance(log_chunk_blocks, int)
        or log_chunk_blocks < 1
    ):
        raise ValueError("log_chunk_blocks must be a positive integer")
    if (
        isinstance(balance_sample_size, bool)
        or not isinstance(balance_sample_size, int)
        or balance_sample_size < 0
    ):
        raise ValueError("balance_sample_size must be a non-negative integer")

    chain_id = _text(rpc_call("eth_chainId", [])).casefold()
    if chain_id != CHAIN_ID:
        raise EthereumXoneSnapshotRegistryError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    header = rpc_call("eth_getBlockByNumber", [hex(snapshot_block), False])
    if not isinstance(header, Mapping):
        raise EthereumXoneSnapshotRegistryError("snapshot block header was not returned")
    header_number = _hex_quantity(header.get("number"), field="snapshot header number")
    if header_number != snapshot_block:
        raise EthereumXoneSnapshotRegistryError("snapshot header number mismatch")
    block_hash = _hash32(header.get("hash"), field="snapshot block hash")
    timestamp = _hex_quantity(header.get("timestamp"), field="snapshot timestamp")

    events: list[dict[str, Any]] = []
    coverage_ranges: list[tuple[int, int]] = []
    start = XONE_CREATION_BLOCK
    while start <= snapshot_block:
        end = min(snapshot_block, start + log_chunk_blocks - 1)
        raw_logs = rpc_call(
            "eth_getLogs",
            [
                {
                    "address": XONE_CONTRACT,
                    "fromBlock": hex(start),
                    "toBlock": hex(end),
                    "topics": [TRANSFER_TOPIC],
                }
            ],
        )
        if not isinstance(raw_logs, Sequence) or isinstance(
            raw_logs, (str, bytes, bytearray)
        ):
            raise EthereumXoneSnapshotRegistryError(
                f"eth_getLogs did not return a list for {start}-{end}"
            )
        for raw in raw_logs:
            if not isinstance(raw, Mapping):
                raise EthereumXoneSnapshotRegistryError("eth_getLogs row is not an object")
            event = parse_xone_transfer_log(raw)
            if event["block_number"] < start or event["block_number"] > end:
                raise EthereumXoneSnapshotRegistryError(
                    "RPC returned XONE log outside requested coverage range"
                )
            events.append(event)
        coverage_ranges.append((start, end))
        start = end + 1

    total_supply = _decode_uint256(
        rpc_call(
            "eth_call",
            [{"to": XONE_CONTRACT, "data": TOTAL_SUPPLY_SELECTOR}, hex(snapshot_block)],
        ),
        field="historical totalSupply",
    )

    proof = reconstruct_xone_registry(
        events,
        snapshot_block=snapshot_block,
        snapshot_block_hash=block_hash,
        snapshot_timestamp=timestamp,
        coverage_ranges=coverage_ranges,
        total_supply_base_units=total_supply,
    )

    sample = _deterministic_sample(
        proof["registry"],
        block_hash=block_hash,
        sample_size=balance_sample_size,
    )
    sample_results: list[dict[str, Any]] = []
    for row in sample:
        historical = _decode_uint256(
            rpc_call(
                "eth_call",
                [
                    {
                        "to": XONE_CONTRACT,
                        "data": _balance_of_calldata(row["address"]),
                    },
                    hex(snapshot_block),
                ],
            ),
            field=f"historical balanceOf({row['address']})",
        )
        expected = int(row["balance_base_units"])
        if historical != expected:
            raise EthereumXoneSnapshotRegistryError(
                f"historical balanceOf mismatch for {row['address']}"
            )
        sample_results.append(
            {
                "address": row["address"],
                "balance_base_units": str(historical),
                "verified": True,
            }
        )

    proof["historical_balance_sample_verified"] = True
    proof["historical_balance_sample_size"] = len(sample_results)
    proof["historical_balance_sample"] = sample_results
    proof["source_url"] = source_url
    return proof


def promote_official_snapshot(
    *,
    source_candidate: Mapping[str, Any],
    registry_proof: Mapping[str, Any],
    official_registry_artifact_verified: bool = False,
    xnt_allocation_binding_verified: bool = False,
) -> dict[str, Any]:
    """Bind an authoritative exact-block claim to a reconstructed registry.

    This is deliberately narrow. A source candidate must be authoritative and
    contain exactly one block that equals the independently reconstructed block.
    XNT allocation remains a separate flag and cannot be inferred from snapshot
    identity alone.
    """

    if source_candidate.get("authoritative_source") is not True:
        raise EthereumXoneSnapshotRegistryError(
            "official snapshot promotion requires an authoritative source"
        )
    blocks = source_candidate.get("snapshot_block_candidates")
    if (
        not isinstance(blocks, Sequence)
        or isinstance(blocks, (str, bytes, bytearray))
        or len(blocks) != 1
    ):
        raise EthereumXoneSnapshotRegistryError(
            "authoritative snapshot source must identify exactly one block"
        )
    source_block = _block_number(blocks[0], field="source snapshot block")
    if registry_proof.get("reconstructed_registry_verified") is not True:
        raise EthereumXoneSnapshotRegistryError(
            "registry must be independently reconstructed and verified"
        )
    registry_block = _block_number(
        registry_proof.get("snapshot_block"),
        field="registry snapshot block",
    )
    if source_block != registry_block:
        raise EthereumXoneSnapshotRegistryError(
            "authoritative source block disagrees with reconstructed registry"
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "snapshot_block": registry_block,
        "snapshot_block_hash": registry_proof.get("snapshot_block_hash"),
        "registry_sha256": registry_proof.get("registry_sha256"),
        "holder_count": registry_proof.get("holder_count"),
        "source_claim_id": source_candidate.get("claim_id"),
        "source_url": source_candidate.get("url"),
        "source_role": source_candidate.get("source_role"),
        "reconstructed_registry_verified": True,
        "official_xone_snapshot_verified": True,
        "official_registry_artifact_verified":
            bool(official_registry_artifact_verified),
        "xone_snapshot_eligibility_verified": True,
        "xone_snapshot_xnt_allocation_binding_verified":
            bool(xnt_allocation_binding_verified),
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "BALANCE_OF_SELECTOR",
    "CONTRACT_VERSION",
    "DEFAULT_BALANCE_SAMPLE_SIZE",
    "DEFAULT_LOG_CHUNK_BLOCKS",
    "EthereumXoneSnapshotRegistryError",
    "TOTAL_SUPPLY_SELECTOR",
    "XONE_CREATION_BLOCK",
    "discover_official_snapshot_candidates",
    "extract_xone_snapshot_claims",
    "fetch_and_verify_xone_registry",
    "promote_official_snapshot",
    "reconstruct_xone_registry",
]
