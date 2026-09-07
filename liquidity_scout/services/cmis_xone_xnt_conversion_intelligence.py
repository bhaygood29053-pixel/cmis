"""Internal CMIS service seam for dedicated XONE/XNT conversion discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Optional

from liquidity_scout.providers.ethereum import (
    CONTRACT_VERSION as ETHEREUM_XONE_IDENTITY_CONTRACT,
    corroborate_xone_identity_proofs,
    verify_xone_identity,
)
from liquidity_scout.providers.xone_xnt import (
    SCRAPER_CONTRACT,
    XoneXntConversionScraper,
    extract_xone_xnt_claims,
    group_claims_for_review,
    source_catalog,
)


SERVICE = "xone_xnt_conversion_intelligence"
SERVICE_CONTRACT = "xone_xnt_conversion_intelligence/v1"
STATE = "internal_foundation"


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_only": True,
        "web_claim_verified": False,
        "ethereum_xone_identity_verified": False,
        "ethereum_event_verified": False,
        "x1_event_verified": False,
        "cross_chain_correlation_verified": False,
        "freshness_verified": False,
        "source_independence_verified": False,
        "cmis_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


class CMISXoneXntConversionIntelligenceService:
    """Dedicated XONE/XNT conversion discovery without public promotion."""

    service = SERVICE
    service_contract = SERVICE_CONTRACT

    def __init__(self, *, scraper: Optional[XoneXntConversionScraper] = None) -> None:
        self.scraper = scraper or XoneXntConversionScraper()

    def sources(self) -> dict[str, Any]:
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "state": STATE,
            "sources": source_catalog(),
            "read_only": True,
            "xone_xnt_only": True,
            **_truth_state(),
        }

    def scrape_url(
        self,
        source_id: str,
        url: str,
        *,
        max_claims: int = 100,
    ) -> dict[str, Any]:
        result = self.scraper.scrape_url(source_id, url, max_claims=max_claims)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "state": STATE,
            "result": result,
            "read_only": True,
            "xone_xnt_only": True,
            **_truth_state(),
        }

    def discover_sitemap_candidates(
        self,
        source_id: str,
        *,
        sitemap_url: Optional[str] = None,
        max_urls: int = 250,
    ) -> dict[str, Any]:
        result = self.scraper.discover_sitemap_candidates(
            source_id,
            sitemap_url=sitemap_url,
            max_urls=max_urls,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "state": STATE,
            "result": result,
            "read_only": True,
            "xone_xnt_only": True,
            **_truth_state(),
        }

    def scrape_sitemap_candidates(
        self,
        source_id: str,
        *,
        sitemap_url: Optional[str] = None,
        max_urls: int = 20,
        max_claims_per_url: int = 25,
    ) -> dict[str, Any]:
        result = self.scraper.scrape_sitemap_candidates(
            source_id,
            sitemap_url=sitemap_url,
            max_urls=max_urls,
            max_claims_per_url=max_claims_per_url,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "state": STATE,
            "result": result,
            "read_only": True,
            "xone_xnt_only": True,
            **_truth_state(),
        }

    def verify_ethereum_xone_identity(
        self,
        *,
        rpc_call: Any,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Verify only the exact Ethereum XONE contract identity."""

        proof = verify_xone_identity(
            rpc_call=rpc_call,
            source_url=source_url,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_identity_contract": ETHEREUM_XONE_IDENTITY_CONTRACT,
            "state": STATE,
            "ethereum_identity": proof,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
            },
        }

    def corroborate_ethereum_xone_identity(
        self,
        proofs: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Require matching exact-identity proofs from distinct RPC transports."""

        corroboration = corroborate_xone_identity_proofs(proofs)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_identity_contract": ETHEREUM_XONE_IDENTITY_CONTRACT,
            "state": STATE,
            "ethereum_identity": corroboration,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
            },
        }

    def normalize_documents(
        self,
        documents: Sequence[Mapping[str, Any]],
        *,
        observed_at: float,
        max_claims_per_document: int = 100,
    ) -> dict[str, Any]:
        """Normalize already-captured documents for deterministic testing/import."""

        if not documents:
            raise ValueError("documents must not be empty")
        claims: list[dict[str, Any]] = []
        for document in documents:
            source_id = str(document.get("source_id") or "").strip()
            url = str(document.get("url") or "").strip()
            text_value = document.get("text")
            if not source_id or not url or not isinstance(text_value, str):
                raise ValueError("each document requires source_id, url, and text")
            claims.extend(
                extract_xone_xnt_claims(
                    text_value,
                    source_id=source_id,
                    url=url,
                    observed_at=observed_at,
                    max_claims=max_claims_per_document,
                )
            )

        unique_claims: list[dict[str, Any]] = []
        seen: set[str] = set()
        for claim in claims:
            claim_id = str(claim["claim_id"])
            if claim_id in seen:
                continue
            seen.add(claim_id)
            unique_claims.append(claim)

        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "state": STATE,
            "candidate_claim_count": len(unique_claims),
            "claims": unique_claims,
            "claim_groups": group_claims_for_review(unique_claims),
            "read_only": True,
            "xone_xnt_only": True,
            **_truth_state(),
        }


__all__ = [
    "CMISXoneXntConversionIntelligenceService",
    "SERVICE",
    "SERVICE_CONTRACT",
    "STATE",
]
