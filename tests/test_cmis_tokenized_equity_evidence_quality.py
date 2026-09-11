from copy import deepcopy

import pytest

from liquidity_scout.services.cmis_tokenized_equity_evidence_quality import (
    TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT,
    build_tokenized_equity_evidence_quality,
)
from liquidity_scout.services.cmis_tokenized_equity_market_activity import (
    METRIC_SEMANTICS,
    REQUIRED_METRICS,
    build_tokenized_equity_market_activity,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    build_tokenized_equity_provenance,
)
from liquidity_scout.services.cmis_tokenized_equity_rights import (
    REQUIRED_DIMENSIONS,
    build_tokenized_equity_rights,
)


def provenance():
    return build_tokenized_equity_provenance(
        token={"chain": "x1", "asset_id": "EquityMint111", "asset_id_kind": "mint"},
        underlying_security={"security_id": "US0000000001", "security_id_kind": "isin"},
        representation_type="tokenized_security_representation",
        issuer={"name": "Example Issuer"},
        evidence_ids=["legacy-reference-only"],
    )


def rights_record(base=None):
    base = base or provenance()
    dimensions = {
        name: {"state": "UNKNOWN", "summary": "Not established.", "evidence": []}
        for name in REQUIRED_DIMENSIONS
    }
    dimensions["voting_rights"] = {
        "state": "DENIED",
        "summary": "Governing terms deny voting rights.",
        "evidence": [
            {
                "evidence_id": "upstream-rights-id",
                "source_class": "official_terms",
                "source_url": "https://issuer.example/terms",
                "document_id": "terms-v1",
                "section": "Voting Rights",
                "fact_time": "2026-09-01T00:00:00Z",
                "retrieved_at": "2026-09-10T20:00:00Z",
                "content_sha256": "a" * 64,
            }
        ],
    }
    return build_tokenized_equity_rights(
        tokenized_equity_provenance=base,
        dimensions=dimensions,
    )


def market_record(base=None, *, stale=False):
    base = base or provenance()
    metrics = {}
    for name in REQUIRED_METRICS:
        semantic = "reference_price" if name == "price_usd" else METRIC_SEMANTICS[name]
        metrics[name] = {"state": "UNKNOWN", "semantic": semantic}

    source = {
        "provider_id": "bounded-indexer",
        "source_class": "indexer",
        "source_url": "https://indexer.example/observation/1",
        "observation_id": "obs-1",
        "retrieved_at": "2026-09-10T20:10:00Z",
        "content_sha256": "b" * 64,
    }
    fact_time = "2026-09-10T19:00:00Z" if stale else "2026-09-10T20:09:00Z"
    metrics["price_usd"] = {
        "state": "OBSERVED",
        "semantic": "reference_price",
        "value": "25.50",
        "fact_time": fact_time,
        "sources": [source],
    }
    metrics["trade_count"] = {
        "state": "OBSERVED",
        "semantic": METRIC_SEMANTICS["trade_count"],
        "value": 0,
        "window_start": "2026-09-09T20:10:00Z",
        "window_end": "2026-09-10T20:10:00Z",
        "sources": [{**source, "observation_id": "obs-trades", "content_sha256": "c" * 64}],
    }
    return build_tokenized_equity_market_activity(
        tokenized_equity_provenance=base,
        scope={
            "scope_kind": "pool",
            "chain": "x1",
            "scope_id": "Pool111",
            "scope_id_kind": "address",
            "program_id": "DexProgram111",
            "coverage_complete_for_scope": True,
            "coverage_basis": "bounded exact-pool scan",
        },
        metrics=metrics,
        evaluated_at="2026-09-10T20:10:00Z",
        max_age_seconds=300,
    )


def test_receipts_are_content_addressed_and_deterministic():
    p = provenance()
    r = rights_record(p)
    m = market_record(p)
    first = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_rights=r,
        tokenized_equity_market_activity=m,
    )
    second = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=deepcopy(p),
        tokenized_equity_rights=deepcopy(r),
        tokenized_equity_market_activity=deepcopy(m),
    )
    assert first == second
    assert first["contract"] == TOKENIZED_EQUITY_EVIDENCE_QUALITY_CONTRACT
    assert all(item["receipt_id"].startswith("rwa_component_") for item in first["component_receipts"])
    assert all(item["receipt_id"].startswith("rwa_evidence_") for item in first["evidence_receipts"])
    assert len({item["receipt_id"] for item in first["evidence_receipts"]}) == len(first["evidence_receipts"])


def test_caller_receipt_ids_cannot_replace_derived_identity():
    p = provenance()
    r = rights_record(p)
    r["dimensions"]["voting_rights"]["evidence"][0]["receipt_id"] = "attacker-controlled"
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_rights=r,
    )
    receipt = next(item for item in result["evidence_receipts"] if item["claim_path"] == "rights.voting_rights")
    assert receipt["receipt_id"] != "attacker-controlled"
    assert result["boundaries"]["caller_supplied_receipt_id_authorized"] is False
    assert result["boundaries"]["caller_fact_or_evidence_substitution_for_promoted_runtime_authorized"] is False


