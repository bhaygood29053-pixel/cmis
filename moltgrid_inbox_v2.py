"""
Liquidity Scout — MoltGrid Inbox Test v2

READ-ONLY:
- Fetches the MoltGrid Signal feed.
- Treats a post as "mine" only when BOTH:
    1. wallet == AGENT_WALLET
    2. name == "Liquidity Scout"
- Finds recent direct replies to those Liquidity Scout posts.
- Finds recent explicit mentions of "Liquidity Scout".
- Ignores old Roberta/Clawbot conversations.
- Does NOT post, sign, trade, or move funds.
"""

import requests
from datetime import datetime, timezone, timedelta

from config import SETTINGS

FEED_URL = "https://moltgridx1.vercel.app/api/post"
BOT_NAME = "Liquidity Scout"
LOOKBACK_HOURS = 24


def parse_time(value):
    if not value:
        return None
    try:
        # Convert trailing Z to a Python-compatible UTC offset.
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_posts():
    response = requests.get(FEED_URL, timeout=15)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        posts = data.get("posts", [])
    elif isinstance(data, list):
        posts = data
    else:
        posts = []

    return posts


def main():
    if not SETTINGS.agent_wallet:
        print("ERROR: AGENT_WALLET is missing from .env")
        return

    posts = fetch_posts()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=LOOKBACK_HOURS)

    print(f"MoltGrid posts read: {len(posts)}")

    # Critical fix:
    # Old Roberta used the same wallet, so wallet alone is NOT enough.
    my_posts = [
        p for p in posts
        if str(p.get("wallet", "")) == SETTINGS.agent_wallet
        and str(p.get("name", "")).strip().lower() == BOT_NAME.lower()
    ]

    my_post_ids = {str(p.get("id")) for p in my_posts if p.get("id")}

    print(f"Actual Liquidity Scout posts found: {len(my_posts)}")

    incoming = []

    for post in posts:
        # Ignore anything produced by our own wallet.
        if str(post.get("wallet", "")) == SETTINGS.agent_wallet:
            continue

        post_time = parse_time(post.get("timestamp"))

        # Only consider messages from the last 24 hours.
        if post_time is not None and post_time < cutoff:
            continue

        content = str(post.get("content", ""))
        reply_to = post.get("replyTo")

        is_direct_reply = (
            reply_to is not None
            and str(reply_to) in my_post_ids
        )

        is_explicit_mention = BOT_NAME.lower() in content.lower()

        if is_direct_reply or is_explicit_mention:
            incoming.append(post)

    # Newest first.
    incoming.sort(
        key=lambda p: parse_time(p.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    print(
        f"Recent messages/replies for Liquidity Scout "
        f"(last {LOOKBACK_HOURS}h): {len(incoming)}"
    )
    print()

    if not incoming:
        print("No recent Liquidity Scout message was detected.")
        print()
        print("TEST:")
        print("1. Go to MoltGrid.")
        print("2. Reply directly to a CURRENT Liquidity Scout post.")
        print('3. Type: Liquidity Scout, what do you see right now?')
        print("4. Run this program again.")
        return

    for i, post in enumerate(incoming[:10], 1):
        print("=" * 72)
        print(f"MESSAGE {i}")
        print(f"Post ID:  {post.get('id')}")
        print(f"From:     {post.get('name') or post.get('wallet')}")
        print(f"Wallet:   {post.get('wallet')}")
        print(f"Reply To: {post.get('replyTo')}")
        print(f"Time:     {post.get('timestamp')}")
        print("Content:")
        print(post.get("content", ""))
        print()

    print("=" * 72)
    print("READ-ONLY TEST COMPLETE")
    print("Nothing was posted to MoltGrid and no transaction was made.")


if __name__ == "__main__":
    main()
