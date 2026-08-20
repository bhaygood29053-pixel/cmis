import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)


class X1BridgeSourceProvenanceTests(unittest.TestCase):
    def test_official_network_observation_makes_exact_url_probe_eligible(self):
        candidate = "https://bridge-api.x1.xyz/v1/example"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    proof_type="official_app_network_observation",
                    reference="sanitized capture: app.bridge.x1.xyz requested exact URL",
                    exact_url=candidate,
                    source_url="https://app.bridge.x1.xyz/info",
                )
            ],
        )
        self.assertTrue(result.source_provenance_verified)
        self.assertTrue(result.read_probe_eligible)
        self.assertFalse(result.endpoint_semantics_verified)
        self.assertFalse(result.cmis_promotable)
        self.assertEqual(result.host, "bridge-api.x1.xyz")

    def test_allowed_proof_type_for_different_url_does_not_verify_candidate(self):
        result = evaluate_bridge_source_provenance(
            url="https://bridge-api.x1.xyz/v1/status",
            proofs=[
                BridgeSourceProof(
                    proof_type="x1_owned_documentation",
                    reference="official documentation for a different endpoint",
                    exact_url="https://bridge-api.x1.xyz/v1/config",
                    source_url="https://docs.x1.xyz/",
                )
            ],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertTrue(any("exact candidate URL" in warning for warning in result.warnings))

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
        candidate = "https://bridge-api.x1.xyz/"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    proof_type="third_party_extension_metadata",
                    reference="historical extension host permission",
                    exact_url=candidate,
                    source_url="https://example.invalid/extension-metadata",
                )
            ],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertTrue(any("unsupported provenance" in warning for warning in result.warnings))

    def test_generic_warp_bridge_docs_cannot_masquerade_as_x1_owned_documentation(self):
        candidate = "https://bridge-api.x1.xyz/v1/status"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    proof_type="x1_owned_documentation",
                    reference="unrelated documentation using the Warp Bridge name",
                    exact_url=candidate,
                    source_url="https://warp-example.mintlify.app/api-reference/status",
                )
            ],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertFalse(result.cmis_promotable)
        self.assertTrue(
            any("not structurally X1-owned" in warning for warning in result.warnings)
        )

    def test_web_backed_proof_requires_explicit_source_url(self):
        candidate = "https://bridge-api.x1.xyz/status"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    proof_type="x1_owned_documentation",
                    reference="claimed official documentation",
                    exact_url=candidate,
                )
            ],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertTrue(
            any("requires an explicit proof source URL" in warning for warning in result.warnings)
        )

    def test_official_app_network_observation_requires_official_app_origin(self):
        candidate = "https://bridge-api.x1.xyz/status"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    proof_type="official_app_network_observation",
                    reference="capture attributed to the wrong application origin",
                    exact_url=candidate,
                    source_url="https://example.invalid/bridge",
                )
            ],
        )
        self.assertFalse(result.source_provenance_verified)
        self.assertFalse(result.read_probe_eligible)
        self.assertTrue(
            any("must originate from app.bridge.x1.xyz" in warning for warning in result.warnings)
        )

    def test_x1_owned_github_artifact_origin_is_accepted_structurally(self):
        candidate = "https://bridge-api.x1.xyz/status"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    proof_type="x1_owned_application_artifact",
                    reference="captured fixture representing an X1-owned repository artifact",
                    exact_url=candidate,
                    source_url="https://github.com/x1-labs/example-artifact",
                )
            ],
        )
        self.assertTrue(result.source_provenance_verified)
        self.assertTrue(result.read_probe_eligible)
        self.assertFalse(result.endpoint_semantics_verified)
        self.assertFalse(result.cmis_promotable)

    def test_multiple_accepted_proofs_are_deduplicated_and_sorted(self):
        candidate = "https://bridge-api.x1.xyz/status?network=x1"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    "x1_owned_application_artifact",
                    "bundle reference",
                    candidate,
                    "https://app.bridge.x1.xyz/",
                ),
                BridgeSourceProof(
                    "official_app_network_observation",
                    "network capture",
                    candidate,
                    "https://app.bridge.x1.xyz/info",
                ),
                BridgeSourceProof(
                    "official_app_network_observation",
                    "second capture",
                    candidate,
                    "https://app.bridge.x1.xyz/history",
                ),
            ],
        )
        self.assertEqual(
            result.proof_types,
            ("official_app_network_observation", "x1_owned_application_artifact"),
        )
        self.assertTrue(result.read_probe_eligible)

    def test_onchain_configuration_does_not_require_a_web_origin(self):
        candidate = "https://bridge-api.x1.xyz/status"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    "onchain_configuration",
                    "verified on-chain configuration fixture binds exact URL",
                    candidate,
                )
            ],
        )
        self.assertTrue(result.source_provenance_verified)
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
        keys = (
            "api_key",
            "api-key",
            "x-api-key",
            "apikey",
            "auth",
            "authorization",
            "key",
            "secret",
            "client_secret",
            "sig",
            "signature",
            "token",
            "access_token",
            "refresh_token",
            "password",
            "session_id",
            "jwt",
        )
        for key in keys:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "credential-like"):
                evaluate_bridge_source_provenance(
                    url=f"https://bridge-api.x1.xyz/status?network=x1&{key}=do-not-store",
                    proofs=[],
                )

    def test_public_query_parameters_remain_allowed(self):
        candidate = "https://bridge-api.x1.xyz/status?network=x1&direction=solana"
        result = evaluate_bridge_source_provenance(
            url=candidate,
            proofs=[
                BridgeSourceProof(
                    "x1_owned_documentation",
                    "official exact URL reference fixture",
                    candidate,
                    "https://docs.x1.xyz/",
                )
            ],
        )
        self.assertTrue(result.read_probe_eligible)
        self.assertIn("network=x1", result.url)

    def test_rejects_empty_proof_reference(self):
        candidate = "https://bridge-api.x1.xyz/status"
        with self.assertRaises(ValueError):
            evaluate_bridge_source_provenance(
                url=candidate,
                proofs=[
                    BridgeSourceProof(
                        "official_app_network_observation",
                        "",
                        candidate,
                        "https://app.bridge.x1.xyz/",
                    )
                ],
            )

    def test_rejects_invalid_proof_url(self):
        candidate = "https://bridge-api.x1.xyz/status"
        with self.assertRaises(ValueError):
            evaluate_bridge_source_provenance(
                url=candidate,
                proofs=[
                    BridgeSourceProof(
                        "official_app_network_observation",
                        "capture",
                        "http://bridge-api.x1.xyz/status",
                        "https://app.bridge.x1.xyz/",
                    )
                ],
            )

    def test_rejects_credential_like_proof_source_url(self):
        candidate = "https://bridge-api.x1.xyz/status"
        with self.assertRaisesRegex(ValueError, "credential-like"):
            evaluate_bridge_source_provenance(
                url=candidate,
                proofs=[
                    BridgeSourceProof(
                        "x1_owned_documentation",
                        "fixture",
                        candidate,
                        "https://docs.x1.xyz/?token=do-not-store",
                    )
                ],
            )

    def test_rejects_non_proof_values(self):
        with self.assertRaises(TypeError):
            evaluate_bridge_source_provenance(
                url="https://bridge-api.x1.xyz/status",
                proofs=[{"proof_type": "official_app_network_observation"}],
            )


if __name__ == "__main__":
    unittest.main()
