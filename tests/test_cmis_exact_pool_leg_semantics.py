import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.exact_pool_leg_semantics import (
    prove_exact_pool_leg_semantics,
)
from liquidity_scout.providers.x1.transaction_semantics import TokenDelta


POOL = "PoolA"
ASSET_MINT = "AssetMint"
COUNTER_MINT = "WrappedXNT"
ASSET_ACCOUNT = "AssetVault"
COUNTER_ACCOUNT = "CounterVault"
OWNER = "VaultAuthority"
PROGRAM = "AmmProgram"
END = 100000.0


def family():
    return {
        "asset_account": ASSET_ACCOUNT,
        "counter_account": COUNTER_ACCOUNT,
        "counter_mint": COUNTER_MINT,
        "shared_owner": OWNER,
    }


def coupling_report(*, proven=True, program=PROGRAM, pool_position=3):
    return {
        "service": "canonical_pool_vault_coupling",
        "version": "1.4.9",
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET_MINT,
        "status": (
            "canonical_pool_vault_coupling_proven"
            if proven
            else "no_pool_vault_coupling_proven"
        ),
        "canonical_vault_mapping_candidate": family() if proven else None,
        "families": (
            [
                {
                    "family": family(),
                    "canonical_pool_vault_coupling_proven": True,
                    "canonical_vault_mapping_proven": True,
                    "structural_pool_anchor": {
                        "structural_pool_anchor_verified": True,
                        "stable_program_id": program,
                        "stable_pool_position": pool_position,
                    },
                }
            ]
            if proven
            else []
        ),
        "summary": {
            "canonical_vault_mapping_proven": proven,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
        },
        "errors": [],
    }


def history_entries(*, include_failed=False):
    rows = [
        {"signature": "buy-1", "slot": 1, "block_time": 99900.0, "err": None},
        {"signature": "buy-2", "slot": 2, "block_time": 99800.0, "err": None},
        {"signature": "sell-1", "slot": 3, "block_time": 99700.0, "err": None},
        {"signature": "sell-2", "slot": 4, "block_time": 99600.0, "err": None},
    ]
    if include_failed:
        rows.append(
            {"signature": "failed-chain", "slot": 5, "block_time": 99500.0, "err": {"x": 1}}
        )
    return rows


def scan_report(*, proven=True, entries=None):
    return {
        "range_proven": proven,
        "integrity_verified": proven,
        "entries": history_entries() if entries is None else entries,
        "coverage_scope": "scan_boundary_reached" if proven else "incomplete",
    }


def tx(signature, *, side=None, variant=None):
    return {
        "signature": signature,
        "meta": {"err": None},
        "test_side": side or ("BUY" if signature.startswith("buy") else "SELL"),
        "test_variant": variant,
    }


def occurrence_provider(transaction):
    side = transaction.get("test_side")
    variant = transaction.get("test_variant")
    if variant == "non_pool":
        return [{"program_id": PROGRAM, "accounts": ["OtherPool", ASSET_ACCOUNT, COUNTER_ACCOUNT]}]
    if variant == "missing_vault":
        return [{"program_id": PROGRAM, "accounts": ["x0", "x1", "x2", POOL, "x4", "x5", COUNTER_ACCOUNT]}]
    if variant == "wrong_program":
        return [{"program_id": "OtherProgram", "accounts": ["x0", "x1", "x2", POOL, "x4", "x5", COUNTER_ACCOUNT, ASSET_ACCOUNT]}]
    if variant == "wrong_pool_position":
        return [{"program_id": PROGRAM, "accounts": [POOL, "x1", "x2", "x3", "x4", "x5", COUNTER_ACCOUNT, ASSET_ACCOUNT]}]
    if variant == "ambiguous":
        return [
            {"program_id": PROGRAM, "accounts": ["x0", "x1", "x2", POOL, "x4", "x5", COUNTER_ACCOUNT, ASSET_ACCOUNT]},
            {"program_id": PROGRAM, "accounts": ["x0", "x1", "x2", POOL, "x4", ASSET_ACCOUNT, COUNTER_ACCOUNT]},
        ]
    if variant == "drift":
        return [{"program_id": PROGRAM, "accounts": ["x0", "x1", "x2", POOL, "x4", ASSET_ACCOUNT, "x6", COUNTER_ACCOUNT]}]
    if side == "SELL":
        return [{"program_id": PROGRAM, "accounts": ["x0", "x1", "x2", POOL, "x4", "x5", ASSET_ACCOUNT, COUNTER_ACCOUNT]}]
    return [{"program_id": PROGRAM, "accounts": ["x0", "x1", "x2", POOL, "x4", "x5", COUNTER_ACCOUNT, ASSET_ACCOUNT]}]


