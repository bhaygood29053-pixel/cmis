"""Narrow Solana tokenomics gateway layer for CMIS.

Promotes only exact-mint, read-only tokenomics facts that can be proven from the
accepted canonical Solana RPC contract. Helius DAS may be injected as an
independent indexed supply cross-check when an explicit slot-lag policy is also
configured. Circulating supply, maximum supply, lifetime mint/burn coverage, and
execution remain unavailable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
from liquidity_scout.providers.solana.helius import HeliusSourceError
from liquidity_scout.providers.solana.rpc import SolanaRPCError, SolanaRPCNotFound
from liquidity_scout.providers.solana.supply_verification import verify_rpc_vs_helius_supply
from liquidity_scout.services.cmis_contract import ERROR, PARTIAL, UNAVAILABLE, build_service_envelope

SERVICE = "tokenomics"
CHAIN = "solana"


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _u8(value: object) -> int | None:
    parsed = _nonnegative_int(value)
    if parsed is None or parsed > 255:
        return None
    return parsed


def _raw_amount(value: object) -> str | None:
    if not isinstance(value, str) or not value or not value.isdigit():
        return None
    return value.lstrip("0") or "0"


def _scaled_amount(raw_amount: str, decimals: int) -> str:
    if decimals == 0:
        return raw_amount
    padded = raw_amount.zfill(decimals + 1)
    whole = padded[:-decimals]
    fraction = padded[-decimals:].rstrip("0")
    return whole if not fraction else f"{whole}.{fraction}"


def _lag(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("solana_supply_max_index_slot_lag must be a non-negative integer or null")
    return value


class SolanaTokenomicsMixin:
    """Cooperative CMIS gateway mixin for exact-mint Solana tokenomics."""

    def __init__(self, *, solana_helius_provider: Any = None, solana_supply_max_index_slot_lag: int | None = None, **kwargs: Any):
        self.solana_helius_provider = solana_helius_provider
        self.solana_supply_max_index_slot_lag = _lag(solana_supply_max_index_slot_lag)
        super().__init__(**kwargs)

    def _solana_tokenomics_error(self, code: str, message: str):
        return build_service_envelope(SERVICE, CHAIN, ERROR, errors=[{"code": code, "message": message}])

    def _solana_tokenomics_unavailable(self, code: str, message: str):
        return build_service_envelope(SERVICE, CHAIN, UNAVAILABLE, warnings=[{"code": code, "message": message}])

    def _validated_supply(self, mint: str, record: object):
        if not isinstance(record, Mapping):
            return None, self._solana_tokenomics_error("solana_token_supply_contract_invalid", "Canonical Solana RPC returned a malformed token-supply record.")
        if not (
            record.get("chain") == CHAIN
            and record.get("source") == "solana_rpc"
            and record.get("method") == "getTokenSupply"
            and record.get("mint") == mint
            and record.get("supply_verified") is True
            and record.get("coverage") == "total_token_supply"
        ):
            return None, self._solana_tokenomics_error("solana_token_supply_contract_invalid", "Canonical Solana RPC token-supply identity or coverage checks failed.")
        amount_raw = _raw_amount(record.get("amount_raw"))
        decimals = _u8(record.get("decimals"))
        slot = _nonnegative_int(record.get("context_slot"))
        if amount_raw is None or decimals is None or slot is None:
            return None, self._solana_tokenomics_error("solana_token_supply_contract_invalid", "Canonical Solana RPC token-supply amount, decimals, or slot is invalid.")
        return {"record": dict(record), "amount_raw": amount_raw, "decimals": decimals, "slot": slot}, None

    def _helius_supply_crosscheck(self, mint: str, rpc_supply: Mapping[str, Any]):
        provider = self.solana_helius_provider
        allowed_lag = self.solana_supply_max_index_slot_lag
        if provider is None:
            return ({"status": "unavailable", "reason": "helius_provider_not_configured", "cmis_promotable": False}, None, {"code": "solana_supply_crosscheck_not_configured", "message": "Independent Helius supply cross-check is not configured; canonical RPC supply remains the current source of truth."})
        if allowed_lag is None:
            return ({"status": "unavailable", "reason": "max_index_slot_lag_not_configured", "cmis_promotable": False}, None, {"code": "solana_supply_crosscheck_policy_not_configured", "message": "Helius is configured, but no explicit maximum index-slot lag policy was supplied; the indexed source was not queried."})
        try:
            helius_asset = provider.get_asset(mint)
            result = verify_rpc_vs_helius_supply(rpc_supply, helius_asset, max_index_slot_lag=allowed_lag)
        except HeliusSourceError as exc:
            return ({"status": "unavailable", "reason": "helius_crosscheck_failed", "cmis_promotable": False}, None, {"code": "solana_supply_crosscheck_unavailable", "message": f"Helius supply cross-check failed ({type(exc).__name__})."})
        except Exception as exc:
            return ({"status": "unavailable", "reason": "helius_crosscheck_failed_closed", "cmis_promotable": False}, None, {"code": "solana_supply_crosscheck_failed_closed", "message": f"Helius supply cross-check failed ({type(exc).__name__})."})
        source = None
        if isinstance(helius_asset, Mapping):
            source = {"source": "helius_das", "role": "tokenomics.independent_supply_crosscheck", "block_slot": helius_asset.get("last_indexed_slot")}
        warning = None
        status = result.get("status") if isinstance(result, Mapping) else None
        if status == CONFLICT:
            warning = {"code": "solana_supply_crosscheck_conflict", "message": "Helius indexed supply conflicts with canonical RPC supply within the configured slot-lag window."}
        elif status == INSUFFICIENT_EVIDENCE:
            warning = {"code": "solana_supply_crosscheck_insufficient_evidence", "message": "The independent Helius supply cross-check did not meet the configured evidence/recency gate."}
        elif status == AGREEMENT:
            warning = {"code": "solana_supply_crosscheck_absolute_freshness_unverified", "message": "RPC and Helius supply agree within the configured slot window, but absolute wall-clock freshness is not independently verified."}
        return dict(result), source, warning

    def _solana_tokenomics(self, asset: Any):
        identity = self._solana_asset_lookup(asset)
        if not isinstance(identity, Mapping):
            return self._solana_tokenomics_error("solana_asset_lookup_contract_invalid", "The Solana asset-identity prerequisite returned a malformed result.")
        if identity.get("status") != "ok":
            return self._propagate_upstream(SERVICE, identity)
        identity_asset = identity.get("asset")
        identity_data = identity.get("data")
        if not isinstance(identity_asset, Mapping) or not isinstance(identity_data, Mapping):
            return self._solana_tokenomics_error("solana_asset_lookup_contract_invalid", "The verified Solana asset-identity prerequisite is incomplete.")
        mint = identity_asset.get("mint")
        if not isinstance(mint, str) or not mint:
            return self._solana_tokenomics_error("solana_asset_lookup_contract_invalid", "The verified Solana asset identity contains no exact mint.")
        provider = getattr(self, "solana_rpc_provider", None)
        if provider is None:
            return self._solana_tokenomics_unavailable("solana_rpc_provider_not_configured", "The canonical Solana RPC provider is not configured.")
        try:
            raw_supply = provider.get_token_supply(mint)
        except SolanaRPCNotFound:
            return self._solana_tokenomics_unavailable("solana_token_supply_not_found", "Canonical Solana RPC returned no token-supply record for the mint.")
        except SolanaRPCError as exc:
            return self._solana_tokenomics_unavailable("solana_token_supply_unavailable", f"Canonical Solana token-supply lookup failed ({type(exc).__name__}).")
        except Exception as exc:
            return self._solana_tokenomics_unavailable("solana_token_supply_failed_closed", f"Canonical Solana token-supply lookup failed ({type(exc).__name__}).")
        supply, failure = self._validated_supply(mint, raw_supply)
        if failure is not None:
            return failure
        assert supply is not None
        if identity_data.get("decimals") != supply["decimals"]:
            return self._solana_tokenomics_error("solana_tokenomics_decimals_conflict", "Canonical mint identity and canonical token-supply RPC returned different decimals for the same mint.")
        program = identity_data.get("program")
        authorities = identity_data.get("authorities")
        extension_names = identity_data.get("extension_names")
        if not isinstance(program, Mapping) or not isinstance(authorities, Mapping) or not isinstance(extension_names, list):
            return self._solana_tokenomics_error("solana_asset_lookup_contract_invalid", "Verified Solana mint program/authority data is incomplete.")
        mint_authority = authorities.get("mint_authority")
        freeze_authority = authorities.get("freeze_authority")
        crosscheck, helius_source, crosscheck_warning = self._helius_supply_crosscheck(mint, supply["record"])
        warnings = [
            {"code": "circulating_supply_unverified", "message": "Circulating supply is not independently verified by this Solana slice."},
            {"code": "maximum_supply_unverified", "message": "Maximum supply is not inferred from current supply or mint authority."},
            {"code": "solana_wall_clock_observation_time_unavailable", "message": "Canonical tokenomics facts are anchored to RPC slots; no wall-clock observation timestamp is claimed."},
        ]
        if crosscheck_warning is not None:
            warnings.append(crosscheck_warning)
        sources = list(identity.get("sources") or [])
        sources.append({"source": "solana_rpc", "role": "tokenomics.total_supply", "method": "getTokenSupply", "block_slot": supply["slot"]})
        if helius_source is not None:
            sources.append(helius_source)
        checks = {"identity_verified": True, "total_supply_verified": True, "mint_authority_verified": True, "freeze_authority_verified": True, "circulating_supply_verified": False, "maximum_supply_verified": False}
        verified_checks = sum(1 for value in checks.values() if value)
        return build_service_envelope(
            SERVICE,
            CHAIN,
            PARTIAL,
            asset={"chain": CHAIN, "mint": mint},
            data={
                "mint": mint,
                "supply_verified": True,
                "total_supply_raw": supply["amount_raw"],
                "total_supply": _scaled_amount(supply["amount_raw"], supply["decimals"]),
                "decimals": supply["decimals"],
                "circulating_supply": None,
                "circulating_supply_verified": False,
                "maximum_supply": None,
                "maximum_supply_verified": False,
                "mint_authority": mint_authority,
                "mint_authority_verified": True,
                "mint_authority_status": "revoked" if mint_authority is None else "active",
                "freeze_authority": freeze_authority,
                "freeze_authority_verified": True,
                "freeze_authority_status": "none" if freeze_authority is None else "active",
                "program": dict(program),
                "extension_names": list(extension_names),
                "supply_crosscheck": crosscheck,
            },
            confidence={"complete": False, "verified_checks": verified_checks, "total_checks": len(checks), "verification_ratio": round(verified_checks / len(checks), 6), "checks": checks},
            sources=sources,
            observed_at=None,
            warnings=warnings,
            errors=[],
        )

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (self._text(request.get("service")) or "").lower()
            chain = (self._text(request.get("chain")) or "").lower()
            if service == SERVICE and chain == CHAIN:
                params = request.get("params", {})
                if not isinstance(params, Mapping):
                    return self._gateway_error(SERVICE, CHAIN, "invalid_params", "params must be a JSON object/mapping.")
                if params:
                    return self._gateway_error(SERVICE, CHAIN, "solana_tokenomics_params_not_supported", "Solana tokenomics policy is deployment-configured; the external request accepts only an exact mint asset.")
                return self._solana_tokenomics(request.get("asset"))
        return super().dispatch(request)


__all__ = ["CHAIN", "SERVICE", "SolanaTokenomicsMixin"]
