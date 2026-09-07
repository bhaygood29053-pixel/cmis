"""X1 Agents Radio -> X1 RPC direct-chain corroboration.

This contract accepts one bounded X1 Agents Radio program/deployment candidate
and asks canonical X1 RPC only for facts that RPC can actually prove.

Direct-chain RPC can corroborate the exact queried address, current account
existence, executable state, current owner/loader, bounded finalized address
history, and (for a provider-reported deployment/upgrade slot) successful
activity for the exact address at that slot.

It does not verify Radio names, categories, frameworks, descriptions,
instruction semantics, activity-count completeness, or deployment-vs-upgrade
semantics. Agreement with RPC is not source-independence proof.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from .rpc import rpc_request


CONTRACT_VERSION = "x1_agents_radio_rpc_corroboration/v1"
CHAIN = "x1"
NETWORK = "x1-mainnet"
RADIO_SOURCE = "x1agentsradio.xyz"
DEFAULT_HISTORY_LIMIT = 25
MAX_HISTORY_LIMIT = 100

PROGRAM_CANDIDATE = "program_candidate"
DEPLOYMENT_CANDIDATE = "deployment_candidate"

PROGRAM_ACCOUNT_CORROBORATED = "PROGRAM_ACCOUNT_CORROBORATED"
REPORTED_SLOT_ACTIVITY_CORROBORATED = "REPORTED_SLOT_ACTIVITY_CORROBORATED"
ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
ACCOUNT_NOT_EXECUTABLE = "ACCOUNT_NOT_EXECUTABLE"
EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"


class X1AgentsRadioRPCCorroborationError(ValueError):
    """Raised when a Radio candidate or RPC result cannot be used safely."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _base58_decoded_length(value: str) -> int | None:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    index = {char: position for position, char in enumerate(alphabet)}
    text = _text(value)
    if text is None:
        return None

    number = 0
    leading_zeros = 0
    for position, char in enumerate(text):
        digit = index.get(char)
        if digit is None:
            return None
        if position == leading_zeros and char == "1":
            leading_zeros += 1
        number = number * 58 + digit

    payload_length = (number.bit_length() + 7) // 8 if number else 0
    return leading_zeros + payload_length


def _history_limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise X1AgentsRadioRPCCorroborationError(
            "history_limit must be an integer"
        )
    if value < 1 or value > MAX_HISTORY_LIMIT:
        raise X1AgentsRadioRPCCorroborationError(
            f"history_limit must be between 1 and {MAX_HISTORY_LIMIT}"
        )
    return value


def _candidate_type(candidate: Mapping[str, Any]) -> str:
    explicit = _text(candidate.get("record_type"))
    if explicit in {PROGRAM_CANDIDATE, DEPLOYMENT_CANDIDATE}:
        return explicit

    if (
        _text(candidate.get("event_type"))
        or _nonnegative_int(candidate.get("slot")) is not None
        or isinstance(candidate.get("provider_deployment"), Mapping)
    ):
        return DEPLOYMENT_CANDIDATE

    return PROGRAM_CANDIDATE


