"""X1-side XONE -> XNT allocation-record discovery.

This provider searches bounded public artifacts for records that explicitly place a
canonical Ethereum address beside an exact X1/SVM pubkey in XONE allocation,
claim, registry, vesting, or distribution context.

Discovery is intentionally weaker than verification:
- an address pair does not prove snapshot eligibility;
- an X1 account's existence does not prove allocation role;
- XONE name-only context is not exact identity binding;
- XNT amount/state fields are preserved but not promoted as issuance truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse, urlunparse

from .x1_xnt_distribution_mechanism import (
    X1XntMechanismDiscoveryError,
    normalize_x1_pubkey,
)


CONTRACT_VERSION = "xone_xnt_x1_allocation_record_discovery/v1"
CHAIN = "x1"
NETWORK = "x1-mainnet"
DISCOVERED = "DISCOVERED"

XONE_CONTRACT = "0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c"
XONE_CONTRACT_NORMALIZED = XONE_CONTRACT.casefold()

_ETHEREUM_ADDRESS_RE = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")
_BASE58_RE = re.compile(
    r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])"
)
_XNT_AMOUNT_RE = re.compile(
    r"\b(?P<amount>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>XNT|credits?)\b",
    re.IGNORECASE,
)
_ALLOCATION_TERMS = (
    "allocation",
    "allocated",
    "allocate",
    "airdrop",
    "claim",
    "claimable",
    "claimed",
    "distribution",
    "distributed",
    "registry",
    "holder",
    "eligibility",
    "eligible",
    "snapshot",
    "vesting",
    "vested",
    "unlock",
    "credit",
    "reward",
)
_CLAIM_TERMS = ("claim", "claimed", "claimable", "redeem", "redeemed")
_VESTING_TERMS = ("vest", "vesting", "vested", "lock", "locked", "unlock", "cliff")
_AMOUNT_KEYS = {
    "amount",
    "xntamount",
    "xnt_amount",
    "allocation",
    "allocationamount",
    "allocation_amount",
    "credits",
    "credit",
    "reward",
    "rewardamount",
    "reward_amount",
}
_CLAIM_KEYS = {"claim", "claimed", "claimable", "claimstate", "claim_state", "status"}
_VESTING_KEYS = {
    "vesting",
    "vested",
    "lock",
    "locked",
    "unlock",
    "unlockat",
    "unlock_at",
    "unlockdate",
    "unlock_date",
    "cliff",
}
_ID_KEYS = {
    "id",
    "allocationid",
    "allocation_id",
    "claimid",
    "claim_id",
    "recordid",
    "record_id",
    "registryid",
    "registry_id",
}


class XoneXntX1AllocationRecordDiscoveryError(RuntimeError):
    """Raised when allocation-record evidence cannot be processed safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any, *, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def normalize_ethereum_address(value: Any) -> str:
    """Normalize one exact 20-byte Ethereum hex address."""

    text = _text(value)
    if not re.fullmatch(r"0x[0-9A-Fa-f]{40}", text):
        raise XoneXntX1AllocationRecordDiscoveryError(
            "candidate is not an exact 20-byte Ethereum address"
        )
    return text.casefold()


def _normalize_source_url(value: str) -> str:
    parsed = urlparse(_text(value))
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise XoneXntX1AllocationRecordDiscoveryError(
            "source URL must be absolute HTTPS"
        )
    if parsed.username is not None or parsed.password is not None:
        raise XoneXntX1AllocationRecordDiscoveryError(
            "source URL must not embed credentials"
        )
    host = parsed.hostname.casefold().rstrip(".")
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    return urlunparse(("https", netloc, parsed.path or "/", "", parsed.query, ""))


def _ethereum_addresses(text: str) -> list[str]:
    rows: list[str] = []
    for match in _ETHEREUM_ADDRESS_RE.finditer(_text(text)):
        address = normalize_ethereum_address(match.group(0))
        # The accepted XONE token contract may appear in the same artifact as
        # holder/allocation records. It is identity metadata, not a holder key.
        if address == XONE_CONTRACT_NORMALIZED:
            continue
        if address not in rows:
            rows.append(address)
    return rows