def token_row(account, mint, owner, delta_raw):
    decimals = 9
    pre = 1000000
    post = pre + delta_raw
    return TokenDelta(
        account_index=1 if account == ASSET_ACCOUNT else 2,
        account=account,
        owner=owner,
        mint=mint,
        decimals=decimals,
        pre_amount_raw=pre,
        post_amount_raw=post,
        delta_raw=delta_raw,
        delta_ui=Decimal(delta_raw) / (Decimal(10) ** decimals),
        post_ui=Decimal(post) / (Decimal(10) ** decimals),
    )


def delta_provider(transaction):
    side = transaction.get("test_side")
    variant = transaction.get("test_variant")
    if side == "BUY":
        asset_delta, counter_delta = -100, 50
    else:
        asset_delta, counter_delta = 100, -50

    asset_mint = "WrongAssetMint" if variant == "asset_mint" else ASSET_MINT
    counter_mint = "WrongCounterMint" if variant == "counter_mint" else COUNTER_MINT
    asset_owner = "WrongOwner" if variant == "asset_owner" else OWNER
    counter_owner = "WrongOwner" if variant == "counter_owner" else OWNER

    if variant == "same_sign":
        asset_delta, counter_delta = 100, 50
    if variant == "missing_asset_delta":
        return [token_row(COUNTER_ACCOUNT, counter_mint, counter_owner, counter_delta)]
    if variant == "missing_counter_delta":
        return [token_row(ASSET_ACCOUNT, asset_mint, asset_owner, asset_delta)]

    return [
        token_row(ASSET_ACCOUNT, asset_mint, asset_owner, asset_delta),
        token_row(COUNTER_ACCOUNT, counter_mint, counter_owner, counter_delta),
    ]


class Provider:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return self.value


class Fetcher:
    def __init__(self, variants=None, errors=None, sides=None):
        self.variants = variants or {}
        self.errors = errors or {}
        self.sides = sides or {}
        self.calls = []

    def __call__(self, signature, *, rpc_url):
        self.calls.append((signature, rpc_url))
        if signature in self.errors:
            raise self.errors[signature]
        return tx(
            signature,
            side=self.sides.get(signature),
            variant=self.variants.get(signature),
        )


def run(
    *,
    coupling=None,
    scan=None,
    fetcher=None,
    occurrence=occurrence_provider,
    deltas=delta_provider,
):
    coupling_provider = Provider(coupling or coupling_report())
    scanner = Provider(scan or scan_report())
    fetcher = fetcher or Fetcher()
    result = prove_exact_pool_leg_semantics(
        pool_address=POOL,
        asset_mint=ASSET_MINT,
        end_epoch=END,
        coupling_provider=coupling_provider,
        scanner=scanner,
        fetcher=fetcher,
        occurrence_provider=occurrence,
        delta_provider=deltas,
    )
    return result, coupling_provider, scanner, fetcher


