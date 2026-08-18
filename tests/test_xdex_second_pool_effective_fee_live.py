import base64
import os
import struct
import unittest
from decimal import Decimal

import requests

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info, rpc_request
from liquidity_scout.providers.x1.xdex import SWAP_QUOTE_URL


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
XNT = "So11111111111111111111111111111111111111112"
USDC_X = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
POOL_SIZE = 637
FEE_DENOM = 1_000_000
EXTRA_CANDIDATE_RATE = 200  # 2 bps; arithmetic hypothesis only.


def _u64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data, offset):
    return encode_base58_pubkey(data[offset : offset + 32])


def _ceil_fee(amount, rate):
    return (amount * rate + FEE_DENOM - 1) // FEE_DENOM if rate else 0


def _curve_exact_in(raw_input, reserve_in, reserve_out, fee_rate):
    fee = _ceil_fee(raw_input, fee_rate)
    net = raw_input - fee
    return net * reserve_out // (reserve_in + net)


def _raw_amount(ui_amount, decimals):
    scaled = Decimal(str(ui_amount)) * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise AssertionError("amount not exactly representable in raw units")
    return int(scaled)


def _rpc_pair_rows(mint_0, mint_1):
    result = rpc_request(
        "getProgramAccounts",
        [
            PROGRAM,
            {
                "encoding": "base64",
                "commitment": "confirmed",
                "filters": [
                    {"dataSize": POOL_SIZE},
                    {"memcmp": {"offset": 168, "bytes": mint_0}},
                    {"memcmp": {"offset": 200, "bytes": mint_1}},
                ],
            },
        ],
    )
    rows = result.get("value") if isinstance(result, dict) and "value" in result else result
    return rows if isinstance(rows, list) else []


def _discover_pair_pools():
    discovered = {}
    for mint_0, mint_1 in ((USDC_X, XNT), (XNT, USDC_X)):
        for row in _rpc_pair_rows(mint_0, mint_1):
            if not isinstance(row, dict) or not row.get("pubkey"):
                continue
            account = row.get("account") or {}
            raw = account.get("data")
            encoded = raw[0] if isinstance(raw, list) and raw else None
            if not isinstance(encoded, str):
                continue
            try:
                data = base64.b64decode(encoded)
            except Exception:
                continue
            if len(data) != POOL_SIZE:
                continue
            if _pubkey(data, 168) != mint_0 or _pubkey(data, 200) != mint_1:
                continue
            discovered[str(row["pubkey"])] = {
                "pool": str(row["pubkey"]),
                "mint_0": mint_0,
                "mint_1": mint_1,
                "amm_config": _pubkey(data, 8),
            }
    return list(discovered.values())


def _decode_pool(pool_address):
    state = fetch_account_state(pool_address)
    data = state["data"]
    if state.get("owner") != PROGRAM or len(data) != POOL_SIZE:
        raise AssertionError(f"discovered pool failed structural check: {pool_address}")
    return {
        "pool": pool_address,
        "amm_config": _pubkey(data, 8),
        "vault_0": _pubkey(data, 72),
        "vault_1": _pubkey(data, 104),
        "mint_0": _pubkey(data, 168),
        "mint_1": _pubkey(data, 200),
        "decimals_0": data[331],
        "decimals_1": data[332],
        "protocol_fees_0": _u64(data, 341),
        "protocol_fees_1": _u64(data, 349),
        "fund_fees_0": _u64(data, 357),
        "fund_fees_1": _u64(data, 365),
        "creator_fees_0": _u64(data, 397),
        "creator_fees_1": _u64(data, 405),
    }


def _decode_config(config_address):
    state = fetch_account_state(config_address)
    data = state["data"]
    if state.get("owner") != PROGRAM or len(data) < 116:
        raise AssertionError(f"AMM config failed structural check: {config_address}")
    return {
        "trade_fee_rate": _u64(data, 12),
        "protocol_fee_rate": _u64(data, 20),
        "fund_fee_rate": _u64(data, 28),
        "creator_fee_rate": _u64(data, 108),
    }


def _active_reserves(pool):
    v0 = get_token_account_info(pool["vault_0"])
    v1 = get_token_account_info(pool["vault_1"])
    if not v0 or not v1 or not v0.get("identity_verified") or not v1.get("identity_verified"):
        raise AssertionError(f"could not verify vaults for {pool['pool']}")
    if v0.get("mint") != pool["mint_0"] or v1.get("mint") != pool["mint_1"]:
        raise AssertionError(f"vault mint mismatch for {pool['pool']}")
    r0 = int(v0["raw_amount"]) - pool["protocol_fees_0"] - pool["fund_fees_0"] - pool["creator_fees_0"]
    r1 = int(v1["raw_amount"]) - pool["protocol_fees_1"] - pool["fund_fees_1"] - pool["creator_fees_1"]
    return r0, r1


