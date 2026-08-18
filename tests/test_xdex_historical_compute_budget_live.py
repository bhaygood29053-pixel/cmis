import os
import struct
import unittest

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import rpc_request


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111"
TARGET_SAMPLE_COUNT = 5

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


def _extract_budget_summary(rows):
    limit = None
    price = None
    for row in rows:
        if row.get("kind") == "set_compute_unit_limit":
            limit = row.get("compute_unit_limit")
        elif row.get("kind") == "set_compute_unit_price":
            price = row.get("compute_unit_price_raw")
    return limit, price


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
        seen = set()
        for trade in trades:
            signature = str(trade.get("txHash") or "").strip()
            if not signature or signature in seen:
                continue
            seen.add(signature)

            tx = _get_transaction(signature)
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

            # This is a diagnostic candidate only. X1 documents dynamic base
            # fees, so Solana's priority-fee arithmetic must not be promoted as
            # X1's exact all-in fee formula without X1-specific corroboration.
            solana_style_priority_candidate = None
            if isinstance(limit, int) and isinstance(price, int):
                solana_style_priority_candidate = (limit * price + 999_999) // 1_000_000

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
                    "solana_style_priority_fee_candidate_raw": solana_style_priority_candidate,
                    "compute_budget_instructions": rows,
                }
            )
            if len(diagnostics) >= TARGET_SAMPLE_COUNT:
                break

        print("XDEX historical transaction fee / compute-budget diagnostics")
        for row in diagnostics:
            print(row)
        print(
            "Interpretation boundary: meta.fee is transaction-layer network-fee evidence and ComputeBudget instructions are transaction resource/prioritization evidence. "
            "Neither field is used to relabel the independently observed 2800->3000 XDEX quote-engine curve difference. "
            "The Solana-style priority-fee candidate is diagnostic only because X1 documents congestion-reflective dynamic base fees."
        )

        self.assertGreaterEqual(
            len(diagnostics),
            3,
            "need at least three successful completed XDEX swaps with RPC transaction metadata",
        )
        for row in diagnostics:
            self.assertGreater(row["network_fee_raw"], 0, row)
            limit = row["compute_unit_limit"]
            consumed = row["compute_units_consumed"]
            if isinstance(limit, int) and isinstance(consumed, int):
                self.assertGreaterEqual(limit, consumed, row)


if __name__ == "__main__":
    unittest.main()
