"""Exact X1-side binding discovery for the XONE -> XNT evidence track.

This module accepts bounded XONE/XNT web claims, extracts only exact 32-byte
X1/SVM public keys from source text, and optionally qualifies those candidates
with finalized X1 RPC account/history evidence.

The semantic boundary is intentionally strict:
- source text must explicitly contain both XONE and XNT plus binding language;
- XNT-only validator-reward rules are not XONE -> XNT binding evidence;
- account existence, program execution, transfers, or stake lockup state do not
  by themselves prove an XONE -> XNT allocation/claim/vesting/conversion role.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any, Callable, Optional

from .x1_xnt_distribution_mechanism import (
    STAKE_PROGRAM_ID,
    X1XntMechanismDiscoveryError,
    normalize_x1_pubkey,
)


CONTRACT_VERSION = "xone_xnt_x1_binding_discovery/v1"
CHAIN = "x1"
NETWORK = "x1-mainnet"
DISCOVERED = "DISCOVERED"

SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
VOTE_PROGRAM_ID = "Vote111111111111111111111111111111111111111"
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
BPF_UPGRADEABLE_LOADER = "BPFLoaderUpgradeab1e11111111111111111111111"

KNOWN_INFRASTRUCTURE_PROGRAMS = {
    SYSTEM_PROGRAM_ID,
    STAKE_PROGRAM_ID,
    VOTE_PROGRAM_ID,
    COMPUTE_BUDGET_PROGRAM_ID,
    BPF_UPGRADEABLE_LOADER,
}

DEFAULT_HISTORY_LIMIT = 25
MAX_HISTORY_LIMIT = 100
DEFAULT_TRANSACTION_LIMIT = 10
MAX_TRANSACTION_LIMIT = 25

_BINDING_TERMS = (
    "convert",
    "conversion",
    "migrate",
    "migration",
    "burn",
    "redeem",
    "claim",
    "allocation",
    "allocate",
    "distribution",
    "distribute",
    "vest",
    "vesting",
    "unlock",
    "issuance",
    "issue",
    "mint",
    "snapshot",
)

_BASE58_RE = re.compile(
    r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])"
)


class XoneXntX1BindingDiscoveryError(RuntimeError):
    """Raised when X1 binding evidence cannot be processed safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_limit(value: Any, *, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)


def _binding_context(excerpt: str) -> bool:
    lowered = _text(excerpt).casefold()
    return (
        "xone" in lowered
        and "xnt" in lowered
        and any(term in lowered for term in _BINDING_TERMS)
    )


def _extract_pubkeys(excerpt: str) -> list[str]:
    result: list[str] = []
    for match in _BASE58_RE.finditer(_text(excerpt)):
        value = match.group(0)
        try:
            pubkey = normalize_x1_pubkey(value)
        except X1XntMechanismDiscoveryError:
            continue
        if pubkey not in result:
            result.append(pubkey)
    return result


def _candidate_role(pubkey: str) -> str:
    if pubkey in KNOWN_INFRASTRUCTURE_PROGRAMS:
        return "known_x1_infrastructure_program"
    return "unverified_xone_xnt_x1_binding_candidate"


def _source_ref(claim: Mapping[str, Any], *, pubkey: str) -> dict[str, Any]:
    claim_id = _text(claim.get("claim_id"))
    url = _text(claim.get("url"))
    excerpt = _text(claim.get("excerpt"))
    if not claim_id:
        raise XoneXntX1BindingDiscoveryError("claim_id is required")
    if not url:
        raise XoneXntX1BindingDiscoveryError("claim url is required")
    return {
        "claim_id": claim_id,
        "source_id": _text(claim.get("source_id")) or None,
        "source_name": _text(claim.get("source_name")) or None,
        "source_role": _text(claim.get("source_role")) or None,
        "url": url,
        "observed_at": claim.get("observed_at"),
        "excerpt": excerpt,
        "topics": [_text(item) for item in _sequence(claim.get("topics")) if _text(item)],
        "candidate_pubkey": pubkey,
        "explicit_xone_and_xnt_context": (
            "xone" in excerpt.casefold() and "xnt" in excerpt.casefold()
        ),
        "binding_language_present": _binding_context(excerpt),
        "source_binding_verified": False,
    }


