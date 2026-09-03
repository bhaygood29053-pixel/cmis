import hashlib
import json
import unittest

from liquidity_scout.providers.x1.warp_wallet_history_observation import (
    CONTRACT,
    SOURCE_URL_TEMPLATE,
    list_warp_wallet_history_observations,
)


WALLET = "ECRBHgmcZwgmTAHUbxMgjYYahYmubTaeSHpZ51mF3G3F"
URL = (
    "https://app.bridge.x1.xyz/api/bridge/transactions/wallet/"
    f"{WALLET}?limit=100"
)


def entry(
    *,
    url=URL,
    method="GET",
    referer="https://app.bridge.x1.xyz/history",
    status=200,
    mime_type="application/json",
    body=None,
    size=1269,
    encoding=None,
):
    content = {"mimeType": mime_type, "size": size}
    if body is not None:
        content["text"] = (
            body if isinstance(body, str) else json.dumps(body)
        )
    if encoding is not None:
        content["encoding"] = encoding
    return {
        "request": {
            "method": method,
            "url": url,
            "headers": [{"name": "referer", "value": referer}],
        },
        "response": {
            "status": status,
            "headers": [{"name": "content-type", "value": mime_type}],
            "content": content,
        },
    }


def har(*entries):
    return {"log": {"entries": list(entries)}}


class WarpWalletHistoryObservationTests(unittest.TestCase):
    def test_metadata_only_history_observation_is_sanitized_and_not_semantic(self):
        observations = list_warp_wallet_history_observations(har(entry()))
        self.assertEqual(len(observations), 1)
        result = observations[0]
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["source_url_template"], SOURCE_URL_TEMPLATE)
        self.assertEqual(result["query_limit"], 100)
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["content_type"], "application/json")
        self.assertEqual(result["response_size_bytes"], 1269)
        self.assertFalse(result["response_body_present"])
        self.assertFalse(result["json_parse_verified"])
        self.assertFalse(result["semantic_capture_eligible"])
        self.assertFalse(result["transaction_semantics_accepted"])
        self.assertFalse(result["coverage_semantics_accepted"])
        self.assertFalse(result["wallet_identifier_retained"])
        self.assertFalse(result["exact_wallet_url_retained"])
        self.assertFalse(result["execution_authorized"])

        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(WALLET, serialized)

    def test_parseable_json_body_becomes_review_eligible_not_accepted(self):
        payload = {
            "transactions": [
                {
                    "txSig": "sig1",
                    "status": "executed",
                    "timestamp": 1788445753000,
                }
            ]
        }
        response_text = json.dumps(payload)
        observations = list_warp_wallet_history_observations(
            har(entry(body=response_text))
        )
        self.assertEqual(len(observations), 1)
        result = observations[0]
        self.assertTrue(result["response_body_present"])
        self.assertTrue(result["json_parse_verified"])
        self.assertTrue(result["semantic_capture_eligible"])
        self.assertEqual(
            result["response_sha256"],
            hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
        )
        self.assertFalse(result["transaction_semantics_accepted"])
        self.assertFalse(result["coverage_semantics_accepted"])

    def test_wrong_page_referrer_is_rejected(self):
        self.assertEqual(
            list_warp_wallet_history_observations(
                har(entry(referer="https://app.bridge.x1.xyz/info"))
            ),
            [],
        )

    def test_wrong_limit_or_extra_query_is_rejected(self):
        wrong_limit = URL.replace("limit=100", "limit=99")
        extra = URL + "&page=2"
        self.assertEqual(
            list_warp_wallet_history_observations(har(entry(url=wrong_limit))),
            [],
        )
        self.assertEqual(
            list_warp_wallet_history_observations(har(entry(url=extra))),
            [],
        )

    def test_non_get_non_200_non_json_and_base64_are_rejected(self):
        self.assertEqual(
            list_warp_wallet_history_observations(
                har(
                    entry(method="POST"),
                    entry(status=500),
                    entry(mime_type="text/html"),
                    entry(encoding="base64"),
                )
            ),
            [],
        )

    def test_wallet_path_shape_is_exact(self):
        wrong = (
            "https://app.bridge.x1.xyz/api/bridge/transactions/wallet/"
            "not-a-wallet?limit=100"
        )
        self.assertEqual(
            list_warp_wallet_history_observations(har(entry(url=wrong))),
            [],
        )

    def test_observation_identity_is_deterministic(self):
        first = list_warp_wallet_history_observations(har(entry()))[0]
        second = list_warp_wallet_history_observations(har(entry()))[0]
        self.assertEqual(
            first["observation_sha256"],
            second["observation_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
