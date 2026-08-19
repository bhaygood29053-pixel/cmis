import json
import os
import unittest

from liquidity_scout.providers.x1.x1scroll_rpc_access import (
    X1SCROLL_RPC_ENDPOINTS,
    probe_x1scroll_rpc_access,
)


RUN_LIVE = os.getenv("RUN_X1SCROLL_RPC_LIVE_TESTS") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1SCROLL_RPC_LIVE_TESTS=1 to probe read-only X1Scroll RPC access",
)
class X1ScrollRpcAccessLiveTests(unittest.TestCase):
    def test_published_candidates_gethealth_and_getslot_access(self):
        observations = []

        for endpoint in sorted(X1SCROLL_RPC_ENDPOINTS):
            for method in ("getHealth", "getSlot"):
                with self.subTest(endpoint=endpoint, method=method):
                    result = probe_x1scroll_rpc_access(
                        endpoint=endpoint,
                        method=method,
                    )
                    observations.append(result)

                    self.assertEqual(result["chain"], "x1")
                    self.assertEqual(result["endpoint"], endpoint)
                    self.assertEqual(result["method"], method)
                    self.assertIn(result["status"], {"ok", "partial", "unavailable"})
                    self.assertIn(
                        result["access"],
                        {
                            "available_unauthenticated",
                            "access_denied",
                            "endpoint_not_found",
                            "rate_limited",
                            "provider_error",
                            "unexpected_http_status",
                            "invalid_json_response",
                            "invalid_jsonrpc_response",
                            "jsonrpc_error",
                            "jsonrpc_contract_unverified",
                        },
                    )
                    self.assertFalse(result["credentials_supplied"])
                    self.assertFalse(result["source_independence_verified"])
                    self.assertFalse(result["archival_completeness_verified"])
                    self.assertFalse(result["retention_verified"])
                    self.assertFalse(result["finality_semantics_verified"])
                    self.assertFalse(result["cmis_promotable"])

        print("X1Scroll bounded RPC access observations")
        print(json.dumps(observations, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    unittest.main()
