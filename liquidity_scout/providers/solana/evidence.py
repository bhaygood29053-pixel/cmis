"""Adapt already-validated Solana RPC observations into CMIS evidence records.

This module performs no network transport. It consumes the strict contracts
returned by ``SolanaRPCProvider`` and preserves their exact identity, unit, and
slot semantics in the shared CMIS evidence shape.

Freshness is deliberately caller-controlled and defaults closed. A valid RPC
slot proves provenance, not that an observation is fresh enough for a specific
market/risk decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.evidence import build_evidence_observation

VERSION = "1.0"
CHAIN = "solana"
SOURCE = "solana_rpc"

TOKEN_BASE_UNITS = "TOKEN_BASE_UNITS"
COUNT = "COUNT"
ADDRESS_OR_NULL = "ADDRESS_OR_NULL"
PROGRAM_ID = "PROGRAM_ID"
PROGRAM_LABEL = "PROGRAM_LABEL"
BOOLEAN = "BOOLEAN"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _slot(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _unsigned_integer_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value or not value.isdigit():
        return None
    return value.lstrip("0") or "0"


def _u8(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 255 else None


def _common(
    *,
    fact_type: str,
    mint: str,
    slot: int,
    source_role: str,
    freshness_verified: bool,
) -> dict[str, Any]:
    return {
        "chain": CHAIN,
        "fact_type": fact_type,
        "subject_id": mint,
        "source": SOURCE,
        "source_role": source_role,
        "observed_at": None,
        "block_slot": slot,
        "calculation_version": f"solana-rpc-evidence-{VERSION}",
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": bool(freshness_verified),
        "warnings": [] if freshness_verified else ["freshness_not_verified"],
    }


def build_solana_supply_evidence(
    supply: Mapping[str, Any],
    *,
    freshness_verified: bool = False,
) -> dict[str, Any]:
    """Build exact total-supply and decimals evidence from ``getTokenSupply``."""

    if not isinstance(supply, Mapping):
        raise TypeError("Solana supply evidence input must be a mapping")

    reasons: list[str] = []
    if supply.get("chain") != CHAIN:
        reasons.append("wrong_chain")
    if supply.get("source") != SOURCE:
        reasons.append("wrong_source")
    if supply.get("method") != "getTokenSupply":
        reasons.append("wrong_method")
    if supply.get("supply_verified") is not True:
        reasons.append("supply_unverified")
    if supply.get("coverage") != "total_token_supply":
        reasons.append("supply_coverage_unverified")

    mint = _text(supply.get("mint"))
    slot = _slot(supply.get("context_slot"))
    amount = _unsigned_integer_string(supply.get("amount_raw"))
    decimals = _u8(supply.get("decimals"))

    if mint is None:
        reasons.append("mint_missing")
    if slot is None:
        reasons.append("slot_invalid")
    if amount is None:
        reasons.append("supply_amount_invalid")
    if decimals is None:
        reasons.append("decimals_invalid")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return {
            "service": "solana_rpc_evidence_adapter",
            "version": VERSION,
            "evidence_ready": False,
            "cmis_promotable": False,
            "observations": [],
            "rejection_reasons": reasons,
        }

    assert mint is not None and slot is not None and amount is not None and decimals is not None

    supply_observation = build_evidence_observation(
        **_common(
            fact_type="token_total_supply_base_units",
            mint=mint,
            slot=slot,
            source_role="canonical_onchain",
            freshness_verified=freshness_verified,
        ),
        raw_identifier="getTokenSupply.value.amount",
        raw_value=amount,
        normalized_value=amount,
        unit=TOKEN_BASE_UNITS,
    )
    decimals_observation = build_evidence_observation(
        **_common(
            fact_type="token_decimals",
            mint=mint,
            slot=slot,
            source_role="canonical_onchain",
            freshness_verified=freshness_verified,
        ),
        raw_identifier="getTokenSupply.value.decimals",
        raw_value=decimals,
        normalized_value=decimals,
        unit=COUNT,
    )
    return {
        "service": "solana_rpc_evidence_adapter",
        "version": VERSION,
        "evidence_ready": True,
        "cmis_promotable": False,
        "observations": [supply_observation, decimals_observation],
        "rejection_reasons": [],
    }


def build_solana_mint_state_evidence(
    mint_state: Mapping[str, Any],
    *,
    freshness_verified: bool = False,
) -> dict[str, Any]:
    """Build provenance records for canonical mint program/authority state.

    Address/program/boolean facts remain non-numeric observations. They preserve
    exact RPC state for fact-specific verification later; this adapter does not
    force them through ``compare_same_fact_exact``.
    """

    if not isinstance(mint_state, Mapping):
        raise TypeError("Solana mint-state evidence input must be a mapping")

    reasons: list[str] = []
    if mint_state.get("chain") != CHAIN:
        reasons.append("wrong_chain")
    if mint_state.get("source") != SOURCE:
        reasons.append("wrong_source")
    if mint_state.get("method") != "getAccountInfo(jsonParsed)":
        reasons.append("wrong_method")
    if mint_state.get("program_identity_verified") is not True:
        reasons.append("program_identity_unverified")
    if mint_state.get("mint_state_verified") is not True:
        reasons.append("mint_state_unverified")

    mint = _text(mint_state.get("mint"))
    slot = _slot(mint_state.get("context_slot"))
    owner_program_id = _text(mint_state.get("owner_program_id"))
    parsed_program = _text(mint_state.get("parsed_program"))
    amount = _unsigned_integer_string(mint_state.get("amount_raw"))
    decimals = _u8(mint_state.get("decimals"))
    initialized = mint_state.get("is_initialized")

    if mint is None:
        reasons.append("mint_missing")
    if slot is None:
        reasons.append("slot_invalid")
    if owner_program_id is None:
        reasons.append("owner_program_id_missing")
    if parsed_program is None:
        reasons.append("parsed_program_missing")
    if amount is None:
        reasons.append("mint_supply_invalid")
    if decimals is None:
        reasons.append("decimals_invalid")
    if initialized is not None and not isinstance(initialized, bool):
        reasons.append("initialized_state_invalid")

    for field in ("mint_authority", "freeze_authority"):
        value = mint_state.get(field)
        if value is not None and _text(value) is None:
            reasons.append(f"{field}_invalid")

    extensions = mint_state.get("extension_names")
    if not isinstance(extensions, list) or any(
        not isinstance(item, str) or not item.strip() for item in extensions
    ):
        reasons.append("extension_names_invalid")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return {
            "service": "solana_rpc_evidence_adapter",
            "version": VERSION,
            "evidence_ready": False,
            "cmis_promotable": False,
            "observations": [],
            "extensions": [],
            "rejection_reasons": reasons,
        }

    assert mint is not None and slot is not None
    assert owner_program_id is not None and parsed_program is not None
    assert amount is not None and decimals is not None

    common = {
        "mint": mint,
        "slot": slot,
        "freshness_verified": freshness_verified,
    }
    observations = [
        build_evidence_observation(
            **_common(
                fact_type="token_total_supply_base_units",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.data.parsed.info.supply",
            raw_value=amount,
            normalized_value=amount,
            unit=TOKEN_BASE_UNITS,
        ),
        build_evidence_observation(
            **_common(
                fact_type="token_decimals",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.data.parsed.info.decimals",
            raw_value=decimals,
            normalized_value=decimals,
            unit=COUNT,
        ),
        build_evidence_observation(
            **_common(
                fact_type="token_owner_program_id",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.value.owner",
            raw_value=owner_program_id,
            normalized_value=None,
            unit=PROGRAM_ID,
        ),
        build_evidence_observation(
            **_common(
                fact_type="token_program_label",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.data.program",
            raw_value=parsed_program,
            normalized_value=None,
            unit=PROGRAM_LABEL,
        ),
        build_evidence_observation(
            **_common(
                fact_type="token_mint_authority",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.data.parsed.info.mintAuthority",
            raw_value=mint_state.get("mint_authority"),
            normalized_value=None,
            unit=ADDRESS_OR_NULL,
        ),
        build_evidence_observation(
            **_common(
                fact_type="token_freeze_authority",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.data.parsed.info.freezeAuthority",
            raw_value=mint_state.get("freeze_authority"),
            normalized_value=None,
            unit=ADDRESS_OR_NULL,
        ),
        build_evidence_observation(
            **_common(
                fact_type="token_initialized",
                source_role="canonical_onchain",
                **common,
            ),
            raw_identifier="getAccountInfo.data.parsed.info.isInitialized",
            raw_value=initialized,
            normalized_value=None,
            unit=BOOLEAN,
        ),
    ]

    clean_extensions = list(dict.fromkeys(item.strip() for item in extensions))
    return {
        "service": "solana_rpc_evidence_adapter",
        "version": VERSION,
        "evidence_ready": True,
        "cmis_promotable": False,
        "observations": observations,
        "extensions": clean_extensions,
        "rejection_reasons": [],
    }


def build_solana_largest_accounts_evidence(
    largest_accounts: Mapping[str, Any],
    *,
    freshness_verified: bool = False,
) -> dict[str, Any]:
    """Preserve top-account observations without manufacturing holder coverage.

    The returned account evidence is intentionally not converted to a
    ``holder_count`` CMIS fact. Each account balance remains pool-independent,
    address-scoped concentration evidence for later deterministic analysis.
    """

    if not isinstance(largest_accounts, Mapping):
        raise TypeError("Solana largest-accounts evidence input must be a mapping")

    reasons: list[str] = []
    if largest_accounts.get("chain") != CHAIN:
        reasons.append("wrong_chain")
    if largest_accounts.get("source") != SOURCE:
        reasons.append("wrong_source")
    if largest_accounts.get("method") != "getTokenLargestAccounts":
        reasons.append("wrong_method")
    if largest_accounts.get("coverage") != "largest_token_accounts_only":
        reasons.append("coverage_not_largest_accounts_only")
    if largest_accounts.get("counted_entity") != "token_accounts":
        reasons.append("counted_entity_mismatch")
    if largest_accounts.get("total_holder_count_verified") is not False:
        reasons.append("holder_count_must_remain_unverified")

    mint = _text(largest_accounts.get("mint"))
    slot = _slot(largest_accounts.get("context_slot"))
    accounts = largest_accounts.get("accounts")
    if mint is None:
        reasons.append("mint_missing")
    if slot is None:
        reasons.append("slot_invalid")
    if not isinstance(accounts, list):
        reasons.append("accounts_invalid")
        accounts = []

    observations: list[dict[str, Any]] = []
    if not reasons:
        seen: set[str] = set()
        for index, account in enumerate(accounts):
            if not isinstance(account, Mapping):
                reasons.append(f"account_{index}_invalid")
                continue
            address = _text(account.get("address"))
            amount = _unsigned_integer_string(account.get("amount_raw"))
            decimals = _u8(account.get("decimals"))
            if address is None:
                reasons.append(f"account_{index}_address_invalid")
                continue
            if address in seen:
                reasons.append("duplicate_account_address")
                continue
            seen.add(address)
            if amount is None:
                reasons.append(f"account_{index}_amount_invalid")
                continue
            if decimals is None:
                reasons.append(f"account_{index}_decimals_invalid")
                continue
            assert mint is not None and slot is not None
            observations.append(
                build_evidence_observation(
                    chain=CHAIN,
                    fact_type="token_account_balance_base_units",
                    subject_id=f"mint:{mint}:token_account:{address}",
                    source=SOURCE,
                    source_role="canonical_onchain_concentration",
                    observed_at=None,
                    block_slot=slot,
                    raw_identifier=address,
                    raw_value=amount,
                    normalized_value=amount,
                    unit=TOKEN_BASE_UNITS,
                    calculation_version=f"solana-rpc-evidence-{VERSION}",
                    identity_verified=True,
                    semantics_verified=True,
                    freshness_verified=bool(freshness_verified),
                    warnings=[] if freshness_verified else ["freshness_not_verified"],
                )
            )

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return {
            "service": "solana_rpc_evidence_adapter",
            "version": VERSION,
            "evidence_ready": False,
            "cmis_promotable": False,
            "fact_type": "token_account_balance_base_units",
            "holder_count_fact_created": False,
            "observations": [],
            "rejection_reasons": reasons,
        }

    return {
        "service": "solana_rpc_evidence_adapter",
        "version": VERSION,
        "evidence_ready": True,
        "cmis_promotable": False,
        "fact_type": "token_account_balance_base_units",
        "holder_count_fact_created": False,
        "observations": observations,
        "rejection_reasons": [],
    }


__all__ = [
    "ADDRESS_OR_NULL",
    "BOOLEAN",
    "CHAIN",
    "COUNT",
    "PROGRAM_ID",
    "PROGRAM_LABEL",
    "SOURCE",
    "TOKEN_BASE_UNITS",
    "VERSION",
    "build_solana_largest_accounts_evidence",
    "build_solana_mint_state_evidence",
    "build_solana_supply_evidence",
]
