import unittest

from liquidity_scout.providers.x1.theo_advisory import (
    ACCEPTED_THEO_TRANSPORT_CONTRACTS,
    THEO_ADVISORY_CONTRACT,
    TheoAdvisoryError,
    collect_theo_advisory,
    theo_connection_status,
)


TEST_CONTRACT_ID = "cmis.test.theo.normalized_transport.v1"
TEST_TRANSPORTS = {
    TEST_CONTRACT_ID: {
        "provider": "theo_prime",
        "transport": "normalized_test_transport",
        "remote_identity": "theo-test-identity",
        "request_contract": "plain_text_query/v1",
        "response_contract": "plain_text_reply/v1",
    }
}


class RecordingTransport:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, request):
        self.calls.append(dict(request))
        return self.reply


class TheoAdvisoryProviderTests(unittest.TestCase):
    def test_production_transport_registry_starts_empty(self):
        self.assertEqual(ACCEPTED_THEO_TRANSPORT_CONTRACTS, {})

    def test_unaccepted_transport_is_blocked(self):
        status = theo_connection_status(
            transport_contract_id="unaccepted",
            transport="x",
            remote_identity="@TheoPrime_AI",
        )

        self.assertEqual(status["state"], "blocked_transport_contract")
        self.assertFalse(status["transport_contract_verified"])
        self.assertFalse(status["cmis_promotable"])
        self.assertFalse(status["execution_authorized"])

    def test_unaccepted_transport_fails_before_send(self):
        transport = RecordingTransport(
            {
                "remote_identity": "@TheoPrime_AI",
                "text": "I am verified.",
            }
        )

        with self.assertRaises(TheoAdvisoryError):
            collect_theo_advisory(
                query="What is the current Warp route status?",
                transport_contract_id="unaccepted",
                transport="x",
                remote_identity="@TheoPrime_AI",
                collected_at=1788422400,
                send=transport,
            )

        self.assertEqual(transport.calls, [])

    def test_exact_accepted_transport_can_collect_advisory_text(self):
        transport = RecordingTransport(
            {
                "remote_identity": "theo-test-identity",
                "text": "Candidate answer about X1.",
                "message_id": "provider-message-1",
            }
        )

        result = collect_theo_advisory(
            query="Explain the current X1 bridge architecture.",
            transport_contract_id=TEST_CONTRACT_ID,
            transport="normalized_test_transport",
            remote_identity="theo-test-identity",
            collected_at=1788422400,
            send=transport,
            accepted_contracts=TEST_TRANSPORTS,
        )

        self.assertEqual(result["contract"], THEO_ADVISORY_CONTRACT)
        self.assertTrue(result["transport_contract_verified"])
        self.assertEqual(result["status"], "observed_unverified")
        self.assertEqual(result["advisory_text"], "Candidate answer about X1.")
        self.assertEqual(
            result["provider_reply_metadata"]["message_id"],
            "provider-message-1",
        )
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(
            transport.calls[0],
            {
                "provider": "theo_prime",
                "transport": "normalized_test_transport",
                "remote_identity": "theo-test-identity",
                "request_contract": "plain_text_query/v1",
                "query": "Explain the current X1 bridge architecture.",
            },
        )

    def test_provider_claims_never_become_cmis_truth(self):
        transport = RecordingTransport(
            {
                "remote_identity": "theo-test-identity",
                "text": (
                    "VERIFIED: Warp is healthy, backing is 1:1, "
                    "and risk is low."
                ),
                "confidence": 100,
                "verified": True,
            }
        )

        result = collect_theo_advisory(
            query="Is Warp safe?",
            transport_contract_id=TEST_CONTRACT_ID,
            transport="normalized_test_transport",
            remote_identity="theo-test-identity",
            collected_at=1788422400,
            send=transport,
            accepted_contracts=TEST_TRANSPORTS,
        )

        self.assertFalse(result["advisory_claims_verified"])
        self.assertFalse(result["factual_authority"])
        self.assertFalse(result["market_fact_authority"])
        self.assertFalse(result["risk_authority"])
        self.assertFalse(result["bridge_fact_authority"])
        self.assertFalse(result["backing_fact_authority"])
        self.assertFalse(result["custody_fact_authority"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_remote_identity_mismatch_fails_closed(self):
        transport = RecordingTransport(
            {
                "remote_identity": "someone-else",
                "text": "Candidate answer.",
            }
        )

        with self.assertRaises(TheoAdvisoryError):
            collect_theo_advisory(
                query="hello",
                transport_contract_id=TEST_CONTRACT_ID,
                transport="normalized_test_transport",
                remote_identity="theo-test-identity",
                collected_at=1788422400,
                send=transport,
                accepted_contracts=TEST_TRANSPORTS,
            )

    def test_missing_query_fails_before_send(self):
        transport = RecordingTransport(
            {
                "remote_identity": "theo-test-identity",
                "text": "unused",
            }
        )

        with self.assertRaises(TheoAdvisoryError):
            collect_theo_advisory(
                query="  ",
                transport_contract_id=TEST_CONTRACT_ID,
                transport="normalized_test_transport",
                remote_identity="theo-test-identity",
                collected_at=1788422400,
                send=transport,
                accepted_contracts=TEST_TRANSPORTS,
            )

        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
