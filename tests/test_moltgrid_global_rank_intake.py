import unittest
from types import SimpleNamespace

from liquidity_scout.integrations import moltgrid


QUESTION = "Top 10 XDEX tokens by volume"


class MoltGridGlobalRankIntakeTests(unittest.TestCase):
    def _listener(self):
        return SimpleNamespace(
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
            looks_like_general_question=lambda question: str(question).strip().endswith("?"),
            wants_global_xdex_ranking=lambda question: str(question).lower().startswith("top 10 "),
        )

    def test_exact_global_rank_request_is_admitted_as_general_owner_question(self):
        listener = self._listener()

        moltgrid.wire_market_core(listener)

        self.assertTrue(listener.looks_like_general_question(QUESTION))
        self.assertFalse(listener.looks_like_general_question("just a casual statement"))

    def test_intake_wiring_is_idempotent(self):
        listener = self._listener()

        moltgrid.wire_market_core(listener)
        moltgrid.wire_market_core(listener)

        self.assertTrue(listener.looks_like_general_question(QUESTION))
        self.assertTrue(listener.looks_like_general_question("What is DeFi?"))


if __name__ == "__main__":
    unittest.main()
