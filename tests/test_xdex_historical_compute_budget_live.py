import os
import struct
import unittest

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import X1RPCError, rpc_request


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111"
TARGET_SAMPLE_COUNT = 5
MAX_SIGNATURE_ATTEMPTS = 12

# Current X1 Tachyon v3.1 source defines:
#   Base fee = derived compute units * 10
#   Total fee = base fee + prioritization fee
# and its tests compute prioritization fee as ceil(limit * price / 1_000_000).
# The live probe below independently checks whether completed XDEX transactions
# are arithmetically consistent with that current X1 fee implementation.
X1_BASE_FEE_MULTIPLIER = 10
MICRO_LAMPORTS_PER_LAMPORT = 1_000_000

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {char: index for index, char in enumerate(_B58_ALPHABET)}


def _b58decode(text):
    value = 0
    for char in str(text or ""):
        value = value * 58 + _B58_INDEX[char]
    body = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    pad = len(str(text or "")) - len(str(text or "").lstrip("1"))
    return (b"\x00" * pad) + body


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
    direct = ix.get("programId") if isinstance(ix, dict) else None
    if direct:
        return str(direct)
    index = ix.get("programIdIndex") if isinstance(ix, dict) else None
    if isinstance(index, int) and 0 <= index < len(account_keys):
        return account_keys[index]
    return None


def _decode_compute_budget_instruction(ix, account_keys):
    if _program_id(ix, account_keys) != COMPUTE_BUDGET_PROGRAM:
        return None
    data_text = ix.get("data") if isinstance(ix, dict) else None
    if not isinstance(data_text, str) or not data_text:
        return {"kind": "compute_budget_unparsed", "raw_data": data_text}
    try:
        data = _b58decode(data_text)
    except (KeyError, ValueError):
        return {"kind": "compute_budget_unparsed", "raw_data": data_text}
    if not data:
        return {"kind": "compute_budget_empty", "raw_data": data_text}

    tag = data[0]
    row = {"tag": tag, "data_length": len(data), "raw_data": data_text}
    if tag == 0 and len(data) >= 9:
        units, additional_fee = struct.unpack_from("<II", data, 1)
        row.update(
            {
                "kind": "request_units_deprecated",
                "units": units,
                "additional_fee_raw": additional_fee,
            }
        )
    elif tag == 1 and len(data) >= 5:
        row.update(
            {
                "kind": "request_heap_frame",
                "heap_frame_bytes": struct.unpack_from("<I", data, 1)[0],
            }
        )
    elif tag == 2 and len(data) >= 5:
        row.update(
            {
                "kind": "set_compute_unit_limit",
                "compute_unit_limit": struct.unpack_from("<I", data, 1)[0],
            }
        )
    elif tag == 3 and len(data) >= 9:
        row.update(
            {
                "kind": "set_compute_unit_price",
                "compute_unit_price_raw": struct.unpack_from("<Q", data, 1)[0],
            }
        )
    elif tag == 4 and len(data) >= 5:
        row.update(
            {
                "kind": "set_loaded_accounts_data_size_limit",
                "loaded_accounts_data_size_limit": struct.unpack_from("<I", data, 1)[0],
            }
        )
    else:
        row["kind"] = "compute_budget_unknown"
    return row


def _compute_budget_rows(tx):
    message = ((tx or {}).get("transaction") or {}).get("message") or {}
    account_keys = _account_keys(tx)
    rows = []
    for index, ix in enumerate(message.get("instructions") or []):
        if not isinstance(ix, dict):
            continue
        decoded = _decode_compute_budget_instruction(ix, account_keys)
        if decoded is not None:
            decoded["instruction_index"] = index
            rows.append(decoded)
    return rows


def _outer_program_ids(tx):
    message = ((tx or {}).get("transaction") or {}).get("message") or {}
    account_keys = _account_keys(tx)
    result = []
    for ix in message.get("instructions") or []:
        if not isinstance(ix, dict):
            continue
        result.append(_program_id(ix, account_keys))
    return result


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


def _extract_budget_summary(rows):
    limit = None
    price = None
    for row in rows:
        if row.get("kind") == "set_compute_unit_limit":
            limit = row.get("compute_unit_limit")
        elif row.get("kind") == "set_compute_unit_price":
            price = row.get("compute_unit_price_raw")
    return limit, price


def _x1_priority_fee(compute_unit_limit, compute_unit_price):
    if not isinstance(compute_unit_limit, int) or not isinstance(compute_unit_price, int):
        return None
    return (
        compute_unit_limit * compute_unit_price + MICRO_LAMPORTS_PER_LAMPORT - 1
    ) // MICRO_LAMPORTS_PER_LAMPORT


