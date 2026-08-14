from decimal import Decimal
"""
Liquidity Scout v0.12 — Hybrid XDEX + Ollama Signal Listener

What it does:
- Watches MoltGrid Signal replies.
- Searches the FULL XDEX pool catalog for the asset named in the question.
- Supports symbol, token name, mint address, and pool address matching.
- Answers with the strongest matching pool by liquidity/volume.
- Handles XNT with X1.Ninja's top-level xntPriceUsd reference.
- NEVER silently falls back to AGI if another asset was requested.
- Reuses the existing MoltGrid answered-message state so old replies are not duplicated.

Examples it should understand:
    What is SolXen doing today?
    What is the price of XNT?
    Tell me about ANL.
    What is the liquidity for BRAINS?
    Find XENCAT.
    What pools does THEO have?

Safety:
- no wallet signing
- no private key
- no live trading
- no paper trade execution
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
import historical_metrics as history
import xdex_rankings as rankings


from config import SETTINGS

from liquidity_scout.services import (
    FIELD_ORDER as CORE_FIELD_ORDER,
    format_field_line as core_format_field_line,
    full_snapshot_lines as core_full_snapshot_lines,
    requested_asset_fields as core_requested_asset_fields,
    wants_token_address,
)

MOLTGRID_URL = "https://moltgridx1.vercel.app/api/post"
POOLS_URL = "https://api.x1.ninja/v1/pools"

BOT_NAME = "Liquidity Scout"
LOOKBACK_HOURS = 24
POLL_SECONDS = int(os.getenv("MOLTGRID_REPLY_POLL_SECONDS", "15"))
CATALOG_REFRESH_SECONDS = int(os.getenv("XDEX_CATALOG_REFRESH_SECONDS", "300"))
PAGE_SIZE = 100

# Hybrid intelligence layer.
# XDEX facts always come from X1.Ninja. Ollama is used only to interpret
# verified XDEX data or answer general conceptual questions.
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL", "http://localhost:11434"
).rstrip("/")
AI_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct").strip()
AI_MAX_OUTPUT_TOKENS = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "450"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))

# Cloud AI provider for deep XDEX analysis.
# Ollama remains the local fallback if DeepSeek is unavailable.
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv(
    "DEEPSEEK_BASE_URL",
    "https://api.deepseek.com",
).rstrip("/")
DEEPSEEK_MODEL = os.getenv(
    "DEEPSEEK_MODEL",
    "deepseek-v4-flash",
).strip()
DEEPSEEK_TIMEOUT_SECONDS = int(
    os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
)
DEEPSEEK_TEMPERATURE = float(
    os.getenv("DEEPSEEK_TEMPERATURE", "0.1")
)

DATA_DIR = Path(__file__).resolve().parent / "data"
STATE_PATH = DATA_DIR / "moltgrid_conversation_state.json"

BOT_CONTENT_MARKERS = (
    "Liquidity Scout |",
    "Liquidity Scout Trader v0.1",
    "Liquidity Scout reply:",
    "Liquidity Scout reply:",
)

# Common words we do NOT want to mistake for ticker symbols.
STOPWORDS = {
    "WHAT", "IS", "THE", "OF", "DOING", "TODAY", "PRICE", "LIQUIDITY",
    "VOLUME", "SHOW", "ME", "TELL", "ABOUT", "FIND", "HOW", "DOES", "HAVE",
    "POOL", "POOLS", "ON", "XDEX", "RIGHT", "NOW", "CURRENT", "CURRENTLY",
    "MARKET", "CAP", "HOLDERS", "SAFETY", "TOKEN", "COIN", "ASSET",
    "BUY", "SELL", "HOLD", "SIGNAL", "PLEASE", "WHATS", "WHAT'S",
}




def n(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def s(value):
    return str(value or "").strip()


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None



def format_age(created_at):
    if not created_at:
        return "N/A"
    try:
        created = parse_time(created_at)
        if created is None:
            return "N/A"

        now = datetime.now(timezone.utc)
        delta = now - created
        if delta.total_seconds() < 0:
            return "N/A"

        minutes = int(delta.total_seconds() // 60)
        hours = int(delta.total_seconds() // 3600)
        days = delta.days

        if minutes < 60:
            return f"{minutes}m"
        if hours < 24:
            return f"{hours}h"
        if days < 30:
            return f"{days}d"
        if days < 365:
            return f"{max(1, days // 30)}mo"

        years = days // 365
        months = (days % 365) // 30
        return f"{years}y {months}mo" if months else f"{years}y"
    except Exception:
        return "N/A"

def fetch_signal_posts():
    r = requests.get(MOLTGRID_URL, timeout=15)
    r.raise_for_status()
    body = r.json()

    if isinstance(body, dict):
        return body.get("posts", [])
    if isinstance(body, list):
        return body
    return []


def is_liquidity_scout_post(post):
    if str(post.get("wallet", "")) != SETTINGS.agent_wallet:
        return False

    content = s(post.get("content"))
    name = s(post.get("name")).lower()

    return (
        name == BOT_NAME.lower()
        or any(marker.lower() in content.lower() for marker in BOT_CONTENT_MARKERS)
    )


def load_state():
    if not STATE_PATH.exists():
        return {
            "answered_post_ids": [],
            "implicit_asset_mode_started_at": None,
            "thread_reply_mode_started_at": None,
        }

    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}

    raw.setdefault("answered_post_ids", [])
    raw.setdefault("implicit_asset_mode_started_at", None)
    raw.setdefault("thread_reply_mode_started_at", None)
    return raw


def save_state(state):
    DATA_DIR.mkdir(exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def load_answered():
    return set(load_state().get("answered_post_ids", []))


def save_answered(answered):
    state = load_state()
    state["answered_post_ids"] = sorted(answered)
    save_state(state)


def ensure_implicit_mode_start():
    """
    On first v5 launch, record when implicit standalone asset questions
    became enabled. This prevents v5 from suddenly answering older Roberta
    posts that existed before this feature was turned on.
    """
    state = load_state()
    value = state.get("implicit_asset_mode_started_at")

    if value:
        parsed = parse_time(value)
        if parsed is not None:
            return parsed

    started = datetime.now(timezone.utc)
    state["implicit_asset_mode_started_at"] = started.isoformat()
    save_state(state)
    return started


def ensure_thread_reply_mode_start():
    """
    Record when threaded follow-up listening was enabled.
    Existing messages from before this moment are ignored.
    """
    state = load_state()
    value = state.get("thread_reply_mode_started_at")

    if value:
        parsed = parse_time(value)
        if parsed is not None:
            return parsed

    started = datetime.now(timezone.utc)
    state["thread_reply_mode_started_at"] = started.isoformat()
    save_state(state)
    return started


QUESTION_CUES = (
    "?", "what", "whats", "what's", "tell", "show", "find", "price",
    "liquidity", "volume", "market cap", "marketcap", "holders", "holder",
    "safety", "safe", "doing", "how", "pool", "pools", "worth",
    "change", "up", "down", "today", "right now", "current",
"compare", "compared", "versus", " vs ", " vs. ",
)



def looks_like_agent_identity_question(content):
    """Detect questions about Roberta / Liquidity Scout herself."""
    text = s(content).strip().lower()

    if not text:
        return False

    identity_phrases = (
        "operating principles",
        "your principles",
        "your mission",
        "your purpose",
        "your role",
        "who are you",
        "what are you",
        "what can you do",
        "what do you do",
        "your capabilities",
        "how do you manage risk",
        "how do you handle risk",
        "your risk controls",
        "your safety rules",
        "your safety principles",
        "your rules",
        "your guidelines",
        "your memory",
        "what do you remember",
        "what are you designed to do",
    )

    return any(phrase in text for phrase in identity_phrases)


def looks_like_asset_question(content, resolved_term):
    """
    Avoid replying to every casual Signal that merely mentions a token.
    We answer if there is question-like language, or if the post is
    essentially just the asset identifier itself.
    """
    text = s(content).strip()
    lower = text.lower()

    if any(cue in lower for cue in QUESTION_CUES):
        return True

    normalized = normalize_text(text)
    words = normalized.split()

    if resolved_term and normalized.lower() == resolved_term.lower():
        return True

    # Short commands such as "ANL info" or "BRAINS details".
    if len(words) <= 3 and resolved_term:
        return True

    return False


def looks_like_general_question(content):
    """
    Detect a conversational question without requiring an XDEX asset match.
    Used only for the owner's own new standalone Signals. Other users still
    need to reply to Liquidity Scout or address it explicitly.
    """
    text = s(content).strip()
    lower = text.lower()

    if not text:
        return False

    if "?" in text:
        return True

    starters = (
        "what ", "why ", "how ", "when ", "where ", "who ",
        "explain ", "define ", "tell me ", "can ", "does ", "do ",
        "is ", "are ", "should ", "could ", "would ",
    )
    return lower.startswith(starters)


def wants_historical_liquidity(question):
    """Detect questions asking about liquidity changes over time."""
    q = s(question).lower()

    if "liquidity" not in q and not re.search(r"\bliq\b", q):
        return False

    historical_terms = (
        "fallen", "falling", "fell",
        "dropped", "drop", "declined", "decreased",
        "increased", "increasing", "risen", "rose",
        "changed", "change", "trend", "trending",
        "this week", "last week",
        "7d", "7 days", "seven days",
        "24h", "24 hours",
        "30d", "30 days",
        "yesterday", "ago",
        "over the last",
        "since",
    )

    if any(term in q for term in historical_terms):
        return True

    # Percentage comparison such as:
    # "Has liquidity fallen more than 30%?"
    if "%" in q:
        return True

    return False


def wants_asset_analysis(question):
    """
    Distinguish raw-data requests from interpretation requests.

    Examples:
      "What is FOREST liquidity?" -> False (deterministic metric only)
      "Is FOREST liquidity dangerous?" -> True (live data + AI analysis)
      "Why is AGI falling?" -> True
    """
    q = s(question).lower()

    # Historical comparisons are deterministic and should not be
    # answered by the LLM analysis route.
    if history.parse_historical_comparison(question):
        return False

    analysis_phrases = (
        "dangerous", "risky", "risk", "healthy", "unhealthy",
        "good", "bad", "strong", "weak", "thin", "deep",
        "concerning", "concern", "worry", "worried",
        "why ", "what does this mean", "what does that mean",
        "explain", "analyze", "analyse", "analysis",
        "tell me about", "overview",
        "outlook", "pressure", "bullish", "bearish",
        "worth buying", "worth selling", "should i buy", "should i sell",
        "is it safe", "how safe", "is this safe",
    )

    if any(phrase in q for phrase in analysis_phrases):
        return True

    # "Is FOREST safe?" / "Is AGI risky?" style questions.
    if re.search(r"\bis\b.+\bsafe\b", q):
        return True
    if re.search(r"\bis\b.+\brisky\b", q):
        return True

    return False


def ai_available():
    """
    Confirm both the local Ollama server and configured model are available.
    """
    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=4,
        )
        response.raise_for_status()

        payload = response.json()
        models = payload.get("models") or []

        installed = {
            s(item.get("name") or item.get("model"))
            for item in models
            if isinstance(item, dict)
        }

        return AI_MODEL in installed
    except Exception:
        return False



ROBERTA_HXMP_MEMORY = None


def initialize_hxmp_memory():
    """Load Roberta's verified HXMP memory once at startup."""
    global ROBERTA_HXMP_MEMORY

    try:
        from hxmp_memory import load_roberta_memory

        memory = load_roberta_memory()

        if not memory.get("verified"):
            raise RuntimeError("HXMP verification failed")

        ROBERTA_HXMP_MEMORY = memory
        return memory

    except Exception as exc:
        ROBERTA_HXMP_MEMORY = None
        print(f"HXMP memory unavailable: {exc}")
        return None


