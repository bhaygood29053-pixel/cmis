import unittest

from liquidity_scout.providers.x1.rpc_vault_reserve_units import (
    verify_rpc_vault_reserve_units,
)


PROGRAM = "Program111111111111111111111111111111111111"


def rows(count=3):
    ninja = []
    xdex = []
    rpc = {}
    for i in range(count):
        pool = f"Pool{i}"
        mint0 = f"MintA{i}"
        mint1 = f"MintB{i}"
        vault0 = f"VaultA{i}"
        vault1 = f"VaultB{i}"
        ninja.append(
            {
                "address": pool,
                "pooledBase": str(100 + i),
                "pooledQuote": str(200 + i),
                "liquidity": str(999 + i),
            }
        )
        xdex.append(
            {
                "address": pool,
                "token1_address": mint0,
                "token2_address": mint1,
                "tvl": str(500 + i),
            }
        )
        rpc[pool] = {
            "mint_0": mint0,
            "mint_1": mint1,
            "vault_0": vault0,
            "vault_1": vault1,
        }
    return ninja, xdex, rpc


def structural_from(rpc):
    def verifier(**kwargs):
        decoded = rpc[kwargs["account"]]
        return {
            "decoded_state": decoded,
            "summary": {"pool_state_structural_role_verified": True},
        }
    return verifier


def token_fetcher(account, **kwargs):
    index = int(account[-1])
    if account.startswith("VaultA"):
        return {
            "account_exists": True,
            "identity_verified": True,
            "mint": f"MintA{index}",
            "raw_amount": "1234500",
            "decimals": 4,
            "ui_amount_string": "123.45",
            "token_authority": "Authority",
            "program_owner": "TokenProgram",
        }
    return {
        "account_exists": True,
        "identity_verified": True,
        "mint": f"MintB{index}",
        "raw_amount": "7",
        "decimals": 9,
        "ui_amount_string": "0.000000007",
        "token_authority": "Authority",
        "program_owner": "TokenProgram",
    }


class RPCVaultReserveUnitTests(unittest.TestCase):
    def test_verifies_raw_balances_decimals_and_exact_scaling(self):
        ninja, xdex, rpc = rows(3)

        result = verify_rpc_vault_reserve_units(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=structural_from(rpc),
            token_account_fetcher=token_fetcher,
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
            max_samples=3,
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["rpc_vault_balance_fields_verified"])
        self.assertTrue(result["rpc_vault_decimals_verified"])
        self.assertTrue(result["rpc_reserve_unit_scaling_verified"])
        self.assertTrue(result["rpc_vault_reserve_amounts_verified"])
        self.assertEqual(
            result["samples"][0]["vaults"][0]["scaled_amount"],
            "123.45",
        )
        self.assertEqual(
            result["samples"][0]["vaults"][1]["scaled_amount"],
            "0.000000007",
        )
        self.assertEqual(
            result["samples"][0]["provider_raw_candidates"]["x1_ninja"],
            {
                "pooledBase": "100",
                "pooledQuote": "200",
                "liquidity": "999",
            },
        )
        self.assertEqual(
            result["samples"][0]["provider_raw_candidates"]["xdex"],
            {"tvl": "500"},
        )
        self.assertFalse(result["provider_candidate_semantics_verified"])
        self.assertFalse(result["base_quote_semantics_verified"])
        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_raw_integer_scaling_preserves_zero_without_float_rounding(self):
        ninja, xdex, rpc = rows(3)

        def zero_fetcher(account, **kwargs):
            info = token_fetcher(account, **kwargs)
            info["raw_amount"] = "000000"
            info["decimals"] = 9
            info["ui_amount_string"] = "0"
            return info

        result = verify_rpc_vault_reserve_units(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=structural_from(rpc),
            token_account_fetcher=zero_fetcher,
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
            max_samples=3,
        )
        self.assertEqual(result["samples"][0]["vaults"][0]["scaled_amount"], "0")
        self.assertTrue(result["rpc_reserve_unit_scaling_verified"])

    def test_malformed_raw_amount_fails_closed(self):
        ninja, xdex, rpc = rows(3)

        def bad_fetcher(account, **kwargs):
            info = token_fetcher(account, **kwargs)
            if account == "VaultA1":
                info["raw_amount"] = "12.5"
            return info

        result = verify_rpc_vault_reserve_units(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=structural_from(rpc),
            token_account_fetcher=bad_fetcher,
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
            max_samples=3,
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["rpc_reserve_unit_scaling_verified"])
        self.assertIn(
            "vault_0_balance_or_unit_unverified",
            result["samples"][1]["rejection_reasons"],
        )

    def test_vault_mint_mismatch_fails_closed(self):
        ninja, xdex, rpc = rows(3)

        def mismatch_fetcher(account, **kwargs):
            info = token_fetcher(account, **kwargs)
            if account == "VaultB2":
                info["mint"] = "WRONG"
            return info

        result = verify_rpc_vault_reserve_units(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=structural_from(rpc),
            token_account_fetcher=mismatch_fetcher,
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
            max_samples=3,
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["rpc_vault_reserve_amounts_verified"])

    def test_position_mapping_mismatch_fails_closed_before_vault_semantics(self):
        ninja, xdex, rpc = rows(3)
        xdex[0]["token1_address"], xdex[0]["token2_address"] = (
            xdex[0]["token2_address"],
            xdex[0]["token1_address"],
        )

        result = verify_rpc_vault_reserve_units(
            ninja_pools=ninja,
            xdex_pools=xdex,
            structural_verifier=structural_from(rpc),
            token_account_fetcher=token_fetcher,
            recognized_program_ids=(PROGRAM,),
            min_verified_pools=3,
            max_samples=3,
        )

        self.assertEqual(result["status"], "partial")
        self.assertIn(
            "xdex_token_position_to_rpc_mint_mapping_mismatch",
            result["samples"][0]["rejection_reasons"],
        )

    def test_requires_at_least_three_samples(self):
        with self.assertRaises(ValueError):
            verify_rpc_vault_reserve_units(
                ninja_pools=[],
                xdex_pools=[],
                min_verified_pools=2,
            )


if __name__ == "__main__":
    unittest.main()
