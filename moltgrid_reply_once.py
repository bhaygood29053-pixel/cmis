"""
Liquidity Scout — MoltGrid One-Reply Test

Purpose:
- Read the MoltGrid Signal feed.
- Find the newest recent reply to a CURRENT Liquidity Scout post.
- Allow the reply to come from the SAME wallet (e.g. Roberta/human UI).
- Analyze AGI/XNT using the existing live market modules.
- Post ONE deterministic market-status reply back to that message.
- Record the message ID so it is not answered twice.

Safety:
- No wallet signing.
- No private key.
- No live trading.
- No paper trade is executed by this script.
"""

import json
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

DATA_DIR = Path(__file__).resolve().parent / "data"
STATE_PATH = DATA_DIR / "moltgrid_reply_state.json"

# These identify CURRENT Liquidity Scout posts even if MoltGrid's UI
# displays the AgentID/profile name "Roberta" for the shared wallet.
BOT_CONTENT_MARKERS = (
    "Liquidity Scout |",
    "Liquidity Scout Trader v0.1",
)


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_posts():
    response = requests.get(FEED_URL, timeout=15)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict):
        return payload.get("posts", [])
    if isinstance(payload, list):
        return payload
    return []


def is_liquidity_scout_post(post):
    if str(post.get("wallet", "")) != SETTINGS.agent_wallet:
        return False

    content = str(post.get("content", ""))
    name = str(post.get("name", "")).strip().lower()

    return (
        name == BOT_NAME.lower()
        or any(marker.lower() in content.lower() for marker in BOT_CONTENT_MARKERS)
    )


def load_answered_ids():
    if not STATE_PATH.exists():
        return set()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return set(raw.get("answered_post_ids", []))
    except Exception:
        return set()


def save_answered_ids(ids):
    DATA_DIR.mkdir(exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"answered_post_ids": sorted(ids)}, indent=2),
        encoding="utf-8",
    )


def find_newest_unanswered_reply(posts):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=LOOKBACK_HOURS)

    bot_posts = [p for p in posts if is_liquidity_scout_post(p)]
    bot_post_ids = {str(p.get("id")) for p in bot_posts if p.get("id")}

    answered = load_answered_ids()
    candidates = []

    for post in posts:
        post_id = str(post.get("id") or "")
        reply_to = post.get("replyTo")
        content = str(post.get("content", ""))

        if not post_id or post_id in answered:
            continue

        # Never interpret one of our generated replies as a new user question.
        if content.startswith("Liquidity Scout reply:"):
            continue

        if reply_to is None or str(reply_to) not in bot_post_ids:
            continue

        post_time = parse_time(post.get("timestamp"))
        if post_time is not None and post_time < cutoff:
            continue

        candidates.append(post)

    candidates.sort(
        key=lambda p: parse_time(p.get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return candidates[0] if candidates else None, len(bot_posts)


def get_market_analysis():
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

    risk_text = "No entry requested."
    if signal.action == "BUY":
        allowed, blockers = entry_allowed(snapshot, portfolio, SETTINGS)
        if allowed:
            risk_text = "Paper-trade risk rules currently allow an entry."
        else:
            risk_text = "BUY blocked: " + "; ".join(blockers)
    elif signal.action == "SELL":
        if portfolio.position:
            risk_text = "SELL signal detected on the current paper position."
        else:
            risk_text = "SELL signal detected, but there is no paper position to exit."
    else:
        risk_text = "HOLD — no trade indicated."

    return snapshot, signal, risk_text


def build_reply(question, snapshot, signal, risk_text):
    # Deterministic response for v0.1. No LLM/API is used yet.
    return (
        "Liquidity Scout reply:\n"
        f"Right now {snapshot.base_symbol}/{snapshot.quote_symbol} is "
        f"{signal.action} (score {signal.score:+d}).\n"
        f"Price: {snapshot.price:.10g} XNT\n"
        f"Liquidity: ${snapshot.liquidity_usd:,.0f} | "
        f"24h volume: ${snapshot.volume_24h:,.0f}\n"
        f"Momentum: {signal.momentum:+.2%}\n"
        f"Risk: {risk_text}\n"
        "Mode: paper trading only."
    )


def post_reply(target_post, content):
    payload = {
        "wallet": SETTINGS.agent_wallet,
        "content": content,
        "name": BOT_NAME,
        "type": "agent",
        # MoltGrid post objects expose replyTo. We test whether POST accepts it.
        "replyTo": target_post["id"],
    }

    response = requests.post(FEED_URL, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def main():
    if not SETTINGS.agent_wallet:
        print("ERROR: AGENT_WALLET is missing from .env")
        return

    posts = fetch_posts()
    target, bot_post_count = find_newest_unanswered_reply(posts)

    print(f"MoltGrid posts read: {len(posts)}")
    print(f"Current Liquidity Scout posts recognized: {bot_post_count}")

    if target is None:
        print("No recent unanswered reply to Liquidity Scout was found.")
        print()
        print("Reply directly to a CURRENT Liquidity Scout post and run this again.")
        return

    print()
    print("Newest unanswered message found:")
    print(f"Post ID:  {target.get('id')}")
    print(f"From:     {target.get('name') or target.get('wallet')}")
    print(f"Reply To: {target.get('replyTo')}")
    print(f"Content:  {target.get('content')}")
    print()

    snapshot, signal, risk_text = get_market_analysis()
    reply_text = build_reply(target.get("content", ""), snapshot, signal, risk_text)

    print("Liquidity Scout will reply with:")
    print("-" * 72)
    print(reply_text)
    print("-" * 72)

    result = post_reply(target, reply_text)

    created = result.get("post", {}) if isinstance(result, dict) else {}
    created_id = created.get("id")
    created_reply_to = created.get("replyTo")

    print()
    print("MoltGrid accepted the reply.")
    print(f"New post ID: {created_id}")
    print(f"Returned replyTo: {created_reply_to}")

    if str(created_reply_to) == str(target.get("id")):
        print("SUCCESS: MoltGrid attached the response to your message.")
        answered = load_answered_ids()
        answered.add(str(target["id"]))
        save_answered_ids(answered)
    else:
        print("WARNING: MoltGrid created the post but did not confirm reply linkage.")
        print("Do not run this script again yet. Check MoltGrid and tell ChatGPT what you see.")


if __name__ == "__main__":
    main()
