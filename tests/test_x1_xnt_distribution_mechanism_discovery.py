from __future__ import annotations

import unittest

from liquidity_scout.providers.xone_xnt import (
    OFFICIAL_REWARDS_URL,
    STAKE_PROGRAM_ID,
    X1_XNT_DISTRIBUTION_MECHANISM_CONTRACT_VERSION,
    X1XntMechanismDiscoveryError,
    discover_xnt_distribution_candidates,
    extract_xnt_mechanism_claims,
    normalize_x1_pubkey,
    qualify_xnt_distribution_candidate,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


CANDIDATE = "11111111111111111111111111111111"
CUSTODIAN = "Vote111111111111111111111111111111111111111"


class FakeRPC:
    def __init__(self, value, *, slot=123):
        self.value = value
        self.slot = slot
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method != "getAccountInfo":
            raise AssertionError(f"unexpected RPC method {method}")
        return {"context": {"slot": self.slot}, "value": self.value}


def official_text(candidate: str | None = None) -> str:
    suffix = (
        f" The XNT reward account candidate is {candidate}."
        if candidate
        else ""
    )
    return (
        "Testnet validator credits convert at 50,000 credits = 1 XNT. "
        "At genesis, 10% of the XNT reward is immediately available and the "
        "remaining 90% is subject to a 365 days lock with vesting. "
        "Vested XNT tokens unlock only after 365 days from mainnet launch."
        + suffix
    )


class X1XntDistributionMechanismDiscoveryTests(unittest.TestCase):
    def test_extracts_official_reward_lock_and_unlock_rules(self):
        claims = extract_xnt_mechanism_claims(
            official_text(),
            source_id="x1_docs",
            url=OFFICIAL_REWARDS_URL,
            observed_at=100.0,
        )
        self.assertGreaterEqual(len(claims), 2)
        topics = {topic for claim in claims for topic in claim["topics"]}
        self.assertIn("validator_rewards", topics)
        self.assertIn("lockup", topics)
        self.assertIn("vesting", topics)
        self.assertIn("unlock", topics)

        values = {
            key: value
            for claim in claims
            for key, rows in claim["normalized_values"].items()
            for value in rows
        }
        joined = " | ".join(
            value
            for claim in claims
            for rows in claim["normalized_values"].values()
            for value in rows
        )
        self.assertIn("50,000 credits = 1 XNT", joined)
        self.assertIn("10%", joined)
        self.assertIn("90%", joined)
        self.assertIn("365 days", joined)
        for claim in claims:
            self.assertTrue(claim["native_xnt_context"])
            self.assertTrue(claim["wxnt_equivalence_not_assumed"])
            self.assertFalse(claim["xnt_rule_claim_verified"])
            self.assertFalse(claim["xnt_distribution_mechanism_identified"])
            self.assertFalse(claim["xnt_vesting_or_unlock_verified"])
            self.assertFalse(claim["xone_xnt_conversion_verified"])
            self.assertFalse(claim["execution_authorized"])

    def test_discovers_only_exact_32_byte_base58_pubkeys(self):
        claims = extract_xnt_mechanism_claims(
            official_text(CANDIDATE),
            source_id="x1_docs",
            url=OFFICIAL_REWARDS_URL,
            observed_at=100.0,
        )
        discovery = discover_xnt_distribution_candidates(claims)
        self.assertEqual(
            discovery["contract_version"],
            X1_XNT_DISTRIBUTION_MECHANISM_CONTRACT_VERSION,
        )
        self.assertEqual(discovery["candidate_count"], 1)
        self.assertEqual(discovery["candidates"][0]["candidate_pubkey"], CANDIDATE)
        self.assertFalse(discovery["candidates"][0]["candidate_role_verified"])
        self.assertFalse(discovery["xnt_distribution_mechanism_identified"])
        self.assertFalse(discovery["xone_xnt_conversion_verified"])

        claims_invalid = extract_xnt_mechanism_claims(
            "XNT vesting program candidate 12345678901234567890123456789012.",
            source_id="x1_docs",
            url=OFFICIAL_REWARDS_URL,
            observed_at=101.0,
        )
        self.assertEqual(
            discover_xnt_distribution_candidates(claims_invalid)["candidate_count"],
            0,
        )

    def test_zero_candidates_is_scoped_not_global_absence(self):
        claims = extract_xnt_mechanism_claims(
            official_text(),
            source_id="x1_docs",
            url=OFFICIAL_REWARDS_URL,
            observed_at=100.0,
        )
        discovery = discover_xnt_distribution_candidates(claims)
        self.assertEqual(discovery["candidate_count"], 0)
        self.assertTrue(
            discovery[
                "zero_candidates_mean_only_no_exact_pubkeys_in_supplied_claims"
            ]
        )
        self.assertFalse(discovery["xnt_distribution_mechanism_identified"])

    def test_source_boundary_fails_closed(self):
        with self.assertRaisesRegex(X1XntMechanismDiscoveryError, "outside"):
            extract_xnt_mechanism_claims(
                "XNT rewards unlock after 365 days.",
                source_id="x1_docs",
                url="https://example.com/fake",
                observed_at=1.0,
            )

    def test_pubkey_validation(self):
        self.assertEqual(normalize_x1_pubkey(CANDIDATE), CANDIDATE)
        with self.assertRaises(X1XntMechanismDiscoveryError):
            normalize_x1_pubkey("not-a-pubkey")

    def test_missing_candidate_account_is_verified_absence_at_that_pubkey_only(self):
        result = qualify_xnt_distribution_candidate(
            {"candidate_pubkey": CANDIDATE},
            rpc_call=FakeRPC(None),
            source_url="https://rpc.mainnet.x1.xyz",
        )
        self.assertTrue(result["rpc_finalized_commitment"])
        self.assertTrue(result["account_state_verified"])
        self.assertFalse(result["account_exists"])
        self.assertFalse(result["xnt_distribution_mechanism_identified"])
        self.assertFalse(result["xnt_vesting_or_unlock_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_stake_lockup_state_is_structural_not_distribution_role(self):
        value = {
            "owner": STAKE_PROGRAM_ID,
            "executable": False,
            "lamports": 2_500_000_000,
            "space": 200,
            "data": {
                "program": "stake",
                "parsed": {
                    "type": "delegated",
                    "info": {
                        "meta": {
                            "lockup": {
                                "epoch": 0,
                                "unixTimestamp": 1791244800,
                                "custodian": CUSTODIAN,
                            }
                        }
                    },
                },
            },
        }
        result = qualify_xnt_distribution_candidate(
            {"candidate_pubkey": CANDIDATE},
            rpc_call=FakeRPC(value),
        )
        self.assertTrue(result["account_exists"])
        self.assertTrue(result["stake_program_owned"])
        self.assertTrue(result["stake_lockup_state_verified"])
        self.assertEqual(result["stake_lockup"]["unix_timestamp"], 1791244800)
        self.assertTrue(result["stake_lockup_does_not_prove_distribution_role"])
        self.assertFalse(result["candidate_role_verified"])
        self.assertFalse(result["xnt_distribution_mechanism_identified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xnt_vesting_or_unlock_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])

    def test_service_handoff_preserves_nonpromotion(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.discover_x1_xnt_distribution_mechanism(
            [
                {
                    "source_id": "x1_docs",
                    "url": OFFICIAL_REWARDS_URL,
                    "text": official_text(CANDIDATE),
                }
            ],
            observed_at=100.0,
        )
        self.assertTrue(result["x1_xnt_mechanism_discovery_verified"])
        self.assertGreater(result["xnt_mechanism_claim_count"], 0)
        self.assertEqual(
            result["xnt_mechanism_discovery"]["candidate_count"],
            1,
        )
        self.assertFalse(result["xnt_distribution_mechanism_identified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xnt_vesting_or_unlock_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
