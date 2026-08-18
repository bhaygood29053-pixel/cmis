import unittest
from fractions import Fraction
from math import floor

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rpc import X1RPCError

from tests.test_xdex_executed_fee_semantics_live import (
    RUN_LIVE,
    POOL,
    CONFIG_2800,
    XENCAT,
    XNT,
    XENCAT_DECIMALS,
    XNT_DECIMALS,
    AMM_CONFIG_INDEX,
    POOL_STATE_INDEX,
    INPUT_VAULT_INDEX,
    OUTPUT_VAULT_INDEX,
    INPUT_MINT_INDEX,
    OUTPUT_MINT_INDEX,
    EXPECTED_ACCOUNT_COUNT,
    _ceil_fee,
    _close_raw,
    _decode_swap_base_input,
    _get_transaction,
    _raw_from_provider,
    _token_balance_map,
)


FEE_DENOMINATOR = 1_000_000
PROTOCOL_FEE_RATE = 250_000
FUND_FEE_RATE = 50_000
SEARCH_RADIUS = 256
MAX_SIGNATURE_ATTEMPTS = 32
MIN_CHAIN_LENGTH = 5


def _excluded_fee_increment(trade_fee):
    # Reference Raydium CP-Swap and the decoded XDEX config model protocol/fund
    # rates as portions within the trade fee. The supplied XDEX v0.1.0 IDL has
    # no creator-fee fields, so only protocol + fund counters are modeled here.
    return (
        (int(trade_fee) * PROTOCOL_FEE_RATE) // FEE_DENOMINATOR
        + (int(trade_fee) * FUND_FEE_RATE) // FEE_DENOMINATOR
    )


def _net_input(amount_in, rate_ppm):
    return int(amount_in) - _ceil_fee(amount_in, rate_ppm)


def _normalize_row(ix, pre, post, tx, signature):
    accounts = ix["accounts"]
    if len(accounts) < EXPECTED_ACCOUNT_COUNT:
        return None
    if accounts[AMM_CONFIG_INDEX] != CONFIG_2800 or accounts[POOL_STATE_INDEX] != POOL:
        return None

    input_vault = accounts[INPUT_VAULT_INDEX]
    output_vault = accounts[OUTPUT_VAULT_INDEX]
    input_mint = accounts[INPUT_MINT_INDEX]
    output_mint = accounts[OUTPUT_MINT_INDEX]
    input_pre = (pre.get(input_vault) or {}).get("raw")
    input_post = (post.get(input_vault) or {}).get("raw")
    output_pre = (pre.get(output_vault) or {}).get("raw")
    output_post = (post.get(output_vault) or {}).get("raw")
    if not all(isinstance(v, int) for v in (input_pre, input_post, output_pre, output_post)):
        return None

    if input_mint == XENCAT and output_mint == XNT:
        direction = "T2N"
        t_pre, t_post = input_pre, input_post
        n_pre, n_post = output_pre, output_post
        actual_output = n_pre - n_post
    elif input_mint == XNT and output_mint == XENCAT:
        direction = "N2T"
        n_pre, n_post = input_pre, input_post
        t_pre, t_post = output_pre, output_post
        actual_output = t_pre - t_post
    else:
        return None

    if actual_output <= 0:
        return None
    return {
        "signature": signature,
        "slot": tx.get("slot"),
        "direction": direction,
        "amount_in_raw": ix["amount_in_raw"],
        "minimum_amount_out_raw": ix["minimum_amount_out_raw"],
        "t_pre": t_pre,
        "t_post": t_post,
        "n_pre": n_pre,
        "n_post": n_post,
        "actual_output_raw": actual_output,
        "pre_state": (t_pre, n_pre),
        "post_state": (t_post, n_post),
    }


def _longest_state_contiguous_chain(rows):
    by_pre = {}
    post_states = set()
    for row in rows:
        by_pre[row["pre_state"]] = row
        post_states.add(row["post_state"])

    starts = [row for row in rows if row["pre_state"] not in post_states]
    if not starts:
        starts = list(rows)

    best = []
    for start in starts:
        chain = []
        seen = set()
        row = start
        while row is not None and row["signature"] not in seen:
            chain.append(row)
            seen.add(row["signature"])
            row = by_pre.get(row["post_state"])
        if len(chain) > len(best):
            best = chain
    return best


