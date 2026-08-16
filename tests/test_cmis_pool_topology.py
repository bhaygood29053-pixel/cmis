import unittest

from liquidity_scout.providers.x1.pool_topology import (
    collect_recognized_amm_instruction_accounts,
    discover_pool_topology,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    WXNT_MINT,
)


ASSET = "asset-mint"
POOL = "pool-address"


def tx(
    *,
    signature="sig",
    slot=10,
    block_time=170,
    instructions=None,
    account_keys=None,
    pre_token=None,
    post_token=None,
):
    return {
        "slot": slot,
        "blockTime": block_time,
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": account_keys or [],
                "instructions": instructions or [],
            },
        },
        "meta": {
            "err": None,
            "fee": 5000,
            "preBalances": [1000000 for _ in (account_keys or [])],
            "postBalances": [995000 for _ in (account_keys or [])],
            "preTokenBalances": pre_token or [],
            "postTokenBalances": post_token or [],
            "innerInstructions": [],
        },
    }


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


def scan(entries, proven=True):
    return {
        "range_proven": proven,
        "integrity_verified": proven,
        "entries": entries,
    }


class FakeScanner:
    def __init__(self, result):
        self.result = result

    def __call__(self, *args, **kwargs):
        return self.result


class FakeFetcher:
    def __init__(self, by_sig):
        self.by_sig = by_sig
        self.calls = []

    def __call__(self, signature, *, rpc_url):
        self.calls.append(signature)
        return self.by_sig[signature]