def _provider_deployment(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    value = candidate.get("provider_deployment")
    return value if isinstance(value, Mapping) else {}


def _reported_slot(candidate: Mapping[str, Any]) -> int | None:
    direct = _nonnegative_int(candidate.get("slot"))
    if direct is not None:
        return direct

    deployment = _provider_deployment(candidate)
    upgrade = _nonnegative_int(deployment.get("upgrade_slot"))
    if upgrade is not None:
        return upgrade
    return _nonnegative_int(deployment.get("deployment_slot"))


def _reported_event_type(candidate: Mapping[str, Any]) -> str | None:
    direct = _text(candidate.get("event_type"))
    if direct:
        return direct.casefold()
    nested = _text(_provider_deployment(candidate).get("event_type"))
    return nested.casefold() if nested else None


def _reported_transaction_signature(candidate: Mapping[str, Any]) -> str | None:
    direct = _text(candidate.get("transaction_signature"))
    if direct:
        return direct

    deployment = _provider_deployment(candidate)
    nested = _text(deployment.get("transaction_signature"))
    if nested:
        return nested

    raw = candidate.get("raw")
    if isinstance(raw, Mapping):
        return (
            _text(raw.get("transaction_signature"))
            or _text(raw.get("tx_signature"))
            or _text(raw.get("signature"))
        )
    return None


def _provider_claim(candidate: Mapping[str, Any], direct: str, structured: str) -> Any:
    if direct in candidate:
        return candidate.get(direct)
    return candidate.get(structured)


def _normalize_candidate(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise X1AgentsRadioRPCCorroborationError(
            "candidate must be a mapping"
        )

    chain = _text(candidate.get("chain"))
    if chain is not None and chain != CHAIN:
        raise X1AgentsRadioRPCCorroborationError(
            f"candidate chain must be {CHAIN!r}"
        )

    network = _text(candidate.get("network"))
    if network is not None and network != NETWORK:
        raise X1AgentsRadioRPCCorroborationError(
            f"candidate network must be {NETWORK!r}"
        )

    source = _text(candidate.get("source"))
    if source is not None and source != RADIO_SOURCE:
        raise X1AgentsRadioRPCCorroborationError(
            f"candidate source must be {RADIO_SOURCE!r}"
        )

    if candidate.get("execution_authorized") not in {None, False}:
        raise X1AgentsRadioRPCCorroborationError(
            "candidate must not authorize execution"
        )

    truth = candidate.get("truth_state")
    if isinstance(truth, Mapping) and truth.get("cmis_verified") is True:
        raise X1AgentsRadioRPCCorroborationError(
            "Radio discovery candidate must not arrive pre-promoted as CMIS truth"
        )

    program_id = _text(candidate.get("program_id"))
    if program_id is None:
        raise X1AgentsRadioRPCCorroborationError(
            "candidate program_id is required"
        )
    if _base58_decoded_length(program_id) != 32:
        raise X1AgentsRadioRPCCorroborationError(
            "candidate program_id must decode to exactly 32 bytes"
        )

    structured_syntax = candidate.get("program_id_syntax_valid")
    if structured_syntax is False:
        raise X1AgentsRadioRPCCorroborationError(
            "structured Radio candidate marks program_id syntax invalid"
        )

    candidate_type = _candidate_type(candidate)
    reported_slot = _reported_slot(candidate)
    event_type = _reported_event_type(candidate)
    reported_signature = _reported_transaction_signature(candidate)
    reported_signature_syntax_valid = (
        _base58_decoded_length(reported_signature) == 64
        if reported_signature is not None
        else None
    )

    if candidate_type == DEPLOYMENT_CANDIDATE and reported_slot is None:
        raise X1AgentsRadioRPCCorroborationError(
            "deployment candidate requires a non-negative reported slot"
        )

    instructions = candidate.get("provider_instructions")
    if instructions is None:
        raw = candidate.get("raw")
        if isinstance(raw, Mapping):
            instructions = raw.get("bytecode_instructions")
    if not isinstance(instructions, Sequence) or isinstance(
        instructions, (str, bytes, bytearray)
    ):
        instructions = []

    return {
        "program_id": program_id,
        "candidate_type": candidate_type,
        "reported_slot": reported_slot,
        "reported_event_type": event_type,
        "reported_transaction_signature": reported_signature,
        "reported_transaction_signature_syntax_valid": reported_signature_syntax_valid,
        "provider_claims": {
            "name": _provider_claim(candidate, "name", "provider_name"),
            "category": _provider_claim(candidate, "category", "provider_category"),
            "framework": candidate.get("framework"),
            "status": candidate.get("status"),
            "description": candidate.get("description"),
            "instructions": [
                _text(item) for item in list(instructions)[:50] if _text(item)
            ],
            "provider_verified_claim": candidate.get("provider_verified_claim"),
            "tx_count_24h": candidate.get("tx_count_24h"),
        },
    }


def _parse_account_info(result: Any, *, program_id: str) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo must return an object with context/value"
        )

    context = result.get("context")
    if not isinstance(context, Mapping):
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo result is missing context"
        )
    observation_slot = _nonnegative_int(context.get("slot"))
    if observation_slot is None:
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo context slot is invalid"
        )

    if "value" not in result:
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo result is missing value"
        )

    value = result.get("value")
    if value is None:
        return {
            "program_id": program_id,
            "observation_slot": observation_slot,
            "account_existence_verified": True,
            "account_exists": False,
            "account_state_verified": True,
            "executable_verified": False,
            "executable": None,
            "owner_verified": False,
            "owner": None,
            "lamports": None,
            "space": None,
            "source": "X1 RPC getAccountInfo(finalized)",
        }

    if not isinstance(value, Mapping):
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo value must be an object or null"
        )

    executable = value.get("executable")
    owner = _text(value.get("owner"))
    if not isinstance(executable, bool):
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo executable must be boolean"
        )
    if owner is None:
        raise X1AgentsRadioRPCCorroborationError(
            "getAccountInfo owner is required for an existing account"
        )

    lamports = value.get("lamports")
    if isinstance(lamports, bool) or not isinstance(lamports, int) or lamports < 0:
        lamports = None

    space = value.get("space")
    if isinstance(space, bool) or not isinstance(space, int) or space < 0:
        space = None

    return {
        "program_id": program_id,
        "observation_slot": observation_slot,
        "account_existence_verified": True,
        "account_exists": True,
        "account_state_verified": True,
        "executable_verified": True,
        "executable": executable,
        "owner_verified": True,
        "owner": owner,
        "lamports": lamports,
        "space": space,
        "source": "X1 RPC getAccountInfo(finalized)",
    }


