import unittest

from moltgrid_signal_v12_ollama import (
    liquidity_depth_label,
    volume_activity_label,
    price_movement_label,
    wants_token_address,
)


class LiquidityScoutV12Tests(unittest.TestCase):

    def test_liquidity_classification(self):
        self.assertEqual(liquidity_depth_label(4999), "very thin")
        self.assertEqual(liquidity_depth_label(5000), "fairly thin")
        self.assertEqual(liquidity_depth_label(24999), "fairly thin")
        self.assertEqual(
            liquidity_depth_label(25000),
            "not qualitatively classified",
        )
        self.assertEqual(
            liquidity_depth_label(99999),
            "not qualitatively classified",
        )
        self.assertEqual(
            liquidity_depth_label(100000),
            "comparatively deep",
        )

    def test_volume_classification(self):
        self.assertEqual(volume_activity_label(999), "light")
        self.assertEqual(
            volume_activity_label(1000),
            "not qualitatively classified",
        )
        self.assertEqual(
            volume_activity_label(24999),
            "not qualitatively classified",
        )
        self.assertEqual(volume_activity_label(25000), "strong")

    def test_price_movement_classification(self):
        self.assertEqual(price_movement_label(-10), "down sharply")
        self.assertEqual(
            price_movement_label(-3),
            "under noticeable selling pressure",
        )
        self.assertEqual(
            price_movement_label(-2.99),
            "relatively modest movement",
        )
        self.assertEqual(
            price_movement_label(2.99),
            "relatively modest movement",
        )
        self.assertEqual(
            price_movement_label(3),
            "a solid upward move",
        )
        self.assertEqual(price_movement_label(10), "up sharply")

    def test_token_address_is_opt_in(self):
        self.assertTrue(
            wants_token_address("What is AGI's token address?")
        )
        self.assertTrue(
            wants_token_address("Show me the AGI mint address")
        )
        self.assertFalse(
            wants_token_address("What is AGI doing?")
        )
        self.assertFalse(
            wants_token_address("What is AGI's liquidity?")
        )
        self.assertFalse(
            wants_token_address("Show me the pool address")
        )


    def test_two_asset_analyst_comparison(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        agi = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_TEST_ADDRESS",
            "price": "$0.000067681",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 1399,
            "change1": -0.50,
            "change24": -5.57,
            "liquidity": 3522,
            "market_cap": 31105,
            "safety": "A (86/100)",
        }

        xnt = {
            "title": "XNT (Wrapped XNT)",
            "symbol": "XNT",
            "token_address": "XNT_TEST_ADDRESS",
            "price": "$0.5407",
            "liquidity": 33289,
            "vol24": 6651,
            "change24": 0.38,
            "market_cap": 7_460_000,
            "safety": "A (100/100)",
        }

        resolved = [
            ("AGI", ["dummy"]),
            ("XNT", ["dummy"]),
        ]

        with patch.object(
            scout,
            "compact_asset_snapshot",
            side_effect=[agi, xnt],
        ):
            answer = scout.format_multi_asset_answer(
                "Compare AGI vs XNT",
                resolved,
                {},
            )

        self.assertIn(
            "Liquidity Scout XDEX comparison:",
            answer,
        )

        self.assertIn(
            "• Liquidity: $3,522 (very thin)",
            answer,
        )

        self.assertIn(
            "• Liquidity: $33,289",
            answer,
        )

        self.assertIn(
            "• Liquidity: XNT has 9.5× more available liquidity",
            answer,
        )

        self.assertIn(
            "• Trading activity: XNT has 4.8× more 24h volume",
            answer,
        )

        self.assertIn(
            "• Largest absolute 24h price move: AGI (-5.57%).",
            answer,
        )

        self.assertIn(
            "• Best 24h return: XNT (+0.38%).",
            answer,
        )

        self.assertIn(
            "• Tokenomics: AGI A (86/100) • XNT A (100/100)",
            answer,
        )

        self.assertIn(
            "XNT's deeper available liquidity should generally "
            "reduce slippage and price-impact pressure relative to AGI.",
            answer,
        )

        # Privacy rule: token addresses remain hidden unless requested.
        self.assertNotIn("AGI_TEST_ADDRESS", answer)
        self.assertNotIn("XNT_TEST_ADDRESS", answer)

    def test_comparison_token_addresses_are_opt_in(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        agi = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_TEST_ADDRESS",
            "price": "$0.000067681",
            "liquidity": 3522,
            "vol24": 1399,
            "change24": -5.57,
            "market_cap": 31105,
            "safety": "A (86/100)",
        }

        xnt = {
            "title": "XNT (Wrapped XNT)",
            "symbol": "XNT",
            "token_address": "XNT_TEST_ADDRESS",
            "price": "$0.5407",
            "liquidity": 33289,
            "vol24": 6651,
            "change24": 0.38,
            "market_cap": 7_460_000,
            "safety": "A (100/100)",
        }

        resolved = [
            ("AGI", ["dummy"]),
            ("XNT", ["dummy"]),
        ]

        with patch.object(
            scout,
            "compact_asset_snapshot",
            side_effect=[agi, xnt],
        ):
            answer = scout.format_multi_asset_answer(
                "Compare AGI vs XNT and show token address",
                resolved,
                {},
            )

        self.assertIn("Token Addresses:", answer)
        self.assertIn("AGI_TEST_ADDRESS", answer)
        self.assertIn("XNT_TEST_ADDRESS", answer)


    def test_general_defi_question_does_not_resolve_asset(self):
        import moltgrid_signal_v12_ollama as scout

        pools = [
            {
                "address": "POOL_AGI_XNT",
                "liquidity": 3500,
                "volume24h": 1400,
                "baseToken": {
                    "symbol": "AGI",
                    "name": "Artificial General Intelligence",
                    "mint": "AGI_MINT",
                    "address": "AGI_MINT",
                },
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_MINT",
                    "address": "XNT_MINT",
                },
            }
        ]

        term, matches = scout.resolve_asset(
            "What is slippage in a liquidity pool?",
            pools,
        )

        self.assertFalse(matches)

    def test_exact_agi_resolves_correctly(self):
        import moltgrid_signal_v12_ollama as scout

        pools = [
            {
                "address": "POOL_AGI_XNT",
                "liquidity": 3500,
                "volume24h": 1400,
                "baseToken": {
                    "symbol": "AGI",
                    "name": "Artificial General Intelligence",
                    "mint": "AGI_MINT",
                    "address": "AGI_MINT",
                },
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_MINT",
                    "address": "XNT_MINT",
                },
            }
        ]

        term, matches = scout.resolve_asset(
            "What is AGI doing?",
            pools,
        )

        self.assertTrue(matches)
        self.assertEqual(term.upper(), "AGI")
        self.assertGreaterEqual(matches[0][3], 90)

    def test_compare_agi_vs_xnt_resolves_two_assets(self):
        import moltgrid_signal_v12_ollama as scout

        pools = [
            {
                "address": "POOL_AGI_XNT",
                "liquidity": 3500,
                "volume24h": 1400,
                "baseToken": {
                    "symbol": "AGI",
                    "name": "Artificial General Intelligence",
                    "mint": "AGI_MINT",
                    "address": "AGI_MINT",
                },
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_MINT",
                    "address": "XNT_MINT",
                },
            }
        ]

        resolved = scout.resolve_multiple_assets(
            "Compare AGI vs XNT",
            pools,
        )

        self.assertEqual(len(resolved), 2)

        terms = {term.upper() for term, _matches in resolved}
        self.assertEqual(terms, {"AGI", "XNT"})

    def test_unknown_asset_does_not_substitute_known_asset(self):
        import moltgrid_signal_v12_ollama as scout

        pools = [
            {
                "address": "POOL_AGI_XNT",
                "liquidity": 3500,
                "volume24h": 1400,
                "baseToken": {
                    "symbol": "AGI",
                    "name": "Artificial General Intelligence",
                    "mint": "AGI_MINT",
                    "address": "AGI_MINT",
                },
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_MINT",
                    "address": "XNT_MINT",
                },
            }
        ]

        term, matches = scout.resolve_asset(
            "What is TOTALLYUNKNOWNCOIN doing?",
            pools,
        )

        self.assertFalse(matches)



    def test_broad_asset_overview_shows_core_metrics(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        snap = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_SECRET_TEST_ADDRESS",
            "pool_address": "POOL_SECRET_TEST_ADDRESS",
            "price": "$0.000067681",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 1399,
            "change1": -0.50,
            "change24": -5.57,
            "liquidity": 3522,
            "market_cap": 31105,
            "safety": "A (86/100)",
        }

        with patch.object(
            scout,
            "compact_asset_snapshot",
            return_value=snap,
        ), patch.object(
            scout,
            "ai_asset_analysis",
            return_value="Verified market analysis.",
        ):
            answer = scout.format_asset_analysis_answer(
                "Tell me about AGI",
                "AGI",
                ["dummy"],
                {},
            )

        self.assertIn("• Price: $0.000067681", answer)
        self.assertIn("• Liquidity: $3,522", answer)
        self.assertIn("• Volume 24h: $1,399", answer)
        self.assertIn("• Change 24h: -5.57%", answer)
        self.assertIn("• Market Cap: $31,105", answer)
        self.assertIn("• Tokenomics Safety: A (86/100)", answer)

        # Privacy rules must remain intact.
        self.assertNotIn("AGI_SECRET_TEST_ADDRESS", answer)
        self.assertNotIn("POOL_SECRET_TEST_ADDRESS", answer)



    def test_deep_asset_analysis_only_sends_requested_metrics_to_ai(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        snap = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_SECRET_TEST_ADDRESS",
            "pool": "AGI/XNT",
            "pool_address": "POOL_SECRET_TEST_ADDRESS",
            "price": "$0.000067681",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 1399,
            "change1": -0.50,
            "change24": -5.57,
            "liquidity": 3522,
            "market_cap": 31105,
            "safety": "A (86/100)",
        }

        with patch.object(
            scout,
            "compact_asset_snapshot",
            return_value=snap,
        ), patch.object(
            scout,
            "deepseek_text",
            return_value="Verified market analysis.",
        ) as mock_ai:
            scout.format_asset_analysis_answer(
                "Analyze AGI price liquidity volume 24h change market cap safety",
                "AGI",
                ["dummy"],
                {},
            )

        ai_context = mock_ai.call_args.args[1]

        # Broad overview: Ollama receives only the six visible core metrics.
        self.assertIn("Price: $0.000067681", ai_context)
        self.assertIn("Liquidity: $3,522", ai_context)
        self.assertIn("Volume 24h: $1,399", ai_context)
        self.assertIn("Change 24h: -5.57%", ai_context)
        self.assertIn("Market Cap: $31,105", ai_context)
        self.assertIn("Tokenomics Safety: A (86/100)", ai_context)

        # Extra/internal details must not be supplied unless requested.
        self.assertNotIn("Age:", ai_context)
        self.assertNotIn("Holders:", ai_context)
        self.assertNotIn("Transactions 24h:", ai_context)
        self.assertNotIn("Change 1h:", ai_context)
        self.assertNotIn("Token address:", ai_context)
        self.assertNotIn("Pool:", ai_context)
        self.assertNotIn("Pool address:", ai_context)



    def test_asset_analysis_removes_unsupported_risk_severity_labels(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        snap = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_SECRET_TEST_ADDRESS",
            "pool": "AGI/XNT",
            "pool_address": "POOL_SECRET_TEST_ADDRESS",
            "price": "$0.0000652032",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 947.1685,
            "change1": -0.50,
            "change24": -12.20,
            "liquidity": 3429,
            "market_cap": 29965,
            "safety": "A (86/100)",
        }

        model_text = (
            "Trading risk is elevated due to very thin liquidity and "
            "a sharp price drop, increasing execution risk and slippage."
        )

        with patch.object(
            scout,
            "compact_asset_snapshot",
            return_value=snap,
        ), patch.object(
            scout,
            "deepseek_text",
            return_value=model_text,
        ):
            answer = scout.format_asset_analysis_answer(
                "Analyze AGI market risk using price liquidity volume 24h change market cap safety",
                "AGI",
                ["dummy"],
                {},
            )

        self.assertNotIn("risk is elevated", answer.lower())
        self.assertIn("very thin liquidity", answer.lower())
        self.assertIn("slippage", answer.lower())



    def test_asset_analysis_removes_unsupported_execution_risk_severity(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        snap = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_SECRET_TEST_ADDRESS",
            "pool": "AGI/XNT",
            "pool_address": "POOL_SECRET_TEST_ADDRESS",
            "price": "$0.0000670363",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 947.6046,
            "change1": -0.50,
            "change24": -12.73,
            "liquidity": 3452,
            "market_cap": 30144,
            "safety": "A (86/100)",
        }

        model_text = (
            "This combination of thin liquidity and sharp price decline "
            "suggests elevated execution risk."
        )

        with patch.object(
            scout,
            "compact_asset_snapshot",
            return_value=snap,
        ), patch.object(
            scout,
            "deepseek_text",
            return_value=model_text,
        ):
            answer = scout.format_asset_analysis_answer(
                "Analyze AGI market risk using price liquidity volume 24h change market cap safety",
                "AGI",
                ["dummy"],
                {},
            )

        self.assertNotIn("elevated execution risk", answer.lower())
        self.assertIn("thin liquidity", answer.lower())



    def test_deep_asset_analysis_removes_unsupported_activity_and_omitted_metrics(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        snap = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_SECRET_TEST_ADDRESS",
            "pool": "AGI/XNT",
            "pool_address": "POOL_SECRET_TEST_ADDRESS",
            "price": "$0.0000670363",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 947.6046,
            "change1": -0.50,
            "change24": 8.73,
            "liquidity": 3452,
            "market_cap": 30144,
            "safety": "A (86/100)",
        }

        model_text = (
            "AGI has light trading volume, indicating limited trading activity "
            "and positive momentum. The tokenomics safety grade is A (86/100), "
            "which does not indicate security or volatility levels."
        )

        with patch.object(
            scout,
            "compact_asset_snapshot",
            return_value=snap,
        ), patch.object(
            scout,
            "deepseek_text",
            return_value=model_text,
        ):
            answer = scout.format_asset_analysis_answer(
                "Analyze AGI market risk using price liquidity volume 24h change market cap safety",
                "AGI",
                ["dummy"],
                {},
            )

        self.assertIn("light trading volume", answer.lower())
        self.assertNotIn("limited trading activity", answer.lower())
        self.assertNotIn("positive momentum", answer.lower())
        self.assertNotIn("volatility", answer.lower())


    def test_broad_asset_overview_does_not_call_ollama(self):
        import moltgrid_signal_v12_ollama as scout
        from unittest.mock import patch

        snap = {
            "title": "AGI",
            "symbol": "AGI",
            "token_address": "AGI_SECRET_TEST_ADDRESS",
            "pool": "AGI/XNT",
            "pool_address": "POOL_SECRET_TEST_ADDRESS",
            "price": "$0.0000669498",
            "age": "6mo",
            "holders": 1000,
            "txns24": 250,
            "vol24": 924.814,
            "change1": -0.50,
            "change24": -13.82,
            "liquidity": 3452,
            "market_cap": 30103,
            "safety": "A (86/100)",
        }

        with patch.object(
            scout,
            "compact_asset_snapshot",
            return_value=snap,
        ), patch.object(
            scout,
            "ai_asset_analysis",
            side_effect=AssertionError(
                "Broad overview should not call Ollama."
            ),
        ):
            answer = scout.format_asset_analysis_answer(
                "Tell me about AGI",
                "AGI",
                ["dummy"],
                {},
            )

        self.assertIn("• Price: $0.0000669498", answer)
        self.assertIn("• Liquidity: $3,452", answer)
        self.assertIn("• Volume 24h: $924.814", answer)
        self.assertIn("• Change 24h: -13.82%", answer)
        self.assertIn("• Market Cap: $30,103", answer)
        self.assertIn("• Tokenomics Safety: A (86/100)", answer)

        self.assertIn("very thin", answer.lower())
        self.assertIn("slippage", answer.lower())
        self.assertIn("light", answer.lower())
        self.assertIn("down sharply", answer.lower())


    def test_broad_asset_question_routes_to_analysis(self):
        import moltgrid_signal_v12_ollama as scout

        self.assertTrue(
            scout.wants_asset_analysis("Tell me about AGI")
        )

        # A specific metric request should remain deterministic.
        self.assertFalse(
            scout.wants_asset_analysis("What is AGI's liquidity?")
        )


if __name__ == "__main__":
    unittest.main()
