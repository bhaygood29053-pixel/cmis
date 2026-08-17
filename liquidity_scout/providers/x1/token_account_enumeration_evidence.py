"""Deterministic evidence adapters for X1 token-account enumeration.

This module is transport-free. It binds an observed account-program owner to a
separately verified token-account identity, then sanitizes a mint-filtered
``getProgramAccounts`` observation into a replayable count/set-digest artifact.

Neither step proves that the observed program is the one canonical token program
for all of X1, nor that the RPC enumeration is complete or untruncated. Those
claims remain explicit evidence gaps and are never promoted here.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from liquidity_scout.providers.x1.rpc_token_account import (
    ENCODING as TOKEN_ACCOUNT_ENCODING,
    RPC_METHOD as TOKEN_ACCOUNT_METHOD,
    RPC_SOURCE,
)
from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    RPC_METHOD as ENUMERATION_METHOD,
)


VERSION = "1.0"
TOKEN_IDENTITY_SERVICE = "x1_rpc_token_account_identity"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _valid_slot(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _valid_count(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _safe_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item)) is not None]


def derive_x1_token_program_binding(
    observation: Mapping[str, Any],
    identity_verification: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one observed account-program owner to an exactly verified account.

    The result proves only that this verified token account was observed as owned
    by ``token_program_id`` at the recorded RPC slot. It does not generalize that
    program identity to every token or account on X1.
    """
    if not isinstance(observation, Mapping):
        raise TypeError("observation must be a mapping")
    if not isinstance(identity_verification, Mapping):
        raise TypeError("identity_verification must be a mapping")

    account = _text(observation.get("account"))
    mint = _text(observation.get("mint"))
    authority = _text(observation.get("authority"))
    token_program_id = _text(observation.get("account_program_owner"))
    slot = observation.get("slot")

    reasons: list[str] = []
    if observation.get("chain") != "x1":
        reasons.append("wrong_chain")
    if observation.get("source") != RPC_SOURCE:
        reasons.append("rpc_source_mismatch")
    if observation.get("method") != TOKEN_ACCOUNT_METHOD:
        reasons.append("rpc_method_mismatch")
    if observation.get("encoding") != TOKEN_ACCOUNT_ENCODING:
        reasons.append("rpc_encoding_mismatch")
    if observation.get("token_account_fields_parsed") is not True:
        reasons.append("token_account_fields_unparsed")
    if account is None:
        reasons.append("account_missing")
    if mint is None:
        reasons.append("mint_missing")
    if authority is None:
        reasons.append("authority_missing")
    if token_program_id is None:
        reasons.append("account_program_owner_missing")
    if not _valid_slot(slot):
        reasons.append("rpc_slot_invalid")

    if identity_verification.get("service") != TOKEN_IDENTITY_SERVICE:
        reasons.append("identity_service_mismatch")
    if identity_verification.get("chain") != "x1":
        reasons.append("identity_chain_mismatch")
    if identity_verification.get("identity_verified") is not True:
        reasons.append("token_account_identity_unverified")
    if _text(identity_verification.get("account")) != account:
        reasons.append("verified_account_mismatch")
    if _text(identity_verification.get("mint")) != mint:
        reasons.append("verified_mint_mismatch")
    if _text(identity_verification.get("authority")) != authority:
        reasons.append("verified_authority_mismatch")
    if identity_verification.get("slot") != slot:
        reasons.append("verified_slot_mismatch")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        raise ValueError(
            "cannot derive X1 token-program binding: " + ",".join(reasons)
        )

    return {
        "service": "x1_token_program_binding",
        "version": VERSION,
        "chain": "x1",
        "source": RPC_SOURCE,
        "account": account,
        "mint": mint,
        "authority": authority,
        "slot": slot,
        "token_program_id": token_program_id,
        "program_binding_verified_for_account": True,
        "canonical_chain_token_program_verified": False,
        "cmis_promotable": False,
        "warnings": [
            "program_binding_is_verified_for_one_account_not_all_x1_tokens"
        ],
    }