def apply_hxmp_memory(instructions):
    """Add verified HXMP SOUL memory to Ollama system context."""
    memory = ROBERTA_HXMP_MEMORY

    if not memory:
        return instructions

    content = str(memory.get("content") or "").strip()

    if not content:
        return instructions

    return f"""{instructions}

--- VERIFIED PERSISTENT HXMP IDENTITY ---

The following is Roberta's verified persistent SOUL memory
retrieved from X1 through HXMP.

Treat it as durable identity, mission, operating, safety,
and memory guidance.

It does not replace verified XDEX market facts,
risk controls, or execution permissions.

HXMP sequence: {memory.get("sequence")}
HXMP SHA-256: {memory.get("sha256")}

{content}

--- END VERIFIED HXMP IDENTITY ---
"""



def format_hxmp_identity_answer(question):
    """Answer Roberta identity questions directly from verified HXMP memory."""
    memory = ROBERTA_HXMP_MEMORY

    if not memory or not memory.get("verified"):
        return (
            "Liquidity Scout memory is currently unavailable, "
            "so I cannot verify my persistent operating identity."
        )

    q = s(question).lower()

    if "mission" in q or "purpose" in q or "designed to do" in q:
        return (
            "My mission is to analyze cryptocurrency markets, liquidity, "
            "risk, and trading opportunities using measurable evidence "
            "rather than hype."
        )

    if (
        "operating principles" in q
        or "your principles" in q
        or "your rules" in q
        or "your guidelines" in q
    ):
        return (
            "My operating principles are:\n"
            "• Capital preservation comes before profit.\n"
            "• Separate market analysis from trade execution.\n"
            "• Consider liquidity, fees, slippage, volatility, and execution risk.\n"
            "• Never guarantee profits or future prices.\n"
            "• Prefer evidence over speculation.\n"
            "• Clearly communicate uncertainty and risk.\n"
            "• Never bypass established risk controls."
        )

    if "risk" in q:
        return (
            "I manage risk by putting capital preservation first, "
            "considering liquidity, fees, slippage, volatility, and execution risk, "
            "and never bypassing established risk controls."
        )

    if "safety" in q:
        return (
            "My safety rules are to never store or expose private keys, seed phrases, "
            "passwords, API keys, or authentication tokens; keep operational funds "
            "separate from treasury funds; and require approved risk controls for live trading."
        )

    if "memory" in q or "remember" in q:
        return (
            "My persistent memory is for durable operating principles, strategy lessons, "
            "capabilities, and non-sensitive market knowledge. I do not store credentials, "
            "private conversations, or sensitive personal information."
        )

    if (
        "who are you" in q
        or "what are you" in q
        or "what do you do" in q
        or "what can you do" in q
        or "capabilities" in q
        or "role" in q
    ):
        return (
            "I am Roberta, operating as Liquidity Scout—an AI market-intelligence agent "
            "focused on cryptocurrency markets, XDEX liquidity, risk, and trading opportunities."
        )

    return (
        "I am Roberta, operating as Liquidity Scout. "
        "My verified HXMP identity prioritizes evidence, capital preservation, "
        "risk awareness, and separation of analysis from execution."
    )


def ai_text(instructions, user_input, max_output_tokens=None):
    """
    Call the local Ollama /api/chat endpoint directly.

    No cloud LLM API key is used.
    The function returns None instead of crashing the Signal listener if
    Ollama is unavailable or the local model fails.
    """
    output_token_limit = (
        AI_MAX_OUTPUT_TOKENS
        if max_output_tokens is None
        else int(max_output_tokens)
    )

    payload = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": apply_hxmp_memory(instructions),
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
        "stream": False,
        # Qwen3 supports thinking, but Liquidity Scout only needs the final
        # concise answer for MoltGrid Signal.
        "think": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": output_token_limit,
        },
        # Keep the model warm between Signal questions.
        "keep_alive": "10m",
    }

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            print(f"Ollama error: {data['error']}")
            return None

        message = data.get("message") or {}
        text = s(message.get("content"))
        return text or None

    except requests.RequestException as exc:
        print(f"Ollama connection error: {exc}")
        return None
    except (ValueError, TypeError) as exc:
        print(f"Ollama response error: {exc}")
        return None



def deepseek_text(instructions, user_input, max_output_tokens=None):
    """
    Call DeepSeek as an optional cloud AI provider.

    HXMP memory is intentionally NOT attached here. Verified identity
    and persistent memory remain local unless explicitly designed
    otherwise.

    Returns None instead of crashing the Signal listener if DeepSeek
    is unavailable or the API request fails.
    """
    if not DEEPSEEK_API_KEY:
        print("DeepSeek unavailable: DEEPSEEK_API_KEY is not configured.")
        return None

    output_token_limit = (
        AI_MAX_OUTPUT_TOKENS
        if max_output_tokens is None
        else int(max_output_tokens)
    )

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": instructions,
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
        "thinking": {
            "type": "disabled",
        },
        "temperature": DEEPSEEK_TEMPERATURE,
        "max_tokens": output_token_limit,
        "stream": False,
    }

    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=DEEPSEEK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []

        if not choices:
            print("DeepSeek response error: no choices returned.")
            return None

        message = choices[0].get("message") or {}
        text = s(message.get("content"))
        return text or None

    except requests.RequestException as exc:
        print(f"DeepSeek connection error: {exc}")
        return None
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        print(f"DeepSeek response error: {exc}")
        return None

def liquidity_depth_label(liquidity):
    """
    Deterministic Liquidity Scout liquidity classification.
    Do not let the AI invent its own depth category.
    """
    liquidity = n(liquidity)

    if liquidity < 5_000:
        return "very thin"
    if liquidity < 25_000:
        return "fairly thin"
    if liquidity >= 100_000:
        return "comparatively deep"

    return "not qualitatively classified"


def volume_activity_label(volume24):
    """
    Deterministic Liquidity Scout 24h-volume classification.
    """
    volume24 = n(volume24)

    if volume24 < 1_000:
        return "light"
    if volume24 >= 25_000:
        return "strong"

    return "not qualitatively classified"


def price_movement_label(change24):
    """Deterministic 24h price-movement description."""
    change24 = n(change24)

    if change24 <= -10:
        return "down sharply"
    if change24 <= -3:
        return "under noticeable selling pressure"
    if change24 >= 10:
        return "up sharply"
    if change24 >= 3:
        return "a solid upward move"

    return "relatively modest"