def _opposite_direction_slice(chain):
    for index in range(len(chain) - 1):
        if chain[index]["direction"] != chain[index + 1]["direction"]:
            return chain[index:]
    return []


def _infer_initial_counter_pair(first, second, rate_ppm):
    """Infer continuous fee-counter values from the first opposite-direction pair.

    For first A->B then B->A, constant-product equations are linear in the
    unknown excluded-fee counters once the first equation is substituted into
    the second. Fraction keeps this seed deterministic and exact; nearby integer
    counters are then searched against the full contiguous transaction chain.
    """

    if first["direction"] == second["direction"]:
        raise ValueError("first two swaps must have opposite directions")

    if first["direction"] == "N2T":
        ga1, gb1 = first["n_pre"], first["t_pre"]
        ga2, gb2 = second["n_pre"], second["t_pre"]
        a_counter_name = "N"
    else:
        ga1, gb1 = first["t_pre"], first["n_pre"]
        ga2, gb2 = second["t_pre"], second["n_pre"]
        a_counter_name = "T"

    amount1 = first["amount_in_raw"]
    amount2 = second["amount_in_raw"]
    output1 = first["actual_output_raw"]
    output2 = second["actual_output_raw"]
    net1 = _net_input(amount1, rate_ppm)
    net2 = _net_input(amount2, rate_ppm)
    trade_fee1 = _ceil_fee(amount1, rate_ppm)
    counter_increment1 = _excluded_fee_increment(trade_fee1)

    beta = Fraction(output1, net1)
    alpha = Fraction(gb1, 1) - beta * Fraction(ga1 + net1, 1)
    denominator = Fraction(net2, 1) - Fraction(output2, 1) * beta
    if denominator == 0:
        raise ValueError("degenerate counter inference denominator")
    numerator = (
        Fraction(net2 * (ga2 - counter_increment1), 1)
        - Fraction(output2, 1) * (Fraction(gb2 + net2, 1) - alpha)
    )
    counter_a = numerator / denominator
    counter_b = alpha + beta * counter_a

    if a_counter_name == "N":
        return counter_b, counter_a  # T, N
    return counter_a, counter_b


def _simulate_chain(chain, initial_t_counter, initial_n_counter, rate_ppm):
    t_counter = int(initial_t_counter)
    n_counter = int(initial_n_counter)
    rows = []
    for row in chain:
        amount_in = row["amount_in_raw"]
        trade_fee = _ceil_fee(amount_in, rate_ppm)
        net = amount_in - trade_fee
        if row["direction"] == "N2T":
            active_in = row["n_pre"] - n_counter
            active_out = row["t_pre"] - t_counter
            if active_in <= 0 or active_out <= 0:
                return None
            predicted = (net * active_out) // (active_in + net)
            n_counter += _excluded_fee_increment(trade_fee)
        else:
            active_in = row["t_pre"] - t_counter
            active_out = row["n_pre"] - n_counter
            if active_in <= 0 or active_out <= 0:
                return None
            predicted = (net * active_out) // (active_in + net)
            t_counter += _excluded_fee_increment(trade_fee)

        error = predicted - row["actual_output_raw"]
        rows.append(
            {
                "signature": row["signature"],
                "slot": row["slot"],
                "direction": row["direction"],
                "predicted_output_raw": predicted,
                "actual_output_raw": row["actual_output_raw"],
                "error_raw": error,
            }
        )
    return rows


