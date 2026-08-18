import base64
import hashlib
import os
import re
import struct
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import X1RPCError, rpc_request


RUN_LIVE = os.getenv("RUN_XDEX_EXECUTED_FEE_LIVE") == "1"
PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
CONFIG_2800 = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
XENCAT_DECIMALS = 6
XNT_DECIMALS = 9
TARGET_SAMPLE_COUNT = 8
MAX_SIGNATURE_ATTEMPTS = 24
FEE_DENOMINATOR = 1_000_000

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {char: index for index, char in enumerate(_B58_ALPHABET)}
_SWAP_BASE_INPUT_DISC = hashlib.sha256(b"global:swap_base_input").digest()[:8]
_SWAP_EVENT_DISC = hashlib.sha256(b"event:SwapEvent").digest()[:8]
_XDEX_OLD_SWAP_EVENT_LEN = 89
_RAYDIUM_MODERN_SWAP_EVENT_LEN = 170

# Account order from the XDEX-supplied raydium_cp_swap v0.1.0 IDL.
PAYER_INDEX = 0
AUTHORITY_INDEX = 1
AMM_CONFIG_INDEX = 2
POOL_STATE_INDEX = 3
INPUT_TOKEN_ACCOUNT_INDEX = 4
OUTPUT_TOKEN_ACCOUNT_INDEX = 5
INPUT_VAULT_INDEX = 6
OUTPUT_VAULT_INDEX = 7
INPUT_TOKEN_PROGRAM_INDEX = 8
OUTPUT_TOKEN_PROGRAM_INDEX = 9
INPUT_MINT_INDEX = 10
OUTPUT_MINT_INDEX = 11
OBSERVATION_STATE_INDEX = 12
EXPECTED_ACCOUNT_COUNT = 13

_LOG_RE = re.compile(
    r"input_amount:(?P<input>\d+),\s*"
    r"output_amount:(?P<output>\d+),\s*"
    r"trade_fee:(?P<trade_fee>\d+),\s*"
    r"input_transfer_fee:(?P<input_transfer_fee>\d+),\s*"
    r"constant_before:(?P<constant_before>\d+),\s*"
    r"constant_after:(?P<constant_after>\d+),\s*"
    r"is_creator_fee_on_input:(?P<creator_on_input>true|false),\s*"
    r"creator_fee:(?P<creator_fee>\d+)"
)


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
    return (int(amount) * int(rate_ppm) + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR


def _cp_output_raw(amount_in, reserve_in, reserve_out, rate_ppm):
    fee = _ceil_fee(amount_in, rate_ppm)
    net_in = int(amount_in) - fee
    if net_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return None
    return (net_in * int(reserve_out)) // (int(reserve_in) + net_in)


def _account_keys(tx):
    message = ((tx or {}).get("transaction") or {}).get("message") or {}
    result = []
    for entry in message.get("accountKeys") or []:
        if isinstance(entry, dict):
            result.append(str(entry.get("pubkey") or ""))
        else:
            result.append(str(entry or ""))
    return result


def _program_id(ix, account_keys):
    if not isinstance(ix, dict):
        return None
    direct = ix.get("programId")
    if direct:
        return str(direct)
    index = ix.get("programIdIndex")
    if isinstance(index, int) and 0 <= index < len(account_keys):
        return account_keys[index]
    return None


def _resolve_instruction_accounts(ix, account_keys):
    resolved = []
    for entry in (ix or {}).get("accounts") or []:
        if isinstance(entry, int):
            resolved.append(account_keys[entry] if 0 <= entry < len(account_keys) else None)
        elif isinstance(entry, dict):
            resolved.append(str(entry.get("pubkey") or "") or None)
        else:
            resolved.append(str(entry or "") or None)
    return resolved


def _iter_instructions(tx):
    message = ((tx or {}).get("transaction") or {}).get("message") or {}
    account_keys = _account_keys(tx)
    for ix in message.get("instructions") or []:
        if isinstance(ix, dict):
            yield ix, account_keys, "outer"

    meta = (tx or {}).get("meta") or {}
    for group in meta.get("innerInstructions") or []:
        if not isinstance(group, dict):
            continue
        for ix in group.get("instructions") or []:
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
        if len(data) != 24 or data[:8] != _SWAP_BASE_INPUT_DISC:
            continue
        amount_in, minimum_amount_out = struct.unpack_from("<QQ", data, 8)
        accounts = _resolve_instruction_accounts(ix, account_keys)
        matches.append(
            {
                "location": location,
                "amount_in_raw": amount_in,
                "minimum_amount_out_raw": minimum_amount_out,
                "accounts": accounts,
            }
        )
    return matches


def _token_balance_map(tx, field):
    meta = (tx or {}).get("meta") or {}
    keys = _account_keys(tx)
    result = {}
    for row in meta.get(field) or []:
        if not isinstance(row, dict):
            continue
        index = row.get("accountIndex")
        if not isinstance(index, int) or not (0 <= index < len(keys)):
            continue
        ui = row.get("uiTokenAmount") or {}
        raw = ui.get("amount")
        try:
            raw_int = int(raw)
        except (TypeError, ValueError):
            continue
        result[keys[index]] = {
            "raw": raw_int,
            "mint": row.get("mint"),
            "owner": row.get("owner"),
            "decimals": ui.get("decimals"),
            "account_index": index,
        }
    return result


def _decode_old_swap_event(data):
    if len(data) != _XDEX_OLD_SWAP_EVENT_LEN or not data.startswith(_SWAP_EVENT_DISC):
        return None
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
        "layout": "xdex_raydium_cp_swap_v0.1.0",
        "pool_id": pool_id,
        "input_vault_before_raw": input_vault_before,
        "output_vault_before_raw": output_vault_before,
        "input_amount_raw": input_amount,
        "output_amount_raw": output_amount,
        "input_transfer_fee_raw": input_transfer_fee,
        "output_transfer_fee_raw": output_transfer_fee,
        "base_input": base_input,
        "trade_fee_raw": None,
    }