def verified_snapshot_context(snap, fields):
    """
    Serialize only the verified XDEX values approved for this answer.
    Omitted metrics are not exposed to the AI analysis layer.
    """
    lines = [f"Token: {snap['title']}"]

    for field in fields:
        if field == "price":
            lines.append(f"Price: {snap['price']}")

        elif field == "age":
            lines.append(f"Age: {snap['age']}")

        elif field == "holders":
            lines.append(f"Holders: {snap['holders']:,}")

        elif field == "txns24":
            lines.append(f"Transactions 24h: {snap['txns24']:,}")

        elif field == "volume24":
            lines.append(f"Volume 24h: {format_usd(snap['vol24'])}")
            lines.append(
                f"Volume classification: "
                f"{volume_activity_label(snap['vol24'])}"
            )

        elif field == "change1h":
            lines.append(f"Change 1h: {snap['change1']:+.2f}%")

        elif field == "change24h":
            lines.append(f"Change 24h: {snap['change24']:+.2f}%")
            lines.append(
                f"24h price-movement classification: "
                f"{price_movement_label(snap['change24'])}"
            )

        elif field == "liquidity":
            lines.append(f"Liquidity: {format_usd(snap['liquidity'])}")
            lines.append(
                f"Liquidity classification: "
                f"{liquidity_depth_label(snap['liquidity'])}"
            )

        elif field == "market_cap":
            lines.append(
                "Market Cap: Not verified — "
                "circulating supply unavailable from verified data"
            )

        elif field == "safety":
            lines.append(f"Tokenomics Safety: {snap['safety']}")

        elif field == "pool_address":
            lines.append(
                f"Pool address: {snap['pool_address'] or 'N/A'}"
            )

    return "\n".join(lines)