def build_x1_token_account_enumeration_artifact(
    program_binding: Mapping[str, Any],
    enumeration: Mapping[str, Any],
) -> dict[str, Any]:
    """Return sanitized, deterministic evidence for one enumeration candidate."""
    if not isinstance(program_binding, Mapping):
        raise TypeError("program_binding must be a mapping")
    if not isinstance(enumeration, Mapping):
        raise TypeError("enumeration must be a mapping")

    binding_program = _text(program_binding.get("token_program_id"))
    binding_mint = _text(program_binding.get("mint"))
    binding_account = _text(program_binding.get("account"))
    binding_authority = _text(program_binding.get("authority"))
    binding_slot = program_binding.get("slot")

    if program_binding.get("service") != "x1_token_program_binding":
        raise ValueError("unexpected token-program binding service")
    if program_binding.get("chain") != "x1":
        raise ValueError("token-program binding must be for x1")
    if program_binding.get("program_binding_verified_for_account") is not True:
        raise ValueError("token-program binding is not verified")
    if program_binding.get("canonical_chain_token_program_verified") is not False:
        raise ValueError("canonical chain token-program claim is not allowed")
    if program_binding.get("cmis_promotable") is not False:
        raise ValueError("token-program binding may not claim CMIS promotion")
    if None in {
        binding_program,
        binding_mint,
        binding_account,
        binding_authority,
    } or not _valid_slot(binding_slot):
        raise ValueError("token-program binding identity is incomplete")

    enum_mint = _text(enumeration.get("mint"))
    enum_program = _text(enumeration.get("token_program_id"))
    enum_slot = enumeration.get("slot")
    count = enumeration.get("account_count_candidate")
    accounts = enumeration.get("accounts")

    if enumeration.get("chain") != "x1":
        raise ValueError("enumeration must be for x1")
    if enumeration.get("source") != RPC_SOURCE:
        raise ValueError("enumeration RPC source is invalid")
    if enumeration.get("method") != ENUMERATION_METHOD:
        raise ValueError("enumeration RPC method is invalid")
    if enum_mint != binding_mint:
        raise ValueError("enumeration mint does not match verified binding")
    if enum_program != binding_program:
        raise ValueError("enumeration token program does not match verified binding")
    if not _valid_slot(enum_slot):
        raise ValueError("enumeration slot is invalid")
    if enumeration.get("returned_account_identity_verified") is not True:
        raise ValueError("returned account identity is not verified")
    if enumeration.get("token_account_semantics_verified") is not True:
        raise ValueError("returned token-account semantics are not verified")
    if not _valid_count(count):
        raise ValueError("enumeration account count candidate is invalid")
    if not isinstance(accounts, list):
        raise ValueError("enumeration accounts must be a list")
    if len(accounts) != count:
        raise ValueError("enumeration count does not match account list")

    forbidden_true_claims = {
        "enumeration_complete": enumeration.get("enumeration_complete"),
        "truncation_absent_verified": enumeration.get(
            "truncation_absent_verified"
        ),
        "total_count_eligible": enumeration.get("total_count_eligible"),
        "holder_semantics_verified": enumeration.get(
            "holder_semantics_verified"
        ),
        "beneficial_owner_identity_verified": enumeration.get(
            "beneficial_owner_identity_verified"
        ),
        "cmis_promotable": enumeration.get("cmis_promotable"),
    }
    unexpected_claims = [
        name for name, value in forbidden_true_claims.items() if value is not False
    ]
    if unexpected_claims:
        raise ValueError(
            "enumeration contains unsupported promotion/coverage claims: "
            + ",".join(unexpected_claims)
        )
    if enumeration.get("coverage") != "unverified":
        raise ValueError("enumeration coverage must remain unverified")

    addresses: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(accounts):
        if not isinstance(item, Mapping):
            raise ValueError(f"enumeration account {index} is malformed")
        address = _text(item.get("address"))
        if address is None:
            raise ValueError(f"enumeration account {index} address is missing")
        if address in seen:
            raise ValueError("enumeration account addresses are duplicated")
        if _text(item.get("mint")) != binding_mint:
            raise ValueError("enumeration account mint mismatch")
        if _text(item.get("token_program_id")) != binding_program:
            raise ValueError("enumeration account token-program mismatch")
        seen.add(address)
        addresses.append(address)

    canonical_addresses = sorted(addresses)
    address_set_digest = sha256(
        "\n".join(canonical_addresses).encode("utf-8")
    ).hexdigest()

    return {
        "evidence_type": "x1_token_account_enumeration_candidate",
        "evidence_version": VERSION,
        "chain": "x1",
        "mint": binding_mint,
        "token_program_binding": {
            "source": _text(program_binding.get("source")),
            "account": binding_account,
            "authority": binding_authority,
            "slot": binding_slot,
            "token_program_id": binding_program,
            "program_binding_verified_for_account": True,
            "canonical_chain_token_program_verified": False,
        },
        "enumeration": {
            "source": RPC_SOURCE,
            "method": ENUMERATION_METHOD,
            "slot": enum_slot,
            "mint_filter": {
                "offset": (
                    enumeration.get("mint_filter", {}).get("offset")
                    if isinstance(enumeration.get("mint_filter"), Mapping)
                    else None
                ),
                "bytes": (
                    _text(enumeration.get("mint_filter", {}).get("bytes"))
                    if isinstance(enumeration.get("mint_filter"), Mapping)
                    else None
                ),
            },
            "account_count_candidate": count,
            "account_set_sha256": address_set_digest,
            "returned_account_identity_verified": True,
            "token_account_semantics_verified": True,
        },
        "coverage": "unverified",
        "enumeration_complete": False,
        "truncation_absent_verified": False,
        "total_count_eligible": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "artifact_sanitized": True,
        "warnings": list(
            dict.fromkeys(
                _safe_strings(program_binding.get("warnings"))
                + _safe_strings(enumeration.get("warnings"))
            )
        ),
    }


__all__ = [
    "VERSION",
    "build_x1_token_account_enumeration_artifact",
    "derive_x1_token_program_binding",
]
