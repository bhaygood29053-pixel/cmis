from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum.xone_identity import (
    CHAIN_ID,
    XONE_CONTRACT,
    XONE_DEPLOYER,
)
from liquidity_scout.providers.ethereum.xone_migration_sink_semantics import (
    SUPPORTS_INTERFACE_SELECTOR,
)
from liquidity_scout.providers.xone_xnt import (
    CANDIDATE_DISCOVERY_CONTRACT_VERSION,
    discover_conversion_candidates,
    extract_xone_xnt_claims,
    qualify_conversion_candidate,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


def abi_bool(value: bool) -> str:
    return "0x" + (1 if value else 0).to_bytes(32, "big").hex()


class FakeRPC:
    def __init__(
        self,
        *,
        code_by_address=None,
        supports_by_address=None,
        chain_id=CHAIN_ID,
        interface_error_by_address=None,
    ):
        self.chain_id = chain_id
        self.code_by_address = {
            str(k).casefold(): v for k, v in dict(code_by_address or {}).items()
        }
        self.supports_by_address = {
            str(k).casefold(): bool(v)
            for k, v in dict(supports_by_address or {}).items()
        }
        self.interface_error_by_address = {
            str(k).casefold(): str(v)
            for k, v in dict(interface_error_by_address or {}).items()
        }
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return self.chain_id
        if method == "eth_getCode":
            return self.code_by_address.get(str(params[0]).casefold(), "0x")
        if method == "eth_call":
            call = params[0]
            address = str(call["to"]).casefold()
            data = str(call["data"]).casefold()
            if data.startswith(SUPPORTS_INTERFACE_SELECTOR):
                if address in self.interface_error_by_address:
                    from liquidity_scout.providers.ethereum.xone_migration_sink_semantics import (
                        EthereumXoneMigrationSemanticsError,
                    )
                    raise EthereumXoneMigrationSemanticsError(
                        self.interface_error_by_address[address]
                    )
                return abi_bool(self.supports_by_address.get(address, False))
        raise AssertionError(f"unexpected RPC call {method} {params}")


def claim(text: str, *, source_id="x1report", url="https://x1report.com/article/example", observed_at=1.0):
    rows = extract_xone_xnt_claims(
        text,
        source_id=source_id,
        url=url,
        observed_at=observed_at,
    )
    if not rows:
        raise AssertionError("test fixture produced no claim")
    return rows[0]


class XoneXntConversionCandidateDiscoveryTests(unittest.TestCase):
    def test_discovers_exact_address_only_with_conversion_context(self):
        candidate = "0x" + ("ab" * 20)
        rows = [
            claim(
                f"XONE migration to XNT may use conversion contract {candidate}."
            )
        ]
        result = discover_conversion_candidates(rows)
        self.assertEqual(
            result["contract_version"],
            CANDIDATE_DISCOVERY_CONTRACT_VERSION,
        )
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["qualifiable_candidate_count"], 1)
        row = result["candidates"][0]
        self.assertEqual(row["candidate_address"], candidate)
        self.assertEqual(row["candidate_role"], "unverified_conversion_candidate")
        self.assertTrue(row["eligible_for_ethereum_qualification"])
        self.assertGreater(row["relevance_score"], 0)
        self.assertFalse(row["candidate_role_verified"])
        self.assertFalse(row["migration_sink_identified"])
        self.assertFalse(row["xone_xnt_conversion_verified"])
        self.assertFalse(row["execution_authorized"])

    def test_dedupes_address_and_preserves_multiple_claim_sources(self):
        candidate = "0x" + ("cd" * 20)
        first = claim(
            f"XONE conversion to XNT references contract {candidate}.",
            source_id="x1report",
            url="https://x1report.com/article/one",
        )
        second = claim(
            f"XONE migration into XNT mentions Ethereum contract {candidate}.",
            source_id="x1_docs",
            url="https://docs.x1.xyz/example",
            observed_at=2.0,
        )
        result = discover_conversion_candidates([first, second])
        self.assertEqual(result["candidate_count"], 1)
        row = result["candidates"][0]
        self.assertEqual(row["source_claim_count"], 2)
        self.assertEqual(row["distinct_source_ids"], ["x1_docs", "x1report"])
        self.assertEqual(
            {ref["claim_id"] for ref in row["source_claims"]},
            {first["claim_id"], second["claim_id"]},
        )

    def test_known_xone_contract_and_deployer_are_never_sink_candidates(self):
        rows = [
            claim(
                f"XONE contract {XONE_CONTRACT} is on Ethereum and XNT conversion is discussed."
            ),
            claim(
                f"XONE deployer {XONE_DEPLOYER} is mentioned near XNT migration discussion.",
                url="https://x1report.com/article/two",
            ),
        ]
        result = discover_conversion_candidates(rows)
        by_address = {
            row["candidate_address"]: row for row in result["candidates"]
        }
        self.assertEqual(
            by_address[XONE_CONTRACT]["candidate_role"],
            "exact_xone_token_contract",
        )
        self.assertFalse(
            by_address[XONE_CONTRACT]["eligible_for_ethereum_qualification"]
        )
        self.assertEqual(
            by_address[XONE_DEPLOYER]["candidate_role"],
            "exact_xone_deployer",
        )
        self.assertFalse(
            by_address[XONE_DEPLOYER]["eligible_for_ethereum_qualification"]
        )
        self.assertFalse(by_address[XONE_CONTRACT]["migration_sink_identified"])
        self.assertFalse(by_address[XONE_DEPLOYER]["migration_sink_identified"])

    def test_zero_candidates_is_scoped_not_global_absence(self):
        rows = [
            claim("XONE conversion to XNT is still being discussed.")
        ]
        result = discover_conversion_candidates(rows)
        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(
            result[
                "zero_candidates_mean_only_no_exact_address_candidates_in_supplied_claims"
            ]
        )
        self.assertFalse(result["migration_sink_identified"])

    def test_eoa_or_empty_code_candidate_is_not_migration_sink(self):
        address = "0x" + ("11" * 20)
        candidate = discover_conversion_candidates([
            claim(f"XONE may convert to XNT through contract {address}.")
        ])["candidates"][0]
        result = qualify_conversion_candidate(
            candidate,
            rpc_call=FakeRPC(code_by_address={address: "0x"}),
            source_url="https://rpc-one.example",
        )
        self.assertEqual(result["qualification_state"], "no_runtime_bytecode")
        self.assertFalse(result["runtime_code_present"])
        self.assertFalse(result["burn_redeemer_interface_verified"])
        self.assertFalse(result["migration_sink_identified"])
        self.assertFalse(result["execution_authorized"])

    def test_iburnredeemable_contract_remains_only_candidate(self):
        address = "0x" + ("22" * 20)
        candidate = discover_conversion_candidates([
            claim(f"XONE migration to XNT references redeem contract {address}.")
        ])["candidates"][0]
        result = qualify_conversion_candidate(
            candidate,
            rpc_call=FakeRPC(
                code_by_address={address: "0x60016000"},
                supports_by_address={address: True},
            ),
            source_url="https://rpc-one.example",
        )
        self.assertEqual(
            result["qualification_state"],
            "iburnredeemable_compatible_contract",
        )
        self.assertTrue(result["runtime_code_present"])
        self.assertTrue(result["burn_redeemer_interface_verified"])
        self.assertFalse(result["migration_sink_identified"])
        self.assertFalse(result["lock_or_migration_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])

    def test_contract_without_erc165_support_is_not_redeemer(self):
        address = "0x" + ("33" * 20)
        candidate = discover_conversion_candidates([
            claim(f"XONE conversion to XNT references contract {address}.")
        ])["candidates"][0]
        result = qualify_conversion_candidate(
            candidate,
            rpc_call=FakeRPC(
                code_by_address={address: "0x6001"},
                supports_by_address={address: False},
            ),
        )
        self.assertEqual(
            result["qualification_state"],
            "contract_without_iburnredeemable_support",
        )
        self.assertFalse(result["burn_redeemer_interface_verified"])
        self.assertFalse(result["migration_sink_identified"])

    def test_interface_revert_is_preserved_as_unverified_not_false_semantics(self):
        address = "0x" + ("44" * 20)
        candidate = discover_conversion_candidates([
            claim(f"XONE migration to XNT references contract {address}.")
        ])["candidates"][0]
        result = qualify_conversion_candidate(
            candidate,
            rpc_call=FakeRPC(
                code_by_address={address: "0x6001"},
                interface_error_by_address={address: "execution reverted"},
            ),
        )
        self.assertEqual(
            result["qualification_state"],
            "contract_interface_unverified",
        )
        self.assertFalse(result["interface_query_available"])
        self.assertIn("execution reverted", result["interface_query_error"])
        self.assertFalse(result["migration_sink_identified"])

    def test_wrong_chain_fails_closed(self):
        address = "0x" + ("55" * 20)
        candidate = discover_conversion_candidates([
            claim(f"XONE conversion to XNT references contract {address}.")
        ])["candidates"][0]
        with self.assertRaisesRegex(Exception, "expected Ethereum mainnet"):
            qualify_conversion_candidate(
                candidate,
                rpc_call=FakeRPC(
                    chain_id="0xaa36a7",
                    code_by_address={address: "0x6001"},
                ),
            )

    def test_service_handoff_does_not_promote_candidate(self):
        address = "0x" + ("66" * 20)
        claims = [
            claim(f"XONE conversion to XNT references contract {address}.")
        ]
        service = CMISXoneXntConversionIntelligenceService()
        discovery = service.discover_xone_xnt_conversion_candidates(claims)
        self.assertTrue(discovery["conversion_candidate_discovery_verified"])
        self.assertFalse(discovery["migration_sink_identified"])
        candidate = discovery["candidate_discovery"]["candidates"][0]

        qualified = service.qualify_xone_xnt_conversion_candidate(
            candidate,
            rpc_call=FakeRPC(
                code_by_address={address: "0x6001"},
                supports_by_address={address: True},
            ),
            source_url="https://rpc-one.example",
        )
        self.assertTrue(qualified["conversion_candidate_discovery_verified"])
        self.assertTrue(qualified["burn_redeemer_interface_verified"])
        self.assertFalse(qualified["migration_sink_identified"])
        self.assertFalse(qualified["xone_xnt_conversion_verified"])
        self.assertFalse(qualified["cmis_verified"])
        self.assertFalse(qualified["public_service_promoted"])
        self.assertFalse(qualified["scout_reliance_promoted"])
        self.assertFalse(qualified["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
