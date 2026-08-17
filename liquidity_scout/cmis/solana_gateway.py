"""Narrow Solana asset-identity gateway layer for CMIS.

This layer promotes only exact mint-address identity lookup. It does not perform
symbol/name discovery, market collection, tokenomics, risk analysis, or any
transaction operation. A Solana RPC provider must be explicitly injected by the
deployment; the production default remains disabled/fail-closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.providers.solana.rpc import (
    SolanaRPCError,
    SolanaRPCNotFound,
)
from liquidity_scout.services.cmis_contract import (
    ERROR,
    OK,
    UNAVAILABLE,
    build_service_envelope,
)

SERVICE = "asset_lookup"
CHAIN = "solana"
_BASE58_ALPHABET = frozenset(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)


def _looks_like_solana_pubkey(value: object) -> bool:
    """Cheap classification gate; canonical validity is still proven by RPC."""

    if not isinstance(value, str):
        return False
    text = value.strip()
    return 32 <= len(text) <= 44 and all(char in _BASE58_ALPHABET for char in text)


class SolanaAssetLookupMixin:
    """Cooperative gateway mixin for exact-mint Solana identity lookup only."""

    def __init__(self, *, solana_rpc_provider: Any = None, **kwargs: Any):
        self.solana_rpc_provider = solana_rpc_provider
        super().__init__(**kwargs)

    def _solana_lookup_unavailable(self, code: str, message: str):
        return build_service_envelope(
            SERVICE,
            CHAIN,
            UNAVAILABLE,
            warnings=[{"code": code, "message": message}],
        )

    def _solana_asset_lookup(self, asset: Any):
        query = self._text(asset)
        if not query:
            return self._gateway_error(
                SERVICE,
                CHAIN,
                "asset_query_required",
                "An exact Solana mint address is required.",
            )

        if not _looks_like_solana_pubkey(query):
            return self._solana_lookup_unavailable(
                "solana_asset_lookup_requires_exact_mint",
                (
                    "Solana asset lookup currently accepts an exact mint address only. "
                    "Symbol/name discovery is not yet an accepted CMIS capability."
                ),
            )

        provider = self.solana_rpc_provider
        if provider is None:
            return self._solana_lookup_unavailable(
                "solana_rpc_provider_not_configured",
                (
                    "The Solana RPC identity provider is not configured in this CMIS "
                    "deployment."
                ),
            )

        try:
            record = provider.get_mint_account(query)
        except SolanaRPCNotFound:
            return self._solana_lookup_unavailable(
                "solana_mint_not_found",
                "Canonical Solana RPC returned no mint account for the requested address.",
            )
        except SolanaRPCError as exc:
            # Do not reflect arbitrary exception text. A future provider wrapper
            # could accidentally include a credential-bearing RPC URL or response.
            return self._solana_lookup_unavailable(
                "solana_rpc_asset_lookup_unavailable",
                f"Canonical Solana mint lookup failed ({type(exc).__name__}).",
            )
        except Exception as exc:
            return self._solana_lookup_unavailable(
                "solana_rpc_asset_lookup_failed_closed",
                f"Canonical Solana mint lookup failed ({type(exc).__name__}).",
            )

        if not isinstance(record, Mapping):
            return self._gateway_error(
                SERVICE,
                CHAIN,
                "solana_mint_identity_contract_invalid",
                "The Solana RPC provider returned a malformed mint identity record.",
            )

        identity_ok = (
            record.get("chain") == CHAIN
            and record.get("source") == "solana_rpc"
            and record.get("method") == "getAccountInfo(jsonParsed)"
            and record.get("mint") == query
            and record.get("program_identity_verified") is True
            and record.get("mint_state_verified") is True
            and record.get("is_initialized") is True
        )
        if not identity_ok:
            return build_service_envelope(
                SERVICE,
                CHAIN,
                ERROR,
                errors=[{
                    "code": "solana_mint_identity_contract_invalid",
                    "message": (
                        "The Solana RPC mint identity record failed canonical identity "
                        "or initialization checks."
                    ),
                }],
            )

        slot = record.get("context_slot")
        if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
            return build_service_envelope(
                SERVICE,
                CHAIN,
                ERROR,
                errors=[{
                    "code": "solana_mint_identity_slot_invalid",
                    "message": "The canonical Solana mint observation slot is invalid.",
                }],
            )

        decimals = record.get("decimals")
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 255:
            return build_service_envelope(
                SERVICE,
                CHAIN,
                ERROR,
                errors=[{
                    "code": "solana_mint_identity_decimals_invalid",
                    "message": "The canonical Solana mint decimals field is invalid.",
                }],
            )

        extension_names = record.get("extension_names")
        if not isinstance(extension_names, list) or not all(
            isinstance(name, str) and name.strip() for name in extension_names
        ):
            return build_service_envelope(
                SERVICE,
                CHAIN,
                ERROR,
                errors=[{
                    "code": "solana_mint_extensions_invalid",
                    "message": "The canonical Solana mint extension list is invalid.",
                }],
            )

        asset_identity = {
            "chain": CHAIN,
            "mint": query,
        }
        data = {
            "identity_key": f"solana:mint:{query}",
            "resolution": {
                "input_type": "mint",
                "exact": True,
                "ambiguous": False,
            },
            "program": {
                "owner_program_id": record.get("owner_program_id"),
                "parsed_program": record.get("parsed_program"),
                "program_kind": record.get("program_kind"),
                "identity_verified": True,
            },
            "decimals": decimals,
            "is_initialized": True,
            "extension_names": list(extension_names),
            "metadata": {
                "name": None,
                "symbol": None,
                "verified": False,
                "source": None,
            },
        }
        return build_service_envelope(
            SERVICE,
            CHAIN,
            OK,
            asset=asset_identity,
            data=data,
            confidence={
                "identity": "verified",
                "metadata": "unavailable",
            },
            sources=[{
                "source": "solana_rpc",
                "role": "canonical_mint_identity",
                "method": "getAccountInfo(jsonParsed)",
                "block_slot": slot,
            }],
            observed_at=None,
            warnings=[
                {
                    "code": "solana_metadata_not_collected",
                    "message": (
                        "Name and symbol metadata are intentionally unavailable in the "
                        "first exact-mint asset lookup slice."
                    ),
                },
                {
                    "code": "solana_wall_clock_observation_time_unavailable",
                    "message": (
                        "Canonical identity is anchored to an RPC slot; no wall-clock "
                        "observation timestamp is claimed."
                    ),
                },
            ],
        )

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (self._text(request.get("service")) or "").lower()
            chain = (self._text(request.get("chain")) or "").lower()
            if service == SERVICE and chain == CHAIN:
                params = request.get("params", {})
                if not isinstance(params, Mapping):
                    return self._gateway_error(
                        SERVICE,
                        CHAIN,
                        "invalid_params",
                        "params must be a JSON object/mapping.",
                    )
                if params:
                    return self._gateway_error(
                        SERVICE,
                        CHAIN,
                        "solana_asset_lookup_params_not_supported",
                        (
                            "The first Solana asset_lookup slice accepts only the exact "
                            "mint in the top-level asset field."
                        ),
                    )
                return self._solana_asset_lookup(request.get("asset"))

        return super().dispatch(request)


__all__ = [
    "CHAIN",
    "SERVICE",
    "SolanaAssetLookupMixin",
]
