import unittest

from liquidity_scout.providers.x1.history_range import (
    compare_provider_rows_to_chain,
    scan_address_history_range,
    summarize_entries_for_window,
)


def entry(signature, slot, block_time, err=None):
    return {
        "signature": signature,
        "slot": slot,
        "err": err,
        "memo": None,
        "blockTime": block_time,
        "confirmationStatus": "confirmed",
    }


class FakeRPC:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        self.assert_method(method)
        before = params[1].get("before")
        return list(self.pages.get(before, []))

    @staticmethod
    def assert_method(method):
        if method != "getSignaturesForAddress":
            raise AssertionError(method)


class HistoryRangeTests(unittest.TestCase):
    def test_single_page_crosses_boundary_and_proves_range(self):
        rpc = FakeRPC({
            None: [
                entry("s3", 30, 130),
                entry("s2", 20, 120),
                entry("s1", 10, 90),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=140,
            rpc=rpc,
            page_size=10,
            max_signatures=100,
        )
        self.assertTrue(result["range_proven"])
        self.assertTrue(result["start_boundary_reached"])
        self.assertTrue(result["slot_order_verified"])
        self.assertEqual(result["pages_fetched"], 1)

    def test_before_cursor_paginates_until_boundary(self):
        rpc = FakeRPC({
            None: [
                entry("s4", 40, 140),
                entry("s3", 30, 130),
            ],
            "s3": [
                entry("s2", 20, 110),
                entry("s1", 10, 90),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=150,
            rpc=rpc,
            page_size=2,
            max_signatures=10,
        )
        self.assertTrue(result["range_proven"])
        self.assertEqual(result["pages_fetched"], 2)
        self.assertEqual(
            rpc.calls[1][1][1]["before"], "s3"
        )

    def test_out_of_order_slots_reject_range(self):
        rpc = FakeRPC({
            None: [
                entry("s3", 30, 130),
                entry("s2", 10, 120),
                entry("s1", 20, 90),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=140,
            rpc=rpc,
            page_size=10,
            max_signatures=100,
        )
        self.assertFalse(result["slot_order_verified"])
        self.assertFalse(result["range_proven"])

    def test_missing_block_time_rejects_range(self):
        rpc = FakeRPC({
            None: [
                entry("s3", 30, 130),
                entry("s2", 20, None),
                entry("s1", 10, 90),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=140,
            rpc=rpc,
            page_size=10,
            max_signatures=100,
        )
        self.assertFalse(result["block_time_complete"])
        self.assertFalse(result["range_proven"])

    def test_bound_before_boundary_is_not_proven(self):
        rpc = FakeRPC({
            None: [
                entry("s4", 40, 140),
                entry("s3", 30, 130),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=150,
            rpc=rpc,
            page_size=2,
            max_signatures=2,
        )
        self.assertTrue(result["bound_reached"])
        self.assertFalse(result["range_proven"])

    def test_duplicate_across_pages_rejects_integrity(self):
        rpc = FakeRPC({
            None: [
                entry("s4", 40, 140),
                entry("s3", 30, 130),
            ],
            "s3": [
                entry("s3", 30, 130),
                entry("s1", 10, 90),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=150,
            rpc=rpc,
            page_size=2,
            max_signatures=10,
        )
        self.assertEqual(result["duplicate_signatures"], 1)
        self.assertFalse(result["range_proven"])

    def test_provider_rows_compare_to_chain_identity_and_order(self):
        rows = [
            {
                "txHash": "s3",
                "slot": 30,
                "timestamp": "1970-01-01T00:02:10+00:00",
            },
            {
                "txHash": "s2",
                "slot": 20,
                "timestamp": "1970-01-01T00:02:00+00:00",
            },
        ]
        chain = [
            {
                "signature": "s3",
                "slot": 30,
                "block_time": 130.0,
            },
            {
                "signature": "s2",
                "slot": 20,
                "block_time": 120.0,
            },
        ]
        result = compare_provider_rows_to_chain(rows, chain)
        self.assertTrue(
            result["provider_ordering_observed_consistent"]
        )
        self.assertTrue(result["overlapping_identity_verified"])
        self.assertFalse(result["provider_range_contract_verified"])


    def test_scan_result_labels_proof_interval_not_requested_window(self):
        rpc = FakeRPC({
            None: [
                entry("s3", 30, 130),
                entry("s2", 20, 120),
                entry("s1", 10, 90),
            ],
        })
        result = scan_address_history_range(
            "pool",
            start_epoch=100,
            end_epoch=140,
            rpc=rpc,
            page_size=10,
            max_signatures=100,
        )
        self.assertEqual(result["scan_start_epoch"], 100.0)
        self.assertEqual(result["scan_end_epoch"], 140.0)
        self.assertEqual(result["scan_interval_signature_count"], 2)
        self.assertNotIn("window_signature_count", result)
        self.assertNotIn("requested_start_epoch", result)

    def test_literal_requested_window_is_separate_from_longer_proof_scan(self):
        chain_entries = [
            {
                "signature": "new",
                "slot": 40,
                "block_time": 200.0,
                "err": None,
            },
            {
                "signature": "inside_ok",
                "slot": 30,
                "block_time": 170.0,
                "err": None,
            },
            {
                "signature": "inside_failed",
                "slot": 20,
                "block_time": 160.0,
                "err": {"InstructionError": [0, "x"]},
            },
            {
                "signature": "old",
                "slot": 10,
                "block_time": 100.0,
                "err": None,
            },
        ]
        result = summarize_entries_for_window(
            chain_entries,
            start_epoch=150,
            end_epoch=180,
        )
        self.assertEqual(result["signature_count"], 2)
        self.assertEqual(result["successful_signature_count"], 1)
        self.assertEqual(result["failed_signature_count"], 1)
        self.assertEqual(
            result["oldest_signature_time_utc"],
            "1970-01-01T00:02:40+00:00",
        )
        self.assertEqual(
            result["newest_signature_time_utc"],
            "1970-01-01T00:02:50+00:00",
        )


if __name__ == "__main__":
    unittest.main()
