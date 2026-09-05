"""Deterministic X1 Explorer route/entity discovery beneath CMIS Web Discovery.

This module interprets only the route syntax and public implementation evidence
of the official X1 Explorer. It does not treat an explorer route, page label,
repository implementation, or rendered UI as verified chain truth.

The official X1 Explorer source observed for this contract is pinned only as
implementation evidence. It is not proof that a deployed page is running that
exact commit or that the explorer's upstream RPC data is complete/current.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import unquote, urlparse

from .base import DISCOVERED
from .x1_explorer import X1_EXPLORER_SOURCE


STRUCTURED_CONTRACT = "x1_explorer_structured_discovery/v1"

X1_EXPLORER_IMPLEMENTATION_REPOSITORY = "x1-labs/x1-explorer"
X1_EXPLORER_IMPLEMENTATION_REF = "master"
X1_EXPLORER_IMPLEMENTATION_COMMIT = "a2f2512d8436bda544b7db49e06b503515af90d0"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}

ADDRESS_SUBVIEWS = (
    "anchor-account",
    "anchor-program",
    "attributes",
    "blockhashes",
    "compression",
    "concurrent-merkle-tree",
    "domains",
    "entries",
    "feature-gate",
    "instructions",
    "metadata",
    "nftoken-collection-nfts",
    "program-multisig",
    "rewards",
    "security",
    "slot-hashes",
    "stake-history",
    "tokens",
    "transfers",
    "verified-build",
    "vote-history",
)

_SOURCE_EVIDENCE = {
    "repository": X1_EXPLORER_IMPLEMENTATION_REPOSITORY,
    "ref": X1_EXPLORER_IMPLEMENTATION_REF,
    "commit": X1_EXPLORER_IMPLEMENTATION_COMMIT,
    "deployment_identity_verified": False,
    "implementation_semantics_verified_by_cmis": False,
    "role": "official_public_source_implementation_evidence",
}


class X1ExplorerStructuredDiscoveryError(ValueError):
    """Raised when structured X1 Explorer discovery input is malformed."""


def _base58_decode(value: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise X1ExplorerStructuredDiscoveryError("Base58 value must not be empty")

    number = 0
    for char in text:
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            raise X1ExplorerStructuredDiscoveryError(
                f"invalid Base58 character {char!r}"
            )
        number = number * 58 + digit

    payload = (
        number.to_bytes((number.bit_length() + 7) // 8, byteorder="big")
        if number
        else b""
    )
    leading_zeros = len(text) - len(text.lstrip("1"))
    return (b"\x00" * leading_zeros) + payload


def _decoded_length(value: str) -> int | None:
    try:
        return len(_base58_decode(value))
    except X1ExplorerStructuredDiscoveryError:
        return None


def _unsupported(
    *,
    url: str,
    path: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": False,
        "reason": reason,
        "url": url,
        "path": path,
        "entity_type": None,
        "identifier": None,
        "address_subview": None,
        "verification_handoff": [],
        "implementation_evidence": dict(_SOURCE_EVIDENCE),
        "truth_state": {
            "discovery_state": DISCOVERED,
            "explorer_route_verified": False,
            "entity_identity_verified": False,
            "address_subtype_verified": False,
            "web_claim_verified": False,
            "cmis_verified": False,
            "source_independence_verified": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def _verification_handoff(entity_type: str) -> list[dict[str, Any]]:
    if entity_type == "transaction":
        return [
            {
                "explorer_sdk_call": "getSignatureStatus",
                "rpc_method": "getSignatureStatuses",
                "purpose": "history-aware signature status candidate",
                "required": False,
                "notes": "Explorer source enables searchTransactionHistory=true.",
            },
            {
                "explorer_sdk_call": "getBlockTime",
                "rpc_method": "getBlockTime",
                "purpose": "slot-to-block-time corroboration",
                "required": False,
                "depends_on": "status_slot",
            },
            {
                "explorer_sdk_call": "getTransaction",
                "rpc_method": "getTransaction",
                "purpose": "raw transaction and metadata verification",
                "required": True,
                "params_hint": {"maxSupportedTransactionVersion": 0},
            },
            {
                "explorer_sdk_call": "getParsedTransaction",
                "rpc_method": "getTransaction",
                "purpose": "parsed transaction candidate semantics",
                "required": False,
                "params_hint": {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0,
                },
            },
        ]

    if entity_type == "address":
        return [
            {
                "explorer_sdk_call": "getMultipleParsedAccounts",
                "rpc_method": "getMultipleAccounts",
                "purpose": "parsed account identity/state candidate",
                "required": True,
                "params_hint": {"encoding": "jsonParsed", "commitment": "confirmed"},
            },
            {
                "explorer_sdk_call": "getMultipleAccountsInfo",
                "rpc_method": "getMultipleAccounts",
                "purpose": "raw account owner/data corroboration",
                "required": False,
                "params_hint": {"commitment": "confirmed"},
            },
            {
                "explorer_sdk_call": "getSignaturesForAddress",
                "rpc_method": "getSignaturesForAddress",
                "purpose": "bounded account history discovery",
                "required": False,
                "observed_default_limit": 25,
            },
            {
                "explorer_sdk_call": "getParsedTransactions",
                "rpc_method": "getTransaction",
                "purpose": "optional parsing of discovered account-history signatures",
                "required": False,
                "params_hint": {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0,
                },
                "observed_batch_max": 10,
            },
        ]

    if entity_type == "block":
        return [
            {
                "explorer_sdk_call": "getBlock",
                "rpc_method": "getBlock",
                "purpose": "block identity/content verification",
                "required": True,
                "params_hint": {
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0,
                },
            },
            {
                "explorer_sdk_call": "getBlocks",
                "rpc_method": "getBlocks",
                "purpose": "bounded child-slot discovery used by explorer presentation",
                "required": False,
            },
            {
                "explorer_sdk_call": "getSlotLeaders",
                "rpc_method": "getSlotLeaders",
                "purpose": "leader presentation corroboration",
                "required": False,
            },
        ]

    if entity_type == "epoch":
        return []

    raise X1ExplorerStructuredDiscoveryError(
        f"unsupported entity_type {entity_type!r}"
    )


def _supported(
    *,
    url: str,
    path: str,
    entity_type: str,
    identifier: str | int,
    decoded_base58_bytes: int | None = None,
    address_subview: str | None = None,
) -> dict[str, Any]:
    return {
        "contract": STRUCTURED_CONTRACT,
        "supported": True,
        "reason": None,
        "url": url,
        "path": path,
        "entity_type": entity_type,
        "identifier": identifier,
        "decoded_base58_bytes": decoded_base58_bytes,
        "address_subview": address_subview,
        "verification_handoff": _verification_handoff(entity_type),
        "implementation_evidence": dict(_SOURCE_EVIDENCE),
        "truth_state": {
            "discovery_state": DISCOVERED,
            "explorer_route_verified": True,
            "entity_identity_verified": False,
            "address_subtype_verified": False,
            "web_claim_verified": False,
            "cmis_verified": False,
            "source_independence_verified": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def parse_x1_explorer_url(url: str) -> dict[str, Any]:
    """Parse one allowlisted X1 Explorer URL into a deterministic entity candidate."""

    normalized = X1_EXPLORER_SOURCE.validate_url(url)
    parsed = urlparse(normalized)
    raw_segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    path = parsed.path or "/"

    if len(raw_segments) == 2 and raw_segments[0] == "tx":
        signature = raw_segments[1]
        decoded = _decoded_length(signature)
        if decoded != 64:
            return _unsupported(
                url=normalized,
                path=path,
                reason="transaction_signature_must_decode_to_64_bytes",
            )
        return _supported(
            url=normalized,
            path=path,
            entity_type="transaction",
            identifier=signature,
            decoded_base58_bytes=decoded,
        )

    if 2 <= len(raw_segments) <= 3 and raw_segments[0] == "address":
        address = raw_segments[1]
        decoded = _decoded_length(address)
        if decoded != 32:
            return _unsupported(
                url=normalized,
                path=path,
                reason="address_must_decode_to_32_bytes",
            )

        subview = None
        if len(raw_segments) == 3:
            candidate = raw_segments[2]
            if candidate not in ADDRESS_SUBVIEWS:
                return _unsupported(
                    url=normalized,
                    path=path,
                    reason="unsupported_address_subview",
                )
            subview = candidate

        return _supported(
            url=normalized,
            path=path,
            entity_type="address",
            identifier=address,
            decoded_base58_bytes=decoded,
            address_subview=subview,
        )

    if len(raw_segments) == 2 and raw_segments[0] in {"block", "epoch"}:
        raw_number = raw_segments[1]
        if not raw_number.isdigit():
            return _unsupported(
                url=normalized,
                path=path,
                reason=f"{raw_segments[0]}_identifier_must_be_nonnegative_integer",
            )
        number = int(raw_number)
        return _supported(
            url=normalized,
            path=path,
            entity_type=raw_segments[0],
            identifier=number,
        )

    return _unsupported(
        url=normalized,
        path=path,
        reason="unsupported_x1_explorer_route",
    )


def extract_related_x1_explorer_entities(
    links: Iterable[str],
    *,
    max_entities: int = 50,
) -> list[dict[str, Any]]:
    if isinstance(max_entities, bool) or not isinstance(max_entities, int):
        raise ValueError("max_entities must be an integer")
    if max_entities < 1 or max_entities > 100:
        raise ValueError("max_entities must be between 1 and 100")

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for link in links:
        try:
            parsed = parse_x1_explorer_url(str(link))
        except Exception:
            continue
        if not parsed["supported"]:
            continue

        key = (parsed["entity_type"], str(parsed["identifier"]))
        if key in seen:
            continue
        seen.add(key)
        results.append(parsed)
        if len(results) >= max_entities:
            break

    return results


def extract_related_from_web_discovery(
    discovery: Mapping[str, Any],
    *,
    max_entities: int = 50,
) -> list[dict[str, Any]]:
    """Extract related structured entities from one page or crawl result."""

    links: list[str] = []

    pages = discovery.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, Mapping):
                continue
            content = page.get("content")
            if not isinstance(content, Mapping):
                continue
            raw_links = content.get("links")
            if isinstance(raw_links, list):
                links.extend(str(link) for link in raw_links)
    else:
        content = discovery.get("content")
        if isinstance(content, Mapping):
            raw_links = content.get("links")
            if isinstance(raw_links, list):
                links.extend(str(link) for link in raw_links)

    return extract_related_x1_explorer_entities(
        links,
        max_entities=max_entities,
    )


__all__ = [
    "ADDRESS_SUBVIEWS",
    "STRUCTURED_CONTRACT",
    "X1_EXPLORER_IMPLEMENTATION_COMMIT",
    "X1_EXPLORER_IMPLEMENTATION_REF",
    "X1_EXPLORER_IMPLEMENTATION_REPOSITORY",
    "X1ExplorerStructuredDiscoveryError",
    "extract_related_from_web_discovery",
    "extract_related_x1_explorer_entities",
    "parse_x1_explorer_url",
]