def discover_x1_binding_candidates(
    claims: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 50,
) -> dict[str, Any]:
    """Discover exact X1/SVM pubkeys inside explicit XONE/XNT binding claims."""

    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ValueError("claims must be a sequence")
    max_candidates = _positive_limit(
        max_candidates,
        name="max_candidates",
        maximum=100,
    )

    grouped: dict[str, dict[str, Any]] = {}
    ignored_nonbinding_claim_ids: list[str] = []

    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        claim_id = _text(claim.get("claim_id"))
        excerpt = _text(claim.get("excerpt"))
        if not _binding_context(excerpt):
            if claim_id:
                ignored_nonbinding_claim_ids.append(claim_id)
            continue

        for pubkey in _extract_pubkeys(excerpt):
            ref = _source_ref(claim, pubkey=pubkey)
            row = grouped.get(pubkey)
            if row is None:
                role = _candidate_role(pubkey)
                row = {
                    "candidate_id": sha256(
                        f"{CONTRACT_VERSION}|{CHAIN}|{pubkey}".encode("utf-8")
                    ).hexdigest(),
                    "candidate_pubkey": pubkey,
                    "candidate_role": role,
                    "discovery_state": DISCOVERED,
                    "source_claims": [],
                    "source_claim_count": 0,
                    "distinct_source_ids": [],
                    "distinct_source_roles": [],
                    "eligible_for_history_qualification": (
                        role == "unverified_xone_xnt_x1_binding_candidate"
                    ),
                    "source_binding_language_present": True,
                    "source_binding_verified": False,
                    "candidate_role_verified": False,
                    "account_state_verified": False,
                    "bounded_history_verified": False,
                    "x1_binding_identified": False,
                    "xnt_distribution_mechanism_identified": False,
                    "xnt_issuance_verified": False,
                    "xnt_vesting_or_unlock_verified": False,
                    "xone_xnt_conversion_verified": False,
                    "cross_chain_correlation_verified": False,
                    "public_service_promoted": False,
                    "scout_reliance_promoted": False,
                    "execution_authorized": False,
                }
                grouped[pubkey] = row

            existing = {item["claim_id"] for item in row["source_claims"]}
            if ref["claim_id"] not in existing:
                row["source_claims"].append(ref)

    candidates = list(grouped.values())
    for row in candidates:
        row["source_claim_count"] = len(row["source_claims"])
        row["distinct_source_ids"] = sorted(
            {
                item["source_id"]
                for item in row["source_claims"]
                if item.get("source_id")
            }
        )
        row["distinct_source_roles"] = sorted(
            {
                item["source_role"]
                for item in row["source_claims"]
                if item.get("source_role")
            }
        )

    candidates.sort(
        key=lambda row: (
            row["candidate_role"] != "unverified_xone_xnt_x1_binding_candidate",
            -row["source_claim_count"],
            row["candidate_pubkey"],
        )
    )
    candidates = candidates[:max_candidates]

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "candidate_count": len(candidates),
        "history_qualifiable_candidate_count": sum(
            1 for row in candidates if row["eligible_for_history_qualification"]
        ),
        "candidates": candidates,
        "ignored_nonbinding_claim_ids": sorted(set(ignored_nonbinding_claim_ids)),
        "x1_binding_candidate_discovery_verified": True,
        "zero_candidates_mean_only_no_exact_x1_binding_pubkeys_in_supplied_claims":
            len(candidates) == 0,
        "x1_binding_identified": False,
        "xnt_distribution_mechanism_identified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def _nonnegative_int(value: Any, *, field: str, allow_none: bool = False) -> Optional[int]:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise XoneXntX1BindingDiscoveryError(
            f"{field} must be a non-negative integer"
        )
    return value


