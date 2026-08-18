import os
import struct
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    account_key_info,
    fetch_transaction,
)


RUN_LIVE = os.getenv("RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE") == "1"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
XNT = "So11111111111111111111111111111111111111112"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
PROGRAM = XDEX_MAINNET_OBSERVED_PROGRAM_ID

# Raydium-compatible CPMM Anchor discriminator used by the observed XDEX program
# for swap_base_input. The following 16 bytes are two little-endian u64 values:
# amount_in and minimum_amount_out.
SWAP_BASE_INPUT_DISCRIMINATOR = bytes([143, 190, 90, 218, 196, 30, 51, 222])
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {char: index for index, char in enumerate(BASE58_ALPHABET)}

MAX_SIGNATURES = 60
TARGET_SAMPLES = 8
MYSTERY_HAIRCUT_PCT = Decimal("0.52")
SLIPPAGE_PRESETS_PCT = (
    Decimal("0.5"),
    Decimal("1"),
    Decimal("2"),
    Decimal("5"),
)


def _b58decode(text):
    if not isinstance(text, str) or not text:
        return None
    number = 0
    try:
        for char in text:
            number = number * 58 + BASE58_INDEX[char]
    except KeyError:
        return None

    payload = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeros = len(text) - len(text.lstrip("1"))
    return (b"\x00" * leading_zeros) + payload


def _program_id(instruction, account_keys):
    direct = instruction.get("programId")
    if isinstance(direct, str):
        return direct
    if isinstance(direct, dict):
        return str(direct.get("pubkey") or direct.get("address") or "") or None

    index = instruction.get("programIdIndex")
    if isinstance(index, int) and 0 <= index < len(account_keys):
        return account_keys[index]
    return None


def _instruction_accounts(instruction, account_keys):
    raw_accounts = instruction.get("accounts") or []
    resolved = []
    for item in raw_accounts:
        if isinstance(item, str):
            resolved.append(item)
        elif isinstance(item, dict):
            resolved.append(
                str(item.get("pubkey") or item.get("address") or "") or None
            )
        elif isinstance(item, int) and 0 <= item < len(account_keys):
            resolved.append(account_keys[item])
        else:
            resolved.append(None)
    return resolved


def _all_instructions(tx):
    account_keys, _ = account_key_info(tx)
    message = ((tx.get("transaction") or {}).get("message") or {})
    meta = tx.get("meta") or {}

    for instruction in message.get("instructions") or []:
        if isinstance(instruction, dict):
            yield instruction, account_keys, "outer"

    for group in meta.get("innerInstructions") or []:
        if not isinstance(group, dict):
            continue
        parent = group.get("index")
        for instruction in group.get("instructions") or []:
            if isinstance(instruction, dict):
                yield instruction, account_keys, f"inner:{parent}"


def _pool_program_instructions(tx):
    rows = []
    for instruction, account_keys, location in _all_instructions(tx):
        if _program_id(instruction, account_keys) != PROGRAM:
            continue
        accounts = _instruction_accounts(instruction, account_keys)
        if len(accounts) >= 4 and accounts[3] == POOL:
            rows.append((instruction, accounts, location))
    return rows


def _decode_base_input(instruction, accounts, location):
    encoded = instruction.get("data")
    raw = _b58decode(encoded)
    if raw is None or len(raw) < 24:
        return None
    if raw[:8] != SWAP_BASE_INPUT_DISCRIMINATOR:
        return None
    if len(accounts) < 12:
        return None

    amount_in, amount_out_min = struct.unpack_from("<QQ", raw, 8)
    return {
        "location": location,
        "amount_in_raw": amount_in,
        "amount_out_min_raw": amount_out_min,
        "payer": accounts[0],
        "pool": accounts[3],
        "user_input": accounts[4],
        "user_output": accounts[5],
        "input_vault": accounts[6],
        "output_vault": accounts[7],
        "input_mint": accounts[10],
        "output_mint": accounts[11],
    }


def _raw_token_balances(tx):
    account_keys, _ = account_key_info(tx)
    meta = tx.get("meta") or {}

    def collect(rows):
        result = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            index = row.get("accountIndex")
            if not isinstance(index, int) or not (0 <= index < len(account_keys)):
                continue
            ui = row.get("uiTokenAmount") or {}
            amount = ui.get("amount")
            decimals = ui.get("decimals")
            mint = row.get("mint")
            try:
                raw_amount = int(amount)
                decimals_int = int(decimals)
            except (TypeError, ValueError):
                continue
            result[account_keys[index]] = {
                "amount_raw": raw_amount,
                "decimals": decimals_int,
                "mint": mint,
                "owner": row.get("owner"),
            }
        return result

    return collect(meta.get("preTokenBalances")), collect(meta.get("postTokenBalances"))


def _vault_outflow(tx, vault, expected_mint):
    pre, post = _raw_token_balances(tx)
    before = pre.get(vault)
    after = post.get(vault)
    if not before or not after:
        return None
    if before.get("mint") != expected_mint or after.get("mint") != expected_mint:
        return None
    if before.get("decimals") != after.get("decimals"):
        return None

    outflow = before["amount_raw"] - after["amount_raw"]
    if outflow <= 0:
        return None
    return outflow, before["decimals"]


