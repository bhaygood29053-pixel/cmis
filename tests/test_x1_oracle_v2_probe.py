import base64
import struct
import unittest
from datetime import datetime, timezone

import cmis_x1_oracle_v2_probe as probe


def _build_state_bytes(*, zero_first_price=False):
    payload = bytearray()
    payload.extend(probe.ORACLE_STATE_DISCRIMINATOR)
    payload.extend(bytes(range(32)))
    payload.extend(bytes([7]) * 32)
    payload.append(probe.DECIMALS)
    payload.append(255)

    timestamp_base = 1_780_000_000_000
    for asset_index, _asset in enumerate(probe.ASSETS, start=1):
        prices = [
            asset_index * 1_000_000 + slot
            for slot in range(probe.NUM_SLOTS)
        ]
        if zero_first_price and asset_index == 1:
            prices[0] = 0
        timestamps = [
            timestamp_base + asset_index * 100 + slot
            for slot in range(probe.NUM_SLOTS)
        ]
        payload.extend(struct.pack("<5q", *prices))
        payload.extend(struct.pack("<5q", *timestamps))

    assert len(payload) == probe.SERIALIZED_STATE_BYTES
    payload.extend(b"\x00" * 64)
    assert len(payload) == probe.ALLOCATED_STATE_BYTES
    return bytes(payload)


def _rpc_account(data, *, owner, executable, slot=12345):
    return {
        "context": {"slot": slot},
        "value": {
            "data": [base64.b64encode(data).decode("ascii"), "base64"],
            "executable": executable,
            "lamports": 1,
            "owner": owner,
            "rentEpoch": 0,
        },
    }


class _FakeRPCProvider:
    def __init__(self, state_data):
        self.state_data = state_data
        self.calls = []

    def request(self, method, params):
        self.calls.append((method, params))
        address = params[0]
        if address == probe.PROGRAM_ID:
            return _rpc_account(
                b"program-bytes",
                owner="BPFLoaderUpgradeab1e11111111111111111111111",
                executable=True,
            )
        if address == probe.STATE_PDA:
            return _rpc_account(
                self.state_data,
                owner=probe.PROGRAM_ID,
                executable=False,
                slot=12346,
            )
        raise AssertionError(f"unexpected account request: {address}")


class OracleV2ProbeTests(unittest.TestCase):
    def test_declared_state_pda_derives_from_pinned_contract(self):
        derived = probe.derive_program_address()
        self.assertEqual(derived["address"], probe.STATE_PDA)
        self.assertEqual(derived["bump"], 255)

    def test_anchor_discriminator_matches_pinned_contract(self):
        self.assertEqual(
            probe.oracle_state_discriminator(),
            probe.ORACLE_STATE_DISCRIMINATOR,
        )
        self.assertEqual(
            probe.ORACLE_STATE_DISCRIMINATOR.hex(),
            "619c9dbdc249080f",
        )

    def test_decode_oracle_state_uses_exact_layout(self):
        decoded = probe.decode_oracle_state(_build_state_bytes())

        self.assertEqual(decoded["decimals"], 6)
        self.assertEqual(decoded["bump"], 255)
        self.assertEqual(
            decoded["account_data_length"],
            probe.ALLOCATED_STATE_BYTES,
        )
        self.assertEqual(decoded["trailing_allocated_bytes"], 64)
        self.assertEqual(decoded["trailing_nonzero_bytes"], 0)
        self.assertEqual(decoded["assets"]["BTC"]["prices_raw"][0], 1_000_000)
        self.assertEqual(decoded["assets"]["BTC"]["prices"][0], "1")
        self.assertEqual(decoded["assets"]["FARTCOIN"]["prices_raw"][4], 6_000_004)
        self.assertEqual(
            decoded["assets"]["FARTCOIN"]["timestamps_raw"][4],
            1_780_000_000_604,
        )

    def test_decode_rejects_wrong_anchor_discriminator(self):
        data = bytearray(_build_state_bytes())
        data[0] ^= 0xFF

        with self.assertRaises(probe.OracleV2ProbeError):
            probe.decode_oracle_state(bytes(data))

    def test_probe_verifies_contract_shape_without_promoting(self):
        provider = _FakeRPCProvider(_build_state_bytes())
        observed_at = datetime(
            2026,
            8,
            27,
            3,
            30,
            tzinfo=timezone.utc,
        )

        result = probe.probe_oracle_v2(
            rpc_provider=provider,
            observed_at=observed_at,
        )

        self.assertEqual(result["status"], "verified_contract_shape")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["summary"]["total_slots"], 30)
        self.assertEqual(result["summary"]["nonzero_price_slots"], 30)
        self.assertEqual(
            result["summary"]["structurally_valid_slots_before_timestamp_unit_and_freshness"],
            30,
        )
        self.assertEqual(result["summary"]["cmis_price_eligible_slots"], 0)
        self.assertFalse(result["summary"]["timestamp_unit_live_verified"])
        self.assertEqual(
            result["summary"]["source_contract_timestamp_unit"],
            "unix_ms",
        )
        self.assertEqual(
            result["summary"]["min_relay_timestamp_raw"],
            1_780_000_000_100,
        )
        self.assertEqual(
            result["summary"]["max_relay_timestamp_raw"],
            1_780_000_000_604,
        )
        self.assertFalse(result["summary"]["freshness_policy_applied"])
        self.assertFalse(result["summary"]["current_price_use_authorized"])
        self.assertFalse(result["summary"]["source_independence_verified"])
        self.assertFalse(result["promotion"]["cmis_promotable"])
        self.assertFalse(result["promotion"]["execution_authorized"])
        self.assertEqual(len(provider.calls), 2)

    def test_zero_price_slot_is_never_marked_cmis_eligible(self):
        provider = _FakeRPCProvider(
            _build_state_bytes(zero_first_price=True)
        )

        result = probe.probe_oracle_v2(
            rpc_provider=provider,
            observed_at=datetime(
                2026,
                8,
                27,
                3,
                30,
                tzinfo=timezone.utc,
            ),
        )

        first = result["slot_observations"][0]
        self.assertTrue(first["zero_price"])
        self.assertFalse(first["structurally_valid_before_timestamp_unit_and_freshness"])
        self.assertFalse(first["cmis_price_eligible"])
        self.assertFalse(first["timestamp_unit_live_verified"])
        self.assertEqual(first["source_contract_timestamp_unit"], "unix_ms")
        self.assertEqual(
            first["cmis_price_eligibility_reason"],
            "nonpositive_price_or_timestamp",
        )
        self.assertEqual(first["freshness_classification"], "not_applied")
        self.assertEqual(result["summary"]["nonzero_price_slots"], 29)
        self.assertEqual(result["summary"]["cmis_price_eligible_slots"], 0)


if __name__ == "__main__":
    unittest.main()