def _x1_fee_reconstruction(network_fee, compute_unit_limit, compute_unit_price):
    priority_fee = _x1_priority_fee(compute_unit_limit, compute_unit_price)
    if priority_fee is None or not isinstance(network_fee, int) or network_fee < priority_fee:
        return {
            "x1_priority_fee_raw": priority_fee,
            "x1_inferred_base_fee_raw": None,
            "x1_inferred_derived_compute_units": None,
            "x1_inferred_builtin_overhead_cu": None,
            "x1_dynamic_fee_formula_exactly_consistent": False,
        }

    base_fee = network_fee - priority_fee
    if base_fee % X1_BASE_FEE_MULTIPLIER != 0:
        return {
            "x1_priority_fee_raw": priority_fee,
            "x1_inferred_base_fee_raw": base_fee,
            "x1_inferred_derived_compute_units": None,
            "x1_inferred_builtin_overhead_cu": None,
            "x1_dynamic_fee_formula_exactly_consistent": False,
        }

    derived_cu = base_fee // X1_BASE_FEE_MULTIPLIER
    builtin_overhead = (
        derived_cu - compute_unit_limit
        if isinstance(compute_unit_limit, int)
        else None
    )
    return {
        "x1_priority_fee_raw": priority_fee,
        "x1_inferred_base_fee_raw": base_fee,
        "x1_inferred_derived_compute_units": derived_cu,
        "x1_inferred_builtin_overhead_cu": builtin_overhead,
        "x1_dynamic_fee_formula_exactly_consistent": (
            isinstance(builtin_overhead, int) and builtin_overhead >= 0
        ),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to inspect completed XDEX swaps read-only",
)
class XDEXHistoricalComputeBudgetLiveTests(unittest.TestCase):
    def test_completed_swaps_separate_transaction_fee_and_compute_budget_from_quote_math(self):
        history = fetch_pool_trades_raw(POOL)
        trades = history["raw_response"]["trades"]
        self.assertTrue(trades, "X1.Ninja returned no recent rows for the pinned XDEX pool")

        diagnostics = []
        rpc_failures = []
        seen = set()
        attempted = 0
        for trade in trades:
            signature = str(trade.get("txHash") or "").strip()
            if not signature or signature in seen:
                continue
            seen.add(signature)
            attempted += 1
            if attempted > MAX_SIGNATURE_ATTEMPTS:
                break

            try:
                tx = _get_transaction(signature)
            except X1RPCError as exc:
                rpc_failures.append({"signature": signature, "error": str(exc)})
                continue

            if not isinstance(tx, dict):
                continue
            meta = tx.get("meta")
            if not isinstance(meta, dict) or meta.get("err") is not None:
                continue

            fee_raw = meta.get("fee")
            if not isinstance(fee_raw, int):
                continue

            rows = _compute_budget_rows(tx)
            limit, price = _extract_budget_summary(rows)
            consumed = meta.get("computeUnitsConsumed")
            transaction = tx.get("transaction") or {}
            signatures = transaction.get("signatures") or []
            account_keys = _account_keys(tx)
            reconstruction = _x1_fee_reconstruction(fee_raw, limit, price)

            diagnostics.append(
                {
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "block_time": tx.get("blockTime"),
                    "fee_payer": account_keys[0] if account_keys else None,
                    "signature_count": len(signatures),
                    "network_fee_raw": fee_raw,
                    "compute_units_consumed": consumed,
                    "compute_unit_limit": limit,
                    "compute_unit_price_raw": price,
                    "outer_program_ids": _outer_program_ids(tx),
                    **reconstruction,
                    "compute_budget_instructions": rows,
                }
            )
            if len(diagnostics) >= TARGET_SAMPLE_COUNT:
                break

        print("XDEX historical transaction fee / compute-budget diagnostics")
        for row in diagnostics:
            print(row)
        print("X1 RPC failures during bounded sample")
        for row in rpc_failures:
            print(row)
        print(
            "Interpretation boundary: X1 Tachyon v3.1 source defines base fee as derived compute units times 10 and total fee as base plus prioritization fee. "
            "This live test independently checks completed XDEX transaction metadata against that formula. "
            "Transaction-layer network/CU fees remain separate from the independently observed 2800->3000 XDEX quote-engine curve difference."
        )

        if len(diagnostics) < 3 and rpc_failures:
            self.skipTest(
                "official X1 RPC did not return enough historical transactions in this run; "
                f"successful={len(diagnostics)} rpc_failures={len(rpc_failures)}"
            )

        self.assertGreaterEqual(
            len(diagnostics),
            3,
            "need at least three successful completed XDEX swaps with RPC transaction metadata",
        )
        for row in diagnostics:
            self.assertGreater(row["network_fee_raw"], 0, row)
            self.assertTrue(row["x1_dynamic_fee_formula_exactly_consistent"], row)
            limit = row["compute_unit_limit"]
            consumed = row["compute_units_consumed"]
            if isinstance(limit, int) and isinstance(consumed, int):
                self.assertGreaterEqual(limit, consumed, row)


if __name__ == "__main__":
    unittest.main()
