"""Registry for source-specific CMIS Web Discovery providers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import CMISWebDiscoveryProvider
from .github import GitHubWebDiscoveryProvider
from .x1_docs import X1DocsDiscoveryProvider
from .x1_explorer import X1ExplorerDiscoveryProvider
from .x1_ninja import X1NinjaWebDiscoveryProvider
from .x1report import X1ReportDiscoveryProvider
from .xdex import XDEXWebDiscoveryProvider


_PROVIDER_TYPES: dict[str, type[CMISWebDiscoveryProvider]] = {
    "x1_explorer": X1ExplorerDiscoveryProvider,
    "xdex": XDEXWebDiscoveryProvider,
    "x1_ninja": X1NinjaWebDiscoveryProvider,
    "x1report": X1ReportDiscoveryProvider,
    "x1_docs": X1DocsDiscoveryProvider,
    "github": GitHubWebDiscoveryProvider,
}


def provider_ids() -> tuple[str, ...]:
    return tuple(_PROVIDER_TYPES)


def provider_catalog() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_id, provider_type in _PROVIDER_TYPES.items():
        source = provider_type.source
        result.append(
            {
                "source_id": source_id,
                "source_name": source.source_name,
                "source_role": source.source_role,
                "base_urls": list(source.base_urls),
                "allowed_hosts": list(source.allowed_hosts),
                "read_only": True,
                "discovery_only": True,
                "cmis_verified": False,
                "public_service_promoted": False,
                "scout_reliance_promoted": False,
                "execution_authorized": False,
            }
        )
    return result


def build_provider(
    source_id: str,
    *,
    provider_kwargs: Mapping[str, Any] | None = None,
) -> CMISWebDiscoveryProvider:
    key = str(source_id or "").strip()
    if not key:
        raise ValueError("source_id must not be empty")
    provider_type = _PROVIDER_TYPES.get(key)
    if provider_type is None:
        raise ValueError(
            f"unsupported CMIS Web Discovery source_id {key!r}; "
            f"supported={list(_PROVIDER_TYPES)}"
        )
    kwargs = dict(provider_kwargs or {})
    return provider_type(**kwargs)


__all__ = [
    "build_provider",
    "provider_catalog",
    "provider_ids",
]
