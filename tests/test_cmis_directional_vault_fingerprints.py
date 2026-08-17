import unittest

from liquidity_scout.providers.x1.directional_vault_fingerprints import (
    _direction_summary,
    correlate_directional_vault_pairs,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


ASSET = "asset-mint"
COUNTER = "counter-mint"
POOL = "pool-address"
OWNER = "pool-owner"


def token_balance(index, mint, owner, amount, decimals=0):
    return {
        "accountIndex": index,
        "mint": mint,
        "owner": owner,
        "uiTokenAmount": {
            "amount": str(amount),
            "decimals": decimals,
        },
    }


def make_tx(
    signature,
    *,
    slot=10,
    block_time=170,
    direction="BUY",
    account_order=(0, 1, 2),
    asset_owner=OWNER,
    counter_owner=OWNER,
):
    keys = [
        POOL,
        "asset-vault",
        "counter-vault",
        XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    ]
    if direction == "BUY":
        asset_pre, asset_post = 100, 90
        counter_pre, counter_post = 1000, 1010
    elif direction == "SELL":
        asset_pre, asset_post = 90, 100
        counter_pre, counter_post = 1010, 1000
    else:
        asset_pre, asset_post = 100, 90
        counter_pre, counter_post = 1000, 990

    return {
        "slot": slot,
        "blockTime": block_time,
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": keys,
                "instructions": [
                    {
                        "programIdIndex": 3,
                        "accounts": list(account_order),
                    }
                ],
            },
        },
        "meta": {
            "err": None,
            "fee": 1,
            "preBalances": [100, 100, 100, 100],
            "postBalances": [99, 100, 100, 100],
            "preTokenBalances": [
                token_balance(1, ASSET, asset_owner, asset_pre),
                token_balance(
                    2, COUNTER, counter_owner, counter_pre
                ),
            ],
            "postTokenBalances": [
                token_balance(1, ASSET, asset_owner, asset_post),
                token_balance(
                    2, COUNTER, counter_owner, counter_post
                ),
            ],
            "innerInstructions": [],
        },
    }


class FakeScanner:
    def __init__(self, entries, proven=True):
        self.entries = entries
        self.proven = proven

    def __call__(self, *args, **kwargs):
        return {
            "range_proven": self.proven,
            "integrity_verified": self.proven,
            "entries": self.entries,
        }


class FakeFetcher:
    def __init__(self, txs):
        self.txs = txs
        self.calls = []

    def __call__(self, signature, *, rpc_url):
        self.calls.append(signature)
        return self.txs[signature]


def history(signature, slot, block_time, err=None):
    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "err": err,
    }


def run(txs, *, min_direction_occurrences=2,
        min_fingerprint_ratio=0.95):
    entries = [
        history(signature, tx["slot"], tx["blockTime"])
        for signature, tx in txs.items()
    ]
    return correlate_directional_vault_pairs(
        pool_address=POOL,
        asset_mint=ASSET,
        start_epoch=100,
        end_epoch=500,
        min_direction_occurrences=min_direction_occurrences,
        min_fingerprint_ratio=min_fingerprint_ratio,
        scanner=FakeScanner(entries),
        fetcher=FakeFetcher(txs),
    )


