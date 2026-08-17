"""Production CMIS runtime composition.

The HTTP runtime needs the accepted risk/trade extensions, persisted
``verification_evidence`` lookup, and narrowly eligible Solana identity,
tokenomics, market-evidence, and risk layers on one cooperative gateway class.
These layers compose without duplicating their dispatch logic.

Verification evidence persistence is an internal runtime dependency. Callers
can select evidence only by the public service contract; they cannot choose a
SQLite path or inject a ledger through an HTTP request.
"""

from __future__ import annotations

import os
from typing import Any

from liquidity_scout.cmis.evidence_ledger import VerificationEvidenceLedger
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.cmis.solana_market_gateway import SolanaMarketReportMixin
from liquidity_scout.cmis.solana_risk_gateway import SolanaRiskCheckMixin
from liquidity_scout.cmis.solana_tokenomics_gateway import SolanaTokenomicsMixin
from liquidity_scout.cmis.trade_gateway import (
    SUPPORTED_SERVICES as TRADE_SUPPORTED_SERVICES,
    TradeAwareCMISGateway,
)
from liquidity_scout.cmis.verification_gateway import (
    CMISGateway as VerificationCMISGateway,
    SERVICE as VERIFICATION_EVIDENCE_SERVICE,
)


DEFAULT_VERIFICATION_EVIDENCE_DB = os.path.join(
    os.path.expanduser("~"),
    ".liquidity_scout",
    "verification_evidence.db",
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
    SolanaRiskCheckMixin,
    SolanaMarketReportMixin,
    SolanaTokenomicsMixin,
    SolanaAssetLookupMixin,
    TradeAwareCMISGateway,
    VerificationCMISGateway,
):
    """HTTP/runtime gateway with X1 services and gated Solana read-only facts."""

    def __init__(
        self,
        *,
        verification_evidence_ledger: Any = None,
        verification_evidence_db_path: str | None = None,
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

        super().__init__(verification_evidence_ledger=ledger, **kwargs)


__all__ = [
    "DEFAULT_VERIFICATION_EVIDENCE_DB",
    "RuntimeCMISGateway",
    "SUPPORTED_SERVICES",
    "VERIFICATION_EVIDENCE_SERVICE",
]