def sanitize_asset_analysis(text):
    """
    Remove unsupported qualitative trading-risk severity labels from
    model-generated asset analysis while preserving the underlying
    verified risk mechanism.
    """
    if not text:
        return text

    forbidden = (
        "significant",
        "moderate",
        "high",
        "low",
        "elevated",
        "severe",
        "acceptable",
    )
    severity = "|".join(forbidden)

    # Example:
    # "Trading risk is elevated due to very thin liquidity..."
    # -> "Risk factors include very thin liquidity..."
    text = re.sub(
        rf"\b(?:trading\s+)?risk\s+is\s+(?:{severity})\s+due\s+to\s+",
        "Risk factors include ",
        text,
        flags=re.IGNORECASE,
    )

    # Also guard forms such as "high trading risk" or
    # "elevated market risk".
    text = re.sub(
        rf"\b(?:{severity})\s+(?:trading|market|execution)\s+risk\b",
        "market risk",
        text,
        flags=re.IGNORECASE,
    )

    # Remove unsupported model-added interpretations.
    text = re.sub(
        r",?\s*(?:indicating|suggesting)\s+limited\s+trading\s+activity"
        r"(?:\s+and\s+positive\s+momentum)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bpositive\s+momentum\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove volatility commentary when no volatility metric is supplied.
    text = re.sub(
        r",?\s*which\s+does\s+not\s+indicate\s+"
        r"(?:security\s+or\s+)?volatility\s+levels",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s+and\s+does\s+not\s+indicate\s+"
        r"(?:security\s+or\s+)?volatility\s+levels",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"(?:^|(?<=[.!?])\s+)"
        r"(?:No\b[^.!?]*\bvolatility\b|Volatility\b[^.!?]*"
        r"|There\s+is\s+no\b[^.!?]*\bvolatility\b)"
        r"[^.!?]*[.!?]?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s{2,}", " ", text).strip()

    return text

def ai_asset_analysis(question, snap, fields):
    """
    AI may INTERPRET the verified snapshot, but may not change or invent
    XDEX values, token addresses, pool addresses, or safety data.
    """
    instructions = """You are Liquidity Scout, an X1/XDEX market-analysis assistant.

You are given VERIFIED LIVE XDEX DATA from the application.
Rules:
- Discuss only metrics present in VERIFIED LIVE XDEX DATA. Do not mention metrics that were omitted from the supplied data.
- Interpret the supplied data; do not discover, estimate, replace, or invent market numbers.
- Never invent prices, holders, liquidity, volume, market cap, token addresses, pool addresses, transaction counts, safety grades, or percentages.
- If you mention a numeric market value, copy it exactly from VERIFIED LIVE XDEX DATA.
- The XDEX safety grade and safety score are TOKENOMICS metrics.
- Refer to them as the XDEX tokenomics grade or tokenomics safety grade.
- They are NOT cybersecurity, smart-contract security, protocol security, or system-security ratings.
- NEVER infer, translate, or describe the tokenomics grade as low trading risk, moderate trading risk, high trading risk, acceptable trading risk, reasonable security, high confidence, or any similar interpretation.
- If the tokenomics grade is relevant, report it exactly as supplied and state that it is separate from market trading risk.
- Assess trading risk only from verified market factors such as liquidity, volume, price movement, market depth, holder count, and execution/slippage conditions.
- If you describe liquidity depth, use ONLY the supplied "Liquidity classification". Never invent labels such as moderate, healthy, strong, deep, shallow, or adequate unless that exact classification is supplied.
- If Liquidity classification is "not qualitatively classified", state the numeric liquidity without assigning a depth label.
- If you describe 24h trading activity, use ONLY the supplied "Volume classification".
- If Volume classification is "not qualitatively classified", state the numeric 24h volume without calling it low, moderate, high, weak, healthy, strong, light, or similar.
- Transactions 24h is a transaction COUNT. Never describe the transaction count as trading volume.
- Change 1h and Change 24h are price-movement observations, not volatility measurements.
- NEVER call a token volatile, highly volatile, low-volatility, or assign any volatility level unless VERIFIED LIVE XDEX DATA explicitly supplies a volatility metric or classification.
- Describe 24h price movement using ONLY the supplied "24h price-movement classification". Do not invent terms such as sharp, explosive, weak, strong, flat, or extreme.
- A large positive or negative 24h change may be described as a price move, but not by itself as proof of volatility.
- Do not assign qualitative trading-risk severity labels such as significant, moderate, high, low, elevated, severe, or acceptable unless a verified risk classification is explicitly supplied.
- Instead explain the specific observed risk mechanism, such as very thin liquidity increasing slippage and price impact.
- Holder count by itself does not prove holder concentration because wallet distribution percentages are not supplied.
- In visible answers say "available liquidity" or "liquidity"; do not say "liquidity pool" or "pool liquidity" unless the user explicitly asks about the pool.
- Explain risk in plain English using only classifications and observations supported by the verified data.
- Answer the user's actual question first.
- Keep this analysis to exactly 2 concise sentences.
- Do not repeat numeric market values already displayed to the user.
- Do not invent momentum, volatility, activity, or risk labels beyond classifications explicitly supplied in VERIFIED LIVE XDEX DATA.
- Explain the main observed market mechanism and keep tokenomics safety separate from market trading risk.
- Do not give a command to buy or sell. You may explain what conditions look favorable or unfavorable.
"""

    user_input = (
        "USER QUESTION:\n"
        f"{question}\n\n"
        "VERIFIED LIVE XDEX DATA:\n"
        f"{verified_snapshot_context(snap, fields)}"
    )

    analysis = deepseek_text(
        instructions,
        user_input,
        max_output_tokens=90,
    )

    if not analysis:
        print("DeepSeek unavailable; falling back to Ollama.")
        analysis = ai_text(
            instructions,
            user_input,
            max_output_tokens=90,
        )

    return sanitize_asset_analysis(analysis)


def ai_general_answer(question):
    """
    General crypto / DeFi / X1 conceptual route.

    No XDEX asset matched before this function is called. The model is told
    that explicitly so it cannot substitute remembered live token data.
    """
    instructions = """You are Liquidity Scout, a concise crypto, DeFi, X1, and XDEX educational assistant on MoltGrid Signal.

Rules:
- Answer general crypto and DeFi concepts conversationally, clearly, and technically accurately.
- Explain the actual mechanism before using an analogy.
- Avoid common crypto oversimplifications that could mislead the user.
- For AMM price impact specifically: explain that swaps change the pool's reserve ratio and therefore move the execution price according to the AMM pricing formula. Larger swaps relative to available reserves create greater price impact. Do not describe ordinary proportional liquidity deposits or withdrawals as the main cause of swap price impact.
- For impermanent loss specifically: explain that it is the difference between the value of an AMM liquidity position and simply holding the original assets, caused by relative price movement and rebalancing according to the pool's pricing formula. Do not say every AMM maintains equal asset shares, and do not say impermanent loss happens merely because one asset falls in price.
- Do not imply that withdrawing creates impermanent loss. The value difference already exists while liquidity remains in the pool; withdrawing simply locks in the position at that point. The difference may shrink if relative prices move back.
- No XDEX asset matched this question before you were called.
- Do NOT invent or provide remembered live token prices, liquidity, holders, volume, market caps, safety scores, token addresses, or pool addresses.
- If the user appears to be asking for live data about a specific token that was not found on XDEX, say you could not verify that asset on XDEX and ask for its exact ticker, mint address, or pool address.
- X1 ecosystem details can change. If a question requires a current X1-specific fact that you cannot verify from supplied live data, say that clearly instead of guessing.
- Clearly distinguish verified facts, general principles, and uncertainty.
- Do not claim certainty about future prices or returns.
- Keep most answers between 2 and 6 short sentences.
"""

    user_input = (
        "No matching XDEX asset was found for this message.\n\n"
        f"USER QUESTION:\n{question}"
    )

    answer = deepseek_text(
        instructions,
        user_input,
    )

    if not answer:
        print("DeepSeek unavailable; falling back to Ollama.")
        answer = ai_text(
            instructions,
            user_input,
        )

    return answer


def format_ai_unavailable(question, asset_matched=False):
    if asset_matched:
        return (
            "Liquidity Scout reply:\n"
            "I retrieved the live XDEX data, but my AI interpretation layer is not configured yet. "
            "The deterministic XDEX lookup is still working."
        )

    return (
        "Liquidity Scout reply:\n"
        "My general-question intelligence layer is not configured yet. "
        "Live XDEX asset lookups still work normally."
    )



def is_broad_asset_overview(question):
    """Return True for simple asset-overview requests."""
    q = s(question).lower()

    return any(
        phrase in q
        for phrase in (
            "tell me about",
            "overview",
        )
    )


def deterministic_asset_overview_analysis(snap):
    """
    Fast overview interpretation using only deterministic classifications.
    No Ollama call is needed for routine asset summaries.
    """
    liquidity_label = liquidity_depth_label(snap["liquidity"])
    volume_label = volume_activity_label(snap["vol24"])
    movement_label = price_movement_label(snap["change24"])

    parts = []

    if liquidity_label == "not qualitatively classified":
        parts.append(
            "Liquidity has no qualitative depth classification."
        )
    else:
        parts.append(
            f"Available liquidity is {liquidity_label}, which can increase "
            "slippage and price impact during trades."
        )

    if volume_label == "not qualitatively classified":
        parts.append(
            "24-hour trading activity has no qualitative classification."
        )
    else:
        parts.append(
            f"24-hour trading activity is {volume_label}."
        )

    parts.append(
        f"The 24-hour price movement is {movement_label}."
    )

    parts.append(
        "Tokenomics safety is separate from current market trading conditions."
    )

    return " ".join(parts)


def format_asset_analysis_answer(question, term, matches, catalog):
    """
    Route 3: retrieve the complete verified XDEX snapshot internally,
    then present a clean analyst-style answer.
    """
    snap = compact_asset_snapshot(term, matches, catalog)
    fields = requested_asset_fields(question)

    # Broad asset-analysis questions should automatically show the
    # most useful verified market facts.
    if not fields:
        fields = [
            "price",
            "liquidity",
            "volume24",
            "change24h",
            "market_cap",
            "safety",
        ]

    lines = [
        "Liquidity Scout analysis:",
        snap["title"],
    ]

    # Show only metrics explicitly requested by the user.
    if fields:
        lines.append("")
        lines.extend(
            format_field_line(field, snap)
            for field in fields
        )

    if is_broad_asset_overview(question):
        analysis = deterministic_asset_overview_analysis(snap)
    else:
        analysis = ai_asset_analysis(question, snap, fields)

    if analysis:
        lines.extend([
            "",
            f"Analysis: {analysis}",
        ])
    else:
        lines.extend([
            "",
            "AI analysis is currently unavailable. Verified XDEX data:",
        ])

        if not fields:
            lines.extend(full_snapshot_lines(snap))

    if wants_token_address(question):
        lines.extend([
            "",
            f"Token Address: {snap.get('token_address') or 'N/A'}",
        ])

    return "\n".join(lines)


def format_general_answer(question):
    answer = ai_general_answer(question)
    if answer:
        return "Liquidity Scout reply:\n" + answer
    return format_ai_unavailable(question, asset_matched=False)


def find_unanswered_messages(
    posts,
    catalog,
    implicit_mode_started_at,
    thread_reply_mode_started_at,
):
    """
    Detect:
    1. replies to Liquidity Scout posts;
    2. standalone Signals explicitly naming "Liquidity Scout";
    3. standalone asset questions from the owner's same wallet, even if
       "Liquidity Scout" is omitted.

    Implicit same-wallet mode only applies to posts created after v5 was first
    activated, so older Roberta history is not unexpectedly answered.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    answered = load_answered()

    bot_posts = [p for p in posts if is_liquidity_scout_post(p)]
    bot_post_ids = {str(p.get("id")) for p in bot_posts if p.get("id")}

    # Liquidity Scout replies are attached to the original Signal root.
    # Remember those thread-root IDs so follow-up messages inside the
    # same Signal thread are treated as replies to Liquidity Scout too.
    bot_thread_root_ids = {
        str(p.get("replyTo"))
        for p in bot_posts
        if p.get("replyTo") is not None
    }

    incoming = []

    for post in posts:
        post_id = str(post.get("id") or "")
        reply_to = post.get("replyTo")
        content = s(post.get("content"))
        wallet = str(post.get("wallet", ""))

        if not post_id or post_id in answered:
            continue

        # Never treat Liquidity Scout's own posts as incoming messages.
        # This prevents threaded replies from causing a self-reply loop,
        # regardless of which Liquidity Scout response format was used.
        if is_liquidity_scout_post(post):
            continue

        when = parse_time(post.get("timestamp"))
        if when is not None and when < cutoff:
            continue

        is_direct_reply_to_bot = (
            reply_to is not None
            and str(reply_to) in bot_post_ids
        )

        is_thread_followup = (
            reply_to is not None
            and str(reply_to) in bot_thread_root_ids
            and when is not None
            and when >= thread_reply_mode_started_at
        )

        is_reply_to_bot = (
            is_direct_reply_to_bot
            or is_thread_followup
        )

        is_explicit_new_signal = (
            reply_to is None
            and "liquidity scout" in content.lower()
        )

        is_implicit_owner_asset_question = False
        is_implicit_owner_general_question = False
        resolved_term = None
        resolved_matches = []

        if (
            reply_to is None
            and wallet == SETTINGS.agent_wallet
            and "liquidity scout" not in content.lower()
            and when is not None
            and when >= implicit_mode_started_at
        ):
            if looks_like_agent_identity_question(content):
                is_implicit_owner_general_question = True
            else:
                resolved_term, resolved_matches = resolve_asset(
                    content,
                    catalog.pools,
                )

                if (
                    resolved_matches
                    and looks_like_asset_question(content, resolved_term)
                ):
                    is_implicit_owner_asset_question = True
                elif looks_like_general_question(content):
                    is_implicit_owner_general_question = True

        if is_reply_to_bot:
            incoming.append((post, "reply", None, None))
        elif is_explicit_new_signal:
            incoming.append((post, "standalone-explicit", None, None))
        elif is_implicit_owner_asset_question:
            incoming.append(
                (post, "standalone-implicit-asset", resolved_term, resolved_matches)
            )
        elif is_implicit_owner_general_question:
            incoming.append(
                (post, "standalone-implicit-general", None, None)
            )

    incoming.sort(
        key=lambda item: parse_time(item[0].get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )
    return incoming


class XDEXCatalog:
    def __init__(self):
        self.pools: List[Dict[str, Any]] = []
        self.xnt_price_usd = None
        self.last_refresh = 0.0

    def refresh_if_needed(self):
        age = time.time() - self.last_refresh
        if not self.pools or age >= CATALOG_REFRESH_SECONDS:
            self.refresh()

    def refresh(self):
        if not SETTINGS.api_key:
            raise RuntimeError("X1_NINJA_API_KEY is missing from .env")

        headers = {"Authorization": f"Bearer {SETTINGS.api_key}"}
        pools = []
        offset = 0
        total = None
        xnt_price_usd = None

        while True:
            r = requests.get(
                POOLS_URL,
                params={"limit": PAGE_SIZE, "offset": offset},
                headers=headers,
                timeout=20,
            )
            r.raise_for_status()
            body = r.json()

            page = body.get("pools", []) if isinstance(body, dict) else []
            if not isinstance(page, list):
                page = []

            if total is None:
                total = int(body.get("total") or body.get("totalCount") or 0)

            if xnt_price_usd is None:
                xnt_price_usd = body.get("xntPriceUsd")

            pools.extend(page)

            if not page:
                break

            offset += len(page)

            if total and offset >= total:
                break

            if offset > 10000:
                break

            time.sleep(0.03)

        self.pools = pools
        self.xnt_price_usd = xnt_price_usd
        self.last_refresh = time.time()

        print(
            f"[catalog] Loaded {len(self.pools)} XDEX pools"
            + (
                f" | XNT ${n(self.xnt_price_usd):,.6f}"
                if self.xnt_price_usd is not None
                else ""
            )
        )


def token_fields(token):
    if not isinstance(token, dict):
        return []
    return [
        s(token.get("symbol")),
        s(token.get("name")),
        s(token.get("mint")),
        s(token.get("address")),
    ]


def pool_address(pool):
    return s(pool.get("address") or pool.get("poolAddress") or pool.get("id"))


def pair_name(pool):
    base = pool.get("baseToken") or {}
    quote = pool.get("quoteToken") or {}
    return f"{s(base.get('symbol'))}/{s(quote.get('symbol'))}"


def normalize_text(text):
    return re.sub(r"[^A-Za-z0-9.]+", " ", s(text)).strip()


def candidate_terms(question):
    """
    Produce possible asset identifiers from a natural-language question.
    Longer phrases are tried first, then individual words.
    """
    clean = normalize_text(question)
    words = [w for w in clean.split() if w]

    candidates = []

    # Consecutive 3-word and 2-word phrases can match token names.
    for size in (3, 2):
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i:i+size])
            if phrase.upper() not in STOPWORDS:
                candidates.append(phrase)

    # Individual ticker/name/mint candidates.
    for word in words:
        if word.upper() in STOPWORDS:
            continue
        if len(word) >= 2:
            candidates.append(word)

    # Preserve order while deduplicating.
    seen = set()
    out = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)

    return out


def exact_token_match(token, query):
    q = s(query).lower()
    if not q:
        return False
    fields = [f.lower() for f in token_fields(token) if f]
    return q in fields


def partial_token_match(token, query):
    q = s(query).lower()
    if len(q) < 3:
        return False
    fields = [f.lower() for f in token_fields(token) if f]
    return any(q in f for f in fields)


def find_matches_for_term(term, pools):
    matches = []

    for pool in pools:
        base = pool.get("baseToken") or {}
        quote = pool.get("quoteToken") or {}
        addr = pool_address(pool)

        if term.lower() == addr.lower():
            matches.append((pool, "pool", None, 100))
            continue

        if exact_token_match(base, term):
            matches.append((pool, "base", base, 90))
        elif exact_token_match(quote, term):
            matches.append((pool, "quote", quote, 90))
        elif partial_token_match(base, term):
            matches.append((pool, "base", base, 60))
        elif partial_token_match(quote, term):
            matches.append((pool, "quote", quote, 60))

    return matches




def explicitly_requests_multiple_assets(question):
    """
    Only use multi-asset mode when the wording clearly asks for more than one
    asset. This prevents a token/pair name such as 'FOREST X1X' from being
    split into two separate answers by accident.
    """
    q = f" {s(question).lower()} "

    strong_multi_markers = (
        " compare ",
        " compared ",
        " versus ",
        " vs ",
        " vs. ",
        " between ",
    )

    # Words such as "and" occur constantly in normal conceptual questions.
    # Never treat "and" by itself as proof of a multi-asset request.
    return any(marker in q for marker in strong_multi_markers)


def resolve_multiple_assets(question, pools, max_assets=4):
    """
    Resolve multiple distinct XDEX assets mentioned in one question.
    Example: "What's happening with AGI and XIX?"
    """
    terms = candidate_terms(question)
    found = []
    seen_assets = set()

    for term in terms:
        matches = find_matches_for_term(term, pools)

        # Routing requires an exact token name/symbol, mint, or pool address.
        # Ignore quality-60 substring matches from ordinary language.
        matches = [m for m in matches if m[3] >= 90]

        if not matches:
            continue

        matches.sort(
            key=lambda item: (
                item[3],
                n(item[0].get("liquidity")),
                n(item[0].get("volume24h")),
            ),
            reverse=True,
        )

        pool, side, asset, _quality = matches[0]
        if not asset:
            asset = pool.get("baseToken") or {}

        key = asset_key(asset) or f"term:{term.lower()}"
        if key in seen_assets:
            continue

        seen_assets.add(key)
        found.append((term, matches))

        if len(found) >= max_assets:
            break

    return found




def x1_rpc_request(method, params, retries=4):
    """Reliable X1 RPC request with retry/backoff."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    for attempt in range(retries):
        try:
            response = requests.post(
                SETTINGS.x1_rpc_url,
                json=payload,
                timeout=15,
            )

            if response.status_code == 429 or response.status_code >= 500:
                raise RuntimeError(
                    f"X1 RPC HTTP {response.status_code}"
                )

            response.raise_for_status()

            data = response.json()

            if data.get("error"):
                raise RuntimeError(data["error"])

            return data.get("result")

        except Exception as exc:
            if attempt == retries - 1:
                print(
                    f"X1 RPC {method} failed after "
                    f"{retries} attempts: {exc}"
                )
                return None

            time.sleep(0.75 * (2 ** attempt))


def get_token_total_supply(mint):
    """Return exact current token supply from X1 mainnet RPC."""
    mint = s(mint)
    if not mint:
        return None

    result = x1_rpc_request(
        "getTokenSupply",
        [mint],
    )

    value = (result or {}).get("value") or {}
    amount = s(value.get("uiAmountString"))

    return amount or None


def get_token_mint_info(mint):
    """Return verified X1 mint authority and current supply information."""
    mint = s(mint)
    if not mint:
        return None

    result = x1_rpc_request(
        "getAccountInfo",
        [
            mint,
            {"encoding": "jsonParsed"},
        ],
    )

    info = (
        (result or {})
        .get("value", {})
        .get("data", {})
        .get("parsed", {})
        .get("info", {})
    )

    if not info:
        return None

    raw_supply = s(info.get("supply"))
    decimals = int(info.get("decimals") or 0)

    supply = None

    if raw_supply:
        supply = str(
            Decimal(raw_supply)
            / (Decimal(10) ** decimals)
        )

    return {
        "mint_authority": info.get("mintAuthority"),
        "freeze_authority": info.get("freezeAuthority"),
        "supply": supply,
        "raw_supply": raw_supply,
        "decimals": decimals,
    }



def format_token_amount(value):
    """Add thousands separators without losing RPC decimal precision."""
    value = s(value)

    if not value:
        return ""

    whole, dot, fraction = value.partition(".")

    try:
        whole = f"{int(whole):,}"
    except ValueError:
        return value

    if dot:
        return f"{whole}.{fraction}"

    return whole

FIELD_ORDER = CORE_FIELD_ORDER


def requested_asset_fields(question):
    """Legacy-compatible adapter to reusable field-selection policy."""
    return core_requested_asset_fields(
        question,
        historical_comparison=bool(
            history.parse_historical_comparison(question)
        ),
        volume_rank=wants_volume_rank(question),
        historical_liquidity=wants_historical_liquidity(question),
    )


def format_field_line(field, snap):
    """Legacy-compatible adapter to reusable public field formatting."""
    return core_format_field_line(
        field,
        snap,
        format_usd=format_usd,
        get_total_supply=get_token_total_supply,
        get_mint_info=get_token_mint_info,
    )


def full_snapshot_lines(snap):
    """Legacy-compatible adapter to reusable default snapshot formatting."""
    return core_full_snapshot_lines(
        snap,
        format_usd=format_usd,
        get_total_supply=get_token_total_supply,
        get_mint_info=get_token_mint_info,
    )




def compact_asset_snapshot(term, matches, catalog):
    pool, side, asset, _quality = matches[0]
    if not asset:
        asset = pool.get("baseToken") or {}

    symbol = s(asset.get("symbol")) or term
    name = s(asset.get("name"))

    price_usd = n(pool.get("priceUsd"))
    # Public asset liquidity = total across all matching XDEX pools.
    # Keep strongest/primary pool liquidity separately for route/slippage analysis.
    primary_liquidity = n(pool.get("liquidity"))
    liquidity = sum(
        n(item[0].get("liquidity"))
        for item in matches
    )
    pool_count = len(matches)

    vol24 = n(pool.get("volume24h"))
    change1 = n(pool.get("priceChange1h"))
    change24 = n(pool.get("priceChange24h"))
    holders = int(n(pool.get("holders")))
    txns24 = int(n(pool.get("txns24h")))
    market_cap = n(pool.get("marketCap"))
    fdv = n(pool.get("fdv"))
    safety_grade = s(pool.get("safetyGrade")) or "N/A"
    safety_score = n(pool.get("safetyScore"))
    age = format_age(pool.get("createdAt"))

    is_xnt = symbol.upper() == "XNT" or term.upper() == "XNT"
    if is_xnt and catalog.xnt_price_usd is not None:
        price_value = n(catalog.xnt_price_usd)
        price_text = format_usd(price_value)
    else:
        price_value = price_usd
        price_text = format_usd(price_value)

    safety_text = safety_grade
    if safety_score > 0:
        safety_text += f" ({safety_score:g}/100)"

    if is_xnt:
        title = "XNT"
    else:
        title = symbol
        if name and name.upper() != symbol.upper():
            title += f" ({name})"

    return {
        "title": title,
        "symbol": symbol,
        "token_address": s(asset.get("mint") or asset.get("address")),
        "price": price_text,
        "price_usd_value": price_value,
        "age": age,
        "holders": holders,
        "txns24": txns24,
        "vol24": vol24,
        "change1": change1,
        "change24": change24,
        "liquidity": liquidity,
        "primary_liquidity": primary_liquidity,
        "pool_count": pool_count,
        "market_cap": market_cap,
        "fdv": fdv,
        "safety": safety_text,
        "pool": pair_name(pool),
        "pool_address": pool_address(pool),
    }




def asset_identity_lines(snap, question=None):
    """Visible asset identity without pool or token-address clutter."""
    return [
        snap["title"],
    ]


def format_multi_asset_answer(question, resolved_assets, catalog):
    fields = requested_asset_fields(question)
    snaps = []

    for term, matches in resolved_assets:
        snaps.append(
            compact_asset_snapshot(term, matches, catalog)
        )

    lines = ["Liquidity Scout XDEX comparison:"]

    # If the user requested specific fields, preserve the concise field-only mode.
    if fields:
        for i, snap in enumerate(snaps):
            if i:
                lines.append("")

            lines.extend(asset_identity_lines(snap, question))
            lines.extend(
                format_field_line(field, snap)
                for field in fields
            )

    else:
        # Default comparison view: show only the metrics that matter most
        # for market-structure comparison instead of dumping every field.
        for i, snap in enumerate(snaps):
            if i:
                lines.append("")

            liquidity_class = liquidity_depth_label(snap["liquidity"])
            volume_class = volume_activity_label(snap["vol24"])
            move_class = price_movement_label(snap["change24"])

            liquidity_text = format_usd(snap["liquidity"])
            if liquidity_class != "not qualitatively classified":
                liquidity_text += f" ({liquidity_class})"

            volume_text = format_usd(snap["vol24"])
            if volume_class != "not qualitatively classified":
                volume_text += f" ({volume_class})"

            lines.extend([
                snap["title"],
                f"• Price: {snap['price']}",
                f"• Liquidity: {liquidity_text}",
                f"• Volume 24h: {volume_text}",
                f"• Change 24h: {snap['change24']:+.2f}% ({move_class})",
                "• Market Cap: Not verified — "
                "circulating supply unavailable from verified data",
                f"• Tokenomics Safety: {snap['safety']}",
            ])

        if len(snaps) >= 2:
            by_volume = max(snaps, key=lambda x: x["vol24"])
            by_liquidity = max(snaps, key=lambda x: x["liquidity"])

            # Largest move means absolute magnitude, regardless of direction.
            largest_move = max(
                snaps,
                key=lambda x: abs(x["change24"])
            )

            # Best return means highest signed 24h percentage.
            best_return = max(
                snaps,
                key=lambda x: x["change24"]
            )

            lines.extend([
                "",
                "Analyst comparison:",
            ])

            if len(snaps) == 2:
                a, b = snaps

                # Liquidity comparison.
                liq_winner = a if a["liquidity"] >= b["liquidity"] else b
                liq_other = b if liq_winner is a else a

                if liq_other["liquidity"] > 0:
                    liq_ratio = (
                        liq_winner["liquidity"] /
                        liq_other["liquidity"]
                    )

                    lines.append(
                        f"• Liquidity: {liq_winner['symbol']} has "
                        f"{liq_ratio:.1f}× more available liquidity "
                        f"({format_usd(liq_winner['liquidity'])} vs "
                        f"{format_usd(liq_other['liquidity'])})."
                    )
                else:
                    lines.append(
                        f"• Liquidity: {liq_winner['symbol']} has deeper "
                        f"available liquidity "
                        f"({format_usd(liq_winner['liquidity'])} vs "
                        f"{format_usd(liq_other['liquidity'])})."
                    )

                # Volume comparison.
                vol_winner = a if a["vol24"] >= b["vol24"] else b
                vol_other = b if vol_winner is a else a

                if vol_other["vol24"] > 0:
                    vol_ratio = (
                        vol_winner["vol24"] /
                        vol_other["vol24"]
                    )

                    lines.append(
                        f"• Trading activity: {vol_winner['symbol']} has "
                        f"{vol_ratio:.1f}× more 24h volume "
                        f"({format_usd(vol_winner['vol24'])} vs "
                        f"{format_usd(vol_other['vol24'])})."
                    )
                else:
                    lines.append(
                        f"• Trading activity: {vol_winner['symbol']} has "
                        f"higher 24h volume "
                        f"({format_usd(vol_winner['vol24'])} vs "
                        f"{format_usd(vol_other['vol24'])})."
                    )

            else:
                lines.extend([
                    f"• Highest 24h volume: {by_volume['symbol']} "
                    f"({format_usd(by_volume['vol24'])})",
                    f"• Deepest liquidity: {by_liquidity['symbol']} "
                    f"({format_usd(by_liquidity['liquidity'])})",
                ])

            lines.extend([
                f"• Largest absolute 24h price move: "
                f"{largest_move['symbol']} "
                f"({largest_move['change24']:+.2f}%).",

                f"• Best 24h return: "
                f"{best_return['symbol']} "
                f"({best_return['change24']:+.2f}%).",

                "• Tokenomics: "
                + " • ".join(
                    f"{snap['symbol']} {snap['safety']}"
                    for snap in snaps
                ),
            ])

            # Explain execution implications from liquidity only.
            if len(snaps) == 2:
                a, b = snaps
                deeper = a if a["liquidity"] >= b["liquidity"] else b
                thinner = b if deeper is a else a

                if deeper["liquidity"] > thinner["liquidity"]:
                    lines.append(
                        f"• Execution: For similarly sized AMM trades, "
                        f"{deeper['symbol']}'s deeper available liquidity "
                        f"should generally reduce slippage and price-impact "
                        f"pressure relative to {thinner['symbol']}."
                    )

    if wants_token_address(question):
        lines.extend([
            "",
            "Token Addresses:",
        ])

        for snap in snaps:
            lines.append(
                f"• {snap['symbol']}: "
                f"{snap.get('token_address') or 'N/A'}"
            )

    return "\n".join(lines)


def resolve_asset(question, pools):
    """
    Return (query_term, matches).

    We choose the first candidate term that actually matches the XDEX catalog.
    This prevents a question like "What is SolXen doing today?" from
    accidentally falling back to AGI.
    """
    terms = candidate_terms(question)

    for term in terms:
        matches = find_matches_for_term(term, pools)

        # Do not let fuzzy substring matches turn normal crypto/DeFi words
        # into unrelated XDEX assets. Exact token matches score 90 and
        # exact pool-address matches score 100.
        matches = [m for m in matches if m[3] >= 90]

        if matches:
            matches.sort(
                key=lambda item: (
                    item[3],                       # match quality
                    n(item[0].get("liquidity")),  # strongest pool
                    n(item[0].get("volume24h")),
                ),
                reverse=True,
            )
            return term, matches

    return None, []


def describe_direction(change):
    if change >= 5:
        return "strongly up"
    if change >= 1:
        return "up"
    if change <= -5:
        return "strongly down"
    if change <= -1:
        return "down"
    return "roughly flat"



def format_usd(value):
    value = n(value)
    abs_v = abs(value)

    if abs_v == 0:
        return "$0"
    if abs_v >= 1_000_000_000:
        return f"${value/1_000_000_000:,.2f}B"
    if abs_v >= 1_000_000:
        return f"${value/1_000_000:,.2f}M"
    if abs_v >= 1_000:
        return f"${value:,.0f}"
    if abs_v >= 1:
        return f"${value:,.4f}".rstrip("0").rstrip(".")
    if abs_v >= 0.01:
        return f"${value:.4f}".rstrip("0").rstrip(".")
    if abs_v >= 0.0001:
        return f"${value:.6f}".rstrip("0").rstrip(".")
    return f"${value:.10f}".rstrip("0").rstrip(".")


def format_number(value):
    value = n(value)
    abs_v = abs(value)

    if abs_v >= 1_000_000_000:
        return f"{value/1_000_000_000:,.2f}B"
    if abs_v >= 1_000_000:
        return f"{value/1_000_000:,.2f}M"
    if abs_v >= 1_000:
        return f"{value/1_000:,.2f}K"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def asset_key(token):
    if not isinstance(token, dict):
        return None

    mint = s(token.get("mint") or token.get("address"))
    symbol = s(token.get("symbol"))
    name = s(token.get("name"))

    if mint:
        return mint
    if symbol:
        return f"symbol:{symbol.upper()}"
    if name:
        return f"name:{name.lower()}"
    return None


def aggregate_asset_activity(pools):
    """
    Build an XDEX-wide activity table for unique assets.

    Each pool's 24h volume is counted toward both assets participating in
    that pool. This represents how much XDEX pool activity an asset is
    involved in, rather than exchange-wide non-duplicated volume.
    """
    stats = {}

    for pool in pools:
        vol = n(pool.get("volume24h"))
        liq = n(pool.get("liquidity"))

        for token in (pool.get("baseToken") or {}, pool.get("quoteToken") or {}):
            key = asset_key(token)
            if not key:
                continue

            entry = stats.setdefault(
                key,
                {
                    "symbol": s(token.get("symbol")),
                    "name": s(token.get("name")),
                    "mint": s(token.get("mint") or token.get("address")),
                    "volume24h": 0.0,
                    "liquidity": 0.0,
                    "pools": 0,
                },
            )

            entry["volume24h"] += vol
            entry["liquidity"] += liq
            entry["pools"] += 1

    ranked = sorted(
        stats.values(),
        key=lambda item: item["volume24h"],
        reverse=True,
    )

    return ranked


def get_asset_rank(asset, catalog):
    key = asset_key(asset)
    if not key:
        return None

    ranked = aggregate_asset_activity(catalog.pools)

    for index, item in enumerate(ranked, 1):
        item_key = (
            item["mint"]
            if item["mint"]
            else f"symbol:{item['symbol'].upper()}"
            if item["symbol"]
            else f"name:{item['name'].lower()}"
        )

        if item_key == key:
            return {
                "rank": index,
                "total_assets": len(ranked),
                **item,
            }

    return None


def plain_language_summary(change24, liquidity, volume24, safety_grade):
    comments = []

    if change24 <= -10:
        comments.append("price is down sharply over the last 24 hours")
    elif change24 <= -3:
        comments.append("price is under noticeable selling pressure")
    elif change24 >= 10:
        comments.append("price is up sharply over the last 24 hours")
    elif change24 >= 3:
        comments.append("price has solid upward momentum")
    else:
        comments.append("price movement is relatively modest")

    if liquidity < 5_000:
        comments.append("liquidity is very thin")
    elif liquidity < 25_000:
        comments.append("liquidity is still fairly thin")
    elif liquidity >= 100_000:
        comments.append("liquidity is comparatively deep")

    if volume24 < 1_000:
        comments.append("trading activity is light")
    elif volume24 >= 25_000:
        comments.append("trading activity is strong")

    if safety_grade and safety_grade != "N/A":
        comments.append(f"the current tokenomics grade is {safety_grade}")

    if not comments:
        return "Market conditions are mixed."

    text = ", ".join(comments)
    return text[:1].upper() + text[1:] + "."



def xdex_ranking_metric(question):
    """Resolve the requested X1.Ninja/XDEX ranking metric."""
    q = s(question).lower()

    if (
        "trending" in q
        or "trend" in q
        or "most active" in q
    ):
        return "trending"

    if (
        "gainer" in q
        or "gainers" in q
        or "biggest gain" in q
        or "best performing" in q
    ):
        return "gainers"

    if (
        "loser" in q
        or "losers" in q
        or "biggest loss" in q
        or "worst performing" in q
    ):
        return "losers"

    if "liquidity" in q or re.search(r"\bliq\b", q):
        return "liquidity"

    if "holder" in q:
        return "holders"

    if (
        "safety" in q
        or "safest" in q
        or "safe tokens" in q
    ):
        return "safety"

    # Volume is the default XDEX activity ranking.
    return "volume"


def xdex_ranking_limit(question, default=10):
    q = s(question).lower()

    match = re.search(r"\btop\s+(\d+)\b", q)

    if not match:
        return default

    try:
        value = int(match.group(1))
    except ValueError:
        return default

    # Avoid enormous Signal replies.
    return max(1, min(value, 50))


def wants_global_xdex_ranking(question):
    """
    Global leaderboard requests such as:
      Top 10 by volume
      What are the top 20 tokens on XDEX?
      What's trending on X1.Ninja?
      Show me the biggest gainers
    """
    q = s(question).lower().strip()

    global_patterns = (
        r"^top\s+\d+",
        r"\bwhat are the top\s+\d+",
        r"\bshow me the top\s+\d+",
        r"\blist the top\s+\d+",
        r"\bgive me the top\s+\d+",
        r"\btop gainers\b",
        r"\bbiggest gainers\b",
        r"\btop losers\b",
        r"\bbiggest losers\b",
        r"\bsafest tokens\b",
        r"\btop safest\b",
        r"\bwhat tokens are trending\b",
        r"\bwhich tokens are trending\b",
        r"\bwhat is trending\b",
        r"\bwhat's trending\b",
    )

    return any(
        re.search(pattern, q)
        for pattern in global_patterns
    )


def wants_asset_rank(question):
    """
    Specific-asset ranking requests such as:
      Where does AGI rank by volume?
      What is X1X's liquidity rank?
      Is AGI in the top 50?
    """
    if wants_global_xdex_ranking(question):
        return False

    q = s(question).lower()

    return (
        bool(re.search(r"\brank(?:ed|ing)?\b", q))
        or bool(re.search(r"\bin\s+(?:the\s+)?top\s+\d+\b", q))
    )


def xdex_ranking_title(metric):
    return {
        "volume": "24h Volume",
        "liquidity": "Liquidity",
        "holders": "Holders",
        "safety": "Tokenomics Safety",
        "gainers": "24h Gainers",
        "losers": "24h Losers",
        "trending": "1h Trending",
    }.get(metric, metric)


def format_global_xdex_ranking_answer(question, catalog):
    metric = xdex_ranking_metric(question)
    limit = xdex_ranking_limit(question)

    return rankings.format_top(
        catalog.pools,
        metric=metric,
        limit=limit,
    )


def format_asset_rank_answer(question, term, matches, catalog):
    metric = xdex_ranking_metric(question)

    snap = compact_asset_snapshot(
        term,
        matches,
        catalog,
    )

    symbol = snap.get("symbol") or term
    mint = snap.get("token_address")
    lookup = mint or symbol

    asset_rank, total_ranked, meta = rankings.find_asset_rank(
        catalog.pools,
        lookup,
        metric=metric,
    )

    if not asset_rank:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"I found the asset on XDEX, but I could not calculate "
            f"a reliable {xdex_ranking_title(metric)} rank right now."
        )

    style = rankings.ranking_style(
        metric,
        meta,
    )

    lines = [
        f"{style['icon']} X1.NINJA / XDEX ASSET RANK",
        style["label"],
        "",
        rankings.ranking_header(
            metric,
            meta,
        ),
        rankings.ranking_separator(
            metric,
        ),
        rankings.ranking_row(
            asset_rank,
            metric,
            meta,
        ),
    ]

    top_match = re.search(
        r"\b(?:the\s+)?top\s+(\d+)\b",
        s(question).lower(),
    )

    if top_match:
        top_n = int(top_match.group(1))

        lines.extend([
            "",
            (
                f"TOP {top_n}: "
                f"{'YES' if asset_rank['rank'] <= top_n else 'NO'}"
            ),
        ])

    return "\n".join(lines)


