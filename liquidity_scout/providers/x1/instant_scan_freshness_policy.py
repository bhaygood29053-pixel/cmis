"""Accepted X1 Instant X1 Scan current-market freshness policy.

The policy is explicit repository-owned governance. It separates CMIS collection
recency from provider fact-time freshness and has no hidden production defaults.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping


_POLICY_FILE = Path(__file__).with_name("instant_scan_freshness_policy.json")


def _integer(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def _positive_tolerance(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("price_relative_tolerance must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("price_relative_tolerance must be numeric") from exc
    if not math.isfinite(parsed) or not 0 <= parsed <= 0.05:
        raise ValueError("price_relative_tolerance must be between 0 and 0.05")
    return parsed


def _required_text(value: Any, *, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def normalize_instant_scan_freshness_policy(
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ValueError("Instant X1 Scan freshness policy must be a mapping")
    return {
        "policy_id": _required_text(policy.get("policy_id"), name="policy_id"),
        "max_collection_age_seconds": _integer(
            policy.get("max_collection_age_seconds"),
            name="max_collection_age_seconds",
        ),
        "collection_age_provenance": _required_text(
            policy.get("collection_age_provenance"),
            name="collection_age_provenance",
        ),
        "max_price_fact_age_seconds": _integer(
            policy.get("max_price_fact_age_seconds"),
            name="max_price_fact_age_seconds",
        ),
        "price_fact_age_provenance": _required_text(
            policy.get("price_fact_age_provenance"),
            name="price_fact_age_provenance",
        ),
        "max_future_skew_seconds": _integer(
            policy.get("max_future_skew_seconds"),
            name="max_future_skew_seconds",
        ),
        "future_skew_provenance": _required_text(
            policy.get("future_skew_provenance"),
            name="future_skew_provenance",
        ),
        "price_relative_tolerance": _positive_tolerance(
            policy.get("price_relative_tolerance")
        ),
        "price_tolerance_provenance": _required_text(
            policy.get("price_tolerance_provenance"),
            name="price_tolerance_provenance",
        ),
        "policy_complete": True,
        "has_hidden_defaults": False,
    }


def accepted_instant_scan_freshness_policy() -> dict[str, Any]:
    raw = json.loads(_POLICY_FILE.read_text(encoding="utf-8"))
    return normalize_instant_scan_freshness_policy(raw)


__all__ = [
    "accepted_instant_scan_freshness_policy",
    "normalize_instant_scan_freshness_policy",
]
