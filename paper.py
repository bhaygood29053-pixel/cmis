import time
from models import Position

class PaperBroker:
    def __init__(self, portfolio):
        self.portfolio = portfolio

    def buy(self, price: float, quote_amount: float):
        if self.portfolio.position is not None:
            raise RuntimeError("Cannot BUY: position already open")
        if price <= 0 or quote_amount <= 0:
            raise ValueError("price and quote_amount must be positive")
        quote_amount = min(quote_amount, self.portfolio.quote_balance)
        qty = quote_amount / price
        self.portfolio.quote_balance -= quote_amount
        self.portfolio.position = Position(qty, price, int(time.time()))
        self.portfolio.trades += 1
        return {
            "side": "BUY",
            "price": price,
            "quantity": qty,
            "quote_amount": quote_amount,
            "realized_pnl": 0.0,
        }

    def sell_all(self, price: float, reason: str):
        pos = self.portfolio.position
        if pos is None:
            raise RuntimeError("Cannot SELL: no open position")
        proceeds = pos.quantity * price
        cost = pos.quantity * pos.entry_price
        pnl = proceeds - cost
        self.portfolio.quote_balance += proceeds
        self.portfolio.realized_pnl += pnl
        if pnl >= 0:
            self.portfolio.wins += 1
        else:
            self.portfolio.losses += 1
        self.portfolio.position = None
        self.portfolio.trades += 1
        return {
            "side": "SELL",
            "price": price,
            "quantity": pos.quantity,
            "quote_amount": proceeds,
            "realized_pnl": pnl,
            "reason": reason,
        }

    def equity(self, price: float):
        value = self.portfolio.quote_balance
        if self.portfolio.position:
            value += self.portfolio.position.quantity * price
        return value
