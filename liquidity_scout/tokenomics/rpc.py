"""Deterministic X1 tokenomics RPC primitives.

This module exposes verified current token-supply and mint-authority facts from
X1 RPC. It does not infer circulating supply, market cap, token safety, burns,
mints, or net issuance.
"""

from decimal import Decimal, InvalidOperation
import time

import requests


DEFAULT_X1_RPC_URL = "https://rpc.mainnet.x1.xyz"


class X1RPCError(RuntimeError):
    """Raised when a verified X1 RPC request cannot be completed."""


def _text(value):
    return str(value or "").strip()


def _decimals(value):
    if value is None or isinstance(value, bool):
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed < 0:
        return None

    return parsed


def _token_amount(raw_supply, decimals):
    raw_supply = _text(raw_supply)
    decimals = _decimals(decimals)

    if not raw_supply or decimals is None:
        return None

    try:
        raw = Decimal(raw_supply)
    except (InvalidOperation, ValueError):
        return None

    if raw != raw.to_integral_value() or raw < 0:
        return None

    return str(raw / (Decimal(10) ** decimals))


def rpc_request(
    method,
    params,
    *,
    rpc_url=DEFAULT_X1_RPC_URL,
    retries=4,
    timeout=15,
    post=requests.post,
    sleep=time.sleep,
):
    """Perform an X1 JSON-RPC request with deterministic retry/backoff.

    The caller decides whether a final RPC failure should propagate or be
    converted to an unavailable value at a compatibility boundary.
    """
    method = _text(method)
    rpc_url = _text(rpc_url)

    if not method:
        raise ValueError("X1 RPC method is required.")
    if not rpc_url:
        raise ValueError("X1 RPC URL is required.")
    if retries < 1:
        raise ValueError("X1 RPC retries must be at least 1.")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    last_error = None

    for attempt in range(retries):
        try:
            response = post(
                rpc_url,
                json=payload,
                timeout=timeout,
            )

            status_code = getattr(response, "status_code", None)
            if status_code == 429 or (
                isinstance(status_code, int) and status_code >= 500
            ):
                raise X1RPCError(f"X1 RPC HTTP {status_code}")

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise X1RPCError("X1 RPC returned a non-object response.")

            if data.get("error"):
                raise X1RPCError(str(data["error"]))

            return data.get("result")

        except Exception as exc:
            last_error = exc

            if attempt == retries - 1:
                break

            sleep(0.75 * (2 ** attempt))

    raise X1RPCError(
        f"X1 RPC {method} failed after {retries} attempts: {last_error}"
    ) from last_error


def parse_token_supply_result(result):
    """Parse getTokenSupply while preserving missing-data uncertainty."""
    value = (result or {}).get("value")
    if not isinstance(value, dict):
        return None

    raw_supply = _text(value.get("amount"))
    decimals = _decimals(value.get("decimals"))
    total_supply = _token_amount(raw_supply, decimals)
    ui_amount_string = _text(value.get("uiAmountString")) or None

    return {
        "raw_supply": raw_supply or None,
        "decimals": decimals,
        "total_supply": total_supply,
        "ui_amount_string": ui_amount_string,
        "supply_verified": total_supply is not None,
        "source": "X1 RPC getTokenSupply",
    }


def parse_mint_account_result(result):
    """Parse jsonParsed mint account data with explicit verification flags."""
    value = (result or {}).get("value")
    if not isinstance(value, dict):
        return None

    data = value.get("data")
    if not isinstance(data, dict):
        return None

    parsed = data.get("parsed")
    if not isinstance(parsed, dict):
        return None

    info = parsed.get("info")
    if not isinstance(info, dict):
        return None

    raw_supply = _text(info.get("supply"))
    decimals = _decimals(info.get("decimals"))
    total_supply = _token_amount(raw_supply, decimals)

    mint_authority_verified = "mintAuthority" in info
    freeze_authority_verified = "freezeAuthority" in info

    return {
        "mint_authority": (
            info.get("mintAuthority") if mint_authority_verified else None
        ),
        "mint_authority_verified": mint_authority_verified,
        "freeze_authority": (
            info.get("freezeAuthority") if freeze_authority_verified else None
        ),
        "freeze_authority_verified": freeze_authority_verified,
        "raw_supply": raw_supply or None,
        "decimals": decimals,
        "total_supply": total_supply,
        "supply_verified": total_supply is not None,
        "source": "X1 RPC getAccountInfo(jsonParsed)",
    }


def get_token_supply(
    mint,
    *,
    rpc_url=DEFAULT_X1_RPC_URL,
    retries=4,
    timeout=15,
    post=requests.post,
    sleep=time.sleep,
):
    """Return the current verified total-supply record for an X1 mint."""
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")

    result = rpc_request(
        "getTokenSupply",
        [mint],
        rpc_url=rpc_url,
        retries=retries,
        timeout=timeout,
        post=post,
        sleep=sleep,
    )

    return parse_token_supply_result(result)


def get_mint_info(
    mint,
    *,
    rpc_url=DEFAULT_X1_RPC_URL,
    retries=4,
    timeout=15,
    post=requests.post,
    sleep=time.sleep,
):
    """Return verified current supply and authority fields for an X1 mint."""
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")

    result = rpc_request(
        "getAccountInfo",
        [
            mint,
            {"encoding": "jsonParsed"},
        ],
        rpc_url=rpc_url,
        retries=retries,
        timeout=timeout,
        post=post,
        sleep=sleep,
    )

    return parse_mint_account_result(result)
