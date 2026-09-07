"""Bounded XONE/XNT conversion candidate discovery.

This layer turns exact Ethereum addresses already present in bounded XONE/XNT
web claims into reviewable candidates. It does not search arbitrary addresses,
does not infer roles from labels, and never promotes a candidate to verified
XONE -> XNT migration truth.

Candidate scoring is deterministic triage only.  Ethereum qualification can
establish code presence and IBurnRedeemable technical compatibility, but that
still does not prove a conversion/migration role or any X1-side XNT issuance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any, Callable, Optional

from liquidity_scout.providers.ethereum.xone_identity import (
    CHAIN_ID,
    XONE_CONTRACT,
    XONE_DEPLOYER,
)
from liquidity_scout.providers.ethereum.xone_migration_sink_semantics import (
    EthereumXoneMigrationSemanticsError,
    verify_burn_redeemer_candidate,
)


CONTRACT_VERSION = "xone_xnt_conversion_candidate_discovery/v1"
DISCOVERED = "DISCOVERED"

_CONTEXT_TOPICS = {
    "conversion": 10,
    "contract": 7,
    "burn": 6,
    "claim": 5,
    "cross_chain": 4,
    "lockup": 3,
    "vesting": 3,
    "distribution": 2,
}
_CONTEXT_TERMS = (
    "convert",
    "conversion",
    "migrate",
    "migration",
    "redeem",
    "burn",
    "contract",
    "bridge",
    "claim",
)


class XoneXntCandidateDiscoveryError(RuntimeError):
    """Raised when candidate records are malformed or unsafe."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _address(value: Any, *, field: str) -> str:
    text = _text(value).casefold()
    if len(text) != 42 or not text.startswith("0x"):
        raise XoneXntCandidateDiscoveryError(f"{field} is not a 20-byte address")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise XoneXntCandidateDiscoveryError(f"{field} is not hexadecimal") from exc
    return text


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)


def _claim_addresses(claim: Mapping[str, Any]) -> list[str]:
    values = claim.get("normalized_values")
    if not isinstance(values, Mapping):
        return []
    raw = _sequence(values.get("ethereum_addresses"))
    result: list[str] = []
    for value in raw:
        try:
            address = _address(value, field="claim Ethereum address")
        except XoneXntCandidateDiscoveryError:
            continue
        if address not in result:
            result.append(address)
    return result


def _claim_topics(claim: Mapping[str, Any]) -> list[str]:
    return [
        _text(item).casefold()
        for item in _sequence(claim.get("topics"))
        if _text(item)
    ]


def _has_candidate_context(claim: Mapping[str, Any]) -> bool:
    topics = set(_claim_topics(claim))
    if topics & set(_CONTEXT_TOPICS):
        return True
    excerpt = _text(claim.get("excerpt")).casefold()
    return any(term in excerpt for term in _CONTEXT_TERMS)


def _candidate_role(address: str) -> str:
    if address == XONE_CONTRACT:
        return "exact_xone_token_contract"
    if address == XONE_DEPLOYER:
        return "exact_xone_deployer"
    return "unverified_conversion_candidate"


def _candidate_score(claim: Mapping[str, Any], address: str) -> int:
    topics = set(_claim_topics(claim))
    score = sum(weight for topic, weight in _CONTEXT_TOPICS.items() if topic in topics)
    excerpt = _text(claim.get("excerpt")).casefold()
    if "xone" in excerpt and "xnt" in excerpt:
        score += 5
    if address in excerpt:
        score += 4
    if any(term in excerpt for term in ("1:1", "ratio", "convert", "migration")):
        score += 3
    role = _candidate_role(address)
    if role != "unverified_conversion_candidate":
        score = max(0, score - 10)
    return score


def _source_ref(claim: Mapping[str, Any], address: str) -> dict[str, Any]:
    claim_id = _text(claim.get("claim_id"))
    if not claim_id:
        raise XoneXntCandidateDiscoveryError("claim_id is required")
    url = _text(claim.get("url"))
    if not url:
        raise XoneXntCandidateDiscoveryError("claim url is required")
    return {
        "claim_id": claim_id,
        "source_id": _text(claim.get("source_id")) or None,
        "source_name": _text(claim.get("source_name")) or None,
        "source_role": _text(claim.get("source_role")) or None,
        "url": url,
        "observed_at": claim.get("observed_at"),
        "excerpt": _text(claim.get("excerpt")),
        "topics": _claim_topics(claim),
        "address_mentioned": address,
        "web_claim_verified": False,
    }


