import unittest

from liquidity_scout.providers.x1.warp_transaction_history_discovery import (
    BASE_URL,
    CONTRACT,
    WarpTransactionHistoryDiscoveryError,
    build_signatures_url,
    build_transactions_url,
    summarize_signatures_response,
    summarize_transactions_page,
)


class WarpTransactionHistoryDiscoveryTests(unittest.TestCase):
    def test_build_transactions_url_is_bounded_and_exact(self):
        self.assertEqual(
            build_transactions_url(status="executed", limit=5, page=1),
            f"{BASE_URL}/transactions?status=executed&limit=5&page=1",
        )

    def test_unsupported_status_fails_closed(self):
        with self.assertRaisesRegex(
            WarpTransactionHistoryDiscoveryError, "unsupported status"
        ):
            build_transactions_url(status="complete")

    def test_bad_pagination_fails_closed(self):
        with self.assertRaises(WarpTransactionHistoryDiscoveryError):
            build_transactions_url(status="executed", limit=0, page=1)
        with self.assertRaises(WarpTransactionHistoryDiscoveryError):
            build_transactions_url(status="executed", limit=5, page=0)

    def test_signatures_url_rejects_path_injection(self):
        self.assertEqual(
            build_signatures_url("abc123"),
            f"{BASE_URL}/transactions/abc123/signatures",
        )
        with self.assertRaises(WarpTransactionHistoryDiscoveryError):
            build_signatures_url("../admin")

    def test_transaction_summary_is_non_promoting(self):
        payload = {
            "transactions": [
                {
                    "txSig": "sig1",
                    "from": "solana",
                    "to": "x1",
                    "status": "executed",
                    "token": "wSOL",
                    "amount": "1000000000",
                    "sender": "base64sender",
                    "recipient": "base64recipient",
                    "sourceSlot": 123,
                    "timestamp": 1788436231329,
                    "signaturesCollected": 5,
                    "signaturesRequired": 5,
                    "ignored": "not surfaced",
                }
            ],
            "total": 100,
            "page": 1,
            "pageSize": 5,
        }
        result = summarize_transactions_page(payload, requested_status="executed")
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["transaction_count"], 1)
        self.assertEqual(result["observed_status_values"], ["executed"])
        self.assertEqual(result["pagination_metadata"]["total"], 100)
        self.assertIn("ignored", result["transaction_record_field_union"])
        self.assertNotIn("ignored", result["sample_transactions"][0])
        self.assertFalse(result["field_semantics_verified"])
        self.assertFalse(result["pagination_semantics_verified"])
        self.assertFalse(result["coverage_complete_verified"])
        self.assertFalse(result["flow_event_normalization_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_signature_summary_omits_raw_signatures(self):
        payload = {
            "txSig": "sig1",
            "signatures": [
                {
                    "guardianPubkey": "guardian1",
                    "signature": "secret-ish-byte-string",
                    "messageHash": "hash1",
                    "message": {
                        "seq": "42",
                        "sourceChainId": 0,
                        "destChainId": 1,
                        "guardianSetIndex": 3,
                        "sender": "sender",
                        "token": "mint",
                        "amount": "100",
                        "timestamp": 1788436231,
                        "extra": "ignored",
                    },
                }
            ],
        }
        result = summarize_signatures_response(payload, tx_sig="sig1")
        self.assertEqual(result["signature_count"], 1)
        self.assertEqual(result["guardian_pubkeys"], ["guardian1"])
        self.assertIn("signature", result["signature_record_field_union"])
        self.assertNotIn("signature", result["sample_messages"][0])
        self.assertNotIn("extra", result["sample_messages"][0])
        self.assertFalse(result["raw_guardian_signatures_retained"])
        self.assertFalse(result["message_semantics_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_missing_transactions_envelope_fails_closed(self):
        with self.assertRaisesRegex(
            WarpTransactionHistoryDiscoveryError, "transactions"
        ):
            summarize_transactions_page({}, requested_status="executed")


if __name__ == "__main__":
    unittest.main()
