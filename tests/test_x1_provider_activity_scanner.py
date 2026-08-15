import sqlite3
import unittest

from liquidity_scout.providers.x1 import (
    ACTIVITY_SOURCE,
    X1ActivityScanner,
    collect_signature_window as provider_collect_signature_window,
    initialize_activity_db as provider_initialize_activity_db,
    open_activity_db as provider_open_activity_db,
    scan_token_activity as provider_scan_token_activity,
)
from liquidity_scout.providers.x1.activity_scanner import CHAIN
from liquidity_scout.tokenomics import (
    collect_signature_window as legacy_collect_signature_window,
    initialize_activity_db as legacy_initialize_activity_db,
    open_activity_db as legacy_open_activity_db,
    scan_token_activity as legacy_scan_token_activity,
)


MINT = "MintA"


def signature(value, err=None):
    return {"signature": value, "err": err}


def transaction(kind, amount):
    return {
        "blockTime": 1700000000,
        "meta": {"err": None, "innerInstructions": []},
        "transaction": {
            "message": {
                "instructions": [
                    {
                        "parsed": {
                            "type": kind,
                            "info": {
                                "mint": MINT,
                                "account": "TokenAccountA",
                                "authority": "AuthorityA",
                                "amount": str(amount),
                            },
                        }
                    }
                ]
            }
        },
    }


class FakeRPC:
    def __init__(self):
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "getSignaturesForAddress":
            return [signature("sig1")]
        if method == "getTransaction":
            return transaction("burn", "1250000")
        raise AssertionError(f"unexpected RPC method: {method}")


class X1ActivityScannerProviderBoundaryTests(unittest.TestCase):
    def test_provider_metadata_is_explicit(self):
        self.assertEqual(CHAIN, "x1")
        self.assertEqual(ACTIVITY_SOURCE, "X1 RPC parsed token instructions")
        self.assertEqual(X1ActivityScanner.chain, "x1")
        self.assertEqual(X1ActivityScanner.source, ACTIVITY_SOURCE)

    def test_legacy_scanner_exports_are_provider_symbols(self):
        self.assertIs(
            legacy_collect_signature_window,
            provider_collect_signature_window,
        )
        self.assertIs(legacy_initialize_activity_db, provider_initialize_activity_db)
        self.assertIs(legacy_open_activity_db, provider_open_activity_db)
        self.assertIs(legacy_scan_token_activity, provider_scan_token_activity)

    def test_facade_preserves_bounded_scan_semantics(self):
        rpc = FakeRPC()
        scanner = X1ActivityScanner(rpc)
        db = sqlite3.connect(":memory:")
        try:
            report = scanner.scan(
                mint=MINT,
                decimals=6,
                db=db,
                max_signatures=1,
            )
        finally:
            db.close()

        self.assertTrue(report["activity_verified"])
        self.assertEqual(report["coverage_scope"], "bounded")
        self.assertFalse(report["lifetime_coverage_verified"])
        self.assertEqual(
            report["lifetime_coverage_reason"],
            "bounded_signature_window",
        )
        self.assertEqual(report["burned_tokens_observed"], "1.25")
        self.assertEqual(report["net_issuance_tokens"], "-1.25")
        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getSignaturesForAddress", "getTransaction"],
        )

    def test_facade_rejects_missing_rpc_callable(self):
        with self.assertRaises(ValueError):
            X1ActivityScanner(None)


if __name__ == "__main__":
    unittest.main()
