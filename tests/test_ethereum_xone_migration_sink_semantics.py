from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum.xone_identity import (
    CHAIN_ID,
    XONE_CONTRACT,
    XONE_CREATION_TX,
    XONE_DEPLOYER,
)
from liquidity_scout.providers.ethereum.xone_migration_sink_semantics import (
    BURN_SELECTOR,
    CONTRACT_VERSION,
    EthereumXoneMigrationSemanticsError,
    ON_TOKEN_BURNED_INTERFACE_ID,
    SUPPORTS_INTERFACE_SELECTOR,
    USER_BURNS_SELECTOR,
    classify_migration_candidate,
    corroborate_xone_burn_surface,
    supports_interface_calldata,
    user_burns_calldata,
    verify_burn_redeemer_candidate,
    verify_xone_burn_surface,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


def abi_uint(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


def abi_bool(value: bool) -> str:
    return abi_uint(1 if value else 0)


def abi_string(value: str) -> str:
    encoded = value.encode("utf-8")
    padded = encoded + (b"\x00" * ((32 - len(encoded) % 32) % 32))
    return "0x" + (
        (32).to_bytes(32, "big")
        + len(encoded).to_bytes(32, "big")
        + padded
    ).hex()


class FakeRPC:
    def __init__(self, *, burns=None, candidate_support=True, candidate_code="0x6001"):
        self.burns = {
            XONE_DEPLOYER: 123,
            "0x0000000000000000000000000000000000000000": 0,
        }
        if burns:
            self.burns.update({k.casefold(): v for k, v in burns.items()})
        self.candidate_support = candidate_support
        self.candidate_code = candidate_code
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return CHAIN_ID
        if method == "eth_getCode":
            if params[0].casefold() == XONE_CONTRACT:
                return "0x6001600055"
            return self.candidate_code
        if method == "eth_call":
            call = params[0]
            target = call["to"].casefold()
            data = call["data"].casefold()
            if target == XONE_CONTRACT:
                if data == "0x06fdde03":
                    return abi_string("XONE")
                if data == "0x95d89b41":
                    return abi_string("XONE")
                if data == "0x313ce567":
                    return abi_uint(18)
                if data.startswith(USER_BURNS_SELECTOR):
                    user = "0x" + data[-40:]
                    return abi_uint(self.burns.get(user, 0))
            if data.startswith(SUPPORTS_INTERFACE_SELECTOR):
                return abi_bool(self.candidate_support)
        if method == "eth_getTransactionByHash":
            return {
                "hash": XONE_CREATION_TX,
                "from": XONE_DEPLOYER,
                "to": None,
                "blockNumber": "0x11bf648",
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": XONE_CREATION_TX,
                "contractAddress": XONE_CONTRACT,
                "status": "0x1",
                "blockNumber": "0x11bf648",
            }
        raise AssertionError(f"unexpected RPC call {method} {params}")


class XoneMigrationSinkSemanticsTests(unittest.TestCase):
    def test_canonical_selectors_and_calldata(self):
        self.assertEqual(BURN_SELECTOR, "0x9dc29fac")
        self.assertEqual(USER_BURNS_SELECTOR, "0xce653d5f")
        self.assertEqual(ON_TOKEN_BURNED_INTERFACE_ID, "0x543746b1")
        self.assertEqual(SUPPORTS_INTERFACE_SELECTOR, "0x01ffc9a7")
        self.assertEqual(
            user_burns_calldata(XONE_DEPLOYER),
            USER_BURNS_SELECTOR + ("0" * 24) + XONE_DEPLOYER[2:],
        )
        self.assertEqual(
            supports_interface_calldata(),
            SUPPORTS_INTERFACE_SELECTOR
            + ON_TOKEN_BURNED_INTERFACE_ID[2:]
            + ("0" * 56),
        )

    def test_live_burn_surface_is_read_only_and_not_migration(self):
        proof = verify_xone_burn_surface(
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        self.assertEqual(proof["contract_version"], CONTRACT_VERSION)
        self.assertTrue(proof["xone_burn_accounting_surface_verified"])
        self.assertEqual(
            proof["probe_user_burns_base_units"][XONE_DEPLOYER],
            "123",
        )
        self.assertFalse(proof["simple_transfer_sink_required_by_this_proof"])
        self.assertFalse(proof["migration_sink_identified"])
        self.assertFalse(proof["xone_xnt_conversion_verified"])
        self.assertFalse(proof["execution_authorized"])

    def test_candidate_iburnredeemable_support_is_only_technical_candidate(self):
        candidate = "0x" + ("ab" * 20)
        proof = verify_burn_redeemer_candidate(
            candidate,
            rpc_call=FakeRPC(candidate_support=True),
            source_url="https://rpc-one.example",
        )
        self.assertTrue(proof["burn_redeemer_interface_verified"])
        self.assertEqual(proof["candidate_role"], "burn_redeemer_interface_candidate")
        self.assertFalse(proof["migration_sink_identified"])
        self.assertFalse(proof["xone_xnt_conversion_verified"])

        classified = classify_migration_candidate(
            candidate_address=candidate,
            burn_redeemer_proof=proof,
            direct_transfer_to_candidate_verified=True,
        )
        self.assertEqual(classified["candidate_semantic_state"], "burn_redeemer_candidate")
        self.assertFalse(classified["migration_sink_identified"])
        self.assertIn(
            "exact_x1_xnt_issuance_or_allocation_binding",
            classified["required_next_proof"],
        )

    def test_candidate_without_interface_is_not_redeemer(self):
        candidate = "0x" + ("cd" * 20)
        proof = verify_burn_redeemer_candidate(
            candidate,
            rpc_call=FakeRPC(candidate_support=False),
        )
        self.assertFalse(proof["burn_redeemer_interface_verified"])
        self.assertEqual(proof["candidate_role"], "contract_without_iburnredeemable_support")

    def test_eoa_candidate_fails_closed(self):
        candidate = "0x" + ("ef" * 20)
        with self.assertRaisesRegex(EthereumXoneMigrationSemanticsError, "no runtime bytecode"):
            verify_burn_redeemer_candidate(
                candidate,
                rpc_call=FakeRPC(candidate_code="0x"),
            )

    def test_corroboration_requires_distinct_matching_rpc_hosts(self):
        one = verify_xone_burn_surface(
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        two = verify_xone_burn_surface(
            rpc_call=FakeRPC(),
            source_url="https://rpc-two.example",
        )
        result = corroborate_xone_burn_surface([one, two])
        self.assertTrue(result["multi_rpc_corroborated"])
        self.assertEqual(result["rpc_proof_count"], 2)
        self.assertFalse(result["migration_sink_identified"])
        self.assertFalse(result["execution_authorized"])

        same = dict(two)
        same["source_url"] = "https://rpc-one.example/other"
        with self.assertRaisesRegex(EthereumXoneMigrationSemanticsError, "distinct RPC"):
            corroborate_xone_burn_surface([one, same])

    def test_corroboration_rejects_state_disagreement(self):
        one = verify_xone_burn_surface(
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        two = verify_xone_burn_surface(
            rpc_call=FakeRPC(burns={XONE_DEPLOYER: 999}),
            source_url="https://rpc-two.example",
        )
        with self.assertRaisesRegex(EthereumXoneMigrationSemanticsError, "userBurns state"):
            corroborate_xone_burn_surface([one, two])

    def test_conversion_service_keeps_migration_unverified(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.verify_ethereum_xone_burn_surface(
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        self.assertTrue(result["ethereum_xone_identity_verified"])
        self.assertTrue(result["xone_burn_accounting_surface_verified"])
        self.assertFalse(result["migration_sink_identified"])
        self.assertFalse(result["lock_or_migration_verified"])
        self.assertFalse(result["x1_event_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