def _parse_history(result: Any, *, program_id: str, limit: int) -> dict[str, Any]:
    if not isinstance(result, list):
        raise X1AgentsRadioRPCCorroborationError(
            "getSignaturesForAddress result must be a list"
        )

    rows: list[dict[str, Any]] = []
    for raw in result:
        if not isinstance(raw, Mapping):
            raise X1AgentsRadioRPCCorroborationError(
                "getSignaturesForAddress row must be an object"
            )
        signature = _text(raw.get("signature"))
        slot = _nonnegative_int(raw.get("slot"))
        if not signature or slot is None or "err" not in raw:
            raise X1AgentsRadioRPCCorroborationError(
                "getSignaturesForAddress row is malformed"
            )
        block_time = raw.get("blockTime")
        if block_time is not None and (
            isinstance(block_time, bool)
            or not isinstance(block_time, (int, float))
            or block_time < 0
        ):
            raise X1AgentsRadioRPCCorroborationError(
                "getSignaturesForAddress blockTime is malformed"
            )
        rows.append(
            {
                "signature": signature,
                "slot": slot,
                "success": raw.get("err") is None,
                "err": raw.get("err"),
                "block_time": block_time,
                "confirmation_status": _text(raw.get("confirmationStatus")),
            }
        )

    return {
        "program_id": program_id,
        "requested_commitment": "finalized",
        "requested_limit": limit,
        "history_page_verified": True,
        "returned_count": len(rows),
        "successful_count": sum(1 for row in rows if row["success"]),
        "bounded_history_has_successful_activity": any(
            row["success"] for row in rows
        ),
        "empty_page_is_lifetime_inactivity_proof": False,
        "rows": rows,
        "source": "X1 RPC getSignaturesForAddress(finalized)",
    }


def _transaction_account_keys(result: Mapping[str, Any]) -> set[str]:
    transaction = result.get("transaction")
    if not isinstance(transaction, Mapping):
        return set()
    message = transaction.get("message")
    if not isinstance(message, Mapping):
        return set()

    keys: set[str] = set()
    raw_keys = message.get("accountKeys")
    if isinstance(raw_keys, list):
        for raw in raw_keys:
            if isinstance(raw, Mapping):
                value = _text(raw.get("pubkey"))
            else:
                value = _text(raw)
            if value:
                keys.add(value)

    instructions = message.get("instructions")
    if isinstance(instructions, list):
        for instruction in instructions:
            if isinstance(instruction, Mapping):
                program_id = _text(instruction.get("programId"))
                if program_id:
                    keys.add(program_id)
    return keys


