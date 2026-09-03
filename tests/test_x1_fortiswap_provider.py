import unittest

from liquidity_scout.providers.x1.fortiswap import (
    FORTISWAP_DISCOVERY_PATH,
    FortiSwapAPIError,
    FortiSwapReadOnlyProvider,
    classify_route,
    fetch_discovery,
    normalize_discovery_catalog,
    normalize_quote_response,
    normalize_router_volume_response,
    normalize_token_detail_response,
    normalize_tokens_response,
    require_read_only_route,
)


USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
XNT_MINT = "So11111111111111111111111111111111111111112"
POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"


class FakeJSONResponse:
    def __init__(self, payload, *, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class RecordingGet:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, *, headers, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class FortiSwapReadOnlyProviderTests(unittest.TestCase):
    def test_read_only_allowlist_is_exact(self):
        self.assertEqual(
            classify_route("GET", "/api/tokens")["status"],
            "allowed_read_only",
        )
        self.assertEqual(
            classify_route("GET", f"/api/token/{USDC_X_MINT}")["status"],
            "allowed_read_only",
        )
        self.assertEqual(
            classify_route("GET", "/api/router/volume")["status"],
            "allowed_read_only",
        )
        self.assertEqual(
            classify_route("POST", "/api/quote")["status"],
            "allowed_read_only",
        )

    def test_execution_routes_fail_closed(self):
        for route in (
            "/api/tx/build",
            "/api/tx/send",
            "/api/tx/status",
        ):
            classified = classify_route("POST", route)
            self.assertEqual(classified["status"], "blocked_execution")
            self.assertFalse(classified["execution_authorized"])
            with self.assertRaises(FortiSwapAPIError):
                require_read_only_route("POST", route)

    def test_unknown_new_route_is_not_auto_qualified(self):
        result = classify_route("GET", "/api/bridge/quote")
        self.assertEqual(result["status"], "unqualified")
        self.assertFalse(result["execution_authorized"])

    def test_discovery_preserves_new_routes_but_does_not_promote_them(self):
        payload = {
            "x402Version": 2,
            "items": [
                {
                    "resource": "https://app.fortiblox.com/api/tokens",
                    "method": "GET",
                    "routeTemplate": "/api/tokens",
                    "accepts": [{"scheme": "exact", "amount": "1000"}],
                    "inputSchema": {"type": "object"},
                },
                {
                    "resource": "https://app.fortiblox.com/api/tx/build",
                    "method": "POST",
                    "routeTemplate": "/api/tx/build",
                    "accepts": [{"scheme": "exact", "amount": "5000"}],
                    "bodySchema": {"type": "object"},
                },
                {
                    "resource": "https://app.fortiblox.com/api/bridge/quote",
                    "method": "POST",
                    "routeTemplate": "/api/bridge/quote",
                    "accepts": [{"scheme": "exact", "amount": "1000"}],
                },
            ],
        }

        result = normalize_discovery_catalog(payload)

        self.assertEqual(result["allowed_read_only_count"], 1)
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["bridge_semantics_verified"])
        self.assertEqual(
            [item["qualification"] for item in result["items"]],
            [
                "allowed_read_only",
                "blocked_execution",
                "unqualified",
            ],
        )

    def test_discovery_hash_is_stable_across_json_key_order(self):
        first = {
            "x402Version": 2,
            "items": [
                {
                    "method": "GET",
                    "routeTemplate": "/api/tokens",
                    "resource": "https://app.fortiblox.com/api/tokens",
                }
            ],
        }
        second = {
            "items": [
                {
                    "resource": "https://app.fortiblox.com/api/tokens",
                    "routeTemplate": "/api/tokens",
                    "method": "GET",
                }
            ],
            "x402Version": 2,
        }

        self.assertEqual(
            normalize_discovery_catalog(first)["catalog_hash_sha256"],
            normalize_discovery_catalog(second)["catalog_hash_sha256"],
        )

    def test_tokens_trust_claim_is_not_cmis_verification(self):
        result = normalize_tokens_response(
            {
                "updatedAt": 1788055263960,
                "refreshing": False,
                "warming": False,
                "tokens": [
                    {
                        "mint": XNT_MINT,
                        "symbol": "XNT",
                        "name": "XNT",
                        "decimals": 9,
                        "priceUsd": 0.3856,
                        "sources": ["xdex"],
                        "volume24hUsd": 10947.11,
                        "fdvUsd": 412532004.52,
                        "marketCapUsd": 5372658.76,
                        "change1h": 0,
                        "change1d": -1.47,
                        "trust": "verified",
                    }
                ],
                "errors": [],
            }
        )

        token = result["tokens"][0]
        self.assertEqual(token["provider_trust_claim"], "verified")
        self.assertFalse(token["cmis_verified"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_token_detail_preserves_provider_pool_observation(self):
        result = normalize_token_detail_response(
            {
                "mint": USDC_X_MINT,
                "listed": True,
                "symbol": "USDC.X",
                "name": "USDC.X",
                "decimals": 6,
                "priceUsd": 1,
                "change24hPct": -0.67,
                "trust": "verified",
                "stats": {
                    "tvlUsd": 16040.12,
                    "marketCapUsd": 59823.14,
                    "fdvUsd": 59823.14,
                    "volume24hUsd": 3295.49,
                },
                "about": {"website": None},
                "pools": [
                    {
                        "address": POOL,
                        "tokenA": "WXNT",
                        "tokenB": "USDC.X",
                        "tvl": 15109.84,
                        "apr24h": 22.01,
                        "vol24h": 3292.21,
                    }
                ],
                "updatedAt": 1788055263960,
            }
        )

        self.assertEqual(result["provider_trust_claim"], "verified")
        self.assertEqual(result["pools"][0]["address"], POOL)
        self.assertFalse(result["cmis_verified"])

    def test_router_volume_remains_provider_indexer_scope(self):
        result = normalize_router_volume_response(
            {
                "ok": True,
                "days": 90,
                "from": "2026-06-02",
                "to": "2026-08-30",
                "buckets": [
                    {
                        "date": "2026-08-29",
                        "txCount": 1,
                        "volumeUsd": 12.85,
                        "feeUsd": 0.0321,
                        "uniqueUsers": 1,
                        "pricedShare": 1,
                    }
                ],
                "totals": {
                    "txCount": 87,
                    "volumeUsd": 679.65,
                    "feeUsd": 1.6991,
                    "pricedShare": 1,
                },
                "updatedAt": 1788055287216,
            }
        )

        self.assertEqual(result["scope"], "fortiblox_router_indexer_observation")
        self.assertIn("FortiBlox", result["provider_scope_note"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_quote_normalization_preserves_provider_assertions(self):
        result = normalize_quote_response(
            {
                "mode": "exactIn",
                "inputMint": XNT_MINT,
                "outputMint": USDC_X_MINT,
                "amountIn": "1000000000",
                "amountOut": "384467",
                "amountOutNet": "383505",
                "minimumAmountOut": "383044",
                "slippageBps": 12,
                "slippageDynamic": True,
                "priceImpactPct": 0.00510352,
                "hops": 1,
                "highImpact": False,
                "thinLiquidity": False,
                "warnings": [],
                "route": [
                    {
                        "venue": "xdex",
                        "address": POOL,
                        "inMint": XNT_MINT,
                        "outMint": USDC_X_MINT,
                        "feePpm": 2800,
                        "priceImpactPct": 0.00510352,
                        "amountIn": "1000000000",
                        "amountOut": "384467",
                    }
                ],
                "fee": {
                    "bps": 25,
                    "amount": "962",
                    "pct": 0.25,
                    "net": "383505",
                    "enforcedOnChain": False,
                },
                "confidence": {
                    "score": 100,
                    "level": "high",
                    "band": "excellent",
                },
                "safety": {"level": "safe", "reasons": []},
                "asOfSlot": 75215315,
                "validUntilSlot": 75215360,
                "ttlMs": 17000,
                "expiresAt": 1788055353341,
            }
        )

        self.assertEqual(result["route"][0]["venue"], "xdex")
        self.assertEqual(result["route"][0]["pool_address"], POOL)
        self.assertEqual(result["amount_out_net_raw"], "383505")
        self.assertEqual(result["provider_confidence_claim"]["score"], 100)
        self.assertEqual(result["provider_safety_claim"]["level"], "safe")
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["cmis_risk_promoted"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["transaction_build_allowed"])
        self.assertTrue(result["analysis_only"])

    def test_quote_rejects_non_raw_amounts(self):
        with self.assertRaises(FortiSwapAPIError):
            normalize_quote_response(
                {
                    "mode": "exactIn",
                    "inputMint": XNT_MINT,
                    "outputMint": USDC_X_MINT,
                    "amountIn": "1.0",
                    "route": [],
                }
            )

    def test_quote_rejects_missing_route_shape(self):
        with self.assertRaises(FortiSwapAPIError):
            normalize_quote_response(
                {
                    "mode": "exactIn",
                    "inputMint": XNT_MINT,
                    "outputMint": USDC_X_MINT,
                    "amountIn": "1000",
                }
            )

    def test_fetch_discovery_calls_only_free_discovery_endpoint(self):
        get = RecordingGet(
            [
                FakeJSONResponse(
                    {
                        "x402Version": 2,
                        "items": [],
                    }
                )
            ]
        )

        result = fetch_discovery(get=get)

        self.assertEqual(
            get.calls,
            [
                {
                    "url": "https://app.fortiblox.com" + FORTISWAP_DISCOVERY_PATH,
                    "headers": {"accept": "application/json"},
                    "timeout": 15,
                }
            ],
        )
        self.assertEqual(result["items"], [])
        self.assertFalse(result["execution_authorized"])

    def test_discovery_transport_failure_fails_closed(self):
        get = RecordingGet(
            [
                FakeJSONResponse(
                    {},
                    error=RuntimeError("service unavailable"),
                )
            ]
        )

        with self.assertRaises(FortiSwapAPIError):
            fetch_discovery(get=get)

    def test_provider_only_fetches_discovery(self):
        get = RecordingGet(
            [
                FakeJSONResponse(
                    {
                        "x402Version": 2,
                        "items": [],
                    }
                )
            ]
        )
        provider = FortiSwapReadOnlyProvider(get=get)

        result = provider.get_discovery()

        self.assertEqual(result["scope"], "fortiswap_x402_discovery")
        self.assertEqual(len(get.calls), 1)


if __name__ == "__main__":
    unittest.main()
