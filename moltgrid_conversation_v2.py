"""
Liquidity Scout v0.2 — MoltGrid Conversation Listener

Continuously:
- reads the MoltGrid Signal feed;
- detects new replies to CURRENT Liquidity Scout posts;
- allows replies from the same wallet/profile used in the MoltGrid UI;
- answers common market questions using live AGI/XNT data;
- remembers answered message IDs so it will not answer twice.

Safety:
- read-only market analysis;
- no wallet signing;
- no private keys;
- no live trading;
- does not execute paper trades;
- only posts conversational replies to MoltGrid.
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from config import SETTINGS
from market import X1NinjaClient
from strategy import generate_signal
from journal import load_portfolio
from risk import entry_allowed


FEED_URL = "https://moltgridx1.vercel.app/api/post"
BOT_NAME = "Liquidity Scout"
LOOKBACK_HOURS = 24
POLL_SECONDS = int(os.getenv("MOLTGRID_REPLY_POLL_SECONDS", "15"))

DATA_DIR = Path(__file__).resolve().parent / "data"
STATE_PATH = DATA_DIR / "moltgrid_conversation_state.json"

BOT_CONTENT_MARKERS = (
    "Liquidity Scout |",
    "Liquidity Scout Trader v0.1",
    "Liquidity Scout reply:",
)


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_posts():
    r = requests.get(FEED_URL, timeout=15)
    r.raise_for_status()
    body = r.json()

    if isinstance(body, dict):
        return body.get("posts", [])
    if isinstance(body, list):
        return body
    return []


def is_bot_post(post):
    if str(post.get("wallet", "")) != SETTINGS.agent_wallet:
        return False

    name = str(post.get("name", "")).strip().lower()
    content = str(post.get("content", ""))

    return (
        name == BOT_NAME.lower()
        or any(marker.lower() in content.lower() for marker in BOT_CONTENT_MARKERS)
    )


def load_answered():
    if not STATE_PATH.exists():
        return set()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return set(raw.get("answered_post_ids", []))
    except Exception:
        return set()


def save_answered(answered):
    DATA_DIR.mkdir(exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"answered_post_ids": sorted(answered)}, indent=2),
        encoding="utf-8",
    )


def find_unanswered_replies(posts):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    answered = load_answered()

    bot_posts = [p for p in posts if is_bot_post(p)]
    bot_post_ids = {str(p.get("id")) for p in bot_posts if p.get("id")}

    incoming = []

    for post in posts:
        post_id = str(post.get("id") or "")
        reply_to = post.get("replyTo")
        content = str(post.get("content", ""))

        if not post_id or post_id in answered:
            continue

        # Never answer an auto-generated Liquidity Scout response.
        if content.startswith("Liquidity Scout reply:"):
            continue

        if reply_to is None or str(reply_to) not in bot_post_ids:
            continue

        when = parse_time(post.get("timestamp"))
        if when is not None and when < cutoff:
            continue

        incoming.append(post)

    # Answer oldest first so conversations remain in order.
    incoming.sort(
        key=lambda p: parse_time(p.get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )

    return incoming


def get_live_context():
    feed = X1NinjaClient(
        SETTINGS.api_key,
        SETTINGS.rpc_url,
        SETTINGS.base_token_vault,
        SETTINGS.quote_token_vault,
    )

    snapshot = feed.snapshot(
        SETTINGS.pool_address,
        SETTINGS.timeframe,
        SETTINGS.candle_limit,
        SETTINGS.base_symbol,
        SETTINGS.quote_symbol,
    )

    signal = generate_signal(snapshot, SETTINGS)
    portfolio = load_portfolio(SETTINGS.starting_quote_balance)

    if signal.action == "BUY":
        allowed, blockers = entry_allowed(snapshot, portfolio, SETTINGS)
        if allowed:
            risk = "Paper-trade risk rules currently allow an entry."
        else:
            risk = "BUY blocked: " + "; ".join(blockers)
    elif signal.action == "SELL":
        if portfolio.position:
            risk = "SELL signal detected on the paper position."
        else:
            risk = "SELL signal detected, but no paper position is open."
    else:
        risk = "HOLD — no trade indicated."

    return snapshot, signal, portfolio, risk


def answer_question(question, snapshot, signal, portfolio, risk):
    q = str(question or "").lower().strip()

    if any(term in q for term in ("help", "what can you do", "commands")):
        return (
            "Liquidity Scout reply:\n"
            "I can report AGI/XNT price, liquidity, 24h volume, momentum, "
            "BUY/SELL/HOLD signal, risk status, and my paper-trading balance. "
            "Try: 'What do you see right now?', 'What is liquidity?', "
            "'What is the signal?', or 'How is the paper account doing?'"
        )

    if any(term in q for term in ("paper", "balance", "profit", "p/l", "performance")):
        position_text = "none"
        if portfolio.position:
            position_text = (
                f"{portfolio.position.quantity:,.4f} {snapshot.base_symbol} "
                f"@ {portfolio.position.entry_price:.10g} XNT"
            )

        return (
            "Liquidity Scout reply:\n"
            f"Paper cash: {portfolio.quote_balance:,.2f} {snapshot.quote_symbol}\n"
            f"Open position: {position_text}\n"
            f"Realized P/L: {portfolio.realized_pnl:+,.2f} {snapshot.quote_symbol}\n"
            f"Paper trades recorded: {portfolio.trades}\n"
            "Mode: paper trading only."
        )

    if "liquidity" in q:
        return (
            "Liquidity Scout reply:\n"
            f"{snapshot.base_symbol}/{snapshot.quote_symbol} liquidity is "
            f"${snapshot.liquidity_usd:,.0f} with 24h volume of "
            f"${snapshot.volume_24h:,.0f}.\n"
            f"My minimum-liquidity rule is ${SETTINGS.min_liquidity_usd:,.0f}.\n"
            f"Risk: {risk}"
        )

    if "price" in q:
        return (
            "Liquidity Scout reply:\n"
            f"{snapshot.base_symbol}/{snapshot.quote_symbol} price is "
            f"{snapshot.price:.10g} XNT per {snapshot.base_symbol}.\n"
            f"Current signal: {signal.action} (score {signal.score:+d}).\n"
            f"Momentum: {signal.momentum:+.2%}."
        )

    if any(term in q for term in ("signal", "buy", "sell", "hold")):
        return (
            "Liquidity Scout reply:\n"
            f"Current signal: {signal.action} (score {signal.score:+d}).\n"
            f"Momentum: {signal.momentum:+.2%}\n"
            f"Liquidity: ${snapshot.liquidity_usd:,.0f}\n"
            f"Risk: {risk}\n"
            "This is analysis, not a live trade."
        )

    # Default / "what do you see?" response.
    return (
        "Liquidity Scout reply:\n"
        f"Right now {snapshot.base_symbol}/{snapshot.quote_symbol} is "
        f"{signal.action} (score {signal.score:+d}).\n"
        f"Price: {snapshot.price:.10g} XNT\n"
        f"Liquidity: ${snapshot.liquidity_usd:,.0f} | "
        f"24h volume: ${snapshot.volume_24h:,.0f}\n"
        f"Momentum: {signal.momentum:+.2%}\n"
        f"Risk: {risk}\n"
        "Mode: paper trading only."
    )


def post_reply(target_id, content):
    r = requests.post(
        FEED_URL,
        json={
            "wallet": SETTINGS.agent_wallet,
            "content": content,
            "name": BOT_NAME,
            "type": "agent",
            "replyTo": target_id,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def process_cycle():
    posts = fetch_posts()
    pending = find_unanswered_replies(posts)

    if not pending:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            "No new Liquidity Scout replies."
        )
        return

    snapshot, signal, portfolio, risk = get_live_context()
    answered = load_answered()

    for post in pending[:5]:
        post_id = str(post["id"])
        question = str(post.get("content", ""))
        sender = post.get("name") or post.get("wallet")

        print()
        print("=" * 72)
        print(f"New message from: {sender}")
        print(f"Message: {question}")

        answer = answer_question(
            question, snapshot, signal, portfolio, risk
        )

        parent_signal_id = str(post.get("replyTo"))
        result = post_reply(parent_signal_id, answer)
        created = result.get("post", {}) if isinstance(result, dict) else {}
        returned_reply_to = str(created.get("replyTo") or "")

        if returned_reply_to == parent_signal_id:
            answered.add(post_id)
            save_answered(answered)
            print(f"Replied visibly to parent Signal. Post ID: {created.get('id')}")
        else:
            print("WARNING: reply was posted but linkage was not confirmed.")
            print("Stopping this cycle to avoid duplicate replies.")
            break


def main():
    if not SETTINGS.agent_wallet:
        raise SystemExit("ERROR: AGENT_WALLET is missing from .env")

    print("Liquidity Scout MoltGrid conversation listener")
    print(f"Polling every {POLL_SECONDS} seconds")
    print("Mode: market analysis + paper-account reporting only")
    print("Press Ctrl+C to stop.")
    print()

    while True:
        try:
            process_cycle()
        except KeyboardInterrupt:
            print("\nConversation listener stopped.")
            break
        except Exception as exc:
            print(f"Listener error: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
