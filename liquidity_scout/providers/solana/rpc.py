"""Read-only canonical Solana JSON-RPC provider primitives beneath CMIS.

This adapter intentionally exposes a small contract first: token supply, parsed
mint-account state, and largest token-account observations. It performs no
signing, transaction construction, or broadcast and does not treat the largest
accounts list as total holder coverage.
"""

from __future__ import annotations

from collections.abc import Mapping
import base64
import binascii
import os
from typing import Any, Callable

import requests

CHAIN = "solana"
SOURCE = "solana_rpc"
DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"
DEFAULT_COMMITMENT = "confirmed"
CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT = 20

# Canonical Solana token-program identities. These are checked together with
# the RPC jsonParsed program label before ``program_identity_verified`` may be
# true; an arbitrary account owner can never masquerade as a token mint.
SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
_PROGRAM_LABEL_BY_OWNER = {
    SPL_TOKEN_PROGRAM_ID: "spl-token",
    TOKEN_2022_PROGRAM_ID: "spl-token-2022",
}
_PROGRAM_KIND_BY_OWNER = {
    SPL_TOKEN_PROGRAM_ID: "legacy_spl_token",
    TOKEN_2022_PROGRAM_ID: "token_2022",
}


class SolanaRPCError(RuntimeError):
    """Raised when a read-only Solana RPC contract cannot be verified."""


class SolanaRPCNotFound(SolanaRPCError):
    """Raised when a requested canonical account does not exist."""


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise SolanaRPCError(f"{field} must be a non-empty string")
    text = value.strip()
    if not text:
        raise SolanaRPCError(f"{field} must be a non-empty string")
    return text


