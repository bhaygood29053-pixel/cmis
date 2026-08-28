import unittest

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
from liquidity_scout.providers.solana.market_verification import (
    verify_jupiter_vs_dexscreener_prices,
    verify_jupiter_vs_pyth_price,
)


MINT = "Mint111"


def jupiter(price="1.00"):
    return {
        "chain": "solana",
        "source": "jupiter_price_v3",
        "mint": MINT,
        "price_available": True,
        "usd_price": price,
        "currency": "USD",
        "block_id": 123,
        "decimals": 6,
        "freshness_verified": False,
    }


def pair(address, price, *, role="base", subject=MINT):
    return {
        "pair_address": address,
        "dex_id": "raydium",
        "requested_mint_role": role,
        "price_subject_address": subject,
        "price_is_for_requested_mint": role == "base" and subject == MINT,
        "price_usd": price,
    }


def pyth(price="1.00", *, mint=MINT, publish_time=1000):
    return {
        "chain": "solana",
        "source": "pyth_core_solana_push",
        "mint": mint,
        "mapping_verified": True,
        "price_available": True,
        "price_integrity_verified": True,
        "fact_time_verified": True,
        "price_usd": price,
        "publish_time_unix": publish_time,
        "quote_symbol": "USD",
    }


def dexscreener(*pairs):
    return {
        "chain": "solana",
        "source": "dexscreener_token_pairs_v1",
        "mint": MINT,
        "pairs_available": True,
        "pairs": list(pairs),
        "freshness_verified": False,
        "solana_wide_coverage_verified": False,
    }


