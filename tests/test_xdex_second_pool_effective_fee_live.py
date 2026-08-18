import base64
import os
import struct
import unittest
from collections import Counter
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
KNOWN_CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
POOL_SIZE = 637
FEE_DENOM = 1_000_000
OBSERVED_QUOTE_BASELINE_RATE = 3_000  # arithmetic behavior, not a fee label.
MAX_DIFFERENT_CONFIG_TOKEN_PROBES = 12


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


def _program_rows(filters):
    result = rpc_request(
        "getProgramAccounts",
        [
            PROGRAM,
            {
                "encoding": "base64",
                "commitment": "confirmed",
                "filters": filters,
            },
        ],
    )
    rows = result.get("value") if isinstance(result, dict) and "value" in result else result
    return rows if isinstance(rows, list) else []


def _decode_program_row(row):
    if not isinstance(row, dict) or not row.get("pubkey"):
        return None
    account = row.get("account") or {}
    raw = account.get("data")
    encoded = raw[0] if isinstance(raw, list) and raw else None
    if not isinstance(encoded, str):
        return None
    try:
        data = base64.b64decode(encoded)
    except Exception:
        return None
    if len(data) != POOL_SIZE:
        return None
    return {
        "pool": str(row["pubkey"]),
        "mint_0": _pubkey(data, 168),
        "mint_1": _pubkey(data, 200),
        "amm_config": _pubkey(data, 8),
    }


def _rpc_pair_rows(mint_0, mint_1):
    return _program_rows(
        [
            {"dataSize": POOL_SIZE},
            {"memcmp": {"offset": 168, "bytes": mint_0}},
            {"memcmp": {"offset": 200, "bytes": mint_1}},
        ]
    )


def _discover_pair_pools():
    discovered = {}
    for mint_0, mint_1 in ((USDC_X, XNT), (XNT, USDC_X)):
        for row in _rpc_pair_rows(mint_0, mint_1):
            decoded = _decode_program_row(row)
            if not decoded:
                continue
            if decoded["mint_0"] != mint_0 or decoded["mint_1"] != mint_1:
                continue
            discovered[decoded["pool"]] = decoded
    return list(discovered.values())


def _discover_xnt_pools():
    discovered = {}
    for offset in (168, 200):
        rows = _program_rows(
            [
                {"dataSize": POOL_SIZE},
                {"memcmp": {"offset": offset, "bytes": XNT}},
            ]
        )
        for row in rows:
            decoded = _decode_program_row(row)
            if not decoded or XNT not in {decoded["mint_0"], decoded["mint_1"]}:
                continue
            discovered[decoded["pool"]] = decoded
    return list(discovered.values())


def _discover_all_637_pool_candidates():
    discovered = {}
    for row in _program_rows([{"dataSize": POOL_SIZE}]):
        decoded = _decode_program_row(row)
        if decoded:
            discovered[decoded["pool"]] = decoded
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
    if r0 <= 0 or r1 <= 0:
        raise AssertionError(f"non-positive active reserves for {pool['pool']}")
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
    if response.status_code >= 400:
        return None
    try:
        body = response.json()
    except Exception:
        return None
    if not isinstance(body, dict) or body.get("success") is not True or not isinstance(body.get("data"), dict):
        return None
    return body["data"]


