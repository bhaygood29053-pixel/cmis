"""Deterministic Uniswap v4 hook intelligence for CMIS.

The contract validates exact EVM pool/hook identity and decodes the fourteen
Uniswap v4 hook permission bits embedded in the hook address. Address-bit
decoding is structural evidence only: it does not prove deployed bytecode,
business logic, reflection behavior, economic safety, or current pool state.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

CONTRACT_VERSION = "uniswap_v4_hook_intelligence/v1"
ZERO_ADDRESS = "0x" + ("0" * 40)
HOOK_PERMISSION_MASK = 0x3FFF
DEFAULT_EXECUTION_AUTHORIZED = False

PERMISSION_FLAGS = (
    ("before_initialize", 1 << 13),
    ("after_initialize", 1 << 12),
    ("before_add_liquidity", 1 << 11),
    ("after_add_liquidity", 1 << 10),
    ("before_remove_liquidity", 1 << 9),
    ("after_remove_liquidity", 1 << 8),
    ("before_swap", 1 << 7),
    ("after_swap", 1 << 6),
    ("before_donate", 1 << 5),
    ("after_donate", 1 << 4),
    ("before_swap_returns_delta", 1 << 3),
    ("after_swap_returns_delta", 1 << 2),
    ("after_add_liquidity_returns_delta", 1 << 1),
    ("after_remove_liquidity_returns_delta", 1 << 0),
)


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _evm_address(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if len(text) != 42 or not text.startswith("0x"):
        raise ValueError(f"{field} must be a 20-byte 0x-prefixed EVM address")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    return "0x" + text[2:].lower()


def _bytes32(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if len(text) != 66 or not text.startswith("0x"):
        raise ValueError(f"{field} must be a 32-byte 0x-prefixed value")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    return "0x" + text[2:].lower()


def _bounded_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _evidence_ids(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ValueError("source_evidence_ids must be a collection")
    result = [_required_text(value, "source_evidence_id") for value in values]
    if len(result) != len(set(result)):
        raise ValueError("source_evidence_ids must be unique")
    return result


def decode_hook_permissions(hook_address: Any) -> dict[str, Any]:
    """Decode the Uniswap v4 permission mask from one exact hook address."""

    address = _evm_address(hook_address, "hook_address")
    mask = int(address, 16) & HOOK_PERMISSION_MASK
    permissions = {
        name: bool(mask & flag)
        for name, flag in PERMISSION_FLAGS
    }
    return {
        "hook_address": address,
        "permission_mask": f"0x{mask:04x}",
        "permissions": permissions,
    }


def build_uniswap_v4_hook_intelligence(
    *,
    chain: Any,
    pool_id: Any,
    pool_manager: Any,
    currency0: Any,
    currency1: Any,
    fee: Any,
    tick_spacing: Any,
    hook_address: Any,
    pool_key_verified: Any,
    hook_code_verified: Any,
    observed_code_hash: Any = None,
    observed_at: Any = None,
    source_evidence_ids: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Build bounded structural hook intelligence from exact supplied evidence.

    `pool_key_verified` and `hook_code_verified` are caller-supplied evidence
    verdicts. This function validates and preserves them; it does not perform RPC.
    """

    chain_name = _required_text(chain, "chain").casefold()
    pool = _bytes32(pool_id, "pool_id")
    manager = _evm_address(pool_manager, "pool_manager")
    token0 = _evm_address(currency0, "currency0")
    token1 = _evm_address(currency1, "currency1")
    if token0 == token1:
        raise ValueError("currency0 and currency1 must differ")

    fee_value = _bounded_int(fee, "fee", minimum=0, maximum=0xFFFFFF)
    spacing = _bounded_int(tick_spacing, "tick_spacing", minimum=1, maximum=32767)
    pool_key_ok = _strict_bool(pool_key_verified, "pool_key_verified")
    code_ok = _strict_bool(hook_code_verified, "hook_code_verified")
    evidence_ids = _evidence_ids(source_evidence_ids)

    decoded = decode_hook_permissions(hook_address)
    hook = decoded["hook_address"]
    hook_present = hook != ZERO_ADDRESS

    if (pool_key_ok or code_ok) and not evidence_ids:
        raise ValueError(
            "verified pool/code claims require at least one source_evidence_id"
        )
    if not hook_present and code_ok:
        raise ValueError("hook_code_verified cannot be true for the zero hook")
    if hook_present and code_ok and observed_code_hash is None:
        raise ValueError(
            "observed_code_hash is required when hook_code_verified is true"
        )

    code_hash = None
    if observed_code_hash is not None:
        code_hash = _bytes32(observed_code_hash, "observed_code_hash")

    active_permissions = [
        name
        for name, enabled in decoded["permissions"].items()
        if enabled
    ]

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": chain_name,
        "pool": {
            "pool_id": pool,
            "pool_manager": manager,
            "currency0": token0,
            "currency1": token1,
            "fee": fee_value,
            "tick_spacing": spacing,
            "hook_address": hook,
        },
        "hook": {
            "present": hook_present,
            "address": hook,
            "permission_mask": decoded["permission_mask"],
            "permissions": decoded["permissions"],
            "active_permissions": active_permissions,
            "observed_code_hash": code_hash,
        },
        "verification": {
            "pool_key_verified": pool_key_ok,
            "hook_address_permission_bits_decoded": True,
            "hook_code_verified": code_ok,
            "hook_logic_semantics_verified": False,
            "reflection_behavior_verified": False,
            "current_pool_state_verified": False,
            "source_independence_verified": False,
        },
        "evidence": {
            "observed_at": observed_at,
            "source_evidence_ids": evidence_ids,
        },
        "boundaries": {
            "permission_bits_do_not_prove_business_logic": True,
            "reflection_claim_authorized": False,
            "yield_claim_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_EXECUTION_AUTHORIZED",
    "HOOK_PERMISSION_MASK",
    "PERMISSION_FLAGS",
    "ZERO_ADDRESS",
    "build_uniswap_v4_hook_intelligence",
    "decode_hook_permissions",
]
