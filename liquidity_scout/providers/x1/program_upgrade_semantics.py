"""Deterministic X1 upgradeable-program and deploy/upgrade semantic proof.

This contract sits above x1_agents_radio_rpc_corroboration/v1. It decodes the
canonical SVM BPF Upgradeable Loader account state and exact loader instruction
semantics from finalized X1 RPC.

It proves only:
- current Program -> ProgramData linkage under the upgradeable loader;
- current ProgramData last-modified slot and upgrade-authority state;
- exact successful DeployWithMaxDataLen / Upgrade instructions whose account
  positions bind the expected ProgramData and Program accounts.

It does not infer application/business semantics, Radio labels, instruction
IDLs, risk, recommendations, source independence, or execution authority.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from .rpc import rpc_request


CONTRACT_VERSION = "x1_program_upgrade_semantic_verification/v1"
REQUIRED_CORROBORATION_CONTRACT = "x1_agents_radio_rpc_corroboration/v1"

CHAIN = "x1"
NETWORK = "x1-mainnet"

BPF_UPGRADEABLE_LOADER = "BPFLoaderUpgradeab1e11111111111111111111111"

LOADER_STATE_UNINITIALIZED = 0
LOADER_STATE_BUFFER = 1
LOADER_STATE_PROGRAM = 2
LOADER_STATE_PROGRAMDATA = 3

LOADER_INSTRUCTION_DEPLOY_WITH_MAX_DATA_LEN = 2
LOADER_INSTRUCTION_UPGRADE = 3

PROGRAM_STATE_SIZE = 36
PROGRAMDATA_METADATA_SIZE = 45

PROGRAM_STATE_VERIFIED = "PROGRAM_STATE_VERIFIED"
UPGRADE_VERIFIED = "UPGRADE_VERIFIED"
DEPLOYMENT_VERIFIED = "DEPLOYMENT_VERIFIED"
RADIO_EVENT_LABEL_MISMATCH = "RADIO_EVENT_LABEL_MISMATCH"
NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION = "NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION"
EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
NOT_UPGRADEABLE_LOADER_PROGRAM = "NOT_UPGRADEABLE_LOADER_PROGRAM"


class X1ProgramUpgradeSemanticVerificationError(ValueError):
    """Raised when required evidence is malformed or violates the contract."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _base58_decode(value: str) -> bytes | None:
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

    payload = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    return (b"\x00" * leading_zeros) + payload


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError("base58 input must be bytes")
    raw = bytes(value)
    leading_zeros = len(raw) - len(raw.lstrip(b"\x00"))
    number = int.from_bytes(raw, "big")

    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded

    return ("1" * leading_zeros) + (encoded or ("" if leading_zeros else "1"))


def _require_pubkey(value: Any, *, name: str) -> str:
    text = _text(value)
    decoded = _base58_decode(text) if text else None
    if decoded is None or len(decoded) != 32:
        raise X1ProgramUpgradeSemanticVerificationError(
            f"{name} must decode to exactly 32 bytes"
        )
    return text


