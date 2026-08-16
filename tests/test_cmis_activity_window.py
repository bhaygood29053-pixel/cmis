import unittest

from liquidity_scout.services.cmis_activity_window import (
    apply_activity_window,
    parse_activity_window_seconds,
)


def event(signature, pool, side, chain_time, *, asset_scope=True):
    return {
        "status": "ok",
        "pool_address": pool,
        "transaction_signature": signature,
        "provider_type": side.lower(),
        "side": side,
        "side_verified": True,
        "asset_scope_verified": asset_scope,
        "asset_mint": "agi-mint" if asset_scope else "other-mint",
        "quote_mint": "quote",
        "verification_level": "PROVIDER_SIDE_ONCHAIN_CONFIRMED",
        "verification_basis": "SIGNER_OR_ROUTED_BALANCE_DIRECTION",
        "identity": {
            "timestamp_verified": True,
            "chain_block_time": chain_time,
        },
        "exact_pool_leg": None,
        "warnings": [],
        "errors": [],
    }


def envelope(events, *, status="ok"):
    return {
        "service": "verified_asset_activity",
        "chain": "x1",
        "status": status,
        "asset": {"symbol": "AGI", "mint": "agi-mint"},
        "data": {
            "events": list(events),
            "pools": [],
            "swap_candidate_count": len(events),
        },
        "confidence": {
            "complete": status == "ok",
            "pool_selection_complete": True,
            "pool_history_complete": True,
        },
        "warnings": [],
        "errors": [],
    }


def pool_record(
    address,
    *,
    returned,
    processed,
    range_verified=False,
):
    return {
        "pool_address": address,
        "history_ok": True,
        "provider_event_count": returned,
        "processed_event_count": processed,
        "history_semantics": {
            "pagination_or_range_verified": range_verified,
        },
    }


class ActivityWindowTests(unittest.TestCase):
    def test_supported_windows_are_explicit(self):
        self.assertEqual(parse_activity_window_seconds("1h"), 3600)
        self.assertEqual(parse_activity_window_seconds("6h"), 21600)
        self.assertEqual(parse_activity_window_seconds("24h"), 86400)
        with self.assertRaises(ValueError):
            parse_activity_window_seconds("2h")

    def test_window_membership_uses_verified_chain_time(self):
        # End: 2026-08-16T16:00:00Z, start: 15:00Z
        result = apply_activity_window(
            envelope([
                event(
                    "inside",
                    "pool-a",
                    "BUY",
                    "2026-08-16T15:30:00+00:00",
                ),
                event(
                    "before",
                    "pool-a",
                    "SELL",
                    "2026-08-16T14:59:59+00:00",
                ),
            ]),
            window_seconds=3600,
            window_end_epoch=1786896000,
            pool_records=[
                pool_record(
                    "pool-a",
                    returned=2,
                    processed=2,
                    range_verified=False,
                )
            ],
        )

        window = result["data"]["activity_window"]
        activity = result["data"]["window_activity"]
        self.assertEqual(window["processed_event_count_in_window"], 1)
        self.assertEqual(window["processed_event_count_before_window"], 1)
        self.assertEqual(activity["verified_transaction_count"], 1)
        self.assertEqual(activity["verified_buy_transaction_count"], 1)

    def test_unverified_provider_range_keeps_window_partial(self):
        result = apply_activity_window(
            envelope([
                event(
                    "inside",
                    "pool-a",
                    "BUY",
                    "2026-08-16T15:30:00+00:00",
                ),
                event(
                    "old",
                    "pool-a",
                    "SELL",
                    "2026-08-16T14:30:00+00:00",
                ),
            ]),
            window_seconds=3600,
            window_end_epoch=1786896000,
            pool_records=[
                pool_record(
                    "pool-a",
                    returned=2,
                    processed=2,
                    range_verified=False,
                )
            ],
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(
            result["confidence"]["window_coverage_complete"]
        )
        codes = {w["code"] for w in result["warnings"]}
        self.assertIn("activity_window_range_not_proven", codes)

    def test_verified_range_and_start_boundary_can_prove_window(self):
        result = apply_activity_window(
            envelope([
                event(
                    "inside",
                    "pool-a",
                    "BUY",
                    "2026-08-16T15:30:00+00:00",
                ),
                event(
                    "old",
                    "pool-a",
                    "SELL",
                    "2026-08-16T14:30:00+00:00",
                ),
            ]),
            window_seconds=3600,
            window_end_epoch=1786896000,
            pool_records=[
                pool_record(
                    "pool-a",
                    returned=2,
                    processed=2,
                    range_verified=True,
                )
            ],
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(
            result["confidence"]["window_coverage_complete"]
        )

    def test_same_signature_two_pools_is_one_window_transaction(self):
        result = apply_activity_window(
            envelope([
                event(
                    "sig-one",
                    "pool-a",
                    "BUY",
                    "2026-08-16T15:30:00+00:00",
                ),
                event(
                    "sig-one",
                    "pool-b",
                    "BUY",
                    "2026-08-16T15:30:00+00:00",
                ),
            ], status="partial"),
            window_seconds=3600,
            window_end_epoch=1786896000,
            pool_records=[
                pool_record(
                    "pool-a",
                    returned=1,
                    processed=1,
                    range_verified=False,
                ),
                pool_record(
                    "pool-b",
                    returned=1,
                    processed=1,
                    range_verified=False,
                ),
            ],
        )

        activity = result["data"]["window_activity"]
        self.assertEqual(activity["unique_transaction_count"], 1)
        self.assertEqual(activity["verified_transaction_count"], 1)
        self.assertEqual(activity["verified_pool_leg_count"], 2)
        self.assertEqual(activity["multi_pool_transaction_count"], 1)


if __name__ == "__main__":
    unittest.main()
