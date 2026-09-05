from __future__ import annotations

from urllib.parse import urlencode
import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    XDEX_EXTENDED_READONLY_STRUCTURED_CONTRACT,
    XDEX_WEB_SOURCE,
    parse_xdex_extended_readonly_url,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
USDCX = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"


class XDEXExtendedReadOnlyStructuredTests(unittest.TestCase):
    def test_xdex_web_source_explicitly_allows_oracle_host(self):
        self.assertIn("oracle.xdex.xyz", XDEX_WEB_SOURCE.allowed_hosts)
        self.assertIn(
            "https://oracle.xdex.xyz/",
            XDEX_WEB_SOURCE.base_urls,
        )

    def test_frontend_quote_alias_validates_existing_quote_shape(self):
        query = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": XNT,
                "token_in_amount": "10.5000",
                "is_exact_amount_in": "true",
                "slippage": "0.5",
                "amm_config_address": CONFIG,
            }
        )
        result = parse_xdex_extended_readonly_url(
            f"https://api.xdex.xyz/api/xdex/swap/quote?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(
            result["contract"],
            XDEX_EXTENDED_READONLY_STRUCTURED_CONTRACT,
        )
        self.assertEqual(result["endpoint_type"], "frontend_quote_alias")
        self.assertEqual(result["parameters"]["token_in"], USDCX)
        self.assertEqual(result["parameters"]["token_out"], XNT)
        self.assertEqual(result["parameters"]["token_in_amount"], "10.5000")
        self.assertTrue(result["parameters"]["is_exact_amount_in"])
        self.assertEqual(result["parameters"]["slippage_raw"], "0.5")
        self.assertEqual(result["parameters"]["amm_config_address"], CONFIG)
        self.assertFalse(result["parameters"]["route_config_verified"])
        self.assertTrue(result["truth_state"]["xdex_extended_route_verified"])
        self.assertFalse(
            result["truth_state"]["frontend_alias_equivalence_verified"]
        )
        self.assertFalse(result["truth_state"]["route_config_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_frontend_quote_alias_rejects_invalid_config_and_unknown_params(self):
        bad_config = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": XNT,
                "token_in_amount": "10",
                "is_exact_amount_in": "true",
                "amm_config_address": "1111",
            }
        )
        unknown = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": XNT,
                "token_in_amount": "10",
                "is_exact_amount_in": "true",
                "route": "best",
            }
        )

        bad_config_result = parse_xdex_extended_readonly_url(
            f"https://api.xdex.xyz/api/xdex/swap/quote?{bad_config}"
        )
        unknown_result = parse_xdex_extended_readonly_url(
            f"https://api.xdex.xyz/api/xdex/swap/quote?{unknown}"
        )

        self.assertFalse(bad_config_result["supported"])
        self.assertEqual(
            bad_config_result["reason"],
            "amm_config_address_must_decode_to_32_bytes",
        )
        self.assertFalse(unknown_result["supported"])
        self.assertEqual(unknown_result["reason"], "unknown_query_parameter")

    def test_oracle_price_exact_token_mode(self):
        query = urlencode({"token_address": XENCAT})
        result = parse_xdex_extended_readonly_url(
            f"https://oracle.xdex.xyz/api/v1/token/price?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "oracle_token_price")
        self.assertEqual(result["parameters"]["mode"], "exact_token")
        self.assertEqual(result["parameters"]["token_address"], XENCAT)
        self.assertFalse(result["truth_state"]["oracle_price_semantics_verified"])
        self.assertFalse(result["truth_state"]["source_independence_verified"])

    def test_oracle_price_all_details_mode(self):
        result = parse_xdex_extended_readonly_url(
            "https://oracle.xdex.xyz/api/v1/token/price?all=true&details=true"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "oracle_token_price")
        self.assertEqual(result["parameters"]["mode"], "all_details")
        self.assertTrue(result["parameters"]["all"])
        self.assertTrue(result["parameters"]["details"])
        self.assertFalse(result["truth_state"]["provider_response_verified"])

    def test_oracle_price_modes_are_mutually_exclusive(self):
        query = urlencode(
            {
                "token_address": XENCAT,
                "all": "true",
                "details": "true",
            }
        )
        result = parse_xdex_extended_readonly_url(
            f"https://oracle.xdex.xyz/api/v1/token/price?{query}"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(
            result["reason"],
            "oracle_price_modes_are_mutually_exclusive",
        )

    def test_oracle_all_details_requires_true_true(self):
        for query in (
            "all=false&details=true",
            "all=true&details=false",
            "all=1&details=true",
        ):
            with self.subTest(query=query):
                result = parse_xdex_extended_readonly_url(
                    f"https://oracle.xdex.xyz/api/v1/token/price?{query}"
                )
                self.assertFalse(result["supported"])
                self.assertEqual(
                    result["reason"],
                    "oracle_all_details_mode_requires_true_true",
                )

    def test_oracle_sell_quote_validates_token_and_amount(self):
        query = urlencode(
            {
                "token_address": XENCAT,
                "amount_in": "1000",
            }
        )
        result = parse_xdex_extended_readonly_url(
            f"https://oracle.xdex.xyz/api/v1/token/sell-quote?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "oracle_sell_quote")
        self.assertEqual(result["parameters"]["token_address"], XENCAT)
        self.assertEqual(result["parameters"]["amount_in"], "1000")
        self.assertEqual(
            result["parameters"]["known_semantic_scope"],
            "no_fee_cp_curve_reference_for_tested_cases_only",
        )
        self.assertFalse(result["parameters"]["fee_complete"])
        self.assertFalse(result["parameters"]["slippage_adjusted"])
        self.assertFalse(result["parameters"]["executable_quote"])
        self.assertFalse(result["parameters"]["route_optimality_verified"])
        self.assertFalse(result["parameters"]["fill_quality_verified"])
        self.assertFalse(
            result["truth_state"]["oracle_sell_quote_semantics_verified"]
        )

    def test_oracle_sell_quote_rejects_bad_amount_and_extra_parameter(self):
        bad_amount = parse_xdex_extended_readonly_url(
            f"https://oracle.xdex.xyz/api/v1/token/sell-quote"
            f"?token_address={XENCAT}&amount_in=0"
        )
        extra = parse_xdex_extended_readonly_url(
            f"https://oracle.xdex.xyz/api/v1/token/sell-quote"
            f"?token_address={XENCAT}&amount_in=1&slippage=0.5"
        )

        self.assertFalse(bad_amount["supported"])
        self.assertEqual(
            bad_amount["reason"],
            "amount_in_must_be_positive_finite_decimal",
        )
        self.assertFalse(extra["supported"])
        self.assertEqual(extra["reason"], "unknown_query_parameter")

    def test_duplicate_query_parameters_fail_closed(self):
        result = parse_xdex_extended_readonly_url(
            f"https://oracle.xdex.xyz/api/v1/token/price"
            f"?token_address={XENCAT}&token_address={XNT}"
        )
        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "duplicate_query_parameter")

    def test_prepare_endpoints_are_not_part_of_extended_parser(self):
        for path in (
            "/api/xendex/swap/prepare",
            "/api/xdex/swap/prepare",
        ):
            with self.subTest(path=path):
                result = parse_xdex_extended_readonly_url(
                    f"https://api.xdex.xyz{path}?network=X1%20Mainnet"
                )
                self.assertFalse(result["supported"])
                self.assertEqual(
                    result["reason"],
                    "unsupported_xdex_extended_readonly_path",
                )
                self.assertFalse(result["execution_authorized"])

    def test_original_research_quote_route_stays_owned_by_v1_contract(self):
        query = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": XNT,
                "token_in_amount": "10",
                "is_exact_amount_in": "true",
            }
        )
        result = parse_xdex_extended_readonly_url(
            f"https://api.xdex.xyz/api/xendex/swap/quote?{query}"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(
            result["reason"],
            "unsupported_xdex_extended_readonly_path",
        )

    def test_service_wrapper_preserves_discovery_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.discover_xdex_extended_readonly(
            f"https://oracle.xdex.xyz/api/v1/token/price?token_address={XENCAT}"
        )

        self.assertEqual(result["source_id"], "xdex")
        self.assertTrue(result["structured_endpoint"]["supported"])
        self.assertEqual(
            result["structured_endpoint"]["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
