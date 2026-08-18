"""Read-only X1 candidate pool-role evidence for CMIS v1.5.4.

This module validates mint-filtered 637-byte XDEX program-state candidates
against the independently verified binary layout. It deliberately separates:

1. structural pool-state evidence: program owner/size, two mint slots, two vault
   slots, vault token-account mint alignment, and shared vault authority; and
2. observed transaction coupling: whether recent address history contains a
   recognized XDEX instruction that explicitly receives the candidate address.

Structural proof does not establish that the configured AMM program registry is
globally exhaustive. Transaction coupling is corroborating evidence only and is
not required for old/inactive structurally valid pool state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.pool_topology import (
    collect_recognized_amm_instruction_accounts,
)
from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    get_token_account_info,
    rpc_request,
)
from liquidity_scout.providers.x1.transaction_semantics import fetch_transaction

VERSION = "1.5.4"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
DEFAULT_ACCOUNT_SPACE = 637
DEFAULT_MINT_OFFSETS = (168, 200)
DEFAULT_VAULT_OFFSETS = (72, 104)
DEFAULT_SIGNATURE_LIMIT = 20


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def encode_base58_pubkey(payload: bytes) -> str:
    """Encode exactly 32 bytes as a base58 public key."""

    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("payload must be bytes")
    raw = bytes(payload)
    if len(raw) != 32:
        raise ValueError("public-key payload must be exactly 32 bytes")

    leading_zeros = len(raw) - len(raw.lstrip(b"\x00"))
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    return ("1" * leading_zeros) + (encoded or "")


def extract_pubkey_at(data: bytes, offset: int) -> str:
    """Decode one 32-byte public-key slot at an exact byte offset."""

    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    raw = bytes(data)
    end = offset + 32
    if end > len(raw):
        raise ValueError("public-key slot exceeds account data length")
    return encode_base58_pubkey(raw[offset:end])


def _token_account_fetcher(account: str, *, rpc_url: str):
    return get_token_account_info(account, rpc_url=rpc_url)


def _transaction_fetcher(signature: str, *, rpc_url: str):
    return fetch_transaction(signature, rpc_url=rpc_url)


def _recent_instruction_coupling(
    *,
    account: str,
    program_id: str,
    rpc_url: str,
    signature_limit: int,
    requester: Callable[..., Any],
    transaction_fetcher: Callable[..., Any],
) -> dict[str, Any]:
    """Observe recent recognized-program instruction coupling for one address."""

    errors: list[dict[str, Any]] = []
    try:
        history = requester(
            "getSignaturesForAddress",
            [account, {"limit": signature_limit}],
            rpc_url=rpc_url,
        )
    except Exception as exc:
        return {
            "history_available": False,
            "returned_signature_count": 0,
            "successful_transaction_fetch_count": 0,
            "recognized_program_transaction_count": 0,
            "candidate_in_program_instruction_count": 0,
            "candidate_in_program_instruction_observed": False,
            "errors": [
                {
                    "stage": "getSignaturesForAddress",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            ],
        }

    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        return {
            "history_available": False,
            "returned_signature_count": 0,
            "successful_transaction_fetch_count": 0,
            "recognized_program_transaction_count": 0,
            "candidate_in_program_instruction_count": 0,
            "candidate_in_program_instruction_observed": False,
            "errors": [
                {
                    "stage": "getSignaturesForAddress",
                    "error": "X1 RPC returned no usable signature list",
                }
            ],
        }

    successful_fetches = 0
    recognized_program_transactions = 0
    coupled_count = 0

    for raw in history:
        if not isinstance(raw, Mapping) or raw.get("err") is not None:
            continue
        signature = _text(raw.get("signature"))
        if not signature:
            continue
        try:
            tx = transaction_fetcher(signature, rpc_url=rpc_url)
        except Exception as exc:
            errors.append(
                {
                    "stage": "getTransaction",
                    "signature": signature,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if not isinstance(tx, Mapping):
            continue

        successful_fetches += 1
        by_program = collect_recognized_amm_instruction_accounts(
            tx,
            program_ids=(program_id,),
        )
        accounts = by_program.get(program_id) or []
        if accounts:
            recognized_program_transactions += 1
        if account in accounts:
            coupled_count += 1

    return {
        "history_available": True,
        "returned_signature_count": len(history),
        "successful_transaction_fetch_count": successful_fetches,
        "recognized_program_transaction_count": recognized_program_transactions,
        "candidate_in_program_instruction_count": coupled_count,
        "candidate_in_program_instruction_observed": coupled_count > 0,
        "errors": errors,
    }


def verify_candidate_pool_role(
    *,
    account: str,
    target_mint: str,
    program_id: str,
    account_space: int = DEFAULT_ACCOUNT_SPACE,
    mint_offsets: Sequence[int] = DEFAULT_MINT_OFFSETS,
    vault_offsets: Sequence[int] = DEFAULT_VAULT_OFFSETS,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    signature_limit: int = DEFAULT_SIGNATURE_LIMIT,
    requester: Callable[..., Any] = rpc_request,
    token_account_fetcher: Callable[..., Any] = _token_account_fetcher,
    transaction_fetcher: Callable[..., Any] = _transaction_fetcher,
) -> dict[str, Any]:
    """Verify structural pool-state evidence for one mint-filtered candidate."""

    account = _text(account)
    target_mint = _text(target_mint)
    program_id = _text(program_id)
    if not account:
        raise ValueError("account is required")
    if not target_mint:
        raise ValueError("target_mint is required")
    if not program_id:
        raise ValueError("program_id is required")
    if isinstance(account_space, bool) or not isinstance(account_space, int) or account_space <= 0:
        raise ValueError("account_space must be a positive integer")
    if len(tuple(mint_offsets)) != 2 or len(tuple(vault_offsets)) != 2:
        raise ValueError("exactly two mint offsets and two vault offsets are required")
    if isinstance(signature_limit, bool) or not isinstance(signature_limit, int):
        raise ValueError("signature_limit must be an integer between 1 and 100")
    if signature_limit < 1 or signature_limit > 100:
        raise ValueError("signature_limit must be an integer between 1 and 100")

    errors: list[dict[str, Any]] = []
    state = fetch_account_state(
        account,
        rpc_url=rpc_url,
        requester=requester,
    )
    data = state.pop("data", None)
    data = data if isinstance(data, bytes) else None

    owner_matches = _text(state.get("owner")) == program_id
    space_matches = state.get("space") == account_space
    integrity = state.get("response_integrity_verified") is True

    mints: list[str] = []
    vaults: list[str] = []
    if data is not None:
        try:
            mints = [extract_pubkey_at(data, int(offset)) for offset in mint_offsets]
            vaults = [extract_pubkey_at(data, int(offset)) for offset in vault_offsets]
        except Exception as exc:
            errors.append(
                {
                    "stage": "state_slot_decode",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    target_mint_present = target_mint in mints
    mint_slots_distinct = len(mints) == 2 and mints[0] != mints[1]
    vault_slots_distinct = len(vaults) == 2 and vaults[0] != vaults[1]

    vault_reports: list[dict[str, Any]] = []
    for index, vault in enumerate(vaults):
        expected_mint = mints[index] if index < len(mints) else None
        try:
            raw = token_account_fetcher(vault, rpc_url=rpc_url)
            info = dict(raw) if isinstance(raw, Mapping) else {}
        except Exception as exc:
            info = {}
            errors.append(
                {
                    "stage": "vault_token_account",
                    "vault": vault,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

        vault_reports.append(
            {
                "slot_index": index,
                "vault_offset": int(vault_offsets[index]),
                "mint_offset": int(mint_offsets[index]),
                "vault": vault,
                "expected_mint": expected_mint,
                "account_exists": info.get("account_exists") is True,
                "identity_verified": info.get("identity_verified") is True,
                "observed_mint": _text(info.get("mint")),
                "mint_matches_expected": bool(
                    expected_mint
                    and _text(info.get("mint")) == expected_mint
                ),
                "token_authority": _text(info.get("token_authority")),
                "program_owner": _text(info.get("program_owner")),
                "parsed_type": _text(info.get("parsed_type")),
            }
        )

    both_vaults_verified = len(vault_reports) == 2 and all(
        row.get("identity_verified") is True
        and row.get("mint_matches_expected") is True
        for row in vault_reports
    )
    authorities = {
        row.get("token_authority")
        for row in vault_reports
        if row.get("token_authority")
    }
    shared_vault_authority_verified = bool(
        both_vaults_verified and len(authorities) == 1
    )
    shared_authority = next(iter(authorities)) if len(authorities) == 1 else None

    structural_role_verified = bool(
        integrity
        and owner_matches
        and space_matches
        and target_mint_present
        and mint_slots_distinct
        and vault_slots_distinct
        and both_vaults_verified
        and shared_vault_authority_verified
    )

    transaction_coupling = _recent_instruction_coupling(
        account=account,
        program_id=program_id,
        rpc_url=rpc_url,
        signature_limit=signature_limit,
        requester=requester,
        transaction_fetcher=transaction_fetcher,
    )

    public_state = {
        key: value
        for key, value in state.items()
        if key not in {"rpc_url"}
    }

    return {
        "service": "candidate_pool_role_verification",
        "version": VERSION,
        "chain": "x1",
        "account": account,
        "target_mint": target_mint,
        "program_id": program_id,
        "account_space": account_space,
        "mint_offsets": list(mint_offsets),
        "vault_offsets": list(vault_offsets),
        "state": public_state,
        "decoded_state": {
            "mint_0": mints[0] if len(mints) > 0 else None,
            "mint_1": mints[1] if len(mints) > 1 else None,
            "vault_0": vaults[0] if len(vaults) > 0 else None,
            "vault_1": vaults[1] if len(vaults) > 1 else None,
            "target_mint_present": target_mint_present,
            "mint_slots_distinct": mint_slots_distinct,
            "vault_slots_distinct": vault_slots_distinct,
        },
        "vaults": vault_reports,
        "shared_vault_authority": shared_authority,
        "transaction_coupling": transaction_coupling,
        "summary": {
            "state_integrity_verified": integrity,
            "program_owner_verified": owner_matches,
            "account_space_verified": space_matches,
            "target_mint_present": target_mint_present,
            "both_vaults_verified": both_vaults_verified,
            "shared_vault_authority_verified": shared_vault_authority_verified,
            "pool_state_structural_role_verified": structural_role_verified,
            "recent_recognized_instruction_coupling_observed": (
                transaction_coupling.get(
                    "candidate_in_program_instruction_observed"
                )
                is True
            ),
            "pool_role_promoted": structural_role_verified,
            "recognized_program_registry_globally_exhaustive": False,
            "global_onchain_pool_discovery_proven": False,
            "interpretation": (
                "A candidate is structurally promoted only when the verified "
                "637-byte program state decodes to two distinct mints and two "
                "distinct token vaults, each vault matches its corresponding mint, "
                "and both vaults share one token authority. Recent recognized-XDEX "
                "instruction coupling is reported separately as corroboration."
            ),
        },
        "errors": errors + list(transaction_coupling.get("errors") or []),
    }


__all__ = [
    "DEFAULT_ACCOUNT_SPACE",
    "DEFAULT_MINT_OFFSETS",
    "DEFAULT_SIGNATURE_LIMIT",
    "DEFAULT_VAULT_OFFSETS",
    "VERSION",
    "encode_base58_pubkey",
    "extract_pubkey_at",
    "verify_candidate_pool_role",
]
