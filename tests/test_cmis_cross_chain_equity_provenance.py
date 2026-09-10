from copy import deepcopy
import unittest

from liquidity_scout.services.cmis_bridge_route_evidence import (
    build_bridge_route_evidence,
)
from liquidity_scout.services.cmis_cross_chain_equity_provenance import (
    ACCEPTED_ROBINHOOD_X1_ROUTE_SEMANTIC_CONTRACTS,
    CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT,
    build_cross_chain_equity_provenance,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    build_tokenized_equity_provenance,
)


SOLANA_ASSET = "So11111111111111111111111111111111111111112"
ROBINHOOD_ASSET = "0xbc191b1d09e51cbe10c15c9191086931b5876b83"
X1_ASSET = "ExampleEquityX1Mint11111111111111111111111111"
WARP_CONFIG_URL = "https://app.bridge.x1.xyz/api/bridge/config"


def endpoint(chain, asset_id, asset_id_kind):
    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


def base_lineage(source_chain="solana", source_asset=SOLANA_ASSET):
    origin = endpoint(source_chain, source_asset, "mint" if source_chain == "solana" else "contract_address")
    current = endpoint("x1", X1_ASSET, "mint")
    return build_cross_chain_asset_provenance(
        canonical_asset_id="equity-security-example",
        origin=origin,
        current=current,
        hops=[
            {
                "source": origin,
                "destination": current,
                "bridge": "Warp Bridge",
                "representation_type": "bridge_representation",
                "custody_model": "external_dependency",
                "bridge_route_id": f"{source_chain}-x1-equity-route",
            }
        ],
    )


def tokenized_equity(cross_chain=None):
    cross_chain = cross_chain or base_lineage()
    return build_tokenized_equity_provenance(
        token=endpoint("x1", X1_ASSET, "mint"),
        underlying_security={
            "security_id": "US0378331005",
            "security_id_kind": "isin",
        },
        representation_type="tokenized_security_representation",
        issuer={"name": "Example Issuer"},
        backing_model="issuer-described backing",
        custody_model="external custodian dependency",
        wrapper_layers=[
            {
                "layer_type": "source_chain_representation",
                "token": cross_chain["origin"],
                "operator": "Example Source Operator",
            },
            {
                "layer_type": "destination_chain_representation",
                "token": cross_chain["current"],
                "operator": "Example Destination Operator",
            },
        ],
        cross_chain_provenance=cross_chain,
        evidence_ids=["issuer-doc-candidate", "route-evidence-candidate"],
    )


def qualified_route(cross_chain):
    hop = cross_chain["lineage"][0]
    return build_bridge_route_evidence(
        provenance=cross_chain,
        hop_index=0,
        source_provenance={
            "url": WARP_CONFIG_URL,
            "source_provenance_verified": True,
            "read_probe_eligible": True,
        },
        observation={
            "provider": "warp_bridge",
            "source_url": WARP_CONFIG_URL,
            "semantic_contract_id": "warp_config/exact-mint-pair/v1",
            "route_id": hop["bridge_route_id"],
            "bridge": "Warp Bridge",
            "source": hop["source"],
            "destination": hop["destination"],
            "collected_at": 1000.0,
            "source_observed_at": 1000.0,
            "route_status": "active",
            "backing_model": "lock_mint",
            "custody_dependency": "guardian_threshold",
        },
        evaluated_at=1001.0,
    )


