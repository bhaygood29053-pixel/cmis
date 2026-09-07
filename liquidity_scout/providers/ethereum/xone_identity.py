"""Narrow Ethereum mainnet identity verifier for the XONE ERC-20.

This module is an explicit exception-gated provider for Issue #580 only. It is
not a general Ethereum capability. The verifier proves the exact contract
creation and current ERC-20 identity fields that Ethereum JSON-RPC can prove.

Identity verification does not prove any XONE -> XNT conversion, burn,
snapshot, vesting, claim, allocation, issuance, or cross-chain correlation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import time
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests


CONTRACT_VERSION = "ethereum_xone_identity/v1"
CHAIN = "ethereum"
NETWORK = "ethereum-mainnet"
CHAIN_ID = "0x1"

XONE_CONTRACT = "0x4dcda2274899d9bba3bb6f5a852c107dd6e4fe1c"
XONE_CREATION_TX = "0x6d2f0492d54b56044f03a3de5ad1889b6fe115914e9bcfc58e28950ddda6eea5"
XONE_DEPLOYER = "0xc73fc08c931efe3fce850c09278472e8a81c2e05"
XONE_NAME = "XONE"
XONE_SYMBOL = "XONE"
XONE_DECIMALS = 18

NAME_SELECTOR = "0x06fdde03"
SYMBOL_SELECTOR = "0x95d89b41"
DECIMALS_SELECTOR = "0x313ce567"

DEFAULT_RPC_URLS = (
    "https://ethereum-rpc.publicnode.com",
    "https://eth.drpc.org",
    "https://public.1rpc.io/eth",
)


class EthereumXoneIdentityError(RuntimeError):
    """Raised when XONE identity cannot be verified safely."""


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _address(value: Any, *, field: str) -> str:
    text = _text(value)
    if text is None:
        raise EthereumXoneIdentityError(f"{field} is missing")
    lowered = text.casefold()
    if len(lowered) != 42 or not lowered.startswith("0x"):
        raise EthereumXoneIdentityError(f"{field} is not a 20-byte address")
    try:
        int(lowered[2:], 16)
    except ValueError as exc:
        raise EthereumXoneIdentityError(f"{field} is not hexadecimal") from exc
    return lowered


def _tx_hash(value: Any, *, field: str) -> str:
    text = _text(value)
    if text is None:
        raise EthereumXoneIdentityError(f"{field} is missing")
    lowered = text.casefold()
    if len(lowered) != 66 or not lowered.startswith("0x"):
        raise EthereumXoneIdentityError(f"{field} is not a 32-byte hash")
    try:
        int(lowered[2:], 16)
    except ValueError as exc:
        raise EthereumXoneIdentityError(f"{field} is not hexadecimal") from exc
    return lowered


def _hex_bytes(value: Any, *, field: str, allow_empty: bool = False) -> bytes:
    text = _text(value)
    if text is None or not text.startswith("0x"):
        raise EthereumXoneIdentityError(f"{field} is not 0x-prefixed hex")
    payload = text[2:]
    if len(payload) % 2:
        raise EthereumXoneIdentityError(f"{field} has odd-length hex")
    if not payload and allow_empty:
        return b""
    if not payload:
        raise EthereumXoneIdentityError(f"{field} is empty")
    try:
        return bytes.fromhex(payload)
    except ValueError as exc:
        raise EthereumXoneIdentityError(f"{field} is malformed hex") from exc


def _decode_abi_string(value: Any, *, field: str) -> str:
    payload = _hex_bytes(value, field=field)
    if len(payload) < 64:
        raise EthereumXoneIdentityError(f"{field} ABI string is too short")
    offset = int.from_bytes(payload[:32], "big")
    if offset < 0 or offset + 32 > len(payload):
        raise EthereumXoneIdentityError(f"{field} ABI string offset is invalid")
    length = int.from_bytes(payload[offset : offset + 32], "big")
    start = offset + 32
    end = start + length
    if end > len(payload):
        raise EthereumXoneIdentityError(f"{field} ABI string length is invalid")
    try:
        return payload[start:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EthereumXoneIdentityError(f"{field} is not UTF-8") from exc


def _decode_abi_uint(value: Any, *, field: str) -> int:
    payload = _hex_bytes(value, field=field)
    if len(payload) != 32:
        raise EthereumXoneIdentityError(f"{field} ABI uint must be 32 bytes")
    return int.from_bytes(payload, "big")


def ethereum_rpc_request(
    method: str,
    params: Sequence[Any],
    *,
    rpc_url: str,
    timeout: int = 20,
    retries: int = 5,
    post=requests.post,
    sleep=time.sleep,
) -> Any:
    """Perform one Ethereum JSON-RPC request with bounded retry/backoff."""

    rpc_url = _text(rpc_url) or ""
    method = _text(method) or ""
    if not rpc_url:
        raise ValueError("rpc_url is required")
    parsed = urlparse(rpc_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("rpc_url must be an HTTPS URL")
    if not method:
        raise ValueError("method is required")
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 1:
        raise ValueError("retries must be a positive integer")

    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}
    last_error: Optional[BaseException] = None

    for attempt in range(retries):
        try:
            response = post(rpc_url, json=payload, timeout=timeout)
            status = getattr(response, "status_code", None)
            if status == 429 or (isinstance(status, int) and status >= 500):
                raise EthereumXoneIdentityError(f"Ethereum RPC HTTP {status}")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, Mapping):
                raise EthereumXoneIdentityError("Ethereum RPC returned non-object JSON")
            if data.get("error") is not None:
                raise EthereumXoneIdentityError(str(data["error"]))
            if "result" not in data:
                raise EthereumXoneIdentityError("Ethereum RPC response is missing result")
            return data["result"]
        except Exception as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            sleep(0.5 * (2 ** attempt))

    raise EthereumXoneIdentityError(
        f"Ethereum RPC {method} failed after {retries} attempts: {last_error}"
    ) from last_error


def _truth_state(*, identity_verified: bool) -> dict[str, Any]:
    return {
        "exact_ethereum_xone_identity_verified": identity_verified,
        "xone_xnt_conversion_verified": False,
        "xone_burn_verified": False,
        "xone_snapshot_or_eligibility_verified": False,
        "xnt_issuance_verified": False,
        "xnt_vesting_or_unlock_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "execution_authorized": False,
    }


def verify_xone_identity(
    *,
    rpc_call: Callable[[str, Sequence[Any]], Any],
    source_url: Optional[str] = None,
) -> dict[str, Any]:
    """Verify the exact Ethereum XONE identity from direct JSON-RPC facts."""

    chain_id = _text(rpc_call("eth_chainId", []))
    if chain_id is None or chain_id.casefold() != CHAIN_ID:
        raise EthereumXoneIdentityError(
            f"expected Ethereum mainnet chainId {CHAIN_ID}, got {chain_id!r}"
        )

    transaction = rpc_call("eth_getTransactionByHash", [XONE_CREATION_TX])
    if not isinstance(transaction, Mapping):
        raise EthereumXoneIdentityError("creation transaction was not returned")
    tx_hash = _tx_hash(transaction.get("hash"), field="creation transaction hash")
    if tx_hash != XONE_CREATION_TX:
        raise EthereumXoneIdentityError("creation transaction hash mismatch")
    deployer = _address(transaction.get("from"), field="creation transaction from")
    if deployer != XONE_DEPLOYER:
        raise EthereumXoneIdentityError("creation transaction deployer mismatch")
    if transaction.get("to") is not None:
        raise EthereumXoneIdentityError("candidate transaction is not contract creation")
    tx_block = _text(transaction.get("blockNumber"))
    if tx_block is None:
        raise EthereumXoneIdentityError("creation transaction is not mined")

    receipt = rpc_call("eth_getTransactionReceipt", [XONE_CREATION_TX])
    if not isinstance(receipt, Mapping):
        raise EthereumXoneIdentityError("creation receipt was not returned")
    receipt_tx_hash = _tx_hash(receipt.get("transactionHash"), field="receipt transaction hash")
    if receipt_tx_hash != XONE_CREATION_TX:
        raise EthereumXoneIdentityError("creation receipt transaction mismatch")
    receipt_address = _address(receipt.get("contractAddress"), field="receipt contractAddress")
    if receipt_address != XONE_CONTRACT:
        raise EthereumXoneIdentityError("creation receipt contract address mismatch")
    if _text(receipt.get("status")) != "0x1":
        raise EthereumXoneIdentityError("creation transaction did not succeed")
    receipt_block = _text(receipt.get("blockNumber"))
    if receipt_block is None or receipt_block.casefold() != tx_block.casefold():
        raise EthereumXoneIdentityError("creation transaction/receipt block mismatch")

    code_hex = rpc_call("eth_getCode", [XONE_CONTRACT, "finalized"])
    code = _hex_bytes(code_hex, field="runtime bytecode", allow_empty=True)
    if not code:
        raise EthereumXoneIdentityError("XONE contract has no runtime bytecode")

    call_base = {"to": XONE_CONTRACT}
    name = _decode_abi_string(
        rpc_call("eth_call", [{**call_base, "data": NAME_SELECTOR}, "finalized"]),
        field="name()",
    )
    symbol = _decode_abi_string(
        rpc_call("eth_call", [{**call_base, "data": SYMBOL_SELECTOR}, "finalized"]),
        field="symbol()",
    )
    decimals = _decode_abi_uint(
        rpc_call("eth_call", [{**call_base, "data": DECIMALS_SELECTOR}, "finalized"]),
        field="decimals()",
    )

    if name != XONE_NAME:
        raise EthereumXoneIdentityError(f"name() mismatch: {name!r}")
    if symbol != XONE_SYMBOL:
        raise EthereumXoneIdentityError(f"symbol() mismatch: {symbol!r}")
    if decimals != XONE_DECIMALS:
        raise EthereumXoneIdentityError(f"decimals() mismatch: {decimals!r}")

    result = {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "creation_transaction": XONE_CREATION_TX,
        "deployer": XONE_DEPLOYER,
        "creation_block": tx_block,
        "runtime_code_bytes": len(code),
        "runtime_code_sha256": sha256(code).hexdigest(),
        "erc20": {
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
        },
        "direct_chain_fields_verified": [
            "ethereum_mainnet_chain_id",
            "creation_transaction_hash",
            "creation_transaction_is_contract_creation",
            "creation_transaction_deployer",
            "creation_transaction_success",
            "creation_receipt_contract_address",
            "runtime_bytecode_presence",
            "erc20_name",
            "erc20_symbol",
            "erc20_decimals",
        ],
        "source_url": source_url,
        "read_only": True,
        **_truth_state(identity_verified=True),
    }
    return result


def corroborate_xone_identity_proofs(
    proofs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require two matching direct-RPC identity proofs from distinct transports."""

    if not isinstance(proofs, Sequence) or isinstance(proofs, (str, bytes, bytearray)):
        raise EthereumXoneIdentityError("proofs must be a sequence")
    if len(proofs) < 2:
        raise EthereumXoneIdentityError("at least two RPC proofs are required")

    normalized: list[Mapping[str, Any]] = []
    hosts: set[str] = set()
    for proof in proofs:
        if not isinstance(proof, Mapping):
            raise EthereumXoneIdentityError("each proof must be a mapping")
        if proof.get("exact_ethereum_xone_identity_verified") is not True:
            raise EthereumXoneIdentityError("all proofs must verify exact XONE identity")
        source_url = _text(proof.get("source_url"))
        if not source_url:
            raise EthereumXoneIdentityError("each proof requires source_url")
        host = (urlparse(source_url).hostname or "").casefold()
        if not host:
            raise EthereumXoneIdentityError("proof source_url is invalid")
        hosts.add(host)
        normalized.append(proof)

    if len(hosts) < 2:
        raise EthereumXoneIdentityError("two distinct RPC transport hosts are required")

    keys = (
        "chain_id",
        "contract_address",
        "creation_transaction",
        "deployer",
        "creation_block",
        "runtime_code_sha256",
    )
    baseline = normalized[0]
    for proof in normalized[1:]:
        for key in keys:
            if proof.get(key) != baseline.get(key):
                raise EthereumXoneIdentityError(f"RPC proofs disagree on {key}")
        if proof.get("erc20") != baseline.get("erc20"):
            raise EthereumXoneIdentityError("RPC proofs disagree on ERC-20 metadata")

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": CHAIN,
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "contract_address": XONE_CONTRACT,
        "creation_transaction": XONE_CREATION_TX,
        "deployer": XONE_DEPLOYER,
        "erc20": dict(baseline["erc20"]),
        "creation_block": baseline["creation_block"],
        "runtime_code_sha256": baseline["runtime_code_sha256"],
        "rpc_proof_count": len(normalized),
        "rpc_transport_hosts": sorted(hosts),
        "multi_rpc_corroborated": True,
        "transport_provider_diversity_verified": True,
        "rpc_backend_source_independence_verified": False,
        "same_chain_consensus_is_not_cross_source_semantic_independence": True,
        "read_only": True,
        **_truth_state(identity_verified=True),
    }


__all__ = [
    "CHAIN",
    "CHAIN_ID",
    "CONTRACT_VERSION",
    "DEFAULT_RPC_URLS",
    "EthereumXoneIdentityError",
    "NETWORK",
    "XONE_CONTRACT",
    "XONE_CREATION_TX",
    "XONE_DECIMALS",
    "XONE_DEPLOYER",
    "XONE_NAME",
    "XONE_SYMBOL",
    "corroborate_xone_identity_proofs",
    "ethereum_rpc_request",
    "verify_xone_identity",
]
