"""Internal CMIS service seam for dedicated XONE/XNT conversion discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Optional

from liquidity_scout.providers.ethereum import (
    CONTRACT_VERSION as ETHEREUM_XONE_IDENTITY_CONTRACT,
    XONE_EVENT_OBSERVER_CONTRACT_VERSION,
    XONE_MIGRATION_SINK_SEMANTICS_CONTRACT_VERSION,
    XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
    classify_migration_candidate,
    corroborate_xone_burn_surface,
    corroborate_xone_event_observations,
    corroborate_xone_identity_proofs,
    observe_xone_transfer_events,
    corroborate_xone_registry_proofs,
    discover_official_snapshot_candidates,
    extract_xone_snapshot_claims,
    fetch_and_verify_xone_registry,
    promote_official_snapshot,
    verify_burn_redeemer_candidate,
    verify_xone_burn_surface,
    verify_xone_identity,
)
from liquidity_scout.providers.xone_xnt import (
    CANDIDATE_DISCOVERY_CONTRACT_VERSION,
    SCRAPER_CONTRACT,
    X1_XNT_DISTRIBUTION_MECHANISM_CONTRACT_VERSION,
    XONE_XNT_X1_BINDING_CONTRACT_VERSION,
    XONE_XNT_MOONPARTY_SOURCE_SEMANTICS_CONTRACT_VERSION,
    MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION,
    XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
    XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION,
    XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION,
    annotate_retrieved_asset_capture,
    build_asset_graph_edges,
    extract_archived_asset_references,
    extract_asset_provenance_candidates,
    summarize_archived_asset_graph,
    discover_repository_path_candidates,
    extract_archival_provenance_candidates,
    summarize_archival_recovery,
    extract_provenance_candidates,
    rank_provenance_candidates,
    discover_x1_binding_candidates,
    discover_xnt_distribution_candidates,
    extract_xnt_mechanism_claims,
    discover_conversion_candidates,
    XoneXntConversionScraper,
    extract_xone_xnt_claims,
    group_claims_for_review,
    qualify_conversion_candidate,
    qualify_x1_binding_candidate,
    qualify_xnt_distribution_candidate,
    source_catalog,
    verify_moonparty_source_semantics,
    discover_moonparty_deployment_candidates,
    verify_moonparty_deployment_candidate,
    corroborate_moonparty_deployment,
)


SERVICE = "xone_xnt_conversion_intelligence"
SERVICE_CONTRACT = "xone_xnt_conversion_intelligence/v1"
STATE = "internal_foundation"


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_only": True,
        "web_claim_verified": False,
        "ethereum_xone_identity_verified": False,
        "ethereum_event_window_verified": False,
        "ethereum_event_verified": False,
        "xone_burn_verified": False,
        "xone_burn_accounting_surface_verified": False,
        "xone_snapshot_source_discovery_verified": False,
        "xone_snapshot_provenance_expansion_verified": False,
        "xone_snapshot_archival_source_recovery_verified": False,
        "xone_snapshot_archived_asset_graph_resolution_verified": False,
        "archived_asset_graph_traversal_verified": False,
        "archived_asset_reference_discovered": False,
        "archived_asset_capture_retrieved": False,
        "archived_asset_semantic_candidate_discovered": False,
        "archival_capture_discovered": False,
        "archival_capture_retrieved": False,
        "stable_primary_url_recovered": False,
        "direct_primary_archival_source_recovered": False,
        "provenance_candidate_discovered": False,
        "direct_primary_source_recovered": False,
        "snapshot_artifact_candidate_discovered": False,
        "authoritative_exact_snapshot_block_discovered": False,
        "reconstructed_xone_registry_verified": False,
        "official_xone_snapshot_verified": False,
        "official_registry_artifact_verified": False,
        "xone_snapshot_eligibility_verified": False,
        "xone_snapshot_xnt_allocation_binding_verified": False,
        "burn_redeemer_interface_verified": False,
        "conversion_candidate_discovery_verified": False,
        "x1_xnt_mechanism_discovery_verified": False,
        "x1_xnt_candidate_account_state_verified": False,
        "x1_binding_candidate_discovery_verified": False,
        "x1_binding_candidate_history_verified": False,
        "x1_binding_identified": False,
        "moonparty_authoritative_source_semantics_verified": False,
        "moonparty_deployment_verified": False,
        "moonparty_deployment_chain_verified": False,
        "moonparty_runtime_compatible": False,
        "moonparty_xone_binding_verified": False,
        "xone_to_xnt_credit_design_link_verified": False,
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_distribution_mechanism_identified": False,
        "migration_sink_identified": False,
        "lock_or_migration_verified": False,
        "xone_xnt_conversion_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
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

    def observe_ethereum_xone_events(
        self,
        *,
        rpc_call: Any,
        from_block: int | str,
        to_block: int | str,
        source_url: str | None = None,
        max_blocks: int = 5000,
        max_events: int = 2000,
        enrich_recipient_code: bool = False,
    ) -> dict[str, Any]:
        """Verify exact XONE identity, then observe one bounded Transfer-log window."""

        identity = verify_xone_identity(rpc_call=rpc_call, source_url=source_url)
        observation = observe_xone_transfer_events(
            rpc_call=rpc_call,
            from_block=from_block,
            to_block=to_block,
            source_url=source_url,
            max_blocks=max_blocks,
            max_events=max_events,
            enrich_recipient_code=enrich_recipient_code,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_identity_contract": ETHEREUM_XONE_IDENTITY_CONTRACT,
            "ethereum_event_observer_contract": XONE_EVENT_OBSERVER_CONTRACT_VERSION,
            "state": STATE,
            "ethereum_identity": identity,
            "ethereum_event_observation": observation,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
                "ethereum_event_window_verified": True,
                "ethereum_event_verified": observation["ethereum_event_verified"],
                "xone_burn_verified": observation["xone_burn_verified"],
            },
        }

    def corroborate_ethereum_xone_events(
        self,
        observations: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Corroborate one exact bounded XONE event window across RPC transports."""

        corroboration = corroborate_xone_event_observations(observations)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_identity_contract": ETHEREUM_XONE_IDENTITY_CONTRACT,
            "ethereum_event_observer_contract": XONE_EVENT_OBSERVER_CONTRACT_VERSION,
            "state": STATE,
            "ethereum_event_observation": corroboration,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
                "ethereum_event_window_verified": True,
                "ethereum_event_verified": corroboration["ethereum_event_verified"],
                "xone_burn_verified": corroboration["xone_burn_verified"],
            },
        }

    def verify_ethereum_xone_burn_surface(
        self,
        *,
        rpc_call: Any,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Verify exact XONE identity and its readable burn-accounting surface."""

        identity = verify_xone_identity(rpc_call=rpc_call, source_url=source_url)
        burn_surface = verify_xone_burn_surface(
            rpc_call=rpc_call,
            source_url=source_url,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_identity_contract": ETHEREUM_XONE_IDENTITY_CONTRACT,
            "ethereum_migration_sink_semantics_contract":
                XONE_MIGRATION_SINK_SEMANTICS_CONTRACT_VERSION,
            "state": STATE,
            "ethereum_identity": identity,
            "ethereum_burn_surface": burn_surface,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
                "xone_burn_accounting_surface_verified": True,
            },
        }

    def verify_ethereum_xone_redeemer_candidate(
        self,
        candidate_address: str,
        *,
        rpc_call: Any,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Verify technical IBurnRedeemable compatibility without migration promotion."""

        proof = verify_burn_redeemer_candidate(
            candidate_address,
            rpc_call=rpc_call,
            source_url=source_url,
        )
        classification = classify_migration_candidate(
            candidate_address=candidate_address,
            burn_redeemer_proof=proof,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_migration_sink_semantics_contract":
                XONE_MIGRATION_SINK_SEMANTICS_CONTRACT_VERSION,
            "state": STATE,
            "redeemer_candidate": proof,
            "migration_classification": classification,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
                "burn_redeemer_interface_verified":
                    proof["burn_redeemer_interface_verified"],
            },
        }

    def corroborate_ethereum_xone_burn_surface(
        self,
        proofs: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Require matching burn-accounting state across distinct RPC transports."""

        corroboration = corroborate_xone_burn_surface(proofs)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_migration_sink_semantics_contract":
                XONE_MIGRATION_SINK_SEMANTICS_CONTRACT_VERSION,
            "state": STATE,
            "ethereum_burn_surface": corroboration,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
                "xone_burn_accounting_surface_verified": True,
            },
        }

    def resolve_xone_snapshot_archived_asset_graph(
        self,
        root_captures: Sequence[Mapping[str, Any]],
        asset_documents: Sequence[Mapping[str, Any]],
        *,
        observed_at: float,
        max_references_per_document: int = 100,
        max_ranked_candidates: int = 100,
    ) -> dict[str, Any]:
        """Resolve bounded archived application assets without snapshot promotion."""

        if not root_captures:
            raise ValueError("root_captures must not be empty")

        edges: list[dict[str, Any]] = []
        asset_captures: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []

        roots_by_id = {
            str(row.get("capture_id") or ""): dict(row)
            for row in root_captures
            if isinstance(row, Mapping) and row.get("capture_id")
        }

        for document in asset_documents:
            if not isinstance(document, Mapping):
                raise ValueError("each asset document must be a mapping")
            parent_id = str(document.get("parent_capture_id") or "").strip()
            parent = roots_by_id.get(parent_id)
            if parent is None:
                # A nested asset may carry its complete parent capture metadata.
                parent_value = document.get("parent_capture")
                if isinstance(parent_value, Mapping):
                    parent = dict(parent_value)
            if parent is None:
                raise ValueError("asset document requires a known parent capture")

            text_value = document.get("text")
            if not isinstance(text_value, str):
                raise ValueError("asset document requires text")
            depth = int(document.get("depth") or 1)
            references = extract_archived_asset_references(
                text_value,
                parent_original_url=str(parent.get("original") or ""),
                content_type=str(document.get("content_type") or ""),
                max_references=max_references_per_document,
            )
            edges.extend(build_asset_graph_edges(
                parent,
                references,
                depth=depth,
            ))

            capture = document.get("asset_capture")
            if isinstance(capture, Mapping):
                annotated = annotate_retrieved_asset_capture(
                    capture,
                    root_capture_id=str(
                        document.get("root_capture_id")
                        or parent.get("root_capture_id")
                        or parent.get("capture_id")
                        or ""
                    ),
                    parent_capture_id=str(parent.get("capture_id") or ""),
                    depth=depth,
                    retrieved_bytes=int(document.get("retrieved_bytes") or 0),
                    retrieved_content_type=str(
                        document.get("content_type") or ""
                    ),
                    content_sha256=str(
                        document.get("content_sha256") or ""
                    ),
                )
                asset_captures.append(annotated)
                candidates.extend(extract_asset_provenance_candidates(
                    text_value,
                    asset_capture=annotated,
                    observed_at=observed_at,
                    max_candidates=50,
                ))

        summary = summarize_archived_asset_graph(
            list(roots_by_id.values()),
            edges,
            asset_captures,
            candidates,
            max_candidates=max_ranked_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "snapshot_archived_asset_graph_contract":
                XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION,
            "state": STATE,
            "archived_asset_graph": summary,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "xone_snapshot_archived_asset_graph_resolution_verified": True,
                "archived_asset_graph_traversal_verified":
                    summary["asset_graph_traversal_verified"],
                "archived_asset_reference_discovered":
                    summary["asset_edge_count"] > 0,
                "archived_asset_capture_retrieved":
                    summary["asset_capture_retrieved_count"] > 0,
                "archived_asset_semantic_candidate_discovered":
                    summary["asset_semantic_candidate_count"] > 0,
                "stable_primary_url_recovered":
                    summary["stable_primary_social_url_count"] > 0,
                "snapshot_artifact_candidate_discovered":
                    summary["provenance"][
                        "snapshot_artifact_candidate_count"
                    ] > 0,
                "authoritative_exact_snapshot_block_discovered":
                    summary[
                        "authoritative_exact_snapshot_block_discovered"
                    ],
            },
        }

    def recover_xone_snapshot_archival_sources(
        self,
        captures: Sequence[Mapping[str, Any]],
        *,
        observed_at: float,
        stable_primary_urls: Sequence[Mapping[str, Any]] = (),
        max_candidates_per_capture: int = 50,
        max_ranked_candidates: int = 100,
    ) -> dict[str, Any]:
        """Extract bounded snapshot provenance from validated archival captures."""

        if not captures:
            raise ValueError("captures must not be empty")

        candidates: list[dict[str, Any]] = []
        retrieved_rows: list[dict[str, Any]] = []
        for capture in captures:
            if not isinstance(capture, Mapping):
                raise ValueError("each capture must be a mapping")
            text_value = capture.get("text")
            if not isinstance(text_value, str):
                raise ValueError("each capture requires retrieved text")
            metadata = dict(capture)
            metadata["archival_capture_retrieved"] = True
            retrieved_rows.append(metadata)
            candidates.extend(
                extract_archival_provenance_candidates(
                    text_value,
                    capture=metadata,
                    observed_at=observed_at,
                    max_candidates=max_candidates_per_capture,
                )
            )

        recovery = summarize_archival_recovery(
            retrieved_rows,
            candidates,
            stable_primary_urls=stable_primary_urls,
            max_candidates=max_ranked_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "snapshot_archival_recovery_contract":
                XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION,
            "state": STATE,
            "archival_recovery": recovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "xone_snapshot_archival_source_recovery_verified": True,
                "archival_capture_discovered":
                    recovery["archival_capture_count"] > 0,
                "archival_capture_retrieved":
                    recovery["archival_capture_retrieved_count"] > 0,
                "stable_primary_url_recovered":
                    recovery["stable_primary_url_count"] > 0,
                "direct_primary_archival_source_recovered":
                    recovery[
                        "direct_primary_archival_source_candidate_count"
                    ] > 0,
                "snapshot_artifact_candidate_discovered":
                    recovery["provenance"][
                        "snapshot_artifact_candidate_count"
                    ] > 0,
                "authoritative_exact_snapshot_block_discovered":
                    recovery[
                        "authoritative_exact_snapshot_block_discovered"
                    ],
            },
        }

    def discover_xone_xnt_conversion_candidates(
        self,
        claims: Sequence[Mapping[str, Any]],
        *,
        max_candidates: int = 50,
    ) -> dict[str, Any]:
        """Create exact-address review candidates from bounded XONE/XNT claims."""

        discovery = discover_conversion_candidates(
            claims,
            max_candidates=max_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "candidate_discovery_contract":
                CANDIDATE_DISCOVERY_CONTRACT_VERSION,
            "state": STATE,
            "candidate_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "conversion_candidate_discovery_verified": True,
            },
        }

    def qualify_xone_xnt_conversion_candidate(
        self,
        candidate: Mapping[str, Any],
        *,
        rpc_call: Any,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Qualify one discovered Ethereum address without migration promotion."""

        qualification = qualify_conversion_candidate(
            candidate,
            rpc_call=rpc_call,
            source_url=source_url,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "candidate_discovery_contract":
                CANDIDATE_DISCOVERY_CONTRACT_VERSION,
            "state": STATE,
            "candidate_qualification": qualification,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "conversion_candidate_discovery_verified": True,
                "burn_redeemer_interface_verified":
                    qualification.get("burn_redeemer_interface_verified") is True,
            },
        }

    def discover_x1_xnt_distribution_mechanism(
        self,
        documents: Sequence[Mapping[str, Any]],
        *,
        observed_at: float,
        max_claims_per_document: int = 100,
        max_candidates: int = 50,
    ) -> dict[str, Any]:
        """Extract XNT-side mechanism rules and exact X1 pubkey candidates."""

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
                extract_xnt_mechanism_claims(
                    text_value,
                    source_id=source_id,
                    url=url,
                    observed_at=observed_at,
                    max_claims=max_claims_per_document,
                )
            )

        discovery = discover_xnt_distribution_candidates(
            claims,
            max_candidates=max_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "x1_xnt_distribution_mechanism_contract":
                X1_XNT_DISTRIBUTION_MECHANISM_CONTRACT_VERSION,
            "state": STATE,
            "xnt_mechanism_claim_count": len(claims),
            "xnt_mechanism_claims": claims,
            "xnt_mechanism_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "x1_xnt_mechanism_discovery_verified": True,
            },
        }

    def qualify_x1_xnt_distribution_candidate(
        self,
        candidate: Mapping[str, Any],
        *,
        rpc_call: Any,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Qualify one exact X1 candidate account without semantic promotion."""

        qualification = qualify_xnt_distribution_candidate(
            candidate,
            rpc_call=rpc_call,
            source_url=source_url,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "x1_xnt_distribution_mechanism_contract":
                X1_XNT_DISTRIBUTION_MECHANISM_CONTRACT_VERSION,
            "state": STATE,
            "xnt_candidate_qualification": qualification,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "x1_xnt_mechanism_discovery_verified": True,
                "x1_xnt_candidate_account_state_verified":
                    qualification.get("account_state_verified") is True,
            },
        }

    def discover_xone_xnt_x1_binding_candidates(
        self,
        claims: Sequence[Mapping[str, Any]],
        *,
        max_candidates: int = 50,
    ) -> dict[str, Any]:
        """Discover exact X1 pubkeys inside bounded explicit XONE/XNT claims."""

        discovery = discover_x1_binding_candidates(
            claims,
            max_candidates=max_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "x1_binding_discovery_contract":
                XONE_XNT_X1_BINDING_CONTRACT_VERSION,
            "state": STATE,
            "x1_binding_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "x1_binding_candidate_discovery_verified": True,
            },
        }

    def qualify_xone_xnt_x1_binding_candidate(
        self,
        candidate: Mapping[str, Any],
        *,
        rpc_call: Any,
        source_url: str | None = None,
        history_limit: int = 25,
        transaction_limit: int = 10,
    ) -> dict[str, Any]:
        """Qualify exact X1 account/history evidence without role promotion."""

        qualification = qualify_x1_binding_candidate(
            candidate,
            rpc_call=rpc_call,
            source_url=source_url,
            history_limit=history_limit,
            transaction_limit=transaction_limit,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "x1_binding_discovery_contract":
                XONE_XNT_X1_BINDING_CONTRACT_VERSION,
            "state": STATE,
            "x1_binding_qualification": qualification,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "x1_binding_candidate_discovery_verified": True,
                "x1_binding_candidate_history_verified":
                    qualification.get("bounded_history_verified") is True,
            },
        }

    def verify_xone_xnt_moonparty_source_semantics(
        self,
        documents: Mapping[str, str],
        *,
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Verify pinned FairCrypto MoonParty/XONE source semantics only."""

        proof = verify_moonparty_source_semantics(
            documents,
            provenance=provenance,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "moonparty_source_semantics_contract":
                XONE_XNT_MOONPARTY_SOURCE_SEMANTICS_CONTRACT_VERSION,
            "state": STATE,
            "moonparty_source_semantics": proof,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "moonparty_authoritative_source_semantics_verified":
                    proof["authoritative_source_semantics_verified"],
                "xone_to_xnt_credit_design_link_verified":
                    proof["xone_to_xnt_credit_design_link_verified"],
            },
        }

    def discover_moonparty_deployment_candidates(
        self,
        documents: Sequence[Mapping[str, Any]],
        *,
        max_candidates: int = 25,
    ) -> dict[str, Any]:
        """Discover exact MoonParty address candidates from bounded source context."""

        discovery = discover_moonparty_deployment_candidates(
            documents,
            max_candidates=max_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "moonparty_deployment_contract":
                MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION,
            "state": STATE,
            "moonparty_deployment_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **_truth_state(),
        }

    def verify_moonparty_deployment_candidate(
        self,
        candidate_address: str,
        *,
        artifact: Mapping[str, Any],
        rpc_call: Any,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Direct-RPC qualify one exact MoonParty deployment candidate."""

        proof = verify_moonparty_deployment_candidate(
            candidate_address,
            artifact=artifact,
            rpc_call=rpc_call,
            source_url=source_url,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "moonparty_deployment_contract":
                MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION,
            "state": STATE,
            "moonparty_deployment_candidate": proof,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "moonparty_runtime_compatible":
                    proof["moonparty_runtime_compatible"],
                "moonparty_xone_binding_verified":
                    proof["moonparty_xone_binding_verified"],
            },
        }

    def corroborate_moonparty_deployment(
        self,
        proofs: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Promote deployment identity only after multi-RPC corroboration."""

        corroboration = corroborate_moonparty_deployment(proofs)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "moonparty_deployment_contract":
                MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION,
            "state": STATE,
            "moonparty_deployment": corroboration,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "moonparty_deployment_verified": True,
                "moonparty_deployment_chain_verified": True,
                "moonparty_runtime_compatible": True,
                "moonparty_xone_binding_verified": True,
            },
        }

    def expand_xone_snapshot_provenance(
        self,
        documents: Sequence[Mapping[str, Any]],
        *,
        observed_at: float,
        max_candidates_per_document: int = 50,
        max_ranked_candidates: int = 100,
    ) -> dict[str, Any]:
        """Rank bounded historical provenance leads without snapshot promotion."""

        if not documents:
            raise ValueError("documents must not be empty")
        candidates: list[dict[str, Any]] = []
        for document in documents:
            source_id = str(document.get("source_id") or "").strip()
            source_role = str(document.get("source_role") or "").strip()
            url = str(document.get("url") or "").strip()
            text_value = document.get("text")
            path = document.get("path")
            revision = document.get("revision")
            if not source_id or not source_role or not url or not isinstance(text_value, str):
                raise ValueError(
                    "each document requires source_id, source_role, url, and text"
                )
            candidates.extend(
                extract_provenance_candidates(
                    text_value,
                    source_id=source_id,
                    source_role=source_role,
                    url=url,
                    observed_at=observed_at,
                    path=str(path) if path is not None else None,
                    revision=str(revision) if revision is not None else None,
                    max_candidates=max_candidates_per_document,
                )
            )

        discovery = rank_provenance_candidates(
            candidates,
            max_candidates=max_ranked_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "snapshot_provenance_contract":
                XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
            "state": STATE,
            "provenance_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "xone_snapshot_provenance_expansion_verified": True,
                "provenance_candidate_discovered":
                    discovery["candidate_count"] > 0,
                "direct_primary_source_recovered":
                    discovery["direct_primary_source_candidate_count"] > 0,
                "snapshot_artifact_candidate_discovered":
                    discovery["snapshot_artifact_candidate_count"] > 0,
                "authoritative_exact_snapshot_block_discovered":
                    discovery["authoritative_exact_snapshot_block_discovered"],
            },
        }

    def discover_xone_snapshot_repository_paths(
        self,
        entries: Sequence[Mapping[str, Any]],
        *,
        source_id: str,
        source_role: str,
        repository_url: str,
        revision: str,
        observed_at: float,
        max_candidates: int = 100,
    ) -> dict[str, Any]:
        """Classify bounded repository tree paths as provenance leads only."""

        candidates = discover_repository_path_candidates(
            entries,
            source_id=source_id,
            source_role=source_role,
            repository_url=repository_url,
            revision=revision,
            observed_at=observed_at,
            max_candidates=max_candidates,
        )
        discovery = rank_provenance_candidates(
            candidates,
            max_candidates=max_candidates,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "snapshot_provenance_contract":
                XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
            "state": STATE,
            "repository_path_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "xone_snapshot_provenance_expansion_verified": True,
                "provenance_candidate_discovered":
                    discovery["candidate_count"] > 0,
            },
        }

    def discover_ethereum_xone_snapshot_candidates(
        self,
        documents: Sequence[Mapping[str, Any]],
        *,
        observed_at: float,
        max_claims_per_document: int = 50,
    ) -> dict[str, Any]:
        """Extract explicit XONE snapshot/registry claims without promotion."""

        if not documents:
            raise ValueError("documents must not be empty")
        claims: list[dict[str, Any]] = []
        for document in documents:
            source_id = str(document.get("source_id") or "").strip()
            source_role = str(document.get("source_role") or "").strip()
            url = str(document.get("url") or "").strip()
            text_value = document.get("text")
            if not source_id or not source_role or not url or not isinstance(text_value, str):
                raise ValueError(
                    "each document requires source_id, source_role, url, and text"
                )
            claims.extend(
                extract_xone_snapshot_claims(
                    text_value,
                    source_id=source_id,
                    source_role=source_role,
                    url=url,
                    observed_at=observed_at,
                    max_claims=max_claims_per_document,
                )
            )

        discovery = discover_official_snapshot_candidates(claims)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "xone_snapshot_registry_contract":
                XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
            "state": STATE,
            "snapshot_claims": claims,
            "snapshot_discovery": discovery,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "xone_snapshot_source_discovery_verified": True,
            },
        }

    def reconstruct_ethereum_xone_registry(
        self,
        *,
        rpc_call: Any,
        snapshot_block: int,
        source_url: str | None = None,
        log_chunk_blocks: int = 50_000,
        balance_sample_size: int = 25,
    ) -> dict[str, Any]:
        """Reconstruct and verify XONE balances at one explicit Ethereum block."""

        identity = verify_xone_identity(
            rpc_call=rpc_call,
            source_url=source_url,
        )
        registry = fetch_and_verify_xone_registry(
            rpc_call=rpc_call,
            snapshot_block=snapshot_block,
            source_url=source_url,
            log_chunk_blocks=log_chunk_blocks,
            balance_sample_size=balance_sample_size,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "ethereum_identity_contract": ETHEREUM_XONE_IDENTITY_CONTRACT,
            "xone_snapshot_registry_contract":
                XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
            "state": STATE,
            "ethereum_identity": identity,
            "xone_registry": registry,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "ethereum_xone_identity_verified": True,
                "reconstructed_xone_registry_verified": True,
            },
        }

    def corroborate_ethereum_xone_registry(
        self,
        proofs: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Require matching reconstructed XONE registries from distinct RPC hosts."""

        corroboration = corroborate_xone_registry_proofs(proofs)
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "xone_snapshot_registry_contract":
                XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
            "state": STATE,
            "xone_registry": corroboration,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "reconstructed_xone_registry_verified": True,
            },
        }

    def promote_official_ethereum_xone_snapshot(
        self,
        *,
        source_candidate: Mapping[str, Any],
        registry_proof: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Bind one authoritative exact-block snapshot claim to direct Ethereum state."""

        proof = promote_official_snapshot(
            source_candidate=source_candidate,
            registry_proof=registry_proof,
        )
        return {
            "service": SERVICE,
            "service_contract": SERVICE_CONTRACT,
            "scraper_contract": SCRAPER_CONTRACT,
            "xone_snapshot_registry_contract":
                XONE_SNAPSHOT_REGISTRY_CONTRACT_VERSION,
            "state": STATE,
            "official_snapshot": proof,
            "read_only": True,
            "xone_xnt_only": True,
            **{
                **_truth_state(),
                "reconstructed_xone_registry_verified": True,
                "official_xone_snapshot_verified": True,
                "official_registry_artifact_verified":
                    proof["official_registry_artifact_verified"],
                "xone_snapshot_eligibility_verified":
                    proof["xone_snapshot_eligibility_verified"],
                "xone_snapshot_xnt_allocation_binding_verified":
                    proof["xone_snapshot_xnt_allocation_binding_verified"],
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
