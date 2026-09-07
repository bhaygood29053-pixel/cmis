"""Pinned authoritative-source semantics for FairCrypto MoonParty/XONE.

This contract verifies what the pinned FairCrypto source artifacts say. It does
not verify a deployed MoonParty address, chain activation, native XNT issuance,
credit-to-XNT equivalence, vesting, or cross-chain settlement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Any


CONTRACT_VERSION = "xone_xnt_moonparty_source_semantics/v1"

FAIRCRYPTO_X1_APP_REPO = "FairCrypto/x1-app"
FAIRCRYPTO_X1_APP_COMMIT = "abf168fad119e91a8da0773625fd6115e8756cb4"
FAIRCRYPTO_XONE_REPO = "FairCrypto/XONE"
FAIRCRYPTO_XONE_COMMIT = "267bfeaabd69bf81f272cfd52aa5082333cd317a"

MOONPARTY_ABI_PATH = "public/abi/MoonParty.json"
MOONPARTY_TYPES_PATH = "contexts/MoonParty/types.ts"
MOONPARTY_CONTEXT_PATH = "contexts/MoonParty/index.tsx"
MOONPARTY_STATE_PATH = "app/x1/moon-party/state.tsx"
MOONPARTY_GLOBAL_PATH = "app/x1/moon-party/global.tsx"
PROJECTS_PATH = "config/projects.ts"
XONE_SOURCE_PATH = "contracts/XONE.sol"

_REQUIRED_FUNCTIONS = {
    "XONE": (),
    "redeemXone": ("uint256",),
    "getRedeemableXONE": (),
    "getExpectedBurnPointsForXone": (),
    "getXoneRate": ("uint256",),
    "allocateXNTCredits": ("address",),
    "totalAllocatedXNTCredits": (),
    "totalBurnPoints": (),
    "onTokenBurned": ("address", "uint256"),
    "supportsInterface": ("bytes4",),
}

_REQUIRED_SOURCE_KEYS = (
    "moonparty_abi",
    "moonparty_types",
    "moonparty_context",
    "moonparty_state",
    "moonparty_global",
    "projects",
    "xone_source",
)


class XoneXntMoonPartySourceSemanticsError(RuntimeError):
    """Raised when pinned source material is malformed or semantically incomplete."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_digest(documents: Mapping[str, str]) -> str:
    normalized = "\n".join(
        f"{key}\n{documents[key]}"
        for key in sorted(documents)
    )
    return "sha256:" + sha256(normalized.encode("utf-8")).hexdigest()


