from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum.xone_identity import (
    CHAIN_ID,
    CONTRACT_VERSION,
    EthereumXoneIdentityError,
    XONE_CONTRACT,
    XONE_CREATION_TX,
    XONE_DECIMALS,
    XONE_DEPLOYER,
    corroborate_xone_identity_proofs,
    verify_xone_identity,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


def abi_string(value: str) -> str:
    encoded = value.encode("utf-8")
    padded = encoded + (b"\x00" * ((32 - len(encoded) % 32) % 32))
    payload = (
        (32).to_bytes(32, "big")
        + len(encoded).to_bytes(32, "big")
        + padded
    )
    return "0x" + payload.hex()


def abi_uint(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


class FakeRPC:
    def __init__(
        self,
        *,
        chain_id=CHAIN_ID,
        contract_address=XONE_CONTRACT,
        deployer=XONE_DEPLOYER,
        status="0x1",
        code="0x6001600055",
        name="XONE",
        symbol="XONE",
        decimals=XONE_DECIMALS,
        tx_to=None,
        block_number="0x11bf648",
    ):
        self.chain_id = chain_id
        self.contract_address = contract_address
        self.deployer = deployer
        self.status = status
        self.code = code
        self.name = name
        self.symbol = symbol
        self.decimals = decimals
        self.tx_to = tx_to
        self.block_number = block_number
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return self.chain_id
        if method == "eth_getTransactionByHash":
            return {
                "hash": XONE_CREATION_TX,
                "from": self.deployer,
                "to": self.tx_to,
                "blockNumber": self.block_number,
                "input": "0x6000",
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": XONE_CREATION_TX,
                "contractAddress": self.contract_address,
                "status": self.status,
                "blockNumber": self.block_number,
            }
        if method == "eth_getCode":
            return self.code
        if method == "eth_call":
            selector = params[0]["data"]
            if selector == "0x06fdde03":
                return abi_string(self.name)
            if selector == "0x95d89b41":
                return abi_string(self.symbol)
            if selector == "0x313ce567":
                return abi_uint(self.decimals)
        raise AssertionError(f"unexpected RPC call {method} {params}")


class EthereumXoneIdentityTests(unittest.TestCase):
    def test_exact_candidate_identity_passes_only_direct_fields(self):
        rpc = FakeRPC()
        proof = verify_xone_identity(
            rpc_call=rpc,
            source_url="https://ethereum-rpc.publicnode.com",
        )

        self.assertEqual(proof["contract_version"], "ethereum_xone_identity/v1")
        self.assertEqual(proof["contract_version"], CONTRACT_VERSION)
        self.assertEqual(proof["chain_id"], "0x1")
        self.assertEqual(proof["contract_address"], XONE_CONTRACT)
        self.assertEqual(proof["creation_transaction"], XONE_CREATION_TX)
        self.assertEqual(proof["deployer"], XONE_DEPLOYER)
        self.assertEqual(proof["erc20"], {
            "name": "XONE",
            "symbol": "XONE",
            "decimals": 18,
        })
        self.assertGreater(proof["runtime_code_bytes"], 0)
        self.assertEqual(len(proof["runtime_code_sha256"]), 64)
        self.assertTrue(proof["exact_ethereum_xone_identity_verified"])
        self.assertFalse(proof["xone_xnt_conversion_verified"])
        self.assertFalse(proof["xone_burn_verified"])
        self.assertFalse(proof["xnt_issuance_verified"])
        self.assertFalse(proof["cross_chain_correlation_verified"])
        self.assertFalse(proof["public_service_promoted"])
        self.assertFalse(proof["scout_reliance_promoted"])
        self.assertFalse(proof["execution_authorized"])

        self.assertEqual(
            [method for method, _params in rpc.calls],
            [
                "eth_chainId",
                "eth_getTransactionByHash",
                "eth_getTransactionReceipt",
                "eth_getCode",
                "eth_call",
                "eth_call",
                "eth_call",
            ],
        )
        self.assertEqual(rpc.calls[3][1], [XONE_CONTRACT, "finalized"])
        self.assertEqual(rpc.calls[4][1][1], "finalized")

    def test_wrong_deployer_fails_closed(self):
        rpc = FakeRPC(deployer="0x" + ("11" * 20))
        with self.assertRaisesRegex(EthereumXoneIdentityError, "deployer mismatch"):
            verify_xone_identity(rpc_call=rpc)

    def test_wrong_receipt_contract_fails_closed(self):
        rpc = FakeRPC(contract_address="0x" + ("22" * 20))
        with self.assertRaisesRegex(EthereumXoneIdentityError, "contract address mismatch"):
            verify_xone_identity(rpc_call=rpc)

    def test_non_creation_transaction_fails_closed(self):
        rpc = FakeRPC(tx_to="0x" + ("33" * 20))
        with self.assertRaisesRegex(EthereumXoneIdentityError, "not contract creation"):
            verify_xone_identity(rpc_call=rpc)

    def test_failed_creation_receipt_fails_closed(self):
        rpc = FakeRPC(status="0x0")
        with self.assertRaisesRegex(EthereumXoneIdentityError, "did not succeed"):
            verify_xone_identity(rpc_call=rpc)

    def test_empty_runtime_code_fails_closed(self):
        rpc = FakeRPC(code="0x")
        with self.assertRaisesRegex(EthereumXoneIdentityError, "no runtime bytecode"):
            verify_xone_identity(rpc_call=rpc)

    def test_wrong_name_symbol_or_decimals_fails_closed(self):
        with self.assertRaisesRegex(EthereumXoneIdentityError, r"name\(\) mismatch"):
            verify_xone_identity(rpc_call=FakeRPC(name="Fake XONE"))
        with self.assertRaisesRegex(EthereumXoneIdentityError, r"symbol\(\) mismatch"):
            verify_xone_identity(rpc_call=FakeRPC(symbol="FAKE"))
        with self.assertRaisesRegex(EthereumXoneIdentityError, r"decimals\(\) mismatch"):
            verify_xone_identity(rpc_call=FakeRPC(decimals=9))

    def test_wrong_chain_fails_closed(self):
        with self.assertRaisesRegex(EthereumXoneIdentityError, "expected Ethereum mainnet"):
            verify_xone_identity(rpc_call=FakeRPC(chain_id="0xaa36a7"))

    def test_dual_rpc_corroboration_requires_matching_distinct_hosts(self):
        one = verify_xone_identity(
            rpc_call=FakeRPC(),
            source_url="https://ethereum-rpc.publicnode.com",
        )
        two = verify_xone_identity(
            rpc_call=FakeRPC(),
            source_url="https://eth.llamarpc.com",
        )
        result = corroborate_xone_identity_proofs([one, two])
        self.assertTrue(result["multi_rpc_corroborated"])
        self.assertTrue(result["transport_provider_diversity_verified"])
        self.assertFalse(result["rpc_backend_source_independence_verified"])
        self.assertTrue(result["exact_ethereum_xone_identity_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["execution_authorized"])

        same_host = dict(two)
        same_host["source_url"] = "https://ethereum-rpc.publicnode.com/other"
        with self.assertRaisesRegex(EthereumXoneIdentityError, "distinct RPC transport"):
            corroborate_xone_identity_proofs([one, same_host])

    def test_dual_rpc_disagreement_fails_closed(self):
        one = verify_xone_identity(
            rpc_call=FakeRPC(code="0x6001"),
            source_url="https://ethereum-rpc.publicnode.com",
        )
        two = verify_xone_identity(
            rpc_call=FakeRPC(code="0x6002"),
            source_url="https://eth.llamarpc.com",
        )
        with self.assertRaisesRegex(EthereumXoneIdentityError, "runtime_code_sha256"):
            corroborate_xone_identity_proofs([one, two])

    def test_conversion_service_handoff_promotes_identity_only(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.verify_ethereum_xone_identity(
            rpc_call=FakeRPC(),
            source_url="https://ethereum-rpc.publicnode.com",
        )
        self.assertTrue(result["ethereum_xone_identity_verified"])
        self.assertTrue(
            result["ethereum_identity"]["exact_ethereum_xone_identity_verified"]
        )
        self.assertFalse(result["ethereum_event_verified"])
        self.assertFalse(result["x1_event_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