class CMISCrossChainEquityProvenanceTests(unittest.TestCase):
    def test_builds_route_qualified_equity_lineage_without_movement_claim(self):
        cross_chain = base_lineage()
        equity = tokenized_equity(cross_chain)
        route = qualified_route(cross_chain)
        self.assertTrue(route["qualified"])

        result = build_cross_chain_equity_provenance(
            tokenized_equity_provenance=equity,
            route_evidence=[route],
        )

        self.assertEqual(result["contract"], CROSS_CHAIN_EQUITY_PROVENANCE_CONTRACT)
        self.assertEqual(result["origin"]["chain"], "solana")
        self.assertEqual(result["current"]["chain"], "x1")
        self.assertTrue(result["verification"]["tokenized_equity_binding_verified"])
        self.assertTrue(result["verification"]["all_route_evidence_qualified"])
        self.assertTrue(result["verification"]["exact_destination_token_verified"])
        self.assertFalse(result["verification"]["observed_asset_movement_verified"])
        self.assertFalse(result["verification"]["adoption_verified"])
        self.assertFalse(
            result["verification"]["legal_or_economic_equivalence_verified"]
        )
        self.assertFalse(result["verification"]["holder_rights_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_wrapper_asset_identities_are_preserved_without_collapsing(self):
        cross_chain = base_lineage()
        result = build_cross_chain_equity_provenance(
            tokenized_equity_provenance=tokenized_equity(cross_chain),
            route_evidence=[qualified_route(cross_chain)],
        )

        self.assertEqual(len(result["wrapper_layers"]), 2)
        self.assertEqual(result["wrapper_layers"][0]["token"], cross_chain["origin"])
        self.assertEqual(result["wrapper_layers"][1]["token"], cross_chain["current"])
        self.assertNotEqual(
            result["wrapper_layers"][0]["token"]["asset_id"],
            result["wrapper_layers"][1]["token"]["asset_id"],
        )

    def test_one_qualified_route_receipt_is_required_per_hop(self):
        cross_chain = base_lineage()
        with self.assertRaisesRegex(ValueError, "one qualified route evidence"):
            build_cross_chain_equity_provenance(
                tokenized_equity_provenance=tokenized_equity(cross_chain),
                route_evidence=[],
            )

    def test_unaccepted_semantic_contract_cannot_be_promoted_by_boolean_flags(self):
        cross_chain = base_lineage()
        route = qualified_route(cross_chain)
        route["semantic_contract_id"] = "caller-says-verified/v1"

        with self.assertRaisesRegex(ValueError, "semantic contract is not accepted"):
            build_cross_chain_equity_provenance(
                tokenized_equity_provenance=tokenized_equity(cross_chain),
                route_evidence=[route],
            )

    def test_route_endpoints_must_exactly_match_lineage(self):
        cross_chain = base_lineage()
        route = qualified_route(cross_chain)
        route["destination"] = endpoint(
            "x1", "DifferentX1Mint111111111111111111111111111", "mint"
        )

        with self.assertRaisesRegex(ValueError, "destination endpoint mismatch"):
            build_cross_chain_equity_provenance(
                tokenized_equity_provenance=tokenized_equity(cross_chain),
                route_evidence=[route],
            )

    def test_destination_token_must_equal_tokenized_equity_token(self):
        cross_chain = base_lineage()
        equity = tokenized_equity(cross_chain)
        tampered = deepcopy(equity)
        tampered["token"]["asset_id"] = "DifferentX1Mint111111111111111111111111111"

        with self.assertRaisesRegex(ValueError, "must equal tokenized-equity token"):
            build_cross_chain_equity_provenance(
                tokenized_equity_provenance=tampered,
                route_evidence=[qualified_route(cross_chain)],
            )

    def test_robinhood_x1_requires_a_separately_accepted_route_semantic_contract(self):
        self.assertEqual(ACCEPTED_ROBINHOOD_X1_ROUTE_SEMANTIC_CONTRACTS, frozenset())
        cross_chain = base_lineage(
            source_chain="Robinhood Chain",
            source_asset=ROBINHOOD_ASSET,
        )
        route = qualified_route(cross_chain)
        self.assertTrue(route["qualified"])

        with self.assertRaisesRegex(
            ValueError, "no accepted Robinhood Chain -> X1 route semantic contract"
        ):
            build_cross_chain_equity_provenance(
                tokenized_equity_provenance=tokenized_equity(cross_chain),
                route_evidence=[route],
            )

    def test_route_configuration_never_becomes_movement_adoption_or_rights(self):
        cross_chain = base_lineage()
        result = build_cross_chain_equity_provenance(
            tokenized_equity_provenance=tokenized_equity(cross_chain),
            route_evidence=[qualified_route(cross_chain)],
        )
        boundaries = result["boundaries"]

        self.assertFalse(boundaries["route_configuration_equals_asset_movement"])
        self.assertFalse(boundaries["asset_movement_claim_authorized"])
        self.assertFalse(boundaries["bridge_activity_equals_adoption"])
        self.assertFalse(boundaries["token_equals_underlying_share_claim_authorized"])
        self.assertFalse(boundaries["shareholder_ownership_claim_authorized"])
        self.assertFalse(boundaries["beneficial_ownership_claim_authorized"])
        self.assertFalse(boundaries["legal_or_economic_equivalence_claim_authorized"])
        self.assertFalse(boundaries["holder_rights_claim_authorized"])
        self.assertFalse(boundaries["trade_recommendation_authorized"])


if __name__ == "__main__":
    unittest.main()
