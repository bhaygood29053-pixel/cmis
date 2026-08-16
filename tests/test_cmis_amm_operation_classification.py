import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.amm_operation_classification import (
    ADD_LIQUIDITY,
    REMOVE_LIQUIDITY,
    UNKNOWN,
)
from liquidity_scout.providers.x1.exact_pool_leg_semantics_v14101 import (
    prove_exact_pool_leg_semantics,
)
from liquidity_scout.providers.x1.transaction_semantics import TokenDelta


POOL = "PoolA"
ASSET_MINT = "AssetMint"
COUNTER_MINT = "WrappedXNT"
LP_MINT = "LpMint"
ASSET_ACCOUNT = "AssetVault"
COUNTER_ACCOUNT = "CounterVault"
LP_ACCOUNT = "LpTokenAccount"
USER_ASSET = "UserAsset"
USER_COUNTER = "UserCounter"
OWNER = "VaultAuthority"
USER = "LiquidityProvider"
PROGRAM = "AmmProgram"
END = 100000.0


def family():
    return {
        "asset_account": ASSET_ACCOUNT,
        "counter_account": COUNTER_ACCOUNT,
        "counter_mint": COUNTER_MINT,
        "shared_owner": OWNER,
    }


def coupling_report():
    return {
        "service": "canonical_pool_vault_coupling",
        "version": "1.4.9",
        "canonical_vault_mapping_candidate": family(),
        "families": [
            {
                "family": family(),
                "canonical_pool_vault_coupling_proven": True,
                "canonical_vault_mapping_proven": True,
                "structural_pool_anchor": {
                    "structural_pool_anchor_verified": True,
                    "stable_program_id": PROGRAM,
                    "stable_pool_position": 3,
                },
            }
        ],
        "summary": {"canonical_vault_mapping_proven": True},
    }


def history_entries(extra=None):
    rows = [
        {"signature": "buy-1", "slot": 1, "block_time": 99900.0, "err": None},
        {"signature": "buy-2", "slot": 2, "block_time": 99800.0, "err": None},
        {"signature": "sell-1", "slot": 3, "block_time": 99700.0, "err": None},
        {"signature": "sell-2", "slot": 4, "block_time": 99600.0, "err": None},
    ]
    if extra:
        rows.extend(extra)
    return rows


def scan_report(extra=None):
    return {
        "range_proven": True,
        "integrity_verified": True,
        "coverage_scope": "scan_boundary_reached",
        "entries": history_entries(extra),
    }


def parsed(kind, info):
    return {"parsed": {"type": kind, "info": info}, "program": "spl-token"}


def liquidity_inner(variant):
    if variant.startswith("remove"):
        lp_mint = ASSET_MINT if variant == "remove_reserve_lp_mint" else LP_MINT
        burn_account = "OtherLpAccount" if variant == "remove_burn_outside_amm" else LP_ACCOUNT
        rows = [
            parsed(
                "burn",
                {
                    "account": burn_account,
                    "amount": "6000",
                    "authority": USER,
                    "mint": lp_mint,
                },
            ),
            parsed(
                "transferChecked",
                {
                    "authority": OWNER,
                    "destination": USER_COUNTER,
                    "mint": COUNTER_MINT,
                    "source": COUNTER_ACCOUNT,
                    "tokenAmount": {"amount": "50", "decimals": 9},
                },
            ),
            parsed(
                "transferChecked",
                {
                    "authority": OWNER,
                    "destination": USER_ASSET,
                    "mint": ASSET_MINT,
                    "source": ASSET_ACCOUNT,
                    "tokenAmount": {"amount": "100", "decimals": 9},
                },
            ),
        ]
        if variant == "remove_no_burn":
            rows = rows[1:]
        if variant == "remove_no_counter_transfer":
            rows = [rows[0], rows[2]]
        return rows

    rows = [
        parsed(
            "mintTo",
            {
                "account": LP_ACCOUNT,
                "amount": "6000",
                "mint": LP_MINT,
                "mintAuthority": OWNER,
            },
        ),
        parsed(
            "transferChecked",
            {
                "authority": USER,
                "destination": COUNTER_ACCOUNT,
                "mint": COUNTER_MINT,
                "source": USER_COUNTER,
                "tokenAmount": {"amount": "50", "decimals": 9},
            },
        ),
        parsed(
            "transferChecked",
            {
                "authority": USER,
                "destination": ASSET_ACCOUNT,
                "mint": ASSET_MINT,
                "source": USER_ASSET,
                "tokenAmount": {"amount": "100", "decimals": 9},
            },
        ),
    ]
    if variant == "add_no_mint":
        rows = rows[1:]
    return rows