class PoolTopologyTests(unittest.TestCase):
    def test_collects_string_accounts_for_recognized_instruction(self):
        transaction = tx(
            account_keys=[POOL, "asset-account", "quote-account"],
            instructions=[
                {
                    "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "accounts": [POOL, "asset-account", "quote-account"],
                }
            ],
        )
        result = collect_recognized_amm_instruction_accounts(
            transaction
        )
        self.assertEqual(
            result[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
            [POOL, "asset-account", "quote-account"],
        )

    def test_collects_indexed_accounts_for_recognized_instruction(self):
        keys = [
            POOL,
            "asset-account",
            "quote-account",
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        ]
        transaction = tx(
            account_keys=keys,
            instructions=[
                {
                    "programIdIndex": 3,
                    "accounts": [0, 1, 2],
                }
            ],
        )
        result = collect_recognized_amm_instruction_accounts(
            transaction
        )
        self.assertEqual(
            result[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
            [POOL, "asset-account", "quote-account"],
        )

    def test_recurring_asset_and_quote_accounts_become_candidates(self):
        keys = [
            POOL,
            "asset-vault",
            "quote-vault",
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        ]
        instruction = {
            "programIdIndex": 3,
            "accounts": [0, 1, 2],
        }

        one = tx(
            signature="s1",
            account_keys=keys,
            instructions=[instruction],
            pre_token=[
                token_balance(1, ASSET, "owner", 100),
                token_balance(2, WXNT_MINT, "owner", 1000),
            ],
            post_token=[
                token_balance(1, ASSET, "owner", 90),
                token_balance(2, WXNT_MINT, "owner", 1010),
            ],
        )
        two = tx(
            signature="s2",
            slot=11,
            block_time=171,
            account_keys=keys,
            instructions=[instruction],
            pre_token=[
                token_balance(1, ASSET, "owner", 90),
                token_balance(2, WXNT_MINT, "owner", 1010),
            ],
            post_token=[
                token_balance(1, ASSET, "owner", 80),
                token_balance(2, WXNT_MINT, "owner", 1020),
            ],
        )

        result = discover_pool_topology(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner(
                scan([
                    {"signature": "s1", "slot": 10, "block_time": 170, "err": None},
                    {"signature": "s2", "slot": 11, "block_time": 171, "err": None},
                ])
            ),
            fetcher=FakeFetcher({"s1": one, "s2": two}),
        )

        roles = {
            item["role_hypothesis"]: item
            for item in result["candidate_token_accounts"]
        }
        self.assertTrue(
            roles["ASSET_VAULT_CANDIDATE"]["persistent_candidate"]
        )
        self.assertTrue(
            roles["QUOTE_VAULT_CANDIDATE"]["persistent_candidate"]
        )
        self.assertTrue(
            result["summary"]["candidate_topology_observed"]
        )
        self.assertFalse(result["summary"]["topology_promoted"])

    def test_single_occurrence_is_not_persistent_by_default(self):
        keys = [
            POOL,
            "asset-vault",
            "quote-vault",
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        ]
        transaction = tx(
            account_keys=keys,
            instructions=[
                {
                    "programIdIndex": 3,
                    "accounts": [0, 1, 2],
                }
            ],
            pre_token=[
                token_balance(1, ASSET, "owner", 100),
                token_balance(2, WXNT_MINT, "owner", 1000),
            ],
            post_token=[
                token_balance(1, ASSET, "owner", 90),
                token_balance(2, WXNT_MINT, "owner", 1010),
            ],
        )
        result = discover_pool_topology(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner(
                scan([
                    {"signature": "sig", "slot": 10, "block_time": 170, "err": None},
                ])
            ),
            fetcher=FakeFetcher({"sig": transaction}),
        )
        self.assertTrue(
            all(
                not item["persistent_candidate"]
                for item in result["candidate_token_accounts"]
            )
        )
        self.assertFalse(
            result["summary"]["candidate_topology_observed"]
        )

    def test_tracks_pool_address_passed_to_amm_instruction(self):
        keys = [
            POOL,
            "asset-vault",
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        ]
        transaction = tx(
            account_keys=keys,
            instructions=[
                {
                    "programIdIndex": 2,
                    "accounts": [0, 1],
                }
            ],
            pre_token=[token_balance(1, ASSET, "owner", 100)],
            post_token=[token_balance(1, ASSET, "owner", 90)],
        )
        result = discover_pool_topology(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            min_occurrences=1,
            scanner=FakeScanner(
                scan([
                    {"signature": "sig", "slot": 10, "block_time": 170, "err": None},
                ])
            ),
            fetcher=FakeFetcher({"sig": transaction}),
        )
        self.assertEqual(
            result["pool_address_in_amm_instruction_count"], 1
        )

    def test_non_dex_transaction_does_not_create_candidate(self):
        keys = [POOL, "asset-account", "other-program"]
        transaction = tx(
            account_keys=keys,
            instructions=[
                {
                    "programId": "other-program",
                    "accounts": [POOL, "asset-account"],
                }
            ],
            pre_token=[token_balance(1, ASSET, "owner", 100)],
            post_token=[token_balance(1, ASSET, "owner", 90)],
        )
        result = discover_pool_topology(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            min_occurrences=1,
            scanner=FakeScanner(
                scan([
                    {"signature": "sig", "slot": 10, "block_time": 170, "err": None},
                ])
            ),
            fetcher=FakeFetcher({"sig": transaction}),
        )
        self.assertEqual(result["recognized_amm_transaction_count"], 0)
        self.assertEqual(result["candidate_token_accounts"], [])

    def test_same_owner_asset_quote_pair_is_observed_not_promoted(self):
        keys = [
            POOL,
            "asset-vault",
            "quote-vault",
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        ]
        transaction = tx(
            account_keys=keys,
            instructions=[
                {
                    "programIdIndex": 3,
                    "accounts": [0, 1, 2],
                }
            ],
            pre_token=[
                token_balance(1, ASSET, "shared-owner", 100),
                token_balance(2, WXNT_MINT, "shared-owner", 1000),
            ],
            post_token=[
                token_balance(1, ASSET, "shared-owner", 90),
                token_balance(2, WXNT_MINT, "shared-owner", 1010),
            ],
        )
        result = discover_pool_topology(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            min_occurrences=1,
            scanner=FakeScanner(
                scan([
                    {"signature": "sig", "slot": 10, "block_time": 170, "err": None},
                ])
            ),
            fetcher=FakeFetcher({"sig": transaction}),
        )
        owner = result["candidate_owner_groups"][0]
        self.assertTrue(owner["asset_quote_pair_observed"])
        self.assertFalse(owner["topology_promoted"])

    def test_failed_history_transaction_is_not_fetched(self):
        fetcher = FakeFetcher({})
        result = discover_pool_topology(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=180,
            scanner=FakeScanner(
                scan([
                    {
                        "signature": "failed",
                        "slot": 10,
                        "block_time": 170,
                        "err": {"InstructionError": [0, "x"]},
                    },
                ])
            ),
            fetcher=fetcher,
        )
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(
            result["successful_transaction_fetch_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
