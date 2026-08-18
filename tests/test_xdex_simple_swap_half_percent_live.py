import os
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.transaction_semantics import (
    account_key_info,
    collect_program_ids,
    compute_token_deltas,
    fetch_transaction,
)
from tests.test_xdex_cross_transaction_half_percent_live import _mint_deltas
from tests.test_xdex_onchain_slippage_semantics_live import (
    POOL,
    PROGRAM,
    XNT,
    XENCAT,
    _all_instructions,
    _decode_base_input,
    _pool_program_instructions,
    _program_id,
    _vault_outflow,
)


RUN_LIVE = os.getenv("RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE") == "1"
MAX_SIGNATURES = 300
TARGET_SIMPLE_SWAPS = 12
HALF_LOW = Decimal("0.45")
HALF_HIGH = Decimal("0.60")

SYSTEM_PROGRAM = "11111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111"
MEMO_PROGRAM = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
ALLOWED_PROGRAMS = {
    PROGRAM,
    SYSTEM_PROGRAM,
    TOKEN_PROGRAM,
    ASSOCIATED_TOKEN_PROGRAM,
    COMPUTE_BUDGET_PROGRAM,
    MEMO_PROGRAM,
}


def _pct(part, whole):
    if whole <= 0:
        return None
    return Decimal(part) / Decimal(whole) * Decimal(100)


def _count_xdex_instructions(tx):
    count = 0
    for instruction, account_keys, _location in _all_instructions(tx):
        if _program_id(instruction, account_keys) == PROGRAM:
            count += 1
    return count


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE=1 to run read-only simple-swap charge evidence",
)
class XDEXSimpleSwapHalfPercentLiveTests(unittest.TestCase):
    def test_direct_simple_swaps_do_not_hide_half_percent_xencat_transfer(self):
        history = rpc_request(
            "getSignaturesForAddress",
            [POOL, {"limit": MAX_SIGNATURES}],
        )
        self.assertIsInstance(history, list)

        samples = []
        half_percent_charge_samples = []
        exact_zero_extra_charge = 0
        rejected_custom_program = 0
        rejected_third_mint = 0
        rejected_multi_xdex = 0

        for entry in history:
            if len(samples) >= TARGET_SIMPLE_SWAPS:
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

            if _count_xdex_instructions(tx) != 1:
                rejected_multi_xdex += 1
                continue

            program_ids = set(collect_program_ids(tx))
            unexpected_programs = sorted(program_ids - ALLOWED_PROGRAMS)
            if unexpected_programs:
                rejected_custom_program += 1
                continue

            token_rows = compute_token_deltas(tx)
            changed_mints = {row.mint for row in token_rows}
            if changed_mints - {XNT, XENCAT}:
                rejected_third_mint += 1
                continue

            outflow = _vault_outflow(tx, decoded["output_vault"], decoded["output_mint"])
            if outflow is None:
                continue
            actual_output_raw, _decimals = outflow

            xencat_deltas = _mint_deltas(tx, XENCAT)
            charge_raw = None
            charge_pct = None
            xencat_user_delta = None
            measurement = None

            if decoded["output_mint"] == XENCAT:
                # XNT -> XENCAT: compare exactly what left the XENCAT pool vault
                # with the designated user's XENCAT token-account increase.
                xencat_user_delta = xencat_deltas.get(decoded["user_output"])
                if xencat_user_delta is None or xencat_user_delta <= 0:
                    continue
                charge_raw = actual_output_raw - xencat_user_delta
                if charge_raw < 0:
                    continue
                charge_pct = _pct(charge_raw, actual_output_raw)
                measurement = "pool_xencat_out_minus_user_xencat_received"
            else:
                # XENCAT -> XNT: compare the designated user's XENCAT decrease
                # with amount_in encoded in the XDEX swap instruction.
                xencat_user_delta = xencat_deltas.get(decoded["user_input"])
                if xencat_user_delta is None or xencat_user_delta >= 0:
                    continue
                user_spent_raw = -xencat_user_delta
                charge_raw = user_spent_raw - decoded["amount_in_raw"]
                if charge_raw < 0:
                    continue
                charge_pct = _pct(charge_raw, decoded["amount_in_raw"])
                measurement = "user_xencat_spent_minus_encoded_xencat_amount_in"

            if charge_pct is None:
                continue

            _keys, signers = account_key_info(tx)
            row = {
                "signature": signature,
                "slot": tx.get("slot"),
                "direction": f"{decoded['input_mint']}->{decoded['output_mint']}",
                "primary_signer": signers[0] if signers else None,
                "measurement": measurement,
                "xencat_user_delta_raw": xencat_user_delta,
                "amount_in_raw": decoded["amount_in_raw"],
                "actual_pool_output_raw": actual_output_raw,
                "extra_charge_raw": charge_raw,
                "extra_charge_pct": str(charge_pct),
                "network_fee_lamports": int((tx.get("meta") or {}).get("fee") or 0),
            }
            samples.append(row)

            if charge_raw == 0:
                exact_zero_extra_charge += 1
            if HALF_LOW <= charge_pct <= HALF_HIGH:
                half_percent_charge_samples.append(row)

        print("XDEX direct/simple swap ~0.52% actual-charge test")
        print(f"Pool: {POOL}")
        print(f"Direct/simple swaps with clean XENCAT-side accounting: {len(samples)}")
        print(f"Rejected for additional XDEX instructions: {rejected_multi_xdex}")
        print(f"Rejected for additional custom programs: {rejected_custom_program}")
        print(f"Rejected for third-token movement: {rejected_third_mint}")
        print(f"Exact zero extra XENCAT charge: {exact_zero_extra_charge}/{len(samples)}")
        print(f"~0.45%-0.60% actual XENCAT charge observations: {len(half_percent_charge_samples)}")
        for row in samples:
            print(f"simple-swap: {row}")

        self.assertTrue(
            samples,
            "No recent direct/simple XDEX XENCAT/XNT swap exposed clean XENCAT-side accounting",
        )

        if half_percent_charge_samples:
            print(
                "Evidence classification: an actual ~0.52% XENCAT-side charge was observed "
                "in at least one direct/simple swap; follow the recipient before assigning an economic label."
            )
        elif exact_zero_extra_charge == len(samples):
            print(
                "Evidence classification: no ~0.52% token charge was paid on the clean XENCAT side "
                "of any sampled direct/simple swap. The recurring ~0.52% layer is therefore not a "
                "separate XENCAT transfer fee in these transactions."
            )
        else:
            print(
                "Evidence classification: sampled direct/simple swaps show nonzero XENCAT-side differences, "
                "but they do not cluster in the ~0.52% band."
            )


if __name__ == "__main__":
    unittest.main()
