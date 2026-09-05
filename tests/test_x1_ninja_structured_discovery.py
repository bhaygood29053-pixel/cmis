from __future__ import annotations

from urllib.parse import urlencode
import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    X1_NINJA_STRUCTURED_CONTRACT,
    parse_x1_ninja_url,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


POOL = "1" * 32


class X1NinjaStructuredDiscoveryTests(unittest.TestCase):
    def test_pool_catalog_without_query_is_supported(self):
        result = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["contract"], X1_NINJA_STRUCTURED_CONTRACT)
        self.assertEqual(result["endpoint_type"], "pool_catalog")
        self.assertTrue(result["truth_state"]["x1_ninja_route_verified"])
        self.assertFalse(result["truth_state"]["provider_response_verified"])
        self.assertFalse(result["truth_state"]["liquidity_semantics_verified"])
        self.assertFalse(result["truth_state"]["freshness_verified"])
        self.assertTrue(result["authentication_required_by_provider_fetch"])
        self.assertFalse(result["authentication_material_retained"])
        self.assertFalse(result["execution_authorized"])

    def test_pool_catalog_accepts_bounded_pagination_syntax_without_semantics(self):
        result = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools?limit=100&offset=200"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["parameters"]["limit"], 100)
        self.assertEqual(result["parameters"]["offset"], 200)
        self.assertFalse(result["parameters"]["pagination_semantics_verified"])

    def test_pool_catalog_rejects_bad_or_unknown_query_parameters(self):
        bad_limit = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools?limit=0"
        )
        bad_offset = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools?offset=-1"
        )
        unknown = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools?limit=10&sort=liquidity"
        )

        self.assertFalse(bad_limit["supported"])
        self.assertEqual(bad_limit["reason"], "limit_must_be_positive_integer")
        self.assertFalse(bad_offset["supported"])
        self.assertEqual(
            bad_offset["reason"],
            "offset_must_be_nonnegative_integer",
        )
        self.assertFalse(unknown["supported"])
        self.assertEqual(unknown["reason"], "unknown_query_parameter")

    def test_credential_like_query_material_fails_closed(self):
        for query in (
            "api_key=secret",
            "token=secret",
            "authorization=Bearer%20secret",
            "access_token=secret",
        ):
            with self.subTest(query=query):
                result = parse_x1_ninja_url(
                    f"https://api.x1.ninja/v1/pools?{query}"
                )
                self.assertFalse(result["supported"])
                self.assertEqual(
                    result["reason"],
                    "credential_like_query_parameter_rejected",
                )
                self.assertFalse(result["authentication_material_retained"])
                self.assertNotIn("secret", str(result["raw_query"]))

    def test_duplicate_query_parameter_fails_closed(self):
        result = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools?limit=10&limit=20"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "duplicate_query_parameter")

    def test_pool_detail_requires_32_byte_base58_candidate(self):
        good = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/pools/{POOL}"
        )
        bad = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/pools/1111"
        )

        self.assertTrue(good["supported"])
        self.assertEqual(good["endpoint_type"], "pool_detail")
        self.assertEqual(good["parameters"]["pool_address"], POOL)
        self.assertFalse(good["parameters"]["pool_identity_verified"])
        self.assertFalse(good["truth_state"]["pool_identity_verified"])

        self.assertFalse(bad["supported"])
        self.assertEqual(
            bad["reason"],
            "pool_address_must_decode_to_32_bytes",
        )

    def test_pool_detail_rejects_query_parameters(self):
        result = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/pools/{POOL}?details=true"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(
            result["reason"],
            "pool_detail_query_parameters_not_supported",
        )

    def test_trade_history_is_structured_but_semantics_remain_closed(self):
        result = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/trades/{POOL}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "trade_history")
        self.assertEqual(result["parameters"]["pool_address"], POOL)
        self.assertFalse(result["parameters"]["pagination_or_range_verified"])
        self.assertFalse(result["truth_state"]["history_semantics_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])

    def test_trade_history_rejects_query_parameters(self):
        result = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/trades/{POOL}?limit=50"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(
            result["reason"],
            "trade_history_query_parameters_not_supported",
        )

    def test_ohlcv_validates_timeframe_and_limit(self):
        query = urlencode({"tf": "1h", "limit": "300"})
        result = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/ohlcv/{POOL}?{query}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "ohlcv")
        self.assertEqual(result["parameters"]["pool_address"], POOL)
        self.assertEqual(result["parameters"]["timeframe"], "1h")
        self.assertEqual(result["parameters"]["limit"], 300)
        self.assertFalse(result["truth_state"]["history_semantics_verified"])

    def test_ohlcv_rejects_missing_or_invalid_timeframe(self):
        missing = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/ohlcv/{POOL}"
        )
        invalid = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/ohlcv/{POOL}?tf=30m"
        )

        self.assertFalse(missing["supported"])
        self.assertEqual(missing["reason"], "missing_required_timeframe")
        self.assertFalse(invalid["supported"])
        self.assertEqual(invalid["reason"], "unsupported_ohlcv_timeframe")

    def test_ohlcv_limit_is_bounded_and_unknown_params_fail(self):
        zero = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/ohlcv/{POOL}?tf=1h&limit=0"
        )
        too_large = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/ohlcv/{POOL}?tf=1h&limit=301"
        )
        extra = parse_x1_ninja_url(
            f"https://api.x1.ninja/v1/ohlcv/{POOL}?tf=1h&from=1"
        )

        self.assertFalse(zero["supported"])
        self.assertEqual(
            zero["reason"],
            "ohlcv_limit_must_be_between_1_and_300",
        )
        self.assertFalse(too_large["supported"])
        self.assertEqual(
            too_large["reason"],
            "ohlcv_limit_must_be_between_1_and_300",
        )
        self.assertFalse(extra["supported"])
        self.assertEqual(extra["reason"], "unknown_query_parameter")

    def test_trade_stream_is_handshake_only(self):
        result = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/stream/trades"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "trade_stream_access")
        self.assertTrue(result["parameters"]["handshake_only"])
        self.assertFalse(
            result["parameters"]["event_body_consumption_authorized"]
        )
        self.assertFalse(result["parameters"]["event_schema_verified"])
        self.assertFalse(result["parameters"]["event_ordering_verified"])
        self.assertFalse(result["parameters"]["event_finality_verified"])
        self.assertFalse(result["parameters"]["stream_freshness_verified"])
        self.assertFalse(result["event_body_consumption_authorized"])
        self.assertFalse(result["stream_event_semantics_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_trade_stream_rejects_query_parameters(self):
        result = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/stream/trades?cursor=abc"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(
            result["reason"],
            "trade_stream_query_parameters_not_supported",
        )

    def test_x1_ninja_website_is_discovery_only(self):
        result = parse_x1_ninja_url(
            "https://x1.ninja/"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["endpoint_type"], "website")
        self.assertFalse(result["parameters"]["website_semantics_verified"])
        self.assertFalse(result["authentication_required_by_provider_fetch"])
        self.assertFalse(result["truth_state"]["cmis_verified"])

    def test_unknown_api_path_is_not_guessed(self):
        result = parse_x1_ninja_url(
            "https://api.x1.ninja/v1/tokens"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "unsupported_x1_ninja_api_path")
        self.assertFalse(result["execution_authorized"])

    def test_service_wrapper_preserves_discovery_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.discover_x1_ninja_structured(
            f"https://api.x1.ninja/v1/pools/{POOL}"
        )

        self.assertEqual(result["source_id"], "x1_ninja")
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
