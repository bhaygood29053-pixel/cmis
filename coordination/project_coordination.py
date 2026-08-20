"""Shared Roberta/CMIS growth coordination contract.

This module is intentionally dependency-free so it can be mirrored in both
repositories and imported by tests, release tooling, or runtime adapters.

Architecture:
    Request flow:  Roberta -> X1 Scout -> CMIS
    Evidence flow: CMIS -> X1 Scout -> Roberta

The contract keeps project ownership explicit, requires promotion gates before
cross-project reliance, and preserves the read-only safety boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Mapping, Tuple


CONTRACT_ID = "roberta-cmis-growth-contract"
CONTRACT_VERSION = "1.0.0"

CANONICAL_REPOSITORY = "bhaygood29053-pixel/cmis"
MIRROR_REPOSITORIES: Tuple[str, ...] = (
    "bhaygood29053-pixel/cmis",
    "bhaygood29053-pixel/roberta-langgraph",
)

REQUEST_FLOW: Tuple[str, ...] = ("roberta", "x1_scout", "cmis")
EVIDENCE_FLOW: Tuple[str, ...] = ("cmis", "x1_scout", "roberta")


@dataclass(frozen=True)
class ProjectRole:
    name: str
    repository: str
    owns: FrozenSet[str]
    must_not: FrozenSet[str]


@dataclass(frozen=True)
class GrowthGate:
    gate_id: str
    owner: str
    depends_on: Tuple[str, ...]
    acceptance: FrozenSet[str]


PROJECTS: Mapping[str, ProjectRole] = {
    "cmis": ProjectRole(
        name="CMIS",
        repository="bhaygood29053-pixel/cmis",
        owns=frozenset(
            {
                "provider access",
                "evidence verification",
                "normalization",
                "history",
                "proof/freshness semantics",
                "deterministic risk and read-only intelligence",
                "public intelligence service contracts",
            }
        ),
        must_not=frozenset(
            {
                "sign transactions",
                "broadcast transactions",
                "hold wallet custody",
                "authorize execution",
                "invent unsupported behavioral labels",
            }
        ),
    ),
    "x1_scout": ProjectRole(
        name="X1 Scout",
        repository="bhaygood29053-pixel/roberta-langgraph",
        owns=frozenset(
            {
                "X1-specific request planning",
                "CMIS service selection",
                "evidence-preserving adaptation",
                "chain-specific limitations",
            }
        ),
        must_not=frozenset(
            {
                "bypass CMIS for verified provider facts",
                "erase evidence receipts or freshness",
                "convert unavailable facts into guesses",
                "authorize execution",
            }
        ),
    ),
    "roberta": ProjectRole(
        name="Roberta",
        repository="bhaygood29053-pixel/roberta-langgraph",
        owns=frozenset(
            {
                "user intent",
                "conversation coordination",
                "answer-first synthesis",
                "risk/evidence quality separation",
                "user-facing limitations",
            }
        ),
        must_not=frozenset(
            {
                "direct provider access for facts owned by CMIS",
                "claim stronger certainty than supplied evidence",
                "authorize execution",
                "sign or broadcast transactions",
            }
        ),
    ),
}


GROWTH_GATES: Tuple[GrowthGate, ...] = (
    GrowthGate(
        gate_id="cmis_verified_intelligence_public_contract",
        owner="cmis",
        depends_on=(),
        acceptance=frozenset(
            {
                "one narrow read-only service is versioned",
                "request and response schemas are explicit",
                "evidence receipt/proof/freshness rules are explicit",
                "null/unavailable/partial semantics fail closed",
                "facts, inference, and policy are separated",
                "unsupported behavioral labels remain unavailable",
                "exact-head regression tests pass",
            }
        ),
    ),
    GrowthGate(
        gate_id="x1_scout_verified_intelligence_adapter",
        owner="x1_scout",
        depends_on=("cmis_verified_intelligence_public_contract",),
        acceptance=frozenset(
            {
                "Scout calls only promoted CMIS services",
                "Scout preserves evidence receipt and limitations",
                "Scout preserves compatible-scope/freshness semantics",
                "Scout adds no unsupported behavioral interpretation",
                "configured X1 tests pass",
            }
        ),
    ),
    GrowthGate(
        gate_id="roberta_verified_intelligence_synthesis",
        owner="roberta",
        depends_on=("x1_scout_verified_intelligence_adapter",),
        acceptance=frozenset(
            {
                "answer is user-first and concise",
                "risk and evidence quality remain separate dimensions",
                "missing/stale/conflicting evidence fails closed",
                "CMIS limitations remain visible when material",
                "read-only production-readiness replay passes",
            }
        ),
    ),
    GrowthGate(
        gate_id="cross_project_release_compatibility",
        owner="roberta",
        depends_on=("roberta_verified_intelligence_synthesis",),
        acceptance=frozenset(
            {
                "both repositories declare the same contract version",
                "CMIS service version is supported by the Scout adapter",
                "Roberta tests the supported Scout response contract",
                "no execution or value-movement capability is introduced",
            }
        ),
    ),
)


CURRENT_MILESTONE = {
    "name": "first_verified_intelligence_service",
    "cmis_tracking_issue": 237,
    "roberta_tracking_issue": 73,
    "recommended_scope": "compatible-scope top-account concentration change with explicit-policy threshold evaluation",
    "status": "contract_pending",
}


GLOBAL_GUARDRAILS: FrozenSet[str] = frozenset(
    {
        "read-only intelligence only",
        "no transaction construction",
        "no transaction signing",
        "no transaction broadcasting",
        "no wallet custody",
        "no autonomous trading",
        "no value movement",
        "no direct Roberta/Scout provider bypass for CMIS-owned facts",
        "no whale/insider/bot/market-maker/manipulation/intent labels without separately promoted evidence contracts",
    }
)


def validate_coordination_contract() -> None:
    """Raise ValueError if this coordination contract is internally inconsistent."""
    repo_set = set(MIRROR_REPOSITORIES)
    project_repos = {role.repository for role in PROJECTS.values()}

    if CANONICAL_REPOSITORY not in repo_set:
        raise ValueError("Canonical repository must be included in MIRROR_REPOSITORIES.")

    if not project_repos.issubset(repo_set):
        raise ValueError("Every project repository must be covered by the mirror set.")

    if REQUEST_FLOW != tuple(reversed(EVIDENCE_FLOW)):
        raise ValueError("Request and evidence flows must be exact reverses.")

    seen = set()
    for gate in GROWTH_GATES:
        missing = set(gate.depends_on) - seen
        if missing:
            raise ValueError(
                f"Gate {gate.gate_id!r} depends on gates not yet declared: {sorted(missing)}"
            )
        if gate.owner not in PROJECTS:
            raise ValueError(f"Gate {gate.gate_id!r} has unknown owner {gate.owner!r}.")
        if gate.gate_id in seen:
            raise ValueError(f"Duplicate gate id: {gate.gate_id!r}")
        seen.add(gate.gate_id)


def next_required_gate(completed_gates: FrozenSet[str]) -> str | None:
    """Return the next gate whose dependencies are satisfied, or None if complete."""
    known = {gate.gate_id for gate in GROWTH_GATES}
    unknown = set(completed_gates) - known
    if unknown:
        raise ValueError(f"Unknown completed gate(s): {sorted(unknown)}")

    for gate in GROWTH_GATES:
        if gate.gate_id in completed_gates:
            continue
        if set(gate.depends_on).issubset(completed_gates):
            return gate.gate_id
    return None


def can_consume_verified_intelligence(
    completed_gates: FrozenSet[str],
    consumer: str,
) -> bool:
    """Return whether a layer is allowed to rely on the promoted intelligence service."""
    requirements = {
        "x1_scout": {"cmis_verified_intelligence_public_contract"},
        "roberta": {
            "cmis_verified_intelligence_public_contract",
            "x1_scout_verified_intelligence_adapter",
        },
    }
    if consumer not in requirements:
        raise ValueError(f"Unsupported consumer: {consumer!r}")
    return requirements[consumer].issubset(completed_gates)


validate_coordination_contract()


__all__ = [
    "CANONICAL_REPOSITORY",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "CURRENT_MILESTONE",
    "EVIDENCE_FLOW",
    "GLOBAL_GUARDRAILS",
    "GROWTH_GATES",
    "MIRROR_REPOSITORIES",
    "PROJECTS",
    "REQUEST_FLOW",
    "can_consume_verified_intelligence",
    "next_required_gate",
    "validate_coordination_contract",
]
