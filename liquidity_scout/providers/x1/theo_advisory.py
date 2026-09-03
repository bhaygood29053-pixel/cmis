"""Bounded Theo Prime advisory-provider connection foundation for CMIS.

Theo is an external X1 AI agent, not a CMIS trust root.  This module defines
the connection boundary before any live transport is accepted.

A transport contract qualifies only the channel/remote identity semantics.
It never upgrades Theo's returned text into verified blockchain, market, risk,
bridge, backing, custody, or execution facts.

The production transport registry intentionally starts empty.  A separate
evidence PR must establish the exact machine transport before a live call can
be made through this adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from typing import Any


CHAIN = "x1"
NETWORK = "x1-mainnet"
THEO_PROVIDER_ID = "theo_prime"
THEO_ADVISORY_CONTRACT = "theo_advisory_observation/v1"

# Promotion-safe by default.  Do not add a live entry until the exact Theo
# machine transport, remote identity, request contract, and response contract
# have passed a separate evidence/CI gate.
#
# Expected shape:
# {
#   "contract_id": {
#       "provider": "theo_prime",
#       "transport": "...",
#       "remote_identity": "...",
#       "request_contract": "...",
#       "response_contract": "...",
#   }
# }
ACCEPTED_THEO_TRANSPORT_CONTRACTS: dict[str, dict[str, str]] = {}


class TheoAdvisoryError(RuntimeError):
    """Raised when a Theo advisory request cannot be safely accepted."""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_number(value: Any, field: str) -> int | float:
    if isinstance(value, bool):
        raise TheoAdvisoryError(f"{field} must be a positive numeric timestamp.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TheoAdvisoryError(
            f"{field} must be a positive numeric timestamp."
        ) from exc
    if parsed <= 0:
        raise TheoAdvisoryError(f"{field} must be a positive numeric timestamp.")
    if parsed.is_integer():
        return int(parsed)
    return parsed


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _registry(
    accepted_contracts: Mapping[str, Mapping[str, str]] | None,
) -> Mapping[str, Mapping[str, str]]:
    return (
        ACCEPTED_THEO_TRANSPORT_CONTRACTS
        if accepted_contracts is None
        else accepted_contracts
    )


def theo_connection_status(
    *,
    transport_contract_id: Any,
    transport: Any,
    remote_identity: Any,
    accepted_contracts: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Classify one proposed Theo transport without performing network I/O."""

    contract_id = _text(transport_contract_id)
    transport_name = _text(transport)
    identity = _text(remote_identity)
    contracts = _registry(accepted_contracts)

    spec = contracts.get(contract_id or "")
    contract_verified = bool(
        spec
        and spec.get("provider") == THEO_PROVIDER_ID
        and spec.get("transport") == transport_name
        and spec.get("remote_identity") == identity
        and _text(spec.get("request_contract"))
        and _text(spec.get("response_contract"))
    )

    return {
        "contract": "theo_transport_status/v1",
        "chain": CHAIN,
        "network": NETWORK,
        "provider": THEO_PROVIDER_ID,
        "transport_contract_id": contract_id,
        "transport": transport_name,
        "remote_identity": identity,
        "transport_contract_verified": contract_verified,
        "state": (
            "connection_ready"
            if contract_verified
            else "blocked_transport_contract"
        ),
        "factual_authority": False,
        "cmis_promotable": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def require_accepted_theo_transport(
    *,
    transport_contract_id: Any,
    transport: Any,
    remote_identity: Any,
    accepted_contracts: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, str]:
    """Return the exact accepted transport spec or fail before any send."""

    status = theo_connection_status(
        transport_contract_id=transport_contract_id,
        transport=transport,
        remote_identity=remote_identity,
        accepted_contracts=accepted_contracts,
    )
    if not status["transport_contract_verified"]:
        raise TheoAdvisoryError(
            "Theo transport is not accepted; refusing advisory network activity."
        )

    spec = _registry(accepted_contracts)[status["transport_contract_id"]]
    return dict(spec)


def _normalize_reply(
    raw_reply: Any,
    *,
    expected_remote_identity: str,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(raw_reply, Mapping):
        raise TheoAdvisoryError(
            "Theo transport reply must be a normalized JSON-like mapping."
        )

    remote_identity = _text(raw_reply.get("remote_identity"))
    if remote_identity != expected_remote_identity:
        raise TheoAdvisoryError(
            "Theo transport reply remote identity does not match the accepted contract."
        )

    reply_text = _text(raw_reply.get("text"))
    if not reply_text:
        raise TheoAdvisoryError("Theo transport reply is missing non-empty text.")

    return reply_text, dict(raw_reply)


def collect_theo_advisory(
    *,
    query: Any,
    transport_contract_id: Any,
    transport: Any,
    remote_identity: Any,
    collected_at: Any,
    send: Callable[[dict[str, Any]], Any],
    accepted_contracts: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Collect one advisory response through an already-accepted Theo transport.

    The transport callable is injected so the CMIS trust contract is independent
    of X, xChat, Telegram, HTTP, or any future delivery mechanism.  Production
    code cannot call it while the accepted transport registry is empty.
    """

    query_text = _text(query)
    if not query_text:
        raise TheoAdvisoryError("Theo advisory query must be non-empty.")

    if not callable(send):
        raise TheoAdvisoryError("Theo advisory send transport must be callable.")

    contract_id = _text(transport_contract_id)
    transport_name = _text(transport)
    identity = _text(remote_identity)
    if not contract_id or not transport_name or not identity:
        raise TheoAdvisoryError(
            "Theo transport contract id, transport, and remote identity are required."
        )

    spec = require_accepted_theo_transport(
        transport_contract_id=contract_id,
        transport=transport_name,
        remote_identity=identity,
        accepted_contracts=accepted_contracts,
    )
    observed_at = _positive_number(collected_at, "collected_at")

    request = {
        "provider": THEO_PROVIDER_ID,
        "transport": transport_name,
        "remote_identity": identity,
        "request_contract": spec["request_contract"],
        "query": query_text,
    }

    raw_reply = send(dict(request))
    reply_text, normalized_reply = _normalize_reply(
        raw_reply,
        expected_remote_identity=identity,
    )

    query_hash = _canonical_hash(query_text)
    reply_hash = _canonical_hash(reply_text)
    advisory_id = "tao_" + _canonical_hash(
        {
            "transport_contract_id": contract_id,
            "transport": transport_name,
            "remote_identity": identity,
            "query_hash_sha256": query_hash,
            "reply_hash_sha256": reply_hash,
            "collected_at": observed_at,
        }
    )[:32]

    return {
        "contract": THEO_ADVISORY_CONTRACT,
        "advisory_id": advisory_id,
        "chain": CHAIN,
        "network": NETWORK,
        "provider": THEO_PROVIDER_ID,
        "transport_contract_id": contract_id,
        "transport": transport_name,
        "remote_identity": identity,
        "request_contract": spec["request_contract"],
        "response_contract": spec["response_contract"],
        "transport_contract_verified": True,
        "remote_identity_contract_matched": True,
        "query": query_text,
        "query_hash_sha256": query_hash,
        "advisory_text": reply_text,
        "reply_hash_sha256": reply_hash,
        "collected_at": observed_at,
        "provider_reply_metadata": {
            key: value
            for key, value in normalized_reply.items()
            if key not in {"text"}
        },
        "status": "observed_unverified",
        "advisory_claims_verified": False,
        "factual_authority": False,
        "market_fact_authority": False,
        "risk_authority": False,
        "bridge_fact_authority": False,
        "backing_fact_authority": False,
        "custody_fact_authority": False,
        "source_independence_verified": False,
        "cmis_promotable": False,
        "scout_reliance_promoted": False,
        "analysis_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "ACCEPTED_THEO_TRANSPORT_CONTRACTS",
    "CHAIN",
    "NETWORK",
    "THEO_ADVISORY_CONTRACT",
    "THEO_PROVIDER_ID",
    "TheoAdvisoryError",
    "collect_theo_advisory",
    "require_accepted_theo_transport",
    "theo_connection_status",
]
