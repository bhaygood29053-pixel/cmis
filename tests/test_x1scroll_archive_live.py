from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    verify_transaction,
)
from liquidity_scout.providers.x1.x1scroll_archive import (
    X1ScrollArchiveError,
    X1ScrollArchiveProvider,
)

RUN_LIVE = os.getenv("RUN_LIVE_X1SCROLL_ARCHIVE_PROOF") == "1"
API_KEY = os.getenv("X1SCROLL_API_KEY", "").strip()
EVIDENCE_PATH = Path(
    os.getenv(
        "X1SCROLL_LIVE_EVIDENCE_PATH",
        "artifacts/x1scroll-archive-live-458.json",
    )
)

# Predeclared historical X1 fixture already used by deterministic transaction
# semantics tests. It was observed through X1.Ninja + canonical X1 RPC on
# 2026-08-13T14:43:31Z at slot 71338200.
KNOWN_SIGNATURE = (
    "F4HMz4Y6BHRvj5ZgSbzaAiQD9KomEiEghcUH797RZ5ALVqhWooKrQzQgXzx3brTbYDWV5T2dwyxrhC56k5bnxsP"
)
KNOWN_SLOT = 71338200
KNOWN_ASSET_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
MISSING_SIGNATURE = "1" * 64
QUALIFIED_CONFIG = {
    "encoding": "jsonParsed",
    "commitment": "confirmed",
    "maxSupportedTransactionVersion": 0,
}


def _write_evidence(payload):
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, sort_keys=True)
    assert API_KEY not in rendered
    EVIDENCE_PATH.write_text(rendered + "\n", encoding="utf-8")
    print("X1SCROLL_ARCHIVE_LIVE_458")
    print(rendered)


@pytest.mark.skipif(
    not RUN_LIVE,
    reason="set RUN_LIVE_X1SCROLL_ARCHIVE_PROOF=1 for live #458 proof",
)
def test_live_x1scroll_known_signature_and_fail_closed_missing_signature():
    assert API_KEY, "X1SCROLL_API_KEY repository secret is required for live #458"

    provider = X1ScrollArchiveProvider(
        api_key=API_KEY,
        retries=2,
        timeout=20,
    )

    record = provider.get_transaction(
        KNOWN_SIGNATURE,
        config=QUALIFIED_CONFIG,
    )
    assert record["provider"] == "x1scroll"
    assert record["chain"] == "x1"
    assert record["known_signature_lookup"] is True
    assert record["transaction_available"] is True
    assert record["archive_completeness_verified"] is False
    assert record["source_independence_verified"] is False

    tx = record["transaction"]
    assert isinstance(tx, dict)
    assert tx.get("slot") == KNOWN_SLOT

    report = verify_transaction(
        tx,
        signature=KNOWN_SIGNATURE,
        rpc_url="x1scroll://credential-redacted",
        expected_mint=KNOWN_ASSET_MINT,
    )
    assert report.found is True
    assert report.succeeded is True
    assert report.slot == KNOWN_SLOT
    assert report.xdex_amm_invoked is True
    assert XDEX_MAINNET_OBSERVED_PROGRAM_ID in report.program_ids

    missing_mode = None
    try:
        missing = provider.get_transaction(
            MISSING_SIGNATURE,
            config=QUALIFIED_CONFIG,
        )
    except X1ScrollArchiveError as exc:
        message = str(exc)
        assert API_KEY not in message
        assert provider.rpc_url not in message
        missing_mode = "sanitized_error"
    else:
        assert missing["provider"] == "x1scroll"
        assert missing["transaction_available"] is False
        assert missing["transaction"] is None
        missing_mode = "null_not_found"

    evidence = {
        "schema": "x1scroll_archive_live_qualification_458/v1",
        "issue": 458,
        "provider": "x1scroll",
        "known_signature": KNOWN_SIGNATURE,
        "known_slot": KNOWN_SLOT,
        "qualified_config": QUALIFIED_CONFIG,
        "transaction_available": True,
        "parser_compatible": True,
        "xdex_program_verified": True,
        "missing_signature_fail_closed": True,
        "missing_signature_mode": missing_mode,
        "canonical_x1_rpc_remains_primary": True,
        "known_signature_fallback_only": True,
        "address_history_discovery_verified": False,
        "archive_completeness_verified": False,
        "lifetime_coverage_verified": False,
        "source_independence_verified": False,
        "api_key_included": False,
        "execution_authorized": False,
    }
    _write_evidence(evidence)
