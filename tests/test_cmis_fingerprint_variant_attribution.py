import unittest
from dataclasses import dataclass
from decimal import Decimal

import liquidity_scout.providers.x1.fingerprint_variant_attribution as mod


ASSET = "asset-mint"
COUNTER = "counter-mint"
POOL = "pool-address"
ASSET_ACCOUNT = "asset-vault"
COUNTER_ACCOUNT = "counter-vault"
OWNER = "pool-owner"
PROGRAM = "xdex"


@dataclass
class Row:
    account: str
    mint: str
    owner: str
    delta_ui: Decimal


def history(signature, slot, block_time, err=None):
    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "err": err,
    }


def make_tx(signature, direction="SELL", layout=(0, 1, 2), scope="outer"):
    if direction == "BUY":
        asset_delta = Decimal("-10")
        counter_delta = Decimal("10")
    elif direction == "SELL":
        asset_delta = Decimal("10")
        counter_delta = Decimal("-10")
    else:
        asset_delta = Decimal("10")
        counter_delta = Decimal("10")

    return {
        "signature": signature,
        "_rows": [
            Row(ASSET_ACCOUNT, ASSET, OWNER, asset_delta),
            Row(COUNTER_ACCOUNT, COUNTER, OWNER, counter_delta),
        ],
        "_occurrences": [
            {
                "program_id": PROGRAM,
                "scope": scope,
                "group_index": None if scope == "outer" else 0,
                "instruction_index": 0,
                "accounts": [
                    [POOL, ASSET_ACCOUNT, COUNTER_ACCOUNT][i]
                    for i in layout
                ],
            }
        ],
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
    def __init__(self, txs, fail=None):
        self.txs = txs
        self.fail = set(fail or [])
        self.calls = []

    def __call__(self, signature, *, rpc_url):
        self.calls.append(signature)
        if signature in self.fail:
            raise RuntimeError("unavailable")
        return self.txs.get(signature)


def baseline_report(stable=False):
    return {
        "range_proven": True,
        "integrity_verified": True,
        "candidate_pairs": [
            {
                "asset_account": ASSET_ACCOUNT,
                "asset_mint": ASSET,
                "counter_account": COUNTER_ACCOUNT,
                "counter_mint": COUNTER,
                "shared_owner": OWNER,
                "recognized_pool_instruction_transaction_ratio": 1.0,
                "opposite_direction_ratio": 1.0,
                "stable_directional_pair_candidate": stable,
            }
        ],
        "summary": {
            "stable_directional_pair_candidate_count": int(stable),
        },
    }


def baseline_none(**kwargs):
    return {
        "range_proven": True,
        "integrity_verified": True,
        "candidate_pairs": [],
        "summary": {
            "stable_directional_pair_candidate_count": 0,
        },
    }


def baseline_unstable(**kwargs):
    return baseline_report(stable=False)


def baseline_stable(**kwargs):
    return baseline_report(stable=True)


def run(txs, baseline=baseline_unstable, failed=None, fetch_fail=None):
    entries = []
    for index, signature in enumerate(txs):
        entries.append(
            history(
                signature,
                10 + index,
                170 + index,
                err=(
                    {"InstructionError": [0, "x"]}
                    if failed and signature in failed
                    else None
                ),
            )
        )

    original_deltas = mod.compute_token_deltas
    original_occ = mod.collect_recognized_amm_instruction_occurrences
    try:
        mod.compute_token_deltas = lambda tx: tx["_rows"]
        mod.collect_recognized_amm_instruction_occurrences = (
            lambda tx: tx["_occurrences"]
        )
        return mod.attribute_pool_fingerprint_variants(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=500,
            baseline_correlator=baseline,
            scanner=FakeScanner(entries),
            fetcher=FakeFetcher(txs, fail=fetch_fail),
        )
    finally:
        mod.compute_token_deltas = original_deltas
        mod.collect_recognized_amm_instruction_occurrences = original_occ


class FingerprintVariantAttributionTests(unittest.TestCase):
    def test_identifies_single_sell_outlier_signature(self):
        txs = {}
        for i in range(5):
            txs[f"s{i}"] = make_tx(f"s{i}", "SELL", (0, 2, 1))
        txs["outlier"] = make_tx(
            "outlier", "SELL", (0, 1, 2)
        )
        result = run(txs)
        sell = next(
            item for item in result["directions"]
            if item["direction"] == "SELL"
        )
        self.assertEqual(sell["dominant_fingerprint_count"], 5)
        self.assertEqual(sell["transaction_count"], 6)
        self.assertEqual(
            sell["outlier_signatures"], ["outlier"]
        )

    def test_does_not_call_outlier_legitimate(self):
        txs = {
            "s1": make_tx("s1", "SELL", (0, 2, 1)),
            "s2": make_tx("s2", "SELL", (0, 2, 1)),
            "s3": make_tx("s3", "SELL", (0, 1, 2)),
        }
        result = run(txs)
        sell = result["directions"][0]
        self.assertFalse(sell["variant_legitimacy_proven"])
        self.assertEqual(
            sell["outliers"][0]["classification"],
            "unresolved_variant",
        )

    def test_reports_layout_difference(self):
        txs = {
            "s1": make_tx("s1", "SELL", (0, 2, 1)),
            "s2": make_tx("s2", "SELL", (0, 2, 1)),
            "s3": make_tx("s3", "SELL", (0, 1, 2)),
        }
        result = run(txs)
        sell = result["directions"][0]
        variant = next(
            item for item in sell["fingerprint_distribution"]
            if not item["is_dominant"]
        )
        diff = variant["difference_from_dominant"]
        self.assertTrue(diff["asset_position_changed"])
        self.assertTrue(diff["counter_position_changed"])

    def test_buy_and_sell_are_attributed_separately(self):
        txs = {
            "b1": make_tx("b1", "BUY", (0, 1, 2)),
            "b2": make_tx("b2", "BUY", (0, 1, 2)),
            "s1": make_tx("s1", "SELL", (0, 2, 1)),
            "s2": make_tx("s2", "SELL", (0, 2, 1)),
        }
        result = run(txs)
        self.assertEqual(len(result["directions"]), 2)
        self.assertTrue(all(
            item["outlier_signature_count"] == 0
            for item in result["directions"]
        ))

    def test_repeated_variant_is_observed_but_not_proven(self):
        txs = {
            "s1": make_tx("s1", "SELL", (0, 2, 1)),
            "s2": make_tx("s2", "SELL", (0, 2, 1)),
            "s3": make_tx("s3", "SELL", (0, 2, 1)),
            "v1": make_tx("v1", "SELL", (0, 1, 2)),
            "v2": make_tx("v2", "SELL", (0, 1, 2)),
        }
        result = run(txs)
        sell = result["directions"][0]
        self.assertTrue(
            sell["repeated_non_dominant_variant_observed"]
        )
        self.assertFalse(sell["variant_legitimacy_proven"])

    def test_no_candidate_pair_returns_safely(self):
        result = mod.attribute_pool_fingerprint_variants(
            pool_address=POOL,
            asset_mint=ASSET,
            start_epoch=100,
            end_epoch=500,
            baseline_correlator=baseline_none,
            scanner=FakeScanner([]),
            fetcher=FakeFetcher({}),
        )
        self.assertEqual(result["status"], "no_candidate_pair")
        self.assertIsNone(result["leading_pair"])

    def test_failed_history_transaction_is_not_fetched(self):
        txs = {
            "failed": make_tx("failed"),
            "good": make_tx("good"),
        }
        result = run(txs, failed={"failed"})
        self.assertEqual(
            result["failed_history_transaction_count"], 1
        )

    def test_fetch_failure_counted(self):
        txs = {
            "bad": make_tx("bad"),
            "good": make_tx("good"),
        }
        result = run(txs, fetch_fail={"bad"})
        self.assertEqual(result["fetch_unavailable_count"], 1)

    def test_baseline_can_be_unstable_and_still_attributed(self):
        txs = {
            "s1": make_tx("s1"),
            "s2": make_tx("s2"),
        }
        result = run(txs, baseline=baseline_unstable)
        self.assertFalse(
            result["leading_pair"][
                "baseline_stable_directional_pair_candidate"
            ]
        )
        self.assertEqual(
            result["summary"]["attributed_pair_transaction_count"], 2
        )

    def test_promotion_flags_always_false(self):
        txs = {
            "s1": make_tx("s1"),
            "s2": make_tx("s2"),
        }
        result = run(txs, baseline=baseline_stable)
        summary = result["summary"]
        self.assertFalse(summary["variant_legitimacy_proven"])
        self.assertFalse(summary["canonical_vault_mapping_proven"])
        self.assertFalse(
            summary["canonical_vault_mapping_promoted"]
        )
        self.assertFalse(
            summary["exact_pool_leg_semantics_promoted"]
        )


if __name__ == "__main__":
    unittest.main()