def _require_corroboration(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise X1ProgramUpgradeSemanticVerificationError(
            "rpc_corroboration must be a mapping"
        )
    if value.get("contract_version") != REQUIRED_CORROBORATION_CONTRACT:
        raise X1ProgramUpgradeSemanticVerificationError(
            "rpc_corroboration contract mismatch"
        )
    if value.get("chain") != CHAIN:
        raise X1ProgramUpgradeSemanticVerificationError(
            "rpc_corroboration chain mismatch"
        )
    if value.get("execution_authorized") is not False:
        raise X1ProgramUpgradeSemanticVerificationError(
            "rpc_corroboration must preserve execution_authorized=false"
        )

    program_id = _require_pubkey(
        value.get("program_id"),
        name="rpc_corroboration.program_id",
    )
    reported_slot = value.get("reported_slot")
    if reported_slot is not None:
        reported_slot = _nonnegative_int(reported_slot)
        if reported_slot is None:
            raise X1ProgramUpgradeSemanticVerificationError(
                "reported_slot must be a non-negative integer"
            )

    reported_event_type = _text(value.get("reported_event_type"))
    transaction = value.get("rpc")
    transaction = (
        transaction.get("reported_slot_transaction")
        if isinstance(transaction, Mapping)
        else None
    )
    signature = (
        _text(transaction.get("signature"))
        if isinstance(transaction, Mapping)
        else None
    )

    if reported_slot is not None:
        if not isinstance(transaction, Mapping):
            raise X1ProgramUpgradeSemanticVerificationError(
                "reported-slot semantic verification requires prior transaction corroboration"
            )
        if transaction.get("reported_slot_transaction_corroborated") is not True:
            raise X1ProgramUpgradeSemanticVerificationError(
                "reported-slot transaction must be corroborated before semantic verification"
            )
        if signature is None:
            raise X1ProgramUpgradeSemanticVerificationError(
                "corroborated reported-slot transaction signature is required"
            )

    return {
        "program_id": program_id,
        "reported_slot": reported_slot,
        "reported_event_type": (
            reported_event_type.casefold() if reported_event_type else None
        ),
        "signature": signature,
    }


def _decode_account_data(value: Mapping[str, Any], *, name: str) -> bytes:
    data = value.get("data")
    if not (
        isinstance(data, Sequence)
        and not isinstance(data, (str, bytes, bytearray))
        and len(data) >= 2
    ):
        raise X1ProgramUpgradeSemanticVerificationError(
            f"{name}.data must be [base64, encoding]"
        )
    encoded = _text(data[0])
    encoding = _text(data[1])
    if encoded is None or encoding != "base64":
        raise X1ProgramUpgradeSemanticVerificationError(
            f"{name}.data must use base64 encoding"
        )
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise X1ProgramUpgradeSemanticVerificationError(
            f"{name}.data is invalid base64"
        ) from exc


def _parse_account_result(
    result: Any,
    *,
    address: str,
    require_exists: bool = True,
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise X1ProgramUpgradeSemanticVerificationError(
            f"getAccountInfo({address}) must return an object"
        )
    context = result.get("context")
    if not isinstance(context, Mapping):
        raise X1ProgramUpgradeSemanticVerificationError(
            f"getAccountInfo({address}) is missing context"
        )
    observation_slot = _nonnegative_int(context.get("slot"))
    if observation_slot is None:
        raise X1ProgramUpgradeSemanticVerificationError(
            f"getAccountInfo({address}) context slot is invalid"
        )

    if "value" not in result:
        raise X1ProgramUpgradeSemanticVerificationError(
            f"getAccountInfo({address}) is missing value"
        )
    value = result.get("value")
    if value is None:
        if require_exists:
            raise X1ProgramUpgradeSemanticVerificationError(
                f"required account {address} does not exist"
            )
        return {
            "address": address,
            "observation_slot": observation_slot,
            "exists": False,
        }
    if not isinstance(value, Mapping):
        raise X1ProgramUpgradeSemanticVerificationError(
            f"getAccountInfo({address}).value must be an object or null"
        )

    owner = _text(value.get("owner"))
    executable = value.get("executable")
    if owner is None or not isinstance(executable, bool):
        raise X1ProgramUpgradeSemanticVerificationError(
            f"getAccountInfo({address}) owner/executable is malformed"
        )

    return {
        "address": address,
        "observation_slot": observation_slot,
        "exists": True,
        "owner": owner,
        "executable": executable,
        "data": _decode_account_data(value, name=f"getAccountInfo({address})"),
        "source": "X1 RPC getAccountInfo(finalized,base64)",
    }


def decode_upgradeable_loader_state(data: bytes) -> dict[str, Any]:
    """Decode the stable BPF Upgradeable Loader state prefix fail-closed."""

    if not isinstance(data, (bytes, bytearray)):
        raise X1ProgramUpgradeSemanticVerificationError(
            "loader account data must be bytes"
        )
    raw = bytes(data)
    if len(raw) < 4:
        raise X1ProgramUpgradeSemanticVerificationError(
            "loader account data is shorter than the state discriminator"
        )

    discriminator = int.from_bytes(raw[:4], "little")

    if discriminator == LOADER_STATE_UNINITIALIZED:
        return {
            "state": "Uninitialized",
            "discriminator": discriminator,
        }

    if discriminator == LOADER_STATE_BUFFER:
        if len(raw) < 5:
            raise X1ProgramUpgradeSemanticVerificationError(
                "Buffer state is truncated"
            )
        option = raw[4]
        if option == 0:
            authority = None
        elif option == 1:
            if len(raw) < 37:
                raise X1ProgramUpgradeSemanticVerificationError(
                    "Buffer authority state is truncated"
                )
            authority = _base58_encode(raw[5:37])
        else:
            raise X1ProgramUpgradeSemanticVerificationError(
                "Buffer authority option is invalid"
            )
        return {
            "state": "Buffer",
            "discriminator": discriminator,
            "authority_address": authority,
        }

    if discriminator == LOADER_STATE_PROGRAM:
        if len(raw) != PROGRAM_STATE_SIZE:
            raise X1ProgramUpgradeSemanticVerificationError(
                f"Program state must be exactly {PROGRAM_STATE_SIZE} bytes"
            )
        return {
            "state": "Program",
            "discriminator": discriminator,
            "programdata_address": _base58_encode(raw[4:36]),
        }

    if discriminator == LOADER_STATE_PROGRAMDATA:
        if len(raw) < 13:
            raise X1ProgramUpgradeSemanticVerificationError(
                "ProgramData state is truncated"
            )
        slot = int.from_bytes(raw[4:12], "little")
        option = raw[12]
        if option == 0:
            authority = None
        elif option == 1:
            if len(raw) < PROGRAMDATA_METADATA_SIZE:
                raise X1ProgramUpgradeSemanticVerificationError(
                    "ProgramData upgrade-authority state is truncated"
                )
            authority = _base58_encode(raw[13:45])
        else:
            raise X1ProgramUpgradeSemanticVerificationError(
                "ProgramData upgrade-authority option is invalid"
            )
        return {
            "state": "ProgramData",
            "discriminator": discriminator,
            "slot": slot,
            "upgrade_authority_address": authority,
            "upgradeable": authority is not None,
            "program_bytes_offset": PROGRAMDATA_METADATA_SIZE,
            "program_bytes_available": len(raw) >= PROGRAMDATA_METADATA_SIZE,
            "program_data_length": max(0, len(raw) - PROGRAMDATA_METADATA_SIZE),
        }

    raise X1ProgramUpgradeSemanticVerificationError(
        f"unsupported upgradeable-loader state discriminator {discriminator}"
    )


def _message_account_keys(transaction: Mapping[str, Any]) -> list[dict[str, Any]]:
    tx = transaction.get("transaction")
    if not isinstance(tx, Mapping):
        return []
    message = tx.get("message")
    if not isinstance(message, Mapping):
        return []
    raw = message.get("accountKeys")
    if not isinstance(raw, list):
        return []

    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            pubkey = _text(item.get("pubkey"))
            signer = item.get("signer") is True
            writable = item.get("writable") is True
        else:
            pubkey = _text(item)
            signer = index == 0
            writable = False
        result.append(
            {
                "pubkey": pubkey,
                "signer": signer,
                "writable": writable,
            }
        )
    return result


def _resolve_program_id(
    instruction: Mapping[str, Any],
    account_keys: Sequence[Mapping[str, Any]],
) -> str | None:
    direct = instruction.get("programId")
    if isinstance(direct, Mapping):
        direct = direct.get("pubkey") or direct.get("address")
    direct_text = _text(direct)
    if direct_text:
        return direct_text

    index = instruction.get("programIdIndex")
    if (
        isinstance(index, int)
        and not isinstance(index, bool)
        and 0 <= index < len(account_keys)
    ):
        return _text(account_keys[index].get("pubkey"))
    return None


def _resolve_instruction_accounts(
    instruction: Mapping[str, Any],
    account_keys: Sequence[Mapping[str, Any]],
) -> list[str]:
    raw = instruction.get("accounts")
    if not isinstance(raw, list):
        return []

    result: list[str] = []
    for item in raw:
        if isinstance(item, int) and not isinstance(item, bool):
            if item < 0 or item >= len(account_keys):
                return []
            pubkey = _text(account_keys[item].get("pubkey"))
        elif isinstance(item, Mapping):
            pubkey = _text(item.get("pubkey") or item.get("address"))
        else:
            pubkey = _text(item)

        if pubkey is None:
            return []
        result.append(pubkey)
    return result


def _decode_loader_instruction(data: Any) -> dict[str, Any] | None:
    encoded = _text(data)
    if encoded is None:
        return None
    raw = _base58_decode(encoded)
    if raw is None or len(raw) < 4:
        return None

    discriminator = int.from_bytes(raw[:4], "little")

    if discriminator == LOADER_INSTRUCTION_DEPLOY_WITH_MAX_DATA_LEN:
        if len(raw) not in {12, 13}:
            return None
        max_data_len = int.from_bytes(raw[4:12], "little")
        close_buffer = True
        if len(raw) == 13:
            if raw[12] not in {0, 1}:
                return None
            close_buffer = bool(raw[12])
        return {
            "semantic_type": "DEPLOY",
            "instruction_name": "DeployWithMaxDataLen",
            "discriminator": discriminator,
            "max_data_len": max_data_len,
            "close_buffer": close_buffer,
        }

    if discriminator == LOADER_INSTRUCTION_UPGRADE:
        if len(raw) not in {4, 5}:
            return None
        close_buffer = True
        if len(raw) == 5:
            if raw[4] not in {0, 1}:
                return None
            close_buffer = bool(raw[4])
        return {
            "semantic_type": "UPGRADE",
            "instruction_name": "Upgrade",
            "discriminator": discriminator,
            "close_buffer": close_buffer,
        }

    return {
        "semantic_type": "OTHER_LOADER_INSTRUCTION",
        "instruction_name": None,
        "discriminator": discriminator,
    }


def _instruction_groups(transaction: Mapping[str, Any]) -> list[tuple[str, int, Mapping[str, Any]]]:
    groups: list[tuple[str, int, Mapping[str, Any]]] = []
    tx = transaction.get("transaction")
    message = tx.get("message") if isinstance(tx, Mapping) else None
    top = message.get("instructions") if isinstance(message, Mapping) else None
    if isinstance(top, list):
        for index, instruction in enumerate(top):
            if isinstance(instruction, Mapping):
                groups.append(("message", index, instruction))

    meta = transaction.get("meta")
    inner_groups = meta.get("innerInstructions") if isinstance(meta, Mapping) else None
    if isinstance(inner_groups, list):
        for group in inner_groups:
            if not isinstance(group, Mapping):
                continue
            parent = group.get("index")
            instructions = group.get("instructions")
            if not isinstance(instructions, list):
                continue
            for index, instruction in enumerate(instructions):
                if isinstance(instruction, Mapping):
                    groups.append((f"inner:{parent}", index, instruction))
    return groups


def _signer_map(account_keys: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for item in account_keys:
        pubkey = _text(item.get("pubkey"))
        if pubkey:
            result[pubkey] = item.get("signer") is True
    return result


def _loader_event_candidates(
    transaction: Mapping[str, Any],
    *,
    program_id: str,
    programdata_address: str,
) -> dict[str, Any]:
    account_keys = _message_account_keys(transaction)
    signers = _signer_map(account_keys)

    loader_instruction_count = 0
    undecodable_loader_instruction_count = 0
    events: list[dict[str, Any]] = []

    for location, index, instruction in _instruction_groups(transaction):
        if _resolve_program_id(instruction, account_keys) != BPF_UPGRADEABLE_LOADER:
            continue

        loader_instruction_count += 1
        decoded = _decode_loader_instruction(instruction.get("data"))
        if decoded is None:
            undecodable_loader_instruction_count += 1
            continue
        if decoded["semantic_type"] not in {"DEPLOY", "UPGRADE"}:
            continue

        accounts = _resolve_instruction_accounts(instruction, account_keys)
        semantic_type = decoded["semantic_type"]
        if semantic_type == "UPGRADE":
            expected_programdata_index = 0
            expected_program_index = 1
            authority_index = 6
        else:
            expected_programdata_index = 1
            expected_program_index = 2
            authority_index = 7

        account_positions_available = (
            len(accounts) > max(expected_programdata_index, expected_program_index)
        )
        programdata_matches = bool(
            account_positions_available
            and accounts[expected_programdata_index] == programdata_address
        )
        program_matches = bool(
            account_positions_available
            and accounts[expected_program_index] == program_id
        )

        authority = (
            accounts[authority_index]
            if authority_index < len(accounts)
            else None
        )
        authority_signer_verified = bool(
            authority is not None and signers.get(authority) is True
        )

        events.append(
            {
                "location": location,
                "instruction_index": index,
                **decoded,
                "accounts": accounts,
                "programdata_account_position": expected_programdata_index,
                "program_account_position": expected_program_index,
                "programdata_matches": programdata_matches,
                "program_matches": program_matches,
                "exact_account_binding_verified": (
                    programdata_matches and program_matches
                ),
                "authority": authority,
                "authority_signer_verified": authority_signer_verified,
            }
        )

    return {
        "loader_instruction_count": loader_instruction_count,
        "undecodable_loader_instruction_count": undecodable_loader_instruction_count,
        "loader_instruction_decoding_complete": (
            undecodable_loader_instruction_count == 0
        ),
        "events": events,
    }


def _normalized_reported_event(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"upgrade", "upgraded", "program_upgrade"}:
        return "UPGRADE"
    if normalized in {
        "deploy",
        "deployed",
        "deployment",
        "program_deploy",
        "program_deployment",
    }:
        return "DEPLOY"
    return None


def _fetch_account(rpc_call: Callable[[str, Any], Any], address: str) -> dict[str, Any]:
    return _parse_account_result(
        rpc_call(
            "getAccountInfo",
            [
                address,
                {
                    "encoding": "base64",
                    "commitment": "finalized",
                },
            ],
        ),
        address=address,
    )


def _fetch_transaction(
    rpc_call: Callable[[str, Any], Any],
    signature: str,
) -> Mapping[str, Any]:
    result = rpc_call(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "finalized",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )
    if not isinstance(result, Mapping):
        raise X1ProgramUpgradeSemanticVerificationError(
            "semantic verification transaction is unavailable or malformed"
        )
    meta = result.get("meta")
    if not isinstance(meta, Mapping) or "err" not in meta:
        raise X1ProgramUpgradeSemanticVerificationError(
            "semantic verification transaction is missing meta.err"
        )
    return result


def verify_program_upgrade_semantics(
    rpc_corroboration: Mapping[str, Any],
    *,
    rpc_call: Callable[[str, Any], Any] = rpc_request,
) -> dict[str, Any]:
    """Verify current loader state and exact deploy/upgrade transaction semantics."""

    normalized = _require_corroboration(rpc_corroboration)
    program_id = normalized["program_id"]
    reported_slot = normalized["reported_slot"]
    signature = normalized["signature"]

    program_account = _fetch_account(rpc_call, program_id)
    program_owner_is_loader = (
        program_account["owner"] == BPF_UPGRADEABLE_LOADER
    )
    program_is_executable = program_account["executable"] is True

    program_state = None
    programdata_address = None
    if program_owner_is_loader and program_is_executable:
        program_state = decode_upgradeable_loader_state(
            program_account["data"]
        )
        if program_state["state"] == "Program":
            programdata_address = _require_pubkey(
                program_state.get("programdata_address"),
                name="Program.programdata_address",
            )

    if programdata_address is None:
        return {
            "contract_version": CONTRACT_VERSION,
            "chain": CHAIN,
            "network": NETWORK,
            "program_id": program_id,
            "reported_slot": reported_slot,
            "reported_event_type": normalized["reported_event_type"],
            "program_account": {
                "owner": program_account["owner"],
                "executable": program_account["executable"],
                "observation_slot": program_account["observation_slot"],
                "loader_state": program_state,
            },
            "programdata_account": None,
            "current_program_state_verified": False,
            "current_upgradeability_verified": False,
            "current_upgradeable": False,
            "current_immutable": False,
            "verified_event": None,
            "reported_event_semantics_verified": False,
            "radio_event_label_matches_verified_semantics": False,
            "overall_state": NOT_UPGRADEABLE_LOADER_PROGRAM,
            "failures": [
                "program_is_not_executable_upgradeable_loader_program_state"
            ],
            "cmis_verified": False,
            "cmis_promotable": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "risk_conclusion_authorized": False,
            "recommendation_authorized": False,
            "execution_authorized": False,
        }

    programdata_account = _fetch_account(rpc_call, programdata_address)
    programdata_owner_is_loader = (
        programdata_account["owner"] == BPF_UPGRADEABLE_LOADER
    )
    programdata_not_executable = programdata_account["executable"] is False

    programdata_state = (
        decode_upgradeable_loader_state(programdata_account["data"])
        if programdata_owner_is_loader
        else None
    )
    programdata_state_verified = bool(
        isinstance(programdata_state, Mapping)
        and programdata_state.get("state") == "ProgramData"
    )

    current_program_state_verified = bool(
        program_owner_is_loader
        and program_is_executable
        and program_state["state"] == "Program"
        and programdata_owner_is_loader
        and programdata_not_executable
        and programdata_state_verified
    )

    current_upgrade_authority = (
        _text(programdata_state.get("upgrade_authority_address"))
        if programdata_state_verified
        else None
    )
    current_upgradeability_verified = current_program_state_verified
    current_upgradeable = bool(
        current_upgradeability_verified and current_upgrade_authority is not None
    )
    current_immutable = bool(
        current_upgradeability_verified and current_upgrade_authority is None
    )
    current_programdata_slot = (
        _nonnegative_int(programdata_state.get("slot"))
        if programdata_state_verified
        else None
    )

    tx: Mapping[str, Any] | None = None
    tx_slot = None
    tx_success_verified = False
    event_scan = {
        "loader_instruction_count": 0,
        "undecodable_loader_instruction_count": 0,
        "loader_instruction_decoding_complete": True,
        "events": [],
    }
    verified_event = None
    programdata_slot_not_before_event = None

    failures: list[str] = []
    if not current_program_state_verified:
        failures.append("current_program_programdata_linkage_unverified")

    if reported_slot is not None and signature is not None:
        tx = _fetch_transaction(rpc_call, signature)
        tx_slot = _nonnegative_int(tx.get("slot"))
        meta = tx.get("meta")
        tx_success_verified = bool(
            isinstance(meta, Mapping)
            and meta.get("err") is None
            and tx_slot == reported_slot
        )
        if not tx_success_verified:
            failures.append("reported_transaction_slot_or_success_mismatch")

        event_scan = _loader_event_candidates(
            tx,
            program_id=program_id,
            programdata_address=programdata_address,
        )
        bound_events = [
            event
            for event in event_scan["events"]
            if event["exact_account_binding_verified"] is True
        ]
        if len(bound_events) == 1:
            verified_event = bound_events[0]
        elif len(bound_events) > 1:
            failures.append("ambiguous_multiple_bound_loader_events")

        if current_programdata_slot is not None:
            programdata_slot_not_before_event = (
                current_programdata_slot >= reported_slot
            )
            if not programdata_slot_not_before_event:
                failures.append("current_programdata_slot_precedes_reported_event")
    elif reported_slot is not None:
        failures.append("reported_event_transaction_unavailable")

    event_semantics_verified = bool(
        current_program_state_verified
        and tx_success_verified
        and verified_event is not None
        and programdata_slot_not_before_event is not False
    )
    verified_semantic_type = (
        verified_event["semantic_type"]
        if event_semantics_verified and verified_event is not None
        else None
    )

    reported_semantic_type = _normalized_reported_event(
        normalized["reported_event_type"]
    )
    label_matches = bool(
        reported_semantic_type is not None
        and verified_semantic_type is not None
        and reported_semantic_type == verified_semantic_type
    )

    if reported_slot is None:
        overall_state = (
            PROGRAM_STATE_VERIFIED
            if current_program_state_verified
            else EVIDENCE_INCOMPLETE
        )
    elif event_semantics_verified and label_matches:
        overall_state = (
            UPGRADE_VERIFIED
            if verified_semantic_type == "UPGRADE"
            else DEPLOYMENT_VERIFIED
        )
    elif event_semantics_verified and reported_semantic_type is not None:
        overall_state = RADIO_EVENT_LABEL_MISMATCH
        failures.append("radio_event_label_does_not_match_loader_semantics")
    elif (
        tx_success_verified
        and event_scan["loader_instruction_decoding_complete"]
        and not event_scan["events"]
    ):
        overall_state = NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION
        failures.append("no_deploy_or_upgrade_loader_instruction_in_exact_transaction")
    else:
        overall_state = EVIDENCE_INCOMPLETE
        if reported_slot is not None and verified_event is None:
            failures.append("deploy_upgrade_semantics_not_verified")

    current_slot_matches_reported_event = bool(
        current_programdata_slot is not None
        and reported_slot is not None
        and current_programdata_slot == reported_slot
    )
    later_program_modification_observed = bool(
        current_programdata_slot is not None
        and reported_slot is not None
        and current_programdata_slot > reported_slot
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "scope": "upgradeable_loader_program_state_and_exact_event_semantics",
        "program_id": program_id,
        "programdata_address": programdata_address,
        "reported_slot": reported_slot,
        "reported_event_type": normalized["reported_event_type"],
        "reported_semantic_type": reported_semantic_type,
        "signature": signature,
        "program_account": {
            "owner": program_account["owner"],
            "executable": program_account["executable"],
            "observation_slot": program_account["observation_slot"],
            "owner_is_upgradeable_loader": program_owner_is_loader,
            "loader_state": program_state,
        },
        "programdata_account": {
            "owner": programdata_account["owner"],
            "executable": programdata_account["executable"],
            "observation_slot": programdata_account["observation_slot"],
            "owner_is_upgradeable_loader": programdata_owner_is_loader,
            "loader_state": programdata_state,
        },
        "current_program_state_verified": current_program_state_verified,
        "current_programdata_slot": current_programdata_slot,
        "current_upgradeability_verified": current_upgradeability_verified,
        "current_upgrade_authority": current_upgrade_authority,
        "current_upgradeable": current_upgradeable,
        "current_immutable": current_immutable,
        "transaction_slot": tx_slot,
        "transaction_success_and_slot_verified": tx_success_verified,
        "loader_event_scan": event_scan,
        "verified_event": verified_event,
        "verified_semantic_type": verified_semantic_type,
        "reported_event_semantics_verified": event_semantics_verified,
        "radio_event_label_matches_verified_semantics": label_matches,
        "programdata_slot_not_before_event": programdata_slot_not_before_event,
        "current_programdata_slot_matches_reported_event": (
            current_slot_matches_reported_event
        ),
        "later_program_modification_observed": later_program_modification_observed,
        "current_upgrade_authority_is_historical_event_authority": False,
        "program_bytecode_semantics_verified": False,
        "application_instruction_semantics_verified": False,
        "radio_name_category_framework_verified": False,
        "source_independence_verified": False,
        "overall_state": overall_state,
        "failures": list(dict.fromkeys(failures)),
        "cmis_verified": False,
        "cmis_promotable": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


__all__ = [
    "BPF_UPGRADEABLE_LOADER",
    "CONTRACT_VERSION",
    "DEPLOYMENT_VERIFIED",
    "EVIDENCE_INCOMPLETE",
    "NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION",
    "NOT_UPGRADEABLE_LOADER_PROGRAM",
    "PROGRAM_STATE_VERIFIED",
    "RADIO_EVENT_LABEL_MISMATCH",
    "REQUIRED_CORROBORATION_CONTRACT",
    "UPGRADE_VERIFIED",
    "X1ProgramUpgradeSemanticVerificationError",
    "decode_upgradeable_loader_state",
    "verify_program_upgrade_semantics",
]
