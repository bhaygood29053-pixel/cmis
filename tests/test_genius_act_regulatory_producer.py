from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from liquidity_scout.providers.regulatory.genius_act import (
    GENIUS_ACT_SOURCE_REGISTRY,
    RegulatoryEvidenceProductionError,
    X1_USDCX_MINT,
    produce_genius_act_usdcx_regulatory_record,
)


NOW = datetime(2026, 9, 6, 16, 15, tzinfo=timezone.utc)


def _body(spec):
    markers = " | ".join(str(item) for item in spec["required_markers"])
    return f"<html><body>{markers}</body></html>"


def _fetcher_for(registry):
    bodies = {str(spec["url"]): _body(spec) for spec in registry}
    return lambda url: bodies[url]


def test_default_live_producer_emits_valid_current_usdcx_record():
    record = produce_genius_act_usdcx_regulatory_record(
        fetcher=_fetcher_for(GENIUS_ACT_SOURCE_REGISTRY),
        clock=lambda: NOW,
    )

    assert record["service"] == "regulatory_evidence"
    assert record["contract"] == "regulatory_evidence/v1"
    assert record["jurisdiction"] == "US"
    assert record["framework"] == "GENIUS Act"
    assert record["legal"]["law_id"] == "Public Law 119-27"
    assert record["current_regulatory_state"] == {
        "rulemaking_status": "proposed_rule",
        "final_rule_verified": False,
        "effective_now_verified": False,
        "status_as_of": "2026-09-06T16:15:00Z",
    }
    assert record["asset"]["chain_scoped_asset_id"] == X1_USDCX_MINT
    assert record["asset"]["representation_type"] == "bridged"
    assert record["asset"]["bridge_dependency"] is True
    assert record["asset"]["custody_dependency"] is True
    assert record["applicability"] == "INSUFFICIENT_EVIDENCE"
    assert record["compliance_conclusion"] is None
    assert record["compliance_conclusion_authorized"] is False
    assert record["execution_authorized"] is False
    assert all(
        source["retrieved_at"] == "2026-09-06T16:15:00Z"
        for source in record["sources"]
    )
    assert {source["authority_class"] for source in record["sources"]} == {
        "primary_law",
        "primary_regulator",
    }


def test_default_source_registry_is_https_government_only():
    assert GENIUS_ACT_SOURCE_REGISTRY
    for source in GENIUS_ACT_SOURCE_REGISTRY:
        url = source["url"]
        assert url.startswith("https://")
        assert (
            url.startswith("https://www.govinfo.gov/")
            or url.startswith("https://home.treasury.gov/")
        )


def test_missing_authoritative_source_marker_fails_closed():
    target = GENIUS_ACT_SOURCE_REGISTRY[-1]

    def fetch(url):
        if url == target["url"]:
            return "<html><body>unrelated Treasury page</body></html>"
        spec = next(item for item in GENIUS_ACT_SOURCE_REGISTRY if item["url"] == url)
        return _body(spec)

    with pytest.raises(
        RegulatoryEvidenceProductionError,
        match="source identity markers missing",
    ):
        produce_genius_act_usdcx_regulatory_record(
            fetcher=fetch,
            clock=lambda: NOW,
        )


def test_fetch_failure_fails_closed_without_partial_record():
    def fetch(_url):
        raise TimeoutError("source unavailable")

    with pytest.raises(
        RegulatoryEvidenceProductionError,
        match="authoritative source fetch failed",
    ):
        produce_genius_act_usdcx_regulatory_record(
            fetcher=fetch,
            clock=lambda: NOW,
        )


def test_future_final_rule_source_promotes_final_but_not_effective():
    registry = [deepcopy(item) for item in GENIUS_ACT_SOURCE_REGISTRY]
    registry.append(
        {
            "source_id": "treasury-genius-final-rule-test",
            "authority_class": "primary_regulator",
            "publisher": "U.S. Department of the Treasury",
            "title": "GENIUS Act Final Rule",
            "url": "https://home.treasury.gov/news/press-releases/final-test",
            "published_on": "2026-09-05",
            "rulemaking_status": "final_rule",
            "required_markers": ("GENIUS Act", "Final Rule", "September 5, 2026"),
        }
    )

    record = produce_genius_act_usdcx_regulatory_record(
        fetcher=_fetcher_for(registry),
        clock=lambda: NOW,
        source_registry=registry,
    )

    assert record["current_regulatory_state"]["rulemaking_status"] == "final_rule"
    assert record["current_regulatory_state"]["final_rule_verified"] is True
    assert record["current_regulatory_state"]["effective_now_verified"] is False
    assert record["compliance_conclusion"] is None


def test_future_final_rule_with_verified_effective_date_promotes_effective():
    registry = [deepcopy(item) for item in GENIUS_ACT_SOURCE_REGISTRY]
    registry.append(
        {
            "source_id": "treasury-genius-final-effective-test",
            "authority_class": "primary_regulator",
            "publisher": "U.S. Department of the Treasury",
            "title": "GENIUS Act Final Rule",
            "url": "https://home.treasury.gov/news/press-releases/final-effective-test",
            "published_on": "2026-09-05",
            "rulemaking_status": "final_rule",
            "effective_on": "2026-10-01",
            "required_markers": ("GENIUS Act", "Final Rule", "September 5, 2026"),
        }
    )

    record = produce_genius_act_usdcx_regulatory_record(
        fetcher=_fetcher_for(registry),
        clock=lambda: datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
        source_registry=registry,
    )

    assert record["current_regulatory_state"]["rulemaking_status"] == "effective"
    assert record["current_regulatory_state"]["final_rule_verified"] is True
    assert record["current_regulatory_state"]["effective_now_verified"] is True


def test_non_https_source_registry_is_rejected_before_fetch():
    registry = [deepcopy(item) for item in GENIUS_ACT_SOURCE_REGISTRY]
    registry[0]["url"] = "http://example.invalid/law"

    with pytest.raises(
        RegulatoryEvidenceProductionError,
        match="must use https",
    ):
        produce_genius_act_usdcx_regulatory_record(
            fetcher=lambda _url: "never reached",
            clock=lambda: NOW,
            source_registry=registry,
        )
