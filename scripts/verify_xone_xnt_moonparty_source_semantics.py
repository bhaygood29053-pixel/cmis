#!/usr/bin/env python3
"""Live pinned-source proof for FairCrypto MoonParty XONE/XNT semantics."""

from __future__ import annotations

import json
import sys

import requests

from liquidity_scout.providers.xone_xnt import (
    FAIRCRYPTO_X1_APP_COMMIT,
    FAIRCRYPTO_X1_APP_REPO,
    FAIRCRYPTO_XONE_COMMIT,
    FAIRCRYPTO_XONE_REPO,
    MOONPARTY_ABI_PATH,
    MOONPARTY_CONTEXT_PATH,
    MOONPARTY_GLOBAL_PATH,
    MOONPARTY_STATE_PATH,
    MOONPARTY_TYPES_PATH,
    PROJECTS_PATH,
    XONE_SOURCE_PATH,
    verify_moonparty_source_semantics,
)


MAX_BYTES = 2_500_000
USER_AGENT = "CMIS-XONE-XNT-MoonParty-Source/1.0 (+read-only)"


def raw_url(repository: str, commit: str, path: str) -> str:
    owner, name = repository.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{name}/{commit}/{path}"


def fetch(repository: str, commit: str, path: str) -> dict:
    url = raw_url(repository, commit, path)
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/plain,*/*;q=0.1"},
        timeout=20,
        allow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > MAX_BYTES:
        raise RuntimeError(f"{path} exceeds {MAX_BYTES} bytes")
    return {
        "url": url,
        "status_code": response.status_code,
        "bytes": len(response.content),
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "text": response.content.decode("utf-8", errors="strict"),
    }


def main() -> int:
    source_specs = {
        "moonparty_abi": (FAIRCRYPTO_X1_APP_REPO, FAIRCRYPTO_X1_APP_COMMIT, MOONPARTY_ABI_PATH),
        "moonparty_types": (FAIRCRYPTO_X1_APP_REPO, FAIRCRYPTO_X1_APP_COMMIT, MOONPARTY_TYPES_PATH),
        "moonparty_context": (FAIRCRYPTO_X1_APP_REPO, FAIRCRYPTO_X1_APP_COMMIT, MOONPARTY_CONTEXT_PATH),
        "moonparty_state": (FAIRCRYPTO_X1_APP_REPO, FAIRCRYPTO_X1_APP_COMMIT, MOONPARTY_STATE_PATH),
        "moonparty_global": (FAIRCRYPTO_X1_APP_REPO, FAIRCRYPTO_X1_APP_COMMIT, MOONPARTY_GLOBAL_PATH),
        "projects": (FAIRCRYPTO_X1_APP_REPO, FAIRCRYPTO_X1_APP_COMMIT, PROJECTS_PATH),
        "xone_source": (FAIRCRYPTO_XONE_REPO, FAIRCRYPTO_XONE_COMMIT, XONE_SOURCE_PATH),
    }

    retrieval = {}
    documents = {}
    for key, (repository, commit, path) in source_specs.items():
        row = fetch(repository, commit, path)
        documents[key] = row.pop("text")
        retrieval[key] = {
            "repository": repository,
            "commit": commit,
            "path": path,
            **row,
        }

    proof = verify_moonparty_source_semantics(
        documents,
        provenance={
            "x1_app_repository": FAIRCRYPTO_X1_APP_REPO,
            "x1_app_commit": FAIRCRYPTO_X1_APP_COMMIT,
            "xone_repository": FAIRCRYPTO_XONE_REPO,
            "xone_commit": FAIRCRYPTO_XONE_COMMIT,
        },
    )

    output = {
        "status": "PASS",
        "contract_version": proof["contract_version"],
        "retrieval": retrieval,
        "proof": proof,
        "authoritative_source_semantics_verified":
            proof["authoritative_source_semantics_verified"],
        "xone_to_xnt_credit_design_link_verified":
            proof["xone_to_xnt_credit_design_link_verified"],
        "moonparty_deployment_verified": False,
        "xnt_credit_to_native_xnt_equivalence_verified": False,
        "xnt_issuance_verified": False,
        "xone_xnt_conversion_verified": False,
        "cross_chain_correlation_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
