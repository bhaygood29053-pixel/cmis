import unittest

from liquidity_scout.providers.x1.canonical_vault_family_qualification import (
    qualify_canonical_vault_family,
)


POOL = "PoolA"
ASSET_MINT = "AssetMint"
OWNER = "VaultAuthority"


def family(name="A", *, recurrent=True, conflict=False):
    return {
        "family": {
            "asset_account": f"{name}-asset-account",
            "counter_account": f"{name}-counter-account",
            "counter_mint": f"{name}-counter-mint",
            "shared_owner": OWNER,
        },
        "recurrent_pair_family_observed": recurrent,
        "structural_layout_conflict_observed": conflict,
    }


def family_report(families, *, ranges=True):
    return {
        "service": "vault_pair_family_attribution",
        "version": "1.4.7",
        "families": families,
        "summary": {
            "all_requested_window_ranges_proven": ranges,
        },
    }


def token_account(account, mint, authority=OWNER, *, verified=True, exists=True):
    return {
        "account": account,
        "account_exists": exists,
        "program_owner": "TokenProgram111",
        "parsed_type": "account",
        "mint": mint if exists else None,
        "token_authority": authority if exists else None,
        "raw_amount": "100" if exists else None,
        "decimals": 6 if exists else None,
        "ui_amount_string": "0.0001" if exists else None,
        "identity_verified": verified if exists else False,
        "source": "test rpc",
    }


class FamilyProvider:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.report


class TokenProvider:
    def __init__(self, records=None, errors=None):
        self.records = records or {}
        self.errors = errors or {}
        self.calls = []

    def __call__(self, account):
        self.calls.append(account)
        if account in self.errors:
            raise self.errors[account]
        return self.records.get(account)


def qualifying_records(*names):
    records = {}
    for name in names:
        records[f"{name}-asset-account"] = token_account(
            f"{name}-asset-account",
            ASSET_MINT,
        )
        records[f"{name}-counter-account"] = token_account(
            f"{name}-counter-account",
            f"{name}-counter-mint",
        )
    return records


def run(report, records=None, errors=None):
    family_provider = FamilyProvider(report)
    token_provider = TokenProvider(records, errors)
    result = qualify_canonical_vault_family(
        pool_address=POOL,
        asset_mint=ASSET_MINT,
        end_epoch=100000,
        family_provider=family_provider,
        token_account_provider=token_provider,
    )
    return result, family_provider, token_provider