def _decode_modern_swap_event(data):
    if len(data) != _RAYDIUM_MODERN_SWAP_EVENT_LEN or not data.startswith(_SWAP_EVENT_DISC):
        return None
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
    offset += 1 + 32 + 32
    trade_fee, creator_fee = struct.unpack_from("<QQ", data, offset)
    return {
        "layout": "modern_raydium_cp_swap",
        "pool_id": pool_id,
        "input_vault_before_raw": input_vault_before,
        "output_vault_before_raw": output_vault_before,
        "input_amount_raw": input_amount,
        "output_amount_raw": output_amount,
        "input_transfer_fee_raw": input_transfer_fee,
        "output_transfer_fee_raw": output_transfer_fee,
        "base_input": base_input,
        "trade_fee_raw": trade_fee,
        "creator_fee_raw": creator_fee,
    }


def _swap_events(tx):
    meta = (tx or {}).get("meta") or {}
    events = []
    for line in meta.get("logMessages") or []:
        if not isinstance(line, str) or not line.startswith("Program data: "):
            continue
        encoded = line[len("Program data: ") :].strip()
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        event = _decode_old_swap_event(data) or _decode_modern_swap_event(data)
        if event is not None:
            events.append(event)
    return events


def _diagnostic_fee_logs(tx):
    meta = (tx or {}).get("meta") or {}
    rows = []
    for line in meta.get("logMessages") or []:
        if not isinstance(line, str):
            continue
        match = _LOG_RE.search(line)
        if not match:
            continue
        row = {
            key: int(value) if key != "creator_on_input" else value == "true"
            for key, value in match.groupdict().items()
        }
        rows.append(row)
    return rows


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
        retries=2,
        timeout=15,
    )


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_EXECUTED_FEE_LIVE=1 to inspect completed XDEX swaps read-only",
)
class XDEXExecutedFeeSemanticLiveTests(unittest.TestCase):
    def test_completed_swaps_localize_2800_vs_3000_execution_semantics(self):
        history = fetch_pool_trades_raw(POOL)
        trades = history["raw_response"]["trades"]
        self.assertTrue(trades, "X1.Ninja returned no recent trades for the pinned pool")

        rows = []
        direct_fee_rows = []
        event_rows = []
        rpc_failures = []
        seen = set()
        attempts = 0

        for trade in trades:
            signature = str(trade.get("txHash") or "").strip()
            if not signature or signature in seen:
                continue
            seen.add(signature)
            attempts += 1
            if attempts > MAX_SIGNATURE_ATTEMPTS:
                break

            try:
                tx = _get_transaction(signature)
            except X1RPCError as exc:
                rpc_failures.append({"signature": signature, "error": str(exc)})
                continue
            if not isinstance(tx, dict):
                continue
            meta = tx.get("meta") or {}
            if meta.get("err") is not None:
                continue

            instructions = _decode_swap_base_input(tx)
            if not instructions:
                continue

            token_raw = _raw_from_provider(trade.get("amountToken"), XENCAT_DECIMALS)
            native_raw = _raw_from_provider(trade.get("amountNative"), XNT_DECIMALS)
            pre = _token_balance_map(tx, "preTokenBalances")
            post = _token_balance_map(tx, "postTokenBalances")

            matched = None
            for ix in instructions:
                amount_in = ix["amount_in_raw"]
                if _close_raw(amount_in, token_raw):
                    direction = "XENCAT->XNT"
                    indexed_output = native_raw
                elif _close_raw(amount_in, native_raw):
                    direction = "XNT->XENCAT"
                    indexed_output = token_raw
                else:
                    continue
                matched = (ix, direction, indexed_output)
                break
            if matched is None:
                continue

            ix, direction, indexed_output = matched
            accounts = ix["accounts"]
            if len(accounts) < EXPECTED_ACCOUNT_COUNT:
                continue
            amm_config = accounts[AMM_CONFIG_INDEX]
            pool_state = accounts[POOL_STATE_INDEX]
            input_vault = accounts[INPUT_VAULT_INDEX]
            output_vault = accounts[OUTPUT_VAULT_INDEX]
            input_mint = accounts[INPUT_MINT_INDEX]
            output_mint = accounts[OUTPUT_MINT_INDEX]
            if amm_config != CONFIG_2800 or pool_state != POOL:
                continue

            input_pre = (pre.get(input_vault) or {}).get("raw")
            output_pre = (pre.get(output_vault) or {}).get("raw")
            input_post = (post.get(input_vault) or {}).get("raw")
            output_post = (post.get(output_vault) or {}).get("raw")
            gross_output_delta = (
                output_pre - output_post
                if isinstance(output_pre, int) and isinstance(output_post, int)
                else None
            )
            gross_input_delta = (
                input_post - input_pre
                if isinstance(input_pre, int) and isinstance(input_post, int)
                else None
            )
            cp_2800_gross = (
                _cp_output_raw(ix["amount_in_raw"], input_pre, output_pre, 2800)
                if isinstance(input_pre, int) and isinstance(output_pre, int)
                else None
            )
            cp_3000_gross = (
                _cp_output_raw(ix["amount_in_raw"], input_pre, output_pre, 3000)
                if isinstance(input_pre, int) and isinstance(output_pre, int)
                else None
            )

            row = {
                "signature": signature,
                "slot": tx.get("slot"),
                "direction": direction,
                "amount_in_raw": ix["amount_in_raw"],
                "minimum_amount_out_raw": ix["minimum_amount_out_raw"],
                "indexed_actual_output_raw": indexed_output,
                "amm_config": amm_config,
                "pool_state": pool_state,
                "input_mint": input_mint,
                "output_mint": output_mint,
                "input_vault": input_vault,
                "output_vault": output_vault,
                "gross_input_vault_pre_raw": input_pre,
                "gross_output_vault_pre_raw": output_pre,
                "gross_input_vault_post_raw": input_post,
                "gross_output_vault_post_raw": output_post,
                "gross_input_delta_raw": gross_input_delta,
                "gross_output_delta_raw": gross_output_delta,
                "gross_cp_2800_raw": cp_2800_gross,
                "gross_cp_3000_raw": cp_3000_gross,
                "gross_delta_actual_vs_2800_raw": (
                    gross_output_delta - cp_2800_gross
                    if isinstance(gross_output_delta, int) and isinstance(cp_2800_gross, int)
                    else None
                ),
                "gross_delta_actual_vs_3000_raw": (
                    gross_output_delta - cp_3000_gross
                    if isinstance(gross_output_delta, int) and isinstance(cp_3000_gross, int)
                    else None
                ),
                "active_reserves_proven_from_transaction_metadata": False,
                "pool_fee_counters_pre_swap_available": False,
                "return_data_present": bool(meta.get("returnData")),
            }
            rows.append(row)

            for log_row in _diagnostic_fee_logs(tx):
                if _close_raw(log_row.get("input"), ix["amount_in_raw"]):
                    trade_fee = log_row["trade_fee"]
                    direct_fee_rows.append(
                        {
                            "signature": signature,
                            **log_row,
                            "expected_trade_fee_2800_raw": _ceil_fee(log_row["input"], 2800),
                            "expected_trade_fee_3000_raw": _ceil_fee(log_row["input"], 3000),
                            "trade_fee_matches_2800": trade_fee == _ceil_fee(log_row["input"], 2800),
                            "trade_fee_matches_3000": trade_fee == _ceil_fee(log_row["input"], 3000),
                        }
                    )

            for event in _swap_events(tx):
                if event["pool_id"] != POOL or not event["base_input"]:
                    continue
                if not _close_raw(event["input_amount_raw"], ix["amount_in_raw"]):
                    continue
                cp_2800 = _cp_output_raw(
                    event["input_amount_raw"],
                    event["input_vault_before_raw"],
                    event["output_vault_before_raw"],
                    2800,
                )
                cp_3000 = _cp_output_raw(
                    event["input_amount_raw"],
                    event["input_vault_before_raw"],
                    event["output_vault_before_raw"],
                    3000,
                )
                event_rows.append(
                    {
                        "signature": signature,
                        **event,
                        "cp_2800_from_event_reserves_raw": cp_2800,
                        "cp_3000_from_event_reserves_raw": cp_3000,
                        "output_matches_2800": event["output_amount_raw"] == cp_2800,
                        "output_matches_3000": event["output_amount_raw"] == cp_3000,
                        "trade_fee_matches_2800": (
                            event["trade_fee_raw"] == _ceil_fee(event["input_amount_raw"], 2800)
                            if event["trade_fee_raw"] is not None
                            else None
                        ),
                        "trade_fee_matches_3000": (
                            event["trade_fee_raw"] == _ceil_fee(event["input_amount_raw"], 3000)
                            if event["trade_fee_raw"] is not None
                            else None
                        ),
                    }
                )

            if len(rows) >= TARGET_SAMPLE_COUNT:
                break

        print("XDEX executed-fee gross-vault diagnostics")
        for row in rows:
            print(row)
        print("XDEX executed-fee direct diagnostic-log evidence")
        for row in direct_fee_rows:
            print(row)
        print("XDEX executed-fee SwapEvent evidence")
        for row in event_rows:
            print(row)
        print("X1 RPC failures")
        for row in rpc_failures:
            print(row)
        print(
            "Interpretation boundary: reference Raydium CP-Swap subtracts accumulated protocol/fund/creator fee counters from gross vault balances before curve math. "
            "Transaction preTokenBalances expose gross vault amounts but not historical pool-state fee counters. Gross-vault CP comparisons are diagnostics only unless a SwapEvent/log or another historical state source independently exposes active reserves/trade fee."
        )

        if len(rows) < 3 and rpc_failures:
            self.skipTest(
                "official X1 RPC returned too few completed transactions in this bounded run; "
                f"successful={len(rows)} rpc_failures={len(rpc_failures)}"
            )

        self.assertGreaterEqual(
            len(rows),
            3,
            "need at least three completed 2800-config swaps with decoded vault accounts",
        )
        for row in rows:
            self.assertEqual(row["amm_config"], CONFIG_2800, row)
            self.assertEqual(row["pool_state"], POOL, row)
            self.assertIsInstance(row["gross_input_vault_pre_raw"], int, row)
            self.assertIsInstance(row["gross_output_vault_pre_raw"], int, row)
            self.assertIsInstance(row["gross_output_delta_raw"], int, row)
            self.assertFalse(row["active_reserves_proven_from_transaction_metadata"], row)
            if row["indexed_actual_output_raw"] is not None:
                self.assertTrue(_close_raw(row["gross_output_delta_raw"], row["indexed_actual_output_raw"]), row)

        for row in direct_fee_rows:
            self.assertFalse(
                row["trade_fee_matches_2800"] and row["trade_fee_matches_3000"],
                row,
            )


if __name__ == "__main__":
    unittest.main()
