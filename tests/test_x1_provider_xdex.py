import unittest

from liquidity_scout.providers.x1 import (
    XDEX_NETWORK_X1_MAINNET,
    XDEX_SOURCE,
    XDEXAPIError,
    XDEXReadOnlyProvider,
)
from liquidity_scout.providers.x1.xdex import (
    fetch_price_history,
    fetch_swap_quote,
    fetch_token_price,
)


class FakeResponse:
    def __init__(self, body, *, error=None, text=""):
        self.body = body
        self.error = error
        self.text = text

    def raise_for_status(self):
        if self.error is not None:
            try:
                self.error.response = self
            except Exception:
                pass
            raise self.error

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(
            {
                "url": url,
                "params": dict(params),
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class XDEXReadOnlyProviderTests(unittest.TestCase):
    def test_provider_identifies_chain_source_and_live_verified_x1_network_name(self):
        provider = XDEXReadOnlyProvider(session=FakeSession([]))

        self.assertEqual(provider.chain, "x1")
        self.assertEqual(provider.source, "XDEX public API")
        self.assertEqual(XDEX_SOURCE, "XDEX public API")
        self.assertEqual(provider.network, "X1 Mainnet")
        self.assertEqual(XDEX_NETWORK_X1_MAINNET, "X1 Mainnet")

    def test_token_price_uses_live_observed_token_address_parameter(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "success": True,
                        "data": {
                            "price": "0.00006188",
                            "price_change_24h": None,
                            "liquidity": "3366.60",
                        },
                    }
                )
            ]
        )

        result = fetch_token_price("AGI_MINT", session=session)

        self.assertEqual(
            session.calls[0]["params"],
            {
                "network": "X1 Mainnet",
                "token_address": "AGI_MINT",
            },
        )
        self.assertEqual(result["price"], "0.00006188")
        self.assertIsNone(result["price_change_24h"])
        self.assertEqual(result["liquidity"], "3366.60")

    def test_price_history_uses_live_observed_pair_and_time_range_parameters(self):
        points = [
            {"timestamp": "2026-08-15T00:00:00Z", "price": "1.25", "volume": None},
            {"time": 1786830000, "price": 1.5},
        ]
        session = FakeSession([FakeResponse({"success": True, "data": points})])

        result = fetch_price_history(
            "AGI_MINT",
            "XNT_MINT",
            time_from=100,
            time_to=200,
            session=session,
        )

        self.assertEqual(
            session.calls[0]["params"],
            {
                "network": "X1 Mainnet",
                "from_token": "AGI_MINT",
                "to_token": "XNT_MINT",
                "time_from": 100,
                "time_to": 200,
            },
        )
        self.assertEqual(result, points)
        self.assertIsNot(result, points)

    def test_price_history_rejects_invalid_window_before_transport(self):
        session = FakeSession([])

        with self.assertRaisesRegex(ValueError, "must be different"):
            fetch_price_history(
                "SAME",
                "SAME",
                time_from=100,
                time_to=200,
                session=session,
            )

        with self.assertRaisesRegex(ValueError, "time_to must be greater"):
            fetch_price_history(
                "A",
                "B",
                time_from=200,
                time_to=100,
                session=session,
            )

        self.assertEqual(session.calls, [])

    def test_price_history_rejects_non_mapping_point(self):
        session = FakeSession(
            [FakeResponse({"success": True, "data": [{"price": 1}, 5]})]
        )

        with self.assertRaisesRegex(
            XDEXAPIError,
            "price history point 1 must be a JSON object",
        ):
            fetch_price_history(
                "AGI_MINT",
                "XNT_MINT",
                time_from=100,
                time_to=200,
                session=session,
            )

    def test_unsuccessful_provider_response_is_explicit_error(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "success": False,
                        "error": {"message": "token not found"},
                    }
                )
            ]
        )

        with self.assertRaisesRegex(XDEXAPIError, "token not found"):
            fetch_token_price("UNKNOWN", session=session)

    def test_unsuccessful_provider_response_preserves_body_when_message_missing(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "success": False,
                        "data": [],
                        "status": "unavailable",
                    }
                )
            ]
        )

        with self.assertRaisesRegex(XDEXAPIError, "status.*unavailable"):
            fetch_price_history(
                "AGI_MINT",
                "XNM_MINT",
                time_from=100,
                time_to=200,
                session=session,
            )

    def test_swap_quote_uses_live_verified_x1_mainnet_request_shape(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "success": True,
                        "data": {
                            "outputAmount": 12.5,
                            "rate": 12.5,
                            "priceImpactPct": 0.001,
                        },
                    }
                )
            ]
        )

        result = fetch_swap_quote(
            "XNT_MINT",
            "XNM_MINT",
            "1.2500",
            session=session,
        )

        self.assertEqual(
            session.calls[0]["params"],
            {
                "network": "X1 Mainnet",
                "token_in": "XNT_MINT",
                "token_out": "XNM_MINT",
                "token_in_amount": "1.2500",
                "is_exact_amount_in": "true",
            },
        )
        self.assertEqual(result["outputAmount"], 12.5)
        self.assertEqual(result["rate"], 12.5)
        self.assertEqual(result["priceImpactPct"], 0.001)

    def test_swap_quote_can_request_exact_amount_out_without_boolean_coercion(self):
        session = FakeSession(
            [FakeResponse({"success": True, "data": {"outputAmount": "1"}})]
        )

        fetch_swap_quote(
            "TOKEN_A",
            "TOKEN_B",
            2,
            is_exact_amount_in=False,
            session=session,
        )

        self.assertEqual(
            session.calls[0]["params"]["is_exact_amount_in"],
            "false",
        )

    def test_swap_quote_rejects_invalid_trade_inputs_before_transport(self):
        session = FakeSession([])

        with self.assertRaisesRegex(ValueError, "must be different"):
            fetch_swap_quote("SAME", "SAME", 1, session=session)

        with self.assertRaisesRegex(ValueError, "positive finite"):
            fetch_swap_quote("A", "B", 0, session=session)

        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            fetch_swap_quote(
                "A",
                "B",
                1,
                is_exact_amount_in="true",
                session=session,
            )

        self.assertEqual(session.calls, [])

    def test_malformed_data_shapes_fail_closed(self):
        mapping_expected = FakeSession(
            [FakeResponse({"success": True, "data": []})]
        )
        with self.assertRaisesRegex(XDEXAPIError, "token price response data"):
            fetch_token_price("AGI_MINT", session=mapping_expected)

        list_expected = FakeSession(
            [FakeResponse({"success": True, "data": {}})]
        )
        with self.assertRaisesRegex(XDEXAPIError, "price history response data"):
            fetch_price_history(
                "AGI_MINT",
                "XNT_MINT",
                time_from=100,
                time_to=200,
                session=list_expected,
            )

        quote_expected = FakeSession(
            [FakeResponse({"success": True, "data": []})]
        )
        with self.assertRaisesRegex(XDEXAPIError, "swap quote response data"):
            fetch_swap_quote("A", "B", 1, session=quote_expected)

    def test_transport_failure_becomes_provider_error(self):
        session = FakeSession(
            [FakeResponse(None, error=RuntimeError("network down"))]
        )

        with self.assertRaisesRegex(XDEXAPIError, "network down"):
            fetch_token_price("AGI_MINT", session=session)

    def test_http_failure_preserves_bounded_provider_response_text(self):
        session = FakeSession(
            [
                FakeResponse(
                    None,
                    error=RuntimeError("400 Bad Request"),
                    text='{"error":"invalid network"}',
                )
            ]
        )

        with self.assertRaisesRegex(
            XDEXAPIError,
            'response: \\{"error":"invalid network"\\}',
        ):
            fetch_token_price("AGI_MINT", session=session)

    def test_provider_methods_delegate_to_read_only_transports(self):
        session = FakeSession(
            [
                FakeResponse({"success": True, "data": {"price": 1}}),
                FakeResponse(
                    {
                        "success": True,
                        "data": [{"timestamp": 1, "price": 1}],
                    }
                ),
                FakeResponse(
                    {
                        "success": True,
                        "data": {"outputAmount": 2},
                    }
                ),
            ]
        )
        provider = XDEXReadOnlyProvider(session=session, timeout=9)

        self.assertEqual(provider.token_price("T")["price"], 1)
        self.assertEqual(
            provider.price_history(
                "T",
                "U",
                time_from=100,
                time_to=200,
            )[0]["price"],
            1,
        )
        self.assertEqual(provider.swap_quote("T", "U", 1)["outputAmount"], 2)
        self.assertTrue(all(call["timeout"] == 9 for call in session.calls))


if __name__ == "__main__":
    unittest.main()
