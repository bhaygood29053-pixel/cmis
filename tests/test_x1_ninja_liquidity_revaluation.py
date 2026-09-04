import unittest

from liquidity_scout.providers.x1.ninja_liquidity_revaluation import (
    verify_price_only_liquidity_revaluation,
)


class NinjaLiquidityRevaluationTests(unittest.TestCase):
    def test_verifies_reference_pool_price_only_revaluation(self):
        result = verify_price_only_liquidity_revaluation(
            before={
                "liquidity": "6427.570534",
                "pooledBase": "8275.174533379",
                "pooledQuote": "3194.186125",
                "xntPriceUsd": "0.3859962242628034",
            },
            after={
                "liquidity": "6388.37225",
                "pooledBase": "8275.174533379",
                "pooledQuote": "3194.186125",
                "xntPriceUsd": "0.3859962242628034",
            },
            wrapped_xnt_provider_field="pooledBase",
            intervening_pool_signature_count=0,
        )
        self.assertTrue(result["price_only_liquidity_revaluation_verified"])
        self.assertTrue(result["provider_internal_liquidity_formula_supported"])
        self.assertFalse(result["liquidity_usd_semantics_verified"])
        self.assertFalse(result["liquidity_freshness_verified"])

    def test_verifies_wrapped_xnt_quote_pool_revaluation(self):
        result = verify_price_only_liquidity_revaluation(
            before={
                "liquidity": "259.3409308586646",
                "pooledBase": "29653923.13740653",
                "pooledQuote": "322.10095024",
                "xntPriceUsd": "0.3859962242628034",
            },
            after={
                "liquidity": "248.65950124820222",
                "pooledBase": "29653923.13740653",
                "pooledQuote": "322.10095024",
                "xntPriceUsd": "0.3859962242628034",
            },
            wrapped_xnt_provider_field="pooledQuote",
            intervening_pool_signature_count=0,
        )
        self.assertTrue(result["price_only_liquidity_revaluation_verified"])

    def test_reserve_change_fails_closed(self):
        result = verify_price_only_liquidity_revaluation(
            before={
                "liquidity": "100",
                "pooledBase": "10",
                "pooledQuote": "20",
                "xntPriceUsd": "5",
            },
            after={
                "liquidity": "110",
                "pooledBase": "11",
                "pooledQuote": "20",
                "xntPriceUsd": "5",
            },
            wrapped_xnt_provider_field="pooledBase",
            intervening_pool_signature_count=0,
        )
        self.assertFalse(result["price_only_liquidity_revaluation_verified"])
        self.assertIn("provider_reserves_changed", result["rejection_reasons"])

    def test_intervening_pool_transaction_fails_closed(self):
        result = verify_price_only_liquidity_revaluation(
            before={
                "liquidity": "90",
                "pooledBase": "10",
                "pooledQuote": "20",
                "xntPriceUsd": "5",
            },
            after={
                "liquidity": "100",
                "pooledBase": "10",
                "pooledQuote": "20",
                "xntPriceUsd": "5",
            },
            wrapped_xnt_provider_field="pooledBase",
            intervening_pool_signature_count=1,
        )
        self.assertFalse(result["price_only_liquidity_revaluation_verified"])
        self.assertIn(
            "intervening_pool_transactions_present",
            result["rejection_reasons"],
        )

    def test_formula_mismatch_fails_closed(self):
        result = verify_price_only_liquidity_revaluation(
            before={
                "liquidity": "90",
                "pooledBase": "10",
                "pooledQuote": "20",
                "xntPriceUsd": "5",
            },
            after={
                "liquidity": "99",
                "pooledBase": "10",
                "pooledQuote": "20",
                "xntPriceUsd": "5",
            },
            wrapped_xnt_provider_field="pooledBase",
            intervening_pool_signature_count=0,
        )
        self.assertFalse(result["price_only_liquidity_revaluation_verified"])
        self.assertIn(
            "new_liquidity_not_reproduced_by_revaluation_formula",
            result["rejection_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
