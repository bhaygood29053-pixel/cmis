"""
Liquidity Scout Trader v0.1 — MoltGrid Auto Reporter

Uses the existing v0.1 modules.
- Reads live XDEX/X1 data.
- Runs the existing paper-trading strategy and risk engine.
- Posts to MoltGrid only when the signal/action status changes.
- Does NOT sign transactions or move real funds.
"""

import argparse
import json
import time
from pathlib import Path

import requests

from config import SETTINGS
from main import identity_banner, run_cycle
from market import X1NinjaClient


POST_URL = "https://moltgridx1.vercel.app/api/post"
DATA_DIR = Path(__file__).resolve().parent / "data"
DECISIONS_PATH = DATA_DIR / "decisions.jsonl"
MOLTGRID_STATE_PATH = DATA_DIR / "moltgrid_state.json"


def read_latest_decision():
    if not DECISIONS_PATH.exists():
        return None

    lines = [
        line.strip()
        for line in DECISIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return None

    return json.loads(lines[-1])


def load_last_fingerprint():
    if not MOLTGRID_STATE_PATH.exists():
        return None

    try:
        data = json.loads(MOLTGRID_STATE_PATH.read_text(encoding="utf-8"))
        return data.get("last_fingerprint")
    except Exception:
        return None


def save_last_fingerprint(fingerprint):
    DATA_DIR.mkdir(exist_ok=True)
    MOLTGRID_STATE_PATH.write_text(
        json.dumps({"last_fingerprint": fingerprint}, indent=2),
        encoding="utf-8",
    )


def make_fingerprint(decision):
    return f"{decision.get('signal')}|{decision.get('action_taken')}"


def format_signal(decision):
    signal = decision.get("signal", "UNKNOWN")
    action = decision.get("action_taken", "NONE")
    price = float(decision.get("price") or 0)
    liquidity = float(decision.get("liquidity_usd") or 0)
    volume = float(decision.get("volume_24h") or 0)
    score = int(decision.get("score") or 0)
    equity = float(decision.get("equity") or 0)
    pair = decision.get("pair", "AGI/XNT")

    if action.startswith("BUY_BLOCKED"):
        risk_text = "Trade blocked by risk engine."
    elif action in ("PAPER_BUY", "PAPER_SELL"):
        risk_text = f"Paper action: {action}."
    elif "STOP_LOSS" in action or "TAKE_PROFIT" in action:
        risk_text = f"Paper exit: {action}."
    else:
        risk_text = "No trade taken."

    return (
        f"Liquidity Scout | {pair}\n"
        f"Signal: {signal} (score {score:+d})\n"
        f"Price: {price:.10g} XNT\n"
        f"Liquidity: ${liquidity:,.0f} | 24h volume: ${volume:,.0f}\n"
        f"{risk_text}\n"
        f"Paper equity: {equity:,.2f} XNT"
    )


def post_to_moltgrid(content):
    if not SETTINGS.agent_wallet:
        raise RuntimeError("AGENT_WALLET is missing from .env")

    response = requests.post(
        POST_URL,
        json={
            "wallet": SETTINGS.agent_wallet,
            "content": content,
            "name": "Liquidity Scout",
            "type": "agent",
        },
        timeout=15,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def run_and_report(feed):
    run_cycle(feed)

    decision = read_latest_decision()
    if not decision:
        print("MoltGrid: no decision found to report.")
        return

    fingerprint = make_fingerprint(decision)
    previous = load_last_fingerprint()

    if fingerprint == previous:
        print("MoltGrid: no post — signal/action unchanged.")
        return

    content = format_signal(decision)

    try:
        result = post_to_moltgrid(content)
        post_id = None
        if isinstance(result, dict):
            post_id = (result.get("post") or {}).get("id")

        if post_id:
            print(f"MoltGrid: posted status update successfully. Post ID: {post_id}")
        else:
            print("MoltGrid: posted status update successfully.")

        save_last_fingerprint(fingerprint)

    except Exception as exc:
        print(f"MoltGrid post error: {exc}")
        print("The market scan was still recorded; the bot will try again next cycle.")


def main():
    parser = argparse.ArgumentParser(
        description="Liquidity Scout v0.1 with automatic MoltGrid reporting"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one live scan/report cycle and exit.",
    )
    args = parser.parse_args()

    identity_banner()

    feed = X1NinjaClient(
        SETTINGS.api_key,
        SETTINGS.rpc_url,
        SETTINGS.base_token_vault,
        SETTINGS.quote_token_vault,
    )

    print("Market feed: X1.Ninja signals + X1 RPC reserve price")
    print("MoltGrid auto-reporting: ON")
    print("Posting policy: only when signal/action status changes")
    print("Trading mode: PAPER ONLY")

    while True:
        try:
            run_and_report(feed)
        except KeyboardInterrupt:
            print("\nLiquidity Scout stopped.")
            break
        except Exception as exc:
            print(f"Cycle error: {exc}")

        if args.once:
            break

        time.sleep(SETTINGS.poll_seconds)


if __name__ == "__main__":
    main()
