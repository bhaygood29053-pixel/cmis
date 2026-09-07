from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum.xone_event_observer import (
    CONTRACT_VERSION,
    EthereumXoneEventError,
    TRANSFER_TOPIC,
    ZERO_ADDRESS,
    corroborate_xone_event_observations,
    observe_xone_transfer_events,
    parse_xone_transfer_log,
)
from liquidity_scout.providers.ethereum.xone_identity import (
    CHAIN_ID,
    XONE_CONTRACT,
    XONE_CREATION_TX,
    XONE_DEPLOYER,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


def topic_address(address: str) -> str:
    lowered = address.casefold()
    return "0x" + ("0" * 24) + lowered[2:]


def uint256(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


def abi_string(value: str) -> str:
    encoded = value.encode("utf-8")
    padded = encoded + (b"\x00" * ((32 - len(encoded) % 32) % 32))
    return "0x" + (
        (32).to_bytes(32, "big")
        + len(encoded).to_bytes(32, "big")
        + padded
    ).hex()


def transfer_log(
    *,
    from_address: str,
    to_address: str,
    amount: int,
    tx_byte: str = "11",
    block_byte: str = "22",
    block_number: int = 18_609_736,
    log_index: int = 0,
    address: str = XONE_CONTRACT,
    topic0: str = TRANSFER_TOPIC,
    removed: bool = False,
):
    return {
        "address": address,
        "topics": [
            topic0,
            topic_address(from_address),
            topic_address(to_address),
        ],
        "data": uint256(amount),
        "transactionHash": "0x" + (tx_byte * 32),
        "blockHash": "0x" + (block_byte * 32),
        "blockNumber": hex(block_number),
        "logIndex": hex(log_index),
        "removed": removed,
    }


class FullFakeRPC:
    def __init__(self, logs=None, *, recipient_code="0x6001"):
        self.logs = list(logs or [])
        self.recipient_code = recipient_code
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return CHAIN_ID
        if method == "eth_getTransactionByHash":
            return {
                "hash": XONE_CREATION_TX,
                "from": XONE_DEPLOYER,
                "to": None,
                "blockNumber": "0x11bf648",
                "input": "0x6000",
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": XONE_CREATION_TX,
                "contractAddress": XONE_CONTRACT,
                "status": "0x1",
                "blockNumber": "0x11bf648",
            }
        if method == "eth_getCode":
            if params[0].casefold() == XONE_CONTRACT:
                return "0x6001600055"
            return self.recipient_code
        if method == "eth_call":
            selector = params[0]["data"]
            if selector == "0x06fdde03":
                return abi_string("XONE")
            if selector == "0x95d89b41":
                return abi_string("XONE")
            if selector == "0x313ce567":
                return uint256(18)
        if method == "eth_getLogs":
            return list(self.logs)
        if method == "eth_getBlockByNumber":
            return {
                "number": params[0],
                "timestamp": hex(1_700_000_000),
            }
        raise AssertionError(f"unexpected RPC call {method} {params}")


class EthereumXoneEventObserverTests(unittest.TestCase):
    def test_burn_transfer_is_verified_but_not_conversion(self):
        owner = "0x" + ("ab" * 20)
        event = parse_xone_transfer_log(
            transfer_log(
                from_address=owner,
                to_address=ZERO_ADDRESS,
                amount=5 * 10**18,
            ),
            block_timestamp=1_700_000_000,
        )
        self.assertEqual(event["contract_version"], CONTRACT_VERSION)
        self.assertEqual(event["event_type"], "burn")
        self.assertEqual(event["amount_xone"], "5")
        self.assertTrue(event["ethereum_event_verified"])
        self.assertTrue(event["xone_burn_verified"])
        self.assertFalse(event["lock_or_migration_verified"])
        self.assertFalse(event["xone_xnt_conversion_verified"])
        self.assertFalse(event["xnt_issuance_verified"])
        self.assertFalse(event["cross_chain_correlation_verified"])
        self.assertFalse(event["public_service_promoted"])
        self.assertFalse(event["scout_reliance_promoted"])
        self.assertFalse(event["execution_authorized"])

    def test_mint_and_transfer_are_classified_without_migration_inference(self):
        alice = "0x" + ("aa" * 20)
        bob = "0x" + ("bb" * 20)
        mint = parse_xone_transfer_log(
            transfer_log(
                from_address=ZERO_ADDRESS,
                to_address=alice,
                amount=123,
            )
        )
        move = parse_xone_transfer_log(
            transfer_log(
                from_address=alice,
                to_address=bob,
                amount=10**18 + 50,
                tx_byte="12",
            ),
            recipient_current_code_present=True,
        )
        self.assertEqual(mint["event_type"], "mint")
        self.assertTrue(mint["xone_mint_verified"])
        self.assertFalse(mint["xone_burn_verified"])
        self.assertEqual(move["event_type"], "transfer")
        self.assertEqual(move["amount_xone"], "1.00000000000000005")
        self.assertTrue(move["contract_recipient_candidate"])
        self.assertTrue(move["lock_or_migration_candidate"])
        self.assertFalse(move["lock_or_migration_verified"])

    def test_parser_fails_closed_on_wrong_or_malformed_logs(self):
        alice = "0x" + ("aa" * 20)
        bob = "0x" + ("bb" * 20)
        base = transfer_log(from_address=alice, to_address=bob, amount=1)

        wrong_emitter = dict(base)
        wrong_emitter["address"] = "0x" + ("cc" * 20)
        with self.assertRaisesRegex(EthereumXoneEventError, "exact XONE contract"):
            parse_xone_transfer_log(wrong_emitter)

        wrong_topic = dict(base)
        wrong_topic["topics"] = list(base["topics"])
        wrong_topic["topics"][0] = "0x" + ("33" * 32)
        with self.assertRaisesRegex(EthereumXoneEventError, "not ERC-20 Transfer"):
            parse_xone_transfer_log(wrong_topic)

        malformed = dict(base)
        malformed["data"] = "0x01"
        with self.assertRaisesRegex(EthereumXoneEventError, "32-byte uint256"):
            parse_xone_transfer_log(malformed)

        removed = dict(base)
        removed["removed"] = True
        with self.assertRaisesRegex(EthereumXoneEventError, "removed/reorged"):
            parse_xone_transfer_log(removed)

        zero_zero = transfer_log(
            from_address=ZERO_ADDRESS,
            to_address=ZERO_ADDRESS,
            amount=1,
        )
        with self.assertRaisesRegex(EthereumXoneEventError, "semantically ambiguous"):
            parse_xone_transfer_log(zero_zero)

    def test_observer_queries_exact_contract_and_counts_events(self):
        alice = "0x" + ("aa" * 20)
        bob = "0x" + ("bb" * 20)
        logs = [
            transfer_log(
                from_address=ZERO_ADDRESS,
                to_address=alice,
                amount=100,
                log_index=0,
            ),
            transfer_log(
                from_address=alice,
                to_address=bob,
                amount=10,
                tx_byte="12",
                log_index=1,
            ),
            transfer_log(
                from_address=alice,
                to_address=ZERO_ADDRESS,
                amount=5,
                tx_byte="13",
                log_index=2,
            ),
        ]
        rpc = FullFakeRPC(logs)
        result = observe_xone_transfer_events(
            rpc_call=rpc,
            from_block=18_609_736,
            to_block=18_609_736,
            source_url="https://rpc-one.example",
            enrich_recipient_code=True,
        )
        self.assertTrue(result["ethereum_log_window_verified"])
        self.assertTrue(result["ethereum_event_verified"])
        self.assertTrue(result["xone_burn_verified"])
        self.assertEqual(result["event_count"], 3)
        self.assertEqual(result["mint_count"], 1)
        self.assertEqual(result["transfer_count"], 1)
        self.assertEqual(result["burn_count"], 1)
        self.assertFalse(result["lock_or_migration_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["lifetime_activity_complete"])
        get_logs = [params for method, params in rpc.calls if method == "eth_getLogs"]
        self.assertEqual(len(get_logs), 1)
        self.assertEqual(get_logs[0][0]["address"], XONE_CONTRACT)
        self.assertEqual(get_logs[0][0]["topics"], [TRANSFER_TOPIC])

    def test_zero_event_window_is_not_lifetime_zero(self):
        result = observe_xone_transfer_events(
            rpc_call=FullFakeRPC([]),
            from_block=1,
            to_block=2,
            source_url="https://rpc-one.example",
        )
        self.assertEqual(result["event_count"], 0)
        self.assertTrue(result["ethereum_log_window_verified"])
        self.assertFalse(result["ethereum_event_verified"])
        self.assertTrue(result["zero_events_mean_only_no_matching_logs_in_window"])
        self.assertFalse(result["lifetime_activity_complete"])

    def test_oversized_window_requires_pagination(self):
        with self.assertRaisesRegex(EthereumXoneEventError, "paginate"):
            observe_xone_transfer_events(
                rpc_call=FullFakeRPC([]),
                from_block=1,
                to_block=5001,
                max_blocks=5000,
            )

    def test_multi_rpc_corroboration_requires_distinct_matching_observations(self):
        alice = "0x" + ("aa" * 20)
        log = transfer_log(
            from_address=alice,
            to_address=ZERO_ADDRESS,
            amount=99,
        )
        one = observe_xone_transfer_events(
            rpc_call=FullFakeRPC([log]),
            from_block=18_609_736,
            to_block=18_609_736,
            source_url="https://rpc-one.example",
        )
        two = observe_xone_transfer_events(
            rpc_call=FullFakeRPC([log]),
            from_block=18_609_736,
            to_block=18_609_736,
            source_url="https://rpc-two.example",
        )
        result = corroborate_xone_event_observations([one, two])
        self.assertTrue(result["multi_rpc_corroborated"])
        self.assertEqual(result["rpc_proof_count"], 2)
        self.assertTrue(result["ethereum_event_verified"])
        self.assertTrue(result["xone_burn_verified"])
        self.assertFalse(result["lock_or_migration_verified"])
        self.assertFalse(result["execution_authorized"])

        same_host = dict(two)
        same_host["source_url"] = "https://rpc-one.example/other"
        with self.assertRaisesRegex(EthereumXoneEventError, "distinct RPC transport"):
            corroborate_xone_event_observations([one, same_host])

    def test_multi_rpc_event_disagreement_fails_closed(self):
        alice = "0x" + ("aa" * 20)
        one = observe_xone_transfer_events(
            rpc_call=FullFakeRPC([
                transfer_log(
                    from_address=alice,
                    to_address=ZERO_ADDRESS,
                    amount=99,
                )
            ]),
            from_block=18_609_736,
            to_block=18_609_736,
            source_url="https://rpc-one.example",
        )
        two = observe_xone_transfer_events(
            rpc_call=FullFakeRPC([
                transfer_log(
                    from_address=alice,
                    to_address=ZERO_ADDRESS,
                    amount=100,
                )
            ]),
            from_block=18_609_736,
            to_block=18_609_736,
            source_url="https://rpc-two.example",
        )
        with self.assertRaisesRegex(EthereumXoneEventError, "canonical events"):
            corroborate_xone_event_observations([one, two])

    def test_conversion_service_verifies_identity_before_event_handoff(self):
        alice = "0x" + ("aa" * 20)
        rpc = FullFakeRPC([
            transfer_log(
                from_address=alice,
                to_address=ZERO_ADDRESS,
                amount=7,
            )
        ])
        service = CMISXoneXntConversionIntelligenceService()
        result = service.observe_ethereum_xone_events(
            rpc_call=rpc,
            from_block=18_609_736,
            to_block=18_609_736,
            source_url="https://rpc-one.example",
        )
        self.assertTrue(result["ethereum_xone_identity_verified"])
        self.assertTrue(result["ethereum_event_window_verified"])
        self.assertTrue(result["ethereum_event_verified"])
        self.assertTrue(result["xone_burn_verified"])
        self.assertFalse(result["lock_or_migration_verified"])
        self.assertFalse(result["x1_event_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
