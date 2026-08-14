"""Deterministic XDEX market-data core."""

from .aggregation import aggregate_assets
from .client import XDEXCatalog, fetch_all_pools
from .resolver import (
    asset_key,
    candidate_terms,
    find_matches_for_term,
    pool_address,
    resolve_asset,
    resolve_multiple_assets,
)

__all__ = [
    "XDEXCatalog",
    "aggregate_assets",
    "asset_key",
    "candidate_terms",
    "fetch_all_pools",
    "find_matches_for_term",
    "pool_address",
    "resolve_asset",
    "resolve_multiple_assets",
]
