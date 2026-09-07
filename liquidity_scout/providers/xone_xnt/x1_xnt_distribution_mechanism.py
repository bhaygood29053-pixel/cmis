"""Bounded X1-side XNT distribution / vesting mechanism discovery.

This provider is the X1-side companion to the dedicated XONE/XNT intelligence
track.  It extracts XNT mechanism claims from bounded public X1 sources and
qualifies only exact 32-byte X1/SVM public keys through direct X1 RPC.

A web rule, an account's existence, Stake Program ownership, or stake lockup
metadata does not by itself prove that the account participates in XONE -> XNT
conversion or that it is the source of XNT issuance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse, urlunparse


CONTRACT_VERSION = "x1_xnt_distribution_mechanism_discovery/v1"
DISCOVERED = "DISCOVERED"
CHAIN = "x1"
NETWORK = "x1-mainnet"

OFFICIAL_REWARDS_URL = (
    "https://docs.x1.xyz/validating/validator-rewards/"
    "incentivized-testnet-rewards"
)
STAKE_PROGRAM_ID = "Stake11111111111111111111111111111111111111"

_ALLOWED_SOURCES = {
    "x1_docs": {
        "source_name": "X1 Docs",
        "source_role": "official_x1_documentation",
        "hosts": {"docs.x1.xyz", "next.x1.xyz"},
    },
    "x1_official": {
        "source_name": "X1",
        "source_role": "official_x1_web",
        "hosts": {"x1.xyz", "www.x1.xyz"},
    },
    "x1report": {
        "source_name": "X1 Report",
        "source_role": "third_party_x1_reporting",
        "hosts": {"x1report.com", "www.x1report.com"},
    },
}

_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("validator_rewards", ("validator", "testnet reward", "testnet rewards", "credits")),
    ("distribution", ("distribution", "distributed", "receive", "received", "reward", "rewards")),
    ("allocation", ("allocation", "allocated", "pool")),
    ("lockup", ("lockup", "lock-up", "locked", "lock period", "lock with vesting")),
    ("vesting", ("vest", "vesting", "vested", "cliff")),
    ("unlock", ("unlock", "unlocks", "unlocked")),
    ("claim", ("claim", "claimable", "redeem")),
    ("genesis", ("genesis", "mainnet launch", "launch of the chain")),
    ("migration", ("migration", "migrate", "conversion", "convert")),
    ("stake", ("stake", "staking", "delegat")),
)
_MECHANISM_TERMS = tuple(
    sorted(
        {
            needle
            for _topic, needles in _TOPIC_PATTERNS
            for needle in needles
        }
    )
)

# SVM/Solana base58 public keys are typically 32-44 chars.  Exact validation is
# performed by decoding and requiring 32 bytes.
_BASE58_RE = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
_DAYS_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s+days?\b", re.IGNORECASE)
_CREDIT_XNT_RE = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s+credits?\s*(?:=|equals?|convert(?:s|ed)?\s+to|for)\s*"
    r"\d[\d,]*(?:\.\d+)?\s+XNT\b",
    re.IGNORECASE,
)
_RATIO_RE = re.compile(r"\b\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?\b")
_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b",
    re.IGNORECASE,
)


class X1XntMechanismDiscoveryError(RuntimeError):
    """Raised when XNT mechanism discovery/qualification cannot fail safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_source_url(source_id: str, value: str) -> str:
    source = _ALLOWED_SOURCES.get(_text(source_id))
    if source is None:
        raise ValueError(f"unsupported XNT mechanism source_id {source_id!r}")
    parsed = urlparse(_text(value))
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise X1XntMechanismDiscoveryError("source URL must be HTTPS")
    host = parsed.hostname.casefold().rstrip(".")
    if host not in source["hosts"]:
        raise X1XntMechanismDiscoveryError(
            f"source host {host!r} is outside {source_id!r} allowlist"
        )
    if parsed.username is not None or parsed.password is not None:
        raise X1XntMechanismDiscoveryError("source URL must not embed credentials")
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    return urlunparse(("https", netloc, parsed.path or "/", "", parsed.query, ""))


