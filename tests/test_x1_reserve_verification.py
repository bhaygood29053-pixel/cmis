import unittest

from liquidity_scout.cmis.evidence import (
    AGREEMENT,
    CONFLICT,
    build_evidence_observation,
)
from liquidity_scout.providers.x1.reserve_verification import (
    IDENTITY_UNVERIFIED,
    SAME_SOURCE,
    SEMANTICS_UNVERIFIED,
    WRONG_FACT_TYPE,
    verify_x1_pool_reserve,
)


class X1ReserveVerificationTests(unittest.TestCase):
    def _observation(self, **overrides):
        values = {
            "chain": "x1",
            "fact_type": "pool_reserve",
            "subject_id": "pool:pool-address:vault:vault-address:mint:mint-address",
            "source": "X1.Ninja",
            "source_role": "market_provider",
            "observed_at": 1000.0,
            "raw_value": "250000000",
            "normalized_value": "250",
            "unit": "TOKEN_UNITS",
            "block_slot": 123,
            "raw_identifier": "pool-address",
            "calculation_version": "x1-reserve-v1",
            "identity_verified": True,
            "semantics_verified": True,
            "freshness_verified": True,
        }
        values.update(overrides)
        return build_evidence_observation(**values)

    def _rpc(self, **overrides):
        values = {
            "source": "X1 RPC",
            "source_role": "onchain_verifier",
            "raw_identifier": "vault-address",
        }
        values.update(overrides)
        return self._observation(**values)

    def test_matching_independent_reserves_are_high_quality_and_promotable(self):
        result = verify_x1_pool_reserve(self._observation(), self._rpc())

        self.assertEqual(result["verification"]["status"], AGREEMENT)
        self.assertEqual(result["data_quality"]["quality"], "HIGH")
        self.assertTrue(result["cmis_promotable"])

    def test_conflicting_reserves_are_low_quality_and_not_promotable(self):
        result = verify_x1_pool_reserve(
            self._observation(),
            self._rpc(normalized_value="249.999"),
        )

        self.assertEqual(result["verification"]["status"], CONFLICT)
        self.assertEqual(result["data_quality"]["quality"], "LOW")
        self.assertFalse(result["cmis_promotable"])

    def test_unverified_semantics_fail_before_value_comparison(self):
        result = verify_x1_pool_reserve(
            self._observation(semantics_verified=False),
            self._rpc(),
        )

        self.assertEqual(result["verification"]["code"], SEMANTICS_UNVERIFIED)
        self.assertFalse(result["cmis_promotable"])

    def test_unverified_identity_fails_before_value_comparison(self):
        result = verify_x1_pool_reserve(
            self._observation(identity_verified=False),
            self._rpc(),
        )

        self.assertEqual(result["verification"]["code"], IDENTITY_UNVERIFIED)
        self.assertFalse(result["cmis_promotable"])

    def test_same_source_with_different_roles_is_not_independent(self):
        result = verify_x1_pool_reserve(
            self._observation(),
            self._observation(source_role="onchain_verifier"),
        )

        self.assertEqual(result["verification"]["code"], SAME_SOURCE)
        self.assertFalse(result["cmis_promotable"])

    def test_non_reserve_fact_is_rejected(self):
        result = verify_x1_pool_reserve(
            self._observation(fact_type="total_supply"),
            self._rpc(fact_type="total_supply"),
        )

        self.assertEqual(result["verification"]["code"], WRONG_FACT_TYPE)
        self.assertFalse(result["cmis_promotable"])

    def test_missing_freshness_can_agree_but_is_not_promotable(self):
        result = verify_x1_pool_reserve(
            self._observation(freshness_verified=False),
            self._rpc(freshness_verified=False),
        )

        self.assertEqual(result["verification"]["status"], AGREEMENT)
        self.assertEqual(result["data_quality"]["quality"], "MEDIUM")
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
