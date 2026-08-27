import base64
import hashlib
import struct
import unittest
from datetime import datetime, timezone

import cmis_x1_oracle_v2_timestamp_unit_probe as probe


def _b58encode(value):
    alphabet = probe._B58_ALPHABET
    value = bytes(value)
    leading_zeroes = len(value) - len(value.lstrip(b"\x00"))
    number = int.from_bytes(value, "big")

    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded

    return "1" * leading_zeroes + (encoded or ("" if leading_zeroes else "1"))


def _batch_message(
    *,
    relay_index=2,
    prices=None,
    timestamp_raw=1_780_000_000_250,
):
    prices = prices or [
        70_000_000_000,
        4_000_000_000,
        150_000_000,
        20_000_000,
        45_000_000,
        1_200_000,
    ]
    rendered = ":".join(str(value) for value in prices)
    return (
        f"BATCH:{relay_index}:{rendered}:{timestamp_raw}"
    ).encode("ascii")


def _batch_instruction(
    *,
    relay_index=2,
    prices=None,
    timestamp_raw=1_780_000_000_250,
    program_id=probe.PROGRAM_ID,
    state_pda=probe.STATE_PDA,
):
    prices = prices or [
        70_000_000_000,
        4_000_000_000,
        150_000_000,
        20_000_000,
        45_000_000,
        1_200_000,
    ]
    message = _batch_message(
        relay_index=relay_index,
        prices=prices,
        timestamp_raw=timestamp_raw,
    )
    signature = bytes([17]) * 64

    data = bytearray()
    data.extend(probe.BATCH_SUBMIT_PRICES_DISCRIMINATOR)
    data.append(relay_index)
    data.extend(struct.pack("<I", len(prices)))
    data.extend(struct.pack("<6q", *prices))
    data.extend(struct.pack("<q", timestamp_raw))
    data.extend(signature)
    data.extend(struct.pack("<I", len(message)))
    data.extend(message)

    return {
        "programId": program_id,
        "accounts": [
            state_pda,
            "Relay1111111111111111111111111111111111111",
            "Sysvar1nstructions1111111111111111111111111",
        ],
        "data": _b58encode(data),
    }


def _ed25519_instruction(
    message,
    *,
    pubkey_byte=7,
    signature_byte=17,
):
    pubkey = bytes([pubkey_byte]) * 32
    signature = bytes([signature_byte]) * 64

    header_end = 16
    pubkey_offset = header_end
    sig_offset = pubkey_offset + len(pubkey)
    msg_offset = sig_offset + len(signature)

    data = bytearray([1, 0])
    data.extend(
        struct.pack(
            "<7H",
            sig_offset,
            0xFFFF,
            pubkey_offset,
            0xFFFF,
            msg_offset,
            len(message),
            0xFFFF,
        )
    )
    data.extend(pubkey)
    data.extend(signature)
    data.extend(message)

    return {
        "programId": probe.ED25519_PROGRAM_ID,
        "data": _b58encode(data),
    }


def _transaction(
    *,
    signature="Sig111",
    slot=123,
    block_time=1_780_000_000,
    timestamp_raw=1_780_000_000_250,
    relay_index=2,
    err=None,
    include_batch=True,
    include_ed25519=True,
    ed_after_batch=False,
    ed_pubkey_byte=7,
    ed_signature_byte=17,
):
    message = _batch_message(
        relay_index=relay_index,
        timestamp_raw=timestamp_raw,
    )
    instructions = []
    ed_instruction = _ed25519_instruction(
        message,
        pubkey_byte=ed_pubkey_byte,
        signature_byte=ed_signature_byte,
    )
    batch_instruction = _batch_instruction(
        relay_index=relay_index,
        timestamp_raw=timestamp_raw,
    )
    if ed_after_batch:
        if include_batch:
            instructions.append(batch_instruction)
        if include_ed25519:
            instructions.append(ed_instruction)
    else:
        if include_ed25519:
            instructions.append(ed_instruction)
        if include_batch:
            instructions.append(batch_instruction)

    return {
        "signature": signature,
        "transaction_available": True,
        "transaction": {
            "slot": slot,
            "blockTime": block_time,
            "meta": {
                "err": err,
                "logMessages": [
                    (
                        "Program log: Batch prices submitted for relay slot "
                        f"{relay_index}"
                    )
                ],
            },
            "transaction": {
                "message": {
                    "instructions": instructions,
                }
            },
        },
        "source": "X1 RPC getTransaction(jsonParsed)",
    }


def _history_row(
    *,
    signature="Sig111",
    slot=123,
    block_time=1_780_000_000,
    err=None,
):
    return {
        "address": probe.STATE_PDA,
        "signature": signature,
        "slot": slot,
        "err": err,
        "block_time": block_time,
        "confirmation_status": "finalized",
        "source": "X1 RPC getSignaturesForAddress",
    }


