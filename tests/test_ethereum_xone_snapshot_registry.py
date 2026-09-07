from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum import (
    EthereumXoneSnapshotRegistryError,
    XONE_CONTRACT,
    XONE_CREATION_BLOCK,
    XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
    discover_official_snapshot_candidates,
    extract_xone_snapshot_claims,
    fetch_and_verify_xone_registry,
    promote_official_snapshot,
    reconstruct_xone_registry,
)
from liquidity_scout.providers.ethereum.xone_event_observer import (
    TRANSFER_TOPIC,
    ZERO_ADDRESS,
    parse_xone_transfer_log,
)
from liquidity_scout.providers.ethereum.xone_snapshot_registry import (
    BALANCE_OF_SELECTOR,
    TOTAL_SUPPLY_SELECTOR,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


ALICE = "0x1111111111111111111111111111111111111111"
BOB = "0x2222222222222222222222222222222222222222"
BLOCK_HASH = "0x" + ("ab" * 32)


def topic_address(address: str) -> str:
    return "0x" + ("0" * 24) + address[2:].lower()


def word_uint(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


def raw_transfer(
    *,
    block: int,
    index: int,
    from_address: str,
    to_address: str,
    amount: int,
    tx_byte: str,
):
    return {
        "address": XONE_CONTRACT,
        "topics": [
            TRANSFER_TOPIC,
            topic_address(from_address),
            topic_address(to_address),
        ],
        "data": word_uint(amount),
        "transactionHash": "0x" + (tx_byte * 32),
        "blockHash": BLOCK_HASH,
        "blockNumber": hex(block),
        "logIndex": hex(index),
        "removed": False,
    }


def parsed_events():
    return [
        parse_xone_transfer_log(
            raw_transfer(
                block=XONE_CREATION_BLOCK,
                index=0,
                from_address=ZERO_ADDRESS,
                to_address=ALICE,
                amount=500,
                tx_byte="11",
            )
        ),
        parse_xone_transfer_log(
            raw_transfer(
                block=XONE_CREATION_BLOCK + 1,
                index=0,
                from_address=ALICE,
                to_address=BOB,
                amount=100,
                tx_byte="12",
            )
        ),
        parse_xone_transfer_log(
            raw_transfer(
                block=XONE_CREATION_BLOCK + 1,
                index=1,
                from_address=BOB,
                to_address=ZERO_ADDRESS,
                amount=20,
                tx_byte="13",
            )
        ),
    ]


class FakeSnapshotRPC:
    def __init__(self):
        self.calls = []
        self.logs = {
            XONE_CREATION_BLOCK: [raw_transfer(
                block=XONE_CREATION_BLOCK,
                index=0,
                from_address=ZERO_ADDRESS,
                to_address=ALICE,
                amount=500,
                tx_byte="11",
            )],
            XONE_CREATION_BLOCK + 1: [
                raw_transfer(
                    block=XONE_CREATION_BLOCK + 1,
                    index=0,
                    from_address=ALICE,
                    to_address=BOB,
                    amount=100,
                    tx_byte="12",
                ),
                raw_transfer(
                    block=XONE_CREATION_BLOCK + 1,
                    index=1,
                    from_address=BOB,
                    to_address=ZERO_ADDRESS,
                    amount=20,
                    tx_byte="13",
                ),
            ],
        }

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return "0x1"
        if method == "eth_getBlockByNumber":
            return {
                "number": params[0],
                "hash": BLOCK_HASH,
                "timestamp": hex(1_700_000_000),
            }
        if method == "eth_getLogs":
            query = params[0]
            start = int(query["fromBlock"], 16)
            end = int(query["toBlock"], 16)
            rows = []
            for block in range(start, end + 1):
                rows.extend(self.logs.get(block, []))
            return rows
        if method == "eth_call":
            call = params[0]
            data = call["data"].lower()
            if data == TOTAL_SUPPLY_SELECTOR:
                return word_uint(480)
            if data.startswith(BALANCE_OF_SELECTOR):
                address = "0x" + data[-40:]
                expected = {
                    ALICE: 400,
                    BOB: 80,
                }.get(address, 0)
                return word_uint(expected)
        raise AssertionError(f"unexpected RPC call {method} {params}")


class XoneSnapshotRegistryTests(unittest.TestCase):
    def test_extracts_explicit_authoritative_snapshot_block(self):
        text = (
            "The XONE holder snapshot for XNT allocation was taken on "
            "October 5, 2025 at Ethereum block 23500000. "
            f"The snapshot uses XONE contract {XONE_CONTRACT}."
        )
        claims = extract_xone_snapshot_claims(
            text,
            source_id="jack-post",
            source_role="jack_levin_direct",
            url="https://example.test/jack",
            observed_at=100.0,
        )
        self.assertEqual(len(claims), 1)
        claim = claims[0]
        self.assertTrue(claim["authoritative_source"])
        self.assertEqual(claim["snapshot_block_candidates"], [23_500_000])
        self.assertTrue(claim["exact_xone_contract_mentioned"])
        self.assertTrue(claim["xnt_allocation_binding_claimed"])
        self.assertFalse(claim["official_xone_snapshot_verified"])

        discovery = discover_official_snapshot_candidates(claims)
        self.assertEqual(discovery["official_snapshot_candidate_count"], 1)
        self.assertEqual(discovery["authoritative_exact_block_candidates"], [23_500_000])
        self.assertTrue(
            discovery["candidates"][0]["eligible_for_direct_registry_reconstruction"]
        )
        self.assertFalse(discovery["official_xone_snapshot_verified"])

    def test_holder_count_without_snapshot_language_is_not_candidate(self):
        claims = extract_xone_snapshot_claims(
            "XONE has 12,000 holders on Ethereum and XNT is on X1.",
            source_id="secondary",
            source_role="secondary_report",
            url="https://example.test",
            observed_at=1.0,
        )
        self.assertEqual(claims, [])

    def test_secondary_snapshot_claim_cannot_be_official_candidate_for_reconstruction(self):
        claims = extract_xone_snapshot_claims(
            "XONE was reportedly snapshotted at Ethereum block 23500000 for XNT.",
            source_id="report",
            source_role="x1_report",
            url="https://x1report.com/example",
            observed_at=1.0,
        )
        discovery = discover_official_snapshot_candidates(claims)
        self.assertEqual(discovery["official_snapshot_candidate_count"], 1)
        self.assertFalse(
            discovery["candidates"][0]["eligible_for_direct_registry_reconstruction"]
        )

    def test_reconstructs_registry_and_supply(self):
        result = reconstruct_xone_registry(
            parsed_events(),
            snapshot_block=XONE_CREATION_BLOCK + 1,
            snapshot_block_hash=BLOCK_HASH,
            snapshot_timestamp=1_700_000_000,
            coverage_ranges=[
                (XONE_CREATION_BLOCK, XONE_CREATION_BLOCK),
                (XONE_CREATION_BLOCK + 1, XONE_CREATION_BLOCK + 1),
            ],
            total_supply_base_units=480,
        )
        self.assertEqual(
            result["contract_version"],
            XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
        )
        self.assertTrue(result["reconstructed_registry_verified"])
        self.assertTrue(result["historical_total_supply_matches"])
        self.assertEqual(result["holder_count"], 2)
        balances = {
            row["address"]: int(row["balance_base_units"])
            for row in result["registry"]
        }
        self.assertEqual(balances, {ALICE: 400, BOB: 80})
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_missing_log_coverage_fails_closed(self):
        with self.assertRaisesRegex(
            EthereumXoneSnapshotRegistryError,
            "coverage is not contiguous",
        ):
            reconstruct_xone_registry(
                parsed_events(),
                snapshot_block=XONE_CREATION_BLOCK + 1,
                snapshot_block_hash=BLOCK_HASH,
                snapshot_timestamp=1_700_000_000,
                coverage_ranges=[
                    (XONE_CREATION_BLOCK + 1, XONE_CREATION_BLOCK + 1),
                ],
                total_supply_base_units=480,
            )

    def test_duplicate_event_identity_fails_closed(self):
        events = parsed_events()
        with self.assertRaisesRegex(
            EthereumXoneSnapshotRegistryError,
            "duplicate XONE event identity",
        ):
            reconstruct_xone_registry(
                events + [events[0]],
                snapshot_block=XONE_CREATION_BLOCK + 1,
                snapshot_block_hash=BLOCK_HASH,
                snapshot_timestamp=1_700_000_000,
                coverage_ranges=[
                    (XONE_CREATION_BLOCK, XONE_CREATION_BLOCK + 1),
                ],
                total_supply_base_units=480,
            )

    def test_supply_mismatch_fails_closed(self):
        with self.assertRaisesRegex(
            EthereumXoneSnapshotRegistryError,
            "do not equal historical totalSupply",
        ):
            reconstruct_xone_registry(
                parsed_events(),
                snapshot_block=XONE_CREATION_BLOCK + 1,
                snapshot_block_hash=BLOCK_HASH,
                snapshot_timestamp=1_700_000_000,
                coverage_ranges=[
                    (XONE_CREATION_BLOCK, XONE_CREATION_BLOCK + 1),
                ],
                total_supply_base_units=481,
            )

    def test_fetch_verifies_historical_total_supply_and_balance_samples(self):
        rpc = FakeSnapshotRPC()
        result = fetch_and_verify_xone_registry(
            rpc_call=rpc,
            snapshot_block=XONE_CREATION_BLOCK + 1,
            source_url="https://rpc.example",
            log_chunk_blocks=1,
            balance_sample_size=2,
        )
        self.assertTrue(result["reconstructed_registry_verified"])
        self.assertTrue(result["historical_balance_sample_verified"])
        self.assertEqual(result["historical_balance_sample_size"], 2)
        self.assertEqual(result["total_supply_base_units"], "480")
        self.assertFalse(result["official_xone_snapshot_verified"])

        log_calls = [params for method, params in rpc.calls if method == "eth_getLogs"]
        self.assertEqual(len(log_calls), 2)
        self.assertEqual(log_calls[0][0]["address"], XONE_CONTRACT)
        self.assertEqual(log_calls[0][0]["topics"], [TRANSFER_TOPIC])

    def test_official_promotion_requires_authoritative_exact_matching_block(self):
        registry = reconstruct_xone_registry(
            parsed_events(),
            snapshot_block=XONE_CREATION_BLOCK + 1,
            snapshot_block_hash=BLOCK_HASH,
            snapshot_timestamp=1_700_000_000,
            coverage_ranges=[
                (XONE_CREATION_BLOCK, XONE_CREATION_BLOCK + 1),
            ],
            total_supply_base_units=480,
        )
        candidate = {
            "claim_id": "claim-1",
            "source_role": "jack_levin_direct",
            "url": "https://example.test/jack",
            "authoritative_source": True,
            "snapshot_block_candidates": [XONE_CREATION_BLOCK + 1],
        }
        result = promote_official_snapshot(
            source_candidate=candidate,
            registry_proof=registry,
        )
        self.assertTrue(result["official_xone_snapshot_verified"])
        self.assertTrue(result["reconstructed_registry_verified"])
        self.assertFalse(result["official_registry_artifact_verified"])
        self.assertFalse(result["xone_snapshot_eligibility_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["execution_authorized"])

        secondary = dict(candidate)
        secondary["authoritative_source"] = False
        with self.assertRaisesRegex(
            EthereumXoneSnapshotRegistryError,
            "requires an authoritative source",
        ):
            promote_official_snapshot(
                source_candidate=secondary,
                registry_proof=registry,
            )

    def test_service_snapshot_discovery_preserves_boundaries(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.discover_ethereum_xone_snapshot_candidates(
            [
                {
                    "source_id": "official",
                    "source_role": "x1_official",
                    "url": "https://x1.xyz/example",
                    "text": (
                        "XONE snapshot was taken at Ethereum block 23500000 "
                        "for a future registry."
                    ),
                }
            ],
            observed_at=100.0,
        )
        self.assertTrue(result["xone_snapshot_source_discovery_verified"])
        self.assertEqual(
            result["snapshot_discovery"]["official_snapshot_candidate_count"],
            1,
        )
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["xone_snapshot_eligibility_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
