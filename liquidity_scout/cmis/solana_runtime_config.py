"""Deployment-owned Solana runtime configuration for CMIS Phase 10.

The Solana CMIS service mixins are deliberately provider-injected.  This module
is the production composition boundary that turns environment/configuration
into those read-only provider objects without letting HTTP callers choose
providers, policies, persistence paths, or credentials.

Solana stays disabled by default.  Setting ``CMIS_SOLANA_PROVIDER_ENABLED`` to
an explicit true value enables the canonical RPC provider, the exact-fixture
read-only Pyth Core push-feed provider over that same RPC, the public DEX
Screener pair source, and the provenance-safe observation ledger. Jupiter and
Helius are constructed only when their API keys are present. Missing optional
providers therefore fail closed at the service that requires them instead of
preventing CMIS/X1 startup. The Pyth path uses no Hermes credential and never
submits an update or transaction.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from liquidity_scout.cmis.solana_observation_ledger import SolanaObservationLedger
from liquidity_scout.providers.solana.dexscreener import DexScreenerSolanaProvider
from liquidity_scout.providers.solana.helius import HeliusDASProvider
from liquidity_scout.providers.solana.jupiter import JupiterSourceProvider
from liquidity_scout.providers.solana.pyth_push import PythSolanaPushProvider
from liquidity_scout.providers.solana.rpc import SolanaRPCProvider


DEFAULT_SOLANA_OBSERVATION_DB = os.path.join(
    os.path.expanduser("~"),
    ".liquidity_scout",
    "solana_observations.db",
)
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


def _text(env: Mapping[str, Any], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _enabled(env: Mapping[str, Any]) -> bool:
    raw = str(env.get("CMIS_SOLANA_PROVIDER_ENABLED", "")).strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(
        "CMIS_SOLANA_PROVIDER_ENABLED must be one of: 1/0, true/false, "
        "yes/no, on/off"
    )


def _optional_nonnegative_int(
    env: Mapping[str, Any], name: str
) -> int | None:
    text = _text(env, name)
    if text is None:
        return None
    if not text.isdigit():
        raise ValueError(f"{name} must be a non-negative integer")
    return int(text)


def _optional_nonnegative_float(
    env: Mapping[str, Any], name: str
) -> float | None:
    text = _text(env, name)
    if text is None:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be a non-negative finite number") from exc
    if value < 0 or value != value or value in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be a non-negative finite number")
    return value


def build_solana_runtime_dependencies(
    env: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build read-only Solana dependencies and a secret-free status summary.

    ``env`` is injectable for deterministic tests.  Production calls load the
    repository ``.env`` through python-dotenv and then read ``os.environ``.
    Provider constructors may retain credentials internally, but the returned
    status object contains only booleans/policy-presence and never URLs or keys.
    """

    if env is None:
        load_dotenv()
        source: Mapping[str, Any] = os.environ
    else:
        source = env

    enabled = _enabled(source)
    status: dict[str, Any] = {
        "enabled": enabled,
        "rpc_configured": False,
        "jupiter_configured": False,
        "dexscreener_configured": False,
        "pyth_configured": False,
        "helius_configured": False,
        "price_crosscheck_policy_configured": False,
        "supply_crosscheck_policy_configured": False,
        "observation_ledger_configured": False,
        "history_distance_policy_configured": False,
        "read_only": True,
        "execution_authorized": False,
    }
    if not enabled:
        return {}, status

    dependencies: dict[str, Any] = {}

    rpc_url = _text(source, "SOLANA_RPC_URL")
    dependencies["solana_rpc_provider"] = SolanaRPCProvider(rpc_url=rpc_url)
    status["rpc_configured"] = True

    # Pyth Core sponsored push feeds are read through the same Solana RPC.
    # The provider itself is exact-fixture-gated and needs no Hermes/API key.
    dependencies["solana_pyth_provider"] = PythSolanaPushProvider(
        dependencies["solana_rpc_provider"]
    )
    status["pyth_configured"] = True

    # DEX Screener's accepted token-pairs endpoint is public/read-only and does
    # not require a deployment secret.
    dependencies["solana_dexscreener_provider"] = DexScreenerSolanaProvider()
    status["dexscreener_configured"] = True

    jupiter_key = _text(source, "JUPITER_API_KEY")
    if jupiter_key is not None:
        dependencies["solana_jupiter_provider"] = JupiterSourceProvider(
            api_key=jupiter_key
        )
        status["jupiter_configured"] = True

    helius_key = _text(source, "HELIUS_API_KEY")
    if helius_key is not None:
        dependencies["solana_helius_provider"] = HeliusDASProvider(
            api_key=helius_key
        )
        status["helius_configured"] = True

    price_tolerance = _text(
        source, "CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE"
    )
    if price_tolerance is not None:
        # The market mixin remains the single semantic validator for the [0, 1]
        # tolerance contract.  Passing the raw decimal text avoids a second
        # numerical policy implementation here.
        dependencies["solana_price_max_relative_difference"] = price_tolerance
        status["price_crosscheck_policy_configured"] = True

    supply_lag = _optional_nonnegative_int(
        source, "CMIS_SOLANA_SUPPLY_MAX_INDEX_SLOT_LAG"
    )
    if supply_lag is not None:
        dependencies["solana_supply_max_index_slot_lag"] = supply_lag
        status["supply_crosscheck_policy_configured"] = True

    configured_db = _text(source, "CMIS_SOLANA_OBSERVATION_DB")
    raw_db_path = configured_db or DEFAULT_SOLANA_OBSERVATION_DB
    db_path = raw_db_path if raw_db_path == ":memory:" else str(
        Path(raw_db_path).expanduser().resolve()
    )
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    dependencies["solana_observation_ledger"] = SolanaObservationLedger(db_path)
    status["observation_ledger_configured"] = True

    history_distance = _optional_nonnegative_float(
        source, "CMIS_SOLANA_HISTORY_MAX_DISTANCE_SECONDS"
    )
    if history_distance is not None:
        dependencies["solana_history_max_distance_seconds"] = history_distance
        status["history_distance_policy_configured"] = True

    return dependencies, status


__all__ = [
    "DEFAULT_SOLANA_OBSERVATION_DB",
    "build_solana_runtime_dependencies",
]
