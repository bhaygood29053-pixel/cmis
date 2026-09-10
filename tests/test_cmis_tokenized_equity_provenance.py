import unittest

from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    TOKENIZED_EQUITY_PROVENANCE_CONTRACT,
    build_tokenized_equity_provenance,
)


ROBINHOOD_ASSET = "0xbc191b1d09e51cbe10c15c9191086931b5876b83"
X1_ASSET = "ExampleEquityX1Mint11111111111111111111111111"


def endpoint(chain, asset_id, asset_id_kind):
    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


def base_cross_chain():
    origin = endpoint("Robinhood Chain", ROBINHOOD_ASSET, "contract_address")
    current = endpoint("x1", X1_ASSET, "mint")
    return build_cross_chain_asset_provenance(
        canonical_asset_id="equity-security-example",
        origin=origin,
        current=current,
        hops=[
            {
                "source": origin,
                "destination": current,
                "bridge": "candidate bridge",
                "representation_type": "bridge_representation",
                "custody_model": "external_dependency",
                "bridge_route_id": "candidate-route",
            }
        ],
    )


class CMISTokenizedEquityProvenanceTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "token": endpoint("x1", X1_ASSET, "mint"),
            "underlying_security": {
                "security_id": "US0378331005",
                "security_id_kind": "isin",
            },
            "representation_type": "tokenized_security_representation",
            "issuer": {
                "name": "Example Issuer",
                "legal_entity_id": "549300EXAMPLE0000001",
                "legal_entity_id_kind": "lei",
            },
            "backing_model": "issuer-described 1:1 backing",
            "custody_model": "external custodian dependency",
            "wrapper_layers": [
                {
                    "layer_type": "destination_chain_representation",
                    "token": endpoint("x1", X1_ASSET, "mint"),
                    "operator": "Example Operator",
                }
            ],
            "cross_chain_provenance": base_cross_chain(),
            "evidence_ids": ["issuer-doc-1", "route-evidence-1"],
        }
        values.update(overrides)
        return build_tokenized_equity_provenance(**values)

    def test_builds_bounded_non_promoted_structural_record(self):
        result = self.build()

        self.assertEqual(result["contract"], TOKENIZED_EQUITY_PROVENANCE_CONTRACT)
        self.assertEqual(result["token"]["chain"], "x1")
        self.assertEqual(
            result["underlying_security"],
            {"security_id": "US0378331005", "security_id_kind": "isin"},
        )
        self.assertTrue(
            result["verification"]["exact_token_identity_structurally_bound"]
        )
        self.assertTrue(
            result["verification"]["exact_underlying_security_id_structurally_bound"]
        )
        self.assertTrue(
            result["verification"]["cross_chain_structural_continuity_verified"]
        )
        self.assertFalse(result["verification"]["issuer_identity_verified"])
        self.assertFalse(result["verification"]["backing_verified"])
        self.assertFalse(result["verification"]["custody_verified"])
        self.assertFalse(result["verification"]["holder_rights_verified"])
        self.assertFalse(result["verification"]["live_deployment_verified"])
        self.assertFalse(result["verification"]["live_bridge_route_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_token_representation_never_becomes_underlying_share_or_rights_claim(self):
        result = self.build()
        boundaries = result["boundaries"]

        self.assertFalse(boundaries["token_equals_underlying_share_claim_authorized"])
        self.assertFalse(boundaries["direct_shareholder_ownership_claim_authorized"])
        self.assertFalse(boundaries["beneficial_ownership_claim_authorized"])
        self.assertFalse(boundaries["voting_rights_claim_authorized"])
        self.assertFalse(boundaries["dividend_rights_claim_authorized"])
        self.assertFalse(boundaries["redemption_rights_claim_authorized"])
        self.assertFalse(boundaries["legal_or_economic_equivalence_claim_authorized"])
        self.assertFalse(boundaries["legal_advice_authorized"])
        self.assertFalse(boundaries["trade_recommendation_authorized"])

    def test_cross_chain_attachment_preserves_structural_not_live_route_semantics(self):
        result = self.build()
        cross_chain = result["cross_chain"]

        self.assertEqual(cross_chain["origin"]["chain"], "robinhood chain")
        self.assertEqual(cross_chain["current"]["chain"], "x1")
        self.assertTrue(cross_chain["structural_continuity_verified"])
        self.assertFalse(cross_chain["live_bridge_state_verified"])
        self.assertFalse(result["boundaries"]["bridge_availability_claim_authorized"])
        self.assertFalse(result["boundaries"]["x1_live_support_claim_authorized"])

    def test_cross_chain_current_must_equal_token(self):
        with self.assertRaisesRegex(ValueError, "must equal tokenized equity token"):
            self.build(
                token=endpoint(
                    "x1",
                    "DifferentX1Mint111111111111111111111111111",
                    "mint",
                )
            )

    def test_symbol_or_ticker_cannot_be_used_as_token_identity(self):
        with self.assertRaisesRegex(ValueError, "symbol/name labels"):
            self.build(token=endpoint("x1", "AAPL", "ticker"))

    def test_underlying_security_requires_exact_identifier_kind(self):
        with self.assertRaisesRegex(ValueError, "accepted exact security identifier"):
            self.build(
                underlying_security={
                    "security_id": "AAPL",
                    "security_id_kind": "ticker",
                }
            )

    def test_representation_type_is_controlled_but_not_verified_by_builder(self):
        result = self.build(representation_type="synthetic_equity_exposure")
        self.assertEqual(
            result["representation"]["type"], "synthetic_equity_exposure"
        )
        self.assertFalse(
            result["verification"]["representation_classification_verified"]
        )

        with self.assertRaisesRegex(ValueError, "representation_type"):
            self.build(representation_type="actual stock definitely")

    def test_issuer_legal_entity_identifier_must_be_complete_pair(self):
        issuer = {
            "name": "Example Issuer",
            "legal_entity_id": "549300EXAMPLE0000001",
        }
        with self.assertRaisesRegex(ValueError, "provided together"):
            self.build(issuer=issuer)

    def test_evidence_ids_are_selectors_and_deduplicated(self):
        result = self.build(
            evidence_ids=["issuer-doc-1", "issuer-doc-1", "route-evidence-1"]
        )
        self.assertEqual(
            result["evidence_ids"], ["issuer-doc-1", "route-evidence-1"]
        )
        self.assertFalse(result["boundaries"]["descriptive_claims_are_verified_facts"])

    def test_contract_can_exist_without_cross_chain_claim(self):
        result = self.build(cross_chain_provenance=None)
        self.assertIsNone(result["cross_chain"])
        self.assertFalse(
            result["verification"]["cross_chain_structural_continuity_verified"]
        )
        self.assertFalse(result["verification"]["live_bridge_route_verified"])


if __name__ == "__main__":
    unittest.main()
