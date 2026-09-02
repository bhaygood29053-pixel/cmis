import json
import os
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
from liquidity_scout.providers.x1.xdex_pool_open_time_semantics import (
    BAR_INTERVAL_SECONDS,
    evaluate_xdex_pool_open_time_semantics,
)
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_POOL_INCEPTION_LIVE") == "1"
POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
PROGRAM = XDEX_MAINNET_OBSERVED_PROGRAM_ID

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
    def test_pool_open_time_semantics_and_first_bar_anchor(self):
        structural = verify_candidate_pool_role(
            account=POOL,
            target_mint=WRAPPED_XNT_MINT,
            program_id=PROGRAM,
            signature_limit=1,
        )
        state = fetch_account_state(POOL)
        provider = _provider_first_bar()

        semantic = evaluate_xdex_pool_open_time_semantics(
            state,
            structural,
            provider,
            asset_mint=WRAPPED_XNT_MINT,
            quote_mint=USDC_X_MINT,
        )

        open_time = semantic.get("open_time")
        first_bar = semantic.get("provider_first_bar_start")
        first_bar_end = semantic.get("provider_first_bar_interval_end")

        evidence = {
            "schema": "xdex_xnt_pool_inception_anchor_live.v4",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "pool": POOL,
            "program": PROGRAM,
            "pool_state_response_integrity_verified": (
                state.get("response_integrity_verified") is True
            ),
            "pool_state_structural_role_verified": semantic.get(
                "pool_state_structural_role_verified"
            ),
            "exact_pair_identity_verified": semantic.get(
                "exact_pair_identity_verified"
            ),
            "open_time": open_time,
            "open_time_utc": _iso(open_time),
            "open_time_semantics_verified": semantic.get(
                "open_time_semantics_verified"
            ),
            "source_semantics_verified": semantic.get(
                "source_semantics_verified"
            ),
            "provider_first_bar": provider,
            "provider_bar_interval_seconds": BAR_INTERVAL_SECONDS,
            "provider_first_bar_interval_end": first_bar_end,
            "provider_first_bar_interval_end_utc": _iso(first_bar_end),
            "provider_bar_start_precedes_open_time_seconds": (
                open_time - first_bar
                if isinstance(open_time, int) and isinstance(first_bar, int)
                else None
            ),
            "provider_first_bar_covers_swap_open": semantic.get(
                "provider_first_bar_covers_swap_open"
            ),
            "lifetime_start_anchor": semantic.get("lifetime_start_anchor"),
            "asset_lifetime_start_verified": semantic.get(
                "lifetime_start_anchor_verified"
            ),
            "provider_range_complete_verified": False,
            "archive_exhaustion_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "limitations": semantic.get("limitations"),
        }

        print("XDEX XNT POOL INCEPTION ANCHOR EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(semantic["open_time_semantics_verified"])
        self.assertTrue(semantic["provider_first_bar_covers_swap_open"])
        self.assertTrue(semantic["lifetime_start_anchor_verified"])
        self.assertFalse(semantic["full_asset_lifetime_verified"])
        self.assertFalse(semantic["continuous_coverage_verified"])


if __name__ == "__main__":
    unittest.main()
