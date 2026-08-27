#!/usr/bin/env python3
"""Fail-closed public deployment preflight for CMIS.

This verifies only the deployment/auth/capability boundary. It does not claim
provider completeness or live market-data readiness; Roberta's readiness corpus
remains authoritative for that higher layer.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MIN_CMIS_CONTRACT = (1, 11, 0)
IDENTITY_CONTRACT = "x1_asset_identity/v1"
REQUIRED_IDENTITY_LIMITATIONS = {
    "exact_mint_is_canonical_fungible_identity_root",
    "same_mint_descriptor_conflicts_return_partial",
    "xdex_unavailable_is_not_metaplex_only",
    "symbol_or_name_never_reconciles_different_mints",
}
ALLOWED_HEALTH_STATUS = "ok"


class PreflightError(RuntimeError):
    pass


def _semver(value: Any) -> tuple[int, int, int]:
    text = str(value or "").strip()
    parts = text.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise PreflightError(f"invalid CMIS contract_version: {text!r}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _base_url(value: str) -> str:
    text = str(value or "").strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme != "https":
        raise PreflightError("CMIS public URL must use https://")
    if not parsed.hostname:
        raise PreflightError("CMIS public URL must include a hostname")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise PreflightError("CMIS public URL must be an origin with no path/query/fragment")

    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise PreflightError("CMIS public URL must not use a loopback hostname")
    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or 443)
    except socket.gaierror as exc:
        raise PreflightError(f"CMIS hostname does not resolve: {hostname}") from exc
    if not resolved:
        raise PreflightError(f"CMIS hostname does not resolve: {hostname}")

    addresses = []
    for item in resolved:
        sockaddr = item[4]
        if not sockaddr:
            continue
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError as exc:
            raise PreflightError(
                f"CMIS hostname resolved to an invalid address: {sockaddr[0]!r}"
            ) from exc
        addresses.append(address)
    if not addresses or any(not address.is_global for address in addresses):
        rendered = ", ".join(str(address) for address in addresses) or "none"
        raise PreflightError(
            "CMIS public hostname must resolve only to globally routable addresses: "
            + rendered
        )
    return text


def _read_json(
    request: Request,
    *,
    timeout: float,
    expected_status: int,
) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = str(getattr(response, "geturl", lambda: request.full_url)())
            if final_url != request.full_url:
                raise PreflightError(
                    f"{request.full_url} redirected to {final_url}; redirects are not accepted"
                )
            status = int(getattr(response, "status", 200))
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code != expected_status:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                pass
            raise PreflightError(
                f"{request.full_url} returned HTTP {exc.code}, expected {expected_status}"
                + (f": {detail}" if detail else "")
            ) from exc
        body = exc.read().decode("utf-8")
        status = exc.code
    except (URLError, TimeoutError, OSError) as exc:
        raise PreflightError(f"{request.full_url} is unreachable: {exc}") from exc

    if status != expected_status:
        raise PreflightError(
            f"{request.full_url} returned HTTP {status}, expected {expected_status}"
        )
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"{request.full_url} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"{request.full_url} returned non-object JSON")
    return value


def check_public_deployment(
    *,
    base_url: str,
    api_key: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    url = _base_url(base_url)
    key = str(api_key or "").strip()
    if not key:
        raise PreflightError("CMIS_API_KEY is required for public deployment")
    if len(key) < 32:
        raise PreflightError(
            "CMIS_API_KEY must be at least 32 characters for public deployment"
        )

    health = _read_json(
        Request(url + "/healthz", method="GET"),
        timeout=timeout,
        expected_status=200,
    )
    if health.get("service") != "cmis_gateway" or health.get("status") != ALLOWED_HEALTH_STATUS:
        raise PreflightError("CMIS /healthz identity/status is invalid")

    unauthorized = _read_json(
        Request(url + "/v1/cmis/capabilities", method="GET"),
        timeout=timeout,
        expected_status=401,
    )
    error = unauthorized.get("error")
    if (
        unauthorized.get("status") != "error"
        or not isinstance(error, dict)
        or error.get("code") != "unauthorized"
    ):
        raise PreflightError("CMIS capability endpoint did not fail closed without Bearer auth")

    capabilities = _read_json(
        Request(
            url + "/v1/cmis/capabilities",
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        ),
        timeout=timeout,
        expected_status=200,
    )
    if capabilities.get("service") != "cmis_gateway":
        raise PreflightError("CMIS capability service identity mismatch")
    if _semver(capabilities.get("contract_version")) < MIN_CMIS_CONTRACT:
        raise PreflightError(
            "CMIS deployment contract is older than required 1.11.0"
        )

    chains = capabilities.get("chains")
    if not isinstance(chains, dict):
        raise PreflightError("CMIS capabilities.chains is missing")
    x1 = chains.get("x1")
    if not isinstance(x1, dict):
        raise PreflightError("CMIS X1 capability record is missing")
    services = x1.get("services")
    if not isinstance(services, dict):
        raise PreflightError("CMIS X1 services capability record is missing")
    lookup = services.get("asset_lookup")
    if not isinstance(lookup, dict):
        raise PreflightError("CMIS X1 asset_lookup capability is missing")

    if lookup.get("callable") is not True:
        raise PreflightError("CMIS X1 asset_lookup is not callable")
    if lookup.get("identity_contract_version") != IDENTITY_CONTRACT:
        raise PreflightError("CMIS X1 asset identity contract mismatch")
    if lookup.get("exact_mint_normalization") is not True:
        raise PreflightError("CMIS exact-mint normalization is not enabled")
    if lookup.get("normalized_identity_root") != "mint":
        raise PreflightError("CMIS normalized identity root is not mint")
    if lookup.get("metaplex_xdex_reconciliation") is not True:
        raise PreflightError("CMIS Metaplex/XDEX reconciliation is not enabled")

    limitations = lookup.get("limitations")
    if (
        not isinstance(limitations, list)
        or any(not isinstance(item, str) for item in limitations)
    ):
        raise PreflightError("CMIS X1 asset_lookup limitations are malformed")
    missing = sorted(REQUIRED_IDENTITY_LIMITATIONS - set(limitations))
    if missing:
        raise PreflightError(
            "CMIS X1 asset_lookup identity limitations are missing: "
            + ", ".join(missing)
        )

    return {
        "status": "pass",
        "base_url": url,
        "health": "ok",
        "unauthorized_capabilities_rejected": True,
        "authorized_capabilities": True,
        "cmis_contract_version": capabilities.get("contract_version"),
        "identity_contract_version": lookup.get("identity_contract_version"),
        "normalized_identity_root": lookup.get("normalized_identity_root"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a public HTTPS CMIS deployment before Roberta readiness."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("CMIS_BASE_URL", ""),
        help="Public CMIS origin, e.g. https://cmis.example.com",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("CMIS_API_KEY", ""),
        help="CMIS Bearer token; defaults to CMIS_API_KEY",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    try:
        result = check_public_deployment(
            base_url=args.base_url,
            api_key=args.api_key,
            timeout=args.timeout,
        )
    except PreflightError as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
