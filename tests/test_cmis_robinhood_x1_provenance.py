import unittest

from liquidity_scout.services.cmis_cross_chain_provenance import (
    PROVENANCE_CONTRACT,
    ROBINHOOD_X1_EXTENSION_CONTRACT,
    build_cross_chain_asset_provenance,
    build_robinhood_x1_provenance_extension,
)


ROBINHOOD_ASSET = "0xbc191b1d09e51cbe10c15c9191086931b5876b83"
X1_REPRESENTATION = "ExampleRobinhoodX1Representation111111111111"


def endpoint(chain, asset_id, asset_id_kind):
    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


def direct_hop():
    return {
        "source": endpoint(
            "Robinhood Chain",
            ROBINHOOD_ASSET,
            "contract_address",
        ),
        "destination": endpoint(
            "x1",
            X1_REPRESENTATION,
            "mint",
        ),
        "bridge": "Warp Bridge",
        "representation_type": "bridge_representation",
        "custody_model": "external_dependency",
        "bridge_route_id": "candidate-robinhood-x1-route",
    }


class CMISRobinhoodX1ProvenanceTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "canonical_asset_id": "69eleven",
            "origin": endpoint(
                "Robinhood Chain",
                ROBINHOOD_ASSET,
                "contract_address",
            ),
            "current": endpoint("x1", X1_REPRESENTATION, "mint"),
            "hops": [direct_hop()],
            "source_asset_class": "tokenized_market_asset",
            "custody_dependency": "Robinhood",
            "route_evidence_id": "route-candidate-1",
        }
        values.update(overrides)
        return build_robinhood_x1_provenance_extension(**values)

    def test_extension_composes_existing_v1_without_promoting_live_truth(self):
        result = self.build()

        self.assertEqual(
            result["contract"],
            ROBINHOOD_X1_EXTENSION_CONTRACT,
        )
        self.assertEqual(
            result["base_provenance_contract"],
            PROVENANCE_CONTRACT,
        )
        self.assertTrue(
            result["source_context"]["direct_robinhood_to_x1_hop_present"]
        )
        self.assertTrue(
            result["verification"]["robinhood_origin_structurally_bound"]
        )
        self.assertTrue(
            result["verification"]["x1_destination_structurally_bound"]
        )
        self.assertFalse(
            result["verification"]["live_robinhood_x1_route_verified"]
        )
        self.assertFalse(result["verification"]["custody_verified"])
        self.assertFalse(result["verification"]["backing_verified"])
        self.assertFalse(
            result["boundaries"]["tokenized_equity_ownership_claim_authorized"]
        )
        self.assertFalse(result["execution_authorized"])

    def test_existing_v1_output_contract_is_unchanged(self):
        base = build_cross_chain_asset_provenance(
            canonical_asset_id="69eleven",
            origin=endpoint(
                "Robinhood Chain",
                ROBINHOOD_ASSET,
                "contract_address",
            ),
            current=endpoint("x1", X1_REPRESENTATION, "mint"),
            hops=[direct_hop()],
        )

        self.assertEqual(base["contract"], PROVENANCE_CONTRACT)
        self.assertNotIn("source_context", base)
        self.assertNotIn("boundaries", base)

    def test_non_robinhood_origin_fails_closed(self):
        hop = direct_hop()
        hop["source"] = endpoint(
            "ethereum",
            ROBINHOOD_ASSET,
            "contract_address",
        )

        with self.assertRaisesRegex(ValueError, "Robinhood"):
            self.build(
                origin=endpoint(
                    "ethereum",
                    ROBINHOOD_ASSET,
                    "contract_address",
                ),
                hops=[hop],
            )

    def test_non_x1_destination_fails_closed(self):
        hop = direct_hop()
        hop["destination"] = endpoint(
            "ethereum",
            "0x" + ("11" * 20),
            "contract_address",
        )

        with self.assertRaisesRegex(ValueError, "current chain x1"):
            self.build(
                current=endpoint(
                    "ethereum",
                    "0x" + ("11" * 20),
                    "contract_address",
                ),
                hops=[hop],
            )

    def test_symbol_identity_is_still_rejected_by_base_contract(self):
        hop = direct_hop()
        hop["source"] = endpoint("Robinhood Chain", "69ELEVEN", "symbol")

        with self.assertRaisesRegex(ValueError, "symbol/name labels"):
            self.build(
                origin=endpoint(
                    "Robinhood Chain",
                    "69ELEVEN",
                    "symbol",
                ),
                hops=[hop],
            )


if __name__ == "__main__":
    unittest.main()
