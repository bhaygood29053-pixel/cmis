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


def _implied_reserve(raw_input: int, fee_ppm: int, impact_percent: Decimal) -> Decimal:
    net = Decimal(raw_input - _ceil_fee(raw_input, fee_ppm))
    fraction = impact_percent / Decimal(100)
    return net * (Decimal(1) - fraction) / fraction


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
    self_verified = bool(
        vault_record
        and vault_record.get("identity_verified") is True
        and vault_record.get("mint") == token_in
    )
    if not self_verified:
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
    def _diagnose_pair(self, token_in, token_out, amount):
        discovery = discover_direct_route(token_in, token_out)
        self.assertEqual(discovery["status"], "ambiguous")
        self.assertTrue(discovery["candidate_verification_complete"])
        self.assertGreaterEqual(len(discovery["candidates"]), 2)

        snapshots = []
        for candidate in discovery["candidates"]:
            route = {
                "token_in_mint": token_in,
                "token_out_mint": token_out,
                "pool": candidate["pool"],
                "amm_config": candidate["amm_config"],
            }
            snap = collect_exact_route_snapshot(route, amount)
            gross = _gross_input_evidence(route["pool"], token_in)
            provider = Decimal(str(snap["quote_price_impact_percent"]))
            raw_input = int(snap["raw_input_amount"])
            reserve_in = int(snap["active_reserve_in_raw"])
            configured_fee = int(snap["trade_fee_rate_ppm"])
            gross_reserve = gross["gross_input_reserve_raw"]
            row = {
                "pool": route["pool"],
                "amm_config": route["amm_config"],
                "configured_fee_ppm": configured_fee,
                "raw_input": raw_input,
                "active_reserve_in_raw": reserve_in,
                "gross_input_reserve_raw": gross_reserve,
                "accrued_fee_counters_input_raw": gross["accrued_fee_counters_input_raw"],
                "gross_minus_fee_counters_raw": gross["gross_minus_fee_counters_raw"],
                "active_reserve_out_raw": int(snap["active_reserve_out_raw"]),
                "input_decimals": int(snap["input_decimals"]),
                "output_decimals": int(snap["output_decimals"]),
                "provider_price_impact_pct": provider,
                "snapshot_reconstructed_pct": Decimal(str(snap["reconstructed_price_impact_percent"])),
                "impact_active_config_fee": _impact(raw_input, reserve_in, configured_fee),
                "impact_gross_config_fee": _impact(raw_input, gross_reserve, configured_fee),
                "impact_gross_fee_0": _impact(raw_input, gross_reserve, 0),
                "impact_gross_fee_2800": _impact(raw_input, gross_reserve, 2800),
                "impact_gross_fee_3000": _impact(raw_input, gross_reserve, 3000),
                "implied_reserve_configured_fee": _implied_reserve(raw_input, configured_fee, provider),
                "quote_output_amount": snap["quote_output_amount"],
                "quote_rate": snap["quote_rate"],
            }
            row["active_delta_pp"] = abs(provider - row["impact_active_config_fee"])
            row["gross_delta_pp"] = abs(provider - row["impact_gross_config_fee"])
            snapshots.append(row)

        printable = []
        for row in snapshots:
            printable.append({
                **row,
                "provider_price_impact_pct": str(row["provider_price_impact_pct"]),
                "snapshot_reconstructed_pct": str(row["snapshot_reconstructed_pct"]),
                "impact_active_config_fee": str(row["impact_active_config_fee"]),
                "impact_gross_config_fee": str(row["impact_gross_config_fee"]),
                "impact_gross_fee_0": str(row["impact_gross_fee_0"]),
                "impact_gross_fee_2800": str(row["impact_gross_fee_2800"]),
                "impact_gross_fee_3000": str(row["impact_gross_fee_3000"]),
                "implied_reserve_configured_fee": str(row["implied_reserve_configured_fee"]),
                "active_delta_pp": str(row["active_delta_pp"]),
                "gross_delta_pp": str(row["gross_delta_pp"]),
            })
        print("XDEX gross-vs-active price-impact diagnostic:", printable, flush=True)

        by_fee = {row["configured_fee_ppm"]: row for row in snapshots}
        self.assertIn(2800, by_fee)
        self.assertIn(3000, by_fee)
        self.assertEqual(
            by_fee[3000]["gross_minus_fee_counters_raw"],
            by_fee[3000]["active_reserve_in_raw"],
        )
        self.assertGreater(by_fee[3000]["active_delta_pp"], Decimal("0.001"))
        self.assertLess(
            by_fee[3000]["gross_delta_pp"],
            by_fee[3000]["active_delta_pp"],
            "gross-vault hypothesis did not improve the 3000ppm price-impact match",
        )

    def test_xencat_xnt_3000ppm_candidate_metadata(self):
        self._diagnose_pair(XENCAT_MINT, XNT_MINT, "1000")

    def test_xnt_usdc_x_3000ppm_candidate_metadata(self):
        self._diagnose_pair(XNT_MINT, USDC_X_MINT, "1")


if __name__ == "__main__":
    unittest.main()
