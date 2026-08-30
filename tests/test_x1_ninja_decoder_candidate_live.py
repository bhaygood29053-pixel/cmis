import json
import os
import unittest

from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw

RUN_LIVE = os.getenv("RUN_X1_NINJA_DECODER_CANDIDATE_LIVE") == "1"
POOL = "42L71tiJR69Y8jDx9jGCivoxMkyS22LVAANeRS7smH5R"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_DECODER_CANDIDATE_LIVE=1 to run read-only evidence",
)
class NinjaDecoderCandidateLiveTests(unittest.TestCase):
    def test_print_recent_decoder_candidates(self):
        observation = fetch_pool_trades_raw(POOL)
        trades = observation["raw_response"].get("trades") or []
        self.assertTrue(trades, "No X1.Ninja trades returned for mismatch pool")
        candidates = []
        for row in trades[:5]:
            candidates.append({
                "txHash": row.get("txHash"),
                "slot": row.get("slot"),
                "timestamp": row.get("timestamp"),
                "type": row.get("type"),
                "poolAddress": row.get("poolAddress"),
                "maker": row.get("maker"),
            })
        print("[X1 decoder candidates] " + json.dumps(candidates, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
