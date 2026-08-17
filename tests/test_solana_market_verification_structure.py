import unittest

from liquidity_scout.cmis.evidence import INSUFFICIENT_EVIDENCE
from liquidity_scout.providers.solana.market_verification import (
    verify_jupiter_vs_dexscreener_prices,
)


MINT = "Mint111"


def _jupiter():
    return {
        "chain": "solana",
        "source": "jupiter_price_v3",
        "mint": MINT,
        "price_available": True,
        "usd_price": "1",
        "currency": "USD",
        "block_id": 1,
    }


def _pair(address="PairA"):
    return {
        "pair_address": address,
        "dex_id": "raydium",
        "requested_mint_role": "base",
        "price_subject_address": MINT,
        "price_is_for_requested_mint": True,
        "price_usd": "1",
    }


def _dex(pairs):
    return {
        "chain": "solana",
        "source": "dexscreener_token_pairs_v1",
        "mint": MINT,
        "pairs_available": True,
        "pairs": pairs,
    }


class SolanaMarketVerificationStructureTests(unittest.TestCase):
    def test_duplicate_pair_invalidates_crosscheck_even_with_valid_first_pair(self):
        result = verify_jupiter_vs_dexscreener_prices(
            _jupiter(),
            _dex([_pair("PairA"), _pair("PairA")]),
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

    def test_non_mapping_pair_invalidates_crosscheck(self):
        result = verify_jupiter_vs_dexscreener_prices(
            _jupiter(),
            _dex([_pair(), "corrupt"]),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("dexscreener_pair_contract_invalid", result["rejection_reasons"])
        self.assertIn(
            {"pair": "1", "reason": "pair_not_mapping"},
            result["structural_rejections"],
        )

    def test_missing_pair_address_invalidates_crosscheck(self):
        corrupt = _pair()
        corrupt.pop("pair_address")
        result = verify_jupiter_vs_dexscreener_prices(
            _jupiter(),
            _dex([_pair("PairA"), corrupt]),
            max_relative_difference="0.01",
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn(
            {"pair": "1", "reason": "pair_address_missing"},
            result["structural_rejections"],
        )

    def test_quote_side_pair_is_semantically_ineligible_not_structurally_invalid(self):
        quote = _pair("QuotePair")
        quote["requested_mint_role"] = "quote"
        quote["price_subject_address"] = "OtherBase"
        quote["price_is_for_requested_mint"] = False

        result = verify_jupiter_vs_dexscreener_prices(
            _jupiter(),
            _dex([quote, _pair("BasePair")]),
            max_relative_difference="0",
        )

        self.assertEqual(result["structural_rejections"], [])
        self.assertIn(
            {"pair": "QuotePair", "reason": "requested_mint_not_base"},
            result["pair_rejections"],
        )


if __name__ == "__main__":
    unittest.main()