def _parse_abi_document(value: str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        parsed = value
    else:
        try:
            parsed = json.loads(_text(value))
        except json.JSONDecodeError as exc:
            raise XoneXntMoonPartySourceSemanticsError(
                f"MoonParty ABI JSON is malformed: {exc}"
            ) from exc
    if not isinstance(parsed, Mapping):
        raise XoneXntMoonPartySourceSemanticsError("MoonParty ABI must be an object")
    abi = parsed.get("abi")
    if not isinstance(abi, Sequence) or isinstance(abi, (str, bytes, bytearray)):
        raise XoneXntMoonPartySourceSemanticsError("MoonParty artifact is missing ABI")
    return parsed


def _inputs(item: Mapping[str, Any]) -> tuple[str, ...]:
    raw = item.get("inputs")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return ()
    result: list[str] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise XoneXntMoonPartySourceSemanticsError("ABI input row must be an object")
        result.append(_text(row.get("type")))
    return tuple(result)


def _abi_semantics(artifact: Mapping[str, Any]) -> dict[str, Any]:
    abi = artifact["abi"]
    constructor_xone = False
    functions: dict[str, tuple[str, ...]] = {}
    events: set[str] = set()

    for raw in abi:
        if not isinstance(raw, Mapping):
            raise XoneXntMoonPartySourceSemanticsError("ABI row must be an object")
        row_type = _text(raw.get("type"))
        if row_type == "constructor":
            for arg in raw.get("inputs", []):
                if (
                    isinstance(arg, Mapping)
                    and _text(arg.get("name")) == "_xoneAddress"
                    and _text(arg.get("type")) == "address"
                ):
                    constructor_xone = True
        elif row_type == "function":
            name = _text(raw.get("name"))
            if name:
                functions[name] = _inputs(raw)
        elif row_type == "event":
            name = _text(raw.get("name"))
            if name:
                events.add(name)

    missing = [
        f"{name}({','.join(inputs)})"
        for name, inputs in _REQUIRED_FUNCTIONS.items()
        if functions.get(name) != inputs
    ]
    if not constructor_xone:
        missing.append("constructor(_xoneAddress:address)")
    if missing:
        raise XoneXntMoonPartySourceSemanticsError(
            "MoonParty authoritative artifact is missing required semantics: "
            + ", ".join(missing)
        )

    return {
        "contract_name": _text(artifact.get("contractName")),
        "source_name": _text(artifact.get("sourceName")),
        "constructor_accepts_xone_address": constructor_xone,
        "required_function_signatures_verified": True,
        "verified_functions": {
            name: list(inputs)
            for name, inputs in sorted(_REQUIRED_FUNCTIONS.items())
        },
        "asset_burned_event_present": "AssetBurned" in events,
        "burn_points_allocated_event_present": "BurnPointsAllocated" in events,
        "redeemed_event_present": "Redeemed" in events,
    }


def verify_moonparty_source_semantics(
    documents: Mapping[str, str],
    *,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify pinned FairCrypto source semantics with fail-closed boundaries."""

    if not isinstance(documents, Mapping):
        raise XoneXntMoonPartySourceSemanticsError("documents must be a mapping")

    missing_documents = [key for key in _REQUIRED_SOURCE_KEYS if not _text(documents.get(key))]
    if missing_documents:
        raise XoneXntMoonPartySourceSemanticsError(
            "missing required pinned source documents: " + ", ".join(missing_documents)
        )

    if provenance is not None:
        expected = {
            "x1_app_repository": FAIRCRYPTO_X1_APP_REPO,
            "x1_app_commit": FAIRCRYPTO_X1_APP_COMMIT,
            "xone_repository": FAIRCRYPTO_XONE_REPO,
            "xone_commit": FAIRCRYPTO_XONE_COMMIT,
        }
        for key, value in expected.items():
            if _text(provenance.get(key)) != value:
                raise XoneXntMoonPartySourceSemanticsError(
                    f"pinned provenance mismatch for {key}: "
                    f"expected {value!r}, got {_text(provenance.get(key))!r}"
                )

    artifact = _parse_abi_document(documents["moonparty_abi"])
    abi = _abi_semantics(artifact)

    types_source = documents["moonparty_types"]
    context_source = documents["moonparty_context"]
    state_source = documents["moonparty_state"]
    global_source = documents["moonparty_global"]
    projects_source = documents["projects"]
    xone_source = documents["xone_source"]

    checks = {
        "types_allocate_xnt_credits_mapping_present":
            "mapping(address => uint256) public allocateXNTCredits;" in types_source,
        "types_user_allocate_xnt_credits_present":
            "allocateXNTCredits: bigint;" in types_source,
        "context_total_allocated_xnt_credits_read_present":
            "functionName: 'totalAllocatedXNTCredits'" in context_source,
        "state_xone_participation_row_present":
            "contract: 'xoneAddress'" in state_source and "id: 'XONE'" in state_source,
        "state_allocate_cta_present":
            "allocate_cta: 'Allocate'" in state_source,
        "global_xnt_distribution_label_present":
            "XNT Distribution" in global_source,
        "global_burn_points_allocated_label_present":
            "Burn Points Allocated" in global_source,
        "projects_moonparty_faircrypto_owned":
            "name: 'MoonParty'" in projects_source
            and "owner: 'Fair Crypto Foundation'" in projects_source,
        "projects_xone_faircrypto_owned":
            "name: 'XONE'" in projects_source
            and "owner: 'Fair Crypto Foundation'" in projects_source,
        "xone_iburnredeemable_dependency_present":
            "IBurnRedeemable.sol" in xone_source,
        "xone_burn_calls_redeemer_callback":
            "IBurnRedeemable(_msgSender()).onTokenBurned(user, amount);" in xone_source,
        "xone_burn_records_user_burns":
            "userBurns[user] += amount;" in xone_source,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise XoneXntMoonPartySourceSemanticsError(
            "pinned authoritative source semantics failed: " + ", ".join(failed)
        )

    semantic_claim = (
        "Pinned FairCrypto source code defines a MoonParty design where XONE is a "
        "participating/redeemable asset and the same contract exposes per-user and "
        "aggregate XNT credit-allocation accounting."
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "source_provenance_verified": provenance is not None,
        "authoritative_source_semantics_verified": True,
        "source_digest": _source_digest({
            key: _text(documents[key])
            for key in _REQUIRED_SOURCE_KEYS
        }),
        "pinned_sources": {
            "x1_app_repository": FAIRCRYPTO_X1_APP_REPO,
            "x1_app_commit": FAIRCRYPTO_X1_APP_COMMIT,
            "xone_repository": FAIRCRYPTO_XONE_REPO,
            "xone_commit": FAIRCRYPTO_XONE_COMMIT,
        },
        "abi_semantics": abi,
        "source_checks": checks,
        "semantic_claim": semantic_claim,
        "xone_participation_in_moonparty_source_verified": True,
        "xnt_credit_allocation_surface_in_moonparty_source_verified": True,
        "xone_to_xnt_credit_design_link_verified": True,
        "moonparty_deployment_verified": False,
        "moonparty_deployment_chain_verified": False,
        "moonparty_runtime_bytecode_verified": False,
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_credit_transferability_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "october_6_unlock_applies_to_xone_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT_VERSION",
    "FAIRCRYPTO_X1_APP_COMMIT",
    "FAIRCRYPTO_X1_APP_REPO",
    "FAIRCRYPTO_XONE_COMMIT",
    "FAIRCRYPTO_XONE_REPO",
    "MOONPARTY_ABI_PATH",
    "MOONPARTY_CONTEXT_PATH",
    "MOONPARTY_GLOBAL_PATH",
    "MOONPARTY_STATE_PATH",
    "MOONPARTY_TYPES_PATH",
    "PROJECTS_PATH",
    "XONE_SOURCE_PATH",
    "XoneXntMoonPartySourceSemanticsError",
    "verify_moonparty_source_semantics",
]
