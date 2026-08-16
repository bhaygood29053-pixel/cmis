import unittest

from liquidity_scout.services.cmis_chain_window_dex import (
    CLASS_BUY,
    CLASS_CHAIN_FAILED,
    CLASS_NON_ASSET_ACTIVITY,
    CLASS_NON_DEX,
    CLASS_UNRESOLVED_DEX_ASSET_ACTIVITY,
    classify_transaction_verification,
    enumerate_chain_window_dex_activity,
)


ASSET = "asset-mint"


def scan_result(entries, range_proven=True):
    return {
        "range_proven": range_proven,
        "integrity_verified": range_proven,
        "rpc_errors": 0 if range_proven else 1,
        "entries": entries,
    }


def entry(signature, slot, block_time, err=None):
    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "err": err,
    }


class FakeScanner:
    def __init__(self, by_address):
        self.by_address = by_address
        self.calls = []

    def __call__(self, address, **kwargs):
        self.calls.append((address, kwargs))
        return self.by_address[address]


class FakeFetcher:
    def __init__(self):
        self.calls = []

    def __call__(self, signature, *, rpc_url):
        self.calls.append(signature)
        return {"signature": signature}


class FakeVerifier:
    def __init__(self, by_signature):
        self.by_signature = by_signature
        self.calls = []

    def __call__(
        self,
        tx,
        *,
        signature,
        rpc_url,
        expected_mint,
    ):
        self.calls.append(signature)
        return dict(self.by_signature[signature])


def verification(
    *,
    slot=10,
    block_time=170,
    found=True,
    succeeded=True,
    xdex=True,
    xendex=False,
    inferred_side="UNKNOWN",
    inferred_asset_mint=None,
    token_deltas=None,
):
    return {
        "found": found,
        "succeeded": succeeded,
        "slot": slot,
        "block_time": block_time,
        "xdex_amm_invoked": xdex,
        "xendex_amm_invoked": xendex,
        "dex_protocol": "XDEX" if xdex else "UNRESOLVED",
        "verification_level": "DEX_ONCHAIN_CONFIRMED",
        "verification_basis": "TRANSACTION_ONLY",
        "inferred_side": inferred_side,
        "inferred_asset_mint": inferred_asset_mint,
        "inferred_quote_mint": None,
        "primary_signer": "signer",
        "token_deltas": token_deltas or [],
    }


