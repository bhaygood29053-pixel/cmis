"""Fail-closed provenance gate for X1 Warp Bridge read-only source discovery.

This module does not discover endpoints, perform HTTP requests, or interpret bridge state.
It only records whether an exact candidate read URL has sufficient provenance to become
eligible for a later deterministic contract probe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import urlsplit


_ALLOWED_PROOF_TYPES = frozenset(
    {
        "x1_owned_documentation",
        "official_app_network_observation",
        "x1_owned_application_artifact",
        "onchain_configuration",
    }
)


@dataclass(frozen=True)
class BridgeSourceProof:
    proof_type: str
    reference: str


@dataclass(frozen=True)
class BridgeSourceProvenance:
    chain: str
    url: str
    host: str
    proof_types: tuple[str, ...]
    source_provenance_verified: bool
    read_probe_eligible: bool
    endpoint_semantics_verified: bool
    cmis_promotable: bool
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_bridge_source_provenance(
    *,
    url: str,
    proofs: Iterable[BridgeSourceProof],
) -> BridgeSourceProvenance:
    """Evaluate provenance for one exact X1 bridge candidate URL.

    Eligibility means only that a later GET/read-only contract probe may be built for
    the exact URL. It does not verify endpoint semantics or any bridge market fact.
    """

    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    normalized_url = url.strip()
    parsed = urlsplit(normalized_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("bridge source URL must be an absolute https URL")
    if parsed.username or parsed.password:
        raise ValueError("bridge source URL must not contain credentials")
    if parsed.fragment:
        raise ValueError("bridge source URL must not contain a fragment")

    proof_types: set[str] = set()
    warnings: list[str] = []
    for proof in proofs:
        if not isinstance(proof, BridgeSourceProof):
            raise TypeError("proofs must contain BridgeSourceProof values")
        proof_type = proof.proof_type.strip()
        reference = proof.reference.strip()
        if not proof_type or not reference:
            raise ValueError("bridge source proofs require proof_type and reference")
        if proof_type not in _ALLOWED_PROOF_TYPES:
            warnings.append(f"unsupported provenance proof type: {proof_type}")
            continue
        proof_types.add(proof_type)

    verified = bool(proof_types)
    if not verified:
        warnings.append("no accepted provenance proof establishes this exact bridge source")

    return BridgeSourceProvenance(
        chain="x1",
        url=normalized_url,
        host=parsed.hostname.lower(),
        proof_types=tuple(sorted(proof_types)),
        source_provenance_verified=verified,
        read_probe_eligible=verified,
        endpoint_semantics_verified=False,
        cmis_promotable=False,
        warnings=tuple(warnings),
    )
