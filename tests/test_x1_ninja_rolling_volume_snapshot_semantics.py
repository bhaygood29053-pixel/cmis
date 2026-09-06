import unittest

from liquidity_scout.providers.x1.ninja_rolling_volume_snapshot_semantics import (
    CONTRACT,
    evaluate_x1_ninja_rolling_volume_snapshots,
)


TRADE_OLD = {
    "txHash": "2uWfa2LJcjo5qo916N9Ce7aUuu5xKctez9pL3NDCgzgAqUpQ7JZqZGKP4UtfyzmYiVWn6oJWifRhvqM6QDFPvynK",
    "slot": 76745639,
    "timestamp": "2026-09-05T14:20:43.000Z",
    "amountNative": 6.404425898000227,
    "amountToken": 6.559999999999945,
    "priceNative": 0.9762844356707744,
}
TRADE_NEW = {
    "txHash": "5GLpV4oQt8jvPHn5JtW4nG8Xf6vVW1ESCm2FSpA8jUdc3MS2vbqR9ADsVyfaNh2x7QnuG5CzQt2snSyG5UHT6hvy",
    "slot": 76853761,
    "timestamp": "2026-09-06T01:23:31.000Z",
    "amountNative": 6.584980622999865,
    "amountToken": 6.7800000000002,
    "priceNative": 0.971236080088447,
}


def run17():
    return {
        "source_workflow_run": 34004319450,
        "volume24h": 4.7430519845924595,
        "trade_rows": [
            {
                **TRADE_NEW,
                "amountUsd": 2.36993068914611,
                "priceUsd": 0.3495472992840767,
            },
            {
                **TRADE_OLD,
                "amountUsd": 2.30494914882807,
                "priceUsd": 0.35136419951647696,
            },
        ],
    }


def run18():
    return {
        "source_workflow_run": 34005213167,
        "volume24h": 4.7430519845924595,
        "trade_rows": [
            {
                **TRADE_NEW,
                "amountUsd": 2.3108345414128033,
                "priceUsd": 0.34083105330571317,
            },
            {
                **TRADE_OLD,
                "amountUsd": 2.247473368611906,
                "priceUsd": 0.34260264765425685,
            },
        ],
    }


class X1NinjaRollingVolumeSnapshotSemanticsTests(unittest.TestCase):
    def test_exact_captured_runs_prove_trade_repricing_with_stable_aggregate(self):
        result = evaluate_x1_ninja_rolling_volume_snapshots(
            before=run17(),
            after=run18(),
        )

        self.assertEqual(result["contract"], CONTRACT)
        self.assertTrue(result["exact_trade_set_stable"])
        self.assertEqual(result["trade_count"], 2)
        self.assertTrue(result["before_shared_trade_xnt_basis_verified"])
        self.assertTrue(result["after_shared_trade_xnt_basis_verified"])
        self.assertTrue(result["shared_trade_xnt_basis_changed"])
        self.assertEqual(result["before_volume24h"], result["after_volume24h"])
        self.assertTrue(result["volume24h_invariant"])
        self.assertTrue(result["trade_row_usd_repricing_observed"])
        self.assertTrue(
            result["rolling_aggregate_invariant_under_trade_repricing"]
        )
        self.assertNotEqual(
            result["before_trade_row_usd_sum"],
            result["after_trade_row_usd_sum"],
        )
        self.assertFalse(result["provider_internal_formula_verified"])
        self.assertFalse(result["provider_volume_fact_time_verified"])
        self.assertFalse(result["current_price_substitution_authorized"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_trade_identity_change_cannot_support_repricing_claim(self):
        changed = run18()
        changed["trade_rows"][0] = {
            **changed["trade_rows"][0],
            "slot": 999,
        }
        result = evaluate_x1_ninja_rolling_volume_snapshots(
            before=run17(),
            after=changed,
        )
        self.assertFalse(result["exact_trade_set_stable"])
        self.assertFalse(result["trade_row_usd_repricing_observed"])
        self.assertFalse(
            result["rolling_aggregate_invariant_under_trade_repricing"]
        )


if __name__ == "__main__":
    unittest.main()
