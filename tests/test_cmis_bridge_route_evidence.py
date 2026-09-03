import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    ACCEPTED_ROUTE_SEMANTIC_CONTRACTS,
    ROUTE_EVIDENCE_CONTRACT,
    WARP_QUALIFICATION_CONTRACT,
    evaluate_route_freshness,
    qualify_warp_bridge_route,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)


WSOL = "So11111111111111111111111111111111111111112"
WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
INFO_URL = "https://app.bridge.x1.xyz/info"


def endpoint(chain, asset_id, asset_id_kind="mint"):
    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


def provenance(route_id="warp-solana-x1-wsol"):
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
                "bridge_route_id": route_id,
            }
        ],
    )


def source_provenance(url=INFO_URL):
    return evaluate_bridge_source_provenance(
        url=url,
        proofs=[
            BridgeSourceProof(
                proof_type="x1_owned_application_artifact",
                reference="official X1 bridge application page",
                exact_url=url,
            )
        ],
    )


def observation(**overrides):
    value = {
        "provider": "warp_bridge",
        "bridge": "Warp Bridge",
        "route_id": "warp-solana-x1-wsol",
        "source": endpoint("solana", WSOL),
        "destination": endpoint("x1", WSOL_X),
        "source_url": INFO_URL,
        "semantic_contract_id": "warp_bridge/info/v1",
        "route_status": "Offline-Checking...",
        "backing_model": "candidate-lock-mint",
        "custody_dependency": "candidate-guardian-set",
        "source_observed_at": 1000.0,
        "collected_at": 1001.0,
    }
    value.update(overrides)
    return value


class CMISBridgeRouteEvidenceTests(unittest.TestCase):
    def test_warp_registry_starts_with_no_accepted_semantic_contract(self):
        self.assertEqual(ACCEPTED_ROUTE_SEMANTIC_CONTRACTS, {})

    def test_official_ui_candidate_remains_blocked_without_machine_semantics(self):
        result = qualify_warp_bridge_route(
            provenance=provenance(),
            hop_index=0,
            source_provenance=source_provenance(),
            observation=observation(),
            evaluated_at=1010.0,
        )

        self.assertEqual(result["contract"], WARP_QUALIFICATION_CONTRACT)
        self.assertFalse(result["warp_qualified"])
        self.assertEqual(
            result["qualification_state"],
            "blocked_endpoint_semantics",
        )
        evidence = result["route_evidence"]
        self.assertEqual(evidence["contract"], ROUTE_EVIDENCE_CONTRACT)
        self.assertTrue(
            evidence["qualification_checks"]["source_provenance_verified"]
        )
        self.assertTrue(
            evidence["qualification_checks"]["exact_route_identity_verified"]
        )
        self.assertFalse(
            evidence["qualification_checks"]["endpoint_semantics_verified"]
        )
        self.assertFalse(evidence["facts"]["route_status"]["verified"])
        self.assertFalse(evidence["facts"]["backing_model"]["verified"])
        self.assertFalse(evidence["facts"]["custody_dependency"]["verified"])
        self.assertFalse(evidence["public_service_promoted"])
        self.assertFalse(evidence["scout_reliance_promoted"])
        self.assertFalse(evidence["execution_authorized"])

    def test_generic_http_or_json_claim_cannot_self_accept_semantic_contract(self):
        result = qualify_warp_bridge_route(
            provenance=provenance(),
            hop_index=0,
            source_provenance=source_provenance(),
            observation=observation(
                semantic_contract_id="warp_bridge/guessed-json-200/v99",
                route_status="online",
            ),
            evaluated_at=1010.0,
        )
        self.assertFalse(result["warp_qualified"])
        self.assertEqual(
            result["qualification_state"],
            "blocked_endpoint_semantics",
        )

    def test_source_mint_mismatch_fails_closed(self):
        bad = observation(source=endpoint("solana", "DifferentMint111"))
        with self.assertRaisesRegex(ValueError, "source must equal"):
            qualify_warp_bridge_route(
                provenance=provenance(),
                hop_index=0,
                source_provenance=source_provenance(),
                observation=bad,
                evaluated_at=1010.0,
            )

    def test_destination_mint_mismatch_fails_closed(self):
        bad = observation(destination=endpoint("x1", "DifferentMint111"))
        with self.assertRaisesRegex(ValueError, "destination must equal"):
            qualify_warp_bridge_route(
                provenance=provenance(),
                hop_index=0,
                source_provenance=source_provenance(),
                observation=bad,
                evaluated_at=1010.0,
            )

    def test_route_id_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "route_id must equal"):
            qualify_warp_bridge_route(
                provenance=provenance(),
                hop_index=0,
                source_provenance=source_provenance(),
                observation=observation(route_id="guessed-other-route"),
                evaluated_at=1010.0,
            )

    def test_source_url_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "source_url must equal"):
            qualify_warp_bridge_route(
                provenance=provenance(),
                hop_index=0,
                source_provenance=source_provenance(),
                observation=observation(
                    source_url="https://bridge-api.x1.xyz/guessed"
                ),
                evaluated_at=1010.0,
            )

    def test_freshness_distinguishes_collection_and_source_age(self):
        result = evaluate_route_freshness(
            collected_at=1000.0,
            source_observed_at=900.0,
            evaluated_at=1010.0,
            max_age_seconds=60.0,
        )
        self.assertTrue(result["collection_fresh"])
        self.assertFalse(result["source_fresh"])
        self.assertEqual(result["collection_age_seconds"], 10.0)
        self.assertEqual(result["source_age_seconds"], 110.0)

    def test_future_timestamps_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "future"):
            evaluate_route_freshness(
                collected_at=1020.0,
                evaluated_at=1010.0,
            )
        with self.assertRaisesRegex(ValueError, "future"):
            evaluate_route_freshness(
                collected_at=1000.0,
                source_observed_at=1020.0,
                evaluated_at=1010.0,
            )

    def test_evidence_identity_is_deterministic(self):
        kwargs = dict(
            provenance=provenance(),
            hop_index=0,
            source_provenance=source_provenance(),
            observation=observation(),
            evaluated_at=1010.0,
        )
        first = qualify_warp_bridge_route(**kwargs)
        second = qualify_warp_bridge_route(**kwargs)
        self.assertEqual(
            first["route_evidence"]["evidence_id"],
            second["route_evidence"]["evidence_id"],
        )


if __name__ == "__main__":
    unittest.main()
