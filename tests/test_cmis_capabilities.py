import unittest

from liquidity_scout.cmis.capabilities import (
    CMIS_CONTRACT_VERSION,
    build_capability_manifest,
    service_capability,
    validate_capability_contract,
)
from liquidity_scout.cmis.gateway import KNOWN_CHAINS, SUPPORTED_CHAINS
from liquidity_scout.cmis.runtime_gateway import SUPPORTED_SERVICES
from liquidity_scout.cmis.x1_evidence_capabilities import (
    build_x1_evidence_capability_manifest,
    validate_x1_evidence_capability_manifest,
)
from liquidity_scout.services.cmis_bridge_to_xdex_public import (
    CONTRACT_VERSION as BRIDGE_TO_XDEX_CONTRACT_VERSION,
    SERVICE as BRIDGE_TO_XDEX_SERVICE,
)
from liquidity_scout.services.cmis_cross_chain_provenance_public import (
    CONTRACT_VERSION as CROSS_CHAIN_PROVENANCE_CONTRACT_VERSION,
    SERVICE as CROSS_CHAIN_PROVENANCE_SERVICE,
)
from liquidity_scout.services.cmis_burn_intelligence import (
    CONTRACT_VERSION as BURN_INTELLIGENCE_CONTRACT_VERSION,
    SERVICE as BURN_INTELLIGENCE_SERVICE,
)
from liquidity_scout.services.cmis_discovery_intelligence import (
    CONTRACT_VERSION as DISCOVERY_INTELLIGENCE_CONTRACT_VERSION,
    SERVICE as DISCOVERY_INTELLIGENCE_SERVICE,
)
from liquidity_scout.services.cmis_concentration_warning_intelligence import (
    CONTRACT_VERSION as CONCENTRATION_WARNING_CONTRACT_VERSION,
    SERVICE as CONCENTRATION_WARNING_SERVICE,
)
from liquidity_scout.services.cmis_verified_intelligence import (
    CONTRACT_VERSION as CONCENTRATION_INTELLIGENCE_CONTRACT_VERSION,
    SERVICE as CONCENTRATION_INTELLIGENCE_SERVICE,
)
from liquidity_scout.services.pre_trade_capabilities import (
    build_execution_capability_report,
)


