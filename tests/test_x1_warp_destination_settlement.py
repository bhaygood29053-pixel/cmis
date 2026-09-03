import unittest

from liquidity_scout.providers.x1.warp_destination_settlement import (
    CONTRACT,
    collect_warp_destination_settlement_evidence,
)


SIG = "DestSig111111111111111111111111111111111111111111111111111111111111"
SLOT = 68029675


def rpc_ok(method, params, *, rpc_url):
    if method == "getTransaction":
        return {
            "slot": SLOT,
            "blockTime": 1785414808,
            "meta": {"err": None},
            "transaction": {"signatures": [SIG]},
        }
    if method == "getBlockTime":
        return 1785414808
    raise AssertionError(method)


class WarpDestinationSettlementTests(unittest.TestCase):
    def test_exact_finalized_destination_transaction_verifies(self):
        result = collect_warp_destination_settlement_evidence(
            transaction_signature=SIG,
            slot=SLOT,
            rpc_call=rpc_ok,
            rpc_url="https://rpc.example.invalid",
        )
        self.assertEqual(result["contract"], CONTRACT)
        self.assertTrue(result["transaction_found"])
        self.assertTrue(result["slot_verified"])
        self.assertTrue(result["signature_verified"])
        self.assertTrue(result["transaction_succeeded"])
        self.assertTrue(result["finalized"])
        self.assertTrue(result["block_time_verified"])
        self.assertTrue(result["settlement_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_slot_mismatch_fails_closed(self):
        def rpc(method, params, *, rpc_url):
            if method == "getTransaction":
                return {
                    "slot": SLOT + 1,
                    "blockTime": 1785414808,
                    "meta": {"err": None},
                    "transaction": {"signatures": [SIG]},
                }
            return 1785414808

        result = collect_warp_destination_settlement_evidence(
            transaction_signature=SIG,
            slot=SLOT,
            rpc_call=rpc,
            rpc_url="https://rpc.example.invalid",
        )
        self.assertFalse(result["slot_verified"])
        self.assertFalse(result["settlement_verified"])

    def test_failed_transaction_fails_closed(self):
        def rpc(method, params, *, rpc_url):
            if method == "getTransaction":
                return {
                    "slot": SLOT,
                    "blockTime": 1785414808,
                    "meta": {"err": {"InstructionError": [0, "Custom"]}},
                    "transaction": {"signatures": [SIG]},
                }
            return 1785414808

        result = collect_warp_destination_settlement_evidence(
            transaction_signature=SIG,
            slot=SLOT,
            rpc_call=rpc,
            rpc_url="https://rpc.example.invalid",
        )
        self.assertFalse(result["transaction_succeeded"])
        self.assertFalse(result["settlement_verified"])

    def test_block_time_conflict_fails_closed(self):
        def rpc(method, params, *, rpc_url):
            if method == "getTransaction":
                return {
                    "slot": SLOT,
                    "blockTime": 1785414807,
                    "meta": {"err": None},
                    "transaction": {"signatures": [SIG]},
                }
            return 1785414808

        result = collect_warp_destination_settlement_evidence(
            transaction_signature=SIG,
            slot=SLOT,
            rpc_call=rpc,
            rpc_url="https://rpc.example.invalid",
        )
        self.assertFalse(result["block_time_matches_transaction"])
        self.assertFalse(result["settlement_verified"])


if __name__ == "__main__":
    unittest.main()