def tx(signature, variant=None):
    meta = {"err": None}
    if variant and (variant.startswith("remove") or variant.startswith("add")):
        meta["innerInstructions"] = [
            {"index": 2, "instructions": liquidity_inner(variant)}
        ]
    return {
        "signature": signature,
        "meta": meta,
        "test_variant": variant,
        "test_side": "BUY" if signature.startswith("buy") else "SELL",
    }


def occurrence_provider(transaction):
    variant = transaction.get("test_variant")
    if variant and (variant.startswith("remove") or variant.startswith("add")):
        return [
            {
                "program_id": PROGRAM,
                "scope": "outer",
                "group_index": None,
                "instruction_index": 2,
                "accounts": [
                    "x0",
                    OWNER,
                    POOL,
                    LP_ACCOUNT,
                    USER_COUNTER,
                    USER_ASSET,
                    COUNTER_ACCOUNT,
                    ASSET_ACCOUNT,
                    LP_MINT,
                ],
            }
        ]
    side = transaction.get("test_side")
    if side == "SELL":
        accounts = ["x0", "x1", "x2", POOL, "x4", "x5", ASSET_ACCOUNT, COUNTER_ACCOUNT]
    else:
        accounts = ["x0", "x1", "x2", POOL, "x4", "x5", COUNTER_ACCOUNT, ASSET_ACCOUNT]
    return [
        {
            "program_id": PROGRAM,
            "scope": "outer",
            "group_index": None,
            "instruction_index": 2,
            "accounts": accounts,
        }
    ]


def token_row(account, mint, owner, delta_raw):
    pre = 1000000
    post = pre + delta_raw
    return TokenDelta(
        account_index=1 if account == ASSET_ACCOUNT else 2,
        account=account,
        owner=owner,
        mint=mint,
        decimals=9,
        pre_amount_raw=pre,
        post_amount_raw=post,
        delta_raw=delta_raw,
        delta_ui=Decimal(delta_raw) / (Decimal(10) ** 9),
        post_ui=Decimal(post) / (Decimal(10) ** 9),
    )


def delta_provider(transaction):
    variant = transaction.get("test_variant")
    if variant and variant.startswith("remove"):
        asset_delta, counter_delta = -100, -50
    elif variant and variant.startswith("add"):
        asset_delta, counter_delta = 100, 50
    elif transaction.get("test_side") == "SELL":
        asset_delta, counter_delta = 100, -50
    else:
        asset_delta, counter_delta = -100, 50
    return [
        token_row(ASSET_ACCOUNT, ASSET_MINT, OWNER, asset_delta),
        token_row(COUNTER_ACCOUNT, COUNTER_MINT, OWNER, counter_delta),
    ]


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


class Fetcher:
    def __init__(self, variants=None):
        self.variants = variants or {}
        self.calls = []

    def __call__(self, signature, *, rpc_url):
        self.calls.append((signature, rpc_url))
        return tx(signature, self.variants.get(signature))


def run(extra=None, variants=None, operation_classifier=None):
    coupling = Provider(coupling_report())
    scanner = Provider(scan_report(extra))
    fetcher = Fetcher(variants)
    kwargs = {}
    if operation_classifier is not None:
        kwargs["operation_classifier"] = operation_classifier
    result = prove_exact_pool_leg_semantics(
        pool_address=POOL,
        asset_mint=ASSET_MINT,
        end_epoch=END,
        coupling_provider=coupling,
        scanner=scanner,
        fetcher=fetcher,
        occurrence_provider=occurrence_provider,
        delta_provider=delta_provider,
        **kwargs,
    )
    return result, fetcher


