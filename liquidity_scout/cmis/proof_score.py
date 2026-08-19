"""Deterministic CMIS proof-strength scoring.

Proof strength is independent of market/risk severity.  Category scores describe
how well a conclusion is evidenced; they never change or reinterpret the risk
result itself.  Missing evidence is represented as UNKNOWN with ``score=None``
and lowers the aggregate proof strength through missing category coverage.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
CATEGORY_ORDER = (
    "identity",
    "semantics",
    "freshness",
    "source_independence",
    "agreement",
    "scope",
    "historical_coverage",
    "source_traceability",
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _category(
    *,
    state: str,
    score: int | None,
    reasons: list[str],
    evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "score": score,
        "reasons": reasons,
        "evidence_paths": sorted(set(evidence_paths or [])),
    }


def _flags_for(receipt: Mapping[str, Any], suffixes: tuple[str, ...]) -> dict[str, bool]:
    raw = receipt.get("evidence_flags")
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, bool] = {}
    for path, value in raw.items():
        text = str(path)
        if isinstance(value, bool) and any(text.endswith(suffix) for suffix in suffixes):
            result[text] = value
    return result


def _boolean_category(
    flags: Mapping[str, bool],
    *,
    verified_reason: str,
    failed_reason: str,
    unknown_reason: str,
) -> dict[str, Any]:
    if not flags:
        return _category(state="UNKNOWN", score=None, reasons=[unknown_reason])
    paths = list(flags)
    values = list(flags.values())
    if all(values):
        return _category(
            state="VERIFIED",
            score=100,
            reasons=[verified_reason],
            evidence_paths=paths,
        )
    if not any(values):
        return _category(
            state="UNVERIFIED",
            score=0,
            reasons=[failed_reason],
            evidence_paths=paths,
        )
    return _category(
        state="PARTIAL",
        score=50,
        reasons=[verified_reason, failed_reason],
        evidence_paths=paths,
    )


def _source_independence_category(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Score source independence only from explicit provenance verification.

    Distinct source labels and a verifier-shaped record are structural evidence
    only.  They do not prove that the sources have independent upstream lineage.
    CMIS therefore requires an explicit ``source_independence_verified`` evidence
    flag before this category can receive proof credit.
    """

    raw_sources = receipt.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    unique_source_names = {
        _text(item.get("source"))
        for item in sources
        if isinstance(item, Mapping) and _text(item.get("source")) is not None
    }
    verifier_records = [
        item
        for item in sources
        if isinstance(item, Mapping)
        and item.get("evidence_class") == "verifier_observation"
    ]
    independence_flags = _flags_for(receipt, ("source_independence_verified",))
    flag_paths = list(independence_flags)

    # Explicit failure must never be weakened to UNKNOWN merely because other
    # structural evidence is absent. Missing evidence and a failed proof gate
    # are different states.
    if independence_flags and not all(independence_flags.values()):
        return _category(
            state="UNVERIFIED",
            score=0,
            reasons=["one or more source independence gates are explicitly unverified"],
            evidence_paths=flag_paths,
        )

    if not unique_source_names:
        if independence_flags:
            return _category(
                state="UNVERIFIED",
                score=0,
                reasons=[
                    "source independence flag is present but source identity evidence is absent"
                ],
                evidence_paths=flag_paths,
            )
        return _category(
            state="UNKNOWN",
            score=None,
            reasons=["no source identity evidence supplied"],
            evidence_paths=flag_paths,
        )
    if len(unique_source_names) < 2:
        return _category(
            state="UNVERIFIED",
            score=0,
            reasons=["single-source evidence cannot establish source independence"],
            evidence_paths=flag_paths,
        )
    if not verifier_records:
        if independence_flags:
            return _category(
                state="UNVERIFIED",
                score=0,
                reasons=[
                    "source independence flag is present but verifier observation role is not established"
                ],
                evidence_paths=flag_paths,
            )
        return _category(
            state="UNKNOWN",
            score=None,
            reasons=[
                "multiple source identities are present but independent verifier provenance is not explicitly established"
            ],
        )
    if not independence_flags:
        return _category(
            state="UNKNOWN",
            score=None,
            reasons=[
                "distinct source labels and verifier roles do not prove source independence"
            ],
        )
    return _category(
        state="VERIFIED",
        score=100,
        reasons=["source independence is explicitly verified"],
        evidence_paths=flag_paths,
    )


