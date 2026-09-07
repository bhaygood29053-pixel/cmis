import unittest

from liquidity_scout.services.cmis_reflection_flow_intelligence import (
    CONTRACT_VERSION,
    build_reflection_flow_intelligence,
)
from liquidity_scout.services.cmis_uniswap_v4_hook_intelligence import (
    build_uniswap_v4_hook_intelligence,
)


POOL_ID = "0x" + ("11" * 32)
POOL_MANAGER = "0x" + ("22" * 20)
TOKEN0 = "0x" + ("33" * 20)
TOKEN1 = "0x" + ("44" * 20)
HOOK_0088 = "0x" + ("55" * 18) + "0088"
CODE_HASH = "0x" + ("66" * 32)


def hook_evidence():
    return build_uniswap_v4_hook_intelligence(
        chain="robinhood",
        pool_id=POOL_ID,
        pool_manager=POOL_MANAGER,
        currency0=TOKEN0,
        currency1=TOKEN1,
        fee=1000,
        tick_spacing=10,
        hook_address=HOOK_0088,
        pool_key_verified=True,
        hook_code_verified=True,
        observed_code_hash=CODE_HASH,
        observed_at=1000,
        source_evidence_ids=["pool-evidence", "code-evidence"],
    )


def observations():
    return [
        {
            "transaction_id": "0xtx1",
            "pool_id": POOL_ID,
            "hook_address": HOOK_0088,
            "observed_at": 1100,
            "reflection_asset_id": TOKEN1,
            "reflection_amount": "10.5",
            "destination": "0xdistribution",
            "transfer_verified": True,
            "hook_attribution_verified": True,
            "distribution_semantics_verified": True,
            "source_evidence_id": "flow-1",
        },
        {
            "transaction_id": "0xtx2",
            "pool_id": POOL_ID,
            "hook_address": HOOK_0088,
            "observed_at": 1200,
            "reflection_asset_id": TOKEN1,
            "reflection_amount": "4.5",
            "destination": "0xdistribution",
            "transfer_verified": True,
            "hook_attribution_verified": True,
            "distribution_semantics_verified": True,
            "source_evidence_id": "flow-2",
        },
    ]


class CMISReflectionFlowIntelligenceTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "hook_intelligence": hook_evidence(),
            "window_start": 1000,
            "window_end": 1300,
            "reflection_asset_id": TOKEN1,
            "observations": observations(),
        }
        values.update(overrides)
        return build_reflection_flow_intelligence(**values)

    def test_aggregates_only_verified_exact_scope_flows(self):
        result = self.build()

        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["flow"]["verified_event_count"], 2)
        self.assertEqual(result["flow"]["total_reflection_amount"], "15.0")
        self.assertTrue(
            result["verification"]["holder_distribution_semantics_verified"]
        )
        self.assertTrue(
            result["boundaries"]["holder_distribution_claim_authorized"]
        )
        self.assertFalse(
            result["boundaries"]["lifetime_reflection_total_claim_authorized"]
        )
        self.assertFalse(result["execution_authorized"])

    def test_permission_bits_are_not_enough_without_verified_code(self):
        weak_hook = hook_evidence()
        weak_hook["verification"]["hook_code_verified"] = False

        with self.assertRaisesRegex(ValueError, "hook_code_verified"):
            self.build(hook_intelligence=weak_hook)

    def test_pool_mismatch_fails_closed(self):
        bad = observations()
        bad[0]["pool_id"] = "0x" + ("aa" * 32)

        with self.assertRaisesRegex(ValueError, "pool mismatch"):
            self.build(observations=bad)

    def test_hook_mismatch_fails_closed(self):
        bad = observations()
        bad[0]["hook_address"] = "0x" + ("bb" * 20)

        with self.assertRaisesRegex(ValueError, "hook mismatch"):
            self.build(observations=bad)

    def test_unverified_transfer_fails_closed(self):
        bad = observations()
        bad[0]["transfer_verified"] = False

        with self.assertRaisesRegex(ValueError, "transfer_verified"):
            self.build(observations=bad)

    def test_duplicate_transaction_fails_closed(self):
        bad = observations()
        bad[1]["transaction_id"] = bad[0]["transaction_id"]

        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build(observations=bad)

    def test_partial_distribution_semantics_stays_bounded(self):
        partial = observations()
        partial[1]["distribution_semantics_verified"] = False

        result = self.build(observations=partial)

        self.assertFalse(
            result["verification"]["holder_distribution_semantics_verified"]
        )
        self.assertFalse(
            result["boundaries"]["holder_distribution_claim_authorized"]
        )


if __name__ == "__main__":
    unittest.main()