def _x1_pubkeys(text: str) -> list[str]:
    rows: list[str] = []
    for match in _BASE58_RE.finditer(_text(text)):
        value = match.group(0)
        try:
            pubkey = normalize_x1_pubkey(value)
        except X1XntMechanismDiscoveryError:
            continue
        if pubkey not in rows:
            rows.append(pubkey)
    return rows


def _amount_values(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _XNT_AMOUNT_RE.finditer(_text(text)):
        amount = match.group("amount").replace(",", "")
        unit = match.group("unit").casefold()
        normalized_unit = "XNT" if unit == "xnt" else "credits"
        key = (amount, normalized_unit)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "raw": match.group(0),
                "amount": amount,
                "unit": normalized_unit,
            }
        )
    return rows


def _mapping_semantics(mapping: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {str(key).casefold(): value for key, value in mapping.items()}
    amount_fields = {
        key: normalized[key]
        for key in sorted(normalized)
        if key in _AMOUNT_KEYS
    }
    claim_fields = {
        key: normalized[key]
        for key in sorted(normalized)
        if key in _CLAIM_KEYS
    }
    vesting_fields = {
        key: normalized[key]
        for key in sorted(normalized)
        if key in _VESTING_KEYS
    }
    identifier_fields = {
        key: normalized[key]
        for key in sorted(normalized)
        if key in _ID_KEYS
    }
    return {
        "amount_fields": amount_fields,
        "claim_fields": claim_fields,
        "vesting_fields": vesting_fields,
        "identifier_fields": identifier_fields,
    }


def _stringify_mapping(mapping: Mapping[str, Any]) -> str:
    try:
        return json.dumps(mapping, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return " ".join(f"{key}={value}" for key, value in mapping.items())


def _semantic_context(
    text: str,
    *,
    path: Optional[str],
    source_id: str,
) -> dict[str, bool]:
    lowered = " ".join(
        part.casefold()
        for part in (_text(text), _text(path), _text(source_id))
        if part
    )
    return {
        "xone_named": "xone" in lowered,
        "exact_xone_contract_mentioned": XONE_CONTRACT_NORMALIZED in lowered,
        "xnt_named": "xnt" in lowered,
        "allocation_language_present": any(term in lowered for term in _ALLOCATION_TERMS),
        "claim_language_present": any(term in lowered for term in _CLAIM_TERMS),
        "vesting_or_unlock_language_present": any(
            term in lowered for term in _VESTING_TERMS
        ),
    }


def _record(
    *,
    ethereum_address: str,
    x1_pubkey: str,
    context_text: str,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: Optional[str],
    revision: Optional[str],
    structured_semantics: Optional[Mapping[str, Any]] = None,
    extraction_basis: str,
) -> dict[str, Any]:
    eth = normalize_ethereum_address(ethereum_address)
    try:
        pubkey = normalize_x1_pubkey(x1_pubkey)
    except X1XntMechanismDiscoveryError as exc:
        raise XoneXntX1AllocationRecordDiscoveryError(
            "allocation record contains invalid X1 pubkey"
        ) from exc

    normalized_url = _normalize_source_url(url)
    semantic = _semantic_context(
        context_text,
        path=path,
        source_id=source_id,
    )
    amounts = _amount_values(context_text)
    structured = dict(structured_semantics or {})
    amount_fields = structured.get("amount_fields")
    if not isinstance(amount_fields, Mapping):
        amount_fields = {}
    claim_fields = structured.get("claim_fields")
    if not isinstance(claim_fields, Mapping):
        claim_fields = {}
    vesting_fields = structured.get("vesting_fields")
    if not isinstance(vesting_fields, Mapping):
        vesting_fields = {}
    identifier_fields = structured.get("identifier_fields")
    if not isinstance(identifier_fields, Mapping):
        identifier_fields = {}

    xone_specific = (
        semantic["exact_xone_contract_mentioned"]
        or (
            semantic["xone_named"]
            and semantic["allocation_language_present"]
        )
    )
    record_id = sha256(
        (
            f"{CONTRACT_VERSION}|{source_id}|{normalized_url}|{path or ''}|"
            f"{revision or ''}|{eth}|{pubkey}|{context_text[:1200]}"
        ).encode("utf-8")
    ).hexdigest()

    return {
        "record_id": record_id,
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "discovery_state": DISCOVERED,
        "source_id": _text(source_id),
        "source_role": _text(source_role),
        "url": normalized_url,
        "path": _text(path) or None,
        "revision": _text(revision) or None,
        "observed_at": observed_at,
        "extraction_basis": extraction_basis,
        "ethereum_address": eth,
        "ethereum_address_verified": True,
        "x1_pubkey": pubkey,
        "x1_pubkey_verified": True,
        "context_excerpt": re.sub(r"\s+", " ", _text(context_text))[:1800],
        "xone_named": semantic["xone_named"],
        "exact_xone_contract_mentioned": semantic[
            "exact_xone_contract_mentioned"
        ],
        "xnt_named": semantic["xnt_named"],
        "allocation_language_present": semantic[
            "allocation_language_present"
        ],
        "claim_language_present": semantic["claim_language_present"],
        "vesting_or_unlock_language_present": semantic[
            "vesting_or_unlock_language_present"
        ],
        "xone_specific_context": xone_specific,
        "xone_identity_binding_verified": semantic[
            "exact_xone_contract_mentioned"
        ],
        "xnt_amount_values": amounts,
        "xnt_amount_field_present": bool(amounts or amount_fields),
        "structured_amount_fields": dict(amount_fields),
        "structured_claim_fields": dict(claim_fields),
        "structured_vesting_fields": dict(vesting_fields),
        "structured_identifier_fields": dict(identifier_fields),
        "allocation_record_candidate_discovered": True,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
        "snapshot_eligibility_verified": False,
        "snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def _iter_json_mappings(
    value: Any,
    *,
    max_nodes: int,
) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    stack: list[tuple[str, Any]] = [("$", value)]
    seen = 0
    while stack and seen < max_nodes:
        path, node = stack.pop()
        seen += 1
        if isinstance(node, Mapping):
            rows.append((path, node))
            for key, child in reversed(list(node.items())):
                stack.append((f"{path}.{key}", child))
        elif isinstance(node, Sequence) and not isinstance(
            node, (str, bytes, bytearray)
        ):
            for index in range(len(node) - 1, -1, -1):
                stack.append((f"{path}[{index}]", node[index]))
    return rows


def _structured_records(
    text: str,
    *,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: Optional[str],
    revision: Optional[str],
    max_records: int,
) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    rows: list[dict[str, Any]] = []
    for json_path, mapping in _iter_json_mappings(
        payload,
        max_nodes=max(200, max_records * 20),
    ):
        rendered = _stringify_mapping(mapping)
        keys_and_values = " ".join(
            [rendered, " ".join(str(key) for key in mapping.keys())]
        )
        eth_addresses = _ethereum_addresses(keys_and_values)
        pubkeys = _x1_pubkeys(keys_and_values)
        if not eth_addresses or not pubkeys:
            continue
        semantics = _mapping_semantics(mapping)
        context = f"{json_path} {rendered}"
        semantic = _semantic_context(context, path=path, source_id=source_id)
        if not (
            semantic["allocation_language_present"]
            and semantic["xone_named"]
        ):
            continue
        for eth in eth_addresses:
            for pubkey in pubkeys:
                rows.append(
                    _record(
                        ethereum_address=eth,
                        x1_pubkey=pubkey,
                        context_text=context,
                        source_id=source_id,
                        source_role=source_role,
                        url=url,
                        observed_at=observed_at,
                        path=path,
                        revision=revision,
                        structured_semantics=semantics,
                        extraction_basis="structured_json_mapping",
                    )
                )
                if len(rows) >= max_records:
                    return rows
    return rows


def _text_records(
    text: str,
    *,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: Optional[str],
    revision: Optional[str],
    max_records: int,
) -> list[dict[str, Any]]:
    normalized = _text(text)
    rows: list[dict[str, Any]] = []
    seen_windows: set[str] = set()

    matches = list(_ETHEREUM_ADDRESS_RE.finditer(normalized))
    for match in matches:
        start = max(0, match.start() - 900)
        end = min(len(normalized), match.end() + 1200)
        window = normalized[start:end]
        key = sha256(window.encode("utf-8")).hexdigest()
        if key in seen_windows:
            continue
        seen_windows.add(key)
        semantic = _semantic_context(window, path=path, source_id=source_id)
        if not (
            semantic["xone_named"]
            and semantic["allocation_language_present"]
        ):
            continue
        eth_addresses = _ethereum_addresses(window)
        pubkeys = _x1_pubkeys(window)
        if not pubkeys:
            continue
        for eth in eth_addresses:
            for pubkey in pubkeys:
                rows.append(
                    _record(
                        ethereum_address=eth,
                        x1_pubkey=pubkey,
                        context_text=window,
                        source_id=source_id,
                        source_role=source_role,
                        url=url,
                        observed_at=observed_at,
                        path=path,
                        revision=revision,
                        extraction_basis="bounded_text_window",
                    )
                )
                if len(rows) >= max_records:
                    return rows
    return rows


def extract_x1_allocation_records(
    text: str,
    *,
    source_id: str,
    source_role: str,
    url: str,
    observed_at: float,
    path: Optional[str] = None,
    revision: Optional[str] = None,
    max_records: int = 100,
) -> list[dict[str, Any]]:
    """Extract exact Ethereum->X1 allocation-record candidates from one artifact."""

    if not _text(source_id):
        raise ValueError("source_id is required")
    if not _text(source_role):
        raise ValueError("source_role is required")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    max_records = _positive_int(max_records, name="max_records", maximum=500)
    _normalize_source_url(url)

    rows = _structured_records(
        text,
        source_id=source_id,
        source_role=source_role,
        url=url,
        observed_at=observed_at,
        path=path,
        revision=revision,
        max_records=max_records,
    )
    if len(rows) < max_records:
        rows.extend(
            _text_records(
                text,
                source_id=source_id,
                source_role=source_role,
                url=url,
                observed_at=observed_at,
                path=path,
                revision=revision,
                max_records=max_records - len(rows),
            )
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (
            row["ethereum_address"],
            row["x1_pubkey"],
            row["url"],
            row.get("path") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:max_records]


def summarize_x1_allocation_records(
    records: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 100,
) -> dict[str, Any]:
    """Group duplicate pairs and preserve amount/state conflicts without promotion."""

    if not isinstance(records, Sequence) or isinstance(
        records, (str, bytes, bytearray)
    ):
        raise ValueError("records must be a sequence")
    max_candidates = _positive_int(
        max_candidates,
        name="max_candidates",
        maximum=500,
    )

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        eth = normalize_ethereum_address(raw.get("ethereum_address"))
        try:
            pubkey = normalize_x1_pubkey(raw.get("x1_pubkey"))
        except X1XntMechanismDiscoveryError as exc:
            raise XoneXntX1AllocationRecordDiscoveryError(
                "record contains invalid X1 pubkey"
            ) from exc
        pair = (eth, pubkey)
        group = grouped.get(pair)
        if group is None:
            group = {
                "candidate_id": sha256(
                    f"{CONTRACT_VERSION}|{eth}|{pubkey}".encode("utf-8")
                ).hexdigest(),
                "ethereum_address": eth,
                "x1_pubkey": pubkey,
                "record_ids": [],
                "source_urls": [],
                "source_roles": [],
                "paths": [],
                "xone_specific_record_count": 0,
                "exact_xone_identity_bound_record_count": 0,
                "xnt_amount_values": [],
                "structured_amount_field_values": [],
                "claim_field_values": [],
                "vesting_field_values": [],
                "amount_conflict": False,
                "allocation_record_candidate_discovered": True,
                "ethereum_address_verified": True,
                "x1_pubkey_verified": True,
                "xone_identity_binding_verified": False,
                "allocation_semantics_verified": False,
                "claim_state_verified": False,
                "vesting_or_unlock_state_verified": False,
                "snapshot_eligibility_verified": False,
                "snapshot_xnt_allocation_binding_verified": False,
                "xnt_issuance_verified": False,
                "xone_xnt_conversion_verified": False,
                "cross_chain_correlation_verified": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            }
            grouped[pair] = group

        record_id = _text(raw.get("record_id"))
        if record_id and record_id not in group["record_ids"]:
            group["record_ids"].append(record_id)
        for field, target in (
            ("url", "source_urls"),
            ("source_role", "source_roles"),
            ("path", "paths"),
        ):
            value = _text(raw.get(field))
            if value and value not in group[target]:
                group[target].append(value)

        if raw.get("xone_specific_context") is True:
            group["xone_specific_record_count"] += 1
        if raw.get("xone_identity_binding_verified") is True:
            group["exact_xone_identity_bound_record_count"] += 1
            group["xone_identity_binding_verified"] = True

        for amount in raw.get("xnt_amount_values", []) or []:
            if isinstance(amount, Mapping):
                normalized = (
                    _text(amount.get("amount")),
                    _text(amount.get("unit")),
                )
                if all(normalized) and normalized not in group["xnt_amount_values"]:
                    group["xnt_amount_values"].append(normalized)

        amount_fields = raw.get("structured_amount_fields")
        if isinstance(amount_fields, Mapping):
            for key, value in amount_fields.items():
                pair_value = (str(key), str(value))
                if pair_value not in group["structured_amount_field_values"]:
                    group["structured_amount_field_values"].append(pair_value)

        claim_fields = raw.get("structured_claim_fields")
        if isinstance(claim_fields, Mapping):
            for key, value in claim_fields.items():
                pair_value = (str(key), str(value))
                if pair_value not in group["claim_field_values"]:
                    group["claim_field_values"].append(pair_value)

        vesting_fields = raw.get("structured_vesting_fields")
        if isinstance(vesting_fields, Mapping):
            for key, value in vesting_fields.items():
                pair_value = (str(key), str(value))
                if pair_value not in group["vesting_field_values"]:
                    group["vesting_field_values"].append(pair_value)

    candidates = list(grouped.values())
    for group in candidates:
        normalized_amounts = {
            str(item[0]).replace(",", "").strip()
            for item in group["xnt_amount_values"]
            if item and str(item[0]).strip()
        }
        normalized_amounts.update(
            str(value).replace(",", "").strip()
            for _key, value in group["structured_amount_field_values"]
            if str(value).strip()
        )
        group["amount_conflict"] = len(normalized_amounts) > 1

    candidates.sort(
        key=lambda row: (
            -row["exact_xone_identity_bound_record_count"],
            -row["xone_specific_record_count"],
            -len(row["record_ids"]),
            row["ethereum_address"],
            row["x1_pubkey"],
        )
    )
    candidates = candidates[:max_candidates]

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "record_count": len(records),
        "candidate_count": len(candidates),
        "xone_specific_candidate_count": sum(
            1 for row in candidates if row["xone_specific_record_count"] > 0
        ),
        "exact_xone_identity_bound_candidate_count": sum(
            1
            for row in candidates
            if row["xone_identity_binding_verified"] is True
        ),
        "xnt_amount_candidate_count": sum(
            1
            for row in candidates
            if row["xnt_amount_values"]
            or row["structured_amount_field_values"]
        ),
        "amount_conflict_candidate_count": sum(
            1 for row in candidates if row["amount_conflict"]
        ),
        "candidates": candidates,
        "allocation_record_discovery_verified": True,
        "zero_candidates_are_scoped_public_source_evidence_only": (
            len(candidates) == 0
        ),
        "private_or_unpublished_allocation_registry_absence_proven": False,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
        "snapshot_eligibility_verified": False,
        "snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def _nonnegative_int(value: Any, *, field: str, allow_none: bool = False) -> Optional[int]:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise XoneXntX1AllocationRecordDiscoveryError(
            f"{field} must be a non-negative integer"
        )
    return value


def qualify_x1_allocation_candidate(
    candidate: Mapping[str, Any],
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
) -> dict[str, Any]:
    """Qualify only the exact discovered X1 pubkey through finalized account state."""

    if not isinstance(candidate, Mapping):
        raise XoneXntX1AllocationRecordDiscoveryError(
            "candidate must be a mapping"
        )
    eth = normalize_ethereum_address(candidate.get("ethereum_address"))
    try:
        pubkey = normalize_x1_pubkey(candidate.get("x1_pubkey"))
    except X1XntMechanismDiscoveryError as exc:
        raise XoneXntX1AllocationRecordDiscoveryError(
            "candidate contains invalid X1 pubkey"
        ) from exc

    result = rpc_call(
        "getAccountInfo",
        [pubkey, {"encoding": "jsonParsed", "commitment": "finalized"}],
    )
    if not isinstance(result, Mapping):
        raise XoneXntX1AllocationRecordDiscoveryError(
            "getAccountInfo result must be an object"
        )
    context = result.get("context")
    context_slot = None
    if isinstance(context, Mapping) and context.get("slot") is not None:
        context_slot = _nonnegative_int(
            context.get("slot"),
            field="getAccountInfo.context.slot",
        )

    value = result.get("value")
    if value is None:
        account = {
            "account_exists": False,
            "owner": None,
            "executable": None,
            "lamports": None,
            "space": None,
            "parsed_program": None,
            "parsed_type": None,
        }
    elif isinstance(value, Mapping):
        owner_raw = _text(value.get("owner"))
        if not owner_raw:
            raise XoneXntX1AllocationRecordDiscoveryError(
                "account owner is missing"
            )
        try:
            owner = normalize_x1_pubkey(owner_raw)
        except X1XntMechanismDiscoveryError as exc:
            raise XoneXntX1AllocationRecordDiscoveryError(
                "account owner is not a valid X1 pubkey"
            ) from exc
        executable = value.get("executable")
        if not isinstance(executable, bool):
            raise XoneXntX1AllocationRecordDiscoveryError(
                "account executable flag must be boolean"
            )
        lamports = _nonnegative_int(
            value.get("lamports"),
            field="account.lamports",
        )
        space = _nonnegative_int(
            value.get("space"),
            field="account.space",
            allow_none=True,
        )
        parsed_program = None
        parsed_type = None
        data = value.get("data")
        if isinstance(data, Mapping):
            parsed_program = _text(data.get("program")) or None
            parsed = data.get("parsed")
            if isinstance(parsed, Mapping):
                parsed_type = _text(parsed.get("type")) or None
        account = {
            "account_exists": True,
            "owner": owner,
            "executable": executable,
            "lamports": lamports,
            "space": space,
            "parsed_program": parsed_program,
            "parsed_type": parsed_type,
        }
    else:
        raise XoneXntX1AllocationRecordDiscoveryError(
            "getAccountInfo value must be an object or null"
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "ethereum_address": eth,
        "x1_pubkey": pubkey,
        "source_url": source_url,
        "rpc_finalized_commitment": True,
        "context_slot": context_slot,
        "account_state_verified": True,
        **account,
        "account_existence_does_not_prove_allocation_role": True,
        "allocation_semantics_verified": False,
        "claim_state_verified": False,
        "vesting_or_unlock_state_verified": False,
        "snapshot_eligibility_verified": False,
        "snapshot_xnt_allocation_binding_verified": False,
        "xnt_issuance_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
