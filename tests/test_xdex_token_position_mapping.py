import unittest

from liquidity_scout.providers.x1.xdex_token_position_mapping import (
    verify_xdex_token_position_mapping,
)


PROGRAM = "Program111111111111111111111111111111111111"


def make_pool(i, *, reverse=False):
    token1 = f"MintA{i}"
    token2 = f"MintB{i}"
    return {
        "address": f"Pool{i}",
        "token1_address": token1,
        "token2_address": token2,
        "_rpc": (token2, token1) if reverse else (token1, token2),
    }


def verifier_from_rows(rows):
    by_pool = {row["address"]: row["_rpc"] for row in rows}

    def verifier(**kwargs):
        mint_0, mint_1 = by_pool[kwargs["account"]]
        if kwargs["target_mint"] not in {mint_0, mint_1}:
            return {"summary": {"pool_state_structural_role_verified": False}}
        return {
            "decoded_state": {"mint_0": mint_0, "mint_1": mint_1},
            "summary": {"pool_state_structural_role_verified": True},
        }

    return verifier


class XDEXTokenPositionMappingTests(unittest.TestCase):
    def test_verifies_stable_token1_to_mint0_mapping(self):
        rows = [make_pool(i) for i in range(4)]
        ninja = [{"address": row["address"]} for row in rows]

        result = verify_xdex_token_position_mapping(
            ninja_pools=ninja,
            xdex_pools=rows,
            structural_verifier=verifier_from_rows(rows),
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["position_mapping_verified"])
        self.assertEqual(
            result["stable_mapping"],
            "token1_to_mint0__token2_to_mint1",
        )
        self.assertEqual(result["verified_sample_count"], 4)
        self.assertFalse(result["base_quote_semantics_verified"])
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_verifies_stable_reversed_mapping_without_calling_it_base_quote(self):
        rows = [make_pool(i, reverse=True) for i in range(3)]
        ninja = [{"address": row["address"]} for row in rows]

        result = verify_xdex_token_position_mapping(
            ninja_pools=ninja,
            xdex_pools=rows,
            structural_verifier=verifier_from_rows(rows),
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
        )

        self.assertTrue(result["position_mapping_verified"])
        self.assertEqual(
            result["stable_mapping"],
            "token1_to_mint1__token2_to_mint0",
        )
        self.assertFalse(result["provider_base_quote_orientation_verified"])

    def test_mixed_mapping_fails_closed(self):
        rows = [make_pool(0), make_pool(1), make_pool(2, reverse=True)]
        ninja = [{"address": row["address"]} for row in rows]

        result = verify_xdex_token_position_mapping(
            ninja_pools=ninja,
            xdex_pools=rows,
            structural_verifier=verifier_from_rows(rows),
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["position_mapping_verified"])
        self.assertIsNone(result["stable_mapping"])

    def test_requires_three_verified_pools(self):
        rows = [make_pool(0), make_pool(1)]
        ninja = [{"address": row["address"]} for row in rows]

        result = verify_xdex_token_position_mapping(
            ninja_pools=ninja,
            xdex_pools=rows,
            structural_verifier=verifier_from_rows(rows),
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["position_mapping_verified"])

    def test_does_not_use_symbol_only_matches(self):
        xdex = [
            {
                "address": "Pool1",
                "token1_symbol": "AAA",
                "token2_symbol": "BBB",
            }
        ]
        ninja = [{"address": "Pool1"}]

        result = verify_xdex_token_position_mapping(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=lambda **kwargs: None,
            recognized_program_ids=(PROGRAM,),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sample_count"], 0)

    def test_validates_sample_thresholds(self):
        with self.assertRaises(ValueError):
            verify_xdex_token_position_mapping(
                ninja_pools=[],
                xdex_pools=[],
                min_verified_pools=2,
            )
        with self.assertRaises(ValueError):
            verify_xdex_token_position_mapping(
                ninja_pools=[],
                xdex_pools=[],
                min_verified_pools=4,
                max_samples=3,
            )


if __name__ == "__main__":
    unittest.main()
