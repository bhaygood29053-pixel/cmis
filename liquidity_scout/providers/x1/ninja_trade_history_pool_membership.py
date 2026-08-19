"""Bind bounded X1.Ninja history rows to exact transaction/pool evidence.

This module is transport-free and intentionally layered on top of
``verify_ninja_trade_history_sample``. It consumes already-produced
``x1_transaction_pool_membership/v3`` evidence keyed by transaction signature
and upgrades only the narrow pool-membership facts that those proofs establish.

Provider row pool labels are not treated as proof. A sampled row is considered
on-chain verified for the selected pool only when its ``txHash`` is bound to a
valid positive membership proof for that exact pool. History completeness,
ordering, source independence, finality, amount/price semantics, and CMIS
promotion remain outside this contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.ninja_history import CHAIN
from liquidity_scout.providers.x1.ninja_trade_history_sample_evidence import (
    CONTRACT_VERSION as BASE_CONTRACT_VERSION,
    verify_ninja_trade_history_sample,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


CONTRACT_VERSION = "x1_ninja_trade_history_pool_membership/v1"
MEMBERSHIP_CONTRACT_VERSION = "x1_transaction_pool_membership/v3"
_UNRELATED_MEMBERSHIP_FIELDS = (
    "provider_row_pool_claim_verified",
    "source_independence_verified",
    "history_completeness_verified",
    "finality_semantics_verified",
    "amount_semantics_verified",
    "price_semantics_verified",
)


class X1NinjaTradeHistoryPoolMembershipError(ValueError):
    """Raised when supplied transaction/pool evidence is malformed or mismatched."""


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise X1NinjaTradeHistoryPoolMembershipError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise X1NinjaTradeHistoryPoolMembershipError(f"{name} is required")
    return text


def _strict_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise X1NinjaTradeHistoryPoolMembershipError(f"{name} must be a boolean")
    return value


def _non_negative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise X1NinjaTradeHistoryPoolMembershipError(
            f"{name} must be a non-negative integer"
        )
    return value


def _validate_membership_proof(
    *,
    signature: str,
    expected_pool: str,
    proof: Mapping[str, Any],
) -> bool:
    if proof.get("contract_version") != MEMBERSHIP_CONTRACT_VERSION:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof contract version is unsupported"
        )
    if proof.get("chain") != CHAIN:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof chain must be x1"
        )

    proof_signature = _required_text(
        "membership proof transaction_signature",
        proof.get("transaction_signature"),
    )
    if proof_signature != signature:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof transaction signature does not match sampled txHash"
        )

    proof_pool = _required_text(
        "membership proof pool_address", proof.get("pool_address")
    )
    if proof_pool != expected_pool:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof pool does not match selected verified pool"
        )

    instruction_evidence_bound = _strict_bool(
        "membership proof transaction_instruction_evidence_bound",
        proof.get("transaction_instruction_evidence_bound"),
    )
    transaction_found = _strict_bool(
        "membership proof transaction_found", proof.get("transaction_found")
    )
    transaction_succeeded = _strict_bool(
        "membership proof transaction_succeeded", proof.get("transaction_succeeded")
    )
    recognized_amm_invoked = _strict_bool(
        "membership proof recognized_amm_invoked",
        proof.get("recognized_amm_invoked"),
    )
    selected_instruction_verified = _strict_bool(
        "membership proof selected_pool_instruction_verified",
        proof.get("selected_pool_instruction_verified"),
    )
    asset_vault_mutated = _strict_bool(
        "membership proof asset_vault_mutated", proof.get("asset_vault_mutated")
    )
    counter_vault_mutated = _strict_bool(
        "membership proof counter_vault_mutated", proof.get("counter_vault_mutated")
    )
    vault_authority_verified = _strict_bool(
        "membership proof vault_authority_verified",
        proof.get("vault_authority_verified"),
    )
    membership_verified = _strict_bool(
        "membership proof transaction_pool_membership_verified",
        proof.get("transaction_pool_membership_verified"),
    )

    recognized_count = _non_negative_int(
        "membership proof recognized_amm_instruction_count",
        proof.get("recognized_amm_instruction_count"),
    )
    selected_count = _non_negative_int(
        "membership proof selected_pool_instruction_count",
        proof.get("selected_pool_instruction_count"),
    )
    if selected_count > recognized_count:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "selected pool instruction count cannot exceed recognized AMM count"
        )

    selected_evidence = proof.get("selected_pool_instruction_evidence")
    if (
        isinstance(selected_evidence, (str, bytes))
        or not isinstance(selected_evidence, Sequence)
        or any(not isinstance(item, Mapping) for item in selected_evidence)
    ):
        raise X1NinjaTradeHistoryPoolMembershipError(
            "selected pool instruction evidence must be a sequence of mappings"
        )
    if len(selected_evidence) != selected_count:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "selected pool instruction evidence count does not match declared count"
        )

    rejection_reasons = proof.get("rejection_reasons")
    if (
        isinstance(rejection_reasons, (str, bytes))
        or not isinstance(rejection_reasons, Sequence)
        or any(not isinstance(reason, str) or not reason for reason in rejection_reasons)
    ):
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof rejection_reasons must be a sequence of non-empty strings"
        )

    if membership_verified != (len(rejection_reasons) == 0):
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof verification flag disagrees with rejection reasons"
        )

    if proof.get("cmis_promotable") is not False:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "membership proof must preserve cmis_promotable=false"
        )
    for field in _UNRELATED_MEMBERSHIP_FIELDS:
        if field not in proof:
            raise X1NinjaTradeHistoryPoolMembershipError(
                f"membership proof {field} must be explicit"
            )
        if proof[field] is not None:
            raise X1NinjaTradeHistoryPoolMembershipError(
                f"membership proof {field} must remain unproven"
            )

    if membership_verified:
        positive_requirements = (
            instruction_evidence_bound,
            transaction_found,
            transaction_succeeded,
            recognized_amm_invoked,
            selected_instruction_verified,
            asset_vault_mutated,
            counter_vault_mutated,
            vault_authority_verified,
            recognized_count > 0,
            selected_count > 0,
        )
        if not all(positive_requirements):
            raise X1NinjaTradeHistoryPoolMembershipError(
                "positive membership proof is missing required structural evidence"
            )

    return membership_verified


def verify_ninja_trade_history_pool_membership(
    *,
    observation: Mapping[str, Any],
    verification_reports: Mapping[str, VerificationReport],
    transaction_pool_membership_evidence: Mapping[str, Mapping[str, Any]],
    pool_address: str,
    pool_identity_verified: bool,
    max_rows: int = 25,
) -> dict[str, Any]:
    """Bind a bounded Ninja sample to exact v3 transaction/pool membership proofs."""

    if not isinstance(transaction_pool_membership_evidence, Mapping):
        raise TypeError(
            "transaction_pool_membership_evidence must be a mapping keyed by signature"
        )

    base = verify_ninja_trade_history_sample(
        observation=observation,
        verification_reports=verification_reports,
        pool_address=pool_address,
        pool_identity_verified=pool_identity_verified,
        max_rows=max_rows,
    )
    if base.get("contract_version") != BASE_CONTRACT_VERSION:
        raise X1NinjaTradeHistoryPoolMembershipError(
            "unexpected base Ninja history evidence contract version"
        )

    expected_pool = _required_text("pool_address", base.get("pool_address"))
    enhanced_rows: list[dict[str, Any]] = []
    all_membership_verified = bool(base.get("sample_size", 0))
    all_provider_pool_claims_verified = bool(base.get("sample_size", 0))

    rows = base.get("rows")
    if not isinstance(rows, list):
        raise X1NinjaTradeHistoryPoolMembershipError(
            "base Ninja history rows must be a list"
        )

    for row in rows:
        if not isinstance(row, Mapping):
            raise X1NinjaTradeHistoryPoolMembershipError(
                "base Ninja history row evidence must be a mapping"
            )
        signature = _required_text("row transaction_id", row.get("transaction_id"))
        proof = transaction_pool_membership_evidence.get(signature)
        proof_present = proof is not None
        membership_verified = False

        if proof_present:
            if not isinstance(proof, Mapping):
                raise TypeError(
                    "transaction pool membership evidence values must be mappings"
                )
            membership_verified = _validate_membership_proof(
                signature=signature,
                expected_pool=expected_pool,
                proof=proof,
            )

        row_pool_matches = row.get("row_pool_matches_verified_pool_identity") is True
        provider_pool_claim_verified = bool(row_pool_matches and membership_verified)
        all_membership_verified = all_membership_verified and membership_verified
        all_provider_pool_claims_verified = (
            all_provider_pool_claims_verified and provider_pool_claim_verified
        )

        enhanced_row = dict(row)
        enhanced_row["transaction_pool_membership_evidence_present"] = proof_present
        enhanced_row["transaction_pool_membership_verified"] = membership_verified
        enhanced_row["provider_row_pool_claim_onchain_verified"] = (
            provider_pool_claim_verified
        )
        enhanced_rows.append(enhanced_row)

    warnings = [
        warning
        for warning in base.get("warnings", [])
        if warning != "transaction_pool_membership_not_verified"
    ]
    if not all_membership_verified:
        warnings.append("transaction_pool_membership_not_verified_for_every_sampled_row")
    if not all_provider_pool_claims_verified:
        warnings.append("provider_row_pool_claim_not_onchain_verified_for_every_sampled_row")

    semantics = dict(base.get("semantics", {}))
    semantics["transaction_pool_membership_verified"] = all_membership_verified
    semantics["provider_row_pool_claim_onchain_verified"] = (
        all_provider_pool_claims_verified
    )

    result = dict(base)
    result["contract_version"] = CONTRACT_VERSION
    result["base_contract_version"] = BASE_CONTRACT_VERSION
    result["membership_contract_version"] = MEMBERSHIP_CONTRACT_VERSION
    result["sample_transaction_pool_membership_verified"] = all_membership_verified
    result["sample_provider_row_pool_claim_onchain_verified"] = (
        all_provider_pool_claims_verified
    )
    result["rows"] = enhanced_rows
    result["semantics"] = semantics
    result["warnings"] = list(dict.fromkeys(warnings))
    result["cmis_promotable"] = False
    return result


__all__ = [
    "BASE_CONTRACT_VERSION",
    "CONTRACT_VERSION",
    "MEMBERSHIP_CONTRACT_VERSION",
    "X1NinjaTradeHistoryPoolMembershipError",
    "verify_ninja_trade_history_pool_membership",
]