def _parse_transaction(
    result: Any,
    *,
    signature: str,
    program_id: str,
    reported_slot: int,
) -> dict[str, Any]:
    if result is None:
        return {
            "signature": signature,
            "transaction_available": False,
            "transaction_result_verified": True,
            "slot": None,
            "slot_matches_reported": False,
            "success_verified": False,
            "references_program_id_verified": False,
            "reported_slot_transaction_corroborated": False,
            "source": "X1 RPC getTransaction(finalized,jsonParsed)",
        }
    if not isinstance(result, Mapping):
        raise X1AgentsRadioRPCCorroborationError(
            "getTransaction result must be an object or null"
        )

    slot = _nonnegative_int(result.get("slot"))
    meta = result.get("meta")
    if not isinstance(meta, Mapping) or "err" not in meta:
        raise X1AgentsRadioRPCCorroborationError(
            "getTransaction result is missing meta.err"
        )

    slot_matches = slot == reported_slot
    success = meta.get("err") is None
    references_program = program_id in _transaction_account_keys(result)

    return {
        "signature": signature,
        "transaction_available": True,
        "transaction_result_verified": True,
        "slot": slot,
        "slot_matches_reported": slot_matches,
        "success_verified": success,
        "references_program_id_verified": references_program,
        "reported_slot_transaction_corroborated": bool(
            slot_matches and success and references_program
        ),
        "source": "X1 RPC getTransaction(finalized,jsonParsed)",
    }


def _status(
    *,
    account: Mapping[str, Any],
    reported_slot: int | None,
    reported_slot_activity_verified: bool,
    transaction_corroborated: bool,
) -> str:
    if account.get("account_exists") is False:
        return ACCOUNT_NOT_FOUND
    if account.get("account_state_verified") is not True:
        return EVIDENCE_INCOMPLETE
    if account.get("executable") is not True:
        return ACCOUNT_NOT_EXECUTABLE
    if reported_slot is not None and transaction_corroborated:
        return REPORTED_SLOT_ACTIVITY_CORROBORATED
    if reported_slot is not None and not reported_slot_activity_verified:
        return EVIDENCE_INCOMPLETE
    return PROGRAM_ACCOUNT_CORROBORATED


