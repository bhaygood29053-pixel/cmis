import base64
import unittest

from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT,
    INCOMING_ACCOUNT,
    OUTGOING_ACCOUNT,
    WarpOnchainTransferHistoryError,
    decode_incoming_account,
    decode_outgoing_account,
    normalize_warp_route_events,
)
from liquidity_scout.providers.x1.warp_semantic_layout_discovery import (
    anchor_account_discriminator,
    create_program_address,
)


ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58decode(value):
    n = 0
    for char in value:
        n = n * 58 + ALPHABET.index(char)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return bytes(len(value) - len(value.lstrip("1"))) + raw


def pda(seed, seq, bump):
    return create_program_address(
        [seed, int(seq).to_bytes(8, "little"), bytes([bump])]
    )


def find_pda(seed, seq):
    for bump in range(255, -1, -1):
        try:
            return pda(seed, seq, bump), bump
        except WarpOnchainTransferHistoryError:
            pass
        except Exception:
            pass
    raise AssertionError("no PDA bump")


def outgoing_raw(*, seq, sender, mint, amount, timestamp, operation, bump):
    raw = bytearray(anchor_account_discriminator(OUTGOING_ACCOUNT))
    raw += int(seq).to_bytes(8, "little")
    raw += b58decode(sender)
    raw += b58decode(mint)
    raw += int(amount).to_bytes(8, "little")
    raw += int(timestamp).to_bytes(8, "little", signed=True)
    raw += (0).to_bytes(8, "little")
    raw += bytes([operation, bump])
    assert len(raw) == 106
    return bytes(raw)


def incoming_raw(
    *,
    seq,
    sender,
    mint,
    amount,
    source_timestamp,
    executed_timestamp,
    operation,
    processed,
    bump,
    claimable_after=0,
    claimed=True,
):
    raw = bytearray(anchor_account_discriminator(INCOMING_ACCOUNT))
    raw += int(seq).to_bytes(8, "little")
    raw += b58decode(sender)
    raw += b58decode(mint)
    raw += int(amount).to_bytes(8, "little")
    raw += int(source_timestamp).to_bytes(8, "little", signed=True)
    raw += int(executed_timestamp).to_bytes(8, "little", signed=True)
    raw += bytes([operation, int(bool(processed)), bump])
    raw += int(claimable_after).to_bytes(8, "little", signed=True)
    raw += bytes([int(bool(claimed))])
    assert len(raw) == 116
    return bytes(raw)


def route():
    return {
        "contract": "warp_config_semantics/v1",
        "semantic_contract_id": "warp_config/exact-mint-pair/v1",
        "route_id": "warp-solana-x1-wsol",
        "source": {
            "chain": "solana",
            "asset_id": "So11111111111111111111111111111111111111112",
            "asset_id_kind": "mint",
        },
        "destination": {
            "chain": "x1",
            "asset_id": "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8",
            "asset_id_kind": "mint",
        },
        "source_is_native": True,
        "destination_is_native": False,
        "route_decimals": 9,
    }


def snapshot(sol_out=None, sol_in=None, x1_out=None, x1_in=None):
    def block(account_type, rows):
        return {
            "account_type": account_type,
            "account_type_identity_verified": True,
            "all_pda_identities_verified": True,
            "accounts": list(rows or []),
        }

    return {
        "contract": CONTRACT,
        "solana": {
            "outgoing": block(OUTGOING_ACCOUNT, sol_out),
            "incoming": block(INCOMING_ACCOUNT, sol_in),
        },
        "x1": {
            "outgoing": block(OUTGOING_ACCOUNT, x1_out),
            "incoming": block(INCOMING_ACCOUNT, x1_in),
        },
    }