class SolanaMarketVerificationTests(unittest.TestCase):
    def test_jupiter_pyth_agreement_preserves_time_delta_without_time_promotion(self):
        result = verify_jupiter_vs_pyth_price(
            jupiter("1.00"),
            pyth("1.005", publish_time=1002),
            max_relative_difference="0.01",
            jupiter_fact_time_unix=1000,
        )

        self.assertEqual(result["status"], AGREEMENT)
        self.assertTrue(result["identity_verified"])
        self.assertTrue(result["semantics_verified"])
        self.assertTrue(result["within_tolerance"])
        self.assertEqual(result["fact_time_delta_seconds"], "2")
        self.assertIsNone(result["time_identity_policy_complete"])
        self.assertFalse(result["time_identity_policy_applied"])
        self.assertFalse(result["time_identity_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["current_price_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_jupiter_pyth_price_conflict_is_explicit_but_non_promotable(self):
        result = verify_jupiter_vs_pyth_price(
            jupiter("1.00"),
            pyth("1.20", publish_time=1000),
            max_relative_difference="0.01",
            jupiter_fact_time_unix=1000,
        )

        self.assertEqual(result["status"], CONFLICT)
        self.assertFalse(result["within_tolerance"])
        self.assertFalse(result["time_identity_verified"])
        self.assertFalse(result["current_price_promotable"])

    def test_jupiter_pyth_requires_exact_mint_mapping_and_verified_integrity(self):
        wrong_mint = verify_jupiter_vs_pyth_price(
            jupiter(),
            pyth(mint="OtherMint"),
            max_relative_difference="0.01",
            jupiter_fact_time_unix=1000,
        )
        self.assertEqual(wrong_mint["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("mint_mismatch", wrong_mint["rejection_reasons"])

        partial = pyth()
        partial["price_integrity_verified"] = False
        result = verify_jupiter_vs_pyth_price(
            jupiter(),
            partial,
            max_relative_difference="0.01",
            jupiter_fact_time_unix=1000,
        )
        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn(
            "pyth_price_integrity_unverified",
            result["rejection_reasons"],
        )

    def test_jupiter_pyth_missing_jupiter_fact_time_is_insufficient(self):
        result = verify_jupiter_vs_pyth_price(
            jupiter(),
            pyth(),
            max_relative_difference="0.01",
            jupiter_fact_time_unix=None,
        )
        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn(
            "jupiter_fact_time_unavailable",
            result["rejection_reasons"],
        )

    def test_tolerance_is_required_and_has_no_hidden_default(self):
        with self.assertRaisesRegex(ValueError, "must be supplied explicitly"):
            verify_jupiter_vs_dexscreener_prices(
                jupiter(),
                dexscreener(pair("PairA", "1.00")),
                max_relative_difference=None,
            )

    def test_tolerance_must_be_fraction_between_zero_and_one(self):
        for value in (-0.01, 1.01, "bad", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    verify_jupiter_vs_dexscreener_prices(
                        jupiter(),
                        dexscreener(pair("PairA", "1.00")),
                        max_relative_difference=value,
                    )

    def test_all_eligible_pairs_within_tolerance_is_agreement_but_not_promotable(self):
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter("1.00"),
            dexscreener(
                pair("PairA", "1.005"),
                pair("PairB", "0.995"),
            ),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], AGREEMENT)
        self.assertTrue(result["identity_verified"])
        self.assertTrue(result["semantics_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["mint"], MINT)
        self.assertEqual(result["unit"], "USD_PER_TOKEN")
        self.assertEqual(result["max_relative_difference"], "0.01")
        self.assertEqual(result["eligible_pair_count"], 2)
        self.assertTrue(all(item["within_tolerance"] for item in result["comparisons"]))
        self.assertIn("freshness_not_verified", result["warnings"])

    def test_one_outlier_pair_makes_crosscheck_conflict_without_averaging(self):
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter("1.00"),
            dexscreener(
                pair("PairA", "1.005"),
                pair("PairB", "1.50"),
            ),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], CONFLICT)
        self.assertFalse(result["cmis_promotable"])
        by_pair = {item["pair_address"]: item for item in result["comparisons"]}
        self.assertTrue(by_pair["PairA"]["within_tolerance"])
        self.assertFalse(by_pair["PairB"]["within_tolerance"])
        self.assertNotIn("average_price", result)
        self.assertNotIn("selected_pair", result)

    def test_structural_rejection_precedes_outlier_conflict(self):
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter("1.00"),
            dexscreener(
                pair("PairA", "1.50"),
                pair("PairA", "1.00"),
            ),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertFalse(result["cmis_promotable"])
        self.assertIn("dexscreener_pair_contract_invalid", result["rejection_reasons"])
        self.assertIn(
            {"pair": "PairA", "reason": "duplicate_pair_address"},
            result["structural_rejections"],
        )
        self.assertEqual(result["comparisons"], [])

    def test_quote_side_pair_is_ineligible_and_never_used_as_requested_mint_price(self):
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter("1.00"),
            dexscreener(
                pair("QuotePair", "20.00", role="quote", subject="OtherBase"),
                pair("BasePair", "1.00"),
            ),
            max_relative_difference="0",
        )

        self.assertEqual(result["status"], AGREEMENT)
        self.assertEqual(result["eligible_pair_count"], 1)
        self.assertEqual(result["comparisons"][0]["pair_address"], "BasePair")
        self.assertIn(
            {"pair": "QuotePair", "reason": "requested_mint_not_base"},
            result["pair_rejections"],
        )

    def test_only_quote_side_pairs_is_insufficient_evidence(self):
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter("1.00"),
            dexscreener(pair("QuotePair", "20", role="quote", subject="OtherBase")),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertFalse(result["cmis_promotable"])
        self.assertIn("no_eligible_dexscreener_base_pair_price", result["rejection_reasons"])

    def test_missing_jupiter_price_is_insufficient_not_zero(self):
        record = jupiter()
        record["price_available"] = False
        record.pop("usd_price")

        result = verify_jupiter_vs_dexscreener_prices(
            record,
            dexscreener(pair("PairA", "1.00")),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("jupiter_price_unavailable", result["rejection_reasons"])

    def test_missing_dex_pairs_is_insufficient_not_zero(self):
        dex = dexscreener()
        dex["pairs_available"] = False
        dex["pairs"] = []

        result = verify_jupiter_vs_dexscreener_prices(
            jupiter(),
            dex,
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("dexscreener_pairs_unavailable", result["rejection_reasons"])

    def test_mint_or_source_mismatch_fails_closed(self):
        dex = dexscreener(pair("PairA", "1"))
        dex["mint"] = "OtherMint"
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter(), dex, max_relative_difference="0.01"
        )
        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("mint_mismatch", result["rejection_reasons"])

        dex = dexscreener(pair("PairA", "1"))
        dex["source"] = "other"
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter(), dex, max_relative_difference="0.01"
        )
        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("dexscreener_source_mismatch", result["rejection_reasons"])

    def test_invalid_jupiter_price_fails_closed(self):
        result = verify_jupiter_vs_dexscreener_prices(
            jupiter("0"),
            dexscreener(pair("PairA", "1")),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("jupiter_price_invalid", result["rejection_reasons"])

    def test_pair_price_subject_mismatch_is_not_eligible(self):
        bad = pair("PairA", "1")
        bad["price_subject_address"] = "OtherMint"
        bad["price_is_for_requested_mint"] = True

        result = verify_jupiter_vs_dexscreener_prices(
            jupiter(), dexscreener(bad), max_relative_difference="0.01"
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn(
            {"pair": "PairA", "reason": "price_subject_mismatch"},
            result["pair_rejections"],
        )

    def test_relative_difference_is_symmetric(self):
        forward = verify_jupiter_vs_dexscreener_prices(
            jupiter("100"),
            dexscreener(pair("PairA", "110")),
            max_relative_difference="1",
        )
        reverse = verify_jupiter_vs_dexscreener_prices(
            jupiter("110"),
            dexscreener(pair("PairA", "100")),
            max_relative_difference="1",
        )

        self.assertEqual(
            forward["comparisons"][0]["relative_difference"],
            reverse["comparisons"][0]["relative_difference"],
        )


if __name__ == "__main__":
    unittest.main()
