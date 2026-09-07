from __future__ import annotations

import unittest

from liquidity_scout.providers.x1.agents_radio_rpc_corroboration import (
    ACCOUNT_NOT_EXECUTABLE,
    ACCOUNT_NOT_FOUND,
    CONTRACT_VERSION,
    EVIDENCE_INCOMPLETE,
    PROGRAM_ACCOUNT_CORROBORATED,
    REPORTED_SLOT_ACTIVITY_CORROBORATED,
    X1AgentsRadioRPCCorroborationError,
    corroborate_agents_radio_with_x1_rpc,
)


PROGRAM_ID = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
RADIO_PROGRAM_ID = "4Ai4Ps8YsrLfshU9xvkf9pobiVhewELdbXEZA7zaZ8E3"
OWNER = "BPFLoaderUpgradeab1e11111111111111111111111"
SIGNATURE = "5" * 88


def direct_candidate(**overrides):
    value = {
        "chain": "x1",
        "network": "x1-mainnet",
        "program_id": PROGRAM_ID,
        "name": "XDEX",
        "category": "DEX",
        "framework": "anchor",
        "status": "live",
        "description": "provider claim",
        "provider_verified_claim": True,
        "source": "x1agentsradio.xyz",
        "raw": {
            "bytecode_instructions": [
                "Initialize",
                "SwapBaseInput",
            ]
        },
    }
    value.update(overrides)
    return value


def structured_deployment_candidate(**overrides):
    value = {
        "record_type": "deployment_candidate",
        "program_id": PROGRAM_ID,
        "program_id_syntax_valid": True,
        "provider_name": "XDEX",
        "provider_category": "DEX",
        "provider_instructions": ["Initialize", "SwapBaseInput"],
        "provider_deployment": {
            "event_type": "upgrade",
            "upgrade_slot": 500,
        },
        "truth_state": {
            "discovery_state": "DISCOVERED",
            "cmis_verified": False,
        },
        "execution_authorized": False,
    }
    value.update(overrides)
    return value


def account_result(*, executable=True, owner=OWNER, slot=600):
    return {
        "context": {"slot": slot},
        "value": {
            "data": ["AA==", "base64"],
            "executable": executable,
            "lamports": 123456,
            "owner": owner,
            "rentEpoch": 0,
            "space": 36,
        },
    }


def history_result(*, slot=500, err=None):
    return [
        {
            "signature": SIGNATURE,
            "slot": slot,
            "err": err,
            "blockTime": 1788770000,
            "confirmationStatus": "finalized",
        }
    ]


def transaction_result(*, slot=500, err=None, program_id=PROGRAM_ID):
    return {
        "slot": slot,
        "meta": {"err": err},
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": "Wallet11111111111111111111111111111111111"},
                    {"pubkey": program_id},
                ],
                "instructions": [
                    {
                        "programId": program_id,
                        "parsed": {"type": "example"},
                    }
                ],
            }
        },
    }


class FakeRPC:
    def __init__(self, *, account=None, history=None, transaction=None):
        self.account = account_result() if account is None else account
        self.history = history_result() if history is None else history
        self.transaction = (
            transaction_result() if transaction is None else transaction
        )
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "getAccountInfo":
            return self.account
        if method == "getSignaturesForAddress":
            return self.history
        if method == "getTransaction":
            return self.transaction
        raise AssertionError(f"unexpected RPC method {method}")