class CanonicalVaultFamilyQualificationTests(unittest.TestCase):
    def test_single_recurrent_family_with_matching_rpc_identity_qualifies(self):
        result, _, token_provider = run(
            family_report([family("A")]),
            qualifying_records("A"),
        )

        self.assertEqual(result["status"], "qualified_candidate_observed")
        self.assertEqual(result["qualified_family_count"], 1)
        self.assertTrue(result["summary"]["canonical_vault_family_qualified"])
        self.assertEqual(
            result["canonical_vault_family_candidate"]["asset_account"],
            "A-asset-account",
        )
        self.assertEqual(
            token_provider.calls,
            ["A-asset-account", "A-counter-account"],
        )

    def test_asset_mint_mismatch_rejects_family(self):
        records = qualifying_records("A")
        records["A-asset-account"] = token_account(
            "A-asset-account",
            "WrongAssetMint",
        )
        result, _, _ = run(family_report([family("A")]), records)

        self.assertEqual(result["status"], "no_qualified_family")
        self.assertIn(
            "asset_mint_mismatch",
            result["families"][0]["rejection_reasons"],
        )

    def test_counter_mint_mismatch_rejects_family(self):
        records = qualifying_records("A")
        records["A-counter-account"] = token_account(
            "A-counter-account",
            "WrongCounterMint",
        )
        result, _, _ = run(family_report([family("A")]), records)

        self.assertIn(
            "counter_mint_mismatch",
            result["families"][0]["rejection_reasons"],
        )

    def test_asset_authority_mismatch_rejects_family(self):
        records = qualifying_records("A")
        records["A-asset-account"] = token_account(
            "A-asset-account",
            ASSET_MINT,
            authority="WrongAuthority",
        )
        result, _, _ = run(family_report([family("A")]), records)

        self.assertIn(
            "asset_authority_mismatch",
            result["families"][0]["rejection_reasons"],
        )

    def test_counter_authority_mismatch_rejects_family(self):
        records = qualifying_records("A")
        records["A-counter-account"] = token_account(
            "A-counter-account",
            "A-counter-mint",
            authority="WrongAuthority",
        )
        result, _, _ = run(family_report([family("A")]), records)

        self.assertIn(
            "counter_authority_mismatch",
            result["families"][0]["rejection_reasons"],
        )

    def test_missing_rpc_account_fails_closed(self):
        records = qualifying_records("A")
        records["A-counter-account"] = token_account(
            "A-counter-account",
            "A-counter-mint",
            exists=False,
        )
        result, _, _ = run(family_report([family("A")]), records)

        reasons = result["families"][0]["rejection_reasons"]
        self.assertIn("counter_account_missing", reasons)
        self.assertIn("counter_identity_unverified", reasons)
        self.assertFalse(result["summary"]["canonical_vault_family_qualified"])

    def test_structural_conflict_rejects_without_rpc_lookup(self):
        result, _, token_provider = run(
            family_report([family("A", conflict=True)]),
            qualifying_records("A"),
        )

        self.assertIn(
            "structural_layout_conflict",
            result["families"][0]["rejection_reasons"],
        )
        self.assertEqual(token_provider.calls, [])

    def test_non_recurrent_family_rejects_without_rpc_lookup(self):
        result, _, token_provider = run(
            family_report([family("A", recurrent=False)]),
            qualifying_records("A"),
        )

        self.assertIn(
            "family_not_recurrent",
            result["families"][0]["rejection_reasons"],
        )
        self.assertEqual(token_provider.calls, [])

    def test_unproven_history_range_blocks_qualification(self):
        result, _, token_provider = run(
            family_report([family("A")], ranges=False),
            qualifying_records("A"),
        )

        self.assertEqual(result["status"], "insufficient_family_evidence")
        self.assertIn(
            "history_range_unproven",
            result["families"][0]["rejection_reasons"],
        )
        self.assertEqual(token_provider.calls, [])

    def test_two_qualified_families_remain_ambiguous(self):
        result, _, _ = run(
            family_report([family("A"), family("B")]),
            qualifying_records("A", "B"),
        )

        self.assertEqual(result["status"], "ambiguous_qualified_families")
        self.assertEqual(result["qualified_family_count"], 2)
        self.assertIsNone(result["canonical_vault_family_candidate"])
        self.assertFalse(result["summary"]["unique_qualified_family"])
        self.assertFalse(result["summary"]["canonical_vault_family_qualified"])

    def test_rpc_exception_is_explicit_and_fails_closed(self):
        records = qualifying_records("A")
        errors = {"A-asset-account": RuntimeError("rpc unavailable")}
        result, _, _ = run(
            family_report([family("A")]),
            records,
            errors,
        )

        self.assertEqual(result["status"], "no_qualified_family")
        self.assertIn(
            "asset_rpc_evidence_unavailable",
            result["families"][0]["rejection_reasons"],
        )
        self.assertEqual(result["errors"][0]["stage"], "asset_token_account")

    def test_family_provider_exception_is_explicit(self):
        def broken_provider(**_kwargs):
            raise RuntimeError("history unavailable")

        result = qualify_canonical_vault_family(
            pool_address=POOL,
            asset_mint=ASSET_MINT,
            end_epoch=100000,
            family_provider=broken_provider,
            token_account_provider=lambda _account: None,
        )

        self.assertEqual(result["status"], "family_attribution_unavailable")
        self.assertFalse(result["summary"]["family_attribution_available"])
        self.assertEqual(result["errors"][0]["stage"], "family_attribution")

    def test_promotion_flags_remain_false_when_family_qualifies(self):
        result, _, _ = run(
            family_report([family("A")]),
            qualifying_records("A"),
        )
        summary = result["summary"]

        self.assertTrue(summary["canonical_vault_family_qualified"])
        self.assertFalse(summary["canonical_vault_mapping_proven"])
        self.assertFalse(summary["canonical_vault_mapping_promoted"])
        self.assertFalse(summary["exact_pool_leg_semantics_promoted"])
        self.assertFalse(result["families"][0]["canonical_family_proven"])
        self.assertFalse(result["families"][0]["canonical_family_promoted"])


if __name__ == "__main__":
    unittest.main()
