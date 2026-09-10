"""Deterministic tokenized-equity provenance foundation for CMIS.

This module separates exact token identity, underlying-security identity, the
claimed representation structure, and optional accepted cross-chain structural
lineage. It does not verify legal ownership, shareholder rights, issuer claims,
backing, custody, live deployment, bridge availability, or provider truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_cross_chain_provenance import PROVENANCE_CONTRACT

TOKENIZED_EQUITY_PROVENANCE_CONTRACT = "tokenized_equity_provenance/v1"
DEFAULT_EXECUTION_AUTHORIZED = False

DISALLOWED_TOKEN_ID_KINDS = frozenset({"symbol", "ticker", "name", "label"})
ALLOWED_SECURITY_ID_KINDS = frozenset(
    {
        "isin",
        "cusip",
        "sedol",
        "figi",
        "issuer_security_id",
        "registry_security_id",
    }
)
ALLOWED_REPRESENTATION_TYPES = frozenset(
    {
        "direct_equity_token",
        "custodial_equity_receipt",
        "depositary_receipt_token",
        "debt_linked_equity_exposure",
        "synthetic_equity_exposure",
        "wrapped_equity_representation",
        "tokenized_security_representation",
        "unknown",
    }
)


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _token_endpoint(value: Any, *, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")

    chain = _required_text(value.get("chain"), f"{field}.chain").casefold()
    asset_id = _required_text(value.get("asset_id"), f"{field}.asset_id")
    asset_id_kind = _required_text(
        value.get("asset_id_kind"), f"{field}.asset_id_kind"
    ).casefold()
    if asset_id_kind in DISALLOWED_TOKEN_ID_KINDS:
        raise ValueError(
            f"{field}.asset_id_kind cannot use symbol/name labels as identity"
        )

    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


def _same_endpoint(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left["chain"] == right["chain"]
        and left["asset_id"] == right["asset_id"]
        and left["asset_id_kind"] == right["asset_id_kind"]
    )


def _security_identity(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("underlying_security must be a mapping")

    security_id = _required_text(
        value.get("security_id"), "underlying_security.security_id"
    )
    security_id_kind = _required_text(
        value.get("security_id_kind"), "underlying_security.security_id_kind"
    ).casefold()
    if security_id_kind not in ALLOWED_SECURITY_ID_KINDS:
        raise ValueError(
            "underlying_security.security_id_kind must use an accepted exact "
            "security identifier; ticker/name labels are not identity"
        )

    return {
        "security_id": security_id,
        "security_id_kind": security_id_kind,
    }


def _issuer(value: Any) -> dict[str, str | None]:
    if not isinstance(value, Mapping):
        raise ValueError("issuer must be a mapping")

    name = _required_text(value.get("name"), "issuer.name")
    legal_entity_id = _optional_text(value.get("legal_entity_id"))
    legal_entity_id_kind = _optional_text(value.get("legal_entity_id_kind"))
    if bool(legal_entity_id) != bool(legal_entity_id_kind):
        raise ValueError(
            "issuer.legal_entity_id and issuer.legal_entity_id_kind must be "
            "provided together"
        )

    return {
        "name": name,
        "legal_entity_id": legal_entity_id,
        "legal_entity_id_kind": (
            legal_entity_id_kind.casefold() if legal_entity_id_kind else None
        ),
    }


def _wrapper_layers(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("wrapper_layers must be a sequence")

    layers: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"wrapper_layers[{index}] must be a mapping")
        layer_type = _required_text(
            raw.get("layer_type"), f"wrapper_layers[{index}].layer_type"
        ).casefold()
        token = _token_endpoint(
            raw.get("token"), field=f"wrapper_layers[{index}].token"
        )
        key = (
            layer_type,
            token["chain"],
            token["asset_id"],
            token["asset_id_kind"],
        )
        if key in seen:
            raise ValueError("duplicate wrapper layer is not allowed")
        seen.add(key)
        layers.append(
            {
                "layer_index": index,
                "layer_type": layer_type,
                "token": token,
                "operator": _optional_text(raw.get("operator")),
            }
        )
    return layers


def _evidence_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("evidence_ids must be a sequence")

    result: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = _required_text(raw, f"evidence_ids[{index}]")
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _cross_chain_binding(
    value: Any,
    *,
    token: Mapping[str, str],
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("cross_chain_provenance must be a mapping")
    if value.get("contract") != PROVENANCE_CONTRACT:
        raise ValueError(
            "cross_chain_provenance must use accepted cross_chain_asset_provenance/v1"
        )
    if value.get("execution_authorized") is not False:
        raise ValueError(
            "cross_chain_provenance must preserve execution_authorized=false"
        )

    verification = value.get("verification")
    if not isinstance(verification, Mapping):
        raise ValueError("cross_chain_provenance.verification must be a mapping")
    if verification.get("structural_continuity_verified") is not True:
        raise ValueError(
            "cross_chain_provenance structural continuity must be verified"
        )

    current = _token_endpoint(
        value.get("current"), field="cross_chain_provenance.current"
    )
    if not _same_endpoint(current, token):
        raise ValueError(
            "cross_chain_provenance.current must equal tokenized equity token"
        )

    origin = _token_endpoint(
        value.get("origin"), field="cross_chain_provenance.origin"
    )
    lineage = value.get("lineage")
    if not isinstance(lineage, Sequence) or isinstance(lineage, (str, bytes)):
        raise ValueError("cross_chain_provenance.lineage must be a sequence")

    return {
        "contract": PROVENANCE_CONTRACT,
        "canonical_asset_id": _required_text(
            value.get("canonical_asset_id"),
            "cross_chain_provenance.canonical_asset_id",
        ),
        "origin": origin,
        "current": current,
        "representation_depth": int(value.get("representation_depth") or 0),
        "lineage": deepcopy(list(lineage)),
        "structural_continuity_verified": True,
        "live_bridge_state_verified": (
            verification.get("live_bridge_state_verified") is True
        ),
        "backing_verified": verification.get("backing_verified") is True,
        "custody_verified": verification.get("custody_verified") is True,
    }


def build_tokenized_equity_provenance(
    *,
    token: Any,
    underlying_security: Any,
    representation_type: Any,
    issuer: Any,
    backing_model: Any = None,
    custody_model: Any = None,
    wrapper_layers: Any = None,
    cross_chain_provenance: Any = None,
    evidence_ids: Any = None,
) -> dict[str, Any]:
    """Build one bounded structural tokenized-equity provenance record.

    The builder proves schema/identity continuity only. Descriptive issuer,
    representation, backing, custody, and wrapper fields remain claims until a
    later evidence-bearing contract independently verifies them.
    """

    token_endpoint = _token_endpoint(token, field="token")
    security = _security_identity(underlying_security)
    representation = _required_text(
        representation_type, "representation_type"
    ).casefold()
    if representation not in ALLOWED_REPRESENTATION_TYPES:
        raise ValueError("representation_type is not an accepted classification")

    issuer_record = _issuer(issuer)
    wrappers = _wrapper_layers(wrapper_layers)
    evidence = _evidence_ids(evidence_ids)
    cross_chain = _cross_chain_binding(
        cross_chain_provenance,
        token=token_endpoint,
    )

    return {
        "contract": TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
        "token": token_endpoint,
        "underlying_security": security,
        "representation": {
            "type": representation,
            "issuer": issuer_record,
            "backing_model": _optional_text(backing_model),
            "custody_model": _optional_text(custody_model),
            "wrapper_layers": wrappers,
        },
        "cross_chain": cross_chain,
        "evidence_ids": evidence,
        "verification": {
            "exact_token_identity_structurally_bound": True,
            "exact_underlying_security_id_structurally_bound": True,
            "cross_chain_structural_continuity_verified": cross_chain is not None,
            "representation_classification_verified": False,
            "issuer_identity_verified": False,
            "underlying_equity_ownership_verified": False,
            "backing_verified": False,
            "custody_verified": False,
            "holder_rights_verified": False,
            "live_deployment_verified": False,
            "live_bridge_route_verified": False,
            "source_independence_verified": False,
        },
        "boundaries": {
            "descriptive_claims_are_verified_facts": False,
            "token_equals_underlying_share_claim_authorized": False,
            "direct_shareholder_ownership_claim_authorized": False,
            "beneficial_ownership_claim_authorized": False,
            "voting_rights_claim_authorized": False,
            "dividend_rights_claim_authorized": False,
            "redemption_rights_claim_authorized": False,
            "issuer_guarantee_claim_authorized": False,
            "backing_sufficiency_claim_authorized": False,
            "custody_safety_claim_authorized": False,
            "legal_or_economic_equivalence_claim_authorized": False,
            "bridge_availability_claim_authorized": False,
            "x1_live_support_claim_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "legal_advice_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "ALLOWED_REPRESENTATION_TYPES",
    "ALLOWED_SECURITY_ID_KINDS",
    "DEFAULT_EXECUTION_AUTHORIZED",
    "DISALLOWED_TOKEN_ID_KINDS",
    "TOKENIZED_EQUITY_PROVENANCE_CONTRACT",
    "build_tokenized_equity_provenance",
]
