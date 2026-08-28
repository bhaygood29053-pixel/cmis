"""Read-only Pyth Core push-feed evidence for Solana.

Initial scope is deliberately fixture-bound. CMIS never discovers a Pyth feed by
symbol/name. An exact Solana mint must have an explicit repository-approved
mint -> feed-id -> account mapping with provenance.

The first accepted fixture uses the Pyth Core "current" Solana program/account
path which Pyth documents as upgraded in place on 2026-08-26. Pyth recommends
new integrations use the alternate upgraded addresses; CMIS records that
limitation rather than silently switching program generations.

No transaction construction, price update submission, Hermes access, signing,
or broadcast exists in this provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import hashlib
import struct
from typing import Any

from liquidity_scout.providers.solana.rpc import (
    SolanaRPCError,
    SolanaRPCNotFound,
)

CHAIN = "solana"
SOURCE = "pyth_core_solana_push"
VERSION = "pyth_core_solana_push/v1"

PYTH_CORE_RECEIVER_PROGRAM_ID = "rec5EKMGg6MxZYaMdyBfgwp4d5rB9T1VQH5pJv5LtFJ"
PYTH_CORE_PUSH_ORACLE_PROGRAM_ID = "pythWSnswVUd12oZpeFP8e9CVaEqJg25g1Vtc2biRsT"
PYTH_CORE_UPGRADED_RECEIVER_PROGRAM_ID = "rec2HHDDnjLfj4kE7VyEtFA1HPGQLK33259532cRyHp"
PYTH_CORE_UPGRADED_PUSH_ORACLE_PROGRAM_ID = "pyt2F414BA6dPttK6RddPZUdHfapoBN24GL5wbrPCou"

PRICE_UPDATE_V2_DISCRIMINATOR = hashlib.sha256(
    b"account:PriceUpdateV2"
).digest()[:8]
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

PYTH_CORE_CONTRACT_PROVENANCE = (
    "https://docs.pyth.network/price-feeds/core/upgrade/contracts"
)
PYTH_SOLANA_PUSH_FEED_PROVENANCE = (
    "https://docs.pyth.network/price-feeds/core/push-feeds/solana"
)
PYTH_PRICE_LAYOUT_PROVENANCE = (
    "https://github.com/pyth-network/pyth-crosschain/tree/"
    "ea35ae4718ccfe7abb31a1817f92a9dd548af1f2/"
    "target_chains/solana"
)

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_USD_FEED_ID = (
    "eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a"
)
USDC_USD_CURRENT_ACCOUNT = "Dpw1EAVrSB1ibxiDQyTAW6Zip3J4Btk2x4SgApQCeFbX"

PYTH_SOLANA_FEED_FIXTURES: dict[str, dict[str, Any]] = {
    USDC_MINT: {
        "mint": USDC_MINT,
        "asset_symbol": "USDC",
        "quote_symbol": "USD",
        "price_subject": "USDC",
        "unit": "USD_per_USDC",
        "feed_alias": "USDC/USD",
        "feed_id": USDC_USD_FEED_ID,
        "account_address": USDC_USD_CURRENT_ACCOUNT,
        "shard_id": 0,
        "receiver_program_id": PYTH_CORE_RECEIVER_PROGRAM_ID,
        "push_oracle_program_id": PYTH_CORE_PUSH_ORACLE_PROGRAM_ID,
        "contract_generation": "pyth_core_current_in_place_upgraded_2026_08_26",
        "mapping_provenance": (
            "CMIS exact fixture: canonical Solana USDC mint mapped to the "
            "provider-listed Pyth USDC/USD sponsored shard-0 push feed. "
            "No symbol/name discovery is permitted."
        ),
        "provider_feed_provenance": PYTH_SOLANA_PUSH_FEED_PROVENANCE,
        "contract_provenance": PYTH_CORE_CONTRACT_PROVENANCE,
        "provider_source_commit": "ea35ae4718ccfe7abb31a1817f92a9dd548af1f2",
    }
}


class PythSolanaSourceError(RuntimeError):
    """Raised when exact Pyth on-chain evidence cannot be verified."""


def _base58_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PythSolanaSourceError("base58 value must be a non-empty string")
    number = 0
    for char in value:
        try:
            digit = _BASE58_ALPHABET.index(char)
        except ValueError as exc:
            raise PythSolanaSourceError("base58 value contains invalid character") from exc
        number = number * 58 + digit
    payload = b"" if number == 0 else number.to_bytes((number.bit_length() + 7) // 8, "big")
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return (b"\x00" * leading_zeroes) + payload


def _decimal_text(price: int, exponent: int) -> str:
    value = Decimal(price) * (Decimal(10) ** exponent)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _parse_price_update_v2(data: bytes) -> dict[str, Any]:
    if not isinstance(data, bytes):
        raise PythSolanaSourceError("Pyth account data must be bytes")
    if len(data) < 133:
        raise PythSolanaSourceError("Pyth PriceUpdateV2 account is too short")
    if data[:8] != PRICE_UPDATE_V2_DISCRIMINATOR:
        raise PythSolanaSourceError("Pyth PriceUpdateV2 discriminator mismatch")

    offset = 8
    write_authority = data[offset : offset + 32]
    offset += 32

    variant = data[offset]
    offset += 1
    if variant == 0:
        if len(data) < 134:
            raise PythSolanaSourceError("partial PriceUpdateV2 account is too short")
        num_signatures = data[offset]
        offset += 1
        verification_level = "partial"
    elif variant == 1:
        num_signatures = None
        verification_level = "full"
    else:
        raise PythSolanaSourceError("unsupported Pyth verification-level variant")

    required = offset + 32 + 8 + 8 + 4 + 8 + 8 + 8 + 8 + 8
    if len(data) < required:
        raise PythSolanaSourceError("Pyth PriceUpdateV2 payload is truncated")

    feed_id = data[offset : offset + 32].hex()
    offset += 32
    price = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    conf = struct.unpack_from("<Q", data, offset)[0]
    offset += 8
    exponent = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    publish_time = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    prev_publish_time = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    ema_price = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    ema_conf = struct.unpack_from("<Q", data, offset)[0]
    offset += 8
    posted_slot = struct.unpack_from("<Q", data, offset)[0]

    return {
        "write_authority_bytes": write_authority,
        "verification_level": verification_level,
        "verification_num_signatures": num_signatures,
        "feed_id": feed_id,
        "price_raw": price,
        "conf_raw": conf,
        "exponent": exponent,
        "publish_time": publish_time,
        "prev_publish_time": prev_publish_time,
        "ema_price_raw": ema_price,
        "ema_conf_raw": ema_conf,
        "posted_slot": posted_slot,
    }


class PythSolanaPushProvider:
    """Exact-fixture read-only Pyth Core push-feed provider."""

    chain = CHAIN
    source = SOURCE

    def __init__(self, rpc_provider: Any) -> None:
        self._rpc = rpc_provider

    def get_price(self, mint: str) -> dict[str, Any]:
        if not isinstance(mint, str) or not mint.strip():
            raise PythSolanaSourceError("mint must be a non-empty string")
        mint = mint.strip()
        fixture = PYTH_SOLANA_FEED_FIXTURES.get(mint)
        if fixture is None:
            return {
                "chain": CHAIN,
                "source": SOURCE,
                "mint": mint,
                "price_available": False,
                "mapping_verified": False,
                "reason": "pyth_exact_mint_feed_mapping_unavailable",
                "current_price_promotable": False,
                "source_independence_verified": False,
            }

        get_account_data = getattr(self._rpc, "get_account_data", None)
        if not callable(get_account_data):
            raise PythSolanaSourceError(
                "Solana RPC provider does not support exact account-data reads"
            )
        try:
            account = get_account_data(fixture["account_address"])
        except (SolanaRPCError, SolanaRPCNotFound) as exc:
            raise PythSolanaSourceError(
                f"Pyth account read failed ({type(exc).__name__})"
            ) from None
        except Exception as exc:
            raise PythSolanaSourceError(
                f"Pyth account read failed ({type(exc).__name__})"
            ) from None

        if not isinstance(account, Mapping):
            raise PythSolanaSourceError("Solana account response must be a mapping")
        if account.get("chain") != CHAIN or account.get("source") != "solana_rpc":
            raise PythSolanaSourceError("Pyth account RPC provenance mismatch")
        if account.get("address") != fixture["account_address"]:
            raise PythSolanaSourceError("Pyth account address mismatch")
        if account.get("owner") != fixture["receiver_program_id"]:
            raise PythSolanaSourceError("Pyth account owner mismatch")
        if account.get("executable") is not False:
            raise PythSolanaSourceError("Pyth price feed account must be non-executable")
        data = account.get("data")
        if not isinstance(data, bytes):
            raise PythSolanaSourceError("Pyth account data bytes are unavailable")

        parsed = _parse_price_update_v2(data)
        if parsed["feed_id"] != fixture["feed_id"]:
            raise PythSolanaSourceError("Pyth feed ID mismatch")

        expected_write_authority = _base58_decode(fixture["account_address"])
        if len(expected_write_authority) != 32:
            raise PythSolanaSourceError("Pyth fixture account address is invalid")
        write_authority_verified = (
            parsed["write_authority_bytes"] == expected_write_authority
        )
        if not write_authority_verified:
            raise PythSolanaSourceError("Pyth push-feed write authority mismatch")

        publish_time = parsed["publish_time"]
        prev_publish_time = parsed["prev_publish_time"]
        if publish_time <= 0:
            raise PythSolanaSourceError("Pyth publish_time must be positive")
        if prev_publish_time > publish_time:
            raise PythSolanaSourceError(
                "Pyth prev_publish_time must not exceed publish_time"
            )

        full_verification = parsed["verification_level"] == "full"
        price_positive = parsed["price_raw"] > 0
        price_integrity_verified = bool(
            full_verification and write_authority_verified and price_positive
        )

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "version": VERSION,
            "mint": mint,
            "mapping_verified": True,
            "mapping_provenance": fixture["mapping_provenance"],
            "feed_alias": fixture["feed_alias"],
            "feed_id": parsed["feed_id"],
            "feed_id_verified": True,
            "account_address": fixture["account_address"],
            "account_owner": account.get("owner"),
            "account_owner_verified": True,
            "account_context_slot": account.get("context_slot"),
            "posted_slot": parsed["posted_slot"],
            "receiver_program_id": fixture["receiver_program_id"],
            "push_oracle_program_id": fixture["push_oracle_program_id"],
            "contract_generation": fixture["contract_generation"],
            "contract_provenance": fixture["contract_provenance"],
            "provider_feed_provenance": fixture["provider_feed_provenance"],
            "provider_source_commit": fixture["provider_source_commit"],
            "write_authority_matches_feed_account": write_authority_verified,
            "verification_level": parsed["verification_level"],
            "verification_num_signatures": parsed["verification_num_signatures"],
            "full_verification": full_verification,
            "price_available": price_positive,
            "price_raw": parsed["price_raw"],
            "conf_raw": parsed["conf_raw"],
            "exponent": parsed["exponent"],
            "price_usd": (
                _decimal_text(parsed["price_raw"], parsed["exponent"])
                if price_positive
                else None
            ),
            "confidence_usd": _decimal_text(
                parsed["conf_raw"], parsed["exponent"]
            ),
            "publish_time_unix": publish_time,
            "prev_publish_time_unix": prev_publish_time,
            "ema_price_raw": parsed["ema_price_raw"],
            "ema_conf_raw": parsed["ema_conf_raw"],
            "fact_time_verified": True,
            "price_integrity_verified": price_integrity_verified,
            "unit": fixture["unit"],
            "price_subject": fixture["price_subject"],
            "quote_symbol": fixture["quote_symbol"],
            "symbol_discovery_used": False,
            "hermes_used": False,
            "hermes_api_key_required": False,
            "current_price_promotable": False,
            "source_independence_verified": False,
            "execution_authorized": False,
            "warnings": [
                (
                    "Pyth documents this current Solana Core program/account path "
                    "as upgraded in place on 2026-08-26, while recommending new "
                    "integrations use the alternate upgraded program addresses."
                ),
                (
                    "A verified Pyth source observation does not establish "
                    "Jupiter/Pyth time identity, source independence, or CMIS "
                    "current-price promotion."
                ),
            ],
        }


__all__ = [
    "CHAIN",
    "PRICE_UPDATE_V2_DISCRIMINATOR",
    "PYTH_CORE_PUSH_ORACLE_PROGRAM_ID",
    "PYTH_CORE_RECEIVER_PROGRAM_ID",
    "PYTH_CORE_UPGRADED_PUSH_ORACLE_PROGRAM_ID",
    "PYTH_CORE_UPGRADED_RECEIVER_PROGRAM_ID",
    "PYTH_SOLANA_FEED_FIXTURES",
    "PythSolanaPushProvider",
    "PythSolanaSourceError",
    "SOURCE",
    "USDC_MINT",
    "USDC_USD_CURRENT_ACCOUNT",
    "USDC_USD_FEED_ID",
    "VERSION",
]
