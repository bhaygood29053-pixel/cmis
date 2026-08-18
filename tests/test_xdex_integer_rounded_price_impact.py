import unittest

from liquidity_scout.cmis.xdex_route_resolver import (
    XDEXRouteResolverError,
    resolve_xdex_route_evidence,
)
from liquidity_scout.providers.x1.xdex_exact_route import SOURCE as COLLECTOR_SOURCE
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM


ROUTE = {
    "token_in_mint": "TOKEN_IN",
    "token_out_mint": "TOKEN_OUT",
    "pool": "DUST_POOL",
    "amm_config": "ALT_CONFIG",
}


def dust_snapshot(**overrides):
    snapshot = {
        "schema": "xdex_exact_route_snapshot.v1",
        "source": COLLECTOR_SOURCE,
        "chain": "x1",
        "program": X1_PROGRAM,
        "route": dict(ROUTE),
        "observed_at": "2026-08-18T23:24:00Z",
        "token_in_amount": "1000",
        "raw_input_amount": 1_000_000_000,
        "input_decimals": 6,
        "output_decimals": 9,
        "active_reserve_in_raw": 180,
        "active_reserve_out_raw": 56,
        "trade_fee_rate_ppm": 3000,
        "protocol_fee_rate_ppm_of_trade_fee": 0,
        "fund_fee_rate_ppm_of_trade_fee": 0,
        "creator_fee_rate_ppm": 0,
        "reconstructed_price_impact_percent": "99.99998194584077206485559511",
        "quote_price_impact_percent": "98.2143",
        "quote_output_amount": "0.000000055",
        "quote_rate": "0.000000000055",
        "quote_slippage_percent": 0,
        "quote_identity_verified": True,
        "pool_state_verified": True,
        "vault_identity_verified": True,
        "active_reserves_verified": True,
        "amm_config_verified": True,
        "read_only": True,
        "execution_authorized": False,
    }
    snapshot.update(overrides)
    return snapshot


class XDEXIntegerRoundedPriceImpactTests(unittest.TestCase):
    def test_dust_pool_quote_impact_uses_integer_rounded_curve_output(self):
        evidence = resolve_xdex_route_evidence(
            ROUTE,
            "1000",
            collector=lambda route, amount: dust_snapshot(),
        )

        self.assertEqual(
            evidence["capabilities"]["price_impact"]["value"],
            98.2143,
        )

    def test_dust_pool_quote_impact_still_fails_outside_existing_tolerance(self):
        with self.assertRaisesRegex(
            XDEXRouteResolverError,
            "does not match independent verified-reserve reconstruction",
        ):
            resolve_xdex_route_evidence(
                ROUTE,
                "1000",
                collector=lambda route, amount: dust_snapshot(
                    quote_price_impact_percent="98.20",
                ),
            )


if __name__ == "__main__":
    unittest.main()
