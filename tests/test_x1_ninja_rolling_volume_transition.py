import unittest

from liquidity_scout.providers.x1.ninja_rolling_volume_transition import (
    CONTRACT,
    evaluate_x1_ninja_rolling_volume_transition,
)


BEFORE = {
    "source": "PR #503 / workflow 33999943283",
    "lastSyncedAt": "2026-09-05T23:38:49.216Z",
    "volume24h": 2.3859003395922413,
    "transactions24h": 1,
    "priceUsd": 0.35434721928318147,
}

AFTER = {
    "source": "PR #506 / workflow 34004319450",
    "lastSyncedAt": "2026-09-06T01:23:33.262Z",
    "volume24h": 4.7430519845924595,
    "transactions24h": 2,
    "priceUsd": 0.34766248451329623,
}

NEW_SWAP = {
    "signature": "5GLpV4oQt8jvPHn5JtW4nG8Xf6vVW1ESCm2FSpA8jUdc3MS2vbqR9ADsVyfaNh2x7QnuG5CzQt2snSyG5UHT6hvy",
    "slot": 76853761,
    "block_time": 1788657811,
    "asset_amount": 6.7800000000002,
    "quote_amount": 6.584980622999865,
    "price_native": 0.971236080088447,
}


class X1NinjaRollingVolumeTransitionTests(unittest.TestCase):
    def test_exact_captured_transition_matches_post_update_pool_price(self):
        result = evaluate_x1_ninja_rolling_volume_transition(
            before=BEFORE,
            after=AFTER,
            new_swap=NEW_SWAP,
        )

        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["transactions24h_delta"], 1)
        self.assertTrue(result["one_new_provider_transaction_observed"])
        self.assertTrue(result["rolling_volume_transition_observed"])
        self.assertEqual(
            result["volume24h_delta_usd"],
            "2.3571516450002182",
        )
        self.assertTrue(
            result[
                "volume_delta_matches_asset_amount_times_after_price_usd"
            ]
        )
        self.assertTrue(
            result["post_update_pool_usd_price_relationship_verified"]
        )
        self.assertEqual(
            result["implied_stored_asset_usd_price"],
            "0.3476624845132962636435246815",
        )
        self.assertFalse(result["provider_price_used_as_independent_valuation"])
        self.assertFalse(result["provider_internal_formula_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["independent_usd_valuation_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_wrong_post_update_price_fails_relationship(self):
        after = dict(AFTER)
        after["priceUsd"] = 0.34
        result = evaluate_x1_ninja_rolling_volume_transition(
            before=BEFORE,
            after=after,
            new_swap=NEW_SWAP,
        )
        self.assertTrue(result["rolling_volume_transition_observed"])
        self.assertFalse(
            result[
                "volume_delta_matches_asset_amount_times_after_price_usd"
            ]
        )
        self.assertFalse(
            result["post_update_pool_usd_price_relationship_verified"]
        )


if __name__ == "__main__":
    unittest.main()