def discover_conversion_candidates(
    claims: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 50,
) -> dict[str, Any]:
    """Discover exact-address candidates from already-bounded XONE/XNT claims."""

    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ValueError("claims must be a sequence")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")

    grouped: dict[str, dict[str, Any]] = {}
    ignored_claim_ids: list[str] = []

    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        claim_id = _text(claim.get("claim_id"))
        if not _has_candidate_context(claim):
            if claim_id:
                ignored_claim_ids.append(claim_id)
            continue

        addresses = _claim_addresses(claim)
        if not addresses:
            continue

        for address in addresses:
            ref = _source_ref(claim, address)
            score = _candidate_score(claim, address)
            row = grouped.get(address)
            if row is None:
                candidate_id = sha256(
                    f"{CONTRACT_VERSION}|ethereum|{address}".encode("utf-8")
                ).hexdigest()
                row = {
                    "candidate_id": candidate_id,
                    "candidate_address": address,
                    "candidate_role": _candidate_role(address),
                    "discovery_state": DISCOVERED,
                    "relevance_score": score,
                    "source_claims": [],
                    "source_claim_count": 0,
                    "distinct_source_ids": [],
                    "exact_xone_token_contract": address == XONE_CONTRACT,
                    "exact_xone_deployer": address == XONE_DEPLOYER,
                    "eligible_for_ethereum_qualification": (
                        address not in {XONE_CONTRACT, XONE_DEPLOYER}
                    ),
                    "candidate_role_verified": False,
                    "web_claim_verified": False,
                    "burn_redeemer_interface_verified": False,
                    "migration_sink_identified": False,
                    "lock_or_migration_verified": False,
                    "xone_xnt_conversion_verified": False,
                    "xnt_issuance_verified": False,
                    "cross_chain_correlation_verified": False,
                    "public_service_promoted": False,
                    "scout_reliance_promoted": False,
                    "execution_authorized": False,
                }
                grouped[address] = row
            else:
                row["relevance_score"] = max(row["relevance_score"], score)

            if ref["claim_id"] not in {
                item["claim_id"] for item in row["source_claims"]
            }:
                row["source_claims"].append(ref)

    candidates = list(grouped.values())
    for row in candidates:
        row["source_claim_count"] = len(row["source_claims"])
        row["distinct_source_ids"] = sorted({
            item["source_id"]
            for item in row["source_claims"]
            if item.get("source_id")
        })
    candidates.sort(
        key=lambda row: (
            row["candidate_role"] != "unverified_conversion_candidate",
            -row["relevance_score"],
            row["candidate_address"],
        )
    )
    candidates = candidates[:max_candidates]

    return {
        "contract_version": CONTRACT_VERSION,
        "candidate_count": len(candidates),
        "qualifiable_candidate_count": sum(
            1 for row in candidates if row["eligible_for_ethereum_qualification"]
        ),
        "candidates": candidates,
        "ignored_noncontext_claim_ids": sorted(set(ignored_claim_ids)),
        "zero_candidates_mean_only_no_exact_address_candidates_in_supplied_claims":
            len(candidates) == 0,
        "web_claim_verified": False,
        "migration_sink_identified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def qualify_conversion_candidate(
    candidate: Mapping[str, Any],
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
) -> dict[str, Any]:
    """Qualify one discovered candidate without promoting its semantic role."""

    if not isinstance(candidate, Mapping):
        raise XoneXntCandidateDiscoveryError("candidate must be a mapping")
    address = _address(candidate.get("candidate_address"), field="candidate address")
    role = _text(candidate.get("candidate_role"))

    if address == XONE_CONTRACT or role == "exact_xone_token_contract":
        return {
            "contract_version": CONTRACT_VERSION,
            "candidate_address": address,
            "qualification_state": "excluded_known_xone_token_contract",
            "ethereum_chain_id_verified": False,
            "runtime_code_present": True,
            "burn_redeemer_interface_verified": False,
            "migration_sink_identified": False,
            "xone_xnt_conversion_verified": False,
            "execution_authorized": False,
        }
    if address == XONE_DEPLOYER or role == "exact_xone_deployer":
        return {
            "contract_version": CONTRACT_VERSION,
            "candidate_address": address,
            "qualification_state": "excluded_known_xone_deployer",
            "ethereum_chain_id_verified": False,
            "runtime_code_present": None,
            "burn_redeemer_interface_verified": False,
            "migration_sink_identified": False,
            "xone_xnt_conversion_verified": False,
            "execution_authorized": False,
        }

    chain_id = _text(rpc_call("eth_chainId", []))
    if chain_id.casefold() != CHAIN_ID:
        raise XoneXntCandidateDiscoveryError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    raw_code = _text(rpc_call("eth_getCode", [address, "finalized"]))
    if not raw_code.startswith("0x"):
        raise XoneXntCandidateDiscoveryError("candidate eth_getCode result is malformed")
    code_present = len(raw_code) > 2

    if not code_present:
        return {
            "contract_version": CONTRACT_VERSION,
            "candidate_address": address,
            "qualification_state": "no_runtime_bytecode",
            "ethereum_chain_id_verified": True,
            "runtime_code_present": False,
            "burn_redeemer_interface_verified": False,
            "interface_query_available": False,
            "migration_sink_identified": False,
            "lock_or_migration_verified": False,
            "xone_xnt_conversion_verified": False,
            "xnt_issuance_verified": False,
            "cross_chain_correlation_verified": False,
            "source_url": source_url,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }

    try:
        proof = verify_burn_redeemer_candidate(
            address,
            rpc_call=rpc_call,
            source_url=source_url,
        )
    except EthereumXoneMigrationSemanticsError as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "candidate_address": address,
            "qualification_state": "contract_interface_unverified",
            "ethereum_chain_id_verified": True,
            "runtime_code_present": True,
            "burn_redeemer_interface_verified": False,
            "interface_query_available": False,
            "interface_query_error": str(exc),
            "migration_sink_identified": False,
            "lock_or_migration_verified": False,
            "xone_xnt_conversion_verified": False,
            "xnt_issuance_verified": False,
            "cross_chain_correlation_verified": False,
            "source_url": source_url,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }

    return {
        "contract_version": CONTRACT_VERSION,
        "candidate_address": address,
        "qualification_state": (
            "iburnredeemable_compatible_contract"
            if proof["burn_redeemer_interface_verified"]
            else "contract_without_iburnredeemable_support"
        ),
        "ethereum_chain_id_verified": True,
        "runtime_code_present": True,
        "burn_redeemer_interface_verified":
            proof["burn_redeemer_interface_verified"],
        "interface_query_available": True,
        "redeemer_proof": proof,
        "migration_sink_identified": False,
        "lock_or_migration_verified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "source_url": source_url,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DISCOVERED",
    "XoneXntCandidateDiscoveryError",
    "discover_conversion_candidates",
    "qualify_conversion_candidate",
]
