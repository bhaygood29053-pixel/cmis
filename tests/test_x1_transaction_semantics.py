import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.transaction_semantics import (
    USDC_X_MINT,
    WXNT_MINT,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    XENDEX_AMM_PROGRAM_ID,
    collect_program_ids,
    compute_token_deltas,
    verify_transaction,
)

SIGNER = "Signer11111111111111111111111111111111111111"
AGI = "AgiMint1111111111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Real transaction observed 2026-08-13 through X1.Ninja and X1 RPC.
REAL_SIGNATURE = "F4HMz4Y6BHRvj5ZgSbzaAiQD9KomEiEghcUH797RZ5ALVqhWooKrQzQgXzx3brTbYDWV5T2dwyxrhC56k5bnxsP"
REAL_SIGNER = "7obiC6eexLFcHpL4mF4a8JwroV39v2FXUxAJHUtYFU2X"
REAL_POOL_OWNER = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"
REAL_ASSET_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
REAL_SIGNER_ASSET_ACCOUNT = "5fxn1fBKCL9VaCTt43TCtXawGbS9agLxctfPfhPQxcj6"
REAL_POOL_WXNT_ACCOUNT = "7khUrkZN7Y6VgoSR8pASMFjHcKwqdh2cd6NRctXyjSZC"
REAL_POOL_ASSET_ACCOUNT = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"


def make_tx(
    asset_pre,
    asset_post,
    quote_pre,
    quote_post,
    *,
    protocol="xendex",
    quote_mint=WXNT_MINT,
):
    if protocol == "xendex":
        program = XENDEX_AMM_PROGRAM_ID
    elif protocol == "xdex":
        program = XDEX_MAINNET_OBSERVED_PROGRAM_ID
    else:
        program = TOKEN_PROGRAM

    keys = [
        {"pubkey": SIGNER, "signer": True, "writable": True},
        {"pubkey": "AssetAcct11111111111111111111111111111111111", "signer": False, "writable": True},
        {"pubkey": "QuoteAcct11111111111111111111111111111111111", "signer": False, "writable": True},
        {"pubkey": program, "signer": False, "writable": False},
    ]
    return {
        "slot": 123456,
        "blockTime": 1770000000,
        "transaction": {
            "message": {
                "accountKeys": keys,
                "instructions": [{"programId": program, "parsed": {"type": "swap"}}],
            }
        },
        "meta": {
            "err": None,
            "fee": 5000,
            "preBalances": [10_000_000_000, 0, 0, 0],
            "postBalances": [9_999_995_000, 0, 0, 0],
            "preTokenBalances": [
                {
                    "accountIndex": 1,
                    "mint": AGI,
                    "owner": SIGNER,
                    "uiTokenAmount": {
                        "amount": str(asset_pre),
                        "decimals": 6,
                        "uiAmountString": str(Decimal(asset_pre) / Decimal(1_000_000)),
                    },
                },
                {
                    "accountIndex": 2,
                    "mint": quote_mint,
                    "owner": SIGNER,
                    "uiTokenAmount": {
                        "amount": str(quote_pre),
                        "decimals": 9 if quote_mint == WXNT_MINT else 6,
                        "uiAmountString": "0",
                    },
                },
            ],
            "postTokenBalances": [
                {
                    "accountIndex": 1,
                    "mint": AGI,
                    "owner": SIGNER,
                    "uiTokenAmount": {
                        "amount": str(asset_post),
                        "decimals": 6,
                        "uiAmountString": str(Decimal(asset_post) / Decimal(1_000_000)),
                    },
                },
                {
                    "accountIndex": 2,
                    "mint": quote_mint,
                    "owner": SIGNER,
                    "uiTokenAmount": {
                        "amount": str(quote_post),
                        "decimals": 9 if quote_mint == WXNT_MINT else 6,
                        "uiAmountString": "0",
                    },
                },
            ],
            "innerInstructions": [],
        },
    }


