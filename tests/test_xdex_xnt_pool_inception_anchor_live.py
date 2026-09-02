import json
import os
import struct
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.pool_state_fingerprint import (
    fetch_account_state,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)
from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_POOL_INCEPTION_LIVE") == "1"
POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
PROGRAM = XDEX_MAINNET_OBSERVED_PROGRAM_ID

# Exact 637-byte pool-state offsets already used by the repository XDEX parser.
# The field names are still candidate semantics here until independently proved.
OPEN_TIME_OFFSET = 373
RECENT_EPOCH_OFFSET = 381
BAR_INTERVAL_SECONDS = 60

# Boundary discovered by the accepted read-only history-boundary probe.
BOUNDARY_SEARCH_FROM = 1767238740
BOUNDARY_SEARCH_TO = 1767411540


def _iso(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _provider_first_bar():
    rows = fetch_price_history(
        WRAPPED_XNT_MINT,
        USDC_X_MINT,
        time_from=BOUNDARY_SEARCH_FROM,
        time_to=BOUNDARY_SEARCH_TO,
    )
    timestamps = sorted(
        row["t"]
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("t"), int)
        and not isinstance(row.get("t"), bool)
    )
    return {
        "returned_count": len(rows),
        "first_observed_at": timestamps[0] if timestamps else None,
        "first_observed_at_utc": _iso(timestamps[0]) if timestamps else None,
        "last_observed_at": timestamps[-1] if timestamps else None,
        "last_observed_at_utc": _iso(timestamps[-1]) if timestamps else None,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_POOL_INCEPTION_LIVE=1 to run read-only XNT pool inception evidence",
)
class XDEXXNTPoolInceptionAnchorLiveTests(unittest.TestCase):
    def test_pool_state_time_candidate_against_provider_first_bar(self):
        structural = verify_candidate_pool_role(
            account=POOL,
            target_mint=WRAPPED_XNT_MINT,
            program_id=PROGRAM,
            signature_limit=1,
        )
        summary = structural.get("summary") or {}
        decoded = structural.get("decoded_state") or {}

        self.assertTrue(summary.get("pool_state_structural_role_verified"))
        self.assertEqual(
            {decoded.get("mint_0"), decoded.get("mint_1")},
            {WRAPPED_XNT_MINT, USDC_X_MINT},
        )

        state = fetch_account_state(POOL)
        data = state.get("data")
        self.assertTrue(state.get("response_integrity_verified"))
        self.assertEqual(state.get("owner"), PROGRAM)
        self.assertIsInstance(data, bytes)
        self.assertEqual(len(data), 637)

        open_time_candidate = struct.unpack_from(
            "<Q", data, OPEN_TIME_OFFSET
        )[0]
        recent_epoch_candidate = struct.unpack_from(
            "<Q", data, RECENT_EPOCH_OFFSET
        )[0]

        # Plausibility only. This does not promote the field name/meaning.
        self.assertGreater(open_time_candidate, 1_600_000_000)
        self.assertLess(open_time_candidate, 2_000_000_000)

        provider = _provider_first_bar()
        provider_first = provider.get("first_observed_at")
        self.assertIsNotNone(provider_first)

        first_interval_end = provider_first + BAR_INTERVAL_SECONDS
        open_time_in_first_provider_bar_interval = bool(
            provider_first
            <= open_time_candidate
            < first_interval_end
        )
        provider_bar_start_precedes_open_time_seconds = (
            open_time_candidate - provider_first
        )

        evidence = {
            "schema": "xdex_xnt_pool_inception_anchor_live.v3",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "pool": POOL,
            "program": PROGRAM,
            "current_pool_structure_verified": True,
            "pool_state_response_integrity_verified": (
                state.get("response_integrity_verified") is True
            ),
            "pool_state_data_length": len(data),
            "open_time_candidate_offset": OPEN_TIME_OFFSET,
            "open_time_candidate": open_time_candidate,
            "open_time_candidate_utc": _iso(open_time_candidate),
            "open_time_semantics_verified": False,
            "recent_epoch_candidate_offset": RECENT_EPOCH_OFFSET,
            "recent_epoch_candidate": recent_epoch_candidate,
            "provider_boundary_search_from": BOUNDARY_SEARCH_FROM,
            "provider_boundary_search_to": BOUNDARY_SEARCH_TO,
            "provider_first_bar": provider,
            "provider_bar_interval_seconds": BAR_INTERVAL_SECONDS,
            "provider_first_bar_interval_end": first_interval_end,
            "provider_first_bar_interval_end_utc": _iso(first_interval_end),
            "provider_bar_start_precedes_open_time_seconds": (
                provider_bar_start_precedes_open_time_seconds
            ),
            "open_time_candidate_in_provider_boundary_bracket": (
                BOUNDARY_SEARCH_FROM
                <= open_time_candidate
                <= BOUNDARY_SEARCH_TO
            ),
            "open_time_candidate_in_first_provider_bar_interval": (
                open_time_in_first_provider_bar_interval
            ),
            "rpc_history_exhaustion_required_for_this_probe": False,
            "first_verified_supported_market_observation": None,
            "asset_lifetime_start_verified": False,
            "provider_range_complete_verified": False,
            "archive_exhaustion_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
        }

        print("XDEX XNT POOL INCEPTION ANCHOR EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        # A one-minute OHLC bar is timestamped at its interval boundary. The
        # pool-time candidate may therefore fall after the bar timestamp while
        # still belonging to the first observed market interval.
        self.assertTrue(open_time_in_first_provider_bar_interval)


if __name__ == "__main__":
    unittest.main()
