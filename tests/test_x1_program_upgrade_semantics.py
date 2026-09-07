from __future__ import annotations

import base64
import json
import unittest
from pathlib import Path

from liquidity_scout.providers.x1.program_upgrade_semantics import (
    BPF_UPGRADEABLE_LOADER,
    CONTRACT_VERSION,
    DEPLOYMENT_VERIFIED,
    EVIDENCE_INCOMPLETE,
    NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION,
    NOT_UPGRADEABLE_LOADER_PROGRAM,
    PROGRAM_STATE_VERIFIED,
    RADIO_EVENT_LABEL_MISMATCH,
    UPGRADE_VERIFIED,
    X1ProgramUpgradeSemanticVerificationError,
    decode_upgradeable_loader_state,
    verify_program_upgrade_semantics,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


PROGRAM_ID = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
PROGRAMDATA = "4Ai4Ps8YsrLfshU9xvkf9pobiVhewELdbXEZA7zaZ8E3"
AUTHORITY = "9zkypzFPQ2s3D5UqbYuixt3iXo5ig3ZNWLK1TrbNf5eR"
BUFFER = "F3ydfNgdM89BK5hDh7amVmt8AAGQSYCX1afb3EWZKGh8"
SPILL = "11111111111111111111111111111111"
RENT = "SysvarRent111111111111111111111111111111111"
CLOCK = "SysvarC1ock11111111111111111111111111111111"
SIGNATURE = "5" * 88


def b58decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    index = {char: i for i, char in enumerate(alphabet)}
    number = 0
    leading = 0
    for pos, char in enumerate(value):
        if pos == leading and char == "1":
            leading += 1
        number = number * 58 + index[char]
    payload = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    return b"\x00" * leading + payload


def b58encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    leading = len(value) - len(value.lstrip(b"\x00"))
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, rem = divmod(number, 58)
        encoded = alphabet[rem] + encoded
    return "1" * leading + encoded


def program_state(programdata=PROGRAMDATA):
    return (2).to_bytes(4, "little") + b58decode(programdata)


def programdata_state(*, slot=500, authority=AUTHORITY, code=b"program-bytes"):
    payload = (3).to_bytes(4, "little") + slot.to_bytes(8, "little")
    if authority is None:
        payload += b"\x00" + (b"\x00" * 32)
    else:
        payload += b"\x01" + b58decode(authority)
    return payload + code


def account_result(
    address,
    *,
    data,
    owner=BPF_UPGRADEABLE_LOADER,
    executable=False,
    observation_slot=700,
):
    return {
        "context": {"slot": observation_slot},
        "value": {
            "data": [base64.b64encode(data).decode("ascii"), "base64"],
            "executable": executable,
            "lamports": 123,
            "owner": owner,
            "space": len(data),
        },
    }


def corroboration(*, reported_slot=500, event_type="upgraded"):
    return {
        "contract_version": "x1_agents_radio_rpc_corroboration/v1",
        "chain": "x1",
        "network": "x1-mainnet",
        "program_id": PROGRAM_ID,
        "reported_event_type": event_type,
        "reported_slot": reported_slot,
        "rpc": {
            "reported_slot_transaction": {
                "signature": SIGNATURE,
                "transaction_available": True,
                "transaction_result_verified": True,
                "slot": reported_slot,
                "slot_matches_reported": True,
                "success_verified": True,
                "references_program_id_verified": True,
                "reported_slot_transaction_corroborated": True,
            }
        },
        "execution_authorized": False,
    }


def instruction_data(discriminator, *, max_data_len=None, close_buffer=None):
    raw = int(discriminator).to_bytes(4, "little")
    if discriminator == 2:
        raw += int(max_data_len or 0).to_bytes(8, "little")
    if close_buffer is not None:
        raw += bytes([1 if close_buffer else 0])
    return b58encode(raw)


def tx(
    *,
    slot=500,
    semantic="upgrade",
    program=PROGRAM_ID,
    programdata=PROGRAMDATA,
    include_loader=True,
    exact_binding=True,
    err=None,
):
    keys = [
        {"pubkey": AUTHORITY, "signer": True, "writable": False},
        {"pubkey": program, "signer": False, "writable": True},
        {"pubkey": programdata, "signer": False, "writable": True},
        {"pubkey": BPF_UPGRADEABLE_LOADER, "signer": False, "writable": False},
    ]

    instructions = []
    if include_loader:
        if semantic == "upgrade":
            accounts = [
                programdata,
                program,
                BUFFER,
                SPILL,
                RENT,
                CLOCK,
                AUTHORITY,
            ]
            if not exact_binding:
                accounts[1] = AUTHORITY
            data = instruction_data(3)
        elif semantic == "deploy":
            accounts = [
                AUTHORITY,
                programdata,
                program,
                BUFFER,
                RENT,
                CLOCK,
                SPILL,
                AUTHORITY,
            ]
            if not exact_binding:
                accounts[2] = AUTHORITY
            data = instruction_data(2, max_data_len=1_000_000)
        else:
            raise AssertionError(semantic)

        instructions.append(
            {
                "programId": BPF_UPGRADEABLE_LOADER,
                "accounts": accounts,
                "data": data,
            }
        )
    else:
        instructions.append(
            {
                "programId": program,
                "accounts": [AUTHORITY],
                "data": "1",
            }
        )

    return {
        "slot": slot,
        "meta": {
            "err": err,
            "innerInstructions": [],
        },
        "transaction": {
            "message": {
                "accountKeys": keys,
                "instructions": instructions,
            }
        },
    }


class FakeRPC:
    def __init__(
        self,
        *,
        program_owner=BPF_UPGRADEABLE_LOADER,
        program_executable=True,
        programdata_owner=BPF_UPGRADEABLE_LOADER,
        programdata_executable=False,
        programdata_slot=500,
        authority=AUTHORITY,
        transaction=None,
    ):
        self.calls = []
        self.program = account_result(
            PROGRAM_ID,
            data=program_state(),
            owner=program_owner,
            executable=program_executable,
        )
        self.programdata = account_result(
            PROGRAMDATA,
            data=programdata_state(
                slot=programdata_slot,
                authority=authority,
            ),
            owner=programdata_owner,
            executable=programdata_executable,
        )
        self.transaction = tx() if transaction is None else transaction

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "getAccountInfo":
            if params[0] == PROGRAM_ID:
                return self.program
            if params[0] == PROGRAMDATA:
                return self.programdata
            raise AssertionError(params[0])
        if method == "getTransaction":
            self.assert_finalized_transaction_params(params)
            return self.transaction
        raise AssertionError(method)

    @staticmethod
    def assert_finalized_transaction_params(params):
        assert params[0] == SIGNATURE
        assert params[1] == {
            "encoding": "jsonParsed",
            "commitment": "finalized",
            "maxSupportedTransactionVersion": 0,
        }


class X1ProgramUpgradeSemanticVerificationTests(unittest.TestCase):
    def test_existing_xdex_fixture_matches_upgradeable_program_envelope(self):
        fixture = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "xdex_program_recent_20260904.json"
            ).read_text()
        )
        info = fixture["program_information"]

        self.assertEqual(fixture["program_account"], PROGRAM_ID)
        self.assertEqual(info["owner"], BPF_UPGRADEABLE_LOADER)
        self.assertEqual(info["status"], "Executable")
        self.assertEqual(info["data_size_bytes"], 36)
        self.assertTrue(info["upgradeable"])

    def test_decodes_upgradeable_loader_program_state(self):
        result = decode_upgradeable_loader_state(program_state())

        self.assertEqual(result["state"], "Program")
        self.assertEqual(result["discriminator"], 2)
        self.assertEqual(result["programdata_address"], PROGRAMDATA)

    def test_decodes_programdata_upgradeable_and_immutable_state(self):
        upgradeable = decode_upgradeable_loader_state(
            programdata_state(slot=500, authority=AUTHORITY)
        )
        immutable = decode_upgradeable_loader_state(
            programdata_state(slot=600, authority=None)
        )

        self.assertEqual(upgradeable["state"], "ProgramData")
        self.assertEqual(upgradeable["slot"], 500)
        self.assertEqual(
            upgradeable["upgrade_authority_address"],
            AUTHORITY,
        )
        self.assertTrue(upgradeable["upgradeable"])

        self.assertEqual(immutable["slot"], 600)
        self.assertIsNone(immutable["upgrade_authority_address"])
        self.assertFalse(immutable["upgradeable"])

    def test_exact_upgrade_transaction_becomes_verified_upgrade_semantics(self):
        rpc = FakeRPC()
        result = verify_program_upgrade_semantics(
            corroboration(event_type="upgraded"),
            rpc_call=rpc,
        )

        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["overall_state"], UPGRADE_VERIFIED)
        self.assertTrue(result["current_program_state_verified"])
        self.assertEqual(result["programdata_address"], PROGRAMDATA)
        self.assertEqual(result["current_programdata_slot"], 500)
        self.assertEqual(result["current_upgrade_authority"], AUTHORITY)
        self.assertTrue(result["current_upgradeability_verified"])
        self.assertTrue(result["current_upgradeable"])
        self.assertFalse(result["current_immutable"])
        self.assertTrue(result["transaction_success_and_slot_verified"])
        self.assertEqual(result["verified_semantic_type"], "UPGRADE")
        self.assertTrue(result["reported_event_semantics_verified"])
        self.assertTrue(
            result["radio_event_label_matches_verified_semantics"]
        )
        self.assertTrue(
            result["current_programdata_slot_matches_reported_event"]
        )
        self.assertFalse(result["later_program_modification_observed"])

        event = result["verified_event"]
        self.assertEqual(event["instruction_name"], "Upgrade")
        self.assertEqual(event["discriminator"], 3)
        self.assertTrue(event["programdata_matches"])
        self.assertTrue(event["program_matches"])
        self.assertTrue(event["exact_account_binding_verified"])
        self.assertEqual(event["authority"], AUTHORITY)
        self.assertTrue(event["authority_signer_verified"])

        self.assertFalse(
            result["current_upgrade_authority_is_historical_event_authority"]
        )
        self.assertFalse(result["program_bytecode_semantics_verified"])
        self.assertFalse(result["application_instruction_semantics_verified"])
        self.assertFalse(result["radio_name_category_framework_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["risk_conclusion_authorized"])
        self.assertFalse(result["recommendation_authorized"])
        self.assertFalse(result["execution_authorized"])

        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo", "getAccountInfo", "getTransaction"],
        )
        for method, params in rpc.calls[:2]:
            self.assertEqual(method, "getAccountInfo")
            self.assertEqual(
                params[1],
                {
                    "encoding": "base64",
                    "commitment": "finalized",
                },
            )

    def test_exact_deploy_transaction_becomes_verified_deployment_semantics(self):
        rpc = FakeRPC(transaction=tx(semantic="deploy"))
        result = verify_program_upgrade_semantics(
            corroboration(event_type="deployed"),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], DEPLOYMENT_VERIFIED)
        self.assertEqual(result["verified_semantic_type"], "DEPLOY")
        event = result["verified_event"]
        self.assertEqual(event["instruction_name"], "DeployWithMaxDataLen")
        self.assertEqual(event["discriminator"], 2)
        self.assertEqual(event["max_data_len"], 1_000_000)
        self.assertTrue(event["exact_account_binding_verified"])
        self.assertTrue(result["radio_event_label_matches_verified_semantics"])

    def test_radio_upgrade_label_does_not_override_verified_deploy_semantics(self):
        rpc = FakeRPC(transaction=tx(semantic="deploy"))
        result = verify_program_upgrade_semantics(
            corroboration(event_type="upgraded"),
            rpc_call=rpc,
        )

        self.assertEqual(result["verified_semantic_type"], "DEPLOY")
        self.assertEqual(result["overall_state"], RADIO_EVENT_LABEL_MISMATCH)
        self.assertTrue(result["reported_event_semantics_verified"])
        self.assertFalse(
            result["radio_event_label_matches_verified_semantics"]
        )
        self.assertIn(
            "radio_event_label_does_not_match_loader_semantics",
            result["failures"],
        )

    def test_ordinary_program_activity_is_not_upgrade_proof(self):
        rpc = FakeRPC(transaction=tx(include_loader=False))
        result = verify_program_upgrade_semantics(
            corroboration(event_type="upgraded"),
            rpc_call=rpc,
        )

        self.assertEqual(
            result["overall_state"],
            NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION,
        )
        self.assertIsNone(result["verified_event"])
        self.assertIsNone(result["verified_semantic_type"])
        self.assertFalse(result["reported_event_semantics_verified"])
        self.assertFalse(
            result["radio_event_label_matches_verified_semantics"]
        )

    def test_loader_instruction_must_bind_exact_program_and_programdata(self):
        rpc = FakeRPC(transaction=tx(exact_binding=False))
        result = verify_program_upgrade_semantics(
            corroboration(event_type="upgraded"),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], EVIDENCE_INCOMPLETE)
        self.assertIsNone(result["verified_event"])
        self.assertFalse(result["reported_event_semantics_verified"])
        event = result["loader_event_scan"]["events"][0]
        self.assertFalse(event["exact_account_binding_verified"])
        self.assertFalse(event["program_matches"])

    def test_historical_verified_upgrade_survives_later_program_modification(self):
        rpc = FakeRPC(programdata_slot=700)
        result = verify_program_upgrade_semantics(
            corroboration(reported_slot=500, event_type="upgrade"),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], UPGRADE_VERIFIED)
        self.assertTrue(result["programdata_slot_not_before_event"])
        self.assertFalse(
            result["current_programdata_slot_matches_reported_event"]
        )
        self.assertTrue(result["later_program_modification_observed"])
        self.assertEqual(result["current_programdata_slot"], 700)

    def test_current_programdata_slot_cannot_precede_verified_event(self):
        rpc = FakeRPC(programdata_slot=400)
        result = verify_program_upgrade_semantics(
            corroboration(reported_slot=500, event_type="upgrade"),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], EVIDENCE_INCOMPLETE)
        self.assertFalse(result["programdata_slot_not_before_event"])
        self.assertFalse(result["reported_event_semantics_verified"])
        self.assertIn(
            "current_programdata_slot_precedes_reported_event",
            result["failures"],
        )

    def test_current_immutable_program_is_verified_without_historical_overclaim(self):
        rpc = FakeRPC(authority=None)
        result = verify_program_upgrade_semantics(
            corroboration(event_type="upgrade"),
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], UPGRADE_VERIFIED)
        self.assertTrue(result["current_upgradeability_verified"])
        self.assertFalse(result["current_upgradeable"])
        self.assertTrue(result["current_immutable"])
        self.assertIsNone(result["current_upgrade_authority"])
        self.assertFalse(
            result["current_upgrade_authority_is_historical_event_authority"]
        )

    def test_non_upgradeable_loader_program_is_not_semantically_promoted(self):
        rpc = FakeRPC(program_owner="BPFLoader2111111111111111111111111111111111")
        result = verify_program_upgrade_semantics(
            corroboration(event_type="upgrade"),
            rpc_call=rpc,
        )

        self.assertEqual(
            result["overall_state"],
            NOT_UPGRADEABLE_LOADER_PROGRAM,
        )
        self.assertFalse(result["current_program_state_verified"])
        self.assertFalse(result["reported_event_semantics_verified"])
        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo"],
        )

    def test_program_only_verification_without_event_is_supported(self):
        no_event = corroboration()
        no_event["reported_slot"] = None
        no_event["reported_event_type"] = None
        no_event["rpc"]["reported_slot_transaction"] = None

        rpc = FakeRPC()
        result = verify_program_upgrade_semantics(
            no_event,
            rpc_call=rpc,
        )

        self.assertEqual(result["overall_state"], PROGRAM_STATE_VERIFIED)
        self.assertTrue(result["current_program_state_verified"])
        self.assertIsNone(result["verified_event"])
        self.assertEqual(
            [method for method, _params in rpc.calls],
            ["getAccountInfo", "getAccountInfo"],
        )

    def test_prior_corroboration_contract_is_required(self):
        cases = [
            {},
            {**corroboration(), "contract_version": "other/v1"},
            {**corroboration(), "chain": "solana"},
            {**corroboration(), "execution_authorized": True},
        ]

        for evidence in cases:
            with self.subTest(evidence=evidence):
                rpc = FakeRPC()
                with self.assertRaises(
                    X1ProgramUpgradeSemanticVerificationError
                ):
                    verify_program_upgrade_semantics(
                        evidence,
                        rpc_call=rpc,
                    )
                self.assertEqual(rpc.calls, [])

    def test_reported_event_requires_prior_exact_transaction_corroboration(self):
        evidence = corroboration()
        evidence["rpc"]["reported_slot_transaction"][
            "reported_slot_transaction_corroborated"
        ] = False

        rpc = FakeRPC()
        with self.assertRaises(X1ProgramUpgradeSemanticVerificationError):
            verify_program_upgrade_semantics(
                evidence,
                rpc_call=rpc,
            )
        self.assertEqual(rpc.calls, [])

    def test_malformed_loader_state_fails_closed(self):
        with self.assertRaises(X1ProgramUpgradeSemanticVerificationError):
            decode_upgradeable_loader_state(b"\x02\x00")

        with self.assertRaises(X1ProgramUpgradeSemanticVerificationError):
            decode_upgradeable_loader_state(
                (2).to_bytes(4, "little") + b"\x00" * 31
            )

        with self.assertRaises(X1ProgramUpgradeSemanticVerificationError):
            decode_upgradeable_loader_state(
                (3).to_bytes(4, "little")
                + (1).to_bytes(8, "little")
                + b"\x02"
            )

    def test_internal_service_preserves_nonpromotion_boundary(self):
        service = CMISWebDiscoveryService()
        rpc = FakeRPC()

        result = service.verify_x1_program_upgrade_semantics(
            corroboration(event_type="upgrade"),
            rpc_call=rpc,
        )

        self.assertEqual(result["source_id"], "x1_agents_radio")
        self.assertEqual(
            result["semantic_verification"]["contract_version"],
            CONTRACT_VERSION,
        )
        self.assertEqual(
            result["semantic_verification"]["overall_state"],
            UPGRADE_VERIFIED,
        )
        self.assertTrue(result["read_only"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
