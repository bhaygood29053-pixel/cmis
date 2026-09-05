import unittest

from liquidity_scout.providers.x1.ninja_revaluation_watch import (
    DEFAULT_MAX_WATCH_POOLS,
    select_wrapped_xnt_watch_candidates,
)


XNT = "So11111111111111111111111111111111111111112"
REF = "REF11111111111111111111111111111111111111111"


def row(address, base, quote, liquidity="1"):
    return {
        "address": address,
        "baseToken": {"address": base},
        "quoteToken": {"address": quote},
        "liquidity": liquidity,
    }


class NinjaRevaluationWatchSelectionTests(unittest.TestCase):
    def test_selects_exact_wrapped_xnt_candidates_and_excludes_reference(self):
        pools = [
            row("pool-a", "asset-a", XNT),
            row("pool-b", XNT, "asset-b"),
            row(REF, XNT, "usdcx"),
            row("pool-c", "asset-c", "other"),
        ]

        result = select_wrapped_xnt_watch_candidates(
            pools,
            wrapped_xnt_mint=XNT,
            excluded_addresses=[REF],
        )

        self.assertEqual(
            result["selected_candidate_addresses"],
            ["pool-a", "pool-b"],
        )
        self.assertFalse(result["pool_identity_verified"])
        self.assertFalse(result["wrapped_xnt_position_verified"])
        self.assertFalse(result["liquidity_semantics_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_priority_addresses_are_retained_first_without_inventing_candidates(self):
        pools = [
            row("pool-a", "asset-a", XNT),
            row("pool-b", "asset-b", XNT),
            row("pool-c", "asset-c", XNT),
        ]

        result = select_wrapped_xnt_watch_candidates(
            pools,
            wrapped_xnt_mint=XNT,
            priority_addresses=["pool-c", "missing", "pool-a"],
        )

        self.assertEqual(
            result["selected_candidate_addresses"],
            ["pool-c", "pool-a", "pool-b"],
        )
        self.assertEqual(result["priority_candidate_count"], 2)

    def test_nonpositive_or_unparseable_liquidity_is_not_watched(self):
        pools = [
            row("pool-a", "asset-a", XNT, "0"),
            row("pool-b", "asset-b", XNT, "-1"),
            row("pool-c", "asset-c", XNT, "not-a-number"),
            row("pool-d", "asset-d", XNT, "1.25"),
        ]

        result = select_wrapped_xnt_watch_candidates(
            pools,
            wrapped_xnt_mint=XNT,
        )

        self.assertEqual(result["selected_candidate_addresses"], ["pool-d"])

    def test_watch_set_is_bounded_without_claiming_catalog_completeness(self):
        pools = [
            row(f"pool-{index}", f"asset-{index}", XNT)
            for index in range(10)
        ]

        result = select_wrapped_xnt_watch_candidates(
            pools,
            wrapped_xnt_mint=XNT,
            max_pools=5,
        )

        self.assertEqual(result["selected_candidate_count"], 5)
        self.assertTrue(result["selection_truncated"])
        self.assertFalse(result["provider_catalog_complete_verified"])

    def test_default_bound_is_150(self):
        self.assertEqual(DEFAULT_MAX_WATCH_POOLS, 150)

    def test_rejects_out_of_policy_bounds(self):
        pools = [row("pool-a", "asset-a", XNT)]
        for max_pools in (4, 501):
            with self.subTest(max_pools=max_pools):
                with self.assertRaises(ValueError):
                    select_wrapped_xnt_watch_candidates(
                        pools,
                        wrapped_xnt_mint=XNT,
                        max_pools=max_pools,
                    )


if __name__ == "__main__":
    unittest.main()
