import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)


class X1BridgeSourceProvenanceTests(unittest.TestCase):
    def test_official_network_observation_makes_exact_url_probe_eligible(self):
        result = evaluate_bridge_source_provenance(
            url="https://bridge-api.x1.xyz/v1/example",
            proofs=[
                BridgeSourceProof(
                    proof_type="official_app_network_observation",
                    reference="sanitized capture: app.bridge.x1.xyz requested exact URL",
                )
            ],
        )
        self.assertTrue(result.source_provenance_verified)
        self.assertTrue(result.read_probe_eligible)
        self.assertFalse(result.endpoint_semantics_verified)
        self.assertFalse(result.cmis_promotable)
        self.assertEqual(result.host, "bridge-api.x1.xyz")

    def test_unverified_candidate_host_is_not_enough(self):
        result = evaluate_bridge_source_provenance(
            url="https://bridge-api.x1.xyz/",
            proofs=[],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertFalse(result.cmis_promotable)
        self.assertIn("no accepted provenance proof", result.warnings[0])

    def test_third_party_permission_metadata_does_not_verify_source(self):
        result = evaluate_bridge_source_provenance(
            url="https://bridge-api.x1.xyz/",
            proofs=[
                BridgeSourceProof(
                    proof_type="third_party_extension_metadata",
                    reference="historical extension host permission",
                )
            ],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertTrue(any("unsupported provenance" in warning for warning in result.warnings))

    def test_multiple_accepted_proofs_are_deduplicated_and_sorted(self):
        result = evaluate_bridge_source_provenance(
            url="https://bridge-api.x1.xyz/status?network=x1",
            proofs=[
                BridgeSourceProof("x1_owned_application_artifact", "bundle reference"),
                BridgeSourceProof("official_app_network_observation", "network capture"),
                BridgeSourceProof("official_app_network_observation", "second capture"),
            ],
        )
        self.assertEqual(
            result.proof_types,
            ("official_app_network_observation", "x1_owned_application_artifact"),
        )
        self.assertTrue(result.read_probe_eligible)

    def test_rejects_non_https_credential_and_fragment_urls(self):
        invalid_urls = (
            "http://bridge-api.x1.xyz/status",
            "https://user:pass@bridge-api.x1.xyz/status",
            "https://bridge-api.x1.xyz/status#secret",
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                evaluate_bridge_source_provenance(url=url, proofs=[])

    def test_rejects_credential_like_query_parameters(self):
        for key in ("api_key", "apikey", "auth", "authorization", "key", "secret", "sig", "signature", "token"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "credential-like"):
                evaluate_bridge_source_provenance(
                    url=f"https://bridge-api.x1.xyz/status?network=x1&{key}=do-not-store",
                    proofs=[],
                )

    def test_public_query_parameters_remain_allowed(self):
        result = evaluate_bridge_source_provenance(
            url="https://bridge-api.x1.xyz/status?network=x1&direction=solana",
            proofs=[BridgeSourceProof("x1_owned_documentation", "official exact URL reference")],
        )
        self.assertTrue(result.read_probe_eligible)
        self.assertIn("network=x1", result.url)

    def test_rejects_empty_proof_reference(self):
        with self.assertRaises(ValueError):
            evaluate_bridge_source_provenance(
                url="https://bridge-api.x1.xyz/status",
                proofs=[BridgeSourceProof("official_app_network_observation", "")],
            )

    def test_rejects_non_proof_values(self):
        with self.assertRaises(TypeError):
            evaluate_bridge_source_provenance(
                url="https://bridge-api.x1.xyz/status",
                proofs=[{"proof_type": "official_app_network_observation"}],
            )


if __name__ == "__main__":
    unittest.main()