class ExactPoolLegSemanticsTests(unittest.TestCase):
    def test_clean_bidirectional_canonical_reserve_flow_proves_semantics(self):
        result, _, _, _ = run()

        self.assertEqual(result["status"], "exact_pool_leg_semantics_proven")
        self.assertTrue(result["summary"]["canonical_vault_mapping_proven"])
        self.assertTrue(result["summary"]["buy_semantics_proven"])
        self.assertTrue(result["summary"]["sell_semantics_proven"])
        self.assertTrue(result["summary"]["exact_pool_leg_semantics_proven"])
        self.assertEqual(result["directions"][0]["side"], "BUY")
        self.assertEqual(
            result["directions"][0]["stable_structural_fingerprint"]["asset_position"],
            7,
        )
        self.assertEqual(
            result["directions"][1]["stable_structural_fingerprint"]["asset_position"],
            6,
        )

    def test_buy_and_sell_semantics_are_defined_from_reserve_delta_signs(self):
        result, _, _, _ = run()
        resolved = {
            row["signature"]: row
            for row in result["transactions"]
            if row.get("semantic_resolved")
        }

        self.assertEqual(resolved["buy-1"]["reserve_flow"]["asset_reserve"], "OUT")
        self.assertEqual(resolved["buy-1"]["reserve_flow"]["counter_reserve"], "IN")
        self.assertEqual(resolved["sell-1"]["reserve_flow"]["asset_reserve"], "IN")
        self.assertEqual(resolved["sell-1"]["reserve_flow"]["counter_reserve"], "OUT")

    def test_mapping_must_be_proven_before_semantics_scan(self):
        result, _, scanner, fetcher = run(coupling=coupling_report(proven=False))

        self.assertEqual(result["status"], "canonical_vault_mapping_unproven")
        self.assertEqual(scanner.calls, [])
        self.assertEqual(fetcher.calls, [])
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_proven"])

    def test_coupling_provider_exception_is_explicit(self):
        broken = Provider(error=RuntimeError("coupling unavailable"))
        result = prove_exact_pool_leg_semantics(
            pool_address=POOL,
            asset_mint=ASSET_MINT,
            end_epoch=END,
            coupling_provider=broken,
        )

        self.assertEqual(result["status"], "canonical_vault_mapping_unavailable")
        self.assertEqual(result["errors"][0]["stage"], "canonical_pool_vault_coupling")

    def test_history_scan_exception_is_explicit(self):
        scanner = Provider(error=RuntimeError("history unavailable"))
        result = prove_exact_pool_leg_semantics(
            pool_address=POOL,
            asset_mint=ASSET_MINT,
            end_epoch=END,
            coupling_provider=Provider(coupling_report()),
            scanner=scanner,
        )

        self.assertEqual(result["status"], "history_scan_unavailable")
        self.assertEqual(result["errors"][0]["stage"], "history_scan")

    def test_unproven_24h_scan_blocks_semantics(self):
        result, _, _, _ = run(scan=scan_report(proven=False))

        self.assertEqual(result["status"], "history_range_unproven")
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_proven"])

    def test_transaction_fetch_failure_fails_closed(self):
        fetcher = Fetcher(errors={"buy-1": RuntimeError("rpc unavailable")})
        result, _, _, _ = run(fetcher=fetcher)

        self.assertEqual(result["status"], "transaction_evidence_incomplete")
        self.assertFalse(result["summary"]["all_successful_history_transactions_fetched"])
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_proven"])

    def test_same_sign_canonical_reserve_deltas_are_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "same_sign"})
        result, _, _, _ = run(fetcher=fetcher)

        self.assertEqual(result["status"], "pool_leg_semantics_incomplete_or_conflicting")
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")
        self.assertIn("canonical_reserve_deltas_not_opposite_nonzero", row["rejection_reasons"])

    def test_asset_mint_mismatch_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "asset_mint"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn("canonical_asset_mint_mismatch", row["rejection_reasons"])
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_proven"])

    def test_counter_mint_mismatch_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "counter_mint"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn("canonical_counter_mint_mismatch", row["rejection_reasons"])

    def test_asset_authority_mismatch_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "asset_owner"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn("canonical_asset_authority_mismatch", row["rejection_reasons"])

    def test_counter_authority_mismatch_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "counter_owner"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn("canonical_counter_authority_mismatch", row["rejection_reasons"])

    def test_missing_canonical_delta_row_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "missing_asset_delta"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn(
            "canonical_asset_delta_row_missing_or_ambiguous",
            row["rejection_reasons"],
        )

    def test_missing_canonical_vault_from_recognized_instruction_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "missing_vault"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn(
            "canonical_vaults_not_coupled_in_expected_program_instruction",
            row["rejection_reasons"],
        )

    def test_ambiguous_instruction_fingerprint_is_rejected(self):
        fetcher = Fetcher(variants={"buy-1": "ambiguous"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn("canonical_instruction_fingerprint_ambiguous", row["rejection_reasons"])

    def test_pool_position_must_match_v1_4_9_anchor(self):
        fetcher = Fetcher(variants={"buy-1": "wrong_pool_position"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn("canonical_pool_position_mismatch", row["rejection_reasons"])

    def test_program_must_match_v1_4_9_anchor(self):
        fetcher = Fetcher(variants={"buy-1": "wrong_program"})
        result, _, _, _ = run(fetcher=fetcher)
        row = next(item for item in result["transactions"] if item["signature"] == "buy-1")

        self.assertIn(
            "canonical_vaults_not_coupled_in_expected_program_instruction",
            row["rejection_reasons"],
        )

    def test_direction_specific_fingerprint_drift_blocks_bidirectional_proof(self):
        fetcher = Fetcher(variants={"buy-2": "drift"})
        result, _, _, _ = run(fetcher=fetcher)

        self.assertEqual(result["status"], "bidirectional_semantics_unproven")
        buy = next(item for item in result["directions"] if item["side"] == "BUY")
        self.assertFalse(buy["structural_fingerprint_stable"])
        self.assertFalse(buy["side_semantics_proven"])

    def test_one_sided_activity_does_not_prove_exact_semantics(self):
        fetcher = Fetcher(
            sides={"sell-1": "BUY", "sell-2": "BUY"}
        )
        result, _, _, _ = run(fetcher=fetcher)

        self.assertEqual(result["status"], "bidirectional_semantics_unproven")
        self.assertTrue(result["summary"]["buy_semantics_proven"])
        self.assertFalse(result["summary"]["sell_semantics_proven"])

    def test_recognized_pool_transactions_must_exist_in_every_required_window(self):
        entries = [
            {"signature": "buy-1", "slot": 1, "block_time": 90000.0, "err": None},
            {"signature": "buy-2", "slot": 2, "block_time": 89900.0, "err": None},
            {"signature": "sell-1", "slot": 3, "block_time": 89800.0, "err": None},
            {"signature": "sell-2", "slot": 4, "block_time": 89700.0, "err": None},
        ]
        result, _, _, _ = run(scan=scan_report(entries=entries))

        self.assertEqual(result["status"], "pool_leg_semantics_incomplete_or_conflicting")
        one_hour = next(item for item in result["windows"] if item["label"] == "1h")
        self.assertEqual(one_hour["recognized_pool_transaction_count"], 0)
        self.assertFalse(one_hour["all_recognized_pool_transactions_semantically_resolved"])

    def test_failed_chain_history_entry_does_not_define_swap_semantics(self):
        result, _, _, _ = run(scan=scan_report(entries=history_entries(include_failed=True)))

        self.assertEqual(result["status"], "exact_pool_leg_semantics_proven")
        failed = next(item for item in result["transactions"] if item["signature"] == "failed-chain")
        self.assertFalse(failed["chain_succeeded"])
        self.assertFalse(failed["recognized_pool_transaction"])

    def test_semantics_proof_does_not_promote_mapping_or_execution(self):
        result, _, _, _ = run()
        summary = result["summary"]

        self.assertTrue(summary["exact_pool_leg_semantics_proven"])
        self.assertFalse(summary["canonical_vault_mapping_promoted"])
        self.assertFalse(summary["exact_pool_leg_semantics_promoted"])

    def test_scans_only_one_24h_range_then_derives_nested_windows(self):
        result, _, scanner, fetcher = run()

        self.assertEqual(result["status"], "exact_pool_leg_semantics_proven")
        self.assertEqual(len(scanner.calls), 1)
        args, kwargs = scanner.calls[0]
        self.assertEqual(args[0], POOL)
        self.assertEqual(kwargs["start_epoch"], END - 86400)
        self.assertEqual(len(fetcher.calls), 4)


if __name__ == "__main__":
    unittest.main()