def _nonnegative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise SolanaRPCError(f"{field} must be a non-negative integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise SolanaRPCError(f"{field} must be a non-negative integer")
    if parsed < 0:
        raise SolanaRPCError(f"{field} must be a non-negative integer")
    return parsed


def _u8(value: object, *, field: str) -> int:
    parsed = _nonnegative_int(value, field=field)
    if parsed > 255:
        raise SolanaRPCError(f"{field} must fit in u8")
    return parsed


def _raw_amount(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SolanaRPCError(f"{field} must be an unsigned integer string")
    if not value.isdigit():
        raise SolanaRPCError(f"{field} must be an unsigned integer string")
    return value.lstrip("0") or "0"


def _context_slot(result: Mapping[str, Any]) -> int:
    context = result.get("context")
    if not isinstance(context, Mapping):
        raise SolanaRPCError("RPC result.context must be an object")
    return _nonnegative_int(context.get("slot"), field="RPC context slot")


def _extension_names(info: Mapping[str, Any]) -> list[str]:
    extensions = info.get("extensions")
    if not isinstance(extensions, list):
        return []
    names: list[str] = []
    for extension in extensions:
        if isinstance(extension, Mapping):
            name = extension.get("extension") or extension.get("type")
        else:
            name = extension
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return names


def _verified_program_identity(owner_program_id: str, parsed_program: str) -> str:
    expected_label = _PROGRAM_LABEL_BY_OWNER.get(owner_program_id)
    if expected_label is None:
        raise SolanaRPCError("mint account owner is not a supported Solana token program")
    if parsed_program != expected_label:
        raise SolanaRPCError("mint owner program and jsonParsed program label do not match")
    return _PROGRAM_KIND_BY_OWNER[owner_program_id]


class SolanaRPCProvider:
    """Small, read-only Solana RPC facade with fail-closed response parsing."""

    chain = CHAIN
    source = SOURCE

    def __init__(
        self,
        rpc_url: str | None = None,
        *,
        commitment: str = DEFAULT_COMMITMENT,
        timeout: int = 20,
        post: Callable[..., Any] = requests.post,
    ) -> None:
        configured_url = rpc_url if rpc_url is not None else os.getenv(
            "SOLANA_RPC_URL", DEFAULT_RPC_URL
        )
        self._rpc_url = _text(configured_url, field="Solana RPC URL")
        self.commitment = _text(commitment, field="Solana RPC commitment")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        self.timeout = timeout
        self._post = post
        self._request_id = 0

    def _request_result(self, method: str, params: list[Any]) -> Any:
        method = _text(method, field="RPC method")
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        transport_error_type: str | None = None
        try:
            response = self._post(
                self._rpc_url,
                json=payload,
                headers={"content-type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except SolanaRPCError:
            raise
        except Exception as exc:
            # Capture only the exception class while inside the handler. The new
            # public exception is raised after the handler exits, so it carries
            # neither a chained cause nor a suppressed-but-inspectable transport
            # exception that could contain a credential-bearing RPC URL.
            transport_error_type = type(exc).__name__
            body = None

        if transport_error_type is not None:
            raise SolanaRPCError(
                f"{method} transport failed ({transport_error_type})"
            ) from None

        if not isinstance(body, Mapping):
            raise SolanaRPCError(f"{method} returned a non-object JSON-RPC response")
        if body.get("error") is not None:
            error = body.get("error")
            code = error.get("code") if isinstance(error, Mapping) else None
            raise SolanaRPCError(f"{method} returned JSON-RPC error code {code!r}")
        if "result" not in body:
            raise SolanaRPCError(f"{method} returned a malformed result")
        return body.get("result")

    def _request(self, method: str, params: list[Any]) -> Mapping[str, Any]:
        result = self._request_result(method, params)
        if not isinstance(result, Mapping):
            raise SolanaRPCError(f"{method} returned a malformed result")
        return result

    def get_account_data(self, address: str) -> dict[str, Any]:
        """Return one exact account's base64-decoded bytes with RPC provenance."""

        address = _text(address, field="account address")
        result = self._request(
            "getAccountInfo",
            [
                address,
                {
                    "commitment": self.commitment,
                    "encoding": "base64",
                },
            ],
        )
        slot = _context_slot(result)
        value = result.get("value")
        if value is None:
            raise SolanaRPCNotFound("Solana account not found")
        if not isinstance(value, Mapping):
            raise SolanaRPCError("getAccountInfo result.value must be an object")

        owner = _text(value.get("owner"), field="account owner")
        executable = value.get("executable")
        if not isinstance(executable, bool):
            raise SolanaRPCError("account executable must be boolean")
        lamports = _nonnegative_int(value.get("lamports"), field="account lamports")

        data_field = value.get("data")
        if (
            not isinstance(data_field, list)
            or len(data_field) != 2
            or data_field[1] != "base64"
            or not isinstance(data_field[0], str)
        ):
            raise SolanaRPCError("account data must be [base64, 'base64']")
        try:
            data = base64.b64decode(data_field[0], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SolanaRPCError("account data is invalid base64") from exc

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "method": "getAccountInfo(base64)",
            "address": address,
            "context_slot": slot,
            "owner": owner,
            "executable": executable,
            "lamports": lamports,
            "data": data,
            "data_length": len(data),
            "commitment": self.commitment,
        }

    def get_block_time(self, block_id: int) -> dict[str, Any]:
        """Resolve one Solana slot/block reference to estimated Unix production time."""

        block_id = _nonnegative_int(block_id, field="block id")
        result = self._request_result("getBlockTime", [block_id])
        if result is None:
            return {
                "chain": CHAIN,
                "source": SOURCE,
                "method": "getBlockTime",
                "block_id": block_id,
                "block_time_available": False,
                "block_time_unix": None,
                "block_time_verified": False,
                "finality_verified": False,
            }
        block_time = _nonnegative_int(result, field="block time")
        return {
            "chain": CHAIN,
            "source": SOURCE,
            "method": "getBlockTime",
            "block_id": block_id,
            "block_time_available": True,
            "block_time_unix": block_time,
            "block_time_verified": True,
            "finality_verified": False,
        }

    def get_slot(self) -> dict[str, Any]:
        """Return the current slot at this provider's explicit commitment."""

        result = self._request_result(
            "getSlot",
            [{"commitment": self.commitment}],
        )
        slot = _nonnegative_int(result, field="current slot")
        return {
            "chain": CHAIN,
            "source": SOURCE,
            "method": "getSlot",
            "slot": slot,
            "commitment": self.commitment,
            "slot_verified": True,
        }

    def get_token_supply(self, mint: str) -> dict[str, Any]:
        """Return canonical total token supply from ``getTokenSupply``."""

        mint = _text(mint, field="mint")
        result = self._request(
            "getTokenSupply",
            [mint, {"commitment": self.commitment}],
        )
        slot = _context_slot(result)
        value = result.get("value")
        if not isinstance(value, Mapping):
            raise SolanaRPCError("getTokenSupply result.value must be an object")
        amount = _raw_amount(value.get("amount"), field="token supply amount")
        decimals = _u8(value.get("decimals"), field="token decimals")
        ui_amount_string = value.get("uiAmountString")
        if ui_amount_string is not None and not isinstance(ui_amount_string, str):
            raise SolanaRPCError("uiAmountString must be a string or null")

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "method": "getTokenSupply",
            "mint": mint,
            "context_slot": slot,
            "amount_raw": amount,
            "decimals": decimals,
            "ui_amount_string": ui_amount_string,
            "supply_verified": True,
            "coverage": "total_token_supply",
        }

    def get_mint_account(self, mint: str) -> dict[str, Any]:
        """Return verified parsed mint program/authority state from ``getAccountInfo``."""

        mint = _text(mint, field="mint")
        result = self._request(
            "getAccountInfo",
            [
                mint,
                {
                    "encoding": "jsonParsed",
                    "commitment": self.commitment,
                },
            ],
        )
        slot = _context_slot(result)
        value = result.get("value")
        if value is None:
            raise SolanaRPCNotFound("getAccountInfo returned no account for the requested mint")
        if not isinstance(value, Mapping):
            raise SolanaRPCError("getAccountInfo result.value must be an object or null")

        owner_program_id = _text(value.get("owner"), field="mint owner program id")
        data = value.get("data")
        if not isinstance(data, Mapping):
            raise SolanaRPCError("parsed mint account data must be an object")
        parsed_program = _text(data.get("program"), field="parsed token program")
        program_kind = _verified_program_identity(owner_program_id, parsed_program)

        parsed = data.get("parsed")
        if not isinstance(parsed, Mapping) or parsed.get("type") != "mint":
            raise SolanaRPCError("getAccountInfo did not return parsed mint data")
        info = parsed.get("info")
        if not isinstance(info, Mapping):
            raise SolanaRPCError("parsed mint info must be an object")

        supply = _raw_amount(info.get("supply"), field="mint supply")
        decimals = _u8(info.get("decimals"), field="mint decimals")
        mint_authority = info.get("mintAuthority")
        freeze_authority = info.get("freezeAuthority")
        if mint_authority is not None and not isinstance(mint_authority, str):
            raise SolanaRPCError("mintAuthority must be a string or null")
        if freeze_authority is not None and not isinstance(freeze_authority, str):
            raise SolanaRPCError("freezeAuthority must be a string or null")

        initialized = info.get("isInitialized")
        if not isinstance(initialized, bool):
            raise SolanaRPCError("isInitialized must be present and boolean")
        if initialized is not True:
            raise SolanaRPCError("mint account is not initialized")

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "method": "getAccountInfo(jsonParsed)",
            "mint": mint,
            "context_slot": slot,
            "owner_program_id": owner_program_id,
            "parsed_program": parsed_program,
            "program_kind": program_kind,
            "program_identity_verified": True,
            "amount_raw": supply,
            "decimals": decimals,
            "mint_authority": mint_authority,
            "freeze_authority": freeze_authority,
            "is_initialized": initialized,
            "extension_names": _extension_names(info),
            "mint_state_verified": True,
        }

    def get_token_largest_accounts(self, mint: str) -> dict[str, Any]:
        """Return canonical top token accounts without mislabeling holders.

        Solana's canonical RPC contract describes the method as the top 20 token
        accounts. Some infrastructure providers return a larger provider-specific
        extension. CMIS validates ordering, preserves the raw provider row count,
        and normalizes the public account list back to the canonical top-20 scope.
        """

        mint = _text(mint, field="mint")
        result = self._request(
            "getTokenLargestAccounts",
            [mint, {"commitment": self.commitment}],
        )
        slot = _context_slot(result)
        value = result.get("value")
        if not isinstance(value, list):
            raise SolanaRPCError("getTokenLargestAccounts result.value must be a list")

        provider_accounts: list[dict[str, Any]] = []
        previous_amount: int | None = None
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise SolanaRPCError(
                    f"largest token account at index {index} must be an object"
                )
            address = _text(item.get("address"), field="token account address")
            amount = _raw_amount(item.get("amount"), field="token account amount")
            amount_int = int(amount)
            if previous_amount is not None and amount_int > previous_amount:
                raise SolanaRPCError(
                    "getTokenLargestAccounts accounts must be ordered by non-increasing raw amount"
                )
            previous_amount = amount_int
            decimals = _u8(item.get("decimals"), field="token decimals")
            ui_amount_string = item.get("uiAmountString")
            if ui_amount_string is not None and not isinstance(ui_amount_string, str):
                raise SolanaRPCError("uiAmountString must be a string or null")
            provider_accounts.append(
                {
                    "address": address,
                    "amount_raw": amount,
                    "decimals": decimals,
                    "ui_amount_string": ui_amount_string,
                }
            )

        provider_account_count = len(provider_accounts)
        accounts = provider_accounts[:CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT]
        provider_extended = provider_account_count > CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT
        warning = (
            "getTokenLargestAccounts is concentration evidence only and does not "
            "establish total holder, wallet, or beneficial-owner count."
        )
        if provider_extended:
            warning += (
                " The RPC provider returned more rows than the canonical Solana "
                "top-20 contract; CMIS preserved the provider row count and normalized "
                "the account list to the canonical top-20 scope."
            )

        return {
            "chain": CHAIN,
            "source": SOURCE,
            "method": "getTokenLargestAccounts",
            "mint": mint,
            "context_slot": slot,
            "accounts": accounts,
            "account_count_observed": len(accounts),
            "provider_account_count_returned": provider_account_count,
            "canonical_account_limit": CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT,
            "provider_extended_result_truncated": provider_extended,
            "counted_entity": "token_accounts",
            "coverage": "largest_token_accounts_only",
            "total_holder_count_verified": False,
            "warning": warning,
        }


__all__ = [
    "CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT",
    "CHAIN",
    "DEFAULT_RPC_URL",
    "SOURCE",
    "SPL_TOKEN_PROGRAM_ID",
    "TOKEN_2022_PROGRAM_ID",
    "SolanaRPCError",
    "SolanaRPCNotFound",
    "SolanaRPCProvider",
]