def _base58_decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    indexes = {char: index for index, char in enumerate(alphabet)}
    text = _text(value)
    if not text:
        raise X1XntMechanismDiscoveryError("public key must not be empty")
    number = 0
    try:
        for char in text:
            number = number * 58 + indexes[char]
    except KeyError as exc:
        raise X1XntMechanismDiscoveryError("public key is not base58") from exc
    payload = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading_zeroes = len(text) - len(text.lstrip("1"))
    return (b"\x00" * leading_zeroes) + payload


def normalize_x1_pubkey(value: Any) -> str:
    text = _text(value)
    if len(text) < 32 or len(text) > 44:
        raise X1XntMechanismDiscoveryError("candidate is not a valid X1/SVM public key")
    decoded = _base58_decode(text)
    if len(decoded) != 32:
        raise X1XntMechanismDiscoveryError("candidate does not decode to 32 bytes")
    return text


def _split_segments(text: str) -> list[str]:
    normalized = re.sub(r"[\t\r ]+", " ", _text(text))
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    rows = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [row.strip() for row in rows if row.strip()]


def _topics(segment: str) -> list[str]:
    lowered = segment.casefold()
    return [
        topic
        for topic, needles in _TOPIC_PATTERNS
        if any(needle in lowered for needle in needles)
    ]


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = re.sub(r"\s+", " ", value).strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _pubkeys(segment: str) -> list[str]:
    values: list[str] = []
    for match in _BASE58_RE.finditer(segment):
        candidate = match.group(0)
        try:
            normalize_x1_pubkey(candidate)
        except X1XntMechanismDiscoveryError:
            continue
        if candidate not in values:
            values.append(candidate)
    return values


def extract_xnt_mechanism_claims(
    text: str,
    *,
    source_id: str,
    url: str,
    observed_at: float,
    max_claims: int = 100,
) -> list[dict[str, Any]]:
    """Extract bounded XNT rule/mechanism claims without elevating web text."""

    source = _ALLOWED_SOURCES.get(_text(source_id))
    if source is None:
        raise ValueError(f"unsupported XNT mechanism source_id {source_id!r}")
    normalized_url = _normalize_source_url(source_id, url)
    if isinstance(max_claims, bool) or not isinstance(max_claims, int) or max_claims < 1:
        raise ValueError("max_claims must be a positive integer")

    segments = _split_segments(text)
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, segment in enumerate(segments):
        lowered = segment.casefold()
        if "xnt" not in lowered:
            continue
        topics = _topics(segment)
        if not topics and not any(term in lowered for term in _MECHANISM_TERMS):
            continue

        window = segment
        if index + 1 < len(segments) and len(window) < 1_000:
            nxt = segments[index + 1]
            nxt_lower = nxt.casefold()
            if "xnt" in nxt_lower or _topics(nxt):
                window = f"{window} {nxt}"

        excerpt = re.sub(r"\s+", " ", window).strip()[:1_800]
        claim_topics = _topics(excerpt)
        values = {
            "percentages": _unique([m.group(0) for m in _PERCENT_RE.finditer(excerpt)]),
            "day_periods": _unique([m.group(0) for m in _DAYS_RE.finditer(excerpt)]),
            "credit_xnt_rates": _unique([m.group(0) for m in _CREDIT_XNT_RE.finditer(excerpt)]),
            "ratios": _unique([m.group(0) for m in _RATIO_RE.finditer(excerpt)]),
            "dates": _unique([m.group(0) for m in _DATE_RE.finditer(excerpt)]),
            "x1_pubkeys": _pubkeys(excerpt),
        }
        claim_id = sha256(
            f"{CONTRACT_VERSION}|{source_id}|{normalized_url}|{excerpt}".encode("utf-8")
        ).hexdigest()
        if claim_id in seen:
            continue
        seen.add(claim_id)
        claims.append(
            {
                "claim_id": claim_id,
                "source_id": source_id,
                "source_name": source["source_name"],
                "source_role": source["source_role"],
                "url": normalized_url,
                "observed_at": observed_at,
                "excerpt": excerpt,
                "topics": claim_topics,
                "normalized_values": values,
                "native_xnt_context": True,
                "wxnt_equivalence_not_assumed": True,
                "discovery_state": DISCOVERED,
                "xnt_rule_claim_verified": False,
                "xnt_distribution_mechanism_identified": False,
                "xnt_issuance_verified": False,
                "xnt_vesting_or_unlock_verified": False,
                "xone_xnt_conversion_verified": False,
                "cross_chain_correlation_verified": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            }
        )
        if len(claims) >= max_claims:
            break
    return claims