def wants_volume_rank(question):
    q = s(question).lower()
    return (
        "volume" in q
        and any(word in q for word in ("rank", "ranking", "compared", "compare", "relative", "other assets"))
    )


def format_volume_rank_answer(question, term, matches, catalog):
    pool, side, asset, _quality = matches[0]

    if not asset:
        asset = pool.get("baseToken") or {}

    symbol = s(asset.get("symbol")) or term
    rank_data = get_asset_rank(asset, catalog)

    if not rank_data:
        return (
            "Liquidity Scout reply:\n"
            f"I found {symbol} on XDEX, but I could not calculate a reliable "
            "XDEX-wide volume rank for it right now."
        )

    rank = rank_data["rank"]
    total = rank_data["total_assets"]
    total_vol = rank_data["volume24h"]
    pools_count = rank_data["pools"]

    percentile = 100 * (1 - (rank - 1) / max(total, 1))

    if rank <= 10:
        tier = "one of the most actively traded assets on XDEX"
    elif rank <= max(25, int(total * 0.10)):
        tier = "in the upper tier of XDEX trading activity"
    elif rank <= int(total * 0.50):
        tier = "around the middle-to-upper part of XDEX activity"
    else:
        tier = "in the lower half of XDEX trading activity"

    price_usd = n(pool.get("priceUsd"))

    # Total liquidity across every matching pool for this asset.
    liquidity = sum(
        n(item[0].get("liquidity"))
        for item in matches
    )

    change1 = n(pool.get("priceChange1h"))
    change24 = n(pool.get("priceChange24h"))
    market_cap = n(pool.get("marketCap"))
    holders = int(n(pool.get("holders")))
    txns24 = int(n(pool.get("txns24h")))
    safety_grade = s(pool.get("safetyGrade")) or "N/A"
    safety_score = n(pool.get("safetyScore"))
    age = format_age(pool.get("createdAt"))

    is_xnt = symbol.upper() == "XNT" or term.upper() == "XNT"
    if is_xnt and catalog.xnt_price_usd is not None:
        headline_price = format_usd(catalog.xnt_price_usd)
    else:
        headline_price = format_usd(price_usd)

    safety_text = safety_grade
    if safety_score > 0:
        safety_text += f" ({safety_score:g}/100)"

    # Rank 5 out of 312 means roughly top 1.6%, not top 3%.
    top_pct = round((rank / total) * 100, 1) if total > 0 else 100.0

    token_address = s(asset.get("mint") or asset.get("address")) or "N/A"

    address_suffix = ""
    if wants_token_address(question):
        address_suffix = f"\n\nToken Address: {token_address}"

    return (
        "Liquidity Scout reply:\n"
        f"{symbol}\n"
        f"{symbol} ranks #{rank} out of {total} XDEX assets by 24h pool volume.\n\n"
        f"• Price: {headline_price}\n"
        f"• Age: {age}\n"
        f"• Holders: {holders:,}\n"
        f"• Transactions 24h: {txns24:,}\n"
        f"• Volume 24h: {format_usd(total_vol)}\n"
        f"• Change 1h: {change1:+.2f}%\n"
        f"• Change 24h: {change24:+.2f}%\n"
        f"• Liquidity: {format_usd(liquidity)} • Pools: {pools_count}\n"
        "• Market Cap: Not verified — "
        "circulating supply unavailable from verified data\n"
        f"• Tokenomics Safety: {safety_text}\n\n"
        f"Bottom line: {symbol} is {tier}, currently around the top {top_pct}% "
        f"of XDEX assets by 24h volume. It appears in {pools_count} XDEX "
        f"pool{'s' if pools_count != 1 else ''}."
        f"{address_suffix}"
    )