def build_proof_score(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Score evidence categories without using risk or financial severity.

    ``None`` category scores mean evidence was not supplied.  The overall
    percentage treats those categories as unearned proof, so missing evidence
    weakens the aggregate result without converting missing facts to ``False``.
    """

    if not isinstance(receipt, Mapping):
        raise TypeError("CMIS proof score requires an evidence receipt mapping")

    identity = _boolean_category(
        _flags_for(receipt, ("identity_verified", "asset_identity_verified")),
        verified_reason="identity proof gates satisfied",
        failed_reason="one or more identity proof gates are explicitly unverified",
        unknown_reason="no explicit identity verification evidence supplied",
    )
    semantics = _boolean_category(
        _flags_for(receipt, ("semantics_verified", "field_semantics_verified")),
        verified_reason="semantic proof gates satisfied",
        failed_reason="one or more semantic proof gates are explicitly unverified",
        unknown_reason="no explicit semantics verification evidence supplied",
    )

    freshness_record = receipt.get("freshness")
    freshness_verified = (
        freshness_record.get("verified")
        if isinstance(freshness_record, Mapping)
        else None
    )
    if freshness_verified is True:
        freshness = _category(
            state="VERIFIED",
            score=100,
            reasons=["freshness verification gates satisfied"],
        )
    elif freshness_verified is False:
        freshness = _category(
            state="UNVERIFIED",
            score=0,
            reasons=["freshness is explicitly unverified"],
        )
    else:
        freshness = _category(
            state="UNKNOWN",
            score=None,
            reasons=["freshness verification evidence not supplied"],
        )

    source_independence = _source_independence_category(receipt)

    verification = receipt.get("verification")
    verification_status = (
        _text(verification.get("status"))
        if isinstance(verification, Mapping)
        else None
    )
    if verification_status == "AGREEMENT":
        agreement = _category(
            state="VERIFIED",
            score=100,
            reasons=["same-fact agreement recorded"],
        )
    elif verification_status == "CONFLICT":
        agreement = _category(
            state="CONFLICT",
            score=0,
            reasons=["same-fact evidence conflict recorded"],
        )
    elif verification_status == "INSUFFICIENT_EVIDENCE":
        agreement = _category(
            state="UNKNOWN",
            score=None,
            reasons=["same-fact agreement is not proven"],
        )
    else:
        agreement = _category(
            state="UNKNOWN",
            score=None,
            reasons=["no verification status supplied"],
        )

    scope_flags = _flags_for(
        receipt,
        (
            "scope_verified",
            "coverage_complete",
            "window_complete",
            "asset_window_complete",
            "global_onchain_pool_discovery_proven",
            "registry_globally_exhaustive",
        ),
    )
    scope_record = receipt.get("evidence_scope")
    explicit_scope = bool(
        isinstance(scope_record, Mapping)
        and scope_record.get("explicit_scope_available") is True
    )
    if scope_flags:
        scope = _boolean_category(
            scope_flags,
            verified_reason="explicit scope/completeness gates satisfied",
            failed_reason="one or more scope/completeness gates are explicitly unproven",
            unknown_reason="scope evidence not supplied",
        )
        if explicit_scope and scope["state"] == "UNVERIFIED":
            scope["state"] = "PARTIAL"
            scope["score"] = 25
            scope["reasons"].insert(0, "scope is named but completeness remains unproven")
    elif explicit_scope:
        scope = _category(
            state="PARTIAL",
            score=50,
            reasons=["evidence scope is explicit but completeness proof is not supplied"],
        )
    else:
        scope = _category(
            state="UNKNOWN",
            score=None,
            reasons=["evidence scope is not explicit"],
        )

    historical_flags = _flags_for(
        receipt,
        (
            "historical_coverage_verified",
            "archival_completeness_verified",
            "continuous_coverage_verified",
            "retention_verified",
            "history_range_complete",
        ),
    )
    historical_coverage = _boolean_category(
        historical_flags,
        verified_reason="historical coverage gates satisfied",
        failed_reason="historical/archival coverage is explicitly unproven",
        unknown_reason="no historical coverage proof supplied",
    )

    raw_sources = receipt.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    observation = receipt.get("observation")
    observed_times = (
        observation.get("observed_times")
        if isinstance(observation, Mapping)
        and isinstance(observation.get("observed_times"), list)
        else []
    )
    if sources and observed_times:
        source_traceability = _category(
            state="VERIFIED",
            score=100,
            reasons=["source identity and observation time are recorded"],
        )
    elif sources:
        source_traceability = _category(
            state="PARTIAL",
            score=50,
            reasons=["source identity is recorded but observation time is missing"],
        )
    else:
        source_traceability = _category(
            state="UNKNOWN",
            score=None,
            reasons=["source traceability evidence is missing"],
        )

    categories = {
        "identity": identity,
        "semantics": semantics,
        "freshness": freshness,
        "source_independence": source_independence,
        "agreement": agreement,
        "scope": scope,
        "historical_coverage": historical_coverage,
        "source_traceability": source_traceability,
    }

    earned = sum(
        category["score"] if category["score"] is not None else 0
        for category in categories.values()
    )
    scored_count = sum(
        1 for category in categories.values() if category["score"] is not None
    )
    total_categories = len(CATEGORY_ORDER)
    proof_percent = round(earned / total_categories, 2)
    category_coverage_percent = round(scored_count / total_categories * 100, 2)
    has_conflict = any(category["state"] == "CONFLICT" for category in categories.values())

    if not has_conflict and proof_percent >= 80 and category_coverage_percent >= 75:
        strength = "STRONG"
    elif not has_conflict and proof_percent >= 50 and category_coverage_percent >= 50:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    unknown_categories = [
        name for name, category in categories.items() if category["score"] is None
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "proof_strength": strength,
        "proof_percent": proof_percent,
        "category_coverage_percent": category_coverage_percent,
        "categories": categories,
        "unknown_categories": unknown_categories,
        "risk_considered": False,
        "risk_separate": True,
        "method": "deterministic_category_evidence_v1",
    }


__all__ = ["CATEGORY_ORDER", "SCHEMA_VERSION", "build_proof_score"]
