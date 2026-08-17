"""Sanitized observational comparison for X1 holder-looking provider fields.

This module compares only raw numeric relationships among one lexical
X1.Ninja holder-looking field and one mint-filtered X1 RPC token-account
enumeration candidate. It deliberately does not infer holder semantics,
coverage, freshness equivalence, wallet identity, beneficial ownership, or
CMIS promotion from matching or mismatching numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    RPC_METHOD as ENUMERATION_METHOD,
    RPC_SOURCE,
)


VERSION = "1.0"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _valid_count(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _valid_slot(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _candidate_value(holder_candidates: Mapping[str, Any], field_path: str) -> Any:
    values = holder_candidates.get("holder_field_candidates")
    if not isinstance(values, list):
        raise ValueError("holder candidate list is missing")
    matches = [
        item.get("raw_value")
        for item in values
        if isinstance(item, Mapping) and _text(item.get("field_path")) == field_path
    ]
    if len(matches) != 1:
        raise ValueError("holder field path must identify exactly one observed candidate")
    return matches[0]


def _metadata_mints(holder_candidates: Mapping[str, Any]) -> list[str]:
    metadata = holder_candidates.get("token_metadata_candidates")
    if not isinstance(metadata, Mapping):
        return []
    result: list[str] = []
    for role in ("base_token", "quote_token"):
        item = metadata.get(role)
        if isinstance(item, Mapping):
            mint = _text(item.get("address"))
            if mint is not None:
                result.append(mint)
    return list(dict.fromkeys(result))


def _digest_strings(values: list[str]) -> str:
    return sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def build_x1_holder_observational_comparison(
    holder_candidates: Mapping[str, Any],
    enumeration: Mapping[str, Any],
    *,
    expected_mint: Any,
    field_path: Any,
) -> dict[str, Any]:
    """Build a sanitized numeric comparison without assigning holder meaning."""
    if not isinstance(holder_candidates, Mapping):
        raise TypeError("holder_candidates must be a mapping")
    if not isinstance(enumeration, Mapping):
        raise TypeError("enumeration must be a mapping")

    mint = _text(expected_mint)
    path = _text(field_path)
    if mint is None:
        raise ValueError("expected_mint must not be empty")
    if path is None:
        raise ValueError("field_path must not be empty")

    if holder_candidates.get("chain") != "x1":
        raise ValueError("holder candidates must be for x1")
    if holder_candidates.get("service") != "x1_ninja_holder_candidates":
        raise ValueError("unexpected holder candidate service")
    if holder_candidates.get("status") == "error":
        raise ValueError("holder candidate observation was rejected")
    if holder_candidates.get("pool_identity_transport_consistent") is not True:
        raise ValueError("provider pool transport identity is unverified")

    forbidden_holder_claims = (
        "holder_field_semantics_verified",
        "holder_field_asset_binding_verified",
        "holder_uniqueness_semantics_verified",
        "holder_coverage_verified",
        "beneficial_owner_identity_verified",
        "cmis_promotable",
    )
    for name in forbidden_holder_claims:
        if holder_candidates.get(name) is not False:
            raise ValueError(f"unsupported provider semantic claim: {name}")

    provider_count = _candidate_value(holder_candidates, path)
    if not _valid_count(provider_count):
        raise ValueError("provider holder-looking field is not a nonnegative integer")

    metadata_mints = _metadata_mints(holder_candidates)
    provider_pool_contains_expected_mint = mint in metadata_mints
    if not provider_pool_contains_expected_mint:
        raise ValueError("expected mint is not present in provider pool token metadata")

    if enumeration.get("chain") != "x1":
        raise ValueError("enumeration must be for x1")
    if enumeration.get("source") != RPC_SOURCE:
        raise ValueError("enumeration source is invalid")
    if enumeration.get("method") != ENUMERATION_METHOD:
        raise ValueError("enumeration method is invalid")
    if _text(enumeration.get("mint")) != mint:
        raise ValueError("enumeration mint mismatch")
    if enumeration.get("returned_account_identity_verified") is not True:
        raise ValueError("returned account identity is unverified")
    if enumeration.get("token_account_semantics_verified") is not True:
        raise ValueError("token-account semantics are unverified")
    if enumeration.get("coverage") != "unverified":
        raise ValueError("enumeration coverage must remain unverified")

    for name in (
        "enumeration_complete",
        "truncation_absent_verified",
        "total_count_eligible",
        "holder_semantics_verified",
        "beneficial_owner_identity_verified",
        "cmis_promotable",
    ):
        if enumeration.get(name) is not False:
            raise ValueError(f"unsupported enumeration claim: {name}")

    slot = enumeration.get("slot")
    count = enumeration.get("account_count_candidate")
    accounts = enumeration.get("accounts")
    if not _valid_slot(slot):
        raise ValueError("enumeration slot is invalid")
    if not _valid_count(count):
        raise ValueError("enumeration count candidate is invalid")
    if not isinstance(accounts, list) or len(accounts) != count:
        raise ValueError("enumeration account list/count mismatch")

    authorities: list[str] = []
    authority_fields_complete = True
    for index, item in enumerate(accounts):
        if not isinstance(item, Mapping):
            raise ValueError(f"enumeration account {index} is malformed")
        if _text(item.get("mint")) != mint:
            raise ValueError("enumeration account mint mismatch")
        authority = _text(item.get("owner"))
        if authority is None:
            authority_fields_complete = False
        else:
            authorities.append(authority)

    unique_authorities = sorted(set(authorities)) if authority_fields_complete else []
    unique_authority_count = len(unique_authorities) if authority_fields_complete else None
    unique_authority_digest = (
        _digest_strings(unique_authorities) if authority_fields_complete else None
    )

    provider_vs_account_delta = count - provider_count
    provider_equals_account_count = provider_count == count
    provider_vs_authority_delta = (
        unique_authority_count - provider_count
        if unique_authority_count is not None
        else None
    )
    provider_equals_unique_authority_count = (
        provider_count == unique_authority_count
        if unique_authority_count is not None
        else None
    )

    warnings = [
        "numeric_relations_do_not_authenticate_provider_holder_semantics",
        "rpc_enumeration_totality_and_truncation_absence_are_unverified",
        "token_account_authorities_are_not_verified_beneficial_owners",
        "provider_and_rpc_freshness_equivalence_is_unverified",
    ]
    if not authority_fields_complete:
        warnings.append("token_account_authority_fields_incomplete")

    return {
        "service": "x1_holder_observational_comparison",
        "version": VERSION,
        "chain": "x1",
        "verification_status": "INSUFFICIENT_EVIDENCE",
        "comparison_semantics_verified": False,
        "pool_address": _text(holder_candidates.get("pool_address_requested")),
        "expected_mint": mint,
        "provider": {
            "source": "X1.Ninja",
            "observed_at": holder_candidates.get("provider_observed_at"),
            "field_path": path,
            "lexical_holder_count_candidate": provider_count,
            "pool_token_metadata_mints": metadata_mints,
            "pool_contains_expected_mint": True,
            "field_semantics_verified": False,
            "field_asset_binding_verified": False,
            "coverage_verified": False,
        },
        "rpc": {
            "source": RPC_SOURCE,
            "method": ENUMERATION_METHOD,
            "slot": slot,
            "token_account_count_candidate": count,
            "unique_token_account_authority_count_candidate": unique_authority_count,
            "unique_token_account_authority_set_sha256": unique_authority_digest,
            "authority_fields_present_for_all_returned_accounts": authority_fields_complete,
            "enumeration_complete": False,
            "truncation_absent_verified": False,
            "coverage": "unverified",
        },
        "numeric_relations": {
            "rpc_account_count_minus_provider_candidate": provider_vs_account_delta,
            "provider_candidate_equals_rpc_account_count": provider_equals_account_count,
            "rpc_unique_authority_count_minus_provider_candidate": provider_vs_authority_delta,
            "provider_candidate_equals_rpc_unique_authority_count": (
                provider_equals_unique_authority_count
            ),
        },
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
        "artifact_sanitized": True,
        "warnings": warnings,
    }


__all__ = ["VERSION", "build_x1_holder_observational_comparison"]
