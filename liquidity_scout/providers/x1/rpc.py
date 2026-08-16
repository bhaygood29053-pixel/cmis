"""X1 RPC provider primitives for CMIS.

This module owns X1-specific JSON-RPC transport and token-account parsing
beneath CMIS. It reports verified current chain facts only; circulating supply,
market cap, risk, burn/mint aggregation, and CMIS response construction remain
in shared deterministic layers.
"""

import time

import requests


CHAIN = "x1"
DEFAULT_X1_RPC_URL = "https://rpc.mainnet.x1.xyz"
RPC_SOURCE = "X1 RPC"


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
    """Scale an RPC raw integer amount exactly, without float/Decimal rounding."""
    raw_supply = _text(raw_supply)
    decimals = _decimals(decimals)

    if not raw_supply or decimals is None or not raw_supply.isdigit():
        return None

    digits = raw_supply.lstrip("0") or "0"

    if decimals == 0:
        return digits

    digits = digits.rjust(decimals + 1, "0")
    whole = digits[:-decimals] or "0"
    fraction = digits[-decimals:].rstrip("0")

    if not fraction:
        return whole

    return f"{whole}.{fraction}"


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


def parse_token_account_result(result, *, account=None):
    """Parse jsonParsed SPL-style token-account identity evidence.

    The top-level account owner is the token program. The parsed ``info.owner``
    field is the token-account authority used by CMIS vault-family checks.
    Missing or malformed identity fields remain explicitly unverified.
    """
    if not isinstance(result, dict) or "value" not in result:
        return None

    source = "X1 RPC getAccountInfo(jsonParsed token account)"
    account_text = _text(account) or None
    value = result.get("value")

    if value is None:
        return {
            "account": account_text,
            "account_exists": False,
            "program_owner": None,
            "parsed_type": None,
            "mint": None,
            "token_authority": None,
            "raw_amount": None,
            "decimals": None,
            "ui_amount_string": None,
            "identity_verified": False,
            "source": source,
        }

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

    token_amount = info.get("tokenAmount")
    if not isinstance(token_amount, dict):
        token_amount = {}

    mint = _text(info.get("mint")) or None
    token_authority = _text(info.get("owner")) or None
    raw_amount = _text(token_amount.get("amount")) or None
    decimals = _decimals(token_amount.get("decimals"))
    ui_amount_string = _text(token_amount.get("uiAmountString")) or None
    program_owner = _text(value.get("owner")) or None
    parsed_type = _text(parsed.get("type")) or None

    identity_verified = bool(
        mint
        and token_authority
        and raw_amount is not None
        and decimals is not None
    )

    return {
        "account": account_text,
        "account_exists": True,
        "program_owner": program_owner,
        "parsed_type": parsed_type,
        "mint": mint,
        "token_authority": token_authority,
        "raw_amount": raw_amount,
        "decimals": decimals,
        "ui_amount_string": ui_amount_string,
        "identity_verified": identity_verified,
        "source": source,
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


def get_token_account_info(
    account,
    *,
    rpc_url=DEFAULT_X1_RPC_URL,
    retries=4,
    timeout=15,
    post=requests.post,
    sleep=time.sleep,
):
    """Return direct RPC identity evidence for one X1 token account."""
    account = _text(account)
    if not account:
        raise ValueError("Token account is required.")

    result = rpc_request(
        "getAccountInfo",
        [
            account,
            {"encoding": "jsonParsed"},
        ],
        rpc_url=rpc_url,
        retries=retries,
        timeout=timeout,
        post=post,
        sleep=sleep,
    )

    return parse_token_account_result(result, account=account)


class X1RPCProvider:
    """Explicit X1 RPC provider facade for verified current token facts."""

    chain = CHAIN
    rpc_source = RPC_SOURCE

    def __init__(
        self,
        *,
        rpc_url=DEFAULT_X1_RPC_URL,
        retries=4,
        timeout=15,
        post=requests.post,
        sleep=time.sleep,
    ):
        self.rpc_url = _text(rpc_url)
        self.retries = retries
        self.timeout = timeout
        self.post = post
        self.sleep = sleep

        if not self.rpc_url:
            raise ValueError("X1 RPC URL is required.")
        if self.retries < 1:
            raise ValueError("X1 RPC retries must be at least 1.")

    def request(self, method, params):
        return rpc_request(
            method,
            params,
            rpc_url=self.rpc_url,
            retries=self.retries,
            timeout=self.timeout,
            post=self.post,
            sleep=self.sleep,
        )

    def get_token_supply(self, mint):
        return get_token_supply(
            mint,
            rpc_url=self.rpc_url,
            retries=self.retries,
            timeout=self.timeout,
            post=self.post,
            sleep=self.sleep,
        )

    def get_mint_info(self, mint):
        return get_mint_info(
            mint,
            rpc_url=self.rpc_url,
            retries=self.retries,
            timeout=self.timeout,
            post=self.post,
            sleep=self.sleep,
        )

    def get_token_account_info(self, account):
        return get_token_account_info(
            account,
            rpc_url=self.rpc_url,
            retries=self.retries,
            timeout=self.timeout,
            post=self.post,
            sleep=self.sleep,
        )


__all__ = [
    "CHAIN",
    "DEFAULT_X1_RPC_URL",
    "RPC_SOURCE",
    "X1RPCError",
    "X1RPCProvider",
    "get_mint_info",
    "get_token_account_info",
    "get_token_supply",
    "parse_mint_account_result",
    "parse_token_account_result",
    "parse_token_supply_result",
    "rpc_request",
]
