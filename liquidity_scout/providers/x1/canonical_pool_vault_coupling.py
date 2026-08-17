"""CMIS v1.4.9 — canonical X1 pool-vault coupling proof.

v1.4.8 proves that recurrent candidate account pairs are real token accounts
with the expected mints and shared token-account authority. Live ANL/XNT
validation showed why that is not yet enough: many ordinary trader account
pairs can satisfy those identity checks.

v1.4.9 therefore asks a stricter question:

    Which v1.4.8-qualified family is structurally coupled to every recognized
    AMM instruction for the selected pool across the full 1h/6h/24h proof set?

A canonical mapping is proven only when exactly one qualified family:
- is present in every required history window;
- appears in 100% of recognized selected-pool AMM transactions in each window;
- is a stable directional pair candidate in each window;
- keeps qualifying opposite-flow evidence in each window;
- has no cross-window structural-layout conflict; and
- has a stable recognized program + pool-account instruction position across
  every direction with sufficient cross-window evidence.

This is intentionally stricter than ranking or balance heuristics. Token
balances, liquidity size, rank, and "largest account wins" are never used to
select a canonical family. Ambiguity fails closed.

v1.4.9 may prove the canonical pool-to-vault mapping. It still does not promote
that mapping into execution semantics, and it does not promote exact pool-leg
semantics. No signing or transaction execution occurs here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.canonical_vault_family_qualification import (
    qualify_canonical_vault_family,
)

VERSION = "1.4.9"
REQUIRED_WINDOWS = ("1h", "6h", "24h")
REQUIRED_POOL_INSTRUCTION_COVERAGE_RATIO = 1.0
MIN_DIRECTION_EVIDENCE_WINDOWS = 2


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _family_dict(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    family = {
        "asset_account": _text(raw.get("asset_account")),
        "counter_account": _text(raw.get("counter_account")),
        "counter_mint": _text(raw.get("counter_mint")),
        "shared_owner": _text(raw.get("shared_owner")),
    }
    return family if all(family.values()) else None


def _family_key(raw: Any) -> tuple[str, str, str, str] | None:
    family = _family_dict(raw)
    if family is None:
        return None
    return (
        family["asset_account"],
        family["counter_account"],
        family["counter_mint"],
        family["shared_owner"],
    )


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _attribution_family_index(report: Mapping[str, Any]) -> dict[tuple, dict[str, Any]]:
    index: dict[tuple, dict[str, Any]] = {}
    for raw in _sequence(report.get("families")):
        if not isinstance(raw, Mapping):
            continue
        key = _family_key(raw.get("family"))
        if key is not None:
            index[key] = dict(raw)
    return index


def _window_index(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in _sequence(report.get("windows")):
        if not isinstance(raw, Mapping):
            continue
        label = _text(raw.get("label"))
        if label:
            out[label] = dict(raw)
    return out


def _candidate_for_family(window: Mapping[str, Any], key: tuple) -> dict[str, Any] | None:
    for raw in _sequence(window.get("candidates")):
        if not isinstance(raw, Mapping):
            continue
        if _family_key(raw.get("family")) == key:
            return dict(raw)
    return None


def _window_coupling_evidence(
    *,
    window: Mapping[str, Any] | None,
    label: str,
    key: tuple,
) -> dict[str, Any]:
    window = dict(window) if isinstance(window, Mapping) else {}
    candidate = _candidate_for_family(window, key) if window else None
    candidate = candidate if isinstance(candidate, Mapping) else {}

    coverage = _number(
        candidate.get("recognized_pool_instruction_transaction_ratio")
    )
    full_coverage = bool(
        coverage is not None
        and coverage >= REQUIRED_POOL_INSTRUCTION_COVERAGE_RATIO
    )
    range_proven = window.get("range_proven") is True
    integrity_verified = window.get("integrity_verified") is True
    stable_pair = candidate.get("stable_directional_pair_candidate") is True
    raw_structural_stable = candidate.get(
        "stable_structural_directional_pair_candidate"
    )
    structural_stable_pair = (
        stable_pair
        if raw_structural_stable is None
        else raw_structural_stable is True
    )
    qualifying_flow = candidate.get("qualifying_family_evidence") is True
    present = bool(candidate)

    coupled = bool(
        present
        and range_proven
        and integrity_verified
        and full_coverage
        and structural_stable_pair
        and qualifying_flow
    )

    return {
        "window": label,
        "candidate_present": present,
        "range_proven": range_proven,
        "integrity_verified": integrity_verified,
        "transaction_occurrence_count": int(
            candidate.get("transaction_occurrence_count") or 0
        ),
        "recognized_pool_instruction_transaction_ratio": coverage,
        "required_pool_instruction_transaction_ratio": (
            REQUIRED_POOL_INSTRUCTION_COVERAGE_RATIO
        ),
        "full_pool_instruction_coverage": full_coverage,
        "stable_directional_pair_candidate": stable_pair,
        "stable_structural_directional_pair_candidate": (
            structural_stable_pair
        ),
        "qualifying_family_evidence": qualifying_flow,
        "is_leading_candidate": candidate.get("is_leading_candidate") is True,
        "pool_instruction_coupled": coupled,
    }


def _structural_anchor_evidence(family_record: Mapping[str, Any] | None) -> dict[str, Any]:
    family_record = (
        dict(family_record) if isinstance(family_record, Mapping) else {}
    )
    directions = []
    anchors = []
    conflict = family_record.get("structural_layout_conflict_observed") is True
    insufficient_or_unstable = False

    for raw in _sequence(family_record.get("directions")):
        if not isinstance(raw, Mapping):
            continue
        direction = _text(raw.get("direction"))
        evidence_windows = int(raw.get("evidence_window_count") or 0)
        direction_conflict = raw.get("structural_layout_conflict_observed") is True
        cross_window_consistent = (
            raw.get("cross_window_dominant_structural_layout_consistent") is True
        )
        fingerprint = raw.get("stable_dominant_structural_fingerprint")
        fingerprint = fingerprint if isinstance(fingerprint, Mapping) else {}
        program_id = _text(fingerprint.get("program_id"))
        pool_position = fingerprint.get("pool_position")
        asset_position = fingerprint.get("asset_position")
        counter_position = fingerprint.get("counter_position")
        positions_valid = bool(
            isinstance(pool_position, int)
            and not isinstance(pool_position, bool)
            and pool_position >= 0
            and isinstance(asset_position, int)
            and not isinstance(asset_position, bool)
            and asset_position >= 0
            and isinstance(counter_position, int)
            and not isinstance(counter_position, bool)
            and counter_position >= 0
            and len({pool_position, asset_position, counter_position}) == 3
        )

        has_sufficient_cross_window_evidence = (
            evidence_windows >= MIN_DIRECTION_EVIDENCE_WINDOWS
        )
        anchor_usable = bool(
            has_sufficient_cross_window_evidence
            and cross_window_consistent
            and not direction_conflict
            and program_id
            and positions_valid
        )

        if has_sufficient_cross_window_evidence and not anchor_usable:
            insufficient_or_unstable = True
        if direction_conflict:
            conflict = True

        row = {
            "direction": direction,
            "evidence_window_count": evidence_windows,
            "minimum_direction_evidence_windows": (
                MIN_DIRECTION_EVIDENCE_WINDOWS
            ),
            "cross_window_structural_layout_consistent": (
                cross_window_consistent
            ),
            "structural_layout_conflict_observed": direction_conflict,
            "program_id": program_id,
            "pool_position": pool_position,
            "asset_position": asset_position,
            "counter_position": counter_position,
            "positions_valid": positions_valid,
            "usable_pool_anchor": anchor_usable,
        }
        directions.append(row)
        if anchor_usable:
            anchors.append(row)

    program_ids = {row["program_id"] for row in anchors if row["program_id"]}
    pool_positions = {row["pool_position"] for row in anchors}
    program_consistent = len(program_ids) == 1
    pool_position_consistent = len(pool_positions) == 1
    anchor_verified = bool(
        anchors
        and not conflict
        and not insufficient_or_unstable
        and program_consistent
        and pool_position_consistent
    )

    return {
        "direction_evidence": directions,
        "usable_direction_anchor_count": len(anchors),
        "structural_layout_conflict_observed": conflict,
        "sufficient_direction_layout_unstable": insufficient_or_unstable,
        "recognized_program_consistent": program_consistent,
        "pool_position_consistent": pool_position_consistent,
        "stable_program_id": next(iter(program_ids)) if program_consistent else None,
        "stable_pool_position": (
            next(iter(pool_positions)) if pool_position_consistent else None
        ),
        "structural_pool_anchor_verified": anchor_verified,
    }


def _base_unavailable_result(
    *,
    pool_address: str,
    asset_mint: str,
    pair: str | None,
    error: Exception,
) -> dict[str, Any]:
    return {
        "service": "canonical_pool_vault_coupling",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": "vault_family_qualification_unavailable",
        "pool_coupled_family_count": 0,
        "canonical_vault_mapping_candidate": None,
        "families": [],
        "summary": {
            "vault_family_qualification_available": False,
            "all_requested_window_ranges_proven": False,
            "qualified_family_count": 0,
            "unique_pool_coupled_family": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
        },
        "qualification": None,
        "errors": [
            {
                "stage": "vault_family_qualification",
                "error": f"{type(error).__name__}: {error}",
            }
        ],
    }


def prove_canonical_pool_vault_coupling(
    *,
    pool_address: str,
    asset_mint: str,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    qualifier_provider: Callable[..., Mapping[str, Any]] = (
        qualify_canonical_vault_family
    ),
) -> dict[str, Any]:
    """Prove one uniquely pool-coupled family from v1.4.8-qualified evidence."""

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

    kwargs = {
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "end_epoch": end_epoch,
        "pair": pair,
        "page_size": page_size,
        "max_signatures": max_signatures,
    }
    if rpc_url is not None:
        kwargs["rpc_url"] = rpc_url

    try:
        raw_qualification = qualifier_provider(**kwargs)
    except Exception as exc:
        return _base_unavailable_result(
            pool_address=pool_address,
            asset_mint=asset_mint,
            pair=pair,
            error=exc,
        )

    qualification = (
        dict(raw_qualification) if isinstance(raw_qualification, Mapping) else {}
    )
    qualification_summary = qualification.get("summary")
    qualification_summary = (
        qualification_summary
        if isinstance(qualification_summary, Mapping)
        else {}
    )
    all_ranges_proven = (
        qualification_summary.get("all_requested_window_ranges_proven") is True
    )

    attribution = qualification.get("family_attribution")
    attribution = dict(attribution) if isinstance(attribution, Mapping) else {}
    attribution_families = _attribution_family_index(attribution)
    windows = _window_index(attribution)

    raw_qualified = []
    for raw in _sequence(qualification.get("families")):
        if not isinstance(raw, Mapping):
            continue
        if raw.get("qualified_candidate") is True:
            raw_qualified.append(dict(raw))

    family_results = []
    coupled = []

    for raw in raw_qualified:
        family = _family_dict(raw.get("family"))
        key = _family_key(family)
        rejection_reasons = []

        if family is None or key is None:
            rejection_reasons.append("family_identity_incomplete")
            family_record = None
        else:
            family_record = attribution_families.get(key)
            if family_record is None:
                rejection_reasons.append("family_attribution_identity_missing")

        if not all_ranges_proven:
            rejection_reasons.append("history_range_unproven")
        if raw.get("recurrent_pair_family_observed") is not True:
            rejection_reasons.append("family_not_recurrent")
        if raw.get("structural_layout_conflict_observed") is True:
            rejection_reasons.append("structural_layout_conflict")

        window_evidence = []
        if key is not None:
            for label in REQUIRED_WINDOWS:
                evidence = _window_coupling_evidence(
                    window=windows.get(label),
                    label=label,
                    key=key,
                )
                window_evidence.append(evidence)
                if not evidence["candidate_present"]:
                    rejection_reasons.append(f"{label}_candidate_missing")
                elif not evidence["range_proven"] or not evidence["integrity_verified"]:
                    rejection_reasons.append(f"{label}_history_unproven")
                elif not evidence["full_pool_instruction_coverage"]:
                    rejection_reasons.append(f"{label}_pool_instruction_coverage_incomplete")
                elif not evidence[
                    "stable_structural_directional_pair_candidate"
                ]:
                    rejection_reasons.append(f"{label}_directional_pair_unstable")
                elif not evidence["qualifying_family_evidence"]:
                    rejection_reasons.append(f"{label}_opposite_flow_unqualified")

        structural = _structural_anchor_evidence(family_record)
        if not structural["structural_pool_anchor_verified"]:
            if structural["structural_layout_conflict_observed"]:
                rejection_reasons.append("structural_layout_conflict")
            if structural["sufficient_direction_layout_unstable"]:
                rejection_reasons.append("cross_window_direction_layout_unstable")
            if not structural["recognized_program_consistent"]:
                rejection_reasons.append("recognized_program_inconsistent")
            if not structural["pool_position_consistent"]:
                rejection_reasons.append("pool_position_inconsistent")
            if structural["usable_direction_anchor_count"] == 0:
                rejection_reasons.append("structural_pool_anchor_unproven")

        rejection_reasons = list(dict.fromkeys(rejection_reasons))
        all_windows_coupled = bool(
            len(window_evidence) == len(REQUIRED_WINDOWS)
            and all(item["pool_instruction_coupled"] for item in window_evidence)
        )
        is_coupled = bool(
            not rejection_reasons
            and all_windows_coupled
            and structural["structural_pool_anchor_verified"]
        )

        result = {
            "family": family,
            "v1_4_8_qualified": True,
            "required_windows": list(REQUIRED_WINDOWS),
            "window_coupling": window_evidence,
            "all_required_windows_pool_coupled": all_windows_coupled,
            "structural_pool_anchor": structural,
            "canonical_pool_vault_coupling_proven": is_coupled,
            "rejection_reasons": rejection_reasons,
            "canonical_vault_mapping_proven": is_coupled,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
        }
        family_results.append(result)
        if is_coupled:
            coupled.append(result)

    unique = len(coupled) == 1
    candidate = coupled[0]["family"] if unique else None

    if not all_ranges_proven:
        status = "insufficient_coupling_evidence"
    elif not raw_qualified:
        status = "no_qualified_vault_families"
    elif len(coupled) > 1:
        status = "ambiguous_pool_vault_coupling"
    elif unique:
        status = "canonical_pool_vault_coupling_proven"
    else:
        status = "no_pool_vault_coupling_proven"

    return {
        "service": "canonical_pool_vault_coupling",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "pool_coupled_family_count": len(coupled),
        "canonical_vault_mapping_candidate": candidate,
        "thresholds": {
            "required_windows": list(REQUIRED_WINDOWS),
            "required_pool_instruction_transaction_ratio": (
                REQUIRED_POOL_INSTRUCTION_COVERAGE_RATIO
            ),
            "minimum_direction_evidence_windows": (
                MIN_DIRECTION_EVIDENCE_WINDOWS
            ),
        },
        "families": family_results,
        "summary": {
            "vault_family_qualification_available": bool(qualification),
            "all_requested_window_ranges_proven": all_ranges_proven,
            "qualified_family_count": len(raw_qualified),
            "pool_coupled_family_count": len(coupled),
            "unique_pool_coupled_family": unique,
            "canonical_vault_mapping_proven": unique,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.9 proves canonical pool-vault coupling only when exactly "
                "one v1.4.8-qualified family is present in 100% of recognized "
                "selected-pool AMM transactions in each 1h/6h/24h proof window, "
                "remains a stable directional pair with qualifying opposite "
                "flow, and preserves a stable recognized program plus pool "
                "instruction position across sufficient directional evidence. "
                "Balances and candidate ranking are not proof inputs. Mapping "
                "promotion and exact pool-leg semantics remain disabled."
            ),
        },
        "qualification": qualification,
        "errors": list(qualification.get("errors") or []),
    }


__all__ = [
    "MIN_DIRECTION_EVIDENCE_WINDOWS",
    "REQUIRED_POOL_INSTRUCTION_COVERAGE_RATIO",
    "REQUIRED_WINDOWS",
    "VERSION",
    "prove_canonical_pool_vault_coupling",
]