def _evaluate_pool_quote(pool, config, quote, token_in, token_out, amount):
    r0, r1 = _active_reserves(pool)
    by_mint = {
        pool["mint_0"]: (r0, pool["decimals_0"]),
        pool["mint_1"]: (r1, pool["decimals_1"]),
    }
    reserve_in, decimals_in = by_mint[token_in]
    reserve_out, decimals_out = by_mint[token_out]
    raw_input = _raw_amount(amount, decimals_in)
    cp_config = _curve_exact_in(raw_input, reserve_in, reserve_out, config["trade_fee_rate"])
    cp_baseline = _curve_exact_in(
        raw_input,
        reserve_in,
        reserve_out,
        max(config["trade_fee_rate"], OBSERVED_QUOTE_BASELINE_RATE),
    )
    observed_dec = Decimal(str(quote["outputAmount"])) * (Decimal(10) ** decimals_out)
    if observed_dec != observed_dec.to_integral_value():
        return None
    observed = int(observed_dec)
    return {
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
        "cp_tested_3000_baseline_raw": cp_baseline,
        "delta_config_raw": observed - cp_config,
        "delta_tested_3000_baseline_raw": observed - cp_baseline,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 for second-pool effective-fee evidence",
)
class XDEXSecondPoolEffectiveFeeLiveTests(unittest.TestCase):
    def test_xnt_usdc_pool_localizes_3000_ppm_quote_baseline(self):
        candidates = _discover_pair_pools()
        self.assertTrue(candidates, "X1 RPC found no 637-byte XDEX XNT/USDC.X pool")
        print("XDEX XNT/USDC.X discovered pool candidates", candidates)

        quote_cases = (
            (USDC_X, XNT, Decimal("1")),
            (XNT, USDC_X, Decimal("0.1")),
        )
        evidence = []

        for token_in, token_out, amount in quote_cases:
            quote = _quote(token_in, token_out, amount)
            self.assertIsNotNone(quote, f"XDEX returned no quote for {token_in}->{token_out}")
            quote_config = str(quote.get("amm_config_address") or "")
            self.assertTrue(quote_config, quote)

            for candidate in candidates:
                pool = _decode_pool(candidate["pool"])
                if pool["amm_config"] != quote_config:
                    continue
                config = _decode_config(pool["amm_config"])
                row = _evaluate_pool_quote(pool, config, quote, token_in, token_out, amount)
                if row:
                    evidence.append(row)

        print("XDEX second-pool effective-fee evidence")
        for row in evidence:
            print(row)

        self.assertTrue(evidence, "No discovered XNT/USDC.X pool matched quote AMM config")
        self.assertTrue(
            all(row["delta_tested_3000_baseline_raw"] == 0 for row in evidence),
            "XNT/USDC.X zero-slippage quote stopped matching the tested 3000-ppm baseline",
        )

    def test_different_3000_ppm_config_uses_its_config_rate_without_extra_200_ppm(self):
        pools = _discover_xnt_pools()
        different = [p for p in pools if p["amm_config"] != KNOWN_CONFIG]
        self.assertTrue(different, "No XNT pool with a different AMM config was discovered")

        by_other_mint = {}
        for candidate in different:
            other = candidate["mint_1"] if candidate["mint_0"] == XNT else candidate["mint_0"]
            by_other_mint.setdefault(other, []).append(candidate)

        diagnostics = []
        corroborated = []
        for other_mint, candidates in list(by_other_mint.items())[:MAX_DIFFERENT_CONFIG_TOKEN_PROBES]:
            quote = _quote(XNT, other_mint, Decimal("0.01"))
            if not quote:
                diagnostics.append({"other_mint": other_mint, "quote": "unavailable"})
                continue
            selected_config = str(quote.get("amm_config_address") or "")
            diagnostics.append(
                {
                    "other_mint": other_mint,
                    "selected_config": selected_config,
                    "candidate_configs": sorted({c["amm_config"] for c in candidates}),
                }
            )
            if not selected_config or selected_config == KNOWN_CONFIG:
                continue

            for candidate in candidates:
                if candidate["amm_config"] != selected_config:
                    continue
                try:
                    pool = _decode_pool(candidate["pool"])
                    config = _decode_config(selected_config)
                    row = _evaluate_pool_quote(
                        pool,
                        config,
                        quote,
                        XNT,
                        other_mint,
                        Decimal("0.01"),
                    )
                except Exception as exc:
                    diagnostics.append(
                        {
                            "pool": candidate["pool"],
                            "selected_config": selected_config,
                            "evaluation_error": str(exc),
                        }
                    )
                    continue
                if row:
                    corroborated.append(row)
                    if row["delta_config_raw"] == 0:
                        break
            if any(row["delta_config_raw"] == 0 for row in corroborated):
                break

        print("XDEX different-config discovery diagnostics")
        for row in diagnostics:
            print(row)
        print("XDEX different-config effective-fee evidence")
        for row in corroborated:
            print(row)

        self.assertTrue(
            corroborated,
            "No live XNT quote selected a structurally discovered pool under a different AMM config",
        )
        self.assertTrue(
            any(
                row["trade_fee_rate_ppm"] == OBSERVED_QUOTE_BASELINE_RATE
                and abs(row["delta_config_raw"]) <= 1
                for row in corroborated
            ),
            "A different 3000-ppm AMM config did not reproduce the zero-slippage quote at its own config rate",
        )

    def test_inventory_current_637_pool_config_trade_fee_rates(self):
        pools = _discover_all_637_pool_candidates()
        self.assertTrue(pools, "No 637-byte XDEX pool candidates discovered")
        config_addresses = sorted({pool["amm_config"] for pool in pools})
        config_rows = []
        rate_counts = Counter()
        for address in config_addresses:
            config = _decode_config(address)
            rate_counts[config["trade_fee_rate"]] += 1
            config_rows.append({"amm_config": address, **config})

        print("XDEX current 637-byte pool AMM config fee inventory")
        print({"pool_count": len(pools), "config_count": len(config_rows), "trade_fee_rate_counts": dict(rate_counts)})
        for row in config_rows:
            print(row)

        # These rates are part of today's observed inventory, not a claim that
        # future XDEX configs are limited to this set.
        self.assertIn(2_800, rate_counts)
        self.assertIn(3_000, rate_counts)


if __name__ == "__main__":
    unittest.main()
