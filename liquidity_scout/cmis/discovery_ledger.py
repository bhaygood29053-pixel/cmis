"""Deterministic foundation-only X1 Discovery Ledger v1.

This module records immutable CMIS observations and derives the earliest verified
fact-time observation for an exact canonical X1 asset/observation kind. It is
not a public service and does not authorize Scout reliance or execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping, Optional, Tuple


DISCOVERY_LEDGER_CONTRACT_VERSION = "x1_discovery_ledger/v1"
DISCOVERY_SUBJECT_KIND = "x1_asset"
DISCOVERY_IDENTITY_CONTRACT = "x1_asset_identity/v1"
DISCOVERY_PUBLIC_SERVICE_PROMOTED = False
DISCOVERY_SCOUT_RELIANCE_PROMOTED = False
DISCOVERY_READ_ONLY = True
DISCOVERY_EXECUTION_AUTHORIZED = False

VERIFICATION_STATES = frozenset({"verified", "partial", "unavailable", "conflict"})
_BASE58 = frozenset(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)


class DiscoveryLedgerContractError(ValueError):
    """Raised when a discovery observation/state violates the v1 contract."""


def _text(name: str, value: object) -> str:
    result = str(value or "").strip()
    if not result:
        raise DiscoveryLedgerContractError(f"{name} must be non-empty text")
    return result


def _optional_text(name: str, value: object) -> Optional[str]:
    if value is None:
        return None
    result = str(value).strip()
    if not result:
        raise DiscoveryLedgerContractError(
            f"{name} must be non-empty text when supplied"
        )
    return result


def _unix_seconds(
    name: str,
    value: object,
    *,
    allow_none: bool,
) -> Optional[int]:
    if value is None and allow_none:
        return None
    if type(value) is not int or value < 0:
        raise DiscoveryLedgerContractError(
            f"{name} must be a non-negative integer Unix-second timestamp"
        )
    return value


def _text_tuple(name: str, value: object) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise DiscoveryLedgerContractError(f"{name} must be a list/tuple of text")
    items = []
    for raw in value:
        item = str(raw or "").strip()
        if not item:
            raise DiscoveryLedgerContractError(
                f"{name} entries must be non-empty text"
            )
        items.append(item)
    return tuple(sorted(set(items)))


def _is_x1_mint(value: str) -> bool:
    return 32 <= len(value) <= 44 and all(char in _BASE58 for char in value)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


@dataclass(frozen=True)
class DiscoveryObservationV1:
    """One immutable, provenance-preserving internal discovery observation."""

    chain: str
    subject_kind: str
    subject_id: str
    mint: str
    identity_contract: str
    identity_verified: bool
    observation_kind: str
    fact_time_unix: Optional[int]
    fact_time_verified: bool
    recorded_at_unix: int
    source_id: str
    source_role: str
    source_scope: str
    verification_state: str
    evidence_receipt_id: Optional[str] = None
    proof_score_id: Optional[str] = None
    limitations: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        # Canonicalize internal scalar/list fields even if a caller uses the
        # dataclass constructor directly instead of the preferred create().
        object.__setattr__(self, "chain", _text("chain", self.chain).lower())
        object.__setattr__(
            self,
            "subject_kind",
            _text("subject_kind", self.subject_kind),
        )
        object.__setattr__(self, "subject_id", _text("subject_id", self.subject_id))
        object.__setattr__(self, "mint", _text("mint", self.mint))
        object.__setattr__(
            self,
            "identity_contract",
            _text("identity_contract", self.identity_contract),
        )
        object.__setattr__(
            self,
            "observation_kind",
            _text("observation_kind", self.observation_kind),
        )
        object.__setattr__(self, "source_id", _text("source_id", self.source_id))
        object.__setattr__(
            self,
            "source_role",
            _text("source_role", self.source_role),
        )
        object.__setattr__(
            self,
            "source_scope",
            _text("source_scope", self.source_scope),
        )
        object.__setattr__(
            self,
            "verification_state",
            _text("verification_state", self.verification_state).lower(),
        )
        object.__setattr__(
            self,
            "evidence_receipt_id",
            _optional_text("evidence_receipt_id", self.evidence_receipt_id),
        )
        object.__setattr__(
            self,
            "proof_score_id",
            _optional_text("proof_score_id", self.proof_score_id),
        )
        object.__setattr__(
            self,
            "limitations",
            _text_tuple("limitations", self.limitations),
        )
        object.__setattr__(self, "warnings", _text_tuple("warnings", self.warnings))

        if self.chain != "x1":
            raise DiscoveryLedgerContractError("Discovery Ledger v1 is X1-only")
        if self.subject_kind != DISCOVERY_SUBJECT_KIND:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger v1 subject_kind must be x1_asset"
            )
        if not _is_x1_mint(self.mint):
            raise DiscoveryLedgerContractError(
                "Discovery Ledger v1 requires an address-shaped X1 mint"
            )
        if self.subject_id != self.mint:
            raise DiscoveryLedgerContractError(
                "Discovery subject_id must equal the canonical X1 mint"
            )
        if self.identity_contract != DISCOVERY_IDENTITY_CONTRACT:
            raise DiscoveryLedgerContractError(
                "Discovery identity_contract must be x1_asset_identity/v1"
            )
        if self.identity_verified is not True:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger v1 requires verified X1 mint identity"
            )
        _text("observation_kind", self.observation_kind)
        if (
            self.fact_time_unix is not None
            and (type(self.fact_time_unix) is not int or self.fact_time_unix < 0)
        ):
            raise DiscoveryLedgerContractError(
                "fact_time_unix must be a non-negative integer when supplied"
            )
        if self.fact_time_verified is True and self.fact_time_unix is None:
            raise DiscoveryLedgerContractError(
                "fact_time_verified=true requires fact_time_unix"
            )
        if not isinstance(self.fact_time_verified, bool):
            raise DiscoveryLedgerContractError("fact_time_verified must be boolean")
        if type(self.recorded_at_unix) is not int or self.recorded_at_unix < 0:
            raise DiscoveryLedgerContractError(
                "recorded_at_unix must be a non-negative integer"
            )
        _text("source_id", self.source_id)
        _text("source_role", self.source_role)
        _text("source_scope", self.source_scope)
        if self.verification_state not in VERIFICATION_STATES:
            raise DiscoveryLedgerContractError(
                "unsupported discovery verification_state"
            )
        _optional_text("evidence_receipt_id", self.evidence_receipt_id)
        _optional_text("proof_score_id", self.proof_score_id)
        _text_tuple("limitations", self.limitations)
        _text_tuple("warnings", self.warnings)
        if self.execution_authorized is not False:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger must preserve execution_authorized=false"
            )

    @classmethod
    def create(
        cls,
        *,
        mint: str,
        observation_kind: str,
        fact_time_unix: Optional[int],
        fact_time_verified: bool,
        recorded_at_unix: int,
        source_id: str,
        source_role: str,
        source_scope: str,
        verification_state: str,
        evidence_receipt_id: Optional[str] = None,
        proof_score_id: Optional[str] = None,
        limitations: Iterable[str] = (),
        warnings: Iterable[str] = (),
        chain: str = "x1",
        subject_kind: str = DISCOVERY_SUBJECT_KIND,
        subject_id: Optional[str] = None,
        identity_contract: str = DISCOVERY_IDENTITY_CONTRACT,
        identity_verified: bool = True,
        execution_authorized: bool = False,
    ) -> "DiscoveryObservationV1":
        normalized_mint = _text("mint", mint)
        normalized_subject = (
            _text("subject_id", subject_id)
            if subject_id is not None
            else normalized_mint
        )
        normalized_fact_time = _unix_seconds(
            "fact_time_unix",
            fact_time_unix,
            allow_none=True,
        )
        normalized_recorded_at = _unix_seconds(
            "recorded_at_unix",
            recorded_at_unix,
            allow_none=False,
        )
        assert normalized_recorded_at is not None
        if not isinstance(fact_time_verified, bool):
            raise DiscoveryLedgerContractError("fact_time_verified must be boolean")
        if not isinstance(identity_verified, bool):
            raise DiscoveryLedgerContractError("identity_verified must be boolean")
        if not isinstance(execution_authorized, bool):
            raise DiscoveryLedgerContractError(
                "execution_authorized must be boolean"
            )
        return cls(
            chain=_text("chain", chain).lower(),
            subject_kind=_text("subject_kind", subject_kind),
            subject_id=normalized_subject,
            mint=normalized_mint,
            identity_contract=_text("identity_contract", identity_contract),
            identity_verified=identity_verified,
            observation_kind=_text("observation_kind", observation_kind),
            fact_time_unix=normalized_fact_time,
            fact_time_verified=fact_time_verified,
            recorded_at_unix=normalized_recorded_at,
            source_id=_text("source_id", source_id),
            source_role=_text("source_role", source_role),
            source_scope=_text("source_scope", source_scope),
            verification_state=_text(
                "verification_state",
                verification_state,
            ).lower(),
            evidence_receipt_id=_optional_text(
                "evidence_receipt_id",
                evidence_receipt_id,
            ),
            proof_score_id=_optional_text("proof_score_id", proof_score_id),
            limitations=_text_tuple("limitations", tuple(limitations)),
            warnings=_text_tuple("warnings", tuple(warnings)),
            execution_authorized=execution_authorized,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_version": DISCOVERY_LEDGER_CONTRACT_VERSION,
            "chain": self.chain,
            "subject_kind": self.subject_kind,
            "subject_id": self.subject_id,
            "mint": self.mint,
            "identity_contract": self.identity_contract,
            "identity_verified": self.identity_verified,
            "observation_kind": self.observation_kind,
            "fact_time_unix": self.fact_time_unix,
            "fact_time_verified": self.fact_time_verified,
            "recorded_at_unix": self.recorded_at_unix,
            "source_id": self.source_id,
            "source_role": self.source_role,
            "source_scope": self.source_scope,
            "verification_state": self.verification_state,
            "evidence_receipt_id": self.evidence_receipt_id,
            "proof_score_id": self.proof_score_id,
            "limitations": list(self.limitations),
            "warnings": list(self.warnings),
            "execution_authorized": False,
        }

    @property
    def content_id(self) -> str:
        return _sha256_id("do", self.canonical_payload())

    def to_mapping(self) -> dict[str, object]:
        return {
            **self.canonical_payload(),
            "content_id": self.content_id,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiscoveryObservationV1":
        if value.get("contract_version") != DISCOVERY_LEDGER_CONTRACT_VERSION:
            raise DiscoveryLedgerContractError(
                "Discovery observation contract_version mismatch"
            )
        if value.get("execution_authorized") is not False:
            raise DiscoveryLedgerContractError(
                "Discovery observation must preserve execution_authorized=false"
            )
        observation = cls.create(
            chain=value.get("chain"),
            subject_kind=value.get("subject_kind"),
            subject_id=value.get("subject_id"),
            mint=value.get("mint"),
            identity_contract=value.get("identity_contract"),
            identity_verified=value.get("identity_verified"),
            observation_kind=value.get("observation_kind"),
            fact_time_unix=value.get("fact_time_unix"),
            fact_time_verified=value.get("fact_time_verified"),
            recorded_at_unix=value.get("recorded_at_unix"),
            source_id=value.get("source_id"),
            source_role=value.get("source_role"),
            source_scope=value.get("source_scope"),
            verification_state=value.get("verification_state"),
            evidence_receipt_id=value.get("evidence_receipt_id"),
            proof_score_id=value.get("proof_score_id"),
            limitations=value.get("limitations") or (),
            warnings=value.get("warnings") or (),
            execution_authorized=False,
        )
        supplied_id = _text("content_id", value.get("content_id"))
        if supplied_id != observation.content_id:
            raise DiscoveryLedgerContractError(
                "Discovery observation content_id does not match canonical payload"
            )
        return observation


@dataclass(frozen=True)
class DiscoveryLedgerV1:
    """Immutable reference ledger with deterministic append/replay behavior."""

    observations: Tuple[DiscoveryObservationV1, ...] = ()

    def append(self, observation: DiscoveryObservationV1) -> "DiscoveryLedgerV1":
        if not isinstance(observation, DiscoveryObservationV1):
            raise DiscoveryLedgerContractError(
                "Discovery Ledger accepts DiscoveryObservationV1 records only"
            )
        for existing in self.observations:
            if existing.content_id != observation.content_id:
                continue
            if existing.canonical_payload() != observation.canonical_payload():
                raise DiscoveryLedgerContractError(
                    "duplicate discovery content_id has conflicting payload"
                )
            return self
        return DiscoveryLedgerV1(self.observations + (observation,))

    def first_verified_observation(
        self,
        *,
        mint: str,
        observation_kind: str,
    ) -> Optional[DiscoveryObservationV1]:
        canonical_mint = _text("mint", mint)
        kind = _text("observation_kind", observation_kind)
        candidates = [
            observation
            for observation in self.observations
            if observation.chain == "x1"
            and observation.subject_kind == DISCOVERY_SUBJECT_KIND
            and observation.subject_id == canonical_mint
            and observation.observation_kind == kind
            and observation.verification_state == "verified"
            and observation.fact_time_verified is True
            and observation.fact_time_unix is not None
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (item.fact_time_unix, item.content_id),
        )

    def first_verified_observed_at(
        self,
        *,
        mint: str,
        observation_kind: str,
    ) -> Optional[int]:
        observation = self.first_verified_observation(
            mint=mint,
            observation_kind=observation_kind,
        )
        return (
            observation.fact_time_unix
            if observation is not None
            else None
        )

    def to_mapping(self) -> dict[str, object]:
        payload = {
            "contract_version": DISCOVERY_LEDGER_CONTRACT_VERSION,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
            "observations": [
                observation.to_mapping()
                for observation in self.observations
            ],
        }
        return {
            **payload,
            "state_hash": _sha256_id("dl", payload),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DiscoveryLedgerV1":
        if value.get("contract_version") != DISCOVERY_LEDGER_CONTRACT_VERSION:
            raise DiscoveryLedgerContractError(
                "Discovery ledger contract_version mismatch"
            )
        if value.get("read_only") is not True:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger must remain read-only"
            )
        if value.get("public_service_promoted") is not False:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger foundation is not public-service promoted"
            )
        if value.get("scout_reliance_promoted") is not False:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger foundation is not Scout-reliance promoted"
            )
        if value.get("execution_authorized") is not False:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger must preserve execution_authorized=false"
            )
        raw_observations = value.get("observations")
        if not isinstance(raw_observations, list):
            raise DiscoveryLedgerContractError(
                "Discovery Ledger observations must be a list"
            )
        ledger = cls()
        for raw in raw_observations:
            if not isinstance(raw, Mapping):
                raise DiscoveryLedgerContractError(
                    "Discovery Ledger observation entry must be an object"
                )
            ledger = ledger.append(DiscoveryObservationV1.from_mapping(raw))

        expected = ledger.to_mapping()["state_hash"]
        supplied = _text("state_hash", value.get("state_hash"))
        if supplied != expected:
            raise DiscoveryLedgerContractError(
                "Discovery Ledger state_hash does not match canonical state"
            )
        return ledger


def replay_discovery_observations(
    observations: Iterable[DiscoveryObservationV1],
) -> DiscoveryLedgerV1:
    ledger = DiscoveryLedgerV1()
    for observation in observations:
        ledger = ledger.append(observation)
    return ledger


__all__ = [
    "DISCOVERY_EXECUTION_AUTHORIZED",
    "DISCOVERY_IDENTITY_CONTRACT",
    "DISCOVERY_LEDGER_CONTRACT_VERSION",
    "DISCOVERY_PUBLIC_SERVICE_PROMOTED",
    "DISCOVERY_READ_ONLY",
    "DISCOVERY_SCOUT_RELIANCE_PROMOTED",
    "DISCOVERY_SUBJECT_KIND",
    "DiscoveryLedgerContractError",
    "DiscoveryLedgerV1",
    "DiscoveryObservationV1",
    "VERIFICATION_STATES",
    "replay_discovery_observations",
]