class DirectionalVaultFingerprintTests(unittest.TestCase):
    def test_buy_and_sell_may_have_different_stable_fingerprints(self):
        txs = {
            "b1": make_tx("b1", direction="BUY",
                          account_order=(0, 1, 2)),
            "b2": make_tx("b2", slot=11, block_time=171,
                          direction="BUY",
                          account_order=(0, 1, 2)),
            "s1": make_tx("s1", slot=12, block_time=172,
                          direction="SELL",
                          account_order=(0, 2, 1)),
            "s2": make_tx("s2", slot=13, block_time=173,
                          direction="SELL",
                          account_order=(0, 2, 1)),
        }
        result = run(txs)
        pair = result["candidate_pairs"][0]
        self.assertTrue(pair["buy_fingerprint"]["fingerprint_stable"])
        self.assertTrue(pair["sell_fingerprint"]["fingerprint_stable"])
        self.assertTrue(
            pair["stable_directional_pair_candidate"]
        )

    def test_global_layout_difference_no_longer_false_negative(self):
        txs = {}
        for index in range(5):
            txs[f"b{index}"] = make_tx(
                f"b{index}",
                slot=10 + index,
                block_time=170 + index,
                direction="BUY",
                account_order=(0, 1, 2),
            )
        for index in range(5):
            txs[f"s{index}"] = make_tx(
                f"s{index}",
                slot=20 + index,
                block_time=180 + index,
                direction="SELL",
                account_order=(0, 2, 1),
            )
        pair = run(txs)["candidate_pairs"][0]
        self.assertEqual(
            pair["buy_fingerprint"][
                "dominant_instruction_fingerprint_ratio"
            ],
            1.0,
        )
        self.assertEqual(
            pair["sell_fingerprint"][
                "dominant_instruction_fingerprint_ratio"
            ],
            1.0,
        )
        self.assertTrue(
            pair["stable_directional_pair_candidate"]
        )

    def test_unstable_buy_fingerprint_gates_pair(self):
        txs = {
            "b1": make_tx("b1", direction="BUY",
                          account_order=(0, 1, 2)),
            "b2": make_tx("b2", slot=11, block_time=171,
                          direction="BUY",
                          account_order=(0, 2, 1)),
            "s1": make_tx("s1", slot=12, block_time=172,
                          direction="SELL",
                          account_order=(0, 2, 1)),
            "s2": make_tx("s2", slot=13, block_time=173,
                          direction="SELL",
                          account_order=(0, 2, 1)),
        }
        pair = run(txs)["candidate_pairs"][0]
        self.assertFalse(
            pair["buy_fingerprint"]["fingerprint_stable"]
        )
        self.assertFalse(
            pair["stable_directional_pair_candidate"]
        )

    def test_scope_only_variant_is_structurally_stable(self):
        records = {}

        for index in range(8):
            records[f"s{index}"] = {
                "direction": "SELL",
                "fingerprints": {
                    (
                        XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                        "outer",
                        3,
                        6,
                        7,
                    )
                },
            }

        records["s8"] = {
            "direction": "SELL",
            "fingerprints": {
                (
                    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "inner",
                    3,
                    6,
                    7,
                )
            },
        }

        summary = _direction_summary(
            "SELL",
            records,
            min_direction_occurrences=2,
            min_fingerprint_ratio=0.95,
        )

        self.assertEqual(summary["transaction_count"], 9)
        self.assertEqual(
            summary["dominant_instruction_fingerprint_count"],
            8,
        )
        self.assertFalse(summary["fingerprint_stable"])

        self.assertEqual(
            summary["dominant_structural_instruction_fingerprint_count"],
            9,
        )
        self.assertEqual(
            summary["dominant_structural_instruction_fingerprint_ratio"],
            1.0,
        )
        self.assertTrue(summary["structural_fingerprint_stable"])

    def test_single_observed_direction_can_be_stable_with_sample(self):
        txs = {
            "s1": make_tx("s1", direction="SELL",
                          account_order=(0, 2, 1)),
            "s2": make_tx("s2", slot=11, block_time=171,
                          direction="SELL",
                          account_order=(0, 2, 1)),
        }
        pair = run(txs)["candidate_pairs"][0]
        self.assertEqual(pair["buy_fingerprint"]["transaction_count"], 0)
        self.assertTrue(
            pair["sell_fingerprint"]["fingerprint_stable"]
        )
        self.assertTrue(
            pair["stable_directional_pair_candidate"]
        )

    def test_one_sample_direction_is_insufficient_by_default(self):
        txs = {
            "b1": make_tx("b1", direction="BUY"),
            "s1": make_tx("s1", slot=11, block_time=171,
                          direction="SELL",
                          account_order=(0, 2, 1)),
            "s2": make_tx("s2", slot=12, block_time=172,
                          direction="SELL",
                          account_order=(0, 2, 1)),
        }
        pair = run(txs)["candidate_pairs"][0]
        self.assertFalse(
            pair["buy_fingerprint"]["sufficient_sample"]
        )
        self.assertFalse(
            pair["stable_directional_pair_candidate"]
        )

    def test_same_direction_flow_gates_pair(self):
        txs = {
            "u1": make_tx("u1", direction="UNRESOLVED"),
            "u2": make_tx("u2", slot=11, block_time=171,
                          direction="UNRESOLVED"),
        }
        pair = run(txs)["candidate_pairs"][0]
        self.assertEqual(pair["opposite_direction_ratio"], 0.0)
        self.assertFalse(
            pair["stable_directional_pair_candidate"]
        )

    def test_different_owners_are_not_paired(self):
        txs = {
            "b1": make_tx(
                "b1",
                direction="BUY",
                counter_owner="different-owner",
            ),
            "b2": make_tx(
                "b2",
                slot=11,
                block_time=171,
                direction="BUY",
                counter_owner="different-owner",
            ),
        }
        result = run(txs)
        self.assertEqual(result["candidate_pairs"], [])

    def test_failed_history_transaction_not_fetched(self):
        fetcher = FakeFetcher({})
        result = correlate_directional_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner([
                history(
                    "failed",
                    10,
                    170,
                    err={"InstructionError": [0, "x"]},
                ),
            ]),
            fetcher=fetcher,
        )
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(
            result["failed_history_transaction_count"], 1
        )

    def test_canonical_promotion_always_false(self):
        txs = {
            "b1": make_tx("b1", direction="BUY"),
            "b2": make_tx("b2", slot=11, block_time=171,
                          direction="BUY"),
        }
        result = run(txs)
        pair = result["candidate_pairs"][0]
        self.assertFalse(pair["canonical_vault_pair_proven"])
        self.assertFalse(
            result["summary"]["canonical_vault_mapping_proven"]
        )
        self.assertFalse(
            result["summary"]["exact_pool_leg_semantics_promoted"]
        )

    def test_counter_mint_discovered_from_chain(self):
        txs = {
            "b1": make_tx("b1", direction="BUY"),
            "b2": make_tx("b2", slot=11, block_time=171,
                          direction="BUY"),
        }
        pair = run(txs)["candidate_pairs"][0]
        self.assertEqual(pair["counter_mint"], COUNTER)


if __name__ == "__main__":
    unittest.main()