def test_exact_subject_mismatch_fails_closed():
    p = provenance()
    r = rights_record(p)
    r["provenance"]["token"]["asset_id"] = "DifferentMint"
    with pytest.raises(ValueError, match="subject must exactly match"):
        build_tokenized_equity_evidence_quality(
            tokenized_equity_provenance=p,
            tokenized_equity_rights=r,
        )


def test_rights_retrieval_time_never_manufactures_freshness():
    p = provenance()
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_rights=rights_record(p),
    )
    receipt = next(item for item in result["evidence_receipts"] if item["claim_path"] == "rights.voting_rights")
    assert receipt["fact_time"] == "2026-09-01T00:00:00Z"
    assert receipt["retrieved_at"] == "2026-09-10T20:00:00Z"
    assert receipt["freshness"]["state"] == "UNKNOWN"
    assert receipt["source_authority"] == "AUTHORITATIVE_FOR_COMPONENT_CLAIM"
    assert result["freshness"]["policy"]["retrieval_time_alone_proves_freshness"] is False


def test_market_freshness_is_inherited_from_fact_time_policy():
    p = provenance()
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_market_activity=market_record(p),
    )
    price = next(item for item in result["evidence_receipts"] if item["claim_path"] == "market.price_usd")
    trades = next(item for item in result["evidence_receipts"] if item["claim_path"] == "market.trade_count")
    assert price["freshness"]["state"] == "FRESH"
    assert trades["freshness"]["state"] == "FRESH"
    assert result["freshness"]["fresh_receipt_count"] == 2


def test_stale_market_fact_stays_stale_even_when_retrieved_recently():
    p = provenance()
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_market_activity=market_record(p, stale=True),
    )
    price = next(item for item in result["evidence_receipts"] if item["claim_path"] == "market.price_usd")
    assert price["retrieved_at"] == "2026-09-10T20:10:00Z"
    assert price["freshness"]["state"] == "STALE"
    assert result["freshness"]["stale_receipt_count"] == 1


def test_missing_market_evidence_is_unknown_not_zero_filled():
    p = provenance()
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_market_activity=market_record(p),
    )
    assert "market.liquidity_usd" in result["unresolved_fields"]
    assert "market.transfer_count" in result["unresolved_fields"]
    assert result["verification"]["missing_evidence_zero_filled"] is False
    assert not any(item["claim_path"] == "market.liquidity_usd" for item in result["evidence_receipts"])


def test_bounded_zero_trade_count_does_not_become_global_agreement_or_activity_claim():
    p = provenance()
    m = market_record(p)
    assert m["metrics"]["trade_count"]["value"] == 0
    assert m["metrics"]["trade_count"]["bounded_zero_observed"] is True
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_market_activity=m,
    )
    assert result["verification"]["global_agreement_inferred"] is False
    assert result["conflict_evidence"]["absence_of_recorded_conflict_proves_agreement"] is False


def test_conflict_absence_remains_unknown_not_agreement():
    result = build_tokenized_equity_evidence_quality(tokenized_equity_provenance=provenance())
    assert result["conflict_evidence"]["state"] == "UNKNOWN"
    assert result["conflict_evidence"]["conflicts"] == []
    assert result["conflict_evidence"]["conflict_detection_complete"] is False
    assert result["confidence_inputs"]["same_fact_agreement_verified"] is False


def test_legacy_provenance_evidence_ids_are_references_not_content_receipts():
    result = build_tokenized_equity_evidence_quality(tokenized_equity_provenance=provenance())
    assert result["evidence_receipts"] == []
    assert "provenance.source_evidence_content_addressing" in result["unresolved_fields"]
    assert result["confidence_inputs"]["evidence_receipt_count"] == 0


def test_public_foundation_does_not_compute_proof_score_or_risk():
    p = provenance()
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_rights=rights_record(p),
        tokenized_equity_market_activity=market_record(p),
    )
    confidence = result["confidence_inputs"]
    assert confidence["proof_score"] is None
    assert confidence["proof_score_owned_by_protected_runtime"] is True
    assert confidence["risk_considered"] is False
    assert confidence["legal_effect_adjudicated"] is False
    assert result["boundaries"]["proof_score_equals_risk"] is False
    assert result["boundaries"]["confidence_equals_legal_conclusion"] is False
    assert result["boundaries"]["proof_score_calculation_authorized_in_public_foundation"] is False
    assert result["public_service_promoted"] is False
    assert result["scout_reliance_promoted"] is False
    assert result["execution_authorized"] is False


def test_distinct_source_labels_do_not_manufacture_source_independence():
    p = provenance()
    result = build_tokenized_equity_evidence_quality(
        tokenized_equity_provenance=p,
        tokenized_equity_rights=rights_record(p),
        tokenized_equity_market_activity=market_record(p),
    )
    assert len(result["evidence_receipts"]) >= 3
    assert result["confidence_inputs"]["source_independence_verified"] is False
    assert result["verification"]["source_independence_inferred_from_distinct_labels"] is False
