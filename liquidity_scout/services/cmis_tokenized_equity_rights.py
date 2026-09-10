"""Evidence-bound tokenized-equity holder-rights contract for CMIS.

This module binds rights claims to accepted tokenized-equity provenance and
bounded source evidence. It validates evidence structure and authority class;
it does not adjudicate legal effect, establish compliance, or authorize trades.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
)

TOKENIZED_EQUITY_RIGHTS_CONTRACT = "tokenized_equity_rights/v1"
DEFAULT_EXECUTION_AUTHORIZED = False

RIGHT_STATES = frozenset(
    {"VERIFIED", "DENIED", "CONDITIONAL", "UNKNOWN", "NOT_APPLICABLE"}
)
REQUIRED_DIMENSIONS = (
    "underlying_ownership",
    "voting_rights",
    "dividend_treatment",
    "redemption_rights",
    "backing_collateral",
    "issuer_counterparty",
    "jurisdiction_scope",
    "transfer_restrictions",
    "custody_structure",
)

AUTHORITATIVE_SOURCE_CLASSES = frozenset(
    {
        "issuer_governing_document",
        "offering_document",
        "prospectus",
        "regulatory_filing",
        "custody_agreement",
        "depositary_agreement",
        "trust_agreement",
        "official_terms",
        "corporate_action_notice",
        "statute_or_rule",
        "court_or_regulator_order",
    }
)
NON_AUTHORITATIVE_SOURCE_CLASSES = frozenset(
    {
        "marketing_material",
        "issuer_blog",
        "news",
        "secondary_research",
        "social_media",
        "community_content",
    }
)
ALLOWED_SOURCE_CLASSES = AUTHORITATIVE_SOURCE_CLASSES | NON_AUTHORITATIVE_SOURCE_CLASSES

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _timestamp(value: Any, field: str) -> str:
    text = _required_text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return text


def _sequence(value: Any, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence")
    return list(value)


def _token_endpoint(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return {
        "chain": _required_text(value.get("chain"), f"{field}.chain").casefold(),
        "asset_id": _required_text(value.get("asset_id"), f"{field}.asset_id"),
        "asset_id_kind": _required_text(
            value.get("asset_id_kind"), f"{field}.asset_id_kind"
        ).casefold(),
    }


def _bind_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("tokenized_equity_provenance must be a mapping")
    if value.get("contract") != TOKENIZED_EQUITY_PROVENANCE_CONTRACT:
        raise ValueError(
            "tokenized_equity_provenance must use accepted "
            "tokenized_equity_provenance/v1"
        )
    if value.get("execution_authorized") is not False:
        raise ValueError("tokenized_equity_provenance must preserve execution_authorized=false")

    verification = value.get("verification")
    if not isinstance(verification, Mapping):
        raise ValueError("tokenized_equity_provenance.verification must be a mapping")
    if verification.get("exact_token_identity_structurally_bound") is not True:
        raise ValueError("tokenized-equity token identity must be structurally bound")
    if verification.get("exact_underlying_security_id_structurally_bound") is not True:
        raise ValueError("underlying security identity must be structurally bound")
    if verification.get("holder_rights_verified") is not False:
        raise ValueError("provenance foundation cannot pre-assert holder rights")

    token = _token_endpoint(value.get("token"), "tokenized_equity_provenance.token")
    security = value.get("underlying_security")
    if not isinstance(security, Mapping):
        raise ValueError("tokenized_equity_provenance.underlying_security must be a mapping")
    security_id = _required_text(
        security.get("security_id"),
        "tokenized_equity_provenance.underlying_security.security_id",
    )
    security_id_kind = _required_text(
        security.get("security_id_kind"),
        "tokenized_equity_provenance.underlying_security.security_id_kind",
    ).casefold()

    representation = value.get("representation")
    if not isinstance(representation, Mapping):
        raise ValueError("tokenized_equity_provenance.representation must be a mapping")

    return {
        "contract": TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
        "token": token,
        "underlying_security": {
            "security_id": security_id,
            "security_id_kind": security_id_kind,
        },
        "representation_type": _required_text(
            representation.get("type"),
            "tokenized_equity_provenance.representation.type",
        ),
        "issuer": deepcopy(representation.get("issuer")),
        "cross_chain": deepcopy(value.get("cross_chain")),
    }


def _evidence_item(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")

    source_class = _required_text(value.get("source_class"), f"{field}.source_class").casefold()
    if source_class not in ALLOWED_SOURCE_CLASSES:
        raise ValueError(f"{field}.source_class is not accepted")

    source_url = _required_text(value.get("source_url"), f"{field}.source_url")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field}.source_url must be an absolute https URL")

    content_sha256 = _required_text(
        value.get("content_sha256"), f"{field}.content_sha256"
    ).casefold()
    if not _HASH_RE.fullmatch(content_sha256):
        raise ValueError(f"{field}.content_sha256 must be 64 lowercase hex characters")

    return {
        "evidence_id": _required_text(value.get("evidence_id"), f"{field}.evidence_id"),
        "source_class": source_class,
        "source_url": source_url,
        "document_id": _required_text(value.get("document_id"), f"{field}.document_id"),
        "section": _required_text(value.get("section"), f"{field}.section"),
        "fact_time": _timestamp(value.get("fact_time"), f"{field}.fact_time"),
        "retrieved_at": _timestamp(value.get("retrieved_at"), f"{field}.retrieved_at"),
        "content_sha256": content_sha256,
        "authoritative_for_decisive_state": source_class in AUTHORITATIVE_SOURCE_CLASSES,
    }


def _claim(value: Any, *, dimension: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"dimensions.{dimension} must be a mapping")

    state = _required_text(value.get("state"), f"dimensions.{dimension}.state").upper()
    if state not in RIGHT_STATES:
        raise ValueError(f"dimensions.{dimension}.state is not accepted")

    summary = _required_text(value.get("summary"), f"dimensions.{dimension}.summary")
    evidence = [
        _evidence_item(item, field=f"dimensions.{dimension}.evidence[{index}]")
        for index, item in enumerate(
            _sequence(value.get("evidence"), f"dimensions.{dimension}.evidence")
        )
    ]
    evidence_ids = [item["evidence_id"] for item in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError(f"dimensions.{dimension}.evidence contains duplicate evidence_id")

    conditions = [
        _required_text(item, f"dimensions.{dimension}.conditions[{index}]")
        for index, item in enumerate(
            _sequence(value.get("conditions"), f"dimensions.{dimension}.conditions")
        )
    ]

    if state == "CONDITIONAL" and not conditions:
        raise ValueError(f"dimensions.{dimension} CONDITIONAL state requires conditions")
    if state != "CONDITIONAL" and conditions:
        raise ValueError(
            f"dimensions.{dimension}.conditions are allowed only for CONDITIONAL state"
        )

    decisive = state != "UNKNOWN"
    authoritative = [item for item in evidence if item["authoritative_for_decisive_state"]]
    if decisive and not authoritative:
        raise ValueError(
            f"dimensions.{dimension} decisive state requires authoritative evidence"
        )

    return {
        "dimension": dimension,
        "state": state,
        "summary": summary,
        "conditions": conditions,
        "evidence": evidence,
        "evidence_binding_verified": bool(authoritative) if decisive else False,
        "legal_effect_adjudicated": False,
    }


def build_tokenized_equity_rights(
    *,
    tokenized_equity_provenance: Any,
    dimensions: Any,
) -> dict[str, Any]:
    """Build one bounded tokenized-equity rights evidence record.

    `VERIFIED` means the claim is structurally bound to at least one accepted
    authoritative source class. It does not mean CMIS has issued a legal opinion
    or independently adjudicated enforceability.
    """

    provenance = _bind_provenance(tokenized_equity_provenance)
    if not isinstance(dimensions, Mapping):
        raise ValueError("dimensions must be a mapping")

    supplied = set(dimensions.keys())
    required = set(REQUIRED_DIMENSIONS)
    missing = sorted(required - supplied)
    extra = sorted(supplied - required)
    if missing:
        raise ValueError(f"dimensions missing required entries: {', '.join(missing)}")
    if extra:
        raise ValueError(f"dimensions contains unsupported entries: {', '.join(extra)}")

    claims = {
        dimension: _claim(dimensions[dimension], dimension=dimension)
        for dimension in REQUIRED_DIMENSIONS
    }
    decisive_count = sum(claim["state"] != "UNKNOWN" for claim in claims.values())
    verified_count = sum(claim["state"] == "VERIFIED" for claim in claims.values())

    return {
        "contract": TOKENIZED_EQUITY_RIGHTS_CONTRACT,
        "provenance": provenance,
        "state_semantics": (
            "evidence_bound_claim_status_not_legal_adjudication"
        ),
        "dimensions": claims,
        "summary": {
            "dimension_count": len(REQUIRED_DIMENSIONS),
            "decisive_dimension_count": decisive_count,
            "verified_dimension_count": verified_count,
            "unknown_dimension_count": len(REQUIRED_DIMENSIONS) - decisive_count,
        },
        "verification": {
            "accepted_tokenized_equity_provenance_bound": True,
            "all_non_unknown_states_authoritatively_evidence_bound": True,
            "source_content_independently_verified": False,
            "legal_effect_independently_adjudicated": False,
            "shareholder_status_independently_verified": False,
            "backing_sufficiency_verified": False,
            "custody_safety_verified": False,
            "live_x1_deployment_verified": False,
            "live_robinhood_x1_route_verified": False,
        },
        "boundaries": {
            "provenance_establishes_holder_rights": False,
            "ticker_or_name_establishes_equivalence": False,
            "marketing_material_can_independently_verify_rights": False,
            "verified_state_is_legal_advice": False,
            "verified_state_is_compliance_conclusion": False,
            "backing_description_proves_sufficiency": False,
            "custody_description_proves_safety": False,
            "token_transfer_proves_securities_ownership_transfer": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
            "legal_advice_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "ALLOWED_SOURCE_CLASSES",
    "AUTHORITATIVE_SOURCE_CLASSES",
    "DEFAULT_EXECUTION_AUTHORIZED",
    "NON_AUTHORITATIVE_SOURCE_CLASSES",
    "REQUIRED_DIMENSIONS",
    "RIGHT_STATES",
    "TOKENIZED_EQUITY_RIGHTS_CONTRACT",
    "build_tokenized_equity_rights",
]
