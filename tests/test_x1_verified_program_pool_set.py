import unittest

from liquidity_scout.providers.x1.verified_program_pool_set import (
    verify_recognized_program_asset_pool_set,
)


PROGRAM = "program"
TARGET = "target-mint"
QUOTE = "quote-mint"


def _token(symbol, mint):
    return {"symbol": symbol, "name": symbol, "mint": mint}


def _pool(address, base_symbol, base_mint, quote_symbol, quote_mint, liquidity):
    return {
        "address": address,
        "baseToken": _token(base_symbol, base_mint),
        "quoteToken": _token(quote_symbol, quote_mint),
        "liquidity": liquidity,
        "volume24h": liquidity / 10,
    }


CATALOG = [
    _pool("pool-a", "TARGET", TARGET, "QUOTE", QUOTE, 1000),
    _pool("pool-b", "B", "mint-b", "QUOTE", QUOTE, 900),
    _pool("pool-c", "C", "mint-c", "QUOTE", QUOTE, 800),
    _pool("pool-d", "D", "mint-d", "QUOTE", QUOTE, 700),
]


def inventory_provider(**kwargs):
    return {
        "programs": [
            {
                "program_id": PROGRAM,
                "accounts": [
                    {
                        "pubkey": address,
                        "space": 637,
                        "owner_matches_program": True,
                    }
                    for address in ("pool-a", "pool-b", "pool-c", "pool-d")
                ],
            }
        ],
        "summary": {"all_responses_integrity_verified": True},
    }


def layout_verifier(pools, **kwargs):
    return {
        "summary": {
            "pool_mint_pair_layout_verified": True,
            "verified_families": [
                {
                    "program_id": PROGRAM,
                    "space": 637,
                    "stable_mint_offsets": [168, 200],
                    "sample_count": len(pools),
                }
            ],
        }
    }


def discovery_provider(**kwargs):
    return {
        "accounts": [
            {"pubkey": "pool-a"},
            {"pubkey": "pool-hidden"},
        ],
        "summary": {
            "targeted_program_family_mint_filter_observed": True,
        },
        "errors": [],
    }


def successful_role_verifier(**kwargs):
    account = kwargs["account"]
    target_mint = kwargs["target_mint"]
    if account == "pool-hidden":
        mint_0, mint_1 = QUOTE, TARGET
    elif account == "pool-a":
        mint_0, mint_1 = TARGET, QUOTE
    else:
        mint_0, mint_1 = target_mint, QUOTE
    return {
        "account": account,
        "decoded_state": {
            "mint_0": mint_0,
            "mint_1": mint_1,
        },
        "summary": {
            "pool_state_structural_role_verified": True,
            "recent_recognized_instruction_coupling_observed": True,
        },
        "errors": [],
    }


class VerifiedProgramPoolSetTests(unittest.TestCase):
    def test_promotes_complete_set_only_within_verified_program_scope(self):
        report = verify_recognized_program_asset_pool_set(
            asset_mint=TARGET,
            catalog_pools=CATALOG,
            rpc_url="rpc",
            layout_sample_pools=4,
            min_layout_pools=3,
            inventory_provider=inventory_provider,
            layout_verifier=layout_verifier,
            discovery_provider=discovery_provider,
            role_verifier=successful_role_verifier,
        )

        self.assertEqual(
            report["status"],
            "recognized_program_asset_pool_set_structurally_verified",
        )
        self.assertEqual(report["program_id"], PROGRAM)
        self.assertEqual(report["account_space"], 637)
        self.assertEqual(report["mint_offsets"], [168, 200])
        self.assertEqual(len(report["pools"]), 2)
        self.assertTrue(
            report["summary"][
                "recognized_program_asset_pool_set_structurally_verified"
            ]
        )
        self.assertEqual(
            report["summary"]["noncatalog_verified_program_pool_count"],
            1,
        )
        self.assertFalse(
            report["summary"]["recognized_program_registry_globally_exhaustive"]
        )
        self.assertFalse(
            report["summary"]["global_onchain_pool_discovery_proven"]
        )

    def test_one_structural_failure_blocks_program_pool_set_verification(self):
        def role_verifier(**kwargs):
            report = successful_role_verifier(**kwargs)
            if kwargs["account"] == "pool-hidden":
                report["summary"]["pool_state_structural_role_verified"] = False
            return report

        report = verify_recognized_program_asset_pool_set(
            asset_mint=TARGET,
            catalog_pools=CATALOG,
            rpc_url="rpc",
            layout_sample_pools=4,
            min_layout_pools=3,
            inventory_provider=inventory_provider,
            layout_verifier=layout_verifier,
            discovery_provider=discovery_provider,
            role_verifier=role_verifier,
        )

        self.assertEqual(report["status"], "partial")
        self.assertFalse(
            report["summary"][
                "recognized_program_asset_pool_set_structurally_verified"
            ]
        )
        self.assertEqual(report["summary"]["matching_program_state_account_count"], 2)
        self.assertEqual(report["summary"]["verified_program_pool_count"], 1)

    def test_unverified_mint_layout_fails_closed_before_discovery(self):
        discovery_calls = []

        def no_layout(pools, **kwargs):
            return {
                "summary": {
                    "pool_mint_pair_layout_verified": False,
                    "verified_families": [],
                }
            }

        def discovery(**kwargs):
            discovery_calls.append(kwargs)
            return discovery_provider(**kwargs)

        report = verify_recognized_program_asset_pool_set(
            asset_mint=TARGET,
            catalog_pools=CATALOG,
            rpc_url="rpc",
            layout_sample_pools=4,
            min_layout_pools=3,
            inventory_provider=inventory_provider,
            layout_verifier=no_layout,
            discovery_provider=discovery,
            role_verifier=successful_role_verifier,
        )

        self.assertEqual(report["status"], "layout_not_verified")
        self.assertEqual(discovery_calls, [])
        self.assertFalse(
            report["summary"][
                "recognized_program_asset_pool_set_structurally_verified"
            ]
        )


if __name__ == "__main__":
    unittest.main()
