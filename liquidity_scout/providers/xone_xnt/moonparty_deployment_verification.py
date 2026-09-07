"""Exact deployment discovery/verification for the FairCrypto MoonParty design.

This contract deliberately separates three questions:

1. Does a bounded authoritative/public source expose an exact MoonParty address?
2. Does that exact address behave like the pinned FairCrypto MoonParty artifact?
3. Is the address independently corroborated as the Ethereum deployment bound to
   the already accepted Ethereum XONE contract?

Only multi-RPC corroboration may set moonparty_deployment_verified=true.
Even then, XNT-credit accounting is not promoted to native-XNT issuance,
transferability, vesting, an October-6 unlock, or cross-chain settlement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from liquidity_scout.providers.ethereum.xone_identity import (
    CHAIN_ID,
    NETWORK,
    XONE_CONTRACT,
)


CONTRACT_VERSION = "moonparty_deployment_verification/v1"
CHAIN = "ethereum"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Canonical selectors from the pinned MoonParty ABI.
XONE_SELECTOR = "0x217d907d"  # XONE()
TOTAL_BURN_POINTS_SELECTOR = "0x3a6e1165"  # totalBurnPoints()
TOTAL_ALLOCATED_XNT_CREDITS_SELECTOR = "0x53fa94f3"  # totalAllocatedXNTCredits()
DURATION_SELECTOR = "0x1be05289"  # DURATION()
GENESIS_TS_SELECTOR = "0xe3af6d0a"  # genesisTs()
AMP_SELECTOR = "0x0973e6ba"  # amp()
VMPX_SELECTOR = "0x80f4ec4a"  # VMPX()
XEN_BURN_SELECTOR = "0xf53b02ca"  # xenBurn()
XEN_CRYPTO_SELECTOR = "0x71141a58"  # xenCrypto()
XEN_TORRENT_SELECTOR = "0x543d7d97"  # xenTorrent()
SUPPORTS_INTERFACE_SELECTOR = "0x01ffc9a7"
IBURN_REDEEMABLE_INTERFACE_ID = "0x543746b1"

REQUIRED_RUNTIME_SELECTORS = (
    XONE_SELECTOR,
    TOTAL_BURN_POINTS_SELECTOR,
    TOTAL_ALLOCATED_XNT_CREDITS_SELECTOR,
    DURATION_SELECTOR,
    GENESIS_TS_SELECTOR,
    AMP_SELECTOR,
    VMPX_SELECTOR,
    XEN_BURN_SELECTOR,
    XEN_CRYPTO_SELECTOR,
    XEN_TORRENT_SELECTOR,
    SUPPORTS_INTERFACE_SELECTOR,
)

_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_ENV_RE = re.compile(
    r"(?i)MOONPARTY_ADDRESS(?:_[A-Z0-9_\-]+)?\s*[=:]\s*[\"']?"
    r"(0x[a-fA-F0-9]{40})"
)
_JSONISH_RE = re.compile(
    r"(?is)moonPartyAddress.{0,240}?(0x[a-fA-F0-9]{40})"
)
_REVERSE_JSONISH_RE = re.compile(
    r"(?is)(0x[a-fA-F0-9]{40}).{0,240}?moonPartyAddress"
)


class MoonPartyDeploymentVerificationError(RuntimeError):
    """Raised when deployment evidence cannot be verified safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _address(value: Any, *, field: str) -> str:
    text = _text(value).casefold()
    if len(text) != 42 or not text.startswith("0x"):
        raise MoonPartyDeploymentVerificationError(f"{field} is not a 20-byte address")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise MoonPartyDeploymentVerificationError(f"{field} is not hexadecimal") from exc
    return text


def _hex_bytes(value: Any, *, field: str, allow_empty: bool = False) -> bytes:
    text = _text(value)
    if not text.startswith("0x"):
        raise MoonPartyDeploymentVerificationError(f"{field} is not 0x-prefixed hex")
    payload = text[2:]
    if len(payload) % 2:
        raise MoonPartyDeploymentVerificationError(f"{field} has odd-length hex")
    if not payload and allow_empty:
        return b""
    if not payload:
        raise MoonPartyDeploymentVerificationError(f"{field} is empty")
    try:
        return bytes.fromhex(payload)
    except ValueError as exc:
        raise MoonPartyDeploymentVerificationError(f"{field} is malformed hex") from exc


def _decode_word(value: Any, *, field: str) -> bytes:
    payload = _hex_bytes(value, field=field)
    if len(payload) != 32:
        raise MoonPartyDeploymentVerificationError(f"{field} must be one ABI word")
    return payload


def _decode_uint(value: Any, *, field: str) -> int:
    return int.from_bytes(_decode_word(value, field=field), "big")


