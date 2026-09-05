"""Internal CMIS Web Discovery service seam.

This service composes source-specific discovery providers without promoting web
claims into verified CMIS facts. It is intentionally not added to the public
CMIS capability manifest by this foundation slice.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from liquidity_scout.providers.web_discovery import (
    CONTRACT as PROVIDER_CONTRACT,
    WebDiscoveryError,
    build_provider,
    provider_catalog,
    provider_ids,
)


SERVICE = "cmis_web_discovery"
SERVICE_CONTRACT = "cmis_web_discovery/v1"
STATE = "internal_foundation"


def _service_truth_state() -> dict[str, Any]:
    return {
        "discovery_only": True,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


class CMISWebDiscoveryService:
    """Bounded multi-source discovery composition beneath CMIS."""

    service = SERVICE
    service_contract = SERVICE_CONTRACT

    def sources(self) -> dict[str, Any]:
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "provider_contract": PROVIDER_CONTRACT,
            "state": STATE,
            "sources": provider_catalog(),
            "read_only": True,
            **_service_truth_state(),
        }

    def discover(
        self,
        source_id: str,
        *,
        url: Optional[str] = None,
        query: Optional[str] = None,
        max_pages: int = 1,
        max_depth: int = 0,
        provider_kwargs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = build_provider(
            source_id,
            provider_kwargs=provider_kwargs,
        )
        discovery = provider.crawl(
            url,
            query=query,
            max_pages=max_pages,
            max_depth=max_depth,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "provider_contract": PROVIDER_CONTRACT,
            "state": STATE,
            "source_id": provider.source.source_id,
            "discovery": discovery,
            "read_only": True,
            **_service_truth_state(),
        }

    def discover_many(
        self,
        *,
        targets: Mapping[str, Optional[str]] | None = None,
        query: Optional[str] = None,
        max_pages_per_source: int = 1,
        max_depth: int = 0,
        provider_kwargs_by_source: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected = dict(targets) if targets is not None else {
            source_id: None for source_id in provider_ids()
        }
        if not selected:
            raise ValueError("targets must not be empty")

        supported = set(provider_ids())
        unknown = sorted(set(selected) - supported)
        if unknown:
            raise ValueError(
                f"unsupported CMIS Web Discovery source(s): {unknown}"
            )

        kwargs_by_source = dict(provider_kwargs_by_source or {})
        results: list[dict[str, Any]] = []

        for source_id, url in selected.items():
            provider_kwargs = kwargs_by_source.get(source_id)
            try:
                result = self.discover(
                    source_id,
                    url=url,
                    query=query,
                    max_pages=max_pages_per_source,
                    max_depth=max_depth,
                    provider_kwargs=provider_kwargs,
                )
            except WebDiscoveryError as exc:
                result = {
                    "service": SERVICE,
                    "service_contract": SERVICE_CONTRACT,
                    "provider_contract": PROVIDER_CONTRACT,
                    "state": STATE,
                    "source_id": source_id,
                    "discovery": None,
                    "availability": {
                        "status": "UNAVAILABLE",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    "read_only": True,
                    **_service_truth_state(),
                }
            else:
                result["availability"] = {
                    "status": "AVAILABLE",
                    "error_type": None,
                    "error": None,
                }
            results.append(result)

        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "provider_contract": PROVIDER_CONTRACT,
            "state": STATE,
            "requested_source_count": len(selected),
            "results": results,
            "read_only": True,
            **_service_truth_state(),
        }


__all__ = [
    "CMISWebDiscoveryService",
    "SERVICE",
    "SERVICE_CONTRACT",
    "STATE",
]
