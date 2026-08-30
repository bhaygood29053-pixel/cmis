import unittest

from liquidity_scout.providers.x1.exact_pool_triangulation import (
    triangulate_exact_pool_identity,
)


POOL = "POOL1"
MINT_A = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
MINT_B = "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
PROGRAM = "Program111111111111111111111111111111111111"


def verified_report(**kwargs):
    target = kwargs["target_mint"]
    if target not in {MINT_A, MINT_B}:
        raise ValueError("not a pool mint")
    return {
        "account": kwargs["account"],
        "decoded_state": {
            "mint_0": MINT_A,
            "mint_1": MINT_B,
            "vault_0": "VaultA",
            "vault_1": "VaultB",
        },
        "summary": {
            "pool_state_structural_role_verified": True,
            "both_vaults_verified": True,
        },
    }


class ExactPoolTriangulationTests(unittest.TestCase):
    def test_binds_exact_common_pool_and_declared_roles_to_rpc_mints(self):
        ninja = [
            {
                "address": POOL,
                "baseToken": {
                    "symbol": "AAA",
                    "address": "transport-a",
                    "mint": MINT_A,
                },
                "quoteToken": {
                    "symbol": "BBB",
                    "address": "transport-b",
                    "mint": MINT_B,
                },
                "liquidity": 123,
            }
        ]
        xdex = [
            {
                "address": POOL,
                "baseToken": {"address": MINT_A},
                "quoteToken": {"address": MINT_B},
                "tvl": 999,
            }
        ]

        result = triangulate_exact_pool_identity(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=verified_report,
            recognized_program_ids=(PROGRAM,),
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["pool_address"], POOL)
        self.assertEqual(set(result["rpc_mints"]), {MINT_A, MINT_B})
        self.assertTrue(result["identity"]["pool_identity_verified"])
        self.assertTrue(result["identity"]["token_set_identity_verified"])
        self.assertTrue(result["identity"]["provider_role_orientation_agreement"])
        self.assertTrue(result["identity"]["base_quote_orientation_verified"])
        self.assertFalse(
            result["identity"]["onchain_mint_slot_base_quote_semantics_verified"]
        )
        self.assertTrue(result["identity"]["rpc_mint_identity_verified"])
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_detects_provider_base_quote_disagreement_without_guessing(self):
        ninja = [
            {
                "address": POOL,
                "baseToken": {"mint": MINT_A},
                "quoteToken": {"mint": MINT_B},
            }
        ]
        xdex = [
            {
                "address": POOL,
                "baseToken": {"address": MINT_B},
                "quoteToken": {"address": MINT_A},
            }
        ]

        result = triangulate_exact_pool_identity(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=verified_report,
            recognized_program_ids=(PROGRAM,),
        )

        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["identity"]["pool_identity_verified"])
        self.assertTrue(result["identity"]["token_set_identity_verified"])
        self.assertFalse(result["identity"]["provider_role_orientation_agreement"])
        self.assertFalse(result["identity"]["base_quote_orientation_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_flat_xdex_token_positions_verify_set_not_base_quote_orientation(self):
        ninja = [
            {
                "address": POOL,
                "baseToken": {"mint": MINT_A},
                "quoteToken": {"mint": MINT_B},
            }
        ]
        xdex = [
            {
                "pool_address": POOL,
                "token1_address": MINT_A,
                "token2_address": MINT_B,
            }
        ]

        result = triangulate_exact_pool_identity(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=verified_report,
            recognized_program_ids=(PROGRAM,),
        )

        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["identity"]["token_set_identity_verified"])
        self.assertFalse(result["identity"]["base_quote_orientation_verified"])
        self.assertEqual(
            result["provider_identity"]["xdex"]["role_basis"],
            "provider_token1_token2",
        )

    def test_does_not_match_by_symbol_when_addresses_disagree(self):
        ninja = [
            {
                "address": POOL,
                "baseToken": {"symbol": "AAA", "mint": MINT_A},
                "quoteToken": {"symbol": "BBB", "mint": MINT_B},
            }
        ]
        xdex = [
            {
                "address": POOL,
                "baseToken": {"symbol": "AAA", "address": "OTHER_A"},
                "quoteToken": {"symbol": "BBB", "address": "OTHER_B"},
            }
        ]

        result = triangulate_exact_pool_identity(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=verified_report,
            recognized_program_ids=(PROGRAM,),
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["identity"]["token_set_identity_verified"])
        self.assertFalse(result["identity"]["base_quote_orientation_verified"])

    def test_fails_closed_when_no_exact_common_pool_address_exists(self):
        result = triangulate_exact_pool_identity(
            ninja_pools=[
                {
                    "address": "NINJA_ONLY",
                    "baseToken": {"mint": MINT_A},
                    "quoteToken": {"mint": MINT_B},
                }
            ],
            xdex_pools=[
                {
                    "address": "XDEX_ONLY",
                    "baseToken": {"address": MINT_A},
                    "quoteToken": {"address": MINT_B},
                }
            ],
            structural_verifier=verified_report,
            recognized_program_ids=(PROGRAM,),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["common_pool_count_observed"], 0)
        self.assertFalse(result["identity"]["pool_identity_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
