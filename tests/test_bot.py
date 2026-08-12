import unittest
from types import SimpleNamespace

from models import Candle, MarketSnapshot, Portfolio
from strategy import generate_signal
from paper import PaperBroker

class StrategyTests(unittest.TestCase):
    def settings(self):
        return SimpleNamespace(
            fast_sma=3,
            slow_sma=5,
            momentum_lookback=2,
            buy_score=3,
            sell_score=-2,
            volume_spike_ratio=1.5,
        )

    def snapshot(self, closes, volumes):
        candles = [
            Candle(i, c, c, c, c, v)
            for i, (c, v) in enumerate(zip(closes, volumes))
        ]
        return MarketSnapshot("pool", "AGI", "XNT", closes[-1], 100000, 50000, candles)

    def test_bullish_signal(self):
        s = self.snapshot(
            [1.00, 1.00, 1.01, 1.02, 1.05, 1.09],
            [100, 100, 100, 100, 100, 300],
        )
        sig = generate_signal(s, self.settings())
        self.assertEqual(sig.action, "BUY")
        self.assertGreaterEqual(sig.score, 3)

    def test_paper_round_trip(self):
        p = Portfolio(quote_balance=1000)
        broker = PaperBroker(p)
        broker.buy(2.0, 100)
        trade = broker.sell_all(2.2, "TEST")
        self.assertAlmostEqual(trade["realized_pnl"], 10.0, places=6)
        self.assertAlmostEqual(p.quote_balance, 1010.0, places=6)

if __name__ == "__main__":
    unittest.main()
