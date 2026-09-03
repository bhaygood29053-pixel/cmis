import unittest

from liquidity_scout.services.cmis_cross_chain_provenance import (
    PROVENANCE_CONTRACT,
    build_cross_chain_asset_provenance,
)


WSOL = "So11111111111111111111111111111111111111112"
WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
WETH_SOL = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utSqN12bhN7Jb"
ETH_X = "ExampleEthX111111111111111111111111111111111"


def endpoint(chain, asset_id, asset_id_kind="mint"):
    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


class CMISCrossChainProvenanceTests(unittest.TestCase):
    def test_direct_solana_to_x1_representation_is_deterministic_and_read_only(self):
        value = build_cross_chain_asset_provenance(
            canonical_asset_id="sol",
            origin=endpoint("Solana", WSOL),
            current=endpoint("X1", WSOL_X),
            hops=[
                {
                    "source": endpoint("solana", WSOL),
                    "destination": endpoint("x1", WSOL_X),
                    "bridge": "Warp Bridge",
                    "representation_type": "bridge_representation",
                    "custody_model": "unknown",
                }
            ],
        )

        self.assertEqual(value["contract"], PROVENANCE_CONTRACT)
        self.assertEqual(value["origin"]["chain"], "solana")
        self.assertEqual(value["current"]["chain"], "x1")
        self.assertEqual(value["representation_depth"], 1)
        self.assertTrue(value["verification"]["structural_continuity_verified"])
        self.assertFalse(value["verification"]["live_bridge_state_verified"])
        self.assertFalse(value["public_service_promoted"])
        self.assertFalse(value["scout_reliance_promoted"])
        self.assertFalse(value["execution_authorized"])

    def test_multihop_eth_lineage_preserves_every_chain_boundary(self):
        value = build_cross_chain_asset_provenance(
            canonical_asset_id="eth",
            origin=endpoint("ethereum", "0x0000000000000000000000000000000000000000", "native_asset"),
            current=endpoint("x1", ETH_X),
            hops=[
                {
                    "source": endpoint(
                        "ethereum",
                        "0x0000000000000000000000000000000000000000",
                        "native_asset",
                    ),
                    "destination": endpoint("solana", WETH_SOL),
                    "bridge": "Wormhole",
                    "representation_type": "wrapped_representation",
                    "custody_model": "unknown",
                },
                {
                    "source": endpoint("solana", WETH_SOL),
                    "destination": endpoint("x1", ETH_X),
                    "bridge": "Warp Bridge",
                    "representation_type": "bridge_representation",
                    "custody_model": "unknown",
                },
            ],
        )

        self.assertEqual(value["representation_depth"], 2)
        self.assertEqual(
            [hop["destination"]["chain"] for hop in value["lineage"]],
            ["solana", "x1"],
        )
        self.assertEqual(
            [item["bridge"] for item in value["dependencies"]],
            ["Wormhole", "Warp Bridge"],
        )

    def test_symbol_only_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "symbol/name labels"):
            build_cross_chain_asset_provenance(
                canonical_asset_id="sol",
                origin=endpoint("solana", "SOL", "symbol"),
                current=endpoint("x1", WSOL_X),
                hops=[
                    {
                        "source": endpoint("solana", "SOL", "symbol"),
                        "destination": endpoint("x1", WSOL_X),
                        "bridge": "Warp Bridge",
                        "representation_type": "bridge_representation",
                    }
                ],
            )

    def test_discontinuous_lineage_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "prior hop destination"):
            build_cross_chain_asset_provenance(
                canonical_asset_id="eth",
                origin=endpoint(
                    "ethereum",
                    "0x0000000000000000000000000000000000000000",
                    "native_asset",
                ),
                current=endpoint("x1", ETH_X),
                hops=[
                    {
                        "source": endpoint(
                            "ethereum",
                            "0x0000000000000000000000000000000000000000",
                            "native_asset",
                        ),
                        "destination": endpoint("solana", WETH_SOL),
                        "bridge": "Wormhole",
                        "representation_type": "wrapped_representation",
                    },
                    {
                        "source": endpoint("solana", "DifferentMint111"),
                        "destination": endpoint("x1", ETH_X),
                        "bridge": "Warp Bridge",
                        "representation_type": "bridge_representation",
                    },
                ],
            )

    def test_final_destination_must_equal_current(self):
        with self.assertRaisesRegex(ValueError, "final hop destination"):
            build_cross_chain_asset_provenance(
                canonical_asset_id="sol",
                origin=endpoint("solana", WSOL),
                current=endpoint("x1", "OtherMint111"),
                hops=[
                    {
                        "source": endpoint("solana", WSOL),
                        "destination": endpoint("x1", WSOL_X),
                        "bridge": "Warp Bridge",
                        "representation_type": "bridge_representation",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
