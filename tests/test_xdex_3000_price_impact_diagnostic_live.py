import os
import unittest
from decimal import Decimal

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
            provider = Decimal(str(snap["quote_price_impact_percent"]))
            raw_input = int(snap["raw_input_amount"])
            reserve_in = int(snap["active_reserve_in_raw"])
            configured_fee = int(snap["trade_fee_rate_ppm"])
            row = {
                "pool": route["pool"],
                "amm_config": route["amm_config"],
                "configured_fee_ppm": configured_fee,
                "raw_input": raw_input,
                "active_reserve_in_raw": reserve_in,
                "active_reserve_out_raw": int(snap["active_reserve_out_raw"]),
                "input_decimals": int(snap["input_decimals"]),
                "output_decimals": int(snap["output_decimals"]),
                "provider_price_impact_pct": provider,
                "snapshot_reconstructed_pct": Decimal(str(snap["reconstructed_price_impact_percent"])),
                "impact_if_fee_0": _impact(raw_input, reserve_in, 0),
                "impact_if_fee_2800": _impact(raw_input, reserve_in, 2800),
                "impact_if_fee_3000": _impact(raw_input, reserve_in, 3000),
                "implied_reserve_configured_fee": _implied_reserve(raw_input, configured_fee, provider),
                "quote_output_amount": snap["quote_output_amount"],
                "quote_rate": snap["quote_rate"],
            }
            snapshots.append(row)

        # Cross-match each provider priceImpactPct against every candidate reserve
        # under both observed config-fee hypotheses. This can reveal whether quote
        # metadata is accidentally describing another pool while outputAmount is
        # config-pinned.
        for row in snapshots:
            cross = []
            for reserve_row in snapshots:
                for fee in (0, 2800, 3000):
                    predicted = _impact(row["raw_input"], reserve_row["active_reserve_in_raw"], fee)
                    cross.append({
                        "reserve_pool": reserve_row["pool"],
                        "fee_ppm": fee,
                        "predicted_pct": str(predicted),
                        "delta_pp": str(abs(row["provider_price_impact_pct"] - predicted)),
                    })
            cross.sort(key=lambda item: Decimal(item["delta_pp"]))
            row["closest_cross_matches"] = cross[:4]

        printable = []
        for row in snapshots:
            printable.append({
                **row,
                "provider_price_impact_pct": str(row["provider_price_impact_pct"]),
                "snapshot_reconstructed_pct": str(row["snapshot_reconstructed_pct"]),
                "impact_if_fee_0": str(row["impact_if_fee_0"]),
                "impact_if_fee_2800": str(row["impact_if_fee_2800"]),
                "impact_if_fee_3000": str(row["impact_if_fee_3000"]),
                "implied_reserve_configured_fee": str(row["implied_reserve_configured_fee"]),
            })
        print("XDEX 3000ppm price-impact diagnostic:", printable, flush=True)

        # Diagnostic safety assertion only: preserve the observed split until a
        # semantic explanation is proven. Do not weaken the production resolver.
        by_fee = {row["configured_fee_ppm"]: row for row in snapshots}
        self.assertIn(2800, by_fee)
        self.assertIn(3000, by_fee)
        self.assertLessEqual(
            abs(by_fee[2800]["provider_price_impact_pct"] - by_fee[2800]["snapshot_reconstructed_pct"]),
            Decimal("0.001"),
        )
        self.assertGreater(
            abs(by_fee[3000]["provider_price_impact_pct"] - by_fee[3000]["snapshot_reconstructed_pct"]),
            Decimal("0.001"),
        )

    def test_xencat_xnt_3000ppm_candidate_metadata(self):
        self._diagnose_pair(XENCAT_MINT, XNT_MINT, "1000")

    def test_xnt_usdc_x_3000ppm_candidate_metadata(self):
        self._diagnose_pair(XNT_MINT, USDC_X_MINT, "1")


if __name__ == "__main__":
    unittest.main()
