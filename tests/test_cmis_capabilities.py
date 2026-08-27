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
        self.assertEqual(CMIS_CONTRACT_VERSION, "1.10.0")
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
        self.assertIn("evidence_capabilities", manifest["chains"]["x1"])
        self.assertNotIn("evidence_capabilities", manifest["chains"]["solana"])

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
            "all_available_mode_uses_cmis_stored_verified_observations_only",
            history["limitations"],
        )
        self.assertIn(
            "all_available_does_not_imply_complete_asset_lifetime",
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
