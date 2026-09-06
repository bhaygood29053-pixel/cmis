import json
from pathlib import Path

import pytest

from liquidity_scout.services.cmis_regulatory_evidence import (
    RegulatoryEvidenceContractError,
    validate_regulatory_evidence_record,
)


FIXTURES = Path(__file__).parent / "fixtures" / "regulatory"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_usdc_fixture_is_valid_but_does_not_claim_compliance():
    record = validate_regulatory_evidence_record(
        _load("usdc_genius_act_v1.json"),
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset="USDC",
    )
    assert record["asset"]["representation_type"] == "native"
    assert record["asset"]["bridge_dependency"] is False
    assert record["applicability"] == "INSUFFICIENT_EVIDENCE"
    assert record["compliance_conclusion"] is None
    assert record["compliance_conclusion_authorized"] is False
    assert record["execution_authorized"] is False


def test_usdcx_fixture_preserves_bridge_and_custody_dependencies():
    record = validate_regulatory_evidence_record(
        _load("usdcx_genius_act_v1.json"),
        expected_jurisdiction="US",
        expected_framework="GENIUS Act",
        expected_asset="USDC.X",
    )
    assert record["asset"]["representation_type"] == "bridged"
    assert record["asset"]["underlying_asset"] == "USDC"
    assert record["asset"]["bridge_dependency"] is True
    assert record["asset"]["custody_dependency"] is True


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda r: r.__setitem__("compliance_conclusion", "COMPLIANT"),
            "must not emit a compliance conclusion",
        ),
        (
            lambda r: r.__setitem__("compliance_conclusion_authorized", True),
            "compliance_conclusion_authorized",
        ),
        (
            lambda r: r["asset"].__setitem__("bridge_dependency", False),
            "bridge_dependency=true",
        ),
        (
            lambda r: r["legal"].__setitem__("status", "probably_effective"),
            "legal.status",
        ),
        (
            lambda r: r["sources"][0].__setitem__("authority_class", "blog"),
            "authority_class",
        ),
    ],
)
def test_regulatory_evidence_fails_closed_on_authority_drift(mutate, match):
    record = _load("usdcx_genius_act_v1.json")
    mutate(record)
    with pytest.raises(RegulatoryEvidenceContractError, match=match):
        validate_regulatory_evidence_record(record)
