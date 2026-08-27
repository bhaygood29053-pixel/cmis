"""Read-only X1 Metaplex Token Metadata evidence.

This module is a bounded provider foundation for CMIS issue #279. It verifies
only descriptive token metadata for an exact X1 mint. It does not promote
metadata into risk, Proof Score, token authority, market, or execution truth.

The first tracer-bullet deliberately uses a tightly filtered
``getProgramAccounts`` read keyed by the canonical Metaplex metadata layout:
one discriminator byte, 32-byte update authority, then the 32-byte mint at
offset 33. A result is accepted only when exactly one program-owned metadata
account decodes and its embedded mint exactly matches the requested mint.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, rpc_request


VERSION = "0.1.0"
CHAIN = "x1"
SOURCE = "X1 RPC / Metaplex Token Metadata"
TOKEN_METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
METADATA_ACCOUNT_KEY = 4
METADATA_MINT_OFFSET = 33
MAX_NAME_LENGTH = 32
MAX_SYMBOL_LENGTH = 10
MAX_URI_LENGTH = 200
MAX_CREATOR_COUNT = 5

TOKEN_STANDARD_NAMES = {
    0: "NonFungible",
    1: "FungibleAsset",
    2: "Fungible",
    3: "NonFungibleEdition",
    4: "ProgrammableNonFungible",
    5: "ProgrammableNonFungibleEdition",
}

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _base58_encode(raw: bytes) -> str:
    if not isinstance(raw, bytes):
        raise TypeError("raw public key bytes are required")

    leading_zeroes = 0
    for byte in raw:
        if byte != 0:
            break
        leading_zeroes += 1

    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded

    return ("1" * leading_zeroes) + encoded


class _Cursor:
    def __init__(self, data: bytes):
        if not isinstance(data, bytes):
            raise TypeError("metadata data must be bytes")
        self.data = data
        self.offset = 0

    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read(self, size: int) -> bytes:
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("read size must be a non-negative integer")
        end = self.offset + size
        if end > len(self.data):
            raise ValueError("metadata account is truncated")
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return int.from_bytes(self.read(2), "little")

    def u32(self) -> int:
        return int.from_bytes(self.read(4), "little")

    def boolean(self, field: str) -> bool:
        value = self.u8()
        if value not in (0, 1):
            raise ValueError(f"{field} is not a valid Borsh boolean")
        return bool(value)

    def option_u8(self, field: str) -> int | None:
        tag = self.u8()
        if tag == 0:
            return None
        if tag == 1:
            return self.u8()
        raise ValueError(f"{field} has an invalid Borsh option tag")

    def string(self, field: str, maximum: int) -> str:
        length = self.u32()
        if length > maximum:
            raise ValueError(f"{field} exceeds the accepted Token Metadata limit")
        raw = self.read(length)
        try:
            return raw.decode("utf-8").rstrip("\x00")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{field} is not valid UTF-8") from exc


def _skip_creators(cursor: _Cursor) -> None:
    tag = cursor.u8()
    if tag == 0:
        return
    if tag != 1:
        raise ValueError("creators has an invalid Borsh option tag")

    count = cursor.u32()
    if count > MAX_CREATOR_COUNT:
        raise ValueError("creator count exceeds the accepted Token Metadata limit")

    # Creator = 32-byte address + bool verified + u8 share.
    for _ in range(count):
        cursor.read(32)
        cursor.boolean("creator.verified")
        cursor.u8()


def _optional_token_standard(cursor: _Cursor) -> str | None:
    if cursor.remaining() == 0:
        return None

    tag = cursor.u8()
    if tag == 0:
        return None
    if tag != 1:
        raise ValueError("token_standard has an invalid Borsh option tag")
    if cursor.remaining() < 1:
        raise ValueError("token_standard is truncated")

    value = cursor.u8()
    standard = TOKEN_STANDARD_NAMES.get(value)
    if standard is None:
        raise ValueError("unsupported Token Metadata token standard")
    return standard


def parse_metadata_bytes(data: bytes, *, expected_mint: str | None = None) -> dict[str, Any]:
    """Decode the minimum accepted Metaplex Metadata fields.

    The parser intentionally stops after token-standard evidence. Later optional
    collection/use/programmatic fields are outside the first tracer-bullet.
    """

    cursor = _Cursor(data)

    key = cursor.u8()
    if key != METADATA_ACCOUNT_KEY:
        raise ValueError("account discriminator is not MetadataV1")

    update_authority = _base58_encode(cursor.read(32))
    mint = _base58_encode(cursor.read(32))

    name = cursor.string("name", MAX_NAME_LENGTH)
    symbol = cursor.string("symbol", MAX_SYMBOL_LENGTH)
    uri = cursor.string("uri", MAX_URI_LENGTH)
    seller_fee_basis_points = cursor.u16()
    _skip_creators(cursor)

    primary_sale_happened = cursor.boolean("primary_sale_happened")
    is_mutable = cursor.boolean("is_mutable")

    edition_nonce = None
    if cursor.remaining() > 0:
        edition_nonce = cursor.option_u8("edition_nonce")

    token_standard = _optional_token_standard(cursor)

    expected_mint_text = _text(expected_mint)
    if expected_mint_text and mint != expected_mint_text:
        raise ValueError("decoded metadata mint does not match the requested mint")

    return {
        "key": "MetadataV1",
        "mint": mint,
        "name": name,
        "symbol": symbol,
        "uri": uri,
        "metadata_update_authority": update_authority,
        "is_mutable": is_mutable,
        "primary_sale_happened": primary_sale_happened,
        "seller_fee_basis_points": seller_fee_basis_points,
        "edition_nonce": edition_nonce,
        "token_standard": token_standard,
        "descriptive_identity_only": True,
        "spl_mint_authority_verified": False,
        "spl_freeze_authority_verified": False,
    }


def _decode_base64_account_data(account: Mapping[str, Any]) -> bytes:
    data = account.get("data")
    if (
        not isinstance(data, Sequence)
        or isinstance(data, (str, bytes))
        or len(data) < 2
        or data[1] != "base64"
        or not isinstance(data[0], str)
    ):
        raise ValueError("metadata account data is not canonical base64 RPC data")

    try:
        return base64.b64decode(data[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("metadata account base64 data is invalid") from exc


def parse_token_metadata_program_account_result(
    result: Any,
    *,
    program_id: str = TOKEN_METADATA_PROGRAM_ID,
) -> dict[str, Any]:
    """Parse one Token Metadata program-account ``getAccountInfo`` result."""

    program_id = _text(program_id)
    if not program_id:
        raise ValueError("program_id is required")
    if not isinstance(result, Mapping) or "value" not in result:
        raise ValueError("getAccountInfo returned no usable Token Metadata program result")

    context = result.get("context")
    context_slot = (
        _nonnegative_int(context.get("slot"))
        if isinstance(context, Mapping)
        else None
    )
    value = result.get("value")
    if value is None:
        return {
            "program_id": program_id,
            "program_exists": False,
            "executable": None,
            "loader_owner": None,
            "context_slot": context_slot,
            "program_executable_verified": False,
            "source": SOURCE,
        }

    if not isinstance(value, Mapping):
        raise ValueError("Token Metadata program account is malformed")

    executable = value.get("executable")
    if not isinstance(executable, bool):
        raise ValueError("Token Metadata program executable flag is malformed")

    return {
        "program_id": program_id,
        "program_exists": True,
        "executable": executable,
        "loader_owner": _text(value.get("owner")),
        "context_slot": context_slot,
        "program_executable_verified": executable is True,
        "source": SOURCE,
    }


def parse_metadata_accounts_result(
    result: Any,
    *,
    mint: str,
    program_id: str = TOKEN_METADATA_PROGRAM_ID,
) -> dict[str, Any]:
    """Parse an exact-mint filtered ``getProgramAccounts`` result."""

    mint = _text(mint)
    program_id = _text(program_id)
    if not mint:
        raise ValueError("mint is required")
    if not program_id:
        raise ValueError("program_id is required")

    rows = result
    context_slot = None
    if isinstance(result, Mapping) and "value" in result:
        rows = result.get("value")
        context = result.get("context")
        if isinstance(context, Mapping):
            context_slot = _nonnegative_int(context.get("slot"))

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("getProgramAccounts returned no usable metadata account list")

    if len(rows) == 0:
        return {
            "mint": mint,
            "metadata_found": False,
            "metadata_account": None,
            "context_slot": context_slot,
            "identity_verified": False,
            "program_id": program_id,
            "source": SOURCE,
        }

    if len(rows) != 1:
        raise ValueError("exact mint resolved to multiple Token Metadata accounts")

    row = rows[0]
    if not isinstance(row, Mapping):
        raise ValueError("Token Metadata account row is malformed")

    pubkey = _text(row.get("pubkey"))
    account = row.get("account")
    if not pubkey or not isinstance(account, Mapping):
        raise ValueError("Token Metadata account identity is malformed")

    owner = _text(account.get("owner"))
    if owner != program_id:
        raise ValueError("metadata account owner does not match Token Metadata program")

    executable = account.get("executable")
    if executable is not False:
        raise ValueError("metadata state account executable flag is invalid")

    decoded = parse_metadata_bytes(
        _decode_base64_account_data(account),
        expected_mint=mint,
    )

    return {
        "mint": mint,
        "metadata_found": True,
        "metadata_account": pubkey,
        "account_owner": owner,
        "account_executable": False,
        "context_slot": context_slot,
        "identity_verified": True,
        "program_id": program_id,
        "source": SOURCE,
        **decoded,
    }


def get_token_metadata_program_status(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    program_id: str = TOKEN_METADATA_PROGRAM_ID,
    commitment: str = "confirmed",
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    program_id = _text(program_id)
    rpc_url = _text(rpc_url)
    commitment = _text(commitment)
    if not program_id:
        raise ValueError("program_id is required")
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if not commitment:
        raise ValueError("commitment is required")

    result = requester(
        "getAccountInfo",
        [program_id, {"encoding": "base64", "commitment": commitment}],
        rpc_url=rpc_url,
    )
    parsed = parse_token_metadata_program_account_result(
        result,
        program_id=program_id,
    )
    parsed.update(
        {
            "version": VERSION,
            "chain": CHAIN,
            "rpc_url": rpc_url,
            "rpc_method": "getAccountInfo",
            "commitment": commitment,
        }
    )
    return parsed


def get_token_metadata_for_mint(
    mint: str,
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    program_id: str = TOKEN_METADATA_PROGRAM_ID,
    commitment: str = "confirmed",
    requester: Callable[..., Any] = rpc_request,
) -> dict[str, Any]:
    """Fetch bounded Token Metadata identity evidence for one exact X1 mint."""

    mint = _text(mint)
    program_id = _text(program_id)
    rpc_url = _text(rpc_url)
    commitment = _text(commitment)
    if not mint:
        raise ValueError("mint is required")
    if not program_id:
        raise ValueError("program_id is required")
    if not rpc_url:
        raise ValueError("rpc_url is required")
    if not commitment:
        raise ValueError("commitment is required")

    program = get_token_metadata_program_status(
        rpc_url=rpc_url,
        program_id=program_id,
        commitment=commitment,
        requester=requester,
    )
    if program.get("program_executable_verified") is not True:
        raise ValueError("Token Metadata program is missing or non-executable")

    config = {
        "encoding": "base64",
        "commitment": commitment,
        "withContext": True,
        "filters": [
            {
                "memcmp": {
                    "offset": METADATA_MINT_OFFSET,
                    "bytes": mint,
                }
            }
        ],
    }
    result = requester(
        "getProgramAccounts",
        [program_id, config],
        rpc_url=rpc_url,
    )
    metadata = parse_metadata_accounts_result(
        result,
        mint=mint,
        program_id=program_id,
    )

    return {
        "service": "x1_token_metadata_identity_evidence",
        "version": VERSION,
        "chain": CHAIN,
        "source": SOURCE,
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
        "program": program,
        "metadata": metadata,
        "identity_verified": bool(
            program.get("program_executable_verified") is True
            and metadata.get("identity_verified") is True
        ),
    }


class X1TokenMetadataProvider:
    """Read-only facade for bounded X1 Token Metadata evidence."""

    chain = CHAIN
    source = SOURCE
    program_id = TOKEN_METADATA_PROGRAM_ID

    def __init__(
        self,
        *,
        rpc_url: str = DEFAULT_X1_RPC_URL,
        commitment: str = "confirmed",
        requester: Callable[..., Any] = rpc_request,
    ):
        self.rpc_url = _text(rpc_url)
        self.commitment = _text(commitment)
        self.requester = requester
        if not self.rpc_url:
            raise ValueError("rpc_url is required")
        if not self.commitment:
            raise ValueError("commitment is required")

    def program_status(self) -> dict[str, Any]:
        return get_token_metadata_program_status(
            rpc_url=self.rpc_url,
            program_id=self.program_id,
            commitment=self.commitment,
            requester=self.requester,
        )

    def get_metadata(self, mint: str) -> dict[str, Any]:
        return get_token_metadata_for_mint(
            mint,
            rpc_url=self.rpc_url,
            program_id=self.program_id,
            commitment=self.commitment,
            requester=self.requester,
        )


__all__ = [
    "CHAIN",
    "METADATA_MINT_OFFSET",
    "SOURCE",
    "TOKEN_METADATA_PROGRAM_ID",
    "TOKEN_STANDARD_NAMES",
    "VERSION",
    "X1TokenMetadataProvider",
    "get_token_metadata_for_mint",
    "get_token_metadata_program_status",
    "parse_metadata_accounts_result",
    "parse_metadata_bytes",
    "parse_token_metadata_program_account_result",
]
