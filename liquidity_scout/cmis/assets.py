"""Deterministic canonical-asset and provider-representation registry for CMIS.

CMIS must not infer that every token whose provider name starts with ``Wrapped``
is a native asset. Canonical relationships are explicit configuration facts.
Provider/Dex representations remain traceable and may still carry the mint used
for market collection, while the public CMIS asset identity stays canonical.
"""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any, Dict, Optional


NATIVE = "native"
MARKET = "market"
MARKET_PLUS_NATIVE = "market+native"


DEFAULT_ASSET_DEFINITIONS = (
    {
        "canonical_id": "x1:native:XNT",
        "chain": "x1",
        "symbol": "XNT",
        "name": "XNT",
        "asset_type": "native",
        "aliases": ("XNT",),
        "representations": {
            "native": {
                "kind": "native",
                "provider": "x1_network",
            },
            "market": {
                "kind": "wrapped_token",
                "provider": "X1.Ninja/XDEX",
                "query": "XNT",
            },
        },
        "service_modes": {
            "asset_lookup": MARKET,
            "market_report": MARKET,
            "historical_compare": MARKET,
            "tokenomics": NATIVE,
            "risk_check": MARKET_PLUS_NATIVE,
            "pre_trade_check": MARKET_PLUS_NATIVE,
        },
        "native_tokenomics_provider": "x1_supply",
    },
)


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _public_identity(definition: Mapping[str, Any]) -> Dict[str, Any]:
    asset_type = _text(definition.get("asset_type"))
    return {
        "canonical_id": _text(definition.get("canonical_id")),
        "symbol": _text(definition.get("symbol")),
        "name": _text(definition.get("name")),
        "mint": None if asset_type == "native" else _text(definition.get("mint")),
        "asset_type": asset_type,
    }


class AssetRegistry:
    """Explicit chain-aware canonical asset registry.

    The registry matches only configured aliases/canonical IDs. It deliberately
    performs no fuzzy matching and no automatic ``Wrapped X -> X`` conversion.
    """

    def __init__(self, definitions: Optional[Iterable[Mapping[str, Any]]] = None):
        self._definitions = []
        self._by_alias = {}
        for raw in definitions if definitions is not None else DEFAULT_ASSET_DEFINITIONS:
            if not isinstance(raw, Mapping):
                raise ValueError("asset definitions must be mappings")
            definition = deepcopy(dict(raw))
            chain = (_text(definition.get("chain")) or "").lower()
            symbol = _text(definition.get("symbol"))
            canonical_id = _text(definition.get("canonical_id"))
            if not chain or not symbol or not canonical_id:
                raise ValueError("canonical asset definitions require chain, symbol, and canonical_id")

            aliases = definition.get("aliases")
            aliases = list(aliases) if isinstance(aliases, (list, tuple, set, frozenset)) else []
            aliases.extend([symbol, canonical_id])
            normalized_aliases = []
            for alias in aliases:
                alias_text = _text(alias)
                if not alias_text:
                    continue
                key = (chain, alias_text.casefold())
                existing = self._by_alias.get(key)
                if existing is not None and existing.get("canonical_id") != canonical_id:
                    raise ValueError(f"duplicate canonical asset alias: {alias_text}")
                self._by_alias[key] = definition
                if alias_text not in normalized_aliases:
                    normalized_aliases.append(alias_text)
            definition["aliases"] = tuple(normalized_aliases)
            self._definitions.append(definition)

    def resolve(self, chain: Any, asset: Any) -> Optional[Dict[str, Any]]:
        chain_text = (_text(chain) or "").lower()
        asset_text = _text(asset)
        if not chain_text or not asset_text:
            return None
        definition = self._by_alias.get((chain_text, asset_text.casefold()))
        return deepcopy(definition) if definition is not None else None

    @staticmethod
    def public_identity(definition: Mapping[str, Any]) -> Dict[str, Any]:
        return _public_identity(definition)

    @staticmethod
    def service_mode(definition: Mapping[str, Any], service: Any) -> Optional[str]:
        modes = definition.get("service_modes")
        if not isinstance(modes, Mapping):
            return None
        return _text(modes.get(str(service or "").strip().lower()))

    @staticmethod
    def market_query(definition: Mapping[str, Any]) -> Optional[str]:
        representations = definition.get("representations")
        representations = representations if isinstance(representations, Mapping) else {}
        market = representations.get("market")
        market = market if isinstance(market, Mapping) else {}
        return _text(market.get("query")) or _text(definition.get("symbol"))

    @staticmethod
    def representation_record(
        definition: Mapping[str, Any],
        provider_asset: Any,
        *,
        role: str = "market",
        identity_key: Any = None,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(provider_asset, Mapping):
            return None
        symbol = _text(provider_asset.get("symbol"))
        name = _text(provider_asset.get("name"))
        mint = _text(provider_asset.get("mint") or provider_asset.get("address"))
        if not any((symbol, name, mint)):
            return None

        representations = definition.get("representations")
        representations = representations if isinstance(representations, Mapping) else {}
        configured = representations.get(role)
        configured = configured if isinstance(configured, Mapping) else {}

        record = {
            "role": role,
            "kind": _text(configured.get("kind")),
            "provider": _text(configured.get("provider")),
            "chain": _text(definition.get("chain")),
            "symbol": symbol,
            "name": name,
            "mint": mint,
        }
        key = _text(identity_key)
        if key:
            record["identity_key"] = key
        return record

    def canonicalize_envelope(
        self,
        envelope: Any,
        definition: Optional[Mapping[str, Any]],
        *,
        provider_asset: Any = None,
        role: str = "market",
        identity_key: Any = None,
    ):
        """Return a copy with canonical public identity and traced representation."""
        if not isinstance(envelope, Mapping) or not isinstance(definition, Mapping):
            return envelope

        result = deepcopy(dict(envelope))
        original_asset = provider_asset
        if not isinstance(original_asset, Mapping):
            original_asset = result.get("asset")

        result["asset"] = self.public_identity(definition)
        data = result.get("data")
        data = deepcopy(dict(data)) if isinstance(data, Mapping) else {}
        data["canonical_asset"] = self.public_identity(definition)

        representation = self.representation_record(
            definition,
            original_asset,
            role=role,
            identity_key=identity_key,
        )
        if representation is not None:
            records = data.get("representations")
            records = list(records) if isinstance(records, list) else []
            if representation not in records:
                records.append(representation)
            data["representations"] = records

        result["data"] = data
        return result


DEFAULT_ASSET_REGISTRY = AssetRegistry()


__all__ = [
    "AssetRegistry",
    "DEFAULT_ASSET_DEFINITIONS",
    "DEFAULT_ASSET_REGISTRY",
    "MARKET",
    "MARKET_PLUS_NATIVE",
    "NATIVE",
]
