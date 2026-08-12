import argparse
import shutil
import time
from pathlib import Path

from config import SETTINGS
from agentid import verify_agent
from market import X1NinjaClient, DemoMarket
from strategy import generate_signal
from risk import entry_allowed, exit_reason, trade_budget
from paper import PaperBroker
from journal import (
    DATA_DIR, STATE_PATH, load_portfolio, save_portfolio,
    log_decision, log_trade, queue_hxmp_event,
)
from hxmp_bridge import print_review

def identity_banner():
    if not SETTINGS.agent_wallet:
        print("AgentID: AGENT_WALLET not set (identity check skipped)")
        return
    try:
        result = verify_agent(SETTINGS.agent_wallet)
        print(f"AgentID verified: {result.get('verified', False)}")
    except Exception as exc:
        print(f"AgentID verification error: {exc}")

def print_snapshot(snapshot, signal, broker):
    p = broker.portfolio
    eq = broker.equity(snapshot.price)
    position = "NONE"
    if p.position:
        change = snapshot.price / p.position.entry_price - 1
        position = (
            f"{p.position.quantity:,.4f} {snapshot.base_symbol} "
            f"@ {p.position.entry_price:.10g} ({change:+.2%})"
        )

    print("\n" + "=" * 72)
    print(f"{snapshot.base_symbol}/{snapshot.quote_symbol} | price {snapshot.price:.10g}")
    print(f"Liquidity: ${snapshot.liquidity_usd:,.0f} | 24h volume: ${snapshot.volume_24h:,.0f}")
    print(
        f"Signal: {signal.action} | score {signal.score:+d} | "
        f"heuristic confidence {signal.confidence:.0%}"
    )
    print(f"Reason: {signal.reason}")
    print(
        f"Fast SMA {signal.fast_sma:.10g} | Slow SMA {signal.slow_sma:.10g} | "
        f"Momentum {signal.momentum:+.2%} | Volume {signal.volume_ratio:.2f}x"
    )
    print(f"Position: {position}")
    print(
        f"Paper balance: {p.quote_balance:,.2f} {snapshot.quote_symbol} | "
        f"Equity: {eq:,.2f} {snapshot.quote_symbol} | "
        f"Realized P/L: {p.realized_pnl:+,.2f}"
    )

def run_cycle(feed):
    portfolio = load_portfolio(SETTINGS.starting_quote_balance)
    broker = PaperBroker(portfolio)

    snapshot = feed.snapshot(
        SETTINGS.pool_address,
        SETTINGS.timeframe,
        SETTINGS.candle_limit,
        SETTINGS.base_symbol,
        SETTINGS.quote_symbol,
    )
    signal = generate_signal(snapshot, SETTINGS)
    print_snapshot(snapshot, signal, broker)

    action_taken = "NONE"

    # Hard exits override the strategy.
    forced_exit = exit_reason(snapshot, portfolio, SETTINGS)
    if forced_exit:
        trade = broker.sell_all(snapshot.price, forced_exit)
        log_trade(trade)
        action_taken = forced_exit
        if SETTINGS.hxmp_queue_enabled:
            queue_hxmp_event("PAPER_TRADE_EXIT", {
                "pool": snapshot.pool_address,
                "pair": f"{snapshot.base_symbol}/{snapshot.quote_symbol}",
                "side": "SELL",
                "price": snapshot.price,
                "realized_pnl": trade["realized_pnl"],
                "reason": forced_exit,
            })
        print(f"ACTION: PAPER SELL — {forced_exit}")

    elif signal.action == "BUY":
        allowed, blockers = entry_allowed(snapshot, portfolio, SETTINGS)
        if allowed:
            budget = trade_budget(portfolio, SETTINGS)
            trade = broker.buy(snapshot.price, budget)
            log_trade(trade)
            action_taken = "PAPER_BUY"
            if SETTINGS.hxmp_queue_enabled:
                queue_hxmp_event("PAPER_TRADE_ENTRY", {
                    "pool": snapshot.pool_address,
                    "pair": f"{snapshot.base_symbol}/{snapshot.quote_symbol}",
                    "side": "BUY",
                    "price": snapshot.price,
                    "quote_amount": budget,
                    "strategy_score": signal.score,
                    "reason": signal.reason,
                })
            print(
                f"ACTION: PAPER BUY — {budget:,.2f} {snapshot.quote_symbol} "
                f"for {trade['quantity']:,.4f} {snapshot.base_symbol}"
            )
        else:
            action_taken = "BUY_BLOCKED: " + "; ".join(blockers)
            print("ACTION: BUY BLOCKED — " + "; ".join(blockers))

    elif signal.action == "SELL" and portfolio.position:
        trade = broker.sell_all(snapshot.price, "STRATEGY_SELL")
        log_trade(trade)
        action_taken = "PAPER_SELL"
        if SETTINGS.hxmp_queue_enabled:
            queue_hxmp_event("PAPER_TRADE_EXIT", {
                "pool": snapshot.pool_address,
                "pair": f"{snapshot.base_symbol}/{snapshot.quote_symbol}",
                "side": "SELL",
                "price": snapshot.price,
                "realized_pnl": trade["realized_pnl"],
                "reason": signal.reason,
            })
        print(f"ACTION: PAPER SELL — realized P/L {trade['realized_pnl']:+,.2f}")

    else:
        print("ACTION: HOLD")

    equity = broker.equity(snapshot.price)
    log_decision(snapshot, signal, equity, action_taken)
    save_portfolio(portfolio)

def reset():
    for path in [
        STATE_PATH,
        DATA_DIR / "trades.csv",
        DATA_DIR / "decisions.jsonl",
        DATA_DIR / "hxmp_queue.jsonl",
    ]:
        if path.exists():
            path.unlink()
    print("Paper state reset.")

def main():
    parser = argparse.ArgumentParser(description="Liquidity Scout Trader v0.1")
    parser.add_argument("--demo", action="store_true", help="Use synthetic market data.")
    parser.add_argument("--loop", action="store_true", help="Repeat every POLL_SECONDS.")
    parser.add_argument("--reset", action="store_true", help="Reset paper portfolio and journals.")
    parser.add_argument("--hxmp-review", action="store_true", help="Show queued HXMP-ready events.")
    args = parser.parse_args()

    if args.reset:
        reset()
        return
    if args.hxmp_review:
        print_review()
        return

    identity_banner()

    if args.demo:
        feed = DemoMarket()
        print("Market feed: DEMO (synthetic data)")
    else:
        feed = X1NinjaClient(
            SETTINGS.api_key,
            SETTINGS.rpc_url,
            SETTINGS.base_token_vault,
            SETTINGS.quote_token_vault,
        )
        print("Market feed: X1.Ninja signals + X1 RPC reserve price")

    if args.loop:
        while True:
            try:
                run_cycle(feed)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            except Exception as exc:
                print(f"Cycle error: {exc}")
            time.sleep(SETTINGS.poll_seconds)
    else:
        run_cycle(feed)

if __name__ == "__main__":
    main()
