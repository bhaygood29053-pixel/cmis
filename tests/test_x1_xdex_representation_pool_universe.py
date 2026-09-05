import unittest

from liquidity_scout.providers.x1.xdex_representation_pool_universe import (
    XDEXRepresentationPoolUniverseError,
    apply_verified_program_window_to_zero_universe,
    build_xdex_representation_pool_universe,
    build_xdex_representation_pool_universe_from_program_set,
    select_representation_pool_candidates,
)
from liquidity_scout.services.cmis_bridge_to_xdex_utilization import (
    POOL_UNIVERSE_CONTRACT,
)


WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
OTHER = "OtherMint11111111111111111111111111111111111"


def nested_pool(address="PoolA", representation=WSOL_X):
    return {
        "address": address,
        "baseToken": {"mint": representation},
        "quoteToken": {"mint": OTHER},
    }


def flat_pool(address="PoolB", representation=WSOL_X):
    return {
        "address": address,
        "token1_mint": OTHER,
        "token2_mint": representation,
    }


def report(address):
    return {
        "service": "candidate_pool_role_verification",
        "account": address,
        "target_mint": WSOL_X,
        "program_id": "Program111",
        "account_space": 637,
        "decoded_state": {
            "target_mint_present": True,
        },
        "summary": {
            "state_integrity_verified": True,
            "program_owner_verified": True,
            "both_vaults_verified": True,
            "shared_vault_authority_verified": True,
            "pool_state_structural_role_verified": True,
            "pool_role_promoted": True,
        },
    }