def format_historical_comparison_answer(
    question,
    term,
    matches,
    catalog,
):
    request = history.parse_historical_comparison(question)

    if not request:
        return None

    snap = compact_asset_snapshot(
        term,
        matches,
        catalog,
    )

    metric = request["metric"]
    period = request["period"]
    period_seconds = request["period_seconds"]

    mint = snap.get("token_address")
    symbol = snap.get("symbol") or term

    if not period_seconds:
        return (
            f"Liquidity Scout reply: {symbol} • "
            "Please specify a comparison period such as "
            "24h, 7d, or 30d."
        )

    current_map = {
        "price": n(snap.get("price_usd_value")),
        "liquidity": n(snap.get("liquidity")),
        "volume": n(snap.get("vol24")),
        "holders": n(snap.get("holders")),
    }

    # Supply is retrieved from verified X1 RPC.
    if metric == "supply":
        amount = get_token_total_supply(mint)
        current_value = (
            float(amount)
            if amount
            else None
        )
    else:
        current_value = current_map.get(metric)

    # Burn percentage comparisons will use the verified burn DB
    # in the next burn-integration step.
    if metric == "burns":
        return (
            f"Liquidity Scout reply: {symbol} • "
            "Historical burn percentage comparisons are not yet "
            "enabled in the live listener. Verified burn history "
            "is maintained separately by the X1 burn scanner."
        )

    if current_value is None:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Current {metric} data is not available from a "
            "verified source."
        )

    # Always store the current observation.
    history.record_snapshot(
        mint=mint,
        symbol=symbol,
        price=n(snap.get("price_usd_value")),
        liquidity=n(snap.get("liquidity")),
        volume24=n(snap.get("vol24")),
        holders=n(snap.get("holders")),
        total_supply=(
            current_value
            if metric == "supply"
            else None
        ),
        pool_count=snap.get("pool_count"),
    )

    old = history.historical_value(
        mint,
        metric,
        period_seconds,
    )

    if not old:
        current_text = history.format_number(
            metric,
            current_value,
        )

        return (
            history.history_not_ready_message(
                symbol,
                metric,
                period,
                mint,
            )
            + f" Current {metric}: {current_text}."
        )

    old_value = old["value"]

    change = history.percent_change(
        old_value,
        current_value,
    )

    if change is None:
        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Historical {metric} percentage change cannot "
            "be calculated because the earlier value was zero."
        )

    current_text = history.format_number(
        metric,
        current_value,
    )

    old_text = history.format_number(
        metric,
        old_value,
    )

    answer = (
        f"Liquidity Scout reply: {symbol} • "
        f"Current {metric}: {current_text} "
        f"• {period} ago: {old_text} "
        f"• Change: {change:+.2f}%"
    )

    threshold = request.get("threshold")
    direction = request.get("direction")

    if threshold is not None:
        result = history.threshold_result(
            change,
            direction,
            threshold,
        )

        if result is not None:
            direction_text = (
                "decline"
                if direction == "down"
                else "increase"
                if direction == "up"
                else "change"
            )

            answer += (
                f" • {direction_text.title()} of at least "
                f"{threshold:g}%: "
                f"{'YES' if result else 'NO'}"
            )

    return answer


