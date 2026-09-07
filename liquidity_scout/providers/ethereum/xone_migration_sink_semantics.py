"""Fail-closed XONE burn-redeemer / migration-sink semantics.

This contract distinguishes three different ideas that must not be collapsed:

1. the exact Ethereum XONE token exposes a burn accounting surface;
2. a candidate contract may implement the FairCrypto IBurnRedeemable callback;
3. a candidate may actually be the XONE -> XNT migration/conversion mechanism.

Only (1) and, when directly queried, (2) can be proven here.  (3) remains
unverified until independent authoritative evidence binds the exact candidate
to XNT issuance/vesting/claim semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .xone_identity import CHAIN, CHAIN_ID, NETWORK, XONE_CONTRACT, XONE_DEPLOYER


CONTRACT_VERSION = "ethereum_xone_migration_sink_semantics/v1"

# Canonical Ethereum function selectors.
BURN_SELECTOR = "0x9dc29fac"  # burn(address,uint256)
USER_BURNS_SELECTOR = "0xce653d5f"  # userBurns(address)
ON_TOKEN_BURNED_INTERFACE_ID = "0x543746b1"  # onTokenBurned(address,uint256)
SUPPORTS_INTERFACE_SELECTOR = "0x01ffc9a7"  # supportsInterface(bytes4)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class EthereumXoneMigrationSemanticsError(RuntimeError):
    """Raised when XONE burn/migration semantics cannot be verified safely."""


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _address(value: Any, *, field: str) -> str:
    text = _text(value)
    if text is None:
        raise EthereumXoneMigrationSemanticsError(f"{field} is missing")
    lowered = text.casefold()
    if len(lowered) != 42 or not lowered.startswith("0x"):
        raise EthereumXoneMigrationSemanticsError(f"{field} is not a 20-byte address")
    try:
        int(lowered[2:], 16)
    except ValueError as exc:
        raise EthereumXoneMigrationSemanticsError(f"{field} is not hexadecimal") from exc
    return lowered


def _hex_bytes(value: Any, *, field: str, allow_empty: bool = False) -> bytes:
    text = _text(value)
    if text is None or not text.startswith("0x"):
        raise EthereumXoneMigrationSemanticsError(f"{field} is not 0x-prefixed hex")
    payload = text[2:]
    if len(payload) % 2:
        raise EthereumXoneMigrationSemanticsError(f"{field} has odd-length hex")
    if not payload and allow_empty:
        return b""
    if not payload:
        raise EthereumXoneMigrationSemanticsError(f"{field} is empty")
    try:
        return bytes.fromhex(payload)
    except ValueError as exc:
        raise EthereumXoneMigrationSemanticsError(f"{field} is malformed hex") from exc


def _decode_uint256(value: Any, *, field: str) -> int:
    payload = _hex_bytes(value, field=field)
    if len(payload) != 32:
        raise EthereumXoneMigrationSemanticsError(f"{field} must be one ABI word")
    return int.from_bytes(payload, "big")


def _decode_bool(value: Any, *, field: str) -> bool:
    parsed = _decode_uint256(value, field=field)
    if parsed not in (0, 1):
        raise EthereumXoneMigrationSemanticsError(f"{field} is not a canonical ABI bool")
    return bool(parsed)


def _encode_address_word(address: str) -> str:
    normalized = _address(address, field="address argument")
    return ("0" * 24) + normalized[2:]


def user_burns_calldata(user: str) -> str:
    """Encode userBurns(address) without requiring a web3 dependency."""

    return USER_BURNS_SELECTOR + _encode_address_word(user)


def supports_interface_calldata(interface_id: str = ON_TOKEN_BURNED_INTERFACE_ID) -> str:
    """Encode ERC165 supportsInterface(bytes4)."""

    text = _text(interface_id)
    if text is None or len(text) != 10 or not text.startswith("0x"):
        raise ValueError("interface_id must be a 4-byte 0x-prefixed selector")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError("interface_id must be hexadecimal") from exc
    # ABI fixed bytes are left-aligned in the 32-byte word.
    return SUPPORTS_INTERFACE_SELECTOR + text[2:].casefold() + ("0" * 56)


def _truth_state() -> dict[str, Any]:
    return {
        "xone_burn_accounting_surface_verified": False,
        "burn_redeemer_interface_verified": False,
        "transfer_sink_semantics_verified": False,
        "migration_sink_identified": False,
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


def verify_xone_burn_surface(
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
    probe_users: Sequence[str] = (ZERO_ADDRESS, XONE_DEPLOYER),
) -> dict[str, Any]:
    """Verify the exact XONE contract exposes readable per-user burn accounting.

    This does not claim that any burn was caused by XONE -> XNT conversion.
    """

    chain_id = _text(rpc_call("eth_chainId", []))
    if chain_id is None or chain_id.casefold() != CHAIN_ID:
        raise EthereumXoneMigrationSemanticsError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    code = _hex_bytes(
        rpc_call("eth_getCode", [XONE_CONTRACT, "finalized"]),
        field="XONE runtime bytecode",
        allow_empty=True,
    )
    if not code:
        raise EthereumXoneMigrationSemanticsError("XONE contract has no runtime bytecode")

    if not probe_users:
        raise ValueError("probe_users must not be empty")

    user_burns: dict[str, str] = {}
    for user in probe_users:
        normalized = _address(user, field="probe user")
        raw = rpc_call(
            "eth_call",
            [{"to": XONE_CONTRACT, "data": user_burns_calldata(normalized)}, "finalized"],
        )
        amount = _decode_uint256(raw, field=f"userBurns({normalized})")
        user_burns[normalized] = str(amount)

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "selectors": {
            "burn(address,uint256)": BURN_SELECTOR,
            "userBurns(address)": USER_BURNS_SELECTOR,
            "onTokenBurned(address,uint256)": ON_TOKEN_BURNED_INTERFACE_ID,
            "supportsInterface(bytes4)": SUPPORTS_INTERFACE_SELECTOR,
        },
        "runtime_code_present": True,
        "probe_user_burns_base_units": user_burns,
        "burn_design_model": "iburnredeemable_callback_candidate",
        "simple_transfer_sink_required_by_this_proof": False,
        "source_url": source_url,
        "read_only": True,
        **{
            **_truth_state(),
            "xone_burn_accounting_surface_verified": True,
        },
    }


def verify_burn_redeemer_candidate(
    candidate_address: str,
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
) -> dict[str, Any]:
    """Verify code presence and ERC165 IBurnRedeemable support for a candidate.

    Interface support proves only technical compatibility with the burn callback.
    It does not prove that the candidate is a XONE -> XNT converter.
    """

    candidate = _address(candidate_address, field="candidate address")
    if candidate == ZERO_ADDRESS or candidate == XONE_CONTRACT:
        raise EthereumXoneMigrationSemanticsError("candidate address is not eligible")

    chain_id = _text(rpc_call("eth_chainId", []))
    if chain_id is None or chain_id.casefold() != CHAIN_ID:
        raise EthereumXoneMigrationSemanticsError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    code = _hex_bytes(
        rpc_call("eth_getCode", [candidate, "finalized"]),
        field="candidate runtime bytecode",
        allow_empty=True,
    )
    if not code:
        raise EthereumXoneMigrationSemanticsError("candidate has no runtime bytecode")

    supported = _decode_bool(
        rpc_call(
            "eth_call",
            [
                {
                    "to": candidate,
                    "data": supports_interface_calldata(
                        ON_TOKEN_BURNED_INTERFACE_ID
                    ),
                },
                "finalized",
            ],
        ),
        field="supportsInterface(IBurnRedeemable)",
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "xone_contract": XONE_CONTRACT,
        "candidate_address": candidate,
        "candidate_runtime_code_present": True,
        "iburnredeemable_interface_id": ON_TOKEN_BURNED_INTERFACE_ID,
        "burn_redeemer_interface_supported": supported,
        "candidate_role": (
            "burn_redeemer_interface_candidate"
            if supported
            else "contract_without_iburnredeemable_support"
        ),
        "migration_role_requires_separate_evidence": True,
        "source_url": source_url,
        "read_only": True,
        **{
            **_truth_state(),
            "burn_redeemer_interface_verified": supported,
        },
    }


def classify_migration_candidate(
    *,
    candidate_address: str,
    burn_redeemer_proof: Optional[Mapping[str, Any]] = None,
    direct_transfer_to_candidate_verified: bool = False,
    authoritative_xone_xnt_role_evidence: bool = False,
    x1_issuance_binding_verified: bool = False,
) -> dict[str, Any]:
    """Combine bounded candidate facts while refusing semantic shortcuts."""

    candidate = _address(candidate_address, field="candidate address")

    redeemer_supported = False
    if burn_redeemer_proof is not None:
        if burn_redeemer_proof.get("candidate_address") != candidate:
            raise EthereumXoneMigrationSemanticsError("candidate proof address mismatch")
        redeemer_supported = (
            burn_redeemer_proof.get("burn_redeemer_interface_verified") is True
        )

    migration_verified = (
        authoritative_xone_xnt_role_evidence
        and x1_issuance_binding_verified
        and (redeemer_supported or direct_transfer_to_candidate_verified)
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "xone_contract": XONE_CONTRACT,
        "candidate_address": candidate,
        "burn_redeemer_interface_verified": redeemer_supported,
        "direct_transfer_to_candidate_verified": bool(
            direct_transfer_to_candidate_verified
        ),
        "authoritative_xone_xnt_role_evidence": bool(
            authoritative_xone_xnt_role_evidence
        ),
        "x1_issuance_binding_verified": bool(x1_issuance_binding_verified),
        "migration_sink_identified": migration_verified,
        "lock_or_migration_verified": migration_verified,
        "xone_xnt_conversion_verified": migration_verified,
        "xnt_issuance_verified": bool(x1_issuance_binding_verified),
        "cross_chain_correlation_verified": migration_verified,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


def corroborate_xone_burn_surface(
    proofs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require matching burn-accounting observations from distinct RPC hosts."""

    if not isinstance(proofs, Sequence) or isinstance(proofs, (str, bytes, bytearray)):
        raise EthereumXoneMigrationSemanticsError("proofs must be a sequence")
    if len(proofs) < 2:
        raise EthereumXoneMigrationSemanticsError("at least two RPC proofs are required")

    hosts: set[str] = set()
    normalized: list[Mapping[str, Any]] = []
    for proof in proofs:
        if not isinstance(proof, Mapping):
            raise EthereumXoneMigrationSemanticsError("each proof must be a mapping")
        if proof.get("xone_burn_accounting_surface_verified") is not True:
            raise EthereumXoneMigrationSemanticsError(
                "all proofs must verify XONE burn accounting surface"
            )
        if proof.get("contract_address") != XONE_CONTRACT:
            raise EthereumXoneMigrationSemanticsError("proof contract address mismatch")
        source_url = _text(proof.get("source_url"))
        if not source_url:
            raise EthereumXoneMigrationSemanticsError("each proof requires source_url")
        host = (urlparse(source_url).hostname or "").casefold()
        if not host:
            raise EthereumXoneMigrationSemanticsError("proof source_url is invalid")
        hosts.add(host)
        normalized.append(proof)

    if len(hosts) < 2:
        raise EthereumXoneMigrationSemanticsError(
            "two distinct RPC transport hosts are required"
        )

    baseline = normalized[0]
    for proof in normalized[1:]:
        if proof.get("selectors") != baseline.get("selectors"):
            raise EthereumXoneMigrationSemanticsError("RPC proofs disagree on selectors")
        if proof.get("probe_user_burns_base_units") != baseline.get(
            "probe_user_burns_base_units"
        ):
            raise EthereumXoneMigrationSemanticsError(
                "RPC proofs disagree on userBurns state"
            )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "selectors": dict(baseline["selectors"]),
        "probe_user_burns_base_units": dict(
            baseline["probe_user_burns_base_units"]
        ),
        "burn_design_model": baseline["burn_design_model"],
        "rpc_proof_count": len(normalized),
        "rpc_transport_hosts": sorted(hosts),
        "multi_rpc_corroborated": True,
        "transport_provider_diversity_verified": True,
        "rpc_backend_source_independence_verified": False,
        "same_chain_consensus_is_not_cross_source_semantic_independence": True,
        "simple_transfer_sink_required_by_this_proof": False,
        "migration_sink_identified": False,
        "lock_or_migration_verified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "cross_chain_correlation_verified": False,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


__all__ = [
    "BURN_SELECTOR",
    "CONTRACT_VERSION",
    "EthereumXoneMigrationSemanticsError",
    "ON_TOKEN_BURNED_INTERFACE_ID",
    "SUPPORTS_INTERFACE_SELECTOR",
    "USER_BURNS_SELECTOR",
    "classify_migration_candidate",
    "corroborate_xone_burn_surface",
    "supports_interface_calldata",
    "user_burns_calldata",
    "verify_burn_redeemer_candidate",
    "verify_xone_burn_surface",
]
