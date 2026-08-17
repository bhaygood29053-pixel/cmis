import copy
import unittest

from liquidity_scout.cmis.evidence import build_evidence_observation
from liquidity_scout.providers.x1.reserve_verification import verify_x1_pool_reserve
from liquidity_scout.services.cmis_verification_evidence import (
    build_verification_evidence_response,
)


SUBJECT = "x1:pool111:mint111:vault111"
ASSET = {"symbol": "REF", "mint": "mint111"}


def observation(
    source,
    value="42",
    *,
    freshness=True,
    semantics=True,
    identity=True,
    slot=100,
):
    return build_evidence_observation(
        chain="x1",
        fact_type="pool_reserve",
        subject_id=SUBJECT,
        source=source,
        source_role="market_provider" if source == "X1.Ninja" else "onchain_verifier",
        observed_at=1000.0,
        block_slot=slot,
        raw_identifier="pool.pooledBase" if source == "X1.Ninja" else "vault111",
        raw_value=value,
        normalized_value=value,
        unit="TOKEN_UNITS",
        calculation_version="test-1",
        identity_verified=identity,
        semantics_verified=semantics,
        freshness_verified=freshness,
        warnings=[],
    )


def verified_result(primary=None, verifier=None):
    return verify_x1_pool_reserve(
        primary or observation("X1.Ninja"),
        verifier or observation("X1 RPC", slot=101),
    )


