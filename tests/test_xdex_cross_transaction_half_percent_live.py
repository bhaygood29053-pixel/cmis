import os
import unittest
from collections import Counter
from decimal import Decimal

from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.transaction_semantics import fetch_transaction
from tests.test_xdex_onchain_slippage_semantics_live import (
    POOL,
    XNT,
    XENCAT,
    _all_instructions,
    _decode_base_input,
    _pool_program_instructions,
    _raw_token_balances,
    _vault_outflow,
)


RUN_LIVE = os.getenv("RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE") == "1"
MAX_SIGNATURES = 160
TARGET_SAMPLES = 30
VISIBLE_PRESETS_PCT = (
    Decimal("0.5"),
    Decimal("1"),
    Decimal("2"),
    Decimal("5"),
)
HALF_LAYER_LOW = Decimal("0.45")
HALF_LAYER_HIGH = Decimal("0.60")
TARGET_LAYER = Decimal("0.52")
SYSTEM_PROGRAM = "11111111111111111111111111111111"


def _mint_deltas(tx, mint):
    pre, post = _raw_token_balances(tx)
    accounts = set(pre) | set(post)
    out = {}
    for account in accounts:
        before = pre.get(account)
        after = post.get(account)
        record = after or before
        if not record or record.get("mint") != mint:
            continue
        before_raw = int(before.get("amount_raw", 0)) if before else 0
        after_raw = int(after.get("amount_raw", 0)) if after else 0
        delta = after_raw - before_raw
        if delta:
            out[account] = delta
    return out


def _system_transfers(tx):
    transfers = []
    for instruction, _account_keys, location in _all_instructions(tx):
        program = instruction.get("program")
        program_id = instruction.get("programId")
        if isinstance(program_id, dict):
            program_id = program_id.get("pubkey") or program_id.get("address")
        if program != "system" and program_id != SYSTEM_PROGRAM:
            continue
        parsed = instruction.get("parsed")
        if not isinstance(parsed, dict) or parsed.get("type") != "transfer":
            continue
        info = parsed.get("info") or {}
        lamports = info.get("lamports")
        try:
            lamports = int(lamports)
        except (TypeError, ValueError):
            continue
        if lamports <= 0:
            continue
        transfers.append(
            {
                "source": str(info.get("source") or ""),
                "destination": str(info.get("destination") or ""),
                "lamports": lamports,
                "location": location,
            }
        )
    return transfers


def _preset_residual(headroom_pct):
    candidates = []
    for preset in VISIBLE_PRESETS_PCT:
        residual = headroom_pct - preset
        if residual < 0:
            continue
        candidates.append((abs(residual - TARGET_LAYER), preset, residual))
    if not candidates:
        return None, None
    _distance, preset, residual = min(candidates, key=lambda row: row[0])
    return preset, residual


