"""Provider-infrastructure health checks for the official X1 API.

The health endpoint describes ``api.x1.xyz`` service health. It must not be
interpreted as blockchain health, market health, or asset safety.
"""

from typing import Any, Dict

import requests


CHAIN = "x1"
HEALTH_URL = "https://api.x1.xyz/v1/health"
HEALTH_SOURCE = "api.x1.xyz /v1/health"


class X1HealthAPIError(RuntimeError):
    """Raised when X1 API infrastructure health cannot be verified."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def parse_health(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise X1HealthAPIError("X1 API health response must be a JSON object.")

    status = _text(payload.get("status")).lower()
    if not status:
        raise X1HealthAPIError("X1 API health response is missing status.")

    info = payload.get("info", {})
    error = payload.get("error", {})
    details = payload.get("details", {})
    if not isinstance(info, dict) or not isinstance(error, dict) or not isinstance(details, dict):
        raise X1HealthAPIError("X1 API health detail fields must be JSON objects.")

    return {
        "status": status,
        "operational": status == "ok",
        "info": dict(info),
        "error": dict(error),
        "details": dict(details),
    }


def fetch_health(
    *,
    url: str = HEALTH_URL,
    timeout: int = 15,
    get=requests.get,
) -> Dict[str, Any]:
    url = _text(url)
    if not url:
        raise ValueError("X1 health URL is required.")

    try:
        response = get(
            url,
            headers={"accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        parsed = parse_health(response.json())
    except X1HealthAPIError:
        raise
    except Exception as exc:
        raise X1HealthAPIError(f"X1 API health request failed: {exc}") from exc

    return {
        "chain": CHAIN,
        "provider": "api.x1.xyz",
        "status": parsed["status"],
        "operational": parsed["operational"],
        "info": parsed["info"],
        "error": parsed["error"],
        "details": parsed["details"],
        "source": HEALTH_SOURCE,
        "observed_at": None,
        "scope": "provider_infrastructure",
    }


class X1HealthProvider:
    """Explicit facade for X1 API infrastructure-health observations."""

    chain = CHAIN
    source = HEALTH_SOURCE

    def __init__(self, *, url: str = HEALTH_URL, timeout: int = 15, get=requests.get):
        self.url = _text(url)
        self.timeout = timeout
        self.get = get
        if not self.url:
            raise ValueError("X1 health URL is required.")

    def get_health(self) -> Dict[str, Any]:
        return fetch_health(url=self.url, timeout=self.timeout, get=self.get)


__all__ = [
    "CHAIN",
    "HEALTH_SOURCE",
    "HEALTH_URL",
    "X1HealthAPIError",
    "X1HealthProvider",
    "fetch_health",
    "parse_health",
]
