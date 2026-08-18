import unittest

from liquidity_scout.providers.x1.xdex import XDEXAPIError, fetch_price_history


class Response:
    def __init__(self, body):
        self._body = body
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class Session:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return Response(self.body)


class XDEXHistoryTransportTests(unittest.TestCase):
    def test_accepts_observed_top_level_bars_without_semantic_renaming(self):
        bars = [
            {
                "o": 1.0,
                "h": 2.0,
                "l": 0.5,
                "c": 1.5,
                "v": 123.0,
                "t": 1786457160,
            }
        ]
        session = Session({"bars": bars})

        result = fetch_price_history(
            "MINT_A",
            "MINT_B",
            time_from=100,
            time_to=200,
            session=session,
        )

        self.assertEqual(result, bars)
        self.assertEqual(set(result[0]), {"o", "h", "l", "c", "v", "t"})
        self.assertNotIn("price", result[0])
        self.assertNotIn("timestamp", result[0])

    def test_preserves_existing_success_data_envelope(self):
        points = [{"timestamp": 123, "price": "0.1"}]
        result = fetch_price_history(
            "MINT_A",
            "MINT_B",
            time_from=100,
            time_to=200,
            session=Session({"success": True, "data": points}),
        )
        self.assertEqual(result, points)

    def test_rejects_non_list_bars(self):
        with self.assertRaisesRegex(XDEXAPIError, "bars must be list"):
            fetch_price_history(
                "MINT_A",
                "MINT_B",
                time_from=100,
                time_to=200,
                session=Session({"bars": {"t": 123}}),
            )

    def test_rejects_non_mapping_bar(self):
        with self.assertRaisesRegex(XDEXAPIError, "point 0 must be a JSON object"):
            fetch_price_history(
                "MINT_A",
                "MINT_B",
                time_from=100,
                time_to=200,
                session=Session({"bars": [123]}),
            )

    def test_rejects_unknown_unsuccessful_envelope(self):
        with self.assertRaisesRegex(XDEXAPIError, "price history failed"):
            fetch_price_history(
                "MINT_A",
                "MINT_B",
                time_from=100,
                time_to=200,
                session=Session({"message": "not available"}),
            )


if __name__ == "__main__":
    unittest.main()