def _pct(part, whole):
    if whole <= 0:
        return None
    return Decimal(part) / Decimal(whole) * Decimal(100)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE=1 to run read-only cross-transaction fee evidence",
)
class XDEXCrossTransactionHalfPercentLiveTests(unittest.TestCase):
    def test_cross_transaction_half_percent_flow_evidence(self):
        history = rpc_request(
            "getSignaturesForAddress",
            [POOL, {"limit": MAX_SIGNATURES}],
        )
        self.assertIsInstance(history, list)
        self.assertTrue(history)

        samples = []
        output_flow_observable = 0
        output_fully_to_designated_account = 0
        input_flow_observable = 0
        input_fully_to_vault = 0
        token_fee_candidates = []
        native_fee_candidates = []
        preset_plus_half_fits = []
        native_candidate_destinations = Counter()

        for entry in history:
            if len(samples) >= TARGET_SAMPLES:
                break
            if not isinstance(entry, dict) or entry.get("err") is not None:
                continue
            signature = str(entry.get("signature") or "").strip()
            if not signature:
                continue

            tx = fetch_transaction(signature)
            if not isinstance(tx, dict) or (tx.get("meta") or {}).get("err") is not None:
                continue

            pool_instructions = _pool_program_instructions(tx)
            if len(pool_instructions) != 1:
                continue
            instruction, accounts, location = pool_instructions[0]
            decoded = _decode_base_input(instruction, accounts, location)
            if decoded is None:
                continue
            if {decoded["input_mint"], decoded["output_mint"]} != {XNT, XENCAT}:
                continue

            outflow = _vault_outflow(tx, decoded["output_vault"], decoded["output_mint"])
            if outflow is None:
                continue
            actual_output_raw, _output_decimals = outflow
            minimum_output_raw = decoded["amount_out_min_raw"]
            if minimum_output_raw <= 0 or minimum_output_raw > actual_output_raw:
                continue

            headroom_pct = (
                (Decimal(actual_output_raw) - Decimal(minimum_output_raw))
                / Decimal(actual_output_raw)
                * Decimal(100)
            )
            preset, residual = _preset_residual(headroom_pct)
            if residual is not None and HALF_LAYER_LOW <= residual <= HALF_LAYER_HIGH:
                preset_plus_half_fits.append(
                    {
                        "signature": signature,
                        "slot": tx.get("slot"),
                        "headroom_pct": str(headroom_pct),
                        "preset_pct": str(preset),
                        "separate_residual_pct": str(residual),
                    }
                )

            input_deltas = _mint_deltas(tx, decoded["input_mint"])
            output_deltas = _mint_deltas(tx, decoded["output_mint"])

            input_vault_delta = input_deltas.get(decoded["input_vault"])
            if input_vault_delta is not None:
                input_flow_observable += 1
                if input_vault_delta == decoded["amount_in_raw"]:
                    input_fully_to_vault += 1

            user_output_delta = output_deltas.get(decoded["user_output"])
            if user_output_delta is not None and user_output_delta > 0:
                output_flow_observable += 1
                positive_other = sum(
                    delta
                    for account, delta in output_deltas.items()
                    if delta > 0
                    and account not in {decoded["output_vault"], decoded["user_output"]}
                )
                if user_output_delta == actual_output_raw and positive_other == 0:
                    output_fully_to_designated_account += 1

            # Search all same-token account changes for an explicit extra transfer
            # around 0.52%. This would be evidence of a separately routed token fee.
            for account, delta in output_deltas.items():
                if delta <= 0 or account in {decoded["output_vault"], decoded["user_output"]}:
                    continue
                ratio = _pct(delta, actual_output_raw)
                if ratio is not None and HALF_LAYER_LOW <= ratio <= HALF_LAYER_HIGH:
                    token_fee_candidates.append(
                        {
                            "signature": signature,
                            "side": "output",
                            "account": account,
                            "ratio_pct": str(ratio),
                            "raw_amount": delta,
                        }
                    )

            for account, delta in input_deltas.items():
                if delta <= 0 or account == decoded["input_vault"]:
                    continue
                ratio = _pct(delta, decoded["amount_in_raw"])
                if ratio is not None and HALF_LAYER_LOW <= ratio <= HALF_LAYER_HIGH:
                    token_fee_candidates.append(
                        {
                            "signature": signature,
                            "side": "input",
                            "account": account,
                            "ratio_pct": str(ratio),
                            "raw_amount": delta,
                        }
                    )

            # A fee denominated directly in native XNT would appear as a System
            # Program transfer. Compare those transfers to the XNT leg of the swap.
            xnt_reference_raw = (
                decoded["amount_in_raw"]
                if decoded["input_mint"] == XNT
                else actual_output_raw
            )
            for transfer in _system_transfers(tx):
                ratio = _pct(transfer["lamports"], xnt_reference_raw)
                if ratio is None or not (HALF_LAYER_LOW <= ratio <= HALF_LAYER_HIGH):
                    continue
                candidate = {
                    "signature": signature,
                    "destination": transfer["destination"],
                    "ratio_pct": str(ratio),
                    "lamports": transfer["lamports"],
                    "location": transfer["location"],
                }
                native_fee_candidates.append(candidate)
                native_candidate_destinations[transfer["destination"]] += 1

            samples.append(
                {
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "direction": f"{decoded['input_mint']}->{decoded['output_mint']}",
                    "amount_in_raw": decoded["amount_in_raw"],
                    "actual_output_raw": actual_output_raw,
                    "minimum_output_raw": minimum_output_raw,
                    "headroom_pct": str(headroom_pct),
                    "input_vault_delta_raw": input_vault_delta,
                    "user_output_delta_raw": user_output_delta,
                    "network_fee_lamports": int((tx.get("meta") or {}).get("fee") or 0),
                }
            )

        print("XDEX cross-transaction ~0.52% charge investigation")
        print(f"Pool: {POOL}")
        print(f"Successful simple exact-input swaps analyzed: {len(samples)}")
        print(f"Visible-preset + ~0.52% minimum-output fits: {len(preset_plus_half_fits)}")
        for row in preset_plus_half_fits:
            print(f"preset-fit: {row}")
        print(
            "Input token flow fully into decoded pool vault: "
            f"{input_fully_to_vault}/{input_flow_observable} observable swaps"
        )
        print(
            "Actual pool output fully reaches decoded user output token account: "
            f"{output_fully_to_designated_account}/{output_flow_observable} observable swaps"
        )
        print(f"Explicit ~0.52% same-token extra recipients: {len(token_fee_candidates)}")
        for row in token_fee_candidates:
            print(f"token-fee-candidate: {row}")
        print(f"Explicit ~0.52% native-XNT System transfers: {len(native_fee_candidates)}")
        for row in native_fee_candidates:
            print(f"native-fee-candidate: {row}")
        print(f"Native candidate destination frequency: {dict(native_candidate_destinations)}")

        self.assertGreaterEqual(
            len(samples),
            5,
            "Insufficient recent simple XDEX swaps for cross-transaction evidence",
        )

        if token_fee_candidates or native_fee_candidates:
            print(
                "Evidence classification: POSSIBLE explicit ~0.52% fee transfer(s) observed; "
                "recipient identity and economic semantics require a dedicated follow-up."
            )
        else:
            print(
                "Evidence classification: NO explicit separately transferred ~0.52% charge "
                "was observed in the sampled token or native-XNT transaction flows. The "
                "~0.52% layer remains consistent with quote/min-output construction or an "
                "embedded pool/accounting rule rather than a standalone recipient transfer."
            )


if __name__ == "__main__":
    unittest.main()