class CMISCapabilityContractTests(unittest.TestCase):
    def test_runtime_surface_matches_capability_manifest(self):
        validate_capability_contract(
            runtime_services=SUPPORTED_SERVICES,
            known_chains=KNOWN_CHAINS,
        )
        validate_x1_evidence_capability_manifest()

        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )

        self.assertEqual(manifest["contract_version"], CMIS_CONTRACT_VERSION)
        self.assertEqual(CMIS_CONTRACT_VERSION, "1.22.0")
        self.assertEqual(set(manifest["chains"]), {"x1", "solana"})
        self.assertEqual(
            set(manifest["chains"]["x1"]["services"]),
            set(SUPPORTED_SERVICES),
        )
        self.assertEqual(
            set(manifest["chains"]["solana"]["services"]),
            set(SUPPORTED_SERVICES),
        )
        self.assertIn(CONCENTRATION_INTELLIGENCE_SERVICE, SUPPORTED_SERVICES)
        self.assertIn(CONCENTRATION_WARNING_SERVICE, SUPPORTED_SERVICES)
        self.assertIn("evidence_capabilities", manifest["chains"]["x1"])
        self.assertNotIn("evidence_capabilities", manifest["chains"]["solana"])

    def test_burn_intelligence_is_x1_only_bounded_public_service(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        x1 = service_capability(
            manifest,
            chain="x1",
            service=BURN_INTELLIGENCE_SERVICE,
        )
        solana = service_capability(
            manifest,
            chain="solana",
            service=BURN_INTELLIGENCE_SERVICE,
        )

        self.assertEqual(x1["state"], "bounded")
        self.assertTrue(x1["callable"])
        self.assertTrue(x1["read_only"])
        self.assertTrue(x1["public_service_promoted"])
        self.assertTrue(x1["scout_reliance_promoted"])
        self.assertEqual(
            x1["service_contract_version"],
            BURN_INTELLIGENCE_CONTRACT_VERSION,
        )
        self.assertIn("exact_x1_mint_identity", x1["requirements"])
        self.assertIn(
            "observed_cumulative_burn_is_not_lifetime_without_archive_completeness",
            x1["limitations"],
        )
        self.assertFalse(x1["execution_authorized"])

        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertFalse(solana["public_service_promoted"])
        self.assertFalse(solana["scout_reliance_promoted"])
        self.assertFalse(solana["execution_authorized"])

    def test_discovery_intelligence_is_x1_only_bounded_public_service(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        x1 = manifest["chains"]["x1"]["services"][DISCOVERY_INTELLIGENCE_SERVICE]
        solana = manifest["chains"]["solana"]["services"][DISCOVERY_INTELLIGENCE_SERVICE]

        self.assertEqual(x1["state"], "bounded")
        self.assertTrue(x1["callable"])
        self.assertTrue(x1["read_only"])
        self.assertTrue(x1["public_service_promoted"])
        self.assertTrue(x1["scout_reliance_promoted"])
        self.assertEqual(
            x1["service_contract_version"],
            DISCOVERY_INTELLIGENCE_CONTRACT_VERSION,
        )
        self.assertIn(
            "first_verified_observation_is_not_token_launch_time",
            x1["limitations"],
        )
        self.assertFalse(x1["execution_authorized"])
        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertFalse(solana["execution_authorized"])

    def test_instant_x1_scan_is_x1_only_bounded_public_service(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        x1 = service_capability(
            manifest,
            chain="x1",
            service="instant_x1_scan",
        )
        solana = service_capability(
            manifest,
            chain="solana",
            service="instant_x1_scan",
        )

        self.assertEqual(x1["state"], "bounded")
        self.assertTrue(x1["callable"])
        self.assertTrue(x1["read_only"])
        self.assertTrue(x1["composition_only"])
        self.assertTrue(x1["public_service_promoted"])
        self.assertTrue(x1["scout_reliance_promoted"])
        self.assertEqual(
            x1["service_contract_version"],
            "instant_x1_scan/v5",
        )
        self.assertIn(
            "current_top_account_concentration_not_promoted_in_v4",
            x1["limitations"],
        )
        self.assertIn("bounded_verified_provider_price_backfill", x1["requirements"])
        self.assertIn("provider_price_backfill_is_price_only", x1["limitations"])
        self.assertIn("provider_archive_completeness_not_verified", x1["limitations"])
        self.assertIn(
            "continuous_coverage_requires_separate_archive_completeness_proof",
            x1["limitations"],
        )
        self.assertFalse(x1["execution_authorized"])

        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertTrue(solana["composition_only"])
        self.assertFalse(solana["public_service_promoted"])
        self.assertFalse(solana["scout_reliance_promoted"])
        self.assertIn(
            "solana_product_expansion_and_release_deferred",
            solana["limitations"],
        )
        self.assertFalse(solana["execution_authorized"])

    def test_x1_asset_lookup_advertises_normalized_identity_contract(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        lookup = service_capability(
            manifest,
            chain="x1",
            service="asset_lookup",
        )

        self.assertEqual(lookup["state"], "supported")
        self.assertTrue(lookup["callable"])
        self.assertEqual(
            lookup["identity_contract_version"],
            "x1_asset_identity/v1",
        )
        self.assertTrue(lookup["exact_mint_normalization"])
        self.assertEqual(lookup["normalized_identity_root"], "mint")
        self.assertTrue(lookup["metaplex_xdex_reconciliation"])
        self.assertIn(
            "same_mint_descriptor_conflicts_return_partial",
            lookup["limitations"],
        )
        self.assertIn(
            "symbol_or_name_never_reconciles_different_mints",
            lookup["limitations"],
        )

    def test_x1_historical_compare_advertises_all_available_boundary(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        history = service_capability(
            manifest,
            chain="x1",
            service="historical_compare",
        )

        self.assertEqual(history["state"], "supported")
        self.assertTrue(history["callable"])
        self.assertIn("verified_current_market_snapshot", history["requirements"])
        self.assertIn(
            "all_available_mode_uses_cmis_stored_verified_observations",
            history["limitations"],
        )
        self.assertIn(
            "verified_provider_price_backfill_may_extend_price_history",
            history["limitations"],
        )
        self.assertIn(
            "verified_provider_backfill_is_price_only",
            history["limitations"],
        )
        self.assertIn(
            "provider_source_independence_not_verified",
            history["limitations"],
        )
        self.assertIn(
            "provider_archive_completeness_not_verified",
            history["limitations"],
        )
        self.assertIn(
            "configured_usd_stable_quote_does_not_prove_historical_one_dollar_peg",
            history["limitations"],
        )
        self.assertIn(
            "all_available_does_not_imply_complete_asset_lifetime",
            history["limitations"],
        )
        self.assertIn(
            "all_available_onchain_coverage_is_mint_address_scope",
            history["limitations"],
        )
        self.assertIn(
            "rpc_visible_mint_history_does_not_imply_asset_wide_activity",
            history["limitations"],
        )
        self.assertIn(
            "rpc_block_boundary_does_not_prove_archive_completeness",
            history["limitations"],
        )
        self.assertIn(
            "pair_mode_requires_compare_asset_and_overlapping_verified_history",
            history["limitations"],
        )


    def test_first_promoted_intelligence_service_is_x1_only_and_narrow(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        x1 = service_capability(
            manifest,
            chain="x1",
            service=CONCENTRATION_INTELLIGENCE_SERVICE,
        )
        solana = service_capability(
            manifest,
            chain="solana",
            service=CONCENTRATION_INTELLIGENCE_SERVICE,
        )

        self.assertEqual(x1["state"], "bounded")
        self.assertTrue(x1["callable"])
        self.assertTrue(x1["read_only"])
        self.assertTrue(x1["public_service_promoted"])
        self.assertTrue(x1["scout_reliance_promoted"])
        self.assertEqual(
            x1["service_contract_version"],
            CONCENTRATION_INTELLIGENCE_CONTRACT_VERSION,
        )
        self.assertEqual(
            x1["accepted_conclusion_types"],
            ["top_account_concentration_change"],
        )
        self.assertIn("cmis_owned_intelligence_evidence_id", x1["requirements"])
        self.assertIn(
            "caller_supplied_intelligence_evidence_not_accepted",
            x1["limitations"],
        )
        self.assertIn(
            "unresolved_receipt_fields_keep_service_partial",
            x1["limitations"],
        )
        self.assertFalse(x1["execution_authorized"])

        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertFalse(solana["public_service_promoted"])
        self.assertFalse(solana["scout_reliance_promoted"])
        self.assertFalse(solana["execution_authorized"])

        foundation = manifest["intelligence_foundation"]
        self.assertFalse(foundation["public_service_promoted"])
        self.assertFalse(foundation["scout_reliance_promoted"])
        for capability in foundation["capabilities"].values():
            self.assertFalse(capability["public_service_promoted"])
            self.assertFalse(capability["scout_reliance_promoted"])

    def test_concentration_warning_intelligence_is_x1_only_pull_only_service(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        x1 = service_capability(
            manifest,
            chain="x1",
            service=CONCENTRATION_WARNING_SERVICE,
        )
        solana = service_capability(
            manifest,
            chain="solana",
            service=CONCENTRATION_WARNING_SERVICE,
        )

        self.assertEqual(x1["state"], "bounded")
        self.assertTrue(x1["callable"])
        self.assertTrue(x1["read_only"])
        self.assertTrue(x1["public_service_promoted"])
        self.assertTrue(x1["scout_reliance_promoted"])
        self.assertEqual(
            x1["service_contract_version"],
            CONCENTRATION_WARNING_CONTRACT_VERSION,
        )
        self.assertEqual(x1["delivery_mode"], "pull_only")
        self.assertFalse(x1["push_delivery_authorized"])
        self.assertIn(
            "exactly_two_cmis_owned_intelligence_evidence_ids",
            x1["requirements"],
        )
        self.assertIn("watch_clear_are_not_risk_severity", x1["limitations"])
        self.assertFalse(x1["execution_authorized"])

        self.assertEqual(solana["state"], "unavailable")
        self.assertFalse(solana["callable"])
        self.assertFalse(solana["public_service_promoted"])
        self.assertFalse(solana["scout_reliance_promoted"])
        self.assertEqual(solana["delivery_mode"], "pull_only")
        self.assertFalse(solana["push_delivery_authorized"])
        self.assertFalse(solana["execution_authorized"])

    def test_x1_gap_decisions_are_machine_readable_and_fail_closed(self):
        capabilities = build_x1_evidence_capability_manifest()["capabilities"]

        self.assertEqual(
            capabilities["holder_wallet_or_beneficial_owner_total"]["state"],
            "unavailable",
        )
        self.assertFalse(
            capabilities["holder_wallet_or_beneficial_owner_total"]
            ["usable_as_verified_fact"]
        )
        self.assertEqual(
            capabilities["token_account_concentration"]["state"],
            "bounded",
        )
        self.assertEqual(
            capabilities["archival_history_completeness"]["state"],
            "unavailable",
        )

        self.assertEqual(
            capabilities["xdex_history_semantics"]["state"],
            "bounded",
        )
        self.assertEqual(
            capabilities["xdex_quote_semantics"]["state"],
            "bounded",
        )

        self.assertEqual(
            capabilities["xdex_history_timestamp_interval"]["state"],
            "verified",
        )
        self.assertTrue(
            capabilities["xdex_history_timestamp_interval"]
            ["usable_as_verified_fact"]
        )
        self.assertEqual(
            capabilities["xdex_history_native_close_price"]["state"],
            "verified",
        )
        self.assertEqual(
            capabilities["xdex_history_native_ohlc"]["state"],
            "bounded",
        )
        self.assertEqual(
            capabilities["xdex_history_volume_semantics"]["state"],
            "unavailable",
        )
        self.assertEqual(
            capabilities["xdex_history_range_completeness"]["state"],
            "unavailable",
        )

        self.assertEqual(
            capabilities["xdex_quote_mint_identity"]["state"],
            "verified",
        )
        self.assertEqual(
            capabilities["xdex_quote_amm_config_identity"]["state"],
            "verified",
        )
        self.assertEqual(
            capabilities["xdex_quote_trade_fee_rate"]["state"],
            "verified",
        )
        self.assertEqual(
            capabilities["xdex_quote_price_impact_semantics"]["state"],
            "verified",
        )
        self.assertTrue(
            capabilities["xdex_quote_price_impact_semantics"]
            ["usable_as_verified_fact"]
        )

        for name in (
            "xdex_quote_slippage_parameter_semantics",
            "xdex_quote_default_slippage",
            "xdex_quote_output_slippage_transform",
            "xdex_quote_effective_curve_deduction",
        ):
            self.assertEqual(capabilities[name]["state"], "verified", name)
            self.assertTrue(capabilities[name]["usable_as_verified_fact"], name)

        self.assertEqual(
            capabilities["xdex_quote_output_amount_decomposition"]["state"],
            "bounded",
        )
        self.assertFalse(
            capabilities["xdex_quote_output_amount_decomposition"]
            ["usable_as_verified_fact"]
        )
        self.assertEqual(
            capabilities["xdex_quote_slippage_minimum_received"]["state"],
            "bounded",
        )
        self.assertFalse(
            capabilities["xdex_quote_slippage_minimum_received"]
            ["usable_as_verified_fact"]
        )

        for name in (
            "xdex_quote_total_fee_decomposition",
            "xdex_quote_route_quality",
            "xdex_quote_fill_quality",
        ):
            self.assertEqual(capabilities[name]["state"], "unavailable", name)
            self.assertFalse(capabilities[name]["usable_as_verified_fact"], name)

        self.assertEqual(
            capabilities["native_xnt_canonical_translation"]["state"],
            "verified",
        )
        self.assertTrue(
            capabilities["native_xnt_canonical_translation"]
            ["usable_as_verified_fact"]
        )
        self.assertEqual(
            capabilities["native_xnt_xdex_quote_translation"]["state"],
            "verified",
        )
        self.assertEqual(
            capabilities["x1_ninja_sse_live_event_evidence"]["state"],
            "unavailable",
        )
        self.assertEqual(
            capabilities["warp_bridge_operational_state"]["state"],
            "unavailable",
        )
        self.assertEqual(
            capabilities["warp_bridge_guardian_state"]["state"],
            "unavailable",
        )

    def test_route_specific_xdex_proof_does_not_leak_into_generic_pretrade(self):
        report = build_execution_capability_report()
        capabilities = report["evidence"]["capabilities"]

        self.assertEqual(capabilities["price_impact"]["status"], "unavailable")
        self.assertIsNone(capabilities["price_impact"]["value"])
        self.assertEqual(capabilities["fees"]["status"], "unavailable")
        self.assertIsNone(capabilities["fees"]["value"])
        self.assertEqual(capabilities["slippage"]["status"], "unavailable")
        self.assertIsNone(capabilities["slippage"]["value"])

    def test_new_runtime_service_without_manifest_classification_fails_loudly(self):
        with self.assertRaisesRegex(RuntimeError, "service drift"):
            validate_capability_contract(
                runtime_services=(*SUPPORTED_SERVICES, "future_service"),
                known_chains=KNOWN_CHAINS,
            )

    def test_new_known_chain_without_manifest_classification_fails_loudly(self):
        with self.assertRaisesRegex(RuntimeError, "chain drift"):
            validate_capability_contract(
                runtime_services=SUPPORTED_SERVICES,
                known_chains=(*KNOWN_CHAINS, "ethereum"),
            )

    def test_chain_service_lookup_never_guesses_unknown_capability(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )

        x1_pretrade = service_capability(
            manifest,
            chain="x1",
            service="pre_trade_check",
        )
        solana_pretrade = service_capability(
            manifest,
            chain="solana",
            service="pre_trade_check",
        )
        unknown = service_capability(
            manifest,
            chain="ethereum",
            service="market_report",
        )

        self.assertEqual(x1_pretrade["state"], "bounded")
        self.assertTrue(x1_pretrade["callable"])
        self.assertEqual(solana_pretrade["state"], "unavailable")
        self.assertFalse(solana_pretrade["callable"])
        self.assertIsNone(unknown)

    def test_manifest_build_returns_fresh_nested_data(self):
        first = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        first["chains"]["x1"]["services"]["risk_check"]["state"] = "unavailable"
        first["chains"]["x1"]["evidence_capabilities"][
            "native_xnt_canonical_translation"
        ]["state"] = "unavailable"
        first["chains"]["x1"]["services"][CONCENTRATION_INTELLIGENCE_SERVICE][
            "public_service_promoted"
        ] = False

        second = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        self.assertEqual(
            second["chains"]["x1"]["services"]["risk_check"]["state"],
            "supported",
        )
        self.assertEqual(
            second["chains"]["x1"]["evidence_capabilities"][
                "native_xnt_canonical_translation"
            ]["state"],
            "verified",
        )
        self.assertTrue(
            second["chains"]["x1"]["services"][CONCENTRATION_INTELLIGENCE_SERVICE][
                "public_service_promoted"
            ]
        )


if __name__ == "__main__":
    unittest.main()


def test_bridge_to_xdex_promotion_is_bounded_to_x1_program_family():
    manifest = build_capability_manifest(
        runtime_services=SUPPORTED_SERVICES,
        legacy_supported_chains=SUPPORTED_CHAINS,
        known_chains=KNOWN_CHAINS,
    )
    x1 = manifest["chains"]["x1"]["services"][BRIDGE_TO_XDEX_SERVICE]
    assert x1["state"] == "bounded"
    assert x1["callable"] is True
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["service_contract_version"] == BRIDGE_TO_XDEX_CONTRACT_VERSION
    assert "verified_xdex_program_family_is_not_every_x1_dex" in x1["limitations"]
    assert "bridge_activity_is_not_adoption" in x1["limitations"]
    assert "liquidity_is_not_volume" in x1["limitations"]
    assert "no_causal_inference" in x1["limitations"]
    assert "no_automatic_risk_conclusion" in x1["limitations"]
    assert x1["execution_authorized"] is False

    solana = manifest["chains"]["solana"]["services"][BRIDGE_TO_XDEX_SERVICE]
    assert solana["state"] == "unavailable"
    assert solana["callable"] is False
    assert solana["public_service_promoted"] is False
    assert solana["scout_reliance_promoted"] is False


def test_cross_chain_provenance_promotion_is_x1_only_and_structural():
    manifest = build_capability_manifest(
        runtime_services=SUPPORTED_SERVICES,
        legacy_supported_chains=SUPPORTED_CHAINS,
        known_chains=KNOWN_CHAINS,
    )
    x1 = manifest["chains"]["x1"]["services"][CROSS_CHAIN_PROVENANCE_SERVICE]
    assert x1["state"] == "bounded"
    assert x1["callable"] is True
    assert x1["read_only"] is True
    assert x1["public_service_promoted"] is True
    assert x1["scout_reliance_promoted"] is True
    assert x1["service_contract_version"] == CROSS_CHAIN_PROVENANCE_CONTRACT_VERSION
    assert "ordered_provenance_hop_continuity" in x1["requirements"]
    assert "symbol_or_name_equality_is_not_identity_proof" in x1["limitations"]
    assert "bridge_dependency_is_not_risk" in x1["limitations"]
    assert "provenance_does_not_verify_backing" in x1["limitations"]
    assert "provenance_does_not_establish_adoption_or_causality" in x1["limitations"]
    assert x1["execution_authorized"] is False

    solana = manifest["chains"]["solana"]["services"][CROSS_CHAIN_PROVENANCE_SERVICE]
    assert solana["state"] == "unavailable"
    assert solana["callable"] is False
    assert solana["public_service_promoted"] is False
    assert solana["scout_reliance_promoted"] is False
    assert solana["execution_authorized"] is False
