from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum.xone_identity import XONE_CONTRACT
from liquidity_scout.providers.xone_xnt import (
    MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION,
    MoonPartyDeploymentVerificationError,
    corroborate_moonparty_deployment,
    discover_moonparty_deployment_candidates,
    verify_moonparty_deployment_candidate,
)
from liquidity_scout.providers.xone_xnt.moonparty_deployment_verification import (
    AMP_SELECTOR,
    DURATION_SELECTOR,
    GENESIS_TS_SELECTOR,
    IBURN_REDEEMABLE_INTERFACE_ID,
    REQUIRED_RUNTIME_SELECTORS,
    SUPPORTS_INTERFACE_SELECTOR,
    TOTAL_ALLOCATED_XNT_CREDITS_SELECTOR,
    TOTAL_BURN_POINTS_SELECTOR,
    VMPX_SELECTOR,
    XEN_BURN_SELECTOR,
    XEN_CRYPTO_SELECTOR,
    XEN_TORRENT_SELECTOR,
    XONE_SELECTOR,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


CANDIDATE = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
VMPX = "0x3333333333333333333333333333333333333333"
XEN_BURN = "0x4444444444444444444444444444444444444444"
XEN = "0x5555555555555555555555555555555555555555"
XEN_TORRENT = "0x6666666666666666666666666666666666666666"


def word_address(address: str) -> str:
    return "0x" + ("00" * 12) + address[2:].lower()


def word_uint(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


def runtime_bytes() -> bytes:
    body = bytearray(b"\x60\x00")
    for selector in REQUIRED_RUNTIME_SELECTORS:
        body.extend(bytes.fromhex(selector[2:]))
        body.extend(b"\x5b")
    metadata = bytes.fromhex("a164736f6c6343000814")
    body.extend(metadata)
    body.extend(len(metadata).to_bytes(2, "big"))
    return bytes(body)


def artifact() -> dict:
    return {
        "contractName": "MoonParty",
        "deployedBytecode": "0x" + runtime_bytes().hex(),
    }


class FakeRPC:
    def __init__(self, *, candidate=CANDIDATE, xone=XONE_CONTRACT, code=None):
        self.candidate = candidate
        self.xone = xone
        self.code = runtime_bytes() if code is None else code
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return "0x1"
        if method == "eth_getCode":
            self.assert_candidate(params[0])
            return "0x" + self.code.hex()
        if method == "eth_call":
            request = params[0]
            self.assert_candidate(request["to"])
            data = request["data"].lower()
            if data == XONE_SELECTOR:
                return word_address(self.xone)
            if data == VMPX_SELECTOR:
                return word_address(VMPX)
            if data == XEN_BURN_SELECTOR:
                return word_address(XEN_BURN)
            if data == XEN_CRYPTO_SELECTOR:
                return word_address(XEN)
            if data == XEN_TORRENT_SELECTOR:
                return word_address(XEN_TORRENT)
            if data == DURATION_SELECTOR:
                return word_uint(100 * 24 * 3600)
            if data == GENESIS_TS_SELECTOR:
                return word_uint(1_700_000_000)
            if data == AMP_SELECTOR:
                return word_uint(100)
            if data == TOTAL_BURN_POINTS_SELECTOR:
                return word_uint(123)
            if data == TOTAL_ALLOCATED_XNT_CREDITS_SELECTOR:
                return word_uint(45)
            if data.startswith(SUPPORTS_INTERFACE_SELECTOR):
                self.assert_interface_calldata(data)
                return word_uint(1)
        raise AssertionError(f"unexpected RPC call: {method} {params}")

    def assert_candidate(self, value):
        if value.lower() != self.candidate.lower():
            raise AssertionError(f"wrong candidate {value}")

    def assert_interface_calldata(self, data):
        expected = (
            SUPPORTS_INTERFACE_SELECTOR
            + IBURN_REDEEMABLE_INTERFACE_ID[2:]
            + ("0" * 56)
        )
        if data != expected:
            raise AssertionError(f"wrong supportsInterface calldata {data}")


class MoonPartyDeploymentVerificationTests(unittest.TestCase):
    def test_discovers_only_moonparty_scoped_exact_addresses(self):
        result = discover_moonparty_deployment_candidates(
            [
                {
                    "source_id": "env",
                    "url": "https://example.test/.env",
                    "text": f"MOONPARTY_ADDRESS_MAINNET={CANDIDATE}\nOTHER={OTHER}",
                },
                {
                    "source_id": "noise",
                    "url": "https://example.test/noise",
                    "text": f"unrelated contract {OTHER}",
                },
            ]
        )
        self.assertEqual(
            result["contract_version"],
            MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION,
        )
        self.assertEqual(result["deployment_candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["candidate_address"], CANDIDATE)
        self.assertFalse(result["moonparty_deployment_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_zero_candidates_is_scoped_not_non_deployment(self):
        result = discover_moonparty_deployment_candidates(
            [
                {
                    "source_id": "bounded",
                    "url": "https://example.test",
                    "text": "MoonParty source exists but no deployment address is shown.",
                }
            ]
        )
        self.assertEqual(result["deployment_candidate_count"], 0)
        self.assertTrue(result["zero_candidates_are_scoped_corpus_evidence_only"])
        self.assertTrue(result["zero_candidates_do_not_prove_non_deployment"])
        self.assertFalse(result["moonparty_deployment_verified"])

    def test_single_rpc_qualification_verifies_runtime_and_xone_but_not_deployment(self):
        rpc = FakeRPC()
        result = verify_moonparty_deployment_candidate(
            CANDIDATE,
            artifact=artifact(),
            rpc_call=rpc,
            source_url="https://rpc-one.example",
        )
        self.assertTrue(result["single_rpc_candidate_qualified"])
        self.assertTrue(result["moonparty_runtime_compatible"])
        self.assertTrue(result["moonparty_xone_binding_verified"])
        self.assertEqual(result["immutable_bindings"]["XONE"], XONE_CONTRACT)
        self.assertEqual(result["bounded_live_state"]["totalBurnPoints"], 123)
        self.assertEqual(result["bounded_live_state"]["totalAllocatedXNTCredits"], 45)
        self.assertFalse(result["moonparty_deployment_verified"])
        self.assertFalse(result["xnt_credit_to_native_xnt_equivalence_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_runtime_length_mismatch_fails_closed(self):
        rpc = FakeRPC(code=runtime_bytes() + b"\x00")
        with self.assertRaisesRegex(
            MoonPartyDeploymentVerificationError,
            "runtime is not compatible",
        ):
            verify_moonparty_deployment_candidate(
                CANDIDATE,
                artifact=artifact(),
                rpc_call=rpc,
                source_url="https://rpc-one.example",
            )

    def test_wrong_xone_binding_fails_closed(self):
        rpc = FakeRPC(xone=OTHER)
        with self.assertRaisesRegex(
            MoonPartyDeploymentVerificationError,
            "XONE\(\) binding mismatch",
        ):
            verify_moonparty_deployment_candidate(
                CANDIDATE,
                artifact=artifact(),
                rpc_call=rpc,
                source_url="https://rpc-one.example",
            )

    def test_two_transport_corroboration_promotes_deployment_identity_only(self):
        p1 = verify_moonparty_deployment_candidate(
            CANDIDATE,
            artifact=artifact(),
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        p2 = verify_moonparty_deployment_candidate(
            CANDIDATE,
            artifact=artifact(),
            rpc_call=FakeRPC(),
            source_url="https://rpc-two.example",
        )
        result = corroborate_moonparty_deployment([p1, p2])
        self.assertTrue(result["moonparty_deployment_verified"])
        self.assertTrue(result["moonparty_deployment_chain_verified"])
        self.assertTrue(result["moonparty_runtime_compatible"])
        self.assertTrue(result["moonparty_xone_binding_verified"])
        self.assertTrue(result["xone_to_xnt_credit_design_link_deployment_bound"])
        self.assertFalse(result["xnt_credit_to_native_xnt_equivalence_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xnt_vesting_or_unlock_verified"])
        self.assertFalse(result["october_6_unlock_applies_to_xone_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_same_rpc_host_cannot_corroborate(self):
        proof = verify_moonparty_deployment_candidate(
            CANDIDATE,
            artifact=artifact(),
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        with self.assertRaisesRegex(
            MoonPartyDeploymentVerificationError,
            "two distinct RPC transport hosts",
        ):
            corroborate_moonparty_deployment([proof, dict(proof)])

    def test_service_seam_preserves_native_xnt_boundary(self):
        service = CMISXoneXntConversionIntelligenceService()
        proof1 = verify_moonparty_deployment_candidate(
            CANDIDATE,
            artifact=artifact(),
            rpc_call=FakeRPC(),
            source_url="https://rpc-one.example",
        )
        proof2 = verify_moonparty_deployment_candidate(
            CANDIDATE,
            artifact=artifact(),
            rpc_call=FakeRPC(),
            source_url="https://rpc-two.example",
        )
        result = service.corroborate_moonparty_deployment([proof1, proof2])
        self.assertTrue(result["moonparty_deployment_verified"])
        self.assertTrue(result["moonparty_xone_binding_verified"])
        self.assertFalse(result["xnt_credit_to_native_xnt_equivalence_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
