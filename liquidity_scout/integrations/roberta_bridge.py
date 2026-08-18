"""Opt-in local Roberta bridge client for the MoltGrid transport.

This module is transport-only. It forwards the user's message to Roberta and
returns Roberta's final reply. It does not call CMIS/provider internals or
recompute market/risk facts.

MoltGrid can also be placed in a conservative ``simple-only`` presentation
mode. In that mode, concise conversational and single-fact questions continue
to Roberta while requests that normally require long structured output receive
a short professional interface-limitation response instead. Roberta replies
that do pass the channel policy are rendered as plain text so MoltGrid never
needs to interpret Markdown correctly.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

DEFAULT_BASE_URL = "http://127.0.0.1:8766"
DEFAULT_TIMEOUT_SECONDS = 60.0

MOLTGRID_SCOPE_LIMITATION_MESSAGE = (
    "Thank you for your question. This request requires more detailed analysis "
    "or formatting than MoltGrid's current messaging interface can reliably "
    "support. To preserve accuracy and readability, I'm unable to provide that "
    "analysis on this site at this time. I can still help here with general "
    "questions and concise information."
)

_MOLTGRID_ADVANCED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bversus\b",
        r"\bvs\.?\b",
        r"\btop\s+\d+\b",
        r"\brank(?:ing|ed|s)?\b",
        r"\btrending\b",
        r"\bgainers?\b",
        r"\blosers?\b",
        r"\bhistorical\b",
        r"\bhistory\b",
        r"\byesterday\b",
        r"\blast\s+(?:week|month|year)\b",
        r"\bover\s+the\s+last\b",
        r"\bchanged\s+over\b",
        r"\bpre[- ]?trade\b",
        r"\bslippage\b",
        r"\bprice\s+impact\b",
        r"\broute\s+quality\b",
        r"\btransaction\s+simulation\b",
        r"\brisk\s+(?:analysis|assessment|report|check)\b",
        r"\bsafety\s+(?:analysis|assessment|report)\b",
        r"\bdetailed\b",
        r"\bin[- ]depth\b",
        r"\bdeep\s+dive\b",
        r"\bfull\s+report\b",
        r"\bcomplete\s+report\b",
        r"\braw\s+(?:data|output|cmis|evidence|report)\b",
        r"\bverification\s+evidence\b",
        r"\btechnical\s+(?:analysis|diagnostics?|details?|report)\b",
        r"\bdiagnostic(?:s)?\b",
        r"\b(?:markdown|ascii)\s+table\b",
        r"\bcsv\b",
        r"\bjson\b",
        r"\bsource\s+code\b",
        r"\bpython\s+code\b",
        r"\bwrite\s+(?:me\s+)?code\b",
    )
)

_MOLTGRID_TRADE_ADVICE_PATTERN = re.compile(
    r"\b(?:should\s+i|can\s+i|is\s+it\s+(?:ok|okay|safe)\s+to|would\s+you)\b"
    r".{0,80}\b(?:buy|purchase|sell|trade)\b",
    re.IGNORECASE,
)
_MOLTGRID_TRADE_AMOUNT_PATTERN = re.compile(
    r"\b(?:buy|purchase|sell)\b.{0,80}"
    r"(?:\$\s*\d|\busd\b|\bdollars?\b|\b\d+(?:\.\d+)?\b)",
    re.IGNORECASE,
)


class RobertaBridgeError(RuntimeError):
    """Raised when the local Roberta bridge cannot return a trusted reply."""


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def roberta_pretrade_enabled() -> bool:
    """Return whether MoltGrid pre-trade handoff to Roberta is explicitly enabled."""
    return _env_flag("ROBERTA_MOLTGRID_PRETRADE_ENABLED", default=False)


def roberta_conversation_enabled() -> bool:
    """Return whether MoltGrid general/identity handoff to Roberta is enabled."""
    return _env_flag("ROBERTA_MOLTGRID_CONVERSATION_ENABLED", default=False)


def roberta_all_questions_enabled() -> bool:
    """Return whether every admitted MoltGrid question must go to Roberta first."""
    return _env_flag("ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED", default=False)


def moltgrid_simple_only_enabled() -> bool:
    """Return whether MoltGrid should restrict replies to concise question types."""
    return _env_flag("ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED", default=False)


def moltgrid_question_supported(message: str) -> bool:
    """Return whether a message fits the current concise MoltGrid interface scope.

    This is intentionally conservative. It is a presentation/channel policy,
    not a statement about Roberta's underlying capabilities.
    """
    text = " ".join(str(message or "").strip().split())
    if not text:
        return False
    if len(text) > 360:
        return False
    if _MOLTGRID_TRADE_ADVICE_PATTERN.search(text):
        return False
    if _MOLTGRID_TRADE_AMOUNT_PATTERN.search(text):
        return False
    return not any(pattern.search(text) for pattern in _MOLTGRID_ADVANCED_PATTERNS)


def moltgrid_plaintext_reply(reply: str) -> str:
    """Convert a concise Roberta reply into MoltGrid-safe plain text.

    MoltGrid currently displays Markdown markers literally. This function only
    removes presentation syntax; it does not summarize, reinterpret, round, or
    otherwise alter deterministic facts in Roberta's answer.
    """
    text = str(reply or "").strip()
    if not text:
        return text

    # Remove fenced-code markers and heading syntax without changing content.
    # Horizontal whitespace is matched deliberately so blank lines survive.
    text = re.sub(r"(?m)^[ \t]*```[^\n]*\n?", "", text)
    text = text.replace("```", "")
    text = re.sub(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+", "", text)

    # Preserve linked destinations as plain text instead of relying on Markdown.
    text = re.sub(
        r"\[([^\]\n]+)\]\(([^)\n]+)\)",
        r"\1 (\2)",
        text,
    )

    # Strip common inline Markdown decoration while preserving the enclosed text.
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)

    # Unicode bullets remain readable even if MoltGrid collapses line breaks.
    text = re.sub(r"(?m)^[ \t]*[-*+][ \t]+", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _base_url(value: str | None = None) -> str:
    raw = value if value is not None else os.getenv("ROBERTA_BASE_URL", DEFAULT_BASE_URL)
    text = str(raw or "").strip().rstrip("/")
    if not text:
        raise RobertaBridgeError("ROBERTA_BASE_URL is empty.")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RobertaBridgeError("ROBERTA_BASE_URL must be an absolute HTTP(S) URL.")
    return text


def _timeout_seconds(value: float | None = None) -> float:
    if value is not None:
        timeout = float(value)
    else:
        raw = os.getenv("ROBERTA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout = float(raw)
        except ValueError as exc:
            raise RobertaBridgeError("ROBERTA_TIMEOUT_SECONDS must be numeric.") from exc
    if timeout <= 0:
        raise RobertaBridgeError("ROBERTA_TIMEOUT_SECONDS must be greater than zero.")
    return timeout


def ask_roberta(
    message: str,
    *,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
    api_key: str | None = None,
) -> str:
    """Send one exact user message to Roberta's local bridge and return its reply."""
    user_text = str(message or "").strip()
    if not user_text:
        raise RobertaBridgeError("A non-empty user message is required.")

    simple_only = moltgrid_simple_only_enabled()
    if simple_only and not moltgrid_question_supported(user_text):
        return MOLTGRID_SCOPE_LIMITATION_MESSAGE

    url = f"{_base_url(base_url)}/v1/roberta"
    body = json.dumps(
        {"message": user_text},
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    token = str(
        api_key if api_key is not None else os.getenv("ROBERTA_API_KEY", "")
    ).strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(
            request,
            timeout=_timeout_seconds(timeout_seconds),
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RobertaBridgeError(f"Roberta bridge returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RobertaBridgeError("Roberta bridge is unavailable.") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RobertaBridgeError("Roberta bridge returned invalid JSON.") from exc
    if not isinstance(payload, Mapping):
        raise RobertaBridgeError("Roberta bridge returned an invalid response object.")
    if payload.get("service") != "roberta_bridge" or payload.get("status") != "ok":
        raise RobertaBridgeError("Roberta bridge did not return an OK service envelope.")
    reply = payload.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise RobertaBridgeError("Roberta bridge returned no assistant reply.")

    answer = reply.strip()
    return moltgrid_plaintext_reply(answer) if simple_only else answer


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "MOLTGRID_SCOPE_LIMITATION_MESSAGE",
    "RobertaBridgeError",
    "ask_roberta",
    "moltgrid_plaintext_reply",
    "moltgrid_question_supported",
    "moltgrid_simple_only_enabled",
    "roberta_all_questions_enabled",
    "roberta_conversation_enabled",
    "roberta_pretrade_enabled",
]