def _decode_bool(value: Any, *, field: str) -> bool:
    parsed = _decode_uint(value, field=field)
    if parsed not in (0, 1):
        raise MoonPartyDeploymentVerificationError(f"{field} is not a canonical ABI bool")
    return bool(parsed)


def _decode_address(value: Any, *, field: str) -> str:
    word = _decode_word(value, field=field)
    if any(word[:12]):
        raise MoonPartyDeploymentVerificationError(f"{field} address word has nonzero padding")
    return _address("0x" + word[12:].hex(), field=field)


def _supports_interface_calldata(interface_id: str = IBURN_REDEEMABLE_INTERFACE_ID) -> str:
    interface_id = _text(interface_id).casefold()
    if len(interface_id) != 10 or not interface_id.startswith("0x"):
        raise ValueError("interface_id must be a 4-byte 0x-prefixed value")
    try:
        int(interface_id[2:], 16)
    except ValueError as exc:
        raise ValueError("interface_id must be hexadecimal") from exc
    return SUPPORTS_INTERFACE_SELECTOR + interface_id[2:] + ("0" * 56)


def _artifact_runtime(artifact: Mapping[str, Any]) -> bytes:
    if not isinstance(artifact, Mapping):
        raise MoonPartyDeploymentVerificationError("artifact must be a mapping")
    if _text(artifact.get("contractName")) != "MoonParty":
        raise MoonPartyDeploymentVerificationError("artifact contractName is not MoonParty")
    return _hex_bytes(
        artifact.get("deployedBytecode"),
        field="MoonParty artifact deployedBytecode",
    )


def _metadata_trailer(code: bytes) -> bytes:
    if len(code) < 2:
        raise MoonPartyDeploymentVerificationError("runtime bytecode is too short for metadata")
    metadata_length = int.from_bytes(code[-2:], "big")
    trailer_length = metadata_length + 2
    if metadata_length <= 0 or trailer_length > len(code):
        raise MoonPartyDeploymentVerificationError("runtime metadata trailer length is invalid")
    return code[-trailer_length:]


def _runtime_compatibility(
    runtime_code: bytes,
    artifact_runtime: bytes,
) -> dict[str, Any]:
    if not runtime_code:
        raise MoonPartyDeploymentVerificationError("candidate has no runtime bytecode")

    exact_length = len(runtime_code) == len(artifact_runtime)
    artifact_meta = _metadata_trailer(artifact_runtime)
    runtime_meta = _metadata_trailer(runtime_code)
    metadata_matches = runtime_meta == artifact_meta
    selector_presence = {
        selector: bytes.fromhex(selector[2:]) in runtime_code
        for selector in REQUIRED_RUNTIME_SELECTORS
    }
    selectors_present = all(selector_presence.values())

    return {
        "candidate_runtime_bytes": len(runtime_code),
        "artifact_runtime_bytes": len(artifact_runtime),
        "runtime_length_matches_artifact": exact_length,
        "compiler_metadata_trailer_matches": metadata_matches,
        "required_runtime_selector_presence": selector_presence,
        "required_runtime_selectors_present": selectors_present,
        "runtime_code_sha256": sha256(runtime_code).hexdigest(),
        "artifact_runtime_sha256_unlinked": sha256(artifact_runtime).hexdigest(),
        "runtime_bytecode_exact_equality_required": False,
        "artifact_has_deployment_specific_link_or_immutable_regions": True,
        "moonparty_runtime_compatible": (
            exact_length and metadata_matches and selectors_present
        ),
    }


