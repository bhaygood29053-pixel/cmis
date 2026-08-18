import os
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import rpc_request


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
XENCAT_DECIMALS = 6
XNT_DECIMALS = 9
TARGET_SAMPLE_COUNT = 5


def _raw(value, decimals):
    if value is None or isinstance(value, bool):
        return None
    return int((Decimal(str(value)) * (Decimal(10) ** decimals)).to_integral_value())


def _account_keys(tx):
    message = ((tx or {}).get("transaction") or {}).get("message") or {}
    keys = message.get("accountKeys") or []
    result = []
    for entry in keys:
        if isinstance(entry, dict):
            result.append(str(entry.get("pubkey") or ""))
        else:
            result.append(str(entry or ""))
    return result


def _token_account_mints(tx):
    keys = _account_keys(tx)
    mapping = {}
    meta = (tx or {}).get("meta") or {}
    for side in ("preTokenBalances", "postTokenBalances"):
        for row in meta.get(side) or []:
            index = row.get("accountIndex")
            mint = row.get("mint")
            if isinstance(index, int) and 0 <= index < len(keys) and mint:
                mapping[keys[index]] = str(mint)
    return mapping


def _iter_parsed_transfers(tx):
    message = ((tx or {}).get("transaction") or {}).get("message") or {}
    outer = message.get("instructions") or []
    for ix in outer:
        if isinstance(ix, dict):
            yield ix, "outer"

    meta = (tx or {}).get("meta") or {}
    for group in meta.get("innerInstructions") or []:
        for ix in (group or {}).get("instructions") or []:
            if isinstance(ix, dict):
                yield ix, "inner"


def _transfer_rows(tx):
    mint_by_account = _token_account_mints(tx)
    rows = []
    for ix, location in _iter_parsed_transfers(tx):
        parsed = ix.get("parsed")
        if not isinstance(parsed, dict):
            continue
        ix_type = str(parsed.get("type") or "")
        if ix_type not in {"transfer", "transferChecked"}:
            continue
        info = parsed.get("info")
        if not isinstance(info, dict):
            continue
        source = str(info.get("source") or "")
        destination = str(info.get("destination") or "")
        amount = info.get("amount")
        token_amount = info.get("tokenAmount")
        if amount is None and isinstance(token_amount, dict):
            amount = token_amount.get("amount")
        try:
            raw_amount = int(amount)
        except (TypeError, ValueError):
            continue
        mint = str(info.get("mint") or mint_by_account.get(source) or mint_by_account.get(destination) or "")
        rows.append(
            {
                "location": location,
                "program": ix.get("program"),
                "type": ix_type,
                "source": source,
                "destination": destination,
                "mint": mint,
                "amount_raw": raw_amount,
            }
        )
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


def _near(value, target):
    if value is None or target is None:
        return False
    tolerance = max(10, abs(int(target)) // 1_000_000_000)
    return abs(int(value) - int(target)) <= tolerance


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to inspect completed XDEX swaps read-only",
)
class XDEXHistoricalIntegratorFeeTransferLiveTests(unittest.TestCase):
    def test_completed_direct_swaps_expose_or_fail_to_expose_separate_two_bp_transfer(self):
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
            if not isinstance(tx, dict) or ((tx.get("meta") or {}).get("err") is not None):
                continue

            token_in = _raw(trade.get("amountToken"), XENCAT_DECIMALS)
            native_in = _raw(trade.get("amountNative"), XNT_DECIMALS)
            if not token_in or not native_in:
                continue

            transfers = _transfer_rows(tx)
            relevant = [row for row in transfers if row["mint"] in {XENCAT, XNT}]
            if not relevant:
                continue

            # A claimed 2-bp integrator fee on input would be ~200 ppm of the
            # user input. We do not assume which direction X1.Ninja labels as
            # buy/sell; test both observed asset amounts as candidate inputs.
            candidate_fee_amounts = {
                "xencat_2bp_raw": (token_in * 200 + 999_999) // 1_000_000,
                "xnt_2bp_raw": (native_in * 200 + 999_999) // 1_000_000,
            }
            suspected = []
            for row in relevant:
                if any(_near(row["amount_raw"], target) for target in candidate_fee_amounts.values()):
                    suspected.append(row)

            diagnostics.append(
                {
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "amount_token_raw": token_in,
                    "amount_native_raw": native_in,
                    "candidate_2bp_fee_raw": candidate_fee_amounts,
                    "relevant_transfer_count": len(relevant),
                    "suspected_2bp_transfers": suspected,
                    "transfers": relevant,
                }
            )
            if len(diagnostics) >= TARGET_SAMPLE_COUNT:
                break

        print("XDEX historical direct-swap separate-2bp-transfer diagnostics")
        for row in diagnostics:
            print(row)
        print(
            "Interpretation boundary: a matching extra transfer would support a separately collected interface/integrator fee. "
            "No matching transfer in this bounded sample would weigh against that label but would not prove global absence; "
            "the 2800->3000 quote baseline could instead be a conservative quote convention or other backend behavior."
        )

        self.assertGreaterEqual(
            len(diagnostics),
            3,
            "need at least three successful completed direct swaps with parsed XENCAT/XNT token transfers",
        )