def _best_candidate(chain, rate_ppm):
    seed_t, seed_n = _infer_initial_counter_pair(chain[0], chain[1], rate_ppm)
    center_t = round(float(seed_t))
    center_n = round(float(seed_n))
    best = None
    for t_delta in range(-SEARCH_RADIUS, SEARCH_RADIUS + 1):
        t_counter = center_t + t_delta
        if t_counter < 0:
            continue
        for n_delta in range(-SEARCH_RADIUS, SEARCH_RADIUS + 1):
            n_counter = center_n + n_delta
            if n_counter < 0:
                continue
            simulated = _simulate_chain(chain, t_counter, n_counter, rate_ppm)
            if not simulated:
                continue
            errors = [abs(row["error_raw"]) for row in simulated]
            score = (max(errors), sum(errors))
            if best is None or score < best["score"]:
                best = {
                    "rate_ppm": rate_ppm,
                    "initial_t_counter_raw": t_counter,
                    "initial_n_counter_raw": n_counter,
                    "score": score,
                    "max_abs_error_raw": score[0],
                    "sum_abs_error_raw": score[1],
                    "rows": simulated,
                    "fraction_seed_t": str(seed_t),
                    "fraction_seed_n": str(seed_n),
                }
    return best


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_EXECUTED_FEE_LIVE=1 to reconstruct completed XDEX swaps read-only",
)
class XDEXExecutedFeeSequenceLiveTests(unittest.TestCase):
    def test_contiguous_completed_swap_sequence_strongly_favors_2800(self):
        history = fetch_pool_trades_raw(POOL)
        trades = history["raw_response"]["trades"]
        self.assertTrue(trades)

        rows = []
        failures = []
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
                failures.append({"signature": signature, "error": str(exc)})
                continue
            if not isinstance(tx, dict) or ((tx.get("meta") or {}).get("err") is not None):
                continue

            token_raw = _raw_from_provider(trade.get("amountToken"), XENCAT_DECIMALS)
            native_raw = _raw_from_provider(trade.get("amountNative"), XNT_DECIMALS)
            pre = _token_balance_map(tx, "preTokenBalances")
            post = _token_balance_map(tx, "postTokenBalances")
            for ix in _decode_swap_base_input(tx):
                amount_in = ix["amount_in_raw"]
                if not (_close_raw(amount_in, token_raw) or _close_raw(amount_in, native_raw)):
                    continue
                row = _normalize_row(ix, pre, post, tx, signature)
                if row is not None:
                    rows.append(row)
                    break

        chain = _longest_state_contiguous_chain(rows)
        chain = _opposite_direction_slice(chain)
        print("XDEX longest state-contiguous completed-swap chain")
        for row in chain:
            print(row)
        print("RPC failures")
        for row in failures:
            print(row)

        self.assertGreaterEqual(
            len(chain),
            MIN_CHAIN_LENGTH,
            "need a state-contiguous chain of completed swaps with an opposite-direction pair",
        )
        for left, right in zip(chain, chain[1:]):
            self.assertEqual(left["post_state"], right["pre_state"], (left, right))

        candidate_2800 = _best_candidate(chain, 2800)
        candidate_3000 = _best_candidate(chain, 3000)
        print("XDEX 2800 contiguous-sequence reconstruction")
        print(candidate_2800)
        print("XDEX 3000 contiguous-sequence reconstruction")
        print(candidate_3000)

        self.assertIsNotNone(candidate_2800)
        self.assertIsNotNone(candidate_3000)

        # Historical RPC output deltas are exact raw-token execution amounts.
        # The 2800 model should reproduce the linked sequence essentially at
        # integer-rounding precision, while 3000 should be materially worse.
        self.assertLessEqual(candidate_2800["max_abs_error_raw"], 10_000, candidate_2800)
        self.assertGreater(
            candidate_3000["max_abs_error_raw"],
            candidate_2800["max_abs_error_raw"] * 1_000,
            {"candidate_2800": candidate_2800, "candidate_3000": candidate_3000},
        )

        print(
            "Interpretation boundary: under the Raydium-derived fee-counter accounting model and the decoded XDEX protocol/fund rates, "
            "the state-contiguous completed-swap sequence strongly favors 2800 ppm over 3000 ppm. This is independent historical execution corroboration, "
            "but authoritative XDEX source or historical config-state proof is still required before upgrading the implementation reason to globally VERIFIED."
        )


if __name__ == "__main__":
    unittest.main()
