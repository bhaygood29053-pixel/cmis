"""Fail-closed verification of parsed X1 RPC token-account identity.

This adapter compares one already-collected ``getAccountInfo(jsonParsed)``
observation to caller-supplied expected account, mint, and authority values. It
does not decide where those expected values came from and does not infer a pool
relationship. In the reserve proof chain, callers should supply expectations
from separately verified pool/vault identity evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.x1.rpc_token_account import (
    ENCODING,
    RPC_METHOD,
    RPC_SOURCE,
)


VERSION = "1.0"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _valid_slot(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def verify_x1_rpc_token_account_identity(
    observation: Mapping[str, Any],
    *,
    expected_account: Any,
    expected_mint: Any,
    expected_authority: Any,
) -> dict[str, Any]:
    """Verify one X1 token-account identity exactly, without inference."""
    if not isinstance(observation, Mapping):
        raise TypeError("observation must be a mapping")

    expected_account_text = _text(expected_account)
    expected_mint_text = _text(expected_mint)
    expected_authority_text = _text(expected_authority)
    if expected_account_text is None:
        raise ValueError("expected_account must not be empty")
    if expected_mint_text is None:
        raise ValueError("expected_mint must not be empty")
    if expected_authority_text is None:
        raise ValueError("expected_authority must not be empty")

    observed_account = _text(observation.get("account"))
    observed_mint = _text(observation.get("mint"))
    observed_authority = _text(observation.get("authority"))
    slot = observation.get("slot")

    reasons: list[str] = []
    if observation.get("chain") != "x1":
        reasons.append("wrong_chain")
    if observation.get("source") != RPC_SOURCE:
        reasons.append("rpc_source_mismatch")
    if observation.get("method") != RPC_METHOD:
        reasons.append("rpc_method_mismatch")
    if observation.get("encoding") != ENCODING:
        reasons.append("rpc_encoding_mismatch")
    if not _valid_slot(slot):
        reasons.append("rpc_slot_invalid")
    if observation.get("token_account_fields_parsed") is not True:
        reasons.append("token_account_fields_unparsed")
    if observed_account != expected_account_text:
        reasons.append("account_identity_mismatch")
    if observed_mint != expected_mint_text:
        reasons.append("mint_identity_mismatch")
    if observed_authority != expected_authority_text:
        reasons.append("authority_identity_mismatch")

    reasons = list(dict.fromkeys(reasons))
    identity_verified = not reasons

    return {
        "service": "x1_rpc_token_account_identity",
        "version": VERSION,
        "chain": "x1",
        "account": observed_account,
        "mint": observed_mint,
        "authority": observed_authority,
        "slot": slot,
        "expected": {
            "account": expected_account_text,
            "mint": expected_mint_text,
            "authority": expected_authority_text,
        },
        "account_verified": observed_account == expected_account_text,
        "mint_verified": observed_mint == expected_mint_text,
        "authority_verified": observed_authority == expected_authority_text,
        "slot_verified": _valid_slot(slot),
        "identity_verified": identity_verified,
        "cmis_promotable": False,
        "rejection_reasons": reasons,
        "source_observation": {
            "source": _text(observation.get("source")),
            "method": _text(observation.get("method")),
            "encoding": _text(observation.get("encoding")),
            "slot": slot,
        },
    }


__all__ = ["VERSION", "verify_x1_rpc_token_account_identity"]