class CMISVerificationEvidenceTests(unittest.TestCase):
    def test_promotable_agreement_uses_standard_envelope_and_preserves_provenance(self):
        response = build_verification_evidence_response(
            verified_result(),
            chain="x1",
            asset=ASSET,
            observed_at=1001.0,
        )

        self.assertEqual(
            list(response),
            [
                "service",
                "chain",
                "status",
                "asset",
                "data",
                "risk",
                "confidence",
                "sources",
                "observed_at",
                "warnings",
                "errors",
            ],
        )
        self.assertEqual(response["service"], "verification_evidence")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["asset"], ASSET)
        self.assertEqual(response["data"]["fact"]["fact_type"], "pool_reserve")
        self.assertEqual(response["data"]["fact"]["subject_id"], SUBJECT)
        self.assertEqual(response["data"]["fact"]["normalized_value"], "42")
        self.assertEqual(response["data"]["fact"]["unit"], "TOKEN_UNITS")
        self.assertEqual(response["data"]["verification"]["status"], "AGREEMENT")
        self.assertTrue(response["data"]["cmis_promotable"])
        self.assertEqual(response["confidence"]["quality"], "HIGH")
        self.assertTrue(response["confidence"]["cmis_promotable"])
        self.assertEqual(
            response["sources"],
            [
                {
                    "source": "X1.Ninja",
                    "role": "market_provider",
                    "observed_at": 1000.0,
                    "block_slot": 100,
                    "calculation_version": "test-1",
                },
                {
                    "source": "X1 RPC",
                    "role": "onchain_verifier",
                    "observed_at": 1000.0,
                    "block_slot": 101,
                    "calculation_version": "test-1",
                },
            ],
        )
        self.assertEqual(response["warnings"], [])
        self.assertEqual(response["errors"], [])

    def test_agreement_without_freshness_is_partial_but_not_a_promoted_fact(self):
        result = verified_result(
            observation("X1.Ninja", freshness=False),
            observation("X1 RPC", freshness=False, slot=101),
        )
        self.assertFalse(result["cmis_promotable"])

        response = build_verification_evidence_response(result)

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["verification"]["status"], "AGREEMENT")
        self.assertFalse(response["data"]["cmis_promotable"])
        self.assertIsNone(response["data"]["fact"]["normalized_value"])
        self.assertIsNone(response["data"]["fact"]["unit"])
        self.assertEqual(
            response["data"]["observations"]["primary"]["normalized_value"],
            "42",
        )
        self.assertEqual(
            response["data"]["observations"]["verifier"]["normalized_value"],
            "42",
        )
        self.assertEqual(response["confidence"]["quality"], "LOW")
        self.assertIn("FRESHNESS_UNVERIFIED", response["confidence"]["reasons"])
        self.assertEqual(response["warnings"][0]["code"], "agreement_not_promotable")

    def test_conflict_is_partial_and_never_exposes_one_value_as_verified_fact(self):
        result = verified_result(
            observation("X1.Ninja", "42"),
            observation("X1 RPC", "43", slot=101),
        )

        response = build_verification_evidence_response(result)

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["verification"]["status"], "CONFLICT")
        self.assertIsNone(response["data"]["fact"]["normalized_value"])
        self.assertIsNone(response["data"]["fact"]["unit"])
        self.assertFalse(response["data"]["cmis_promotable"])
        self.assertEqual(response["warnings"][0]["code"], "independent_source_conflict")

    def test_insufficient_evidence_is_partial_and_preserves_verifier_reason(self):
        result = verified_result(
            observation("X1.Ninja", semantics=False),
            observation("X1 RPC", semantics=False, slot=101),
        )

        response = build_verification_evidence_response(result)

        self.assertEqual(response["status"], "partial")
        self.assertEqual(
            response["data"]["verification"]["status"],
            "INSUFFICIENT_EVIDENCE",
        )
        self.assertEqual(
            response["data"]["verification"]["code"],
            "SEMANTICS_UNVERIFIED",
        )
        self.assertIsNone(response["data"]["fact"]["normalized_value"])
        self.assertEqual(
            response["warnings"][0]["code"],
            "insufficient_verification_evidence",
        )

    def test_wrapper_drops_unapproved_nested_payloads_and_secret_shaped_extras(self):
        result = copy.deepcopy(verified_result())
        primary = result["verification"]["primary"]
        primary["api_key"] = "secret"
        primary["raw_response"] = {"authorization": "Bearer secret"}
        primary["raw_value"] = {"nested": "transport-payload"}
        primary["warnings"] = ["safe-warning", {"secret": "bad"}]
        result["data_quality"]["extra_payload"] = {"secret": True}

        response = build_verification_evidence_response(result)
        exposed = response["data"]["observations"]["primary"]

        self.assertNotIn("api_key", exposed)
        self.assertNotIn("raw_response", exposed)
        self.assertIsNone(exposed["raw_value"])
        self.assertEqual(exposed["warnings"], ["safe-warning"])
        self.assertNotIn("extra_payload", response["data"]["data_quality"])
        self.assertNotIn("secret", str(response))

    def test_wrapper_rejects_chain_or_fact_identity_mismatch(self):
        result = copy.deepcopy(verified_result())
        result["verification"]["verifier"]["chain"] = "solana"

        response = build_verification_evidence_response(result, chain="x1")
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "verification_chain_mismatch")

        result = copy.deepcopy(verified_result())
        result["verification"]["verifier"]["subject_id"] = "other-subject"
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "verification_fact_identity_mismatch",
        )

    def test_wrapper_rejects_inconsistent_status_and_promotion_claims(self):
        result = copy.deepcopy(verified_result())
        result["verification"]["status"] = "CONFLICT"
        result["verification"]["agreement"] = True

        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "conflict_state_inconsistent")

        result = verified_result(
            observation("X1.Ninja", "42"),
            observation("X1 RPC", "43", slot=101),
        )
        result = copy.deepcopy(result)
        result["cmis_promotable"] = True
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "promotion_state_inconsistent")

    def test_wrapper_rejects_invalid_or_inconsistent_quality_contract(self):
        result = copy.deepcopy(verified_result())
        result["data_quality"]["quality"] = "VERY_HIGH"
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "data_quality_invalid")

        result = copy.deepcopy(verified_result())
        result["data_quality"]["independent_agreement_verified"] = False
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "data_quality_agreement_inconsistent",
        )

        result = copy.deepcopy(verified_result())
        result["data_quality"]["freshness_verified"] = False
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "promotion_quality_inconsistent")

        result = copy.deepcopy(verified_result())
        result["data_quality"]["independent_source_count"] = 1
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "promotion_quality_inconsistent")

    def test_promotable_agreement_requires_equal_normalized_value_and_unit(self):
        result = copy.deepcopy(verified_result())
        result["verification"]["primary_value"] = {"nested": "not-a-scalar"}
        response = build_verification_evidence_response(result)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "promoted_fact_value_invalid")

    def test_wrapper_rejects_missing_fact_specific_verifier_contract(self):
        response = build_verification_evidence_response({})
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "verification_result_missing")

        result = copy.deepcopy(verified_result())
        del result["data_quality"]
        response = build_verification_evidence_response(result)
        self.assertEqual(response["errors"][0]["code"], "data_quality_missing")

    def test_wrapper_is_internal_service_builder_not_gateway_evidence_selector(self):
        response = build_verification_evidence_response(verified_result())
        self.assertNotIn("request", response["data"])
        self.assertNotIn("provider_query", response["data"])


if __name__ == "__main__":
    unittest.main()
