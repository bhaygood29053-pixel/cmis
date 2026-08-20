"""Production CMIS runtime composition.

The HTTP runtime needs the accepted risk/trade extensions, persisted
``verification_evidence`` lookup, narrowly eligible Solana identity/tokenomics/
market/history/risk layers, deterministic XDEX route evidence, the CMIS-owned
concentration-change intelligence evidence ledger, and evidence-quality metadata
on one cooperative gateway class.

Verification evidence persistence, intelligence evidence persistence, and the
XDEX exact-route resolver are internal runtime dependencies. Callers can select
evidence only by the public service contract; they cannot inject a ledger,
trusted route evidence, resolver, provider payload, or evidence bundle through
an HTTP request.

Solana service code remains provider-injected, but the production runtime can
construct accepted read-only providers from deployment environment
configuration. This path is disabled by default and cannot be selected or
modified through an HTTP request.

Evidence receipts/proof scores are post-processing only. They summarize proof
already present in the service envelope and cannot rewrite provider facts,
risk, service status, or execution policy.
"""

from __future__ import annotations

import os
from typing import Any

from liquidity_scout.cmis.evidence_ledger import VerificationEvidenceLedger
from liquidity_scout.cmis.evidence_quality_gateway import EvidenceQualityMixin
from liquidity_scout.cmis.intelligence_evidence_ledger import IntelligenceEvidenceLedger
from liquidity_scout.cmis.pre_trade_policy_gateway import PreTradePolicyMixin
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.cmis.solana_historical_gateway import SolanaHistoricalCompareMixin
from liquidity_scout.cmis.solana_market_gateway import SolanaMarketReportMixin
from liquidity_scout.cmis.solana_risk_gateway import SolanaRiskCheckMixin
from liquidity_scout.cmis.solana_runtime_config import (
    build_solana_runtime_dependencies,
)
from liquidity_scout.cmis.solana_tokenomics_gateway import SolanaTokenomicsMixin
from liquidity_scout.cmis.trade_gateway import (
    SUPPORTED_SERVICES as TRADE_SUPPORTED_SERVICES,
    TradeAwareCMISGateway,
)
from liquidity_scout.cmis.verification_gateway import (
    CMISGateway as VerificationCMISGateway,
    SERVICE as VERIFICATION_EVIDENCE_SERVICE,
)
from liquidity_scout.cmis.verified_xdex_program_scope_gateway import (
    VerifiedXDEXProgramScopeMixin,
)
from liquidity_scout.cmis.xdex_route_resolver import resolve_xdex_route_evidence


DEFAULT_VERIFICATION_EVIDENCE_DB = os.path.join(
    os.path.expanduser("~"),
    ".liquidity_scout",
    "verification_evidence.db",
)
DEFAULT_INTELLIGENCE_EVIDENCE_DB = os.path.join(
    os.path.expanduser("~"),
    ".liquidity_scout",
    "intelligence_evidence.db",
)
SUPPORTED_SERVICES = (
    *TRADE_SUPPORTED_SERVICES,
    *(
        ()
        if VERIFICATION_EVIDENCE_SERVICE in TRADE_SUPPORTED_SERVICES
        else (VERIFICATION_EVIDENCE_SERVICE,)
    ),
)


class RuntimeCMISGateway(
    EvidenceQualityMixin,
    PreTradePolicyMixin,
    SolanaHistoricalCompareMixin,
    SolanaRiskCheckMixin,
    SolanaMarketReportMixin,
    SolanaTokenomicsMixin,
    SolanaAssetLookupMixin,
    VerifiedXDEXProgramScopeMixin,
    TradeAwareCMISGateway,
    VerificationCMISGateway,
):
    """HTTP/runtime gateway with read-only evidence-quality metadata."""

    def __init__(
        self,
        *,
        verification_evidence_ledger: Any = None,
        verification_evidence_db_path: str | None = None,
        intelligence_evidence_ledger: Any = None,
        intelligence_evidence_db_path: str | None = None,
        solana_runtime_env: Any = None,
        xdex_route_resolver: Any = None,
        **kwargs: Any,
    ):
        ledger = verification_evidence_ledger
        if ledger is None:
            configured_path = (
                verification_evidence_db_path
                if verification_evidence_db_path is not None
                else os.getenv(
                    "CMIS_VERIFICATION_EVIDENCE_DB",
                    DEFAULT_VERIFICATION_EVIDENCE_DB,
                )
            )
            path = str(configured_path or "").strip()
            if not path:
                raise ValueError(
                    "CMIS verification-evidence database path must not be empty."
                )
            if path != ":memory:":
                parent = os.path.dirname(os.path.abspath(path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
            ledger = VerificationEvidenceLedger(path)

        intelligence_ledger = intelligence_evidence_ledger
        if intelligence_ledger is None:
            configured_intelligence_path = (
                intelligence_evidence_db_path
                if intelligence_evidence_db_path is not None
                else os.getenv(
                    "CMIS_INTELLIGENCE_EVIDENCE_DB",
                    DEFAULT_INTELLIGENCE_EVIDENCE_DB,
                )
            )
            intelligence_path = str(configured_intelligence_path or "").strip()
            if not intelligence_path:
                raise ValueError(
                    "CMIS intelligence-evidence database path must not be empty."
                )
            if intelligence_path != ":memory:":
                parent = os.path.dirname(os.path.abspath(intelligence_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
            intelligence_ledger = IntelligenceEvidenceLedger(intelligence_path)

        intelligence_resolver = getattr(intelligence_ledger, "get", None)
        if not callable(intelligence_resolver):
            raise ValueError(
                "intelligence_evidence_ledger must provide a callable get method"
            )
        self.intelligence_evidence_ledger = intelligence_ledger
        # The production runtime owns this trust root. Any stray constructor
        # kwarg is overwritten rather than allowed to replace the CMIS-owned
        # resolver with a caller-controlled implementation.
        kwargs["intelligence_evidence_resolver"] = intelligence_resolver

        solana_dependencies, solana_status = build_solana_runtime_dependencies(
            solana_runtime_env
        )
        # Explicit constructor dependencies remain authoritative. This keeps
        # deterministic tests and specialized deployments compatible while the
        # normal HTTP runtime gains environment-owned automatic composition.
        for name, dependency in solana_dependencies.items():
            kwargs.setdefault(name, dependency)
        self.solana_runtime_configuration = solana_status

        self.xdex_route_resolver = (
            resolve_xdex_route_evidence
            if xdex_route_resolver is None
            else xdex_route_resolver
        )
        if not callable(self.xdex_route_resolver):
            raise ValueError("xdex_route_resolver must be callable when supplied")

        super().__init__(verification_evidence_ledger=ledger, **kwargs)


__all__ = [
    "DEFAULT_INTELLIGENCE_EVIDENCE_DB",
    "DEFAULT_VERIFICATION_EVIDENCE_DB",
    "RuntimeCMISGateway",
    "SUPPORTED_SERVICES",
    "VERIFICATION_EVIDENCE_SERVICE",
]