def _account_key_text(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value
    elif isinstance(value, Mapping):
        candidate = _text(value.get("pubkey"))
    else:
        return None
    if not candidate:
        return None
    try:
        return normalize_x1_pubkey(candidate)
    except X1XntMechanismDiscoveryError:
        return None


def _parse_account_info(result: Any, *, pubkey: str) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise XoneXntX1BindingDiscoveryError(
            "getAccountInfo result must be an object"
        )
    context = result.get("context")
    slot = None
    if isinstance(context, Mapping):
        raw_slot = context.get("slot")
        if raw_slot is not None:
            slot = _nonnegative_int(raw_slot, field="getAccountInfo.context.slot")

    value = result.get("value")
    if value is None:
        return {
            "candidate_pubkey": pubkey,
            "context_slot": slot,
            "account_exists": False,
            "owner": None,
            "executable": None,
            "lamports": None,
            "space": None,
            "parsed_program": None,
            "parsed_type": None,
            "account_state_verified": True,
        }
    if not isinstance(value, Mapping):
        raise XoneXntX1BindingDiscoveryError(
            "getAccountInfo value must be an object or null"
        )

    owner = _text(value.get("owner"))
    if not owner:
        raise XoneXntX1BindingDiscoveryError("account owner is missing")
    try:
        owner = normalize_x1_pubkey(owner)
    except X1XntMechanismDiscoveryError as exc:
        raise XoneXntX1BindingDiscoveryError("account owner is not a valid pubkey") from exc

    executable = value.get("executable")
    if not isinstance(executable, bool):
        raise XoneXntX1BindingDiscoveryError(
            "account executable flag must be boolean"
        )
    lamports = _nonnegative_int(value.get("lamports"), field="account.lamports")
    space = _nonnegative_int(
        value.get("space"),
        field="account.space",
        allow_none=True,
    )

    parsed_program = None
    parsed_type = None
    data = value.get("data")
    if isinstance(data, Mapping):
        parsed_program = _text(data.get("program")) or None
        parsed = data.get("parsed")
        if isinstance(parsed, Mapping):
            parsed_type = _text(parsed.get("type")) or None

    return {
        "candidate_pubkey": pubkey,
        "context_slot": slot,
        "account_exists": True,
        "owner": owner,
        "executable": executable,
        "lamports": lamports,
        "space": space,
        "parsed_program": parsed_program,
        "parsed_type": parsed_type,
        "account_state_verified": True,
    }


def _parse_signature_rows(result: Any, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(result, Sequence) or isinstance(result, (str, bytes, bytearray)):
        raise XoneXntX1BindingDiscoveryError(
            "getSignaturesForAddress result must be a sequence"
        )
    rows: list[dict[str, Any]] = []
    for raw in list(result)[:limit]:
        if not isinstance(raw, Mapping):
            raise XoneXntX1BindingDiscoveryError(
                "getSignaturesForAddress row must be an object"
            )
        signature = _text(raw.get("signature"))
        if not signature:
            raise XoneXntX1BindingDiscoveryError("signature row is missing signature")
        slot = _nonnegative_int(raw.get("slot"), field="signature.slot")
        block_time = raw.get("blockTime")
        if block_time is not None:
            block_time = _nonnegative_int(block_time, field="signature.blockTime")
        rows.append(
            {
                "signature": signature,
                "slot": slot,
                "block_time": block_time,
                "err": raw.get("err"),
                "confirmation_status": _text(raw.get("confirmationStatus")) or None,
            }
        )
    return rows


def _parsed_system_transfer(
    instruction: Mapping[str, Any],
    *,
    candidate_pubkey: str,
    location: str,
) -> Optional[dict[str, Any]]:
    program = _text(instruction.get("program")).casefold()
    program_id = _text(instruction.get("programId"))
    parsed = instruction.get("parsed")
    if program != "system" or not isinstance(parsed, Mapping):
        return None
    if _text(parsed.get("type")).casefold() not in {"transfer", "transferwithseed"}:
        return None
    info = parsed.get("info")
    if not isinstance(info, Mapping):
        return None

    source = _text(info.get("source"))
    destination = _text(info.get("destination"))
    if candidate_pubkey not in {source, destination}:
        return None
    lamports = info.get("lamports")
    if lamports is not None:
        lamports = _nonnegative_int(lamports, field="system_transfer.lamports")

    return {
        "location": location,
        "program": "system",
        "program_id": program_id or SYSTEM_PROGRAM_ID,
        "type": _text(parsed.get("type")),
        "source": source or None,
        "destination": destination or None,
        "lamports": lamports,
        "candidate_is_source": source == candidate_pubkey,
        "candidate_is_destination": destination == candidate_pubkey,
        "native_transfer_observed": True,
        "distribution_role_verified": False,
    }


def _transaction_observation(
    result: Any,
    *,
    signature: str,
    candidate_pubkey: str,
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise XoneXntX1BindingDiscoveryError(
            f"getTransaction returned non-object for {signature}"
        )

    slot = _nonnegative_int(result.get("slot"), field="transaction.slot")
    block_time = result.get("blockTime")
    if block_time is not None:
        block_time = _nonnegative_int(block_time, field="transaction.blockTime")

    transaction = result.get("transaction")
    meta = result.get("meta")
    if not isinstance(transaction, Mapping) or not isinstance(meta, Mapping):
        raise XoneXntX1BindingDiscoveryError(
            "transaction/meta must be objects"
        )
    message = transaction.get("message")
    if not isinstance(message, Mapping):
        raise XoneXntX1BindingDiscoveryError("transaction message must be an object")

    account_keys = [
        key
        for key in (_account_key_text(item) for item in _sequence(message.get("accountKeys")))
        if key
    ]
    candidate_indexes = [
        index for index, key in enumerate(account_keys) if key == candidate_pubkey
    ]

    invoked_program_ids: list[str] = []
    native_transfers: list[dict[str, Any]] = []

    def inspect_instruction(raw: Any, location: str) -> None:
        if not isinstance(raw, Mapping):
            return
        program_id = _text(raw.get("programId"))
        if program_id:
            try:
                program_id = normalize_x1_pubkey(program_id)
            except X1XntMechanismDiscoveryError:
                program_id = None
        if program_id and program_id not in invoked_program_ids:
            invoked_program_ids.append(program_id)
        transfer = _parsed_system_transfer(
            raw,
            candidate_pubkey=candidate_pubkey,
            location=location,
        )
        if transfer is not None:
            native_transfers.append(transfer)

    for index, instruction in enumerate(_sequence(message.get("instructions"))):
        inspect_instruction(instruction, f"outer:{index}")

    inner = meta.get("innerInstructions")
    for group in _sequence(inner):
        if not isinstance(group, Mapping):
            continue
        outer_index = group.get("index")
        for inner_index, instruction in enumerate(_sequence(group.get("instructions"))):
            inspect_instruction(
                instruction,
                f"inner:{outer_index}:{inner_index}",
            )

    balance_delta = None
    pre = meta.get("preBalances")
    post = meta.get("postBalances")
    if (
        candidate_indexes
        and isinstance(pre, Sequence)
        and not isinstance(pre, (str, bytes, bytearray))
        and isinstance(post, Sequence)
        and not isinstance(post, (str, bytes, bytearray))
    ):
        index = candidate_indexes[0]
        if index < len(pre) and index < len(post):
            before = _nonnegative_int(pre[index], field="preBalances[candidate]")
            after = _nonnegative_int(post[index], field="postBalances[candidate]")
            balance_delta = after - before

    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "success": meta.get("err") is None,
        "candidate_referenced_in_account_keys": bool(candidate_indexes),
        "candidate_account_indexes": candidate_indexes,
        "candidate_invoked_as_program": candidate_pubkey in invoked_program_ids,
        "invoked_program_ids": invoked_program_ids,
        "native_system_transfers_involving_candidate": native_transfers,
        "native_system_transfer_count": len(native_transfers),
        "candidate_balance_delta_lamports": balance_delta,
        "candidate_balance_delta_includes_fees_and_other_effects": balance_delta is not None,
        "activity_semantic_role_verified": False,
        "xone_xnt_binding_verified": False,
    }


def qualify_x1_binding_candidate(
    candidate: Mapping[str, Any],
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    transaction_limit: int = DEFAULT_TRANSACTION_LIMIT,
) -> dict[str, Any]:
    """Qualify exact account/history evidence without semantic-role promotion."""

    if not isinstance(candidate, Mapping):
        raise XoneXntX1BindingDiscoveryError("candidate must be a mapping")
    pubkey = normalize_x1_pubkey(candidate.get("candidate_pubkey"))
    role = _text(candidate.get("candidate_role"))
    history_limit = _positive_limit(
        history_limit,
        name="history_limit",
        maximum=MAX_HISTORY_LIMIT,
    )
    transaction_limit = _positive_limit(
        transaction_limit,
        name="transaction_limit",
        maximum=MAX_TRANSACTION_LIMIT,
    )

    if pubkey in KNOWN_INFRASTRUCTURE_PROGRAMS or role == "known_x1_infrastructure_program":
        return {
            "contract_version": CONTRACT_VERSION,
            "chain": CHAIN,
            "network": NETWORK,
            "candidate_pubkey": pubkey,
            "qualification_state": "excluded_known_x1_infrastructure_program",
            "account_state_verified": False,
            "bounded_history_verified": False,
            "x1_binding_identified": False,
            "xnt_distribution_mechanism_identified": False,
            "xnt_issuance_verified": False,
            "xnt_vesting_or_unlock_verified": False,
            "xone_xnt_conversion_verified": False,
            "cross_chain_correlation_verified": False,
            "source_url": source_url,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }

    account = _parse_account_info(
        rpc_call(
            "getAccountInfo",
            [pubkey, {"encoding": "jsonParsed", "commitment": "finalized"}],
        ),
        pubkey=pubkey,
    )

    signatures = _parse_signature_rows(
        rpc_call(
            "getSignaturesForAddress",
            [
                pubkey,
                {
                    "commitment": "finalized",
                    "limit": history_limit,
                },
            ],
        ),
        limit=history_limit,
    )

    successful = [row for row in signatures if row["err"] is None]
    observations: list[dict[str, Any]] = []
    for row in successful[:transaction_limit]:
        tx = rpc_call(
            "getTransaction",
            [
                row["signature"],
                {
                    "encoding": "jsonParsed",
                    "commitment": "finalized",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        if tx is None:
            observations.append(
                {
                    "signature": row["signature"],
                    "slot": row["slot"],
                    "transaction_available": False,
                    "activity_semantic_role_verified": False,
                    "xone_xnt_binding_verified": False,
                }
            )
            continue
        observation = _transaction_observation(
            tx,
            signature=row["signature"],
            candidate_pubkey=pubkey,
        )
        observation["transaction_available"] = True
        observations.append(observation)

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "candidate_pubkey": pubkey,
        "qualification_state": "bounded_history_observed",
        "account": account,
        "account_state_verified": account["account_state_verified"],
        "history_limit": history_limit,
        "signature_count": len(signatures),
        "successful_signature_count": len(successful),
        "transaction_limit": transaction_limit,
        "transaction_observation_count": len(observations),
        "transactions": observations,
        "native_system_transfer_observation_count": sum(
            row.get("native_system_transfer_count", 0)
            for row in observations
            if isinstance(row, Mapping)
        ),
        "candidate_invocation_observation_count": sum(
            1
            for row in observations
            if isinstance(row, Mapping)
            and row.get("candidate_invoked_as_program") is True
        ),
        "bounded_history_verified": True,
        "history_activity_does_not_prove_binding_role": True,
        "source_binding_verified": False,
        "candidate_role_verified": False,
        "x1_binding_identified": False,
        "xnt_distribution_mechanism_identified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "source_url": source_url,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "CONTRACT_VERSION",
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_TRANSACTION_LIMIT",
    "DISCOVERED",
    "KNOWN_INFRASTRUCTURE_PROGRAMS",
    "NETWORK",
    "SYSTEM_PROGRAM_ID",
    "XoneXntX1BindingDiscoveryError",
    "discover_x1_binding_candidates",
    "qualify_x1_binding_candidate",
]
