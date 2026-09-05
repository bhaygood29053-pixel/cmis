from __future__ import annotations

import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    X1_EXPLORER_IMPLEMENTATION_COMMIT,
    X1_EXPLORER_STRUCTURED_CONTRACT,
    extract_related_x1_explorer_entities,
    parse_x1_explorer_url,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


ADDRESS = "11111111111111111111111111111111"
SIGNATURE = "1" * 64


class FakeResponse:
    def __init__(
        self,
        body,
        *,
        url,
        status_code=200,
        content_type="text/html; charset=utf-8",
    ):
        self.content = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class X1ExplorerStructuredDiscoveryTests(unittest.TestCase):
    def test_transaction_route_matches_64_byte_base58_search_rule(self):
        result = parse_x1_explorer_url(
            f"https://explorer.mainnet.x1.xyz/tx/{SIGNATURE}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["contract"], X1_EXPLORER_STRUCTURED_CONTRACT)
        self.assertEqual(result["entity_type"], "transaction")
        self.assertEqual(result["identifier"], SIGNATURE)
        self.assertEqual(result["decoded_base58_bytes"], 64)
        self.assertTrue(result["truth_state"]["explorer_route_verified"])
        self.assertFalse(result["truth_state"]["entity_identity_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["execution_authorized"])

        methods = {row["rpc_method"] for row in result["verification_handoff"]}
        self.assertIn("getSignatureStatuses", methods)
        self.assertIn("getBlockTime", methods)
        self.assertIn("getTransaction", methods)

    def test_address_route_matches_32_byte_base58_search_rule(self):
        result = parse_x1_explorer_url(
            f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["entity_type"], "address")
        self.assertEqual(result["identifier"], ADDRESS)
        self.assertEqual(result["decoded_base58_bytes"], 32)
        self.assertIsNone(result["address_subview"])
        self.assertFalse(result["truth_state"]["address_subtype_verified"])

        methods = {row["rpc_method"] for row in result["verification_handoff"]}
        self.assertIn("getMultipleAccounts", methods)
        self.assertIn("getSignaturesForAddress", methods)
        self.assertIn("getTransaction", methods)

    def test_address_subview_is_route_hint_not_address_subtype(self):
        result = parse_x1_explorer_url(
            f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}/transfers"
        )

        self.assertTrue(result["supported"])
        self.assertEqual(result["entity_type"], "address")
        self.assertEqual(result["address_subview"], "transfers")
        self.assertFalse(result["truth_state"]["address_subtype_verified"])
        self.assertFalse(result["truth_state"]["web_claim_verified"])

    def test_unknown_address_subview_fails_closed(self):
        result = parse_x1_explorer_url(
            f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}/wallet-owner"
        )

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "unsupported_address_subview")
        self.assertFalse(result["truth_state"]["explorer_route_verified"])

    def test_invalid_base58_lengths_are_not_guessed(self):
        short_address = parse_x1_explorer_url(
            "https://explorer.mainnet.x1.xyz/address/1111"
        )
        short_signature = parse_x1_explorer_url(
            "https://explorer.mainnet.x1.xyz/tx/1111"
        )
        invalid_character = parse_x1_explorer_url(
            "https://explorer.mainnet.x1.xyz/address/0"
        )

        self.assertFalse(short_address["supported"])
        self.assertEqual(
            short_address["reason"],
            "address_must_decode_to_32_bytes",
        )
        self.assertFalse(short_signature["supported"])
        self.assertEqual(
            short_signature["reason"],
            "transaction_signature_must_decode_to_64_bytes",
        )
        self.assertFalse(invalid_character["supported"])
        self.assertEqual(
            invalid_character["reason"],
            "address_must_decode_to_32_bytes",
        )

    def test_block_and_epoch_routes_are_structured_without_promotion(self):
        block = parse_x1_explorer_url(
            "https://explorer.mainnet.x1.xyz/block/76529110"
        )
        epoch = parse_x1_explorer_url(
            "https://explorer.mainnet.x1.xyz/epoch/123"
        )

        self.assertTrue(block["supported"])
        self.assertEqual(block["entity_type"], "block")
        self.assertEqual(block["identifier"], 76529110)
        self.assertTrue(
            any(
                row["rpc_method"] == "getBlock" and row["required"]
                for row in block["verification_handoff"]
            )
        )

        self.assertTrue(epoch["supported"])
        self.assertEqual(epoch["entity_type"], "epoch")
        self.assertEqual(epoch["identifier"], 123)
        self.assertEqual(epoch["verification_handoff"], [])
        self.assertFalse(epoch["truth_state"]["entity_identity_verified"])

    def test_malformed_or_unrelated_routes_remain_unsupported(self):
        root = parse_x1_explorer_url("https://explorer.mainnet.x1.xyz/")
        extra = parse_x1_explorer_url(
            f"https://explorer.mainnet.x1.xyz/tx/{SIGNATURE}/extra"
        )
        nonnumeric = parse_x1_explorer_url(
            "https://explorer.mainnet.x1.xyz/block/latest"
        )

        self.assertFalse(root["supported"])
        self.assertEqual(root["reason"], "unsupported_x1_explorer_route")
        self.assertFalse(extra["supported"])
        self.assertEqual(extra["reason"], "unsupported_x1_explorer_route")
        self.assertFalse(nonnumeric["supported"])
        self.assertEqual(
            nonnumeric["reason"],
            "block_identifier_must_be_nonnegative_integer",
        )

    def test_related_entity_extraction_is_bounded_and_deduplicated(self):
        links = [
            f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}",
            f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}/tokens",
            f"https://explorer.mainnet.x1.xyz/tx/{SIGNATURE}",
            "https://explorer.mainnet.x1.xyz/block/42",
            "https://explorer.mainnet.x1.xyz/not-supported/value",
        ]

        results = extract_related_x1_explorer_entities(links, max_entities=3)

        self.assertEqual(len(results), 3)
        self.assertEqual(
            [(row["entity_type"], str(row["identifier"])) for row in results],
            [
                ("address", ADDRESS),
                ("transaction", SIGNATURE),
                ("block", "42"),
            ],
        )

    def test_source_implementation_evidence_is_pinned_but_not_deployment_truth(self):
        result = parse_x1_explorer_url(
            f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}"
        )

        evidence = result["implementation_evidence"]
        self.assertEqual(
            evidence["commit"],
            X1_EXPLORER_IMPLEMENTATION_COMMIT,
        )
        self.assertEqual(
            evidence["repository"],
            "x1-labs/x1-explorer",
        )
        self.assertFalse(evidence["deployment_identity_verified"])
        self.assertFalse(evidence["implementation_semantics_verified_by_cmis"])

    def test_service_can_combine_structured_route_with_bounded_page_links(self):
        url = f"https://explorer.mainnet.x1.xyz/address/{ADDRESS}"
        body = (
            "<html><body>"
            f'<a href="/tx/{SIGNATURE}">tx</a>'
            '<a href="/block/42">block</a>'
            "</body></html>"
        )
        session = FakeSession(FakeResponse(body, url=url))
        service = CMISWebDiscoveryService()

        result = service.discover_x1_explorer_structured(
            url,
            include_page=True,
            provider_kwargs={"session": session},
        )

        self.assertEqual(result["structured_route"]["entity_type"], "address")
        self.assertEqual(len(result["related_entities"]), 2)
        self.assertEqual(
            [row["entity_type"] for row in result["related_entities"]],
            ["transaction", "block"],
        )
        self.assertEqual(
            result["structured_route"]["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
