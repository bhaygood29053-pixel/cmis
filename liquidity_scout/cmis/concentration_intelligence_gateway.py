"""Canonical runtime integration for the first promoted Phase 12 intelligence service.

This mixin exposes only the accepted X1 ``concentration_change_intelligence``
contract. Caller-supplied proof objects remain rejected by the service contract;
the trusted evidence resolver is always owned by the runtime.

The mixin sits below ``EvidenceQualityMixin`` in the runtime MRO so the completed
service envelope still receives the standard top-level Evidence Receipt and
Proof Score post-processing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.verified_intelligence_service import (
    dispatch_verified_intelligence_request,
)
from liquidity_scout.services.cmis_verified_intelligence import SERVICE


class ConcentrationIntelligenceGatewayMixin:
    """Promote exactly one CMIS-owned read-only intelligence contract on X1."""

    def store_intelligence_evidence(self, bundle: Mapping[str, Any], *, recorded_at=None):
        """Persist one trusted Phase 11 bundle for later Scout lookup.

        This is an internal runtime method, not an HTTP service. The ledger owns
        deterministic revalidation and X1/conclusion-type restrictions.
        """
        ledger = getattr(self, "intelligence_evidence_ledger", None)
        store = getattr(ledger, "store", None)
        if not callable(store):
            raise RuntimeError("CMIS intelligence-evidence ledger is unavailable")
        return store(bundle, recorded_at=recorded_at)

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = str(request.get("service") or "").strip().lower()
            if service == SERVICE:
                chain = str(request.get("chain") or "").strip().lower()
                if not chain:
                    return self._gateway_error(
                        SERVICE,
                        "unknown",
                        "chain_required",
                        "chain is required.",
                    )
                if chain not in {"x1", "solana"}:
                    return self._gateway_error(
                        SERVICE,
                        chain,
                        "unsupported_chain",
                        "Unsupported chain: " + chain,
                    )
                resolver = getattr(self, "intelligence_evidence_resolver", None)
                return dispatch_verified_intelligence_request(
                    request,
                    evidence_resolver=resolver,
                    promotion_authorized=True,
                )
        return super().dispatch(request)


__all__ = ["ConcentrationIntelligenceGatewayMixin"]
