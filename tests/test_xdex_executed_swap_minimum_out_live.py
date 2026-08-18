import base64
import hashlib
import os
import struct
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import rpc_request


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
XENCAT_DECIMALS = 6
XNT_DECIMALS = 9
TARGET_SAMPLE_COUNT = 5
FEE_RATE_DENOMINATOR = 1_000_000

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {char: index for index, char in enumerate(_B58_ALPHABET)}
_SWAP_BASE_INPUT_DISC = hashlib.sha256(b"global:swap_base_input").digest()[:8]
_SWAP_EVENT_DISC = hashlib.sha256(b"event:SwapEvent").digest()[:8]
_XDEX_EMBEDDED_SWAP_EVENT_LEN = 89
_MODERN_RAYDIUM_SWAP_EVENT_LEN = 170


def _b58decode(text):
    value = 0
    for char in str(text or ""):
        value = value * 58 + _B58_INDEX[char]
    body = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    pad = len(str(text or "")) - len(str(text or "").lstrip("1"))
    return (b"\x00" * pad) + body


def _b58encode(data):
    raw = bytes(data)
    value = int.from_bytes(raw, "big")
    chars = []
    while value:
        value, remainder = divmod(value, 58)
        chars.append(_B58_ALPHABET[remainder])
    pad = len(raw) - len(raw.lstrip(b"\x00"))
    return ("1" * pad) + ("".join(reversed(chars)) if chars else "")


def _raw_from_provider(value, decimals):
    if value is None or isinstance(value, bool):
        return None
    scaled = Decimal(str(value)) * (Decimal(10) ** decimals)
    return int(scaled.to_integral_value())