class ChainWindowDexTests(unittest.TestCase):
    def test_classifies_verified_buy_for_expected_asset(self):
        result = classify_transaction_verification(
            verification(
                inferred_side="BUY",
                inferred_asset_mint=ASSET,
                token_deltas=[{"mint": ASSET}],
            ),
            expected_mint=ASSET,
        )
        self.assertEqual(result["classification"], CLASS_BUY)
        self.assertEqual(result["side"], "BUY")

    def test_recognized_dex_without_target_asset_is_non_asset_activity(self):
        result = classify_transaction_verification(
            verification(
                inferred_side="UNKNOWN",
                token_deltas=[{"mint": "other"}],
            ),
            expected_mint=ASSET,
        )
        self.assertEqual(
            result["classification"],
            CLASS_NON_ASSET_ACTIVITY,
        )

    def test_non_dex_is_not_promoted_to_trade(self):
        result = classify_transaction_verification(
            verification(
                xdex=False,
                token_deltas=[{"mint": ASSET}],
            ),
            expected_mint=ASSET,
        )
        self.assertEqual(result["classification"], CLASS_NON_DEX)

    def test_asset_moved_but_side_unresolved_stays_unresolved(self):
        result = classify_transaction_verification(
            verification(
                inferred_side="UNKNOWN",
                inferred_asset_mint=ASSET,
                token_deltas=[{"mint": ASSET}],
            ),
            expected_mint=ASSET,
        )
        self.assertEqual(
            result["classification"],
            CLASS_UNRESOLVED_DEX_ASSET_ACTIVITY,
        )

    def test_chain_failed_is_not_fetched(self):
        scanner = FakeScanner({
            "p1": scan_result([
                entry("failed", 10, 170, err={"InstructionError": [0, "x"]}),
                entry("boundary", 1, 90),
            ]),
        })
        fetcher = FakeFetcher()
        verifier = FakeVerifier({})
        result = enumerate_chain_window_dex_activity(
            asset_mint=ASSET,
            pools=[{"pool_address": "p1", "pair": "A/Q"}],
            start_epoch=100,
            end_epoch=180,
            scanner=scanner,
            fetcher=fetcher,
            verifier=verifier,
        )
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(
            result["transactions"][0]["classification"],
            CLASS_CHAIN_FAILED,
        )

    def test_same_signature_across_two_pools_is_fetched_once(self):
        scanner = FakeScanner({
            "p1": scan_result([
                entry("same", 10, 170),
                entry("boundary1", 1, 90),
            ]),
            "p2": scan_result([
                entry("same", 10, 170),
                entry("boundary2", 2, 80),
            ]),
        })
        fetcher = FakeFetcher()
        verifier = FakeVerifier({
            "same": verification(
                slot=10,
                block_time=170,
                inferred_side="BUY",
                inferred_asset_mint=ASSET,
                token_deltas=[{"mint": ASSET}],
            ),
        })
        result = enumerate_chain_window_dex_activity(
            asset_mint=ASSET,
            pools=[
                {"pool_address": "p1", "pair": "A/Q1"},
                {"pool_address": "p2", "pair": "A/Q2"},
            ],
            start_epoch=100,
            end_epoch=180,
            scanner=scanner,
            fetcher=fetcher,
            verifier=verifier,
        )
        self.assertEqual(fetcher.calls, ["same"])
        self.assertEqual(
            result["summary"]["unique_window_transaction_count"],
            1,
        )
        self.assertEqual(
            result["summary"]["multi_pool_transaction_count"],
            1,
        )
        self.assertEqual(
            result["summary"]["observed_pool_signature_membership_count"],
            2,
        )
        self.assertEqual(
            result["summary"]["verified_buy_transaction_count"],
            1,
        )

    def test_outside_window_signature_is_not_fetched(self):
        scanner = FakeScanner({
            "p1": scan_result([
                entry("newer", 20, 190),
                entry("inside", 10, 170),
                entry("older", 1, 90),
            ]),
        })
        fetcher = FakeFetcher()
        verifier = FakeVerifier({
            "inside": verification(
                slot=10,
                block_time=170,
                inferred_side="BUY",
                inferred_asset_mint=ASSET,
                token_deltas=[{"mint": ASSET}],
            ),
        })
        result = enumerate_chain_window_dex_activity(
            asset_mint=ASSET,
            pools=["p1"],
            start_epoch=100,
            end_epoch=180,
            scanner=scanner,
            fetcher=fetcher,
            verifier=verifier,
        )
        self.assertEqual(fetcher.calls, ["inside"])
        self.assertEqual(
            result["summary"]["unique_window_transaction_count"],
            1,
        )

    def test_incomplete_pool_range_gates_selected_pool_completeness(self):
        scanner = FakeScanner({
            "p1": scan_result(
                [entry("inside", 10, 170)],
                range_proven=False,
            ),
        })
        fetcher = FakeFetcher()
        verifier = FakeVerifier({
            "inside": verification(
                slot=10,
                block_time=170,
                inferred_side="BUY",
                inferred_asset_mint=ASSET,
                token_deltas=[{"mint": ASSET}],
            ),
        })
        result = enumerate_chain_window_dex_activity(
            asset_mint=ASSET,
            pools=["p1"],
            start_epoch=100,
            end_epoch=180,
            scanner=scanner,
            fetcher=fetcher,
            verifier=verifier,
        )
        self.assertFalse(
            result["summary"]["selected_pool_chain_window_complete"]
        )
        self.assertFalse(result["summary"]["asset_window_complete"])
        self.assertFalse(
            result["summary"]["asset_window_completion_promoted"]
        )


if __name__ == "__main__":
    unittest.main()
