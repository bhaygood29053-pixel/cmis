import os
import struct
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex_direct_route_discovery import discover_direct_route
from liquidity_scout.providers.x1.xdex_exact_route import collect_exact_route_snapshot
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import XENCAT_MINT, XNT_MINT


USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
FEE_DENOMINATOR = 1_000_000


def _ceil_fee(amount: int, rate_ppm: int) -> int:
    if rate_ppm == 0:
        return 0
    return (amount * rate_ppm + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR


def _impact(raw_input: int, reserve_in: int, fee_ppm: int) -> Decimal:
    net = raw_input - _ceil_fee(raw_input, fee_ppm)
    return Decimal(net) * Decimal(100) / Decimal(reserve_in + net)


def _curve_output(raw_input: int, reserve_in: int, reserve_out: int, fee_ppm: int) -> int:
    net = raw_input - _ceil_fee(raw_input, fee_ppm)
    return net * reserve_out // (reserve_in + net)


def _implied_reserve(raw_input: int, fee_ppm: int, impact_percent: Decimal) -> Decimal:
    net = Decimal(raw_input - _ceil_fee(raw_input, fee_ppm))
    fraction = impact_percent / Decimal(100)
    return net * (Decimal(1) - fraction) / fraction


def _quoted_output_raw(snapshot: dict) -> int:
    scaled = Decimal(str(snapshot["quote_output_amount"])) * (
        Decimal(10) ** int(snapshot["output_decimals"])
    )
    if scaled != scaled.to_integral_value():
        raise AssertionError("quoted output is not exactly representable in raw units")
    return int(scaled)


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _gross_input_evidence(pool_address: str, token_in: str) -> dict:
    state = fetch_account_state(pool_address)
    raw = state["data"]
    mint_0 = _pubkey(raw, 168)
    mint_1 = _pubkey(raw, 200)
    vault_0 = _pubkey(raw, 72)
    vault_1 = _pubkey(raw, 104)
    protocol_0, protocol_1 = _u64(raw, 341), _u64(raw, 349)
    fund_0, fund_1 = _u64(raw, 357), _u64(raw, 365)
    creator_0, creator_1 = _u64(raw, 397), _u64(raw, 405)

    if token_in == mint_0:
        vault = vault_0
        fee_counters = protocol_0 + fund_0 + creator_0
    elif token_in == mint_1:
        vault = vault_1
        fee_counters = protocol_1 + fund_1 + creator_1
    else:
        raise AssertionError("token_in is not present in decoded pool state")

    vault_record = get_token_account_info(vault)
    if not (
        vault_record
        and vault_record.get("identity_verified") is True
        and vault_record.get("mint") == token_in
    ):
        raise AssertionError("gross input vault identity is not verified")
    gross = int(vault_record["raw_amount"])
    return {
        "gross_input_reserve_raw": gross,
        "accrued_fee_counters_input_raw": fee_counters,
        "gross_minus_fee_counters_raw": gross - fee_counters,
    }


@unittest.skipUnless(
    os.getenv("RUN_XDEX_3000_PRICE_IMPACT_DIAGNOSTIC_LIVE") == "1",
    "set RUN_XDEX_3000_PRICE_IMPACT_DIAGNOSTIC_LIVE=1 for read-only diagnostic evidence",
)
class XDEX3000PriceImpactDiagnosticLiveTests(unittest.TestCase):
    def _discover(self, token_in, token_out):
        discovery = discover_direct_route(token_in, token_out)
        self.assertEqual(discovery["status"], "ambiguous")
        self.assertTrue(discovery["candidate_verification_complete"])
        self.assertGreaterEqual(len(discovery["candidates"]), 2)
        return discovery

    @staticmethod
    def _route(candidate, token_in, token_out):
        return {
            "token_in_mint": token_in,
            "token_out_mint": token_out,
            "pool": candidate["pool"],
            "amm_config": candidate["amm_config"],
        }

    def _diagnose_pair(self, token_in, token_out, amount):
        discovery = self._discover(token_in, token_out)
        rows = []
        for candidate in discovery["candidates"]:
            route = self._route(candidate, token_in, token_out)
            snap = collect_exact_route_snapshot(route, amount)
            gross = _gross_input_evidence(route["pool"], token_in)
            provider = Decimal(str(snap["quote_price_impact_percent"]))
            raw_input = int(snap["raw_input_amount"])
            reserve_in = int(snap["active_reserve_in_raw"])
            configured_fee = int(snap["trade_fee_rate_ppm"])
            gross_reserve = gross["gross_input_reserve_raw"]
            active_impact = _impact(raw_input, reserve_in, configured_fee)
            gross_impact = _impact(raw_input, gross_reserve, configured_fee)
            rows.append({
                "pool": route["pool"],
                "amm_config": route["amm_config"],
                "configured_fee_ppm": configured_fee,
                "raw_input": raw_input,
                "active_reserve_in_raw": reserve_in,
                "gross_input_reserve_raw": gross_reserve,
                "accrued_fee_counters_input_raw": gross["accrued_fee_counters_input_raw"],
                "provider_price_impact_pct": str(provider),
                "active_price_impact_pct": str(active_impact),
                "gross_price_impact_pct": str(gross_impact),
                "active_delta_pp": str(abs(provider - active_impact)),
                "gross_delta_pp": str(abs(provider - gross_impact)),
                "implied_reserve_configured_fee": str(
                    _implied_reserve(raw_input, configured_fee, provider)
                ),
                "quote_output_amount": snap["quote_output_amount"],
            })

        print("XDEX active-vs-gross price-impact diagnostic:", rows, flush=True)
        by_fee = {row["configured_fee_ppm"]: row for row in rows}
        self.assertIn(2800, by_fee)
        self.assertIn(3000, by_fee)
        self.assertLessEqual(Decimal(by_fee[2800]["active_delta_pp"]), Decimal("0.001"))
        self.assertGreater(Decimal(by_fee[3000]["active_delta_pp"]), Decimal("0.001"))

    def test_xencat_3000ppm_quote_output_uses_current_thin_pool_math(self):
        discovery = self._discover(XENCAT_MINT, XNT_MINT)
        candidate = next(
            row for row in discovery["candidates"]
            if row["amm_config"] == "ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x"
        )
        route = self._route(candidate, XENCAT_MINT, XNT_MINT)
        evidence = []
        exact_active_matches = 0

        for amount in ("0.001", "0.01", "0.1", "1", "10", "1000"):
            snap = collect_exact_route_snapshot(route, amount)
            raw_input = int(snap["raw_input_amount"])
            reserve_in = int(snap["active_reserve_in_raw"])
            reserve_out = int(snap["active_reserve_out_raw"])
            fee_ppm = int(snap["trade_fee_rate_ppm"])
            quoted_raw = _quoted_output_raw(snap)
            active_curve_raw = _curve_output(raw_input, reserve_in, reserve_out, fee_ppm)
            provider_impact = Decimal(str(snap["quote_price_impact_percent"]))
            implied_reserve = _implied_reserve(raw_input, fee_ppm, provider_impact)
            if quoted_raw == active_curve_raw:
                exact_active_matches += 1
            evidence.append({
                "amount": amount,
                "raw_input": raw_input,
                "active_reserve_in_raw": reserve_in,
                "active_reserve_out_raw": reserve_out,
                "quoted_output_raw": quoted_raw,
                "active_curve_output_raw": active_curve_raw,
                "provider_price_impact_pct": str(provider_impact),
                "active_price_impact_pct": str(_impact(raw_input, reserve_in, fee_ppm)),
                "implied_reserve_from_provider_impact": str(implied_reserve),
            })

        print("XDEX thin-pool output-vs-impact probe:", evidence, flush=True)
        self.assertGreaterEqual(
            exact_active_matches,
            4,
            "config-pinned outputAmount did not consistently follow current active thin-pool CPMM math",
        )

    def test_xencat_xnt_3000ppm_candidate_metadata(self):
        self._diagnose_pair(XENCAT_MINT, XNT_MINT, "1000")

    def test_xnt_usdc_x_3000ppm_candidate_metadata(self):
        self._diagnose_pair(XNT_MINT, USDC_X_MINT, "1")


if __name__ == "__main__":
    unittest.main()