class AMMOperationClassificationTests(unittest.TestCase):
    def test_plain_swaps_still_prove_exact_semantics(self):
        result, _ = run()
        self.assertEqual(result["version"], "1.4.10.1")
        self.assertEqual(result["status"], "exact_pool_leg_semantics_proven")
        self.assertEqual(result["operation_counts"]["swaps"], 4)
        self.assertEqual(result["operation_counts"]["unknown"], 0)

    def test_proven_remove_liquidity_is_excluded_from_swap_denominator(self):
        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, fetcher = run(extra, {"remove-1": "remove"})

        self.assertEqual(result["status"], "exact_pool_leg_semantics_proven")
        self.assertTrue(result["summary"]["exact_pool_leg_semantics_proven"])
        self.assertEqual(result["operation_counts"], {
            "recognized": 5,
            "swaps": 4,
            "add_liquidity": 0,
            "remove_liquidity": 1,
            "unknown": 0,
        })
        row = next(r for r in result["transactions"] if r["signature"] == "remove-1")
        self.assertEqual(row["operation_class"], REMOVE_LIQUIDITY)
        self.assertTrue(row["operation_classified"])
        self.assertTrue(row["proven_non_swap"])
        self.assertFalse(row["semantic_resolved"])
        self.assertEqual(row["operation_evidence"]["lp_token_burn"]["mint"], LP_MINT)
        self.assertEqual(len(fetcher.calls), 5)

        one_hour = next(w for w in result["windows"] if w["label"] == "1h")
        self.assertEqual(one_hour["recognized_pool_transaction_count"], 5)
        self.assertEqual(one_hour["proven_swap_transaction_count"], 4)
        self.assertEqual(one_hour["remove_liquidity_transaction_count"], 1)
        self.assertEqual(one_hour["semantic_resolution_ratio"], 1.0)
        self.assertTrue(one_hour["all_recognized_pool_operations_classified"])

    def test_remove_liquidity_without_lp_burn_remains_unknown(self):
        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"remove-1": "remove_no_burn"})
        row = next(r for r in result["transactions"] if r["signature"] == "remove-1")

        self.assertEqual(row["operation_class"], UNKNOWN)
        self.assertIn("unique_lp_token_burn_not_proven", row["operation_rejection_reasons"])
        self.assertEqual(result["status"], "amm_operation_classification_incomplete_or_conflicting")
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_proven"])

    def test_remove_liquidity_requires_both_exact_reserve_transfers(self):
        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"remove-1": "remove_no_counter_transfer"})
        row = next(r for r in result["transactions"] if r["signature"] == "remove-1")

        self.assertEqual(row["operation_class"], UNKNOWN)
        self.assertIn(
            "exact_counter_reserve_out_transfer_not_proven",
            row["operation_rejection_reasons"],
        )

    def test_lp_burn_mint_cannot_be_a_reserve_mint(self):
        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"remove-1": "remove_reserve_lp_mint"})
        row = next(r for r in result["transactions"] if r["signature"] == "remove-1")
        self.assertEqual(row["operation_class"], UNKNOWN)
        self.assertIn("unique_lp_token_burn_not_proven", row["operation_rejection_reasons"])

    def test_lp_burn_account_must_participate_in_amm_instruction(self):
        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"remove-1": "remove_burn_outside_amm"})
        row = next(r for r in result["transactions"] if r["signature"] == "remove-1")
        self.assertEqual(row["operation_class"], UNKNOWN)

    def test_proven_add_liquidity_is_excluded_from_swap_denominator(self):
        extra = [{"signature": "add-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"add-1": "add"})
        row = next(r for r in result["transactions"] if r["signature"] == "add-1")

        self.assertEqual(result["status"], "exact_pool_leg_semantics_proven")
        self.assertEqual(row["operation_class"], ADD_LIQUIDITY)
        self.assertTrue(row["proven_non_swap"])
        self.assertEqual(result["operation_counts"]["add_liquidity"], 1)
        self.assertEqual(result["operation_counts"]["unknown"], 0)

    def test_add_liquidity_without_lp_mint_remains_unknown(self):
        extra = [{"signature": "add-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"add-1": "add_no_mint"})
        row = next(r for r in result["transactions"] if r["signature"] == "add-1")

        self.assertEqual(row["operation_class"], UNKNOWN)
        self.assertIn("unique_lp_token_mint_not_proven", row["operation_rejection_reasons"])
        self.assertFalse(result["summary"]["all_recognized_pool_operations_classified"])

    def test_classifier_exception_fails_closed(self):
        def broken(*args, **kwargs):
            raise RuntimeError("boom")

        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"remove-1": "remove"}, operation_classifier=broken)
        row = next(r for r in result["transactions"] if r["signature"] == "remove-1")

        self.assertEqual(row["operation_class"], UNKNOWN)
        self.assertTrue(
            any(reason.startswith("operation_classifier_exception") for reason in row["operation_rejection_reasons"])
        )
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_proven"])

    def test_operation_layer_never_promotes_execution(self):
        extra = [{"signature": "remove-1", "slot": 5, "block_time": 99500.0, "err": None}]
        result, _ = run(extra, {"remove-1": "remove"})

        self.assertFalse(result["summary"]["canonical_vault_mapping_promoted"])
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_promoted"])


if __name__ == "__main__":
    unittest.main()
