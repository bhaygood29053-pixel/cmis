import json
import os
import unittest

from liquidity_scout.providers.x1.routed_multi_amm_ambiguity import (
    aggregate_routed_multi_amm_characterizations,
    characterize_routed_multi_amm_ambiguity,
)


RUN_LIVE = os.getenv("RUN_X1_ROUTED_MULTI_AMM_LIVE") == "1"
POOL = "GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x"
SIGNATURES = (
    "4hjYucVge1FXes1VoGVEg1nccuYdWNNBQGcv4MoxMUApZbbuL9eZodBob9DhJeaCAHpuSvLcZqtQh6aNRc3zKTcS",
    "b7VarGVfLNGxVbzNFkbGkmRXeZ5h7J9aBTkbtd4G1wbJSerZK52L6gP3Lno53nQu3WFhZF5b2pJjhy81euoBjNq",
)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_ROUTED_MULTI_AMM_LIVE=1 to run read-only evidence",
)
class RoutedMultiAmmAmbiguityLiveTests(unittest.TestCase):
    def test_exact_blocking_signatures_are_characterized(self):
        rows = [
            characterize_routed_multi_amm_ambiguity(
                signature=signature,
                pool_address=POOL,
            )
            for signature in SIGNATURES
        ]
        aggregate = aggregate_routed_multi_amm_characterizations(rows)

        public = {
            "pool_address": POOL,
            "target_signatures": list(SIGNATURES),
            "aggregate": aggregate,
        }
        print(
            "[X1 routed multi-AMM ambiguity evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(aggregate["status"], "verified")
        self.assertTrue(aggregate["all_signatures_verified"])
        self.assertTrue(aggregate["all_exact_vault_deltas_verified"])
        self.assertEqual(aggregate["signature_count"], 2)

        for row in rows:
            self.assertEqual(row["status"], "verified")
            self.assertGreaterEqual(
                row["recognized_amm_instruction_count_raw"],
                2,
            )
            self.assertTrue(row["exact_vault_deltas_verified"])
            self.assertFalse(row["classification_change_authorized"])
            self.assertTrue(row["existing_fail_closed_block_should_remain"])
            self.assertFalse(row["provider_fact_time_verified"])
            self.assertFalse(row["update_source_semantics_verified"])
            self.assertFalse(row["freshness_verified"])
            self.assertFalse(row["price_usd_semantics_verified"])
            self.assertFalse(row["liquidity_semantics_verified"])
            self.assertFalse(row["cmis_promotable"])
            self.assertFalse(row["execution_authorized"])

        self.assertFalse(aggregate["departure_pattern_verified"])
        self.assertFalse(aggregate["classification_change_authorized"])
        self.assertFalse(aggregate["cmis_promotable"])
        self.assertFalse(aggregate["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
