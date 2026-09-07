from __future__ import annotations

import json
import unittest

from liquidity_scout.providers.xone_xnt import (
    FAIRCRYPTO_X1_APP_COMMIT,
    FAIRCRYPTO_X1_APP_REPO,
    FAIRCRYPTO_XONE_COMMIT,
    FAIRCRYPTO_XONE_REPO,
    XONE_XNT_MOONPARTY_SOURCE_SEMANTICS_CONTRACT_VERSION,
    XoneXntMoonPartySourceSemanticsError,
    verify_moonparty_source_semantics,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


def abi_item(name, inputs=()):
    return {
        "inputs": [{"internalType": t, "name": f"a{i}", "type": t} for i, t in enumerate(inputs)],
        "name": name,
        "outputs": [],
        "stateMutability": "view",
        "type": "function",
    }


def documents():
    artifact = {
        "contractName": "MoonParty",
        "sourceName": "contracts/MoonParty.sol",
        "abi": [
            {
                "inputs": [
                    {"internalType": "address", "name": "_xoneAddress", "type": "address"}
                ],
                "stateMutability": "nonpayable",
                "type": "constructor",
            },
            abi_item("XONE"),
            abi_item("redeemXone", ("uint256",)),
            abi_item("getRedeemableXONE"),
            abi_item("getExpectedBurnPointsForXone"),
            abi_item("getXoneRate", ("uint256",)),
            abi_item("allocateXNTCredits", ("address",)),
            abi_item("totalAllocatedXNTCredits"),
            abi_item("totalBurnPoints"),
            abi_item("onTokenBurned", ("address", "uint256")),
            abi_item("supportsInterface", ("bytes4",)),
            {"anonymous": False, "inputs": [], "name": "AssetBurned", "type": "event"},
            {"anonymous": False, "inputs": [], "name": "BurnPointsAllocated", "type": "event"},
            {"anonymous": False, "inputs": [], "name": "Redeemed", "type": "event"},
        ],
    }
    return {
        "moonparty_abi": json.dumps(artifact),
        "moonparty_types": """
mapping(address => uint256) public allocateXNTCredits;
export type TMoonPartyUser = { allocateXNTCredits: bigint; };
""",
        "moonparty_context": """
{ ...moonPartyContract(chain), functionName: 'totalAllocatedXNTCredits', chainId: chain?.id }
""",
        "moonparty_state": """
{ contract: 'xoneAddress', id: 'XONE', allocate_cta: 'Allocate' }
""",
        "moonparty_global": """
<Typography>XNT Distribution</Typography>
<Typography>Burn Points Allocated</Typography>
""",
        "projects": """
xone: { name: 'XONE', owner: 'Fair Crypto Foundation' },
moonParty: { name: 'MoonParty', owner: 'Fair Crypto Foundation' }
""",
        "xone_source": """
import "@faircrypto/xen-crypto/contracts/interfaces/IBurnRedeemable.sol";
mapping(address => uint256) public userBurns;
function burn(address user, uint256 amount) public {
  userBurns[user] += amount;
  IBurnRedeemable(_msgSender()).onTokenBurned(user, amount);
}
""",
    }


def provenance():
    return {
        "x1_app_repository": FAIRCRYPTO_X1_APP_REPO,
        "x1_app_commit": FAIRCRYPTO_X1_APP_COMMIT,
        "xone_repository": FAIRCRYPTO_XONE_REPO,
        "xone_commit": FAIRCRYPTO_XONE_COMMIT,
    }


class MoonPartySourceSemanticsTests(unittest.TestCase):
    def test_verifies_exact_source_design_without_deployment_promotion(self):
        result = verify_moonparty_source_semantics(
            documents(),
            provenance=provenance(),
        )
        self.assertEqual(
            result["contract_version"],
            XONE_XNT_MOONPARTY_SOURCE_SEMANTICS_CONTRACT_VERSION,
        )
        self.assertTrue(result["source_provenance_verified"])
        self.assertTrue(result["authoritative_source_semantics_verified"])
        self.assertTrue(result["xone_participation_in_moonparty_source_verified"])
        self.assertTrue(result["xnt_credit_allocation_surface_in_moonparty_source_verified"])
        self.assertTrue(result["xone_to_xnt_credit_design_link_verified"])

        abi = result["abi_semantics"]
        self.assertTrue(abi["constructor_accepts_xone_address"])
        self.assertTrue(abi["required_function_signatures_verified"])
        self.assertIn("allocateXNTCredits", abi["verified_functions"])
        self.assertIn("redeemXone", abi["verified_functions"])
        self.assertTrue(abi["asset_burned_event_present"])
        self.assertTrue(abi["burn_points_allocated_event_present"])
        self.assertTrue(abi["redeemed_event_present"])

        self.assertFalse(result["moonparty_deployment_verified"])
        self.assertFalse(result["moonparty_deployment_chain_verified"])
        self.assertFalse(result["moonparty_runtime_bytecode_verified"])
        self.assertFalse(result["xnt_credit_to_native_xnt_equivalence_verified"])
        self.assertFalse(result["xnt_credit_transferability_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xnt_vesting_or_unlock_verified"])
        self.assertFalse(result["xone_snapshot_eligibility_verified"])
        self.assertFalse(result["october_6_unlock_applies_to_xone_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_missing_allocate_xnt_credits_fails_closed(self):
        docs = documents()
        artifact = json.loads(docs["moonparty_abi"])
        artifact["abi"] = [
            row for row in artifact["abi"]
            if row.get("name") != "allocateXNTCredits"
        ]
        docs["moonparty_abi"] = json.dumps(artifact)
        with self.assertRaisesRegex(
            XoneXntMoonPartySourceSemanticsError,
            "allocateXNTCredits",
        ):
            verify_moonparty_source_semantics(docs, provenance=provenance())

    def test_provenance_mismatch_fails_closed(self):
        bad = provenance()
        bad["x1_app_commit"] = "deadbeef"
        with self.assertRaisesRegex(
            XoneXntMoonPartySourceSemanticsError,
            "pinned provenance mismatch",
        ):
            verify_moonparty_source_semantics(documents(), provenance=bad)

    def test_ui_label_alone_cannot_pass(self):
        docs = documents()
        docs["moonparty_state"] = "id: 'XONE'"
        with self.assertRaisesRegex(
            XoneXntMoonPartySourceSemanticsError,
            "state_xone_participation_row_present",
        ):
            verify_moonparty_source_semantics(docs, provenance=provenance())

    def test_service_seam_preserves_nonpromotion(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.verify_xone_xnt_moonparty_source_semantics(
            documents(),
            provenance=provenance(),
        )
        self.assertTrue(result["moonparty_authoritative_source_semantics_verified"])
        self.assertTrue(result["xone_to_xnt_credit_design_link_verified"])
        self.assertFalse(result["moonparty_deployment_verified"])
        self.assertFalse(result["xnt_credit_to_native_xnt_equivalence_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