def discover_moonparty_deployment_candidates(
    documents: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 25,
) -> dict[str, Any]:
    """Extract exact Ethereum candidates only from MoonParty-specific context."""

    if not isinstance(documents, Sequence) or isinstance(
        documents, (str, bytes, bytearray)
    ):
        raise MoonPartyDeploymentVerificationError("documents must be a sequence")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")

    rows: dict[str, dict[str, Any]] = {}
    inspected: list[dict[str, Any]] = []

    for index, document in enumerate(documents):
        if not isinstance(document, Mapping):
            raise MoonPartyDeploymentVerificationError("each document must be a mapping")
        source_id = _text(document.get("source_id")) or f"source_{index}"
        url = _text(document.get("url"))
        text_value = document.get("text")
        if not url or not isinstance(text_value, str):
            raise MoonPartyDeploymentVerificationError(
                "each document requires url and text"
            )

        matches: list[tuple[str, str]] = []
        for regex, basis in (
            (_ENV_RE, "explicit_moonparty_env_binding"),
            (_JSONISH_RE, "moonparty_address_forward_context"),
            (_REVERSE_JSONISH_RE, "moonparty_address_reverse_context"),
        ):
            for found in regex.finditer(text_value):
                matches.append((found.group(1), basis))

        # A bounded fallback requires the literal MoonParty marker and the address
        # inside the same short source line. Generic page-wide addresses are ignored.
        for line in text_value.splitlines():
            if "moonparty" not in line.casefold():
                continue
            for found in _ADDRESS_RE.findall(line):
                matches.append((found, "same_line_moonparty_context"))

        unique_source_addresses: set[str] = set()
        for raw_address, basis in matches:
            address = _address(raw_address, field="candidate address")
            if address in {ZERO_ADDRESS, XONE_CONTRACT}:
                continue
            unique_source_addresses.add(address)
            row = rows.setdefault(
                address,
                {
                    "candidate_address": address,
                    "candidate_role": "unverified_moonparty_deployment_candidate",
                    "source_bindings": [],
                    "eligible_for_direct_rpc_qualification": True,
                    "moonparty_deployment_verified": False,
                    "execution_authorized": False,
                },
            )
            binding = {
                "source_id": source_id,
                "url": url,
                "basis": basis,
            }
            if binding not in row["source_bindings"]:
                row["source_bindings"].append(binding)

        inspected.append(
            {
                "source_id": source_id,
                "url": url,
                "moonparty_marker_present": "moonparty" in text_value.casefold(),
                "exact_candidate_count": len(unique_source_addresses),
            }
        )

    candidates = sorted(
        rows.values(),
        key=lambda row: (
            -len(row["source_bindings"]),
            row["candidate_address"],
        ),
    )[:max_candidates]

    return {
        "contract_version": CONTRACT_VERSION,
        "deployment_candidate_discovery_verified": True,
        "inspected_document_count": len(inspected),
        "inspected_documents": inspected,
        "deployment_candidate_count": len(candidates),
        "candidates": candidates,
        "zero_candidates_are_scoped_corpus_evidence_only": len(candidates) == 0,
        "zero_candidates_do_not_prove_non_deployment": True,
        "moonparty_deployment_verified": False,
        "moonparty_deployment_chain_verified": False,
        "moonparty_runtime_compatible": False,
        "moonparty_xone_binding_verified": False,
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_issuance_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def verify_moonparty_deployment_candidate(
    candidate_address: str,
    *,
    artifact: Mapping[str, Any],
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
) -> dict[str, Any]:
    """Qualify one exact Ethereum candidate without final deployment promotion."""

    candidate = _address(candidate_address, field="candidate address")
    if candidate in {ZERO_ADDRESS, XONE_CONTRACT}:
        raise MoonPartyDeploymentVerificationError("candidate address is not eligible")

    chain_id = _text(rpc_call("eth_chainId", [])).casefold()
    if chain_id != CHAIN_ID:
        raise MoonPartyDeploymentVerificationError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    runtime_code = _hex_bytes(
        rpc_call("eth_getCode", [candidate, "finalized"]),
        field="candidate runtime bytecode",
        allow_empty=True,
    )
    artifact_runtime = _artifact_runtime(artifact)
    runtime = _runtime_compatibility(runtime_code, artifact_runtime)
    if not runtime["moonparty_runtime_compatible"]:
        raise MoonPartyDeploymentVerificationError(
            "candidate runtime is not compatible with pinned MoonParty artifact"
        )

    def call(selector: str) -> Any:
        return rpc_call(
            "eth_call",
            [{"to": candidate, "data": selector}, "finalized"],
        )

    xone_binding = _decode_address(call(XONE_SELECTOR), field="XONE()")
    if xone_binding != XONE_CONTRACT:
        raise MoonPartyDeploymentVerificationError(
            f"XONE() binding mismatch: {xone_binding}"
        )

    burn_redeemer_supported = _decode_bool(
        rpc_call(
            "eth_call",
            [
                {
                    "to": candidate,
                    "data": _supports_interface_calldata(),
                },
                "finalized",
            ],
        ),
        field="supportsInterface(IBurnRedeemable)",
    )
    if not burn_redeemer_supported:
        raise MoonPartyDeploymentVerificationError(
            "candidate does not support IBurnRedeemable"
        )

    immutable_bindings = {
        "XONE": xone_binding,
        "VMPX": _decode_address(call(VMPX_SELECTOR), field="VMPX()"),
        "xenBurn": _decode_address(call(XEN_BURN_SELECTOR), field="xenBurn()"),
        "xenCrypto": _decode_address(call(XEN_CRYPTO_SELECTOR), field="xenCrypto()"),
        "xenTorrent": _decode_address(call(XEN_TORRENT_SELECTOR), field="xenTorrent()"),
    }
    for name, address in immutable_bindings.items():
        if address == ZERO_ADDRESS:
            raise MoonPartyDeploymentVerificationError(
                f"{name} binding is zero address"
            )

    state = {
        "DURATION": _decode_uint(call(DURATION_SELECTOR), field="DURATION()"),
        "genesisTs": _decode_uint(call(GENESIS_TS_SELECTOR), field="genesisTs()"),
        "amp": _decode_uint(call(AMP_SELECTOR), field="amp()"),
        "totalBurnPoints": _decode_uint(
            call(TOTAL_BURN_POINTS_SELECTOR),
            field="totalBurnPoints()",
        ),
        "totalAllocatedXNTCredits": _decode_uint(
            call(TOTAL_ALLOCATED_XNT_CREDITS_SELECTOR),
            field="totalAllocatedXNTCredits()",
        ),
    }

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "candidate_address": candidate,
        "source_url": source_url,
        "candidate_runtime_qualification_verified": True,
        **runtime,
        "immutable_bindings": immutable_bindings,
        "moonparty_xone_binding_verified": True,
        "iburnredeemable_interface_supported": True,
        "bounded_live_state": state,
        "bounded_state_is_not_native_xnt_issuance_proof": True,
        "single_rpc_candidate_qualified": True,
        "moonparty_deployment_verified": False,
        "moonparty_deployment_chain_verified": False,
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_credit_transferability_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


def corroborate_moonparty_deployment(
    proofs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Promote exact deployment identity only after two distinct RPC transports agree."""

    if not isinstance(proofs, Sequence) or isinstance(proofs, (str, bytes, bytearray)):
        raise MoonPartyDeploymentVerificationError("proofs must be a sequence")
    if len(proofs) < 2:
        raise MoonPartyDeploymentVerificationError(
            "at least two direct-RPC proofs are required"
        )

    normalized: list[Mapping[str, Any]] = []
    hosts: set[str] = set()
    for proof in proofs:
        if not isinstance(proof, Mapping):
            raise MoonPartyDeploymentVerificationError("each proof must be a mapping")
        if proof.get("single_rpc_candidate_qualified") is not True:
            raise MoonPartyDeploymentVerificationError(
                "all proofs must be qualified MoonParty candidates"
            )
        if proof.get("moonparty_xone_binding_verified") is not True:
            raise MoonPartyDeploymentVerificationError(
                "all proofs must verify exact XONE binding"
            )
        if proof.get("moonparty_runtime_compatible") is not True:
            raise MoonPartyDeploymentVerificationError(
                "all proofs must verify runtime compatibility"
            )
        source_url = _text(proof.get("source_url"))
        host = (urlparse(source_url).hostname or "").casefold()
        if not host:
            raise MoonPartyDeploymentVerificationError(
                "each proof requires a valid source_url"
            )
        hosts.add(host)
        normalized.append(proof)

    if len(hosts) < 2:
        raise MoonPartyDeploymentVerificationError(
            "two distinct RPC transport hosts are required"
        )

    baseline = normalized[0]
    immutable_keys = (
        "candidate_address",
        "chain_id",
        "runtime_code_sha256",
        "candidate_runtime_bytes",
        "artifact_runtime_bytes",
        "immutable_bindings",
    )
    for proof in normalized[1:]:
        for key in immutable_keys:
            if proof.get(key) != baseline.get(key):
                raise MoonPartyDeploymentVerificationError(
                    f"RPC proofs disagree on {key}"
                )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "moonparty_address": baseline["candidate_address"],
        "runtime_code_sha256": baseline["runtime_code_sha256"],
        "runtime_code_bytes": baseline["candidate_runtime_bytes"],
        "immutable_bindings": dict(baseline["immutable_bindings"]),
        "rpc_proof_count": len(normalized),
        "rpc_transport_hosts": sorted(hosts),
        "multi_rpc_corroborated": True,
        "transport_provider_diversity_verified": True,
        "rpc_backend_source_independence_verified": False,
        "moonparty_deployment_verified": True,
        "moonparty_deployment_chain_verified": True,
        "moonparty_runtime_compatible": True,
        "moonparty_xone_binding_verified": True,
        "iburnredeemable_interface_supported": True,
        "xone_to_xnt_credit_design_link_deployment_bound": True,
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_credit_transferability_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "AMP_SELECTOR",
    "CHAIN",
    "CONTRACT_VERSION",
    "DURATION_SELECTOR",
    "GENESIS_TS_SELECTOR",
    "IBURN_REDEEMABLE_INTERFACE_ID",
    "MoonPartyDeploymentVerificationError",
    "REQUIRED_RUNTIME_SELECTORS",
    "SUPPORTS_INTERFACE_SELECTOR",
    "TOTAL_ALLOCATED_XNT_CREDITS_SELECTOR",
    "TOTAL_BURN_POINTS_SELECTOR",
    "VMPX_SELECTOR",
    "XEN_BURN_SELECTOR",
    "XEN_CRYPTO_SELECTOR",
    "XEN_TORRENT_SELECTOR",
    "XONE_SELECTOR",
    "corroborate_moonparty_deployment",
    "discover_moonparty_deployment_candidates",
    "verify_moonparty_deployment_candidate",
]
