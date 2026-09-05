from __future__ import annotations

from urllib.parse import urlencode
import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    X1PAYS_CORROBORATION_COMMIT,
    XDEX_STRUCTURED_CONTRACT,
    parse_xdex_url,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


WXNT = "So11111111111111111111111111111111111111112"
USDCX = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"


class XDEXStructuredDiscoveryTests(unittest.TestCase):
    def test_pool_list_endpoint(self):
        result = parse_xdex_url(
            "https://api.xdex.xyz/api/xendex/pool/list?network=mainnet"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["contract"], XDEX_STRUCTURED_CONTRACT)
        self.assertEqual(result["endpoint_type"], "pool_list")
        self.assertEqual(result["parameters"]["network"], "mainnet")
        self.assertTrue(result["parameters"]["recognized_network"])
        self.assertTrue(result["truth_state"]["xdex_route_verified"])
        self.assertFalse(result["truth_state"]["provider_response_verified"])
        self.assertFalse(result["truth_state"]["pool_identity_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

        self.assertEqual(
            result["verification_handoff"][0]["target"],
            "XDEXReadOnlyProvider.pool_list",
        )

    def test_token_price_validates_32_byte_base58_address(self):
        query = urlencode(
            {
                "network": "X1 Mainnet",
                "token_address": USDCX,
            }
        )
        result = parse_xdex_url(
            f"https://api.xdex.xyz/api/token-price/price?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "token_price")
        self.assertEqual(result["parameters"]["token_address"], USDCX)
        self.assertTrue(result["parameters"]["recognized_network"])
        self.assertFalse(result["truth_state"]["cmis_verified"])

    def test_price_history_validates_tokens_and_window(self):
        query = urlencode(
            {
                "network": "X1 Mainnet",
                "from_token": WXNT,
                "to_token": USDCX,
                "time_from": "1788400000",
                "time_to": "1788403600",
            }
        )
        result = parse_xdex_url(
            f"https://api.xdex.xyz/api/xendex/chart/history?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "price_history")
        self.assertEqual(result["parameters"]["from_token"], WXNT)
        self.assertEqual(result["parameters"]["to_token"], USDCX)
        self.assertEqual(result["parameters"]["time_from"], 1788400000)
        self.assertEqual(result["parameters"]["time_to"], 1788403600)
        self.assertFalse(result["truth_state"]["history_semantics_verified"])

        self.assertEqual(
            result["verification_handoff"][0]["target"],
            "XDEXReadOnlyProvider.price_history",
        )

    def test_swap_quote_preserves_optional_slippage_without_promoting_it(self):
        query = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": WXNT,
                "token_in_amount": "10.5000",
                "is_exact_amount_in": "true",
                "slippage": "0.5",
            }
        )
        result = parse_xdex_url(
            f"https://api.xdex.xyz/api/xendex/swap/quote?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "swap_quote")
        self.assertEqual(result["parameters"]["token_in_amount"], "10.5000")
        self.assertTrue(result["parameters"]["is_exact_amount_in"])
        self.assertEqual(result["parameters"]["slippage_raw"], "0.5")
        self.assertFalse(
            result["parameters"]["slippage_semantics_verified_by_structured_layer"]
        )
        self.assertFalse(result["truth_state"]["quote_semantics_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])

    def test_documentation_route_is_candidate_only(self):
        result = parse_xdex_url(
            "https://xdexdocs.gitbook.io/xdex/developers/interface-definition-idl"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "documentation")
        self.assertIn(
            "/xdex/developers/interface-definition-idl",
            result["parameters"]["path"],
        )
        self.assertFalse(result["parameters"]["documentation_semantics_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])

    def test_missing_required_parameter_fails_closed(self):
        result = parse_xdex_url(
            "https://api.xdex.xyz/api/xendex/pool/list"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["endpoint_type"], "pool_list")
        self.assertEqual(result["reason"], "missing_required_query_parameter")
        self.assertFalse(result["truth_state"]["xdex_route_verified"])

    def test_unknown_parameter_fails_closed(self):
        result = parse_xdex_url(
            "https://api.xdex.xyz/api/xendex/pool/list"
            "?network=mainnet&surprise=true"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "unknown_query_parameter")

    def test_duplicate_parameter_fails_closed(self):
        result = parse_xdex_url(
            "https://api.xdex.xyz/api/xendex/pool/list"
            "?network=mainnet&network=testnet"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "duplicate_query_parameter")

    def test_invalid_token_address_fails_closed(self):
        query = urlencode(
            {
                "network": "X1 Mainnet",
                "token_address": "1111",
            }
        )
        result = parse_xdex_url(
            f"https://api.xdex.xyz/api/token-price/price?{query}"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(
            result["reason"],
            "token_address_must_decode_to_32_bytes",
        )

    def test_history_same_token_and_bad_window_fail_closed(self):
        same = urlencode(
            {
                "network": "X1 Mainnet",
                "from_token": WXNT,
                "to_token": WXNT,
                "time_from": "100",
                "time_to": "200",
            }
        )
        bad_window = urlencode(
            {
                "network": "X1 Mainnet",
                "from_token": WXNT,
                "to_token": USDCX,
                "time_from": "200",
                "time_to": "100",
            }
        )

        same_result = parse_xdex_url(
            f"https://api.xdex.xyz/api/xendex/chart/history?{same}"
        )
        bad_window_result = parse_xdex_url(
            f"https://api.xdex.xyz/api/xendex/chart/history?{bad_window}"
        )

        self.assertFalse(same_result["supported"])
        self.assertEqual(same_result["reason"], "history_tokens_must_differ")
        self.assertFalse(bad_window_result["supported"])
        self.assertEqual(
            bad_window_result["reason"],
            "time_to_must_be_greater_than_time_from",
        )

    def test_quote_invalid_decimal_or_boolean_fails_closed(self):
        bad_amount = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": WXNT,
                "token_in_amount": "-1",
                "is_exact_amount_in": "true",
            }
        )
        bad_bool = urlencode(
            {
                "network": "X1 Mainnet",
                "token_in": USDCX,
                "token_out": WXNT,
                "token_in_amount": "10",
                "is_exact_amount_in": "yes",
            }
        )

        amount_result = parse_xdex_url(
            f"https://api.xdex.xyz/api/xendex/swap/quote?{bad_amount}"
        )
        bool_result = parse_xdex_url(
            f"https://api.xdex.xyz/api/xendex/swap/quote?{bad_bool}"
        )

        self.assertFalse(amount_result["supported"])
        self.assertEqual(
            amount_result["reason"],
            "token_in_amount_must_be_positive_finite_decimal",
        )
        self.assertFalse(bool_result["supported"])
        self.assertEqual(
            bool_result["reason"],
            "is_exact_amount_in_must_be_boolean_text",
        )

    def test_wrong_api_path_is_not_guessed(self):
        result = parse_xdex_url(
            "https://api.xdex.xyz/api/xendex/swap/prepare?network=X1%20Mainnet"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "unsupported_xdex_api_path")
        self.assertFalse(result["execution_authorized"])

    def test_third_party_implementation_evidence_is_corroboration_only(self):
        result = parse_xdex_url(
            "https://api.xdex.xyz/api/xendex/pool/list?network=mainnet"
        )
        corroboration = result["implementation_evidence"]["third_party_corroboration"]

        self.assertEqual(corroboration["repository"], "Xenian84/x1pays")
        self.assertEqual(corroboration["commit"], X1PAYS_CORROBORATION_COMMIT)
        self.assertFalse(corroboration["independent_market_data_source"])
        self.assertFalse(corroboration["xdex_api_deployment_semantics_verified"])

    def test_service_wrapper_preserves_discovery_authority_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.discover_xdex_structured(
            "https://api.xdex.xyz/api/xendex/pool/list?network=mainnet"
        )

        self.assertEqual(result["source_id"], "xdex")
        self.assertTrue(result["structured_endpoint"]["supported"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
