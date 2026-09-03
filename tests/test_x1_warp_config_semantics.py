import copy
import json
import pathlib
import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    ACCEPTED_FIXTURE_CANONICAL_SHA256,
    WARP_CONFIG_SEMANTICS_CONTRACT,
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
    WARP_CONFIG_SOURCE_URL,
    build_warp_config_route_observation,
    canonical_sha256,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    ACCEPTED_ROUTE_SEMANTIC_CONTRACTS,
    qualify_warp_bridge_route,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)


WSOL = "So11111111111111111111111111111111111111112"
WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
ROUTE_ID = "warp-solana-x1-wsol"
FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "warp_bridge_config_20260903.json"


def endpoint(chain, mint):
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def provenance():
    return build_cross_chain_asset_provenance(
        canonical_asset_id="sol",
        origin=endpoint("solana", WSOL),
        current=endpoint("x1", WSOL_X),
        hops=[
            {
                "source": endpoint("solana", WSOL),
                "destination": endpoint("x1", WSOL_X),
                "bridge": "Warp Bridge",
                "representation_type": "bridge_representation",
                "custody_model": "unknown",
                "bridge_route_id": ROUTE_ID,
            }
        ],
    )


def source_provenance():
    return evaluate_bridge_source_provenance(
        url=WARP_CONFIG_SOURCE_URL,
        proofs=[
            BridgeSourceProof(
                proof_type="official_app_network_observation",
                reference=(
                    "2026-09-03 clean Chrome HAR from "
                    "https://app.bridge.x1.xyz/info"
                ),
                exact_url=WARP_CONFIG_SOURCE_URL,
            )
        ],
    )


class WarpConfigSemanticsTests(unittest.TestCase):
    def test_fixture_canonical_hash_is_pinned(self):
        fixture = load_fixture()
        self.assertEqual(
            canonical_sha256(fixture),
            ACCEPTED_FIXTURE_CANONICAL_SHA256,
        )

    def test_wsol_route_semantics_are_exact_and_bounded(self):
        result = build_warp_config_route_observation(
            config_response=load_fixture(),
            route_id=ROUTE_ID,
            source=endpoint("solana", WSOL),
            destination=endpoint("x1", WSOL_X),
        )

        self.assertEqual(result["contract"], WARP_CONFIG_SEMANTICS_CONTRACT)
        self.assertEqual(
            result["semantic_contract_id"],
            WARP_CONFIG_SEMANTIC_CONTRACT_ID,
        )
        self.assertEqual(result["source_url"], WARP_CONFIG_SOURCE_URL)
        self.assertEqual(result["route_status"], "active")
        self.assertEqual(
            result["backing_model"],
            "provider_config_native_source_to_non_native_destination",
        )
        self.assertEqual(
            result["custody_dependency"],
            "guardian_quorum:solana=5/7;x1=5/7",
        )
        self.assertEqual(result["source_observed_at"], 1788436231.329)
        self.assertEqual(result["source_timestamp_unit"], "milliseconds")
        self.assertEqual(result["source_symbol"], "wSOL")
        self.assertEqual(result["destination_symbol"], "wSOL.X")
        self.assertTrue(result["source_is_native"])
        self.assertFalse(result["destination_is_native"])
        self.assertFalse(result["backing_reserve_sufficiency_verified"])
        self.assertFalse(result["legal_custodian_identity_verified"])
        self.assertFalse(result["guardian_honesty_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_accepted_config_observation_qualifies_exact_wsol_route(self):
        observation = build_warp_config_route_observation(
            config_response=load_fixture(),
            route_id=ROUTE_ID,
            source=endpoint("solana", WSOL),
            destination=endpoint("x1", WSOL_X),
        )
        result = qualify_warp_bridge_route(
            provenance=provenance(),
            hop_index=0,
            source_provenance=source_provenance(),
            observation=observation,
            evaluated_at=1788436232.329,
        )

        self.assertTrue(result["warp_qualified"])
        self.assertEqual(result["qualification_state"], "qualified")
        self.assertIn(
            WARP_CONFIG_SEMANTIC_CONTRACT_ID,
            result["accepted_warp_semantic_contracts"],
        )
        checks = result["route_evidence"]["qualification_checks"]
        self.assertTrue(all(checks.values()))
        self.assertTrue(
            result["route_evidence"]["facts"]["route_status"]["verified"]
        )
        self.assertTrue(
            result["route_evidence"]["facts"]["backing_model"]["verified"]
        )
        self.assertTrue(
            result["route_evidence"]["facts"]["custody_dependency"]["verified"]
        )
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_exact_mint_identity_is_required_not_symbol_pairing(self):
        with self.assertRaisesRegex(ValueError, "exactly one entry"):
            build_warp_config_route_observation(
                config_response=load_fixture(),
                route_id=ROUTE_ID,
                source=endpoint("solana", "WrongMint111111111111111111111111111111"),
                destination=endpoint("x1", WSOL_X),
            )

    def test_any_chain_or_token_pause_makes_route_paused(self):
        fixture = copy.deepcopy(load_fixture())
        for case in ("source_chain", "destination_chain", "source_token", "destination_token"):
            candidate = copy.deepcopy(fixture)
            if case == "source_chain":
                candidate["solana"]["config"]["paused"] = True
            elif case == "destination_chain":
                candidate["x1"]["config"]["paused"] = True
            elif case == "source_token":
                next(
                    token
                    for token in candidate["solana"]["tokens"]
                    if token["mint"] == WSOL
                )["paused"] = True
            else:
                next(
                    token
                    for token in candidate["x1"]["tokens"]
                    if token["mint"] == WSOL_X
                )["paused"] = True

            result = build_warp_config_route_observation(
                config_response=candidate,
                route_id=ROUTE_ID,
                source=endpoint("solana", WSOL),
                destination=endpoint("x1", WSOL_X),
            )
            self.assertEqual(result["route_status"], "paused", case)

    def test_guardian_threshold_must_be_valid(self):
        fixture = copy.deepcopy(load_fixture())
        fixture["solana"]["config"]["threshold"] = 8
        with self.assertRaisesRegex(ValueError, "cannot exceed guardian count"):
            build_warp_config_route_observation(
                config_response=fixture,
                route_id=ROUTE_ID,
                source=endpoint("solana", WSOL),
                destination=endpoint("x1", WSOL_X),
            )

    def test_decimals_mismatch_fails_closed(self):
        fixture = copy.deepcopy(load_fixture())
        next(
            token
            for token in fixture["x1"]["tokens"]
            if token["mint"] == WSOL_X
        )["decimals"] = 8
        with self.assertRaisesRegex(ValueError, "decimals must match"):
            build_warp_config_route_observation(
                config_response=fixture,
                route_id=ROUTE_ID,
                source=endpoint("solana", WSOL),
                destination=endpoint("x1", WSOL_X),
            )

    def test_registry_accepts_only_the_exact_config_url(self):
        spec = ACCEPTED_ROUTE_SEMANTIC_CONTRACTS[
            WARP_CONFIG_SEMANTIC_CONTRACT_ID
        ]
        self.assertEqual(spec["provider"], "warp_bridge")
        self.assertEqual(spec["source_url"], WARP_CONFIG_SOURCE_URL)


if __name__ == "__main__":
    unittest.main()
