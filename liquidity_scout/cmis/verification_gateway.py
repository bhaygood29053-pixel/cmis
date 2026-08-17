"""External CMIS gateway extension for persisted verification evidence.

The accepted base gateway owns market/provider-backed services. This extension
adds only exact read-only lookup of already-persisted CMIS verification evidence.
It never accepts provider payloads, verifier results, asset-name inference, or a
database path from the caller. The evidence ledger is injected by the CMIS
runtime.
"""

from collections.abc import Mapping
from typing import Any, Dict

from liquidity_scout.services.cmis_verification_evidence_lookup import (
    lookup_verification_evidence,
)

from .gateway import (
    CMISGateway as BaseCMISGateway,
    KNOWN_CHAINS,
    SUPPORTED_CHAINS,
    SUPPORTED_SERVICES as BASE_SUPPORTED_SERVICES,
)


SERVICE = "verification_evidence"
SUPPORTED_SERVICES = (*BASE_SUPPORTED_SERVICES, SERVICE)
_ALLOWED_REQUEST_KEYS = frozenset({"service", "chain", "params"})
_ALLOWED_PARAMS = frozenset({"evidence_id", "fact_type", "subject_id"})


class CMISGateway(BaseCMISGateway):
    """CMIS external gateway with exact persisted-evidence lookup enabled."""

    def __init__(self, *, verification_evidence_ledger: Any = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.verification_evidence_ledger = verification_evidence_ledger

    def _verification_evidence(
        self,
        *,
        chain: str,
        params: Mapping[str, Any],
    ) -> Dict[str, Any]:
        unexpected = sorted(str(key) for key in params if key not in _ALLOWED_PARAMS)
        if unexpected:
            return self._gateway_error(
                SERVICE,
                chain,
                "verification_evidence_params_not_allowed",
                (
                    "verification_evidence params may contain only evidence_id or "
                    "the exact fact_type + subject_id selector."
                ),
            )

        return lookup_verification_evidence(
            self.verification_evidence_ledger,
            chain=chain,
            evidence_id=params.get("evidence_id"),
            fact_type=params.get("fact_type"),
            subject_id=params.get("subject_id"),
        )

    def dispatch(self, request: Any) -> Dict[str, Any]:
        """Dispatch verification evidence narrowly; delegate all other services."""
        if not isinstance(request, Mapping):
            return super().dispatch(request)

        service = (self._text(request.get("service")) or "").lower()
        if service != SERVICE:
            return super().dispatch(request)

        chain = (self._text(request.get("chain")) or "").lower()
        if not chain:
            return self._gateway_error(
                SERVICE,
                "unknown",
                "chain_required",
                "chain is required.",
            )
        if chain not in KNOWN_CHAINS:
            return self._gateway_error(
                SERVICE,
                chain,
                "unsupported_chain",
                "Unsupported chain: " + chain,
            )
        if chain not in SUPPORTED_CHAINS:
            return self._chain_unavailable(SERVICE, chain)

        unexpected_request_keys = sorted(
            str(key) for key in request if key not in _ALLOWED_REQUEST_KEYS
        )
        if unexpected_request_keys:
            return self._gateway_error(
                SERVICE,
                chain,
                "verification_evidence_request_fields_not_allowed",
                (
                    "verification_evidence accepts only service, chain, and params; "
                    "asset/provider/verifier payload fields are not accepted."
                ),
            )

        params = request.get("params", {})
        if not isinstance(params, Mapping):
            return self._gateway_error(
                SERVICE,
                chain,
                "invalid_params",
                "params must be a JSON object/mapping.",
            )

        return self._verification_evidence(chain=chain, params=params)


__all__ = ["CMISGateway", "SERVICE", "SUPPORTED_SERVICES"]