def _close_raw(left, right):
    if left is None or right is None:
        return False
    tolerance = max(10, abs(int(left)) // 1_000_000_000)
    return abs(int(left) - int(right)) <= tolerance


def _ceil_fee(amount, rate_ppm):
    return (int(amount) * int(rate_ppm) + FEE_RATE_DENOMINATOR - 1) // FEE_RATE_DENOMINATOR


def _cp_output_raw(amount_in, reserve_in, reserve_out, rate_ppm):
    fee = _ceil_fee(amount_in, rate_ppm)
    net_in = int(amount_in) - fee
    if net_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    return (net_in * int(reserve_out)) // (int(reserve_in) + net_in)


def _program_id(ix, account_keys):
    direct = ix.get("programId") if isinstance(ix, dict) else None
    if direct:
        return str(direct)
    index = ix.get("programIdIndex") if isinstance(ix, dict) else None
    if not isinstance(index, int) or index < 0 or index >= len(account_keys):
        return None
    entry = account_keys[index]
    if isinstance(entry, dict):
        return str(entry.get("pubkey") or "") or None
    return str(entry or "") or None


def _iter_instructions(tx):
    transaction = (tx or {}).get("transaction")
    message = transaction.get("message") if isinstance(transaction, dict) else None
    account_keys = message.get("accountKeys") if isinstance(message, dict) else None
    account_keys = account_keys if isinstance(account_keys, list) else []

    outer = message.get("instructions") if isinstance(message, dict) else None
    if isinstance(outer, list):
        for ix in outer:
            if isinstance(ix, dict):
                yield ix, account_keys, "outer"

    meta = (tx or {}).get("meta")
    groups = meta.get("innerInstructions") if isinstance(meta, dict) else None
    if isinstance(groups, list):
        for group in groups:
            instructions = group.get("instructions") if isinstance(group, dict) else None
            if not isinstance(instructions, list):
                continue
            for ix in instructions:
                if isinstance(ix, dict):
                    yield ix, account_keys, "inner"


def _decode_swap_base_input(tx):
    matches = []
    for ix, account_keys, location in _iter_instructions(tx):
        if _program_id(ix, account_keys) != PROGRAM:
            continue
        data_text = ix.get("data")
        if not isinstance(data_text, str) or not data_text:
            continue
        try:
            data = _b58decode(data_text)
        except (KeyError, ValueError):
            continue
        if len(data) < 24 or data[:8] != _SWAP_BASE_INPUT_DISC:
            continue
        amount_in, minimum_amount_out = struct.unpack_from("<QQ", data, 8)
        matches.append({
            "location": location,
            "data_length": len(data),
            "discriminator_hex": data[:8].hex(),
            "amount_in_raw": amount_in,
            "minimum_amount_out_raw": minimum_amount_out,
        })
    return matches


def _decode_swap_event_payload(data):
    if not data.startswith(_SWAP_EVENT_DISC):
        return None

    # The currently deployed XDEX frontend embeds a raydium_cp_swap v0.1.0 IDL
    # whose SwapEvent contains exactly these fields and is 89 bytes including
    # the Anchor event discriminator. Keep this layout separate from newer
    # Raydium events so we do not silently import fields XDEX does not expose.
    if len(data) == _XDEX_EMBEDDED_SWAP_EVENT_LEN:
        offset = 8
        pool_id = _b58encode(data[offset : offset + 32])
        offset += 32
        (
            input_vault_before,
            output_vault_before,
            input_amount,
            output_amount,
            input_transfer_fee,
            output_transfer_fee,
        ) = struct.unpack_from("<QQQQQQ", data, offset)
        offset += 48
        base_input = bool(data[offset])
        return {
            "layout": "xdex_embedded_raydium_cp_swap_v0.1.0",
            "pool_id": pool_id,
            "input_vault_before": input_vault_before,
            "output_vault_before": output_vault_before,
            "input_amount": input_amount,
            "output_amount": output_amount,
            "input_transfer_fee": input_transfer_fee,
            "output_transfer_fee": output_transfer_fee,
            "base_input": base_input,
            "input_mint": None,
            "output_mint": None,
            "trade_fee": None,
            "creator_fee": None,
            "creator_fee_on_input": None,
        }

    if len(data) == _MODERN_RAYDIUM_SWAP_EVENT_LEN:
        offset = 8
        pool_id = _b58encode(data[offset : offset + 32])
        offset += 32
        (
            input_vault_before,
            output_vault_before,
            input_amount,
            output_amount,
            input_transfer_fee,
            output_transfer_fee,
        ) = struct.unpack_from("<QQQQQQ", data, offset)
        offset += 48
        base_input = bool(data[offset])
        offset += 1
        input_mint = _b58encode(data[offset : offset + 32])
        offset += 32
        output_mint = _b58encode(data[offset : offset + 32])
        offset += 32
        trade_fee, creator_fee = struct.unpack_from("<QQ", data, offset)
        offset += 16
        creator_fee_on_input = bool(data[offset])
        return {
            "layout": "modern_raydium_cp_swap",
            "pool_id": pool_id,
            "input_vault_before": input_vault_before,
            "output_vault_before": output_vault_before,
            "input_amount": input_amount,
            "output_amount": output_amount,
            "input_transfer_fee": input_transfer_fee,
            "output_transfer_fee": output_transfer_fee,
            "base_input": base_input,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "trade_fee": trade_fee,
            "creator_fee": creator_fee,
            "creator_fee_on_input": creator_fee_on_input,
        }

    return None


def _decode_swap_events(tx):
    meta = (tx or {}).get("meta")
    logs = meta.get("logMessages") if isinstance(meta, dict) else None
    if not isinstance(logs, list):
        return []
    matches = []
    for line in logs:
        if not isinstance(line, str) or not line.startswith("Program data: "):
            continue
        encoded = line[len("Program data: ") :].strip()
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        event = _decode_swap_event_payload(data)
        if event is not None:
            matches.append(event)
    return matches


def _get_transaction(signature):
    return rpc_request(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to inspect completed XDEX swaps read-only",
)
class XDEXExecutedSwapMinimumOutLiveTests(unittest.TestCase):
    def test_completed_swap_instruction_exposes_transaction_specific_minimum_output(self):
        history = fetch_pool_trades_raw(POOL)
        trades = history["raw_response"]["trades"]
        self.assertTrue(trades, "X1.Ninja returned no recent rows for the pinned XDEX pool")

        rows = []
        event_rows = []
        seen_signatures = set()
        for trade in trades:
            signature = str(trade.get("txHash") or "").strip()
            if not signature or signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            tx = _get_transaction(signature)
            if not isinstance(tx, dict):
                continue
            meta = tx.get("meta")
            if not isinstance(meta, dict) or meta.get("err") is not None:
                continue

            decoded = _decode_swap_base_input(tx)
            if not decoded:
                continue

            token_raw = _raw_from_provider(trade.get("amountToken"), XENCAT_DECIMALS)
            native_raw = _raw_from_provider(trade.get("amountNative"), XNT_DECIMALS)

            matched_instruction = None
            for instruction in decoded:
                amount_in = instruction["amount_in_raw"]
                minimum_out = instruction["minimum_amount_out_raw"]

                if _close_raw(amount_in, token_raw):
                    direction = "XENCAT->XNT"
                    actual_out = native_raw
                    output_mint = XNT
                    output_decimals = XNT_DECIMALS
                elif _close_raw(amount_in, native_raw):
                    direction = "XNT->XENCAT"
                    actual_out = token_raw
                    output_mint = XENCAT
                    output_decimals = XENCAT_DECIMALS
                else:
                    continue

                if actual_out is None or actual_out <= 0 or minimum_out <= 0:
                    continue

                ratio = Decimal(minimum_out) / Decimal(actual_out)
                protection_bps = (Decimal(1) - ratio) * Decimal(10_000)
                rows.append({
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "block_time": tx.get("blockTime"),
                    "direction": direction,
                    "output_mint": output_mint,
                    "output_decimals": output_decimals,
                    "instruction_location": instruction["location"],
                    "instruction_data_length": instruction["data_length"],
                    "instruction_discriminator_hex": instruction["discriminator_hex"],
                    "amount_in_raw": amount_in,
                    "minimum_amount_out_raw": minimum_out,
                    "indexed_actual_output_raw": actual_out,
                    "minimum_to_actual_ratio": str(ratio),
                    "observed_protection_gap_bps": str(protection_bps),
                })
                matched_instruction = instruction
                break

            if matched_instruction is not None:
                for event in _decode_swap_events(tx):
                    if event["pool_id"] != POOL or not event["base_input"]:
                        continue
                    if not _close_raw(event["input_amount"], matched_instruction["amount_in_raw"]):
                        continue

                    cp_2800 = _cp_output_raw(
                        event["input_amount"],
                        event["input_vault_before"],
                        event["output_vault_before"],
                        2800,
                    )
                    cp_3000 = _cp_output_raw(
                        event["input_amount"],
                        event["input_vault_before"],
                        event["output_vault_before"],
                        3000,
                    )
                    event_row = {
                        "signature": signature,
                        "slot": tx.get("slot"),
                        "layout": event["layout"],
                        "pool_id": event["pool_id"],
                        "input_amount_raw": event["input_amount"],
                        "output_amount_raw": event["output_amount"],
                        "input_vault_before_raw": event["input_vault_before"],
                        "output_vault_before_raw": event["output_vault_before"],
                        "input_transfer_fee_raw": event["input_transfer_fee"],
                        "output_transfer_fee_raw": event["output_transfer_fee"],
                        "cp_output_2800_raw": cp_2800,
                        "cp_output_3000_raw": cp_3000,
                        "delta_vs_2800_raw": event["output_amount"] - cp_2800,
                        "delta_vs_3000_raw": event["output_amount"] - cp_3000,
                        "matches_2800": event["output_amount"] == cp_2800,
                        "matches_3000": event["output_amount"] == cp_3000,
                    }
                    if event["trade_fee"] is not None:
                        expected_2800 = _ceil_fee(event["input_amount"], 2800)
                        expected_3000 = _ceil_fee(event["input_amount"], 3000)
                        event_row.update({
                            "trade_fee_raw": event["trade_fee"],
                            "expected_trade_fee_2800_raw": expected_2800,
                            "expected_trade_fee_3000_raw": expected_3000,
                            "trade_fee_matches_2800": event["trade_fee"] == expected_2800,
                            "trade_fee_matches_3000": event["trade_fee"] == expected_3000,
                        })
                    event_rows.append(event_row)
                    break

            if len(rows) >= TARGET_SAMPLE_COUNT:
                break

        print("XDEX completed-swap minimum-output evidence")
        for row in rows:
            print(row)

        print("XDEX completed-swap embedded-IDL SwapEvent curve diagnostics")
        for row in event_rows:
            print(row)

        self.assertGreaterEqual(
            len(rows),
            3,
            "need at least three completed swaps whose XDEX swap_base_input instruction can be decoded and matched to indexed amounts",
        )

        gaps = [Decimal(row["observed_protection_gap_bps"]) for row in rows]
        for row, gap in zip(rows, gaps):
            self.assertEqual(row["instruction_data_length"], 24)
            self.assertEqual(row["instruction_discriminator_hex"], _SWAP_BASE_INPUT_DISC.hex())
            self.assertLessEqual(
                row["minimum_amount_out_raw"],
                row["indexed_actual_output_raw"],
                "a successful completed swap must not receive less than its encoded threshold",
            )
            self.assertGreaterEqual(gap, Decimal("0"))

        if event_rows:
            matches_2800 = sum(1 for row in event_rows if row["matches_2800"])
            matches_3000 = sum(1 for row in event_rows if row["matches_3000"])
            print(
                "Executed SwapEvent CP match counts:",
                {"2800_ppm": matches_2800, "3000_ppm": matches_3000, "decoded_events": len(event_rows)},
            )
            for row in event_rows:
                self.assertEqual(
                    row["input_transfer_fee_raw"],
                    0,
                    "pinned classic SPL-token pair should not introduce an input transfer fee",
                )
                self.assertEqual(
                    row["output_transfer_fee_raw"],
                    0,
                    "pinned classic SPL-token pair should not introduce an output transfer fee",
                )
            print(
                "Interpretation boundary: the 89-byte event layout comes from the currently deployed XDEX frontend's embedded "
                "raydium_cp_swap v0.1.0 IDL. Exact CP matching can localize executed curve behavior, but does not assign a business "
                "label to any quote-service-only adjustment."
            )
        else:
            print(
                "No XDEX embedded-IDL SwapEvent payloads were decoded from the sampled XDEX transactions; "
                "do not infer executed fee rate from the quote API alone."
            )

        print("Anchor discriminator candidate global:swap_base_input:", _SWAP_BASE_INPUT_DISC.hex())
        print("Anchor event discriminator candidate event:SwapEvent:", _SWAP_EVENT_DISC.hex())
        print("Observed completed-swap minimum/output gaps (bps):", [str(g) for g in gaps])
        print(
            "Interpretation boundary: the second u64 is strongly corroborated as a transaction-specific minimum-output threshold; "
            "historical thresholds vary and therefore must not be equated with the current quote API's 0.5% default."
        )


if __name__ == "__main__":
    unittest.main()