def _quote(token_in, token_out, amount):
    response = requests.get(
        SWAP_QUOTE_URL,
        params={
            "network": "X1 Mainnet",
            "token_in": token_in,
            "token_out": token_out,
            "token_in_amount": format(Decimal(str(amount)), "f"),
            "is_exact_amount_in": "true",
            "slippage": "0",
        },
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or body.get("success") is not True or not isinstance(body.get("data"), dict):
        raise AssertionError(f"unexpected XDEX quote response: {body}")
    return body["data"]


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 for second-pool effective-fee evidence",
)
class XDEXSecondPoolEffectiveFeeLiveTests(unittest.TestCase):
    def test_xnt_usdc_pool_localizes_two_basis_point_effective_deduction(self):
        candidates = _discover_pair_pools()
        self.assertTrue(candidates, "X1 RPC found no 637-byte XDEX XNT/USDC.X pool")
        print("XDEX XNT/USDC.X discovered pool candidates", candidates)

        quote_cases = (
            (USDC_X, XNT, Decimal("1")),
            (XNT, USDC_X, Decimal("0.1")),
        )
        evidence = []
        exact_plus_200_matches = 0

        for token_in, token_out, amount in quote_cases:
            quote = _quote(token_in, token_out, amount)
            quote_config = str(quote.get("amm_config_address") or "")
            self.assertTrue(quote_config, quote)

            matched_candidates = []
            for candidate in candidates:
                pool = _decode_pool(candidate["pool"])
                if pool["amm_config"] != quote_config:
                    continue
                config = _decode_config(pool["amm_config"])
                r0, r1 = _active_reserves(pool)
                by_mint = {
                    pool["mint_0"]: (r0, pool["decimals_0"]),
                    pool["mint_1"]: (r1, pool["decimals_1"]),
                }
                if token_in not in by_mint or token_out not in by_mint:
                    continue
                reserve_in, decimals_in = by_mint[token_in]
                reserve_out, decimals_out = by_mint[token_out]
                raw_input = _raw_amount(amount, decimals_in)
                cp_config = _curve_exact_in(raw_input, reserve_in, reserve_out, config["trade_fee_rate"])
                cp_plus_200 = _curve_exact_in(
                    raw_input,
                    reserve_in,
                    reserve_out,
                    config["trade_fee_rate"] + EXTRA_CANDIDATE_RATE,
                )
                observed_dec = Decimal(str(quote["outputAmount"])) * (Decimal(10) ** decimals_out)
                if observed_dec != observed_dec.to_integral_value():
                    continue
                observed = int(observed_dec)
                row = {
                    "pool": pool["pool"],
                    "direction": f"{token_in[:6]}->{token_out[:6]}",
                    "amount": str(amount),
                    "amm_config": pool["amm_config"],
                    "trade_fee_rate_ppm": config["trade_fee_rate"],
                    "protocol_fee_rate_raw": config["protocol_fee_rate"],
                    "fund_fee_rate_raw": config["fund_fee_rate"],
                    "creator_fee_rate_raw": config["creator_fee_rate"],
                    "observed_zero_slippage_raw": observed,
                    "cp_config_fee_raw": cp_config,
                    "cp_config_plus_200_raw": cp_plus_200,
                    "delta_config_raw": observed - cp_config,
                    "delta_config_plus_200_raw": observed - cp_plus_200,
                }
                matched_candidates.append(row)
                if observed == cp_plus_200:
                    exact_plus_200_matches += 1
            evidence.extend(matched_candidates)

        print("XDEX second-pool effective-fee evidence")
        for row in evidence:
            print(row)

        self.assertTrue(evidence, "No discovered XNT/USDC.X pool matched quote AMM config")
        # At least one direction/pool must reproduce the live quote exactly under
        # config trade-fee rate + 200 ppm before we treat the second market as
        # corroborating evidence. This still does not assign a business label.
        self.assertGreaterEqual(
            exact_plus_200_matches,
            1,
            "No XNT/USDC.X quote exactly matched config trade fee + 200 ppm",
        )


if __name__ == "__main__":
    unittest.main()
