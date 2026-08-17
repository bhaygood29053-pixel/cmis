import json
import os
import unittest

from liquidity_scout.providers.x1.ninja_trade_stream import probe_trade_stream_access


RUN_LIVE = os.getenv("RUN_X1_NINJA_SSE_LIVE_TESTS") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_SSE_LIVE_TESTS=1 to probe read-only SSE access",
)
class X1NinjaTradeStreamLiveTests(unittest.TestCase):
    def test_live_trade_stream_access_handshake_without_event_consumption(self):
        result = probe_trade_stream_access()

        print("X1.Ninja trade-stream access probe")
        print(json.dumps(result, indent=2, sort_keys=True, default=str))

        self.assertEqual(result["service"], "x1_ninja_trade_stream_access")
        self.assertEqual(result["chain"], "x1")
        self.assertIn(result["status"], {"ok", "partial", "unavailable"})
        self.assertIn(
            result["access"],
            {
                "available_sse_handshake",
                "unexpected_success_content_type",
                "access_denied",
                "endpoint_not_found",
                "rate_limited",
                "provider_error",
                "http_client_error",
                "unexpected_http_status",
            },
        )
        self.assertFalse(result["event_body_consumed"])
        self.assertFalse(result["event_schema_verified"])
        self.assertFalse(result["event_ordering_verified"])
        self.assertFalse(result["event_finality_verified"])
        self.assertFalse(result["reconnect_semantics_verified"])
        self.assertFalse(result["backfill_semantics_verified"])
        self.assertFalse(result["dropped_event_detection_verified"])
        self.assertFalse(result["stream_freshness_verified"])
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