def make_real_xdex_buy_fixture():
    # The fixture retains the exact economically relevant values surfaced by
    # the real RPC transaction. Absolute signer balance is synthetic; its exact
    # observed delta (-0.28369609 XNT) and fee (0.001656810 XNT) are preserved.
    keys = [
        {"pubkey": REAL_SIGNER, "signer": True, "writable": True},       # 0
        {"pubkey": REAL_SIGNER_ASSET_ACCOUNT, "signer": False, "writable": True},  # 1
        {"pubkey": REAL_POOL_WXNT_ACCOUNT, "signer": False, "writable": True},     # 2
        {"pubkey": REAL_POOL_ASSET_ACCOUNT, "signer": False, "writable": True},    # 3
        {"pubkey": "ComputeBudget111111111111111111111111111111", "signer": False, "writable": False}, # 4
        {"pubkey": "11111111111111111111111111111111", "signer": False, "writable": False},            # 5
        {"pubkey": TOKEN_PROGRAM, "signer": False, "writable": False},                                    # 6
        {"pubkey": "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL", "signer": False, "writable": False}, # 7
        {"pubkey": XDEX_MAINNET_OBSERVED_PROGRAM_ID, "signer": False, "writable": False},                 # 8
    ]

    return {
        "slot": 71_338_200,
        "blockTime": 1_786_632_211,  # 2026-08-13T14:43:31Z
        "transaction": {
            "message": {
                "accountKeys": keys,
                "instructions": [
                    {"programId": keys[4]["pubkey"]},
                    {"programId": keys[5]["pubkey"]},
                    {"programId": keys[6]["pubkey"]},
                    {"programId": keys[7]["pubkey"]},
                    {"programId": keys[8]["pubkey"]},
                ],
            }
        },
        "meta": {
            "err": None,
            "fee": 1_656_810,
            # Preserve the exact observed signer native delta: -0.28369609 XNT.
            "preBalances": [10_000_000_000, 0, 0, 0, 0, 0, 0, 0, 0],
            "postBalances": [9_716_303_910, 0, 0, 0, 0, 0, 0, 0, 0],
            "preTokenBalances": [
                {
                    "accountIndex": 1,
                    "mint": REAL_ASSET_MINT,
                    "owner": REAL_SIGNER,
                    "uiTokenAmount": {"amount": "0", "decimals": 6, "uiAmountString": "0"},
                },
                {
                    "accountIndex": 2,
                    "mint": WXNT_MINT,
                    "owner": REAL_POOL_OWNER,
                    "uiTokenAmount": {
                        "amount": "49295383312",
                        "decimals": 9,
                        "uiAmountString": "49.295383312",
                    },
                },
                {
                    "accountIndex": 3,
                    "mint": REAL_ASSET_MINT,
                    "owner": REAL_POOL_OWNER,
                    "uiTokenAmount": {
                        "amount": "1153464457911",
                        "decimals": 6,
                        "uiAmountString": "1153464.457911",
                    },
                },
            ],
            "postTokenBalances": [
                {
                    "accountIndex": 1,
                    "mint": REAL_ASSET_MINT,
                    "owner": REAL_SIGNER,
                    "uiTokenAmount": {
                        "amount": "6561529046",
                        "decimals": 6,
                        "uiAmountString": "6561.529046",
                    },
                },
                {
                    "accountIndex": 2,
                    "mint": WXNT_MINT,
                    "owner": REAL_POOL_OWNER,
                    "uiTokenAmount": {
                        "amount": "49575383312",
                        "decimals": 9,
                        "uiAmountString": "49.575383312",
                    },
                },
                {
                    "accountIndex": 3,
                    "mint": REAL_ASSET_MINT,
                    "owner": REAL_POOL_OWNER,
                    "uiTokenAmount": {
                        "amount": "1146902928865",
                        "decimals": 6,
                        "uiAmountString": "1146902.928865",
                    },
                },
            ],
            "innerInstructions": [],
        },
    }


REAL_SELL_SIGNATURE = "23i8KUeyXgxbwaG41mUpmZPhiKQp6zMLNxWP9pQRoQhDvoAb9K1CLGphCcRCTeCsdsZKxfFLRmR6LY6pd46qUcXv"
REAL_SELL_SIGNER = "3n7NQgbVUfxyzwGJosuv68RHAPa8FE6dWn6c6NzKWC7F"
REAL_POOL_OWNER = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"
REAL_SELL_ASSET = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
REAL_ROUTE_TOKEN = "Du6Z596DwGnfUcMSyRHSBQzNybiQKu8GESVfruEv9Jqr"


def _raw(ui: str, decimals: int) -> str:
    return str(int(Decimal(ui) * (Decimal(10) ** decimals)))


