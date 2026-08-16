import unittest

from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)
from liquidity_scout.providers.x1.vault_pair_correlation import (
    collect_recognized_amm_instruction_occurrences,
    correlate_pool_vault_pairs,
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
    asset_pre=100,
    asset_post=90,
    counter_pre=1000,
    counter_post=1010,
    include_pool=True,
    asset_owner=OWNER,
    counter_owner=OWNER,
    positions=(0, 1, 2),
):
    keys = [
        POOL,
        "asset-vault",
        "counter-vault",
        XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    ]
    accounts = [
        keys[positions[0]],
        keys[positions[1]],
        keys[positions[2]],
    ]
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
                        "accounts": accounts if include_pool else [1, 2],
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
                    2,
                    COUNTER,
                    counter_owner,
                    counter_pre,
                ),
            ],
            "postTokenBalances": [
                token_balance(1, ASSET, asset_owner, asset_post),
                token_balance(
                    2,
                    COUNTER,
                    counter_owner,
                    counter_post,
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


class VaultPairCorrelationTests(unittest.TestCase):
    def test_collects_ordered_instruction_positions(self):
        transaction = make_tx("s1")
        found = collect_recognized_amm_instruction_occurrences(
            transaction
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(
            found[0]["accounts"],
            [POOL, "asset-vault", "counter-vault"],
        )

    def test_two_consistent_transactions_form_stable_pair(self):
        txs = {
            "s1": make_tx("s1", slot=10, block_time=170),
            "s2": make_tx(
                "s2",
                slot=11,
                block_time=171,
                asset_pre=90,
                asset_post=80,
                counter_pre=1010,
                counter_post=1020,
            ),
        }
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner([
                history("s1", 10, 170),
                history("s2", 11, 171),
            ]),
            fetcher=FakeFetcher(txs),
        )
        self.assertEqual(
            result["summary"]["stable_pair_candidate_count"], 1
        )
        pair = result["candidate_pairs"][0]
        self.assertEqual(pair["opposite_direction_ratio"], 1.0)
        self.assertEqual(
            pair["dominant_instruction_fingerprint_ratio"], 1.0
        )
        self.assertFalse(pair["canonical_vault_pair_proven"])

    def test_sell_direction_is_supported(self):
        txs = {
            "s1": make_tx(
                "s1",
                asset_pre=90,
                asset_post=100,
                counter_pre=1010,
                counter_post=1000,
            ),
            "s2": make_tx(
                "s2",
                slot=11,
                block_time=171,
                asset_pre=100,
                asset_post=110,
                counter_pre=1000,
                counter_post=990,
            ),
        }
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner([
                history("s1", 10, 170),
                history("s2", 11, 171),
            ]),
            fetcher=FakeFetcher(txs),
        )
        self.assertEqual(
            result["candidate_pairs"][0]["sell_direction_count"], 2
        )

    def test_same_direction_does_not_pass_opposite_threshold(self):
        txs = {
            "s1": make_tx(
                "s1",
                asset_pre=100,
                asset_post=90,
                counter_pre=1000,
                counter_post=990,
            ),
            "s2": make_tx(
                "s2",
                slot=11,
                block_time=171,
                asset_pre=90,
                asset_post=80,
                counter_pre=990,
                counter_post=980,
            ),
        }
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner([
                history("s1", 10, 170),
                history("s2", 11, 171),
            ]),
            fetcher=FakeFetcher(txs),
        )
        self.assertFalse(
            result["candidate_pairs"][0]["stable_pair_candidate"]
        )

    def test_different_owners_are_not_paired(self):
        txs = {
            "s1": make_tx(
                "s1",
                counter_owner="different-owner",
            ),
            "s2": make_tx(
                "s2",
                slot=11,
                block_time=171,
                counter_owner="different-owner",
            ),
        }
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner([
                history("s1", 10, 170),
                history("s2", 11, 171),
            ]),
            fetcher=FakeFetcher(txs),
        )
        self.assertEqual(result["candidate_pairs"], [])

    def test_pool_must_be_in_same_recognized_instruction(self):
        transaction = make_tx("s1", include_pool=False)
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            min_occurrences=1,
            scanner=FakeScanner([history("s1", 10, 170)]),
            fetcher=FakeFetcher({"s1": transaction}),
        )
        self.assertEqual(
            result["recognized_pool_instruction_transaction_count"], 0
        )
        self.assertEqual(result["candidate_pairs"], [])

    def test_changed_instruction_fingerprint_can_gate_pair(self):
        one = make_tx("s1")
        # Keep the same account set but change order: pool, counter, asset.
        two = make_tx(
            "s2",
            slot=11,
            block_time=171,
            positions=(0, 2, 1),
            asset_pre=90,
            asset_post=80,
            counter_pre=1010,
            counter_post=1020,
        )
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            min_fingerprint_ratio=0.75,
            scanner=FakeScanner([
                history("s1", 10, 170),
                history("s2", 11, 171),
            ]),
            fetcher=FakeFetcher({"s1": one, "s2": two}),
        )
        pair = result["candidate_pairs"][0]
        self.assertEqual(
            pair["dominant_instruction_fingerprint_ratio"], 0.5
        )
        self.assertFalse(pair["stable_pair_candidate"])

    def test_failed_history_transaction_is_not_fetched(self):
        fetcher = FakeFetcher({})
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            min_occurrences=1,
            scanner=FakeScanner([
                history(
                    "failed",
                    10,
                    170,
                    err={"InstructionError": [0, "x"]},
                )
            ]),
            fetcher=fetcher,
        )
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(
            result["failed_history_transaction_count"], 1
        )

    def test_nondefault_counter_mint_is_discovered_from_chain(self):
        txs = {
            "s1": make_tx("s1"),
            "s2": make_tx(
                "s2",
                slot=11,
                block_time=171,
                asset_pre=90,
                asset_post=80,
                counter_pre=1010,
                counter_post=1020,
            ),
        }
        result = correlate_pool_vault_pairs(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner([
                history("s1", 10, 170),
                history("s2", 11, 171),
            ]),
            fetcher=FakeFetcher(txs),
        )
        self.assertEqual(
            result["candidate_pairs"][0]["counter_mint"], COUNTER
        )


if __name__ == "__main__":
    unittest.main()