def _oracle_state_result(*, pubkey_byte=7, context_slot=999):
    account_data = bytearray(probe.ORACLE_STATE_ALLOCATED_BYTES)
    account_data[:8] = probe.ORACLE_STATE_DISCRIMINATOR
    start = probe.ORACLE_PUBKEY_OFFSET
    account_data[start : start + probe.ORACLE_PUBKEY_BYTES] = (
        bytes([pubkey_byte]) * probe.ORACLE_PUBKEY_BYTES
    )
    return {
        "context": {"slot": context_slot},
        "value": {
            "owner": probe.PROGRAM_ID,
            "executable": False,
            "lamports": 1,
            "data": [
                base64.b64encode(bytes(account_data)).decode("ascii"),
                "base64",
            ],
        },
    }


class _FakeRPCProvider:
    def __init__(
        self,
        *,
        history=None,
        transactions=None,
        block_times=None,
        oracle_state=None,
    ):
        self.history = history or [_history_row()]
        self.transactions = transactions or [_transaction()]
        self.block_times = block_times or {
            123: {
                "slot": 123,
                "block_time": 1_780_000_000,
                "block_time_verified": True,
                "source": "X1 RPC getBlockTime",
            }
        }
        self.oracle_state = oracle_state or _oracle_state_result()
        self.calls = []

    def request(self, method, params):
        self.calls.append(("request", method, params))
        if method != "getAccountInfo":
            raise AssertionError(f"unexpected RPC method: {method}")
        return self.oracle_state

    def get_signatures_for_address(self, address, *, limit=1000):
        self.calls.append(("history", address, limit))
        return self.history

    def get_parsed_transactions(self, signatures):
        self.calls.append(("transactions", tuple(signatures)))
        return self.transactions

    def get_block_time(self, slot):
        self.calls.append(("block_time", slot))
        return self.block_times[slot]