def format_pool_answer(question, term, matches, catalog):
    historical_answer = format_historical_comparison_answer(
        question,
        term,
        matches,
        catalog,
    )

    if historical_answer:
        return historical_answer

    if wants_asset_rank(question):
        return format_asset_rank_answer(
            question,
            term,
            matches,
            catalog,
        )

    snap = compact_asset_snapshot(term, matches, catalog)
    fields = requested_asset_fields(question)

    lines = [
        "Liquidity Scout reply:",
        *asset_identity_lines(snap, question),
        "",
    ]

    if wants_token_address(question):
        lines.extend([
            f"• Token Address: {snap.get('token_address') or 'N/A'}",
        ])
        return "\n".join(lines)

    if fields:
        # Specific request: return only the fields requested.
        lines.extend(
            format_field_line(field, snap)
            for field in fields
        )

        return "\n".join(lines)

    # General asset request.
    lines.extend(full_snapshot_lines(snap))

    lines.extend([
        "",
        "Bottom line: "
        + plain_language_summary(
            snap["change24"],
            snap["liquidity"],
            snap["vol24"],
            snap["safety"].split(" ")[0],
        ),
    ])

    if len(matches) > 1:
        lines.append(
            f"I found {len(matches)} matching XDEX pools and used "
            "the strongest match by liquidity/volume."
        )

    return "\n".join(lines)