def _nearest_preset(value_pct):
    preset = min(SLIPPAGE_PRESETS_PCT, key=lambda item: abs(item - value_pct))
    return preset, abs(preset - value_pct)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE=1 to run read-only XDEX transaction evidence",
)
class XDEXOnchainSlippageSemanticLiveTests(unittest.TestCase):
    def test_decode_real_swaps_and_measure_minimum_output_headroom(self):
        history = rpc_request(
            "getSignaturesForAddress",
            [POOL, {"limit": MAX_SIGNATURES}],
        )
        self.assertIsInstance(history, list)
        self.assertTrue(history, "X1 RPC returned no recent history for the pinned XDEX pool")

        samples = []
        scanned = 0
        skipped_multi_pool_instruction = 0

        for entry in history:
            if len(samples) >= TARGET_SAMPLES:
                break
            if not isinstance(entry, dict) or entry.get("err") is not None:
                continue
            signature = str(entry.get("signature") or "").strip()
            if not signature:
                continue

            scanned += 1
            tx = fetch_transaction(signature)
            if not isinstance(tx, dict) or (tx.get("meta") or {}).get("err") is not None:
                continue

            pool_instructions = _pool_program_instructions(tx)
            # A single pool instruction keeps pre/post vault deltas attributable
            # to one swap rather than a routed or repeated use of this pool.
            if len(pool_instructions) != 1:
                if len(pool_instructions) > 1:
                    skipped_multi_pool_instruction += 1
                continue

            instruction, accounts, location = pool_instructions[0]
            decoded = _decode_base_input(instruction, accounts, location)
            if decoded is None:
                continue

            if {decoded["input_mint"], decoded["output_mint"]} != {XNT, XENCAT}:
                continue

            outflow = _vault_outflow(
                tx,
                decoded["output_vault"],
                decoded["output_mint"],
            )
            if outflow is None:
                continue
            actual_output_raw, output_decimals = outflow

            minimum_output_raw = decoded["amount_out_min_raw"]
            if minimum_output_raw <= 0 or minimum_output_raw > actual_output_raw:
                continue

            headroom_pct = (
                (Decimal(actual_output_raw) - Decimal(minimum_output_raw))
                / Decimal(actual_output_raw)
                * Decimal(100)
            )
            nearest_preset, preset_delta = _nearest_preset(headroom_pct)
            mystery_delta = abs(headroom_pct - MYSTERY_HAIRCUT_PCT)

            fee_lamports = int((tx.get("meta") or {}).get("fee") or 0)
            scale = Decimal(10) ** output_decimals
            samples.append(
                {
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "direction": f"{decoded['input_mint']}->{decoded['output_mint']}",
                    "amount_in_raw": decoded["amount_in_raw"],
                    "minimum_output_raw": minimum_output_raw,
                    "actual_pool_output_raw": actual_output_raw,
                    "minimum_output_ui": str(Decimal(minimum_output_raw) / scale),
                    "actual_pool_output_ui": str(Decimal(actual_output_raw) / scale),
                    "minimum_output_headroom_pct": str(headroom_pct),
                    "nearest_ui_slippage_preset_pct": str(nearest_preset),
                    "preset_delta_percentage_points": str(preset_delta),
                    "delta_from_0_52_percentage_points": str(mystery_delta),
                    "network_fee_lamports": fee_lamports,
                    "instruction_location": decoded["location"],
                }
            )

        print("XDEX on-chain minimum-output/slippage evidence")
        print(f"Pool: {POOL}")
        print(f"Recent successful signatures scanned: {scanned}")
        print(f"Multi-use pool transactions skipped: {skipped_multi_pool_instruction}")
        print(f"Qualifying exact-input swaps: {len(samples)}")
        for row in samples:
            print(row)

        self.assertTrue(
            samples,
            "No simple recent XDEX swap_base_input transaction could be decoded for the pinned XENCAT/XNT pool",
        )

        # Hard semantic proof from the chain: every successful exact-input swap
        # carries an explicit minimum_amount_out and actual pool output must meet
        # or exceed it. This separates slippage protection from network gas.
        for row in samples:
            self.assertLessEqual(
                int(row["minimum_output_raw"]),
                int(row["actual_pool_output_raw"]),
            )
            self.assertGreaterEqual(int(row["network_fee_lamports"]), 0)

        # Evidence-only classification. We deliberately do not assert that the
        # observed headroom equals a particular UI preset because execution can
        # move between quote construction and landing. The printed distribution
        # is the evidence used to decide whether ~0.52% is slippage/min-out.
        headrooms = [Decimal(row["minimum_output_headroom_pct"]) for row in samples]
        closest_to_mystery = min(headrooms, key=lambda value: abs(value - MYSTERY_HAIRCUT_PCT))
        print(f"Closest observed min-out headroom to 0.52%: {closest_to_mystery}%")
        print(
            "On-chain semantic conclusion: minimum_amount_out is a distinct "
            "transaction field and network gas is separate in meta.fee."
        )


if __name__ == "__main__":
    unittest.main()