class XDEXRepresentationPoolUniverseTests(unittest.TestCase):
    def test_selects_nested_and_flat_exact_mint_candidates(self):
        result = select_representation_pool_candidates(
            [nested_pool(), flat_pool()],
            representation_mint=WSOL_X,
        )
        self.assertEqual(
            result["candidate_pool_addresses"],
            ["PoolA", "PoolB"],
        )
        self.assertEqual(result["selection_unresolved"], [])

    def test_builds_verified_provider_scoped_pool_universe(self):
        pools = [nested_pool(), flat_pool(), nested_pool("OtherPool", OTHER)]
        result = build_xdex_representation_pool_universe(
            representation_mint=WSOL_X,
            xdex_pools=pools,
            structural_reports_by_address={
                "PoolA": report("PoolA"),
                "PoolB": report("PoolB"),
            },
            observed_at=1_788_600_000,
        )
        self.assertEqual(result["contract"], POOL_UNIVERSE_CONTRACT)
        self.assertEqual(result["representation_candidate_pool_count"], 2)
        self.assertEqual(result["verified_pool_count"], 2)
        self.assertEqual(result["pool_addresses"], ["PoolA", "PoolB"])
        self.assertEqual(result["unresolved_pools"], [])
        self.assertTrue(result["enumeration_verified"])
        self.assertTrue(result["all_pool_identities_verified"])
        self.assertTrue(result["provider_catalog_scope_complete"])
        self.assertFalse(
            result["recognized_program_registry_globally_exhaustive"]
        )
        self.assertFalse(result["global_onchain_pool_discovery_proven"])
        self.assertFalse(result["liquidity_semantics_verified"])
        self.assertFalse(result["volume_24h_semantics_verified"])
        self.assertFalse(result["market_freshness_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_missing_structural_report_keeps_universe_unverified(self):
        result = build_xdex_representation_pool_universe(
            representation_mint=WSOL_X,
            xdex_pools=[nested_pool()],
            structural_reports_by_address={},
            observed_at=1_788_600_000,
        )
        self.assertFalse(result["enumeration_verified"])
        self.assertFalse(result["all_pool_identities_verified"])
        self.assertEqual(result["verified_pool_count"], 0)
        self.assertEqual(
            result["unresolved_pools"][0]["reason"],
            "missing_structural_pool_report",
        )

    def test_unverified_structural_role_keeps_pool_unresolved(self):
        bad = report("PoolA")
        bad["summary"]["pool_state_structural_role_verified"] = False
        result = build_xdex_representation_pool_universe(
            representation_mint=WSOL_X,
            xdex_pools=[nested_pool()],
            structural_reports_by_address={"PoolA": bad},
            observed_at=1_788_600_000,
        )
        self.assertFalse(result["enumeration_verified"])
        self.assertEqual(
            result["unresolved_pools"][0]["reason"],
            "pool_state_structural_role_unverified",
        )

    def test_duplicate_representation_pool_address_is_unresolved(self):
        result = build_xdex_representation_pool_universe(
            representation_mint=WSOL_X,
            xdex_pools=[nested_pool(), nested_pool()],
            structural_reports_by_address={"PoolA": report("PoolA")},
            observed_at=1_788_600_000,
        )
        self.assertFalse(result["enumeration_verified"])
        self.assertIn(
            "duplicate_representation_pool_address",
            {row["reason"] for row in result["unresolved_pools"]},
        )

    def test_same_representation_on_both_sides_is_unresolved(self):
        row = {
            "address": "PoolA",
            "baseToken": {"mint": WSOL_X},
            "quoteToken": {"mint": WSOL_X},
        }
        result = build_xdex_representation_pool_universe(
            representation_mint=WSOL_X,
            xdex_pools=[row],
            structural_reports_by_address={"PoolA": report("PoolA")},
            observed_at=1_788_600_000,
        )
        self.assertFalse(result["enumeration_verified"])
        self.assertEqual(
            result["unresolved_pools"][0]["reason"],
            "representation_mint_matches_multiple_pool_sides",
        )

    def test_unrelated_pool_does_not_require_structural_report(self):
        unrelated = nested_pool("OtherPool", OTHER)
        result = build_xdex_representation_pool_universe(
            representation_mint=WSOL_X,
            xdex_pools=[unrelated],
            structural_reports_by_address={},
            observed_at=1_788_600_000,
        )
        self.assertTrue(result["enumeration_verified"])
        self.assertEqual(result["representation_candidate_pool_count"], 0)
        self.assertEqual(result["pool_addresses"], [])

    def test_rejects_invalid_pool_sequence(self):
        with self.assertRaisesRegex(
            XDEXRepresentationPoolUniverseError,
            "xdex_pools must be a sequence",
        ):
            select_representation_pool_candidates(
                {"address": "PoolA"},
                representation_mint=WSOL_X,
            )

    def test_program_set_adapter_preserves_explicit_verified_zero_scope(self):
        program_set = {
            "service": "verified_program_asset_pool_set",
            "status": "recognized_program_asset_pool_set_structurally_verified",
            "asset_mint": WSOL_X,
            "program_id": "Program111",
            "pools": [],
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": True,
                "targeted_program_family_mint_filter_observed": True,
                "all_matching_accounts_structurally_verified": True,
                "all_catalog_asset_pools_recovered": True,
                "verified_zero_set": True,
            },
        }
        result = build_xdex_representation_pool_universe_from_program_set(
            program_pool_set=program_set,
            observed_at=1_788_600_000,
        )
        self.assertTrue(result["enumeration_verified"])
        self.assertTrue(result["all_pool_identities_verified"])
        self.assertTrue(result["verified_zero_set"])
        self.assertEqual(result["pool_addresses"], [])
        self.assertTrue(result["current_liquidity_zero_verified"])
        self.assertTrue(result["liquidity_semantics_verified"])
        self.assertFalse(result["volume_24h_semantics_verified"])
        self.assertFalse(result["volume_24h_window_coverage_verified"])
        self.assertFalse(result["global_onchain_pool_discovery_proven"])
        self.assertFalse(result["execution_authorized"])

    def test_program_set_adapter_rejects_unverified_empty_set(self):
        program_set = {
            "service": "verified_program_asset_pool_set",
            "status": "recognized_program_asset_pool_set_structurally_verified",
            "asset_mint": WSOL_X,
            "program_id": "Program111",
            "pools": [],
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": True,
                "targeted_program_family_mint_filter_observed": True,
                "all_matching_accounts_structurally_verified": True,
                "all_catalog_asset_pools_recovered": True,
                "verified_zero_set": False,
            },
        }
        with self.assertRaisesRegex(
            XDEXRepresentationPoolUniverseError,
            "lacks explicit verified-zero",
        ):
            build_xdex_representation_pool_universe_from_program_set(
                program_pool_set=program_set,
                observed_at=1_788_600_000,
            )

    def test_program_set_adapter_validates_nonzero_pool_contains_mint(self):
        program_set = {
            "service": "verified_program_asset_pool_set",
            "status": "recognized_program_asset_pool_set_structurally_verified",
            "asset_mint": WSOL_X,
            "program_id": "Program111",
            "pools": [
                {
                    "pool_address": "PoolA",
                    "mint_0": WSOL_X,
                    "mint_1": OTHER,
                    "catalog_listed": False,
                    "pool_state_structural_role_verified": True,
                }
            ],
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": True,
                "targeted_program_family_mint_filter_observed": True,
                "all_matching_accounts_structurally_verified": True,
                "all_catalog_asset_pools_recovered": True,
                "verified_zero_set": False,
            },
        }
        result = build_xdex_representation_pool_universe_from_program_set(
            program_pool_set=program_set,
            observed_at=1_788_600_000,
        )
        self.assertFalse(result["verified_zero_set"])
        self.assertEqual(result["pool_addresses"], ["PoolA"])
        self.assertFalse(result["liquidity_semantics_verified"])
        self.assertFalse(result["market_freshness_verified"])

    def test_verified_program_window_promotes_only_24h_zero_on_zero_universe(self):
        universe = build_xdex_representation_pool_universe_from_program_set(
            program_pool_set={
                "service": "verified_program_asset_pool_set",
                "status": "recognized_program_asset_pool_set_structurally_verified",
                "asset_mint": WSOL_X,
                "program_id": "Program111",
                "pools": [],
                "summary": {
                    "recognized_program_asset_pool_set_structurally_verified": True,
                    "targeted_program_family_mint_filter_observed": True,
                    "all_matching_accounts_structurally_verified": True,
                    "all_catalog_asset_pools_recovered": True,
                    "verified_zero_set": True,
                },
            },
            observed_at=1_788_600_000,
        )
        activity = {
            "contract": "xdex_program_asset_window_activity/v1",
            "program_id": "Program111",
            "asset_mint": WSOL_X,
            "requested_window": {
                "start_epoch": 1_788_513_600.0,
                "end_epoch": 1_788_600_000.0,
                "duration_seconds": 86400.0,
            },
            "program_signature_range_proven": True,
            "program_signature_integrity_verified": True,
            "all_successful_transactions_verified": True,
            "window_trace_complete_verified": True,
            "program_scoped_asset_activity_zero_verified": True,
            "volume_24h_window_coverage_verified": True,
            "volume_24h_semantics_verified": True,
            "verified_volume_24h_value": "0",
            "verified_volume_24h_unit": "USD",
            "target_mint_activity_transaction_count": 0,
            "target_mint_delta_count": 0,
            "window_signature_count": 12,
            "zero_authorization_basis": "complete_program_trace",
            "execution_authorized": False,
        }

        enriched = apply_verified_program_window_to_zero_universe(
            pool_universe=universe,
            program_window_activity=activity,
        )
        self.assertTrue(enriched["verified_zero_set"])
        self.assertTrue(enriched["current_liquidity_zero_verified"])
        self.assertTrue(enriched["volume_24h_semantics_verified"])
        self.assertTrue(enriched["volume_24h_window_coverage_verified"])
        self.assertEqual(enriched["verified_volume_24h_value"], "0")
        self.assertEqual(enriched["program_window_activity_signature_count"], 12)
        self.assertFalse(enriched["cmis_promotable"])
        self.assertFalse(enriched["execution_authorized"])

    def test_program_window_cannot_bind_target_activity_as_zero(self):
        universe = build_xdex_representation_pool_universe_from_program_set(
            program_pool_set={
                "service": "verified_program_asset_pool_set",
                "status": "recognized_program_asset_pool_set_structurally_verified",
                "asset_mint": WSOL_X,
                "program_id": "Program111",
                "pools": [],
                "summary": {
                    "recognized_program_asset_pool_set_structurally_verified": True,
                    "targeted_program_family_mint_filter_observed": True,
                    "all_matching_accounts_structurally_verified": True,
                    "all_catalog_asset_pools_recovered": True,
                    "verified_zero_set": True,
                },
            },
            observed_at=1_788_600_000,
        )
        activity = {
            "contract": "xdex_program_asset_window_activity/v1",
            "program_id": "Program111",
            "asset_mint": WSOL_X,
            "requested_window": {"duration_seconds": 86400.0},
            "program_signature_range_proven": True,
            "program_signature_integrity_verified": True,
            "all_successful_transactions_verified": True,
            "window_trace_complete_verified": True,
            "program_scoped_asset_activity_zero_verified": False,
            "volume_24h_window_coverage_verified": False,
            "volume_24h_semantics_verified": False,
            "verified_volume_24h_value": None,
            "verified_volume_24h_unit": None,
            "target_mint_activity_transaction_count": 1,
            "target_mint_delta_count": 2,
            "execution_authorized": False,
        }
        with self.assertRaisesRegex(
            XDEXRepresentationPoolUniverseError,
            "program_scoped_asset_activity_zero_verified",
        ):
            apply_verified_program_window_to_zero_universe(
                pool_universe=universe,
                program_window_activity=activity,
            )


if __name__ == "__main__":
    unittest.main()
