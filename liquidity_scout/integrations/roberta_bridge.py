"""Opt-in local Roberta bridge client for the MoltGrid transport.

This module is transport-only. It forwards the user's message to Roberta and
returns Roberta's final reply. It does not call CMIS/provider internals or
recompute market/risk facts.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

DEFAULT_BASE_URL = "http://127.0.0.1:8766"
DEFAULT_TIMEOUT_SECONDS = 60.0


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
    return reply.strip()


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "RobertaBridgeError",
    "ask_roberta",
    "roberta_pretrade_enabled",
]
