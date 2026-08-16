"""CMIS v1.4.8 — canonical vault-family qualification for X1.

v1.4.7 established recurrent vault-pair family evidence across nested history
windows. v1.4.8 adds a stricter, read-only qualification gate: direct X1 RPC
must independently confirm the candidate asset token account, counter token
account, their mints, and their shared token-account authority.

Qualification is intentionally not canonical promotion. A uniquely qualified
family is a stronger candidate for later reserve/pool mapping proof, but this
module never sets canonical mapping or exact pool-leg promotion flags true.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc import (
    DEFAULT_X1_RPC_URL,
    X1RPCProvider,
)
from liquidity_scout.providers.x1.vault_pair_family_attribution import (
    evaluate_vault_pair_family_attribution,
)

VERSION = "1.4.8"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _family_dict(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    fields = {
        "asset_account": _text(raw.get("asset_account")),
        "counter_account": _text(raw.get("counter_account")),
        "counter_mint": _text(raw.get("counter_mint")),
        "shared_owner": _text(raw.get("shared_owner")),
    }
    if not all(fields.values()):
        return None
    return fields


def _safe_token_account_lookup(
    account: str,
    provider: Callable[[str], Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        raw = provider(account)
    except Exception as exc:
        return None, {
            "account": account,
            "error": f"{type(exc).__name__}: {exc}",
        }

    if not isinstance(raw, Mapping):
        return None, {
            "account": account,
            "error": "token-account provider returned no mapping evidence",
        }

    return dict(raw), None


def _account_evidence(
    record: Mapping[str, Any] | None,
    *,
    expected_mint: str,
    expected_authority: str,
) -> dict[str, Any]:
    record = dict(record) if isinstance(record, Mapping) else {}
    actual_mint = _text(record.get("mint"))
    actual_authority = _text(record.get("token_authority"))

    return {
        "account_exists": record.get("account_exists") is True,
        "identity_verified": record.get("identity_verified") is True,
        "expected_mint": expected_mint,
        "actual_mint": actual_mint,
        "mint_matches": bool(actual_mint and actual_mint == expected_mint),
        "expected_token_authority": expected_authority,
        "actual_token_authority": actual_authority,
        "token_authority_matches": bool(
            actual_authority and actual_authority == expected_authority
        ),
        "program_owner": _text(record.get("program_owner")),
        "parsed_type": _text(record.get("parsed_type")),
        "raw_amount": record.get("raw_amount"),
        "decimals": record.get("decimals"),
        "ui_amount_string": record.get("ui_amount_string"),
        "source": record.get("source"),
    }


def qualify_canonical_vault_family(
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    family_provider: Callable[..., Mapping[str, Any]] = (
        evaluate_vault_pair_family_attribution
    ),
    token_account_provider: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Qualify v1.4.7 recurrent families using direct token-account evidence.

    The result is fail-closed. At most one family may become the returned
    canonical vault-family candidate. Multiple independently qualified families
    remain ambiguous and no winner is selected.
    """

    pool_address = _text(pool_address)
    asset_mint = _text(asset_mint)
    if not pool_address:
        raise ValueError("pool_address is required")
    if not asset_mint:
        raise ValueError("asset_mint is required")

    try:
        end_epoch = float(end_epoch)
    except (TypeError, ValueError) as exc:
        raise ValueError("end_epoch must be numeric") from exc
    if end_epoch < 0:
        raise ValueError("end_epoch must be non-negative")

    family_kwargs = {
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "end_epoch": end_epoch,
        "pair": pair,
        "page_size": page_size,
        "max_signatures": max_signatures,
    }
    if rpc_url is not None:
        family_kwargs["rpc_url"] = rpc_url

    errors: list[dict[str, Any]] = []
    try:
        raw_family_report = family_provider(**family_kwargs)
    except Exception as exc:
        return {
            "service": "canonical_vault_family_qualification",
            "version": VERSION,
            "chain": "x1",
            "pool_address": pool_address,
            "pair": pair,
            "asset_mint": asset_mint,
            "status": "family_attribution_unavailable",
            "qualified_family_count": 0,
            "canonical_vault_family_candidate": None,
            "families": [],
            "summary": {
                "family_attribution_available": False,
                "all_requested_window_ranges_proven": False,
                "canonical_vault_family_qualified": False,
                "canonical_vault_mapping_proven": False,
                "canonical_vault_mapping_promoted": False,
                "exact_pool_leg_semantics_promoted": False,
            },
            "errors": [
                {
                    "stage": "family_attribution",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            ],
        }

    family_report = (
        dict(raw_family_report)
        if isinstance(raw_family_report, Mapping)
        else {}
    )
    summary = family_report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    all_ranges_proven = (
        summary.get("all_requested_window_ranges_proven") is True
    )

    raw_families = family_report.get("families")
    raw_families = (
        raw_families
        if isinstance(raw_families, Sequence)
        and not isinstance(raw_families, (str, bytes))
        else []
    )

    if token_account_provider is None:
        rpc = X1RPCProvider(rpc_url=rpc_url or DEFAULT_X1_RPC_URL)
        token_account_provider = rpc.get_token_account_info

    family_results: list[dict[str, Any]] = []
    qualified: list[dict[str, Any]] = []

    for index, raw_family in enumerate(raw_families):
        raw_family = raw_family if isinstance(raw_family, Mapping) else {}
        family = _family_dict(raw_family.get("family"))
        recurrent = raw_family.get("recurrent_pair_family_observed") is True
        structural_conflict = (
            raw_family.get("structural_layout_conflict_observed") is True
        )

        rejection_reasons: list[str] = []
        if family is None:
            rejection_reasons.append("family_identity_incomplete")
        if not all_ranges_proven:
            rejection_reasons.append("history_range_unproven")
        if not recurrent:
            rejection_reasons.append("family_not_recurrent")
        if structural_conflict:
            rejection_reasons.append("structural_layout_conflict")

        asset_record = None
        counter_record = None
        asset_error = None
        counter_error = None

        eligible_for_rpc = family is not None and not rejection_reasons
        if eligible_for_rpc:
            asset_record, asset_error = _safe_token_account_lookup(
                family["asset_account"],
                token_account_provider,
            )
            counter_record, counter_error = _safe_token_account_lookup(
                family["counter_account"],
                token_account_provider,
            )

            if asset_error:
                errors.append(
                    {
                        "stage": "asset_token_account",
                        "family_index": index,
                        **asset_error,
                    }
                )
            if counter_error:
                errors.append(
                    {
                        "stage": "counter_token_account",
                        "family_index": index,
                        **counter_error,
                    }
                )

        expected_owner = family["shared_owner"] if family else ""
        expected_counter_mint = family["counter_mint"] if family else ""

        asset_evidence = _account_evidence(
            asset_record,
            expected_mint=asset_mint,
            expected_authority=expected_owner,
        )
        counter_evidence = _account_evidence(
            counter_record,
            expected_mint=expected_counter_mint,
            expected_authority=expected_owner,
        )

        if eligible_for_rpc:
            if asset_error is not None:
                rejection_reasons.append("asset_rpc_evidence_unavailable")
            if counter_error is not None:
                rejection_reasons.append("counter_rpc_evidence_unavailable")

            if asset_error is None:
                if not asset_evidence["account_exists"]:
                    rejection_reasons.append("asset_account_missing")
                if not asset_evidence["identity_verified"]:
                    rejection_reasons.append("asset_identity_unverified")
                if not asset_evidence["mint_matches"]:
                    rejection_reasons.append("asset_mint_mismatch")
                if not asset_evidence["token_authority_matches"]:
                    rejection_reasons.append("asset_authority_mismatch")

            if counter_error is None:
                if not counter_evidence["account_exists"]:
                    rejection_reasons.append("counter_account_missing")
                if not counter_evidence["identity_verified"]:
                    rejection_reasons.append("counter_identity_unverified")
                if not counter_evidence["mint_matches"]:
                    rejection_reasons.append("counter_mint_mismatch")
                if not counter_evidence["token_authority_matches"]:
                    rejection_reasons.append("counter_authority_mismatch")

        # Keep rejection reasons deterministic and non-duplicated.
        rejection_reasons = list(dict.fromkeys(rejection_reasons))
        is_qualified = not rejection_reasons

        result = {
            "family": family,
            "recurrent_pair_family_observed": recurrent,
            "all_requested_window_ranges_proven": all_ranges_proven,
            "structural_layout_conflict_observed": structural_conflict,
            "asset_account_evidence": asset_evidence,
            "counter_account_evidence": counter_evidence,
            "shared_authority_verified": bool(
                asset_evidence["token_authority_matches"]
                and counter_evidence["token_authority_matches"]
            ),
            "qualified_candidate": is_qualified,
            "rejection_reasons": rejection_reasons,
            "canonical_family_proven": False,
            "canonical_family_promoted": False,
        }
        family_results.append(result)
        if is_qualified:
            qualified.append(result)

    unique = len(qualified) == 1
    candidate = qualified[0]["family"] if unique else None

    if len(qualified) > 1:
        status = "ambiguous_qualified_families"
    elif unique:
        status = "qualified_candidate_observed"
    elif not all_ranges_proven:
        status = "insufficient_family_evidence"
    else:
        status = "no_qualified_family"

    return {
        "service": "canonical_vault_family_qualification",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "qualified_family_count": len(qualified),
        "canonical_vault_family_candidate": candidate,
        "families": family_results,
        "summary": {
            "family_attribution_available": True,
            "all_requested_window_ranges_proven": all_ranges_proven,
            "unique_qualified_family": unique,
            "canonical_vault_family_qualified": unique,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.8 qualifies recurrent vault-pair families only when "
                "direct X1 RPC independently confirms both token-account "
                "identities, expected mints, and the shared token-account "
                "authority. Multiple qualified families remain ambiguous. "
                "Qualification is not canonical vault promotion; reserve/pool "
                "mapping proof remains a later gate."
            ),
        },
        "family_attribution": family_report,
        "errors": errors,
    }


__all__ = [
    "VERSION",
    "qualify_canonical_vault_family",
]