class OracleV2TimestampUnitProbeTests(unittest.TestCase):
    def test_anchor_batch_discriminator_is_pinned(self):
        self.assertEqual(
            probe.batch_submit_prices_discriminator(),
            probe.BATCH_SUBMIT_PRICES_DISCRIMINATOR,
        )
        self.assertEqual(
            probe.BATCH_SUBMIT_PRICES_DISCRIMINATOR.hex(),
            "116224b954f96553",
        )

    def test_signed_batch_message_parses_exact_shape(self):
        parsed = probe.parse_batch_signed_message(_batch_message())

        self.assertEqual(parsed["relay_index"], 2)
        self.assertEqual(len(parsed["prices_raw"]), 6)
        self.assertEqual(parsed["timestamp_raw"], 1_780_000_000_250)
        self.assertEqual(
            parsed["message_sha256"],
            hashlib.sha256(_batch_message()).hexdigest(),
        )

    def test_signed_batch_message_rejects_bad_field_count(self):
        with self.assertRaises(probe.OracleV2TimestampProbeError):
            probe.parse_batch_signed_message(
                b"BATCH:1:1:2:3:4:5:123"
            )

    def test_signed_batch_message_rejects_invalid_relay(self):
        with self.assertRaises(probe.OracleV2TimestampProbeError):
            probe.parse_batch_signed_message(
                _batch_message(relay_index=6)
            )

    def test_batch_instruction_decodes_and_matches_signed_message(self):
        decoded = probe.decode_batch_submit_prices_instruction(
            _batch_instruction()
        )

        self.assertEqual(decoded["relay_index"], 2)
        self.assertEqual(decoded["timestamp_raw"], 1_780_000_000_250)
        self.assertEqual(len(decoded["prices_raw"]), 6)
        self.assertEqual(decoded["accounts"][0], probe.STATE_PDA)
        self.assertFalse(
            decoded["deployed_binary_source_equivalence_verified"]
        )

    def test_batch_instruction_rejects_wrong_state_pda(self):
        with self.assertRaises(probe.OracleV2TimestampProbeError):
            probe.decode_batch_submit_prices_instruction(
                _batch_instruction(state_pda="WrongState111")
            )

    def test_ed25519_instruction_extracts_matching_message_without_raw_signature(self):
        message = _batch_message()
        decoded = probe.decode_ed25519_instruction(
            _ed25519_instruction(message)
        )

        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]["message"], message)
        self.assertEqual(
            decoded[0]["message_sha256"],
            hashlib.sha256(message).hexdigest(),
        )
        self.assertNotIn("signature", decoded[0])
        self.assertNotIn("pubkey", decoded[0])

    def test_probe_reports_raw_difference_without_hidden_tolerance(self):
        provider = _FakeRPCProvider()

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
            history_limit=25,
            observed_at=datetime(
                2026,
                8,
                27,
                3,
                50,
                tzinfo=timezone.utc,
            ),
        )

        self.assertEqual(result["status"], "evidence_collected")
        self.assertEqual(
            result["summary"]["decoded_verified_batch_samples"],
            1,
        )
        self.assertEqual(
            result["samples"][0]["candidate_unix_ms_difference_ms"],
            250,
        )
        self.assertIsNone(
            result["samples"][0]["explicit_correlation_assessment"]
        )
        self.assertFalse(
            result["summary"]["explicit_correlation_policy_configured"]
        )
        self.assertFalse(result["summary"]["timestamp_unit_verified"])
        self.assertFalse(result["promotion"]["timestamp_unit_verified"])
        self.assertFalse(result["promotion"]["freshness_verified"])
        self.assertFalse(result["promotion"]["current_price_use_authorized"])
        self.assertFalse(result["promotion"]["execution_authorized"])

    def test_explicit_tolerance_requires_provenance(self):
        with self.assertRaisesRegex(
            probe.OracleV2TimestampProbeError,
            "supplied together",
        ):
            probe.probe_timestamp_unit_evidence(
                rpc_provider=_FakeRPCProvider(),
                max_difference_ms=500,
            )

    def test_explicit_correlation_can_pass_per_sample_without_global_promotion(self):
        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=_FakeRPCProvider(),
            max_difference_ms=500,
            tolerance_provenance="test fixture only",
        )

        assessment = result["samples"][0][
            "explicit_correlation_assessment"
        ]
        self.assertTrue(assessment["verified"])
        self.assertEqual(assessment["difference_ms"], 250)
        self.assertTrue(
            result["summary"]["all_samples_within_explicit_tolerance"]
        )
        self.assertFalse(result["summary"]["timestamp_unit_verified"])
        self.assertFalse(
            result["summary"][
                "timestamp_unit_sample_sufficiency_policy_defined"
            ]
        )

    def test_failed_transaction_is_not_accepted(self):
        provider = _FakeRPCProvider(
            history=[_history_row(err={"InstructionError": [1, "x"]})],
            transactions=[],
        )

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["summary"]["decoded_verified_batch_samples"],
            0,
        )

    def test_missing_ed25519_link_rejects_candidate(self):
        provider = _FakeRPCProvider(
            transactions=[
                _transaction(include_ed25519=False)
            ]
        )

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["rejected_transactions"][0]["reason"],
            "matching_ed25519_preinstruction_not_found",
        )

    def test_signature_mismatch_rejects_candidate(self):
        provider = _FakeRPCProvider(
            transactions=[
                _transaction(ed_signature_byte=9)
            ]
        )

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["rejected_transactions"][0]["reason"],
            "matching_ed25519_preinstruction_not_found",
        )

    def test_oracle_pubkey_mismatch_rejects_candidate(self):
        provider = _FakeRPCProvider(
            transactions=[
                _transaction(ed_pubkey_byte=8)
            ]
        )

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["rejected_transactions"][0]["reason"],
            "matching_ed25519_preinstruction_not_found",
        )

    def test_ed25519_after_oracle_instruction_rejects_candidate(self):
        provider = _FakeRPCProvider(
            transactions=[
                _transaction(ed_after_batch=True)
            ]
        )

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["rejected_transactions"][0]["reason"],
            "matching_ed25519_preinstruction_not_found",
        )

    def test_current_oracle_pubkey_is_preserved_as_hash_only(self):
        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=_FakeRPCProvider(),
        )

        expected = hashlib.sha256(bytes([7]) * 32).hexdigest()
        self.assertEqual(
            result["oracle_key_evidence"]["oracle_pubkey_sha256"],
            expected,
        )
        self.assertNotIn("oracle_pubkey", result["oracle_key_evidence"])
        sample = result["samples"][0]
        self.assertTrue(sample["ed25519_signature_matches_batch_argument"])
        self.assertTrue(sample["ed25519_pubkey_matches_current_state"])
        self.assertTrue(sample["ed25519_precedes_oracle_instruction"])
        self.assertEqual(
            sample["configured_oracle_pubkey_sha256"],
            expected,
        )

    def test_get_block_time_mismatch_rejects_candidate(self):
        provider = _FakeRPCProvider(
            block_times={
                123: {
                    "slot": 123,
                    "block_time": 1_780_000_001,
                    "block_time_verified": True,
                    "source": "X1 RPC getBlockTime",
                }
            }
        )

        result = probe.probe_timestamp_unit_evidence(
            rpc_provider=provider,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["rejected_transactions"][0]["reason"],
            "getBlockTime_transaction_block_time_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