def discover_xnt_distribution_candidates(
    claims: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 50,
) -> dict[str, Any]:
    """Aggregate exact X1 pubkeys mentioned in bounded XNT mechanism claims."""

    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        raise ValueError("claims must be a sequence")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")

    grouped: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        values = claim.get("normalized_values")
        if not isinstance(values, Mapping):
            continue
        raw_pubkeys = values.get("x1_pubkeys")
        if not isinstance(raw_pubkeys, Sequence) or isinstance(
            raw_pubkeys, (str, bytes, bytearray)
        ):
            continue
        for raw in raw_pubkeys:
            try:
                pubkey = normalize_x1_pubkey(raw)
            except X1XntMechanismDiscoveryError:
                continue
            row = grouped.get(pubkey)
            if row is None:
                row = {
                    "candidate_id": sha256(
                        f"{CONTRACT_VERSION}|{CHAIN}|{pubkey}".encode("utf-8")
                    ).hexdigest(),
                    "candidate_pubkey": pubkey,
                    "candidate_role": "unverified_xnt_distribution_or_vesting_candidate",
                    "source_claim_ids": [],
                    "source_urls": [],
                    "source_roles": [],
                    "topics": [],
                    "candidate_role_verified": False,
                    "account_state_verified": False,
                    "stake_program_owned": False,
                    "stake_lockup_state_verified": False,
                    "xnt_distribution_mechanism_identified": False,
                    "xnt_issuance_verified": False,
                    "xnt_vesting_or_unlock_verified": False,
                    "xone_xnt_conversion_verified": False,
                    "cross_chain_correlation_verified": False,
                    "public_service_promoted": False,
                    "scout_reliance_promoted": False,
                    "execution_authorized": False,
                }
                grouped[pubkey] = row
            claim_id = _text(claim.get("claim_id"))
            if claim_id and claim_id not in row["source_claim_ids"]:
                row["source_claim_ids"].append(claim_id)
            source_url = _text(claim.get("url"))
            if source_url and source_url not in row["source_urls"]:
                row["source_urls"].append(source_url)
            source_role = _text(claim.get("source_role"))
            if source_role and source_role not in row["source_roles"]:
                row["source_roles"].append(source_role)
            for topic in claim.get("topics", []):
                topic_text = _text(topic)
                if topic_text and topic_text not in row["topics"]:
                    row["topics"].append(topic_text)

    candidates = list(grouped.values())
    candidates.sort(
        key=lambda row: (
            -len(row["source_claim_ids"]),
            row["candidate_pubkey"],
        )
    )
    candidates = candidates[:max_candidates]
    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "zero_candidates_mean_only_no_exact_pubkeys_in_supplied_claims": len(candidates) == 0,
        "xnt_distribution_mechanism_identified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def _nonnegative_int(value: Any, *, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise X1XntMechanismDiscoveryError(f"{field} must be a non-negative integer")
    return value


def _parse_stake_lockup(parsed: Any) -> tuple[bool, Optional[dict[str, Any]]]:
    if not isinstance(parsed, Mapping):
        return False, None
    program = _text(parsed.get("program")).casefold()
    if program != "stake":
        return False, None
    body = parsed.get("parsed")
    if not isinstance(body, Mapping):
        return False, None
    info = body.get("info")
    if not isinstance(info, Mapping):
        return False, None
    meta = info.get("meta")
    if not isinstance(meta, Mapping):
        return False, None
    lockup = meta.get("lockup")
    if not isinstance(lockup, Mapping):
        return False, None

    epoch = lockup.get("epoch")
    timestamp = lockup.get("unixTimestamp")
    custodian = lockup.get("custodian")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        return False, None
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        return False, None
    custodian_text = _text(custodian)
    if custodian_text:
        try:
            normalize_x1_pubkey(custodian_text)
        except X1XntMechanismDiscoveryError:
            return False, None

    return True, {
        "epoch": epoch,
        "unix_timestamp": timestamp,
        "custodian": custodian_text or None,
    }