class X1AgentsRadioRPCCorroborationTests(unittest.TestCase):
    def test_program_candidate_corroborates_only_direct_chain_fields(self):
        rpc = FakeRPC(history=[])
        result = corroborate_agents_radio_with_x1_rpc(
            direct_candidate(),
            rpc_call=rpc,
        )

        self.assertEqual(
            result["contract_version"],
            "x1_agents_radio_rpc_corroboration/v1",
        )
        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["program_id"], PROGRAM_ID)
        self.assertEqual(result["overall_state"], PROGRAM_ACCOUNT_CORROBORATED)
        self.assertTrue(result["exact_program_account_corroborated"])
        self.assertTrue(result["rpc"]["account"]["account_exists"])
        self.assertTrue(result["rpc"]["account"]["executable"])
        self.assertEqual(result["rpc"]["account"]["owner"], OWNER)
        self.assertTrue(result["rpc"]["history"]["history_page_verified"])
        self.assertEqual(result["rpc"]["history"]["returned_count"], 0)
        self.assertFalse(
            result["rpc"]["history"]["empty_page_is_lifetime_inactivity_proof"]
        )

        claims = result["provider_claim_verification"]
        self.assertFalse(claims["name_verified"])
        self.assertFalse(claims["category_verified"])
        self.assertFalse(claims["framework_verified"])
        self.assertFalse(claims["status_verified"])
        self.assertFalse(claims["description_verified"])
        self.assertFalse(claims["instruction_semantics_verified"])
        self.assertFalse(claims["provider_verified_claim_promoted"])
        self.assertFalse(claims["tx_count_24h_verified"])
        self.assertFalse(claims["deployment_semantics_verified"])
        self.assertFalse(claims["upgrade_semantics_verified"])

        self.assertTrue(
            result[
                "rpc_is_canonical_direct_chain_verifier_for_returned_chain_fields"
            ]
        )
        self.assertFalse(result["radio_rpc_source_independence_verified"])
        self.assertFalse(result["same_fact_agreement_is_source_independence"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["risk_conclusion_authorized"])
        self.assertFalse(result["recommendation_authorized"])
        self.assertFalse(result["execution_authorized"])

        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo", "getSignaturesForAddress"],
        )
        self.assertEqual(
            rpc.calls[0][1],
            [
                PROGRAM_ID,
                {
                    "encoding": "base64",
                    "commitment": "finalized",
                },
            ],
        )
        self.assertEqual(
            rpc.calls[1][1],
            [
                PROGRAM_ID,
                {
                    "commitment": "finalized",
                    "limit": 25,
                },
            ],
        )

    def test_deployment_candidate_can_corroborate_activity_not_upgrade_semantics(self):
        rpc = FakeRPC()
        result = corroborate_agents_radio_with_x1_rpc(
            structured_deployment_candidate(),
            rpc_call=rpc,
        )

        self.assertEqual(
            result["overall_state"],
            REPORTED_SLOT_ACTIVITY_CORROBORATED,
        )
        self.assertEqual(result["reported_event_type"], "upgrade")
        self.assertEqual(result["reported_slot"], 500)
        self.assertTrue(result["reported_slot_activity_verified"])
        self.assertTrue(result["reported_slot_transaction_corroborated"])

        tx = result["rpc"]["reported_slot_transaction"]
        self.assertTrue(tx["transaction_available"])
        self.assertTrue(tx["slot_matches_reported"])
        self.assertTrue(tx["success_verified"])
        self.assertTrue(tx["references_program_id_verified"])
        self.assertTrue(tx["reported_slot_transaction_corroborated"])

        self.assertIn(
            "successful_activity_at_reported_slot",
            result["verified_chain_fields"],
        )
        self.assertIn(
            "reported_slot_transaction_references_program_id",
            result["verified_chain_fields"],
        )
        self.assertFalse(
            result["provider_claim_verification"]["deployment_semantics_verified"]
        )
        self.assertFalse(
            result["provider_claim_verification"]["upgrade_semantics_verified"]
        )
        self.assertFalse(result["cmis_verified"])

        self.assertEqual(
            [method for method, _params in rpc.calls],
            [
                "getAccountInfo",
                "getSignaturesForAddress",
                "getTransaction",
            ],
        )

    def test_reported_slot_not_in_bounded_history_is_not_negative_deployment_proof(self):
        rpc = FakeRPC(history=history_result(slot=501))
        result = corroborate_agents_radio_with_x1_rpc(
            structured_deployment_candidate(),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], EVIDENCE_INCOMPLETE)
        self.assertTrue(result["exact_program_account_corroborated"])
        self.assertFalse(result["reported_slot_activity_verified"])
        self.assertIsNone(result["rpc"]["reported_slot_transaction"])
        self.assertIn(
            "reported_slot_not_observed_in_bounded_successful_history",
            result["failures"],
        )
        self.assertFalse(
            result["provider_claim_verification"]["deployment_semantics_verified"]
        )
        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo", "getSignaturesForAddress"],
        )

    def test_failed_signature_at_reported_slot_does_not_corroborate_activity(self):
        rpc = FakeRPC(
            history=history_result(
                slot=500,
                err={"InstructionError": [0, "Custom"]},
            )
        )
        result = corroborate_agents_radio_with_x1_rpc(
            structured_deployment_candidate(),
            rpc_call=rpc,
        )

        self.assertFalse(result["reported_slot_activity_verified"])
        self.assertFalse(result["reported_slot_transaction_corroborated"])
        self.assertIsNone(result["rpc"]["reported_slot_transaction"])

    def test_transaction_must_match_slot_succeed_and_reference_program(self):
        cases = [
            transaction_result(slot=499),
            transaction_result(err={"InstructionError": [0, "Custom"]}),
            transaction_result(
                program_id=RADIO_PROGRAM_ID,
            ),
            None,
        ]
        for tx_result in cases:
            with self.subTest(tx_result=tx_result):
                rpc = FakeRPC(transaction=tx_result)
                result = corroborate_agents_radio_with_x1_rpc(
                    structured_deployment_candidate(),
                    rpc_call=rpc,
                )

                self.assertTrue(result["reported_slot_activity_verified"])
                self.assertFalse(
                    result["reported_slot_transaction_corroborated"]
                )
                self.assertIn(
                    "reported_slot_transaction_not_corroborated",
                    result["failures"],
                )

    def test_account_not_found_is_verified_absence_at_current_rpc_state(self):
        rpc = FakeRPC(
            account={
                "context": {"slot": 600},
                "value": None,
            },
        )
        result = corroborate_agents_radio_with_x1_rpc(
            direct_candidate(),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], ACCOUNT_NOT_FOUND)
        self.assertTrue(
            result["rpc"]["account"]["account_existence_verified"]
        )
        self.assertFalse(result["rpc"]["account"]["account_exists"])
        self.assertFalse(result["exact_program_account_corroborated"])
        self.assertIn("program_account_not_found", result["failures"])
        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo"],
        )

    def test_existing_non_executable_account_is_not_promoted_as_program(self):
        rpc = FakeRPC(account=account_result(executable=False), history=[])
        result = corroborate_agents_radio_with_x1_rpc(
            direct_candidate(),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], ACCOUNT_NOT_EXECUTABLE)
        self.assertTrue(result["rpc"]["account"]["account_exists"])
        self.assertTrue(result["rpc"]["account"]["executable_verified"])
        self.assertFalse(result["rpc"]["account"]["executable"])
        self.assertFalse(result["exact_program_account_corroborated"])
        self.assertIn("program_account_not_executable", result["failures"])

    def test_invalid_or_mis_scoped_candidate_fails_before_rpc(self):
        cases = [
            direct_candidate(program_id="not-base58"),
            direct_candidate(chain="solana"),
            direct_candidate(network="solana-mainnet"),
            direct_candidate(source="example.com"),
            direct_candidate(execution_authorized=True),
            {
                **structured_deployment_candidate(),
                "truth_state": {
                    "discovery_state": "DISCOVERED",
                    "cmis_verified": True,
                },
            },
            {
                **structured_deployment_candidate(),
                "program_id_syntax_valid": False,
            },
        ]

        for candidate in cases:
            with self.subTest(candidate=candidate):
                rpc = FakeRPC()
                with self.assertRaises(
                    X1AgentsRadioRPCCorroborationError
                ):
                    corroborate_agents_radio_with_x1_rpc(
                        candidate,
                        rpc_call=rpc,
                    )
                self.assertEqual(rpc.calls, [])

    def test_deployment_candidate_requires_reported_slot(self):
        candidate = structured_deployment_candidate(
            provider_deployment={"event_type": "upgrade"}
        )
        rpc = FakeRPC()
        with self.assertRaises(X1AgentsRadioRPCCorroborationError):
            corroborate_agents_radio_with_x1_rpc(
                candidate,
                rpc_call=rpc,
            )
        self.assertEqual(rpc.calls, [])

    def test_history_limit_is_bounded(self):
        for limit in (0, 101, True, "25"):
            with self.subTest(limit=limit):
                with self.assertRaises(
                    X1AgentsRadioRPCCorroborationError
                ):
                    corroborate_agents_radio_with_x1_rpc(
                        direct_candidate(),
                        rpc_call=FakeRPC(),
                        history_limit=limit,
                    )

        rpc = FakeRPC(history=[])
        result = corroborate_agents_radio_with_x1_rpc(
            direct_candidate(),
            rpc_call=rpc,
            history_limit=100,
        )
        self.assertEqual(result["rpc"]["history"]["requested_limit"], 100)

    def test_malformed_rpc_account_or_history_fails_closed(self):
        malformed_accounts = [
            None,
            {},
            {"context": {"slot": -1}, "value": None},
            {
                "context": {"slot": 1},
                "value": {
                    "executable": "yes",
                    "owner": OWNER,
                },
            },
        ]
        for account in malformed_accounts:
            with self.subTest(account=account):
                with self.assertRaises(
                    X1AgentsRadioRPCCorroborationError
                ):
                    corroborate_agents_radio_with_x1_rpc(
                        direct_candidate(),
                        rpc_call=FakeRPC(account=account),
                    )

        with self.assertRaises(X1AgentsRadioRPCCorroborationError):
            corroborate_agents_radio_with_x1_rpc(
                direct_candidate(),
                rpc_call=FakeRPC(history={"not": "a list"}),
            )

    def test_transaction_inspection_can_be_disabled_without_promoting_semantics(self):
        rpc = FakeRPC()
        result = corroborate_agents_radio_with_x1_rpc(
            structured_deployment_candidate(),
            rpc_call=rpc,
            inspect_reported_slot_transaction=False,
        )

        self.assertTrue(result["reported_slot_activity_verified"])
        self.assertFalse(result["reported_slot_transaction_corroborated"])
        self.assertIsNone(result["rpc"]["reported_slot_transaction"])
        self.assertFalse(
            result["provider_claim_verification"]["upgrade_semantics_verified"]
        )
        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo", "getSignaturesForAddress"],
        )


if __name__ == "__main__":
    unittest.main()