def format_not_found(question):
    return (
        "Liquidity Scout reply:\n"
        "I couldn't find a matching XDEX asset for that request.\n\n"
        "Try the token symbol or full name — for example:\n"
        "• What is XNT doing?\n"
        "• Tell me about ANL\n"
        "• How does AGI rank by volume?\n\n"
        "I won't substitute a different token when I can't identify the one you asked about."
    )


def post_visible_reply(parent_signal_id, content):
    r = requests.post(
        MOLTGRID_URL,
        json={
            "wallet": SETTINGS.agent_wallet,
            "content": content,
            "name": BOT_NAME,
            "type": "agent",
            # Attach to the original Signal, not a nested child reply.
            "replyTo": parent_signal_id,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def process_cycle(catalog, implicit_mode_started_at):
    """
    Hybrid routing:

    Route 1 — Specific asset data:
        deterministic XDEX output only.

    Route 2 — Full asset report:
        deterministic XDEX output only.

    Route 3 — Asset analysis:
        deterministic XDEX lookup first, AI interprets second.

    Route 4 — General crypto/X1/DeFi:
        conversational AI, with no invented XDEX live data.
    """
    catalog.refresh_if_needed()

    posts = fetch_signal_posts()
    thread_reply_mode_started_at = ensure_thread_reply_mode_start()

    pending = find_unanswered_messages(
        posts,
        catalog,
        implicit_mode_started_at,
        thread_reply_mode_started_at,
    )

    if not pending:
        return

    answered = load_answered()

    for post, message_type, pre_term, pre_matches in pending[:5]:
        post_id = str(post["id"])
        question = s(post.get("content"))
        sender = post.get("name") or post.get("wallet")

        if message_type.startswith("standalone"):
            reply_target_id = post_id
        else:
            reply_target_id = str(post.get("replyTo"))

        print()
        print("=" * 72)
        print(f"New {message_type} message from: {sender}")
        print(f"Message: {question}")

        # Agent identity / HXMP questions always take priority over
        # fuzzy XDEX asset resolution.
        if wants_global_xdex_ranking(question):
            metric = xdex_ranking_metric(question)
            print(
                "Route: GLOBAL XDEX RANKING | "
                f"metric: {metric}"
            )
            answer = format_global_xdex_ranking_answer(
                question,
                catalog,
            )

        elif looks_like_agent_identity_question(question):
            print("Route 4: AGENT IDENTITY / HXMP QUESTION")
            answer = format_hxmp_identity_answer(question)

        else:
            # Preserve v11 multi-asset behavior.
            if explicitly_requests_multiple_assets(question):
                multi = resolve_multiple_assets(question, catalog.pools)
            else:
                multi = []

            if len(multi) >= 2:
                names = ", ".join(term for term, _ in multi)
                print(f"Route: MULTI-ASSET DATA | detected: {names}")
                answer = format_multi_asset_answer(question, multi, catalog)

            else:
                if pre_matches:
                    term, matches = pre_term, pre_matches
                elif multi:
                    term, matches = multi[0]
                else:
                    term, matches = resolve_asset(question, catalog.pools)

                if matches:
                    if wants_asset_analysis(question):
                        print(f"Route 3: ASSET ANALYSIS | asset: {term}")
                        answer = format_asset_analysis_answer(
                            question, term, matches, catalog
                        )
                    else:
                        fields = requested_asset_fields(question)

                        if fields:
                            print(
                                "Route 1: SPECIFIC ASSET DATA | "
                                f"asset: {term} | fields: {', '.join(fields)}"
                            )
                        else:
                            print(
                                f"Route 2: FULL ASSET REPORT | asset: {term}"
                            )

                        answer = format_pool_answer(
                            question, term, matches, catalog
                        )

                else:
                    print("Route 4: GENERAL CRYPTO/X1/DEFI QUESTION")
                    answer = format_general_answer(question)

        result = post_visible_reply(reply_target_id, answer)
        created = result.get("post", {}) if isinstance(result, dict) else {}
        returned_reply_to = str(created.get("replyTo") or "")

        if returned_reply_to == reply_target_id:
            answered.add(post_id)
            save_answered(answered)
            print(f"Answered successfully on Signal. Post ID: {created.get('id')}")
        else:
            print("WARNING: reply linkage was not confirmed.")
            print("Stopping this cycle to avoid duplicate replies.")
            break


def main():
    if not SETTINGS.agent_wallet:
        raise SystemExit("ERROR: AGENT_WALLET is missing from .env")

    if not SETTINGS.api_key:
        raise SystemExit("ERROR: X1_NINJA_API_KEY is missing from .env")

    hxmp_memory = initialize_hxmp_memory()

    catalog = XDEXCatalog()

    print("Liquidity Scout v0.12 — Hybrid XDEX + DeepSeek Signal Listener")
    print(f"Polling MoltGrid every {POLL_SECONDS} seconds")
    print(f"Refreshing XDEX catalog every {CATALOG_REFRESH_SECONDS} seconds")
    print("Asset scope: full XDEX pool catalog")
    print("Input: replies + explicit Signals + owner asset/general questions")
    print(f"Primary LLM: DeepSeek V4 Flash ({DEEPSEEK_MODEL})")
    print(
        "DeepSeek cloud: "
        + ("ON" if DEEPSEEK_API_KEY else "OFF")
    )
    print(
        "Local fallback: "
        + (f"ON ({AI_MODEL})" if ai_available() else "OFF")
    )
    print("Live XDEX facts: deterministic only")

    if hxmp_memory:
        print(
            "HXMP memory: VERIFIED "
            f"(sequence {hxmp_memory.get('sequence')}, "
            f"{hxmp_memory.get('sha256')})"
        )
    else:
        print("HXMP memory: OFF — built-in prompts active")

    print("Trading: disabled in this listener")
    print("Press Ctrl+C to stop.")
    print()

    # Load catalog immediately so startup problems appear now, not later.
    catalog.refresh()

    implicit_mode_started_at = ensure_implicit_mode_start()
    print(
        "Implicit owner asset-question mode active since: "
        f"{implicit_mode_started_at.isoformat()}"
    )

    while True:
        try:
            process_cycle(catalog, implicit_mode_started_at)
        except KeyboardInterrupt:
            print("\nLiquidity Scout XDEX listener stopped.")
            break
        except Exception as exc:
            print(f"Listener error: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
