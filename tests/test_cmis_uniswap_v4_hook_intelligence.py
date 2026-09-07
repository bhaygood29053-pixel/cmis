import unittest

from liquidity_scout.services.cmis_uniswap_v4_hook_intelligence import (
    CONTRACT_VERSION,
    ZERO_ADDRESS,
    build_uniswap_v4_hook_intelligence,
    decode_hook_permissions,
)


POOL_ID = "0x" + ("11" * 32)
POOL_MANAGER = "0x" + ("22" * 20)
TOKEN0 = "0x" + ("33" * 20)
TOKEN1 = "0x" + ("44" * 20)
HOOK_0088 = "0x" + ("55" * 18) + "0088"
CODE_HASH = "0x" + ("66" * 32)


class CMISUniswapV4HookIntelligenceTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "chain": "robinhood",
            "pool_id": POOL_ID,
            "pool_manager": POOL_MANAGER,
            "currency0": TOKEN0,
            "currency1": TOKEN1,
            "fee": 2500,
            "tick_spacing": 25,
            "hook_address": HOOK_0088,
            "pool_key_verified": True,
            "hook_code_verified": True,
            "observed_code_hash": CODE_HASH,
            "observed_at": 1788750000,
            "source_evidence_ids": ["ev_pool", "ev_code"],
        }
        values.update(overrides)
        return build_uniswap_v4_hook_intelligence(**values)

    def test_decodes_before_swap_and_return_delta_from_0088(self):
        decoded = decode_hook_permissions(HOOK_0088)
        self.assertEqual(decoded["permission_mask"], "0x0088")
        self.assertTrue(decoded["permissions"]["before_swap"])
        self.assertTrue(decoded["permissions"]["before_swap_returns_delta"])
        enabled = [
            name for name, active in decoded["permissions"].items() if active
        ]
        self.assertEqual(
            enabled,
            ["before_swap", "before_swap_returns_delta"],
        )

    def test_build_preserves_strict_read_only_boundaries(self):
        result = self.build()

        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertTrue(result["hook"]["present"])
        self.assertTrue(result["verification"]["pool_key_verified"])
        self.assertTrue(result["verification"]["hook_code_verified"])
        self.assertFalse(
            result["verification"]["hook_logic_semantics_verified"]
        )
        self.assertFalse(
            result["verification"]["reflection_behavior_verified"]
        )
        self.assertFalse(
            result["boundaries"]["reflection_claim_authorized"]
        )
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_zero_hook_is_valid_hookless_pool(self):
        result = self.build(
            hook_address=ZERO_ADDRESS,
            hook_code_verified=False,
            observed_code_hash=None,
            source_evidence_ids=["ev_pool"],
        )

        self.assertFalse(result["hook"]["present"])
        self.assertEqual(result["hook"]["permission_mask"], "0x0000")
        self.assertEqual(result["hook"]["active_permissions"], [])

    def test_zero_hook_cannot_claim_verified_code(self):
        with self.assertRaisesRegex(
            ValueError,
            "zero hook",
        ):
            self.build(hook_address=ZERO_ADDRESS)

    def test_verified_claim_requires_evidence_lineage(self):
        with self.assertRaisesRegex(
            ValueError,
            "source_evidence_id",
        ):
            self.build(source_evidence_ids=[])

    def test_same_currency_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            self.build(currency1=TOKEN0)

    def test_malformed_hook_address_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "20-byte"):
            self.build(hook_address="0x1234")


if __name__ == "__main__":
    unittest.main()
