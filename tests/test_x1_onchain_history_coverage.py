import unittest

from liquidity_scout.providers.x1.onchain_history_coverage import (
    build_rpc_visible_mint_history_coverage,
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


class FakeProvider:
    def __init__(self, pages, *, first_available_block=5, boundary_error=None):
        self.pages = pages
        self.first_available_block = first_available_block
        self.boundary_error = boundary_error
        self.calls = []

    def get_first_available_block(self):
        if self.boundary_error is not None:
            raise self.boundary_error
        return {
            "first_available_block": self.first_available_block,
            "history_boundary_verified": True,
            "archival_completeness_verified": False,
            "source": "X1 RPC getFirstAvailableBlock",
        }

    def request(self, method, params):
        self.calls.append((method, params))
        if method != "getSignaturesForAddress":
            raise AssertionError(method)
        before = params[1].get("before")
        value = self.pages.get(before, [])
        if isinstance(value, Exception):
            raise value
        return list(value)


class X1OnchainHistoryCoverageTests(unittest.TestCase):
    def test_exhausted_verified_mint_history_is_full_rpc_visible_only(self):
        provider = FakeProvider({
            None: [
                entry("s3", 30, 130),
                entry("s2", 20, 120),
            ],
            "s2": [
                entry("s1", 10, 90),
            ],
        })

        result = build_rpc_visible_mint_history_coverage(
            "MINT",
            rpc_provider=provider,
            page_size=2,
            max_signatures=10,
            clock=lambda: 200,
        )

        self.assertEqual(result["status"], "full")
        self.assertEqual(
            result["coverage_scope"],
            "x1_rpc_visible_mint_address_history",
        )
        self.assertTrue(result["rpc_visible_mint_history_complete"])
        self.assertTrue(result["rpc_history_exhausted"])
        self.assertTrue(result["scan_integrity_verified"])
        self.assertTrue(result["rpc_block_boundary_verified"])
        self.assertEqual(result["first_available_block"], 5)
        self.assertEqual(result["newest_verified_slot"], 30)
        self.assertEqual(result["oldest_verified_slot"], 10)
        self.assertFalse(result["asset_wide_activity_verified"])
        self.assertFalse(result["full_asset_lifetime_verified"])
        self.assertFalse(result["archival_completeness_verified"])

    def test_safety_bound_yields_partial_coverage(self):
        provider = FakeProvider({
            None: [
                entry("s4", 40, 140),
                entry("s3", 30, 130),
            ],
        })

        result = build_rpc_visible_mint_history_coverage(
            "MINT",
            rpc_provider=provider,
            page_size=2,
            max_signatures=2,
            clock=lambda: 200,
        )

        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["safety_bound_reached"])
        self.assertFalse(result["rpc_visible_mint_history_complete"])
        self.assertEqual(
            result["reason"],
            "rpc_visible_mint_address_history_safety_bound_reached",
        )

    def test_boundary_failure_keeps_exhausted_scan_partial(self):
        provider = FakeProvider(
            {
                None: [
                    entry("s2", 20, 120),
                    entry("s1", 10, 90),
                ],
            },
            boundary_error=RuntimeError("boundary unavailable"),
        )

        result = build_rpc_visible_mint_history_coverage(
            "MINT",
            rpc_provider=provider,
            page_size=10,
            max_signatures=20,
            clock=lambda: 200,
        )

        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["rpc_history_exhausted"])
        self.assertFalse(result["rpc_block_boundary_verified"])
        self.assertEqual(
            result["reason"],
            "x1_rpc_block_boundary_unverified",
        )
        self.assertIn("rpc_block_boundary_error", result)

    def test_mid_scan_rpc_error_retains_partial_observed_history(self):
        provider = FakeProvider({
            None: [
                entry("s4", 40, 140),
                entry("s3", 30, 130),
            ],
            "s3": RuntimeError("rpc down"),
        })

        result = build_rpc_visible_mint_history_coverage(
            "MINT",
            rpc_provider=provider,
            page_size=2,
            max_signatures=10,
            clock=lambda: 200,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["signature_count"], 2)
        self.assertEqual(result["rpc_errors"], 1)
        self.assertEqual(result["reason"], "x1_rpc_history_scan_failed")
        self.assertFalse(result["rpc_visible_mint_history_complete"])

    def test_missing_provider_is_explicit_unavailable_without_fake_source(self):
        result = build_rpc_visible_mint_history_coverage(
            "MINT",
            rpc_provider=None,
            clock=lambda: 200,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "x1_rpc_provider_not_configured")
        self.assertIsNone(result["source"])
        self.assertFalse(result["full_asset_lifetime_verified"])

    def test_empty_mint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mint is required"):
            build_rpc_visible_mint_history_coverage(
                " ",
                rpc_provider=None,
            )


if __name__ == "__main__":
    unittest.main()
