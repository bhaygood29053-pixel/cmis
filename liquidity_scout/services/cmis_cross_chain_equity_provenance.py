"""Evidence-bound cross-chain tokenized-equity provenance for CMIS.

This contract composes accepted structural tokenized-equity provenance with
qualified bridge-route evidence. It deliberately keeps route/configuration
verification separate from observed asset movement, adoption, legal/economic
equivalence, backing, custody, and holder rights.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from liquidity_scout.services.cmis_bridge_route_evidence import (
    ACCEPTED_ROUTE_SEMANTIC_CONTRACTS,
    ROUTE_EVIDENCE_CONTRACT,
)
from liquidity_scout.services.cmis_cross_chain_provenance import PROVENANCE_CONTRACT
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
)

CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT = "cross_chain_equity_provenance/v1"
DEFAULT_EXECUTION_AUTHORIZED = False

# No Robinhood Chain -> X1 route semantic contract is accepted yet. A future
# change may add an id here only after the exact machine-readable route,
# endpoint, field, and timestamp semantics pass CMIS acceptance.
ACCEPTED_ROBINHOOD_X1_ROUTE_SEMANTIC_CONTRACTS: frozenset[str] = frozenset()
ROBINHOOD_CHAIN_ALIASES = frozenset(
    {"robinhood", "robinhood chain", "robinhood_chain"}
)


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raise ValueError(f"{field} must be a mapping")


def _endpoint(value: Any, field: str) -> dict[str, str]:
    mapped = _mapping(value, field)
    return {
        "chain": _required_text(mapped.get("chain"), f"{field}.chain").casefold(),
        "asset_id": _required_text(mapped.get("asset_id"), f"{field}.asset_id"),
        "asset_id_kind": _required_text(
            mapped.get("asset_id_kind"), f"{field}.asset_id_kind"
        ).casefold(),
    }


def _same_endpoint(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left["chain"] == right["chain"]
        and left["asset_id"] == right["asset_id"]
        and left["asset_id_kind"] == right["asset_id_kind"]
    )


def _tokenized_equity(value: Any) -> Mapping[str, Any]:
    mapped = _mapping(value, "tokenized_equity_provenance")
    if mapped.get("contract") != TOKENIZED_EQUITY_PROVENANCE_CONTRACT:
        raise ValueError(
            "tokenized_equity_provenance must use accepted "
            f"{TOKENIZED_EQUITY_PROVENANCE_CONTRACT}"
        )
    if mapped.get("execution_authorized") is not False:
        raise ValueError(
            "tokenized_equity_provenance must preserve execution_authorized=false"
        )

    verification = _mapping(
        mapped.get("verification"), "tokenized_equity_provenance.verification"
    )
    if verification.get("exact_token_identity_structurally_bound") is not True:
        raise ValueError("tokenized-equity token identity must be structurally bound")
    if verification.get("exact_underlying_security_id_structurally_bound") is not True:
        raise ValueError(
            "tokenized-equity underlying security identity must be structurally bound"
        )

    cross_chain = _mapping(
        mapped.get("cross_chain"), "tokenized_equity_provenance.cross_chain"
    )
    if cross_chain.get("contract") != PROVENANCE_CONTRACT:
        raise ValueError(
            "tokenized_equity_provenance.cross_chain must use accepted "
            f"{PROVENANCE_CONTRACT}"
        )
    if cross_chain.get("structural_continuity_verified") is not True:
        raise ValueError("cross-chain structural continuity must be verified")

    token = _endpoint(mapped.get("token"), "tokenized_equity_provenance.token")
    current = _endpoint(
        cross_chain.get("current"), "tokenized_equity_provenance.cross_chain.current"
    )
    if not _same_endpoint(token, current):
        raise ValueError(
            "cross-chain current endpoint must equal tokenized-equity token"
        )

    return mapped


def _qualified_route_evidence(
    value: Any,
    *,
    hop: Mapping[str, Any],
    hop_index: int,
    canonical_asset_id: str,
) -> dict[str, Any]:
    evidence = _mapping(value, f"route_evidence[{hop_index}]")
    if evidence.get("contract") != ROUTE_EVIDENCE_CONTRACT:
        raise ValueError(
            f"route_evidence[{hop_index}] must use accepted {ROUTE_EVIDENCE_CONTRACT}"
        )
    if evidence.get("execution_authorized") is not False:
        raise ValueError(
            f"route_evidence[{hop_index}] must preserve execution_authorized=false"
        )
    if evidence.get("qualified") is not True:
        raise ValueError(f"route_evidence[{hop_index}] must be qualified")
    if evidence.get("qualification_state") != "qualified":
        raise ValueError(
            f"route_evidence[{hop_index}] qualification_state must be qualified"
        )
    if evidence.get("hop_index") != hop_index:
        raise ValueError(f"route_evidence[{hop_index}] hop_index mismatch")
    if evidence.get("canonical_asset_id") != canonical_asset_id:
        raise ValueError(
            f"route_evidence[{hop_index}] canonical_asset_id mismatch"
        )

    hop_source = _endpoint(hop.get("source"), f"lineage[{hop_index}].source")
    hop_destination = _endpoint(
        hop.get("destination"), f"lineage[{hop_index}].destination"
    )
    evidence_source = _endpoint(
        evidence.get("source"), f"route_evidence[{hop_index}].source"
    )
    evidence_destination = _endpoint(
        evidence.get("destination"), f"route_evidence[{hop_index}].destination"
    )
    if not _same_endpoint(hop_source, evidence_source):
        raise ValueError(f"route_evidence[{hop_index}] source endpoint mismatch")
    if not _same_endpoint(hop_destination, evidence_destination):
        raise ValueError(
            f"route_evidence[{hop_index}] destination endpoint mismatch"
        )

    hop_bridge = _required_text(hop.get("bridge"), f"lineage[{hop_index}].bridge")
    evidence_bridge = _required_text(
        evidence.get("bridge"), f"route_evidence[{hop_index}].bridge"
    )
    if hop_bridge.casefold() != evidence_bridge.casefold():
        raise ValueError(f"route_evidence[{hop_index}] bridge mismatch")

    hop_route_id = _required_text(
        hop.get("bridge_route_id"), f"lineage[{hop_index}].bridge_route_id"
    )
    evidence_route_id = _required_text(
        evidence.get("route_id"), f"route_evidence[{hop_index}].route_id"
    )
    if hop_route_id != evidence_route_id:
        raise ValueError(f"route_evidence[{hop_index}] route_id mismatch")

    evidence_id = _required_text(
        evidence.get("evidence_id"), f"route_evidence[{hop_index}].evidence_id"
    )
    semantic_contract_id = _required_text(
        evidence.get("semantic_contract_id"),
        f"route_evidence[{hop_index}].semantic_contract_id",
    )
    provider = _required_text(
        evidence.get("provider"), f"route_evidence[{hop_index}].provider"
    )
    source_url = _required_text(
        evidence.get("source_url"), f"route_evidence[{hop_index}].source_url"
    )

    semantic_spec = ACCEPTED_ROUTE_SEMANTIC_CONTRACTS.get(semantic_contract_id)
    if semantic_spec is None:
        raise ValueError(
            f"route_evidence[{hop_index}] semantic contract is not accepted"
        )
    if semantic_spec.get("provider") != provider:
        raise ValueError(f"route_evidence[{hop_index}] provider mismatch")
    if semantic_spec.get("source_url") != source_url:
        raise ValueError(f"route_evidence[{hop_index}] source_url mismatch")

    checks = _mapping(
        evidence.get("qualification_checks"),
        f"route_evidence[{hop_index}].qualification_checks",
    )
    if not checks or not all(value is True for value in checks.values()):
        raise ValueError(
            f"route_evidence[{hop_index}] qualification checks must all pass"
        )

    facts = _mapping(evidence.get("facts"), f"route_evidence[{hop_index}].facts")
    for fact_name in ("route_status", "backing_model", "custody_dependency"):
        fact = _mapping(
            facts.get(fact_name),
            f"route_evidence[{hop_index}].facts.{fact_name}",
        )
        if fact.get("verified") is not True:
            raise ValueError(
                f"route_evidence[{hop_index}] {fact_name} must be verified"
            )

    if (
        hop_source["chain"] in ROBINHOOD_CHAIN_ALIASES
        and hop_destination["chain"] == "x1"
        and semantic_contract_id
        not in ACCEPTED_ROBINHOOD_X1_ROUTE_SEMANTIC_CONTRACTS
    ):
        raise ValueError(
            "no accepted Robinhood Chain -> X1 route semantic contract exists"
        )

    return {
        "hop_index": hop_index,
        "evidence_id": evidence_id,
        "provider": provider,
        "bridge": evidence_bridge,
        "route_id": evidence_route_id,
        "semantic_contract_id": semantic_contract_id,
        "source": evidence_source,
        "destination": evidence_destination,
        "qualified": True,
        "qualification_state": "qualified",
    }


def _wrapper_records(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    representation = _mapping(value.get("representation"), "representation")
    wrappers = representation.get("wrapper_layers") or []
    if not isinstance(wrappers, Sequence) or isinstance(wrappers, (str, bytes)):
        raise ValueError("representation.wrapper_layers must be a sequence")

    result: list[dict[str, Any]] = []
    for index, wrapper in enumerate(wrappers):
        mapped = _mapping(wrapper, f"representation.wrapper_layers[{index}]")
        result.append(
            {
                "layer_index": index,
                "layer_type": _required_text(
                    mapped.get("layer_type"),
                    f"representation.wrapper_layers[{index}].layer_type",
                ).casefold(),
                "token": _endpoint(
                    mapped.get("token"),
                    f"representation.wrapper_layers[{index}].token",
                ),
            }
        )
    return result


def build_cross_chain_equity_provenance(
    *,
    tokenized_equity_provenance: Any,
    route_evidence: Any,
) -> dict[str, Any]:
    """Build a route-qualified cross-chain equity lineage without movement claims.

    Every cross-chain hop must have a qualified accepted bridge-route evidence
    receipt. The result proves exact route/endpoint binding only. It does not
    prove that the equity representation moved through that route, that the
    destination representation is legally/economically equivalent to the
    underlying security, or that any holder right exists.
    """

    equity = _tokenized_equity(tokenized_equity_provenance)
    cross_chain = _mapping(equity.get("cross_chain"), "cross_chain")
    canonical_asset_id = _required_text(
        cross_chain.get("canonical_asset_id"), "cross_chain.canonical_asset_id"
    )
    lineage = cross_chain.get("lineage")
    if not isinstance(lineage, Sequence) or isinstance(lineage, (str, bytes)):
        raise ValueError("cross_chain.lineage must be a sequence")
    if not lineage:
        raise ValueError("cross_chain.lineage must not be empty")

    if not isinstance(route_evidence, Sequence) or isinstance(
        route_evidence, (str, bytes)
    ):
        raise ValueError("route_evidence must be a sequence")
    if len(route_evidence) != len(lineage):
        raise ValueError("one qualified route evidence receipt is required per hop")

    qualified_routes = [
        _qualified_route_evidence(
            route_evidence[index],
            hop=_mapping(hop, f"cross_chain.lineage[{index}]"),
            hop_index=index,
            canonical_asset_id=canonical_asset_id,
        )
        for index, hop in enumerate(lineage)
    ]

    origin = _endpoint(cross_chain.get("origin"), "cross_chain.origin")
    current = _endpoint(cross_chain.get("current"), "cross_chain.current")
    token = _endpoint(equity.get("token"), "tokenized_equity_provenance.token")
    if not _same_endpoint(current, token):
        raise ValueError("destination token must equal tokenized-equity token")

    robinhood_x1_hops = [
        route
        for route in qualified_routes
        if route["source"]["chain"] in ROBINHOOD_CHAIN_ALIASES
        and route["destination"]["chain"] == "x1"
    ]

    return {
        "contract": CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT,
        "tokenized_equity_contract": TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
        "cross_chain_contract": PROVENANCE_CONTRACT,
        "canonical_asset_id": canonical_asset_id,
        "underlying_security": deepcopy(equity.get("underlying_security")),
        "token": token,
        "origin": origin,
        "current": current,
        "representation_depth": len(lineage),
        "lineage": deepcopy(list(lineage)),
        "wrapper_layers": _wrapper_records(equity),
        "route_evidence": qualified_routes,
        "verification": {
            "tokenized_equity_binding_verified": True,
            "structural_lineage_continuity_verified": True,
            "all_route_evidence_qualified": True,
            "exact_destination_token_verified": True,
            "robinhood_x1_route_verified": bool(robinhood_x1_hops),
            "observed_asset_movement_verified": False,
            "adoption_verified": False,
            "legal_or_economic_equivalence_verified": False,
            "holder_rights_verified": False,
            "backing_sufficiency_verified": False,
            "custody_safety_verified": False,
        },
        "boundaries": {
            "route_configuration_equals_asset_movement": False,
            "asset_movement_claim_authorized": False,
            "bridge_activity_equals_adoption": False,
            "token_equals_underlying_share_claim_authorized": False,
            "shareholder_ownership_claim_authorized": False,
            "beneficial_ownership_claim_authorized": False,
            "legal_or_economic_equivalence_claim_authorized": False,
            "backing_sufficiency_claim_authorized": False,
            "custody_safety_claim_authorized": False,
            "holder_rights_claim_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "ACCEPTED_ROBINHOOD_X1_ROUTE_SEMANTIC_CONTRACTS",
    "CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT",
    "DEFAULT_EXECUTION_AUTHORIZED",
    "ROBINHOOD_CHAIN_ALIASES",
    "build_cross_chain_equity_provenance",
]