def qualify_xnt_distribution_candidate(
    candidate: Mapping[str, Any],
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
) -> dict[str, Any]:
    """Qualify one exact X1 pubkey through finalized getAccountInfo.

    The result verifies account structure only.  Candidate role remains
    unverified until independent authoritative role binding exists.
    """

    if not isinstance(candidate, Mapping):
        raise X1XntMechanismDiscoveryError("candidate must be a mapping")
    pubkey = normalize_x1_pubkey(candidate.get("candidate_pubkey"))
    result = rpc_call(
        "getAccountInfo",
        [pubkey, {"encoding": "jsonParsed", "commitment": "finalized"}],
    )
    if not isinstance(result, Mapping):
        raise X1XntMechanismDiscoveryError("getAccountInfo result must be an object")
    context = result.get("context")
    slot = None
    if isinstance(context, Mapping):
        slot = _nonnegative_int(context.get("slot"), field="context.slot")
    value = result.get("value")
    if value is None:
        return {
            "contract_version": CONTRACT_VERSION,
            "chain": CHAIN,
            "network": NETWORK,
            "candidate_pubkey": pubkey,
            "qualification_state": "account_not_found",
            "rpc_finalized_commitment": True,
            "context_slot": slot,
            "account_state_verified": True,
            "account_exists": False,
            "owner": None,
            "executable": None,
            "lamports": None,
            "space": None,
            "parsed_program": None,
            "parsed_type": None,
            "stake_program_owned": False,
            "stake_lockup_state_verified": False,
            "stake_lockup": None,
            "candidate_role_verified": False,
            "xnt_distribution_mechanism_identified": False,
            "xnt_issuance_verified": False,
            "xnt_vesting_or_unlock_verified": False,
            "xone_xnt_conversion_verified": False,
            "cross_chain_correlation_verified": False,
            "source_url": source_url,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }
    if not isinstance(value, Mapping):
        raise X1XntMechanismDiscoveryError("getAccountInfo value must be an object or null")

    owner = normalize_x1_pubkey(value.get("owner"))
    executable = value.get("executable")
    if not isinstance(executable, bool):
        raise X1XntMechanismDiscoveryError("account executable flag must be boolean")
    lamports = _nonnegative_int(value.get("lamports"), field="account.lamports")
    if lamports is None:
        raise X1XntMechanismDiscoveryError("account lamports are missing")
    space = _nonnegative_int(value.get("space"), field="account.space")

    data = value.get("data")
    parsed_program = None
    parsed_type = None
    if isinstance(data, Mapping):
        parsed_program = _text(data.get("program")) or None
        body = data.get("parsed")
        if isinstance(body, Mapping):
            parsed_type = _text(body.get("type")) or None

    lockup_verified, lockup = _parse_stake_lockup(data)
    stake_program_owned = owner == STAKE_PROGRAM_ID

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "candidate_pubkey": pubkey,
        "qualification_state": "account_found",
        "rpc_finalized_commitment": True,
        "context_slot": slot,
        "account_state_verified": True,
        "account_exists": True,
        "owner": owner,
        "executable": executable,
        "lamports": lamports,
        "space": space,
        "parsed_program": parsed_program,
        "parsed_type": parsed_type,
        "stake_program_owned": stake_program_owned,
        "stake_lockup_state_verified": lockup_verified,
        "stake_lockup": lockup,
        "candidate_role_verified": False,
        "stake_lockup_does_not_prove_distribution_role": lockup_verified,
        "xnt_distribution_mechanism_identified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "source_url": source_url,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "CHAIN",
    "CONTRACT_VERSION",
    "DISCOVERED",
    "NETWORK",
    "OFFICIAL_REWARDS_URL",
    "STAKE_PROGRAM_ID",
    "X1XntMechanismDiscoveryError",
    "discover_xnt_distribution_candidates",
    "extract_xnt_mechanism_claims",
    "normalize_x1_pubkey",
    "qualify_xnt_distribution_candidate",
]