def make_real_multileg_sell_fixture():
    rows = [
        # account, mint, owner, decimals, pre, post
        ("218QnXejKi43U5Zesk4BqVwni2CWnNb2ZSRNLDgC25MX", REAL_ROUTE_TOKEN, REAL_POOL_OWNER, 9, "36008201.184112356", "35852450.455485458"),
        ("2UiaFqt51DqZZLSxeTrMBoVMEtUdJUoaZCMzfVLUhryF", REAL_ROUTE_TOKEN, REAL_SELL_SIGNER, 9, "464.972696983", "620.723425610"),
        ("3Sv2L8uGge261Wx1jTpkpddvV3KNwSC4bhgSMSvqP6sX", WXNT_MINT, REAL_POOL_OWNER, 9, "32.875481714", "33.015567914"),
        ("5M4f9Q5hqhjtzyrhMydbyL3ouC2bUWa4uCV1BYup7nQC", REAL_SELL_ASSET, REAL_POOL_OWNER, 6, "15616.156330", "10578.178372"),
        ("5kdsNGdvbMtWcvPjLPrydnRm4jNECykFGTZFZyHTTUmk", REAL_ROUTE_TOKEN, REAL_POOL_OWNER, 9, "322488.618438483", "478083.596336754"),
        ("7khUrkZN7Y6VgoSR8pASMFjHcKwqdh2cd6NRctXyjSZC", WXNT_MINT, REAL_POOL_OWNER, 9, "49.508806060", "49.295383312"),
        ("9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7", REAL_SELL_ASSET, REAL_POOL_OWNER, 6, "1148428.151623", "1153464.457911"),
        ("AdaHDKtHEDqRgqkXw87HVdiEV69VpvnXZm5egVFVwkjq", WXNT_MINT, REAL_SELL_SIGNER, 9, "15.992995202", "16.066331750"),
        ("B4sFkU5YSUmyuEUebEq4MVqqYxkEs41RSWSzwFPhNt4k", REAL_SELL_ASSET, REAL_SELL_SIGNER, 6, "18.308184", "19.979854"),
    ]
    account_keys = [{"pubkey": REAL_SELL_SIGNER, "signer": True, "writable": True}]
    for account, *_ in rows:
        account_keys.append({"pubkey": account, "signer": False, "writable": True})
    account_keys.extend([
        {"pubkey": "ComputeBudget111111111111111111111111111111", "signer": False, "writable": False},
        {"pubkey": XDEX_MAINNET_OBSERVED_PROGRAM_ID, "signer": False, "writable": False},
        {"pubkey": TOKEN_PROGRAM, "signer": False, "writable": False},
    ])

    pre = []
    post = []
    for index, (_acct, mint, owner, decimals, pre_ui, post_ui) in enumerate(rows, start=1):
        pre.append({
            "accountIndex": index,
            "mint": mint,
            "owner": owner,
            "uiTokenAmount": {"amount": _raw(pre_ui, decimals), "decimals": decimals, "uiAmountString": pre_ui},
        })
        post.append({
            "accountIndex": index,
            "mint": mint,
            "owner": owner,
            "uiTokenAmount": {"amount": _raw(post_ui, decimals), "decimals": decimals, "uiAmountString": post_ui},
        })

    return {
        "slot": 71_125_019,
        "blockTime": 1_786_553_796,
        "transaction": {
            "message": {
                "accountKeys": account_keys,
                "instructions": [
                    {"programId": "ComputeBudget111111111111111111111111111111"},
                    {"programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID},
                    {"programId": TOKEN_PROGRAM},
                ],
            }
        },
        "meta": {
            "err": None,
            "fee": 1_103_001,
            "preBalances": [10_000_000_000] + [0] * (len(account_keys) - 1),
            "postBalances": [9_998_896_999] + [0] * (len(account_keys) - 1),
            "preTokenBalances": pre,
            "postTokenBalances": post,
            "innerInstructions": [],
        },
    }



class X1TransactionSemanticsIntegrationTests(unittest.TestCase):
    def test_real_buy_fixture_promotes(self):
        report = verify_transaction(
            make_real_xdex_buy_fixture(),
            REAL_SIGNATURE,
            "https://rpc.mainnet.x1.xyz",
            expected_side="BUY",
            expected_token_amount=Decimal("6561.5290459999815"),
            expected_native_amount=Decimal("0.28000000000000114"),
        )
        self.assertEqual(report.dex_protocol, "XDEX")
        self.assertEqual(report.inferred_side, "BUY")
        self.assertEqual(report.verification_basis, "EXACT_POOL_LEG_AMOUNTS")
        self.assertEqual(report.verification_level, "PROVIDER_SIDE_ONCHAIN_CONFIRMED")
        self.assertTrue(report.expectation_match)

    def test_real_multileg_sell_fixture_promotes_exact_leg(self):
        report = verify_transaction(
            make_real_multileg_sell_fixture(),
            REAL_SELL_SIGNATURE,
            "https://rpc.mainnet.x1.xyz",
            expected_side="SELL",
            expected_token_amount=Decimal("5036.306287999963"),
            expected_native_amount=Decimal("0.21342274799999927"),
        )
        self.assertEqual(report.dex_protocol, "XDEX")
        self.assertEqual(report.inferred_side, "SELL")
        self.assertEqual(report.inferred_asset_mint, REAL_SELL_ASSET)
        self.assertEqual(report.inferred_quote_amount, Decimal("0.213422748"))
        self.assertEqual(report.verification_basis, "EXACT_POOL_LEG_AMOUNTS")
        self.assertEqual(report.verification_level, "PROVIDER_SIDE_ONCHAIN_CONFIRMED")

    def test_unknown_is_unresolved_not_mismatch(self):
        report = verify_transaction(
            make_real_multileg_sell_fixture(),
            REAL_SELL_SIGNATURE,
            "https://rpc.mainnet.x1.xyz",
            expected_side="SELL",
        )
        self.assertIsNone(report.expectation_match)
        self.assertEqual(report.verification_level, "PROVIDER_SIDE_ONCHAIN_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