class WarpOnchainTransferHistoryTests(unittest.TestCase):
    def test_decode_outgoing_requires_exact_discriminator_and_pda(self):
        seq = 1234
        pubkey, bump = find_pda(b"evt_out", seq)
        raw = outgoing_raw(
            seq=seq,
            sender="11111111111111111111111111111111",
            mint="So11111111111111111111111111111111111111112",
            amount=1_000_000_000,
            timestamp=1_788_430_000,
            operation=1,
            bump=bump,
        )
        result = decode_outgoing_account(pubkey=pubkey, raw=raw)
        self.assertEqual(result["seq"], seq)
        self.assertEqual(result["amount_raw"], 1_000_000_000)
        self.assertEqual(result["operation"], 1)
        self.assertTrue(result["account_type_identity_verified"])
        self.assertTrue(result["pda_identity_verified"])

    def test_decode_incoming_requires_exact_discriminator_and_pda(self):
        seq = 1234
        pubkey, bump = find_pda(b"evt_in", seq)
        raw = incoming_raw(
            seq=seq,
            sender="11111111111111111111111111111111",
            mint="JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8",
            amount=1_000_000_000,
            source_timestamp=1_788_430_000,
            executed_timestamp=1_788_430_030,
            operation=0,
            processed=True,
            bump=bump,
        )
        result = decode_incoming_account(pubkey=pubkey, raw=raw)
        self.assertEqual(result["source_seq"], seq)
        self.assertTrue(result["processed"])
        self.assertEqual(result["operation"], 0)
        self.assertTrue(result["claimed"])

    def test_wrong_pda_fails_closed(self):
        seq = 42
        _, bump = find_pda(b"evt_out", seq)
        raw = outgoing_raw(
            seq=seq,
            sender="11111111111111111111111111111111",
            mint="So11111111111111111111111111111111111111112",
            amount=10,
            timestamp=1_788_430_000,
            operation=1,
            bump=bump,
        )
        with self.assertRaisesRegex(WarpOnchainTransferHistoryError, "PDA mismatch"):
            decode_outgoing_account(
                pubkey="11111111111111111111111111111111",
                raw=raw,
            )

    def test_exact_pair_becomes_verified_inflow_event(self):
        seq = 9001
        sender = "11111111111111111111111111111111"
        out_pubkey, out_bump = find_pda(b"evt_out", seq)
        in_pubkey, in_bump = find_pda(b"evt_in", seq)

        out = decode_outgoing_account(
            pubkey=out_pubkey,
            raw=outgoing_raw(
                seq=seq,
                sender=sender,
                mint=route()["source"]["asset_id"],
                amount=2_000_000_000,
                timestamp=1_788_430_000,
                operation=1,
                bump=out_bump,
            ),
        )
        inc = decode_incoming_account(
            pubkey=in_pubkey,
            raw=incoming_raw(
                seq=seq,
                sender=sender,
                mint=route()["destination"]["asset_id"],
                amount=2_000_000_000,
                source_timestamp=1_788_430_000,
                executed_timestamp=1_788_430_025,
                operation=0,
                processed=True,
                bump=in_bump,
            ),
        )

        result = normalize_warp_route_events(
            route_observation=route(),
            message_state=snapshot(sol_out=[out], x1_in=[inc]),
        )
        self.assertEqual(result["accepted_settled_event_count"], 1)
        event = result["events"][0]
        self.assertEqual(event["direction"], "inflow")
        self.assertEqual(event["amount_raw"], 2_000_000_000)
        self.assertEqual(event["decimals"], 9)
        self.assertEqual(event["settled_at"], 1_788_430_025)
        self.assertTrue(event["settlement_verified"])
        self.assertTrue(event["pairing_verified"])
        self.assertTrue(result["flow_event_normalization_authorized"])
        self.assertFalse(result["coverage_complete_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_reverse_pair_becomes_route_outflow(self):
        seq = 9002
        sender = "11111111111111111111111111111111"
        out_pubkey, out_bump = find_pda(b"evt_out", seq)
        in_pubkey, in_bump = find_pda(b"evt_in", seq)

        out = decode_outgoing_account(
            pubkey=out_pubkey,
            raw=outgoing_raw(
                seq=seq,
                sender=sender,
                mint=route()["destination"]["asset_id"],
                amount=3_000_000_000,
                timestamp=1_788_431_000,
                operation=0,
                bump=out_bump,
            ),
        )
        inc = decode_incoming_account(
            pubkey=in_pubkey,
            raw=incoming_raw(
                seq=seq,
                sender=sender,
                mint=route()["source"]["asset_id"],
                amount=3_000_000_000,
                source_timestamp=1_788_431_000,
                executed_timestamp=1_788_431_020,
                operation=1,
                processed=True,
                bump=in_bump,
            ),
        )

        result = normalize_warp_route_events(
            route_observation=route(),
            message_state=snapshot(x1_out=[out], sol_in=[inc]),
        )
        self.assertEqual(result["accepted_settled_event_count"], 1)
        self.assertEqual(result["events"][0]["direction"], "outflow")

    def test_mismatch_is_unresolved_not_counted(self):
        seq = 9003
        sender = "11111111111111111111111111111111"
        out_pubkey, out_bump = find_pda(b"evt_out", seq)
        in_pubkey, in_bump = find_pda(b"evt_in", seq)
        out = decode_outgoing_account(
            pubkey=out_pubkey,
            raw=outgoing_raw(
                seq=seq,
                sender=sender,
                mint=route()["source"]["asset_id"],
                amount=100,
                timestamp=1_788_430_000,
                operation=1,
                bump=out_bump,
            ),
        )
        inc = decode_incoming_account(
            pubkey=in_pubkey,
            raw=incoming_raw(
                seq=seq,
                sender=sender,
                mint=route()["destination"]["asset_id"],
                amount=101,
                source_timestamp=1_788_430_000,
                executed_timestamp=1_788_430_010,
                operation=0,
                processed=True,
                bump=in_bump,
            ),
        )
        result = normalize_warp_route_events(
            route_observation=route(),
            message_state=snapshot(sol_out=[out], x1_in=[inc]),
        )
        self.assertEqual(result["accepted_settled_event_count"], 0)
        self.assertEqual(result["unresolved_counts"]["amount_mismatch"], 1)

    def test_delayed_claim_is_not_given_unproved_settlement_time(self):
        seq = 9004
        sender = "11111111111111111111111111111111"
        out_pubkey, out_bump = find_pda(b"evt_out", seq)
        in_pubkey, in_bump = find_pda(b"evt_in", seq)
        out = decode_outgoing_account(
            pubkey=out_pubkey,
            raw=outgoing_raw(
                seq=seq,
                sender=sender,
                mint=route()["source"]["asset_id"],
                amount=100,
                timestamp=1_788_430_000,
                operation=1,
                bump=out_bump,
            ),
        )
        inc = decode_incoming_account(
            pubkey=in_pubkey,
            raw=incoming_raw(
                seq=seq,
                sender=sender,
                mint=route()["destination"]["asset_id"],
                amount=100,
                source_timestamp=1_788_430_000,
                executed_timestamp=1_788_430_010,
                operation=0,
                processed=True,
                bump=in_bump,
                claimable_after=1_788_440_000,
                claimed=True,
            ),
        )
        result = normalize_warp_route_events(
            route_observation=route(),
            message_state=snapshot(sol_out=[out], x1_in=[inc]),
        )
        self.assertEqual(result["accepted_settled_event_count"], 0)
        self.assertEqual(
            result["unresolved_counts"][
                "delayed_claim_settlement_timestamp_unverified"
            ],
            1,
        )

    def test_route_requires_exact_accepted_semantic_contract(self):
        bad = route()
        bad["semantic_contract_id"] = "guess/v1"
        with self.assertRaisesRegex(
            WarpOnchainTransferHistoryError, "semantic contract"
        ):
            normalize_warp_route_events(
                route_observation=bad,
                message_state=snapshot(),
            )


if __name__ == "__main__":
    unittest.main()
