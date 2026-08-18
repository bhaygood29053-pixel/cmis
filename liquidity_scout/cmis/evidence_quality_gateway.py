"""Runtime post-processing for CMIS evidence receipts and proof scores.

This mixin wraps completed CMIS envelopes after the underlying deterministic
service has made its decision.  It cannot override service data, risk, status,
provider facts, or execution policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.proof_score import build_proof_score


class EvidenceQualityMixin:
    """Attach read-only evidence quality metadata to runtime service envelopes."""

    def dispatch(self, request: Any) -> dict[str, Any]:
        response = super().dispatch(request)
        if not isinstance(response, Mapping):
            return response
        if not all(response.get(field) is not None for field in ("service", "chain", "status")):
            return dict(response)

        result = deepcopy(dict(response))
        receipt = build_evidence_receipt(result)
        result["evidence_receipt"] = receipt
        result["proof_score"] = build_proof_score(receipt)
        return result


__all__ = ["EvidenceQualityMixin"]