def corroborate_agents_radio_with_x1_rpc(
    candidate: Mapping[str, Any],
    *,
    rpc_call: Callable[[str, Any], Any] = rpc_request,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    inspect_reported_slot_transaction: bool = True,
) -> dict[str, Any]:
    """Corroborate one Radio candidate against bounded finalized X1 RPC."""

    normalized = _normalize_candidate(candidate)
    limit = _history_limit(history_limit)
    if not isinstance(inspect_reported_slot_transaction, bool):
        raise X1AgentsRadioRPCCorroborationError(
            "inspect_reported_slot_transaction must be boolean"
        )

    program_id = normalized["program_id"]
    account_result = rpc_call(
        "getAccountInfo",
        [
            program_id,
            {
                "encoding": "base64",
                "commitment": "finalized",
            },
        ],
    )
    account = _parse_account_info(
        account_result,
        program_id=program_id,
    )

    history: dict[str, Any] = {
        "program_id": program_id,
        "requested_commitment": "finalized",
        "requested_limit": limit,
        "history_page_verified": False,
        "returned_count": 0,
        "successful_count": 0,
        "bounded_history_has_successful_activity": False,
        "empty_page_is_lifetime_inactivity_proof": False,
        "rows": [],
        "source": "X1 RPC getSignaturesForAddress(finalized)",
    }
    if account["account_exists"]:
        history_result = rpc_call(
            "getSignaturesForAddress",
            [
                program_id,
                {
                    "commitment": "finalized",
                    "limit": limit,
                },
            ],
        )
        history = _parse_history(
            history_result,
            program_id=program_id,
            limit=limit,
        )

    reported_slot = normalized["reported_slot"]
    matching_successful = [
        row
        for row in history["rows"]
        if reported_slot is not None
        and row["slot"] == reported_slot
        and row["success"] is True
    ]
    reported_slot_activity_verified = bool(matching_successful)

    reported_signature = normalized["reported_transaction_signature"]
    reported_signature_syntax_valid = normalized[
        "reported_transaction_signature_syntax_valid"
    ]
    signature_to_inspect = None
    if reported_signature and reported_signature_syntax_valid is True:
        signature_to_inspect = reported_signature
    elif matching_successful:
        signature_to_inspect = matching_successful[0]["signature"]

    transaction: dict[str, Any] | None = None
    if (
        reported_slot is not None
        and signature_to_inspect is not None
        and inspect_reported_slot_transaction
    ):
        transaction_result = rpc_call(
            "getTransaction",
            [
                signature_to_inspect,
                {
                    "encoding": "jsonParsed",
                    "commitment": "finalized",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        transaction = _parse_transaction(
            transaction_result,
            signature=signature_to_inspect,
            program_id=program_id,
            reported_slot=reported_slot,
        )

    transaction_corroborated = bool(
        isinstance(transaction, Mapping)
        and transaction.get("reported_slot_transaction_corroborated") is True
    )
    reported_slot_activity_verified = bool(
        reported_slot_activity_verified or transaction_corroborated
    )
    exact_program_account_corroborated = bool(
        account.get("account_existence_verified") is True
        and account.get("account_exists") is True
        and account.get("executable_verified") is True
        and account.get("executable") is True
        and account.get("owner_verified") is True
    )

    verified_chain_fields: list[str] = []
    if account.get("account_existence_verified") is True:
        verified_chain_fields.append("account_exists")
    if account.get("executable_verified") is True:
        verified_chain_fields.append("executable")
    if account.get("owner_verified") is True:
        verified_chain_fields.append("owner")
    if history.get("history_page_verified") is True:
        verified_chain_fields.extend(
            [
                "bounded_finalized_history_count",
                "bounded_finalized_successful_history_count",
            ]
        )
    if reported_slot_activity_verified:
        verified_chain_fields.append("successful_activity_at_reported_slot")
    if transaction_corroborated:
        verified_chain_fields.extend(
            [
                "reported_slot_transaction_exists",
                "reported_slot_transaction_succeeded",
                "reported_slot_transaction_references_program_id",
            ]
        )

    failures: list[str] = []
    if account.get("account_exists") is False:
        failures.append("program_account_not_found")
    elif account.get("executable") is not True:
        failures.append("program_account_not_executable")
    if account.get("account_exists") and history.get("history_page_verified") is not True:
        failures.append("bounded_history_unverified")
    if reported_slot is not None and not reported_slot_activity_verified:
        failures.append("reported_slot_not_observed_in_bounded_successful_history")
    if (
        reported_slot is not None
        and reported_slot_activity_verified
        and inspect_reported_slot_transaction
        and not transaction_corroborated
    ):
        failures.append("reported_slot_transaction_not_corroborated")

    status = _status(
        account=account,
        reported_slot=reported_slot,
        reported_slot_activity_verified=reported_slot_activity_verified,
        transaction_corroborated=transaction_corroborated,
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "scope": "exact_agents_radio_program_candidate_direct_chain_corroboration",
        "radio_source": RADIO_SOURCE,
        "rpc_source": "X1 RPC",
        "program_id": program_id,
        "candidate_type": normalized["candidate_type"],
        "reported_event_type": normalized["reported_event_type"],
        "reported_slot": reported_slot,
        "reported_transaction_signature": reported_signature,
        "reported_transaction_signature_syntax_valid": reported_signature_syntax_valid,
        "provider_claims": normalized["provider_claims"],
        "rpc": {
            "account": account,
            "history": history,
            "reported_slot_transaction": transaction,
        },
        "exact_program_account_corroborated": exact_program_account_corroborated,
        "reported_slot_activity_verified": reported_slot_activity_verified,
        "reported_slot_transaction_corroborated": transaction_corroborated,
        "verified_chain_fields": verified_chain_fields,
        "provider_claim_verification": {
            "name_verified": False,
            "category_verified": False,
            "framework_verified": False,
            "status_verified": False,
            "description_verified": False,
            "instruction_semantics_verified": False,
            "provider_verified_claim_promoted": False,
            "tx_count_24h_verified": False,
            "deployment_semantics_verified": False,
            "upgrade_semantics_verified": False,
        },
        "overall_state": status,
        "failures": failures,
        "rpc_is_canonical_direct_chain_verifier_for_returned_chain_fields": True,
        "radio_rpc_source_independence_verified": False,
        "same_fact_agreement_is_source_independence": False,
        "cmis_verified": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


__all__ = [
    "ACCOUNT_NOT_EXECUTABLE",
    "ACCOUNT_NOT_FOUND",
    "CHAIN",
    "CONTRACT_VERSION",
    "DEFAULT_HISTORY_LIMIT",
    "DEPLOYMENT_CANDIDATE",
    "EVIDENCE_INCOMPLETE",
    "MAX_HISTORY_LIMIT",
    "NETWORK",
    "PROGRAM_ACCOUNT_CORROBORATED",
    "PROGRAM_CANDIDATE",
    "RADIO_SOURCE",
    "REPORTED_SLOT_ACTIVITY_CORROBORATED",
    "X1AgentsRadioRPCCorroborationError",
    "corroborate_agents_radio_with_x1_rpc",
]
