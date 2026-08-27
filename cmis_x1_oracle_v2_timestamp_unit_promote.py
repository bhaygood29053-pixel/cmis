#!/usr/bin/env python3
"""Apply the accepted Oracle V2 timestamp-unit promotion policy.

This is a read-only evidence evaluation. It recollects bounded Oracle V2
historical evidence through the accepted probe, evaluates that raw bundle under
the explicit operator-approved governance policy, and emits a promotion result.

It does not authorize current-price use, provider promotion, Scout reliance, or
execution.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

from cmis_x1_oracle_v2_timestamp_unit_probe import (
    DEFAULT_HISTORY_LIMIT,
    probe_timestamp_unit_evidence,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_governance import (
    evaluate_oracle_v2_timestamp_unit_promotion,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_promotion_policy import (
    accepted_oracle_v2_timestamp_promotion_policy,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL


SERVICE = "x1_oracle_v2_timestamp_unit_promotion"
VERSION = "1.0"
CHAIN = "x1"


def evaluate_live_timestamp_unit_promotion(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    rpc_provider=None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Collect raw evidence and apply the accepted governance policy."""
    observed_at = observed_at or datetime.now(timezone.utc)
    policy = accepted_oracle_v2_timestamp_promotion_policy()

    raw_evidence = probe_timestamp_unit_evidence(
        rpc_url=rpc_url,
        rpc_provider=rpc_provider,
        history_limit=history_limit,
        observed_at=observed_at,
    )

    governance = evaluate_oracle_v2_timestamp_unit_promotion(
        evidence=raw_evidence,
        policy=policy,
    )

    verified = governance.get("timestamp_unit_verified") is True
    gates = governance.get("gates")
    all_gates_passed = bool(
        isinstance(gates, Mapping)
        and gates
        and all(value is True for value in gates.values())
    )

    status = "ok" if verified and all_gates_passed else "unavailable"
    reason = (
        "accepted_timestamp_unit_policy_satisfied"
        if status == "ok"
        else "accepted_timestamp_unit_policy_not_satisfied"
    )

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": CHAIN,
        "status": status,
        "reason": reason,
        "observed_at": observed_at.isoformat(),
        "policy": policy,
        "raw_evidence_status": raw_evidence.get("status"),
        "raw_evidence": raw_evidence,
        "governance": governance,
        "timestamp_unit": governance.get("timestamp_unit"),
        "timestamp_unit_method": governance.get("method"),
        "timestamp_unit_verified": verified,
        "timestamp_unit_evidence": governance.get(
            "timestamp_unit_evidence"
        ),
        "policy_sha256": governance.get("policy_sha256"),
        "evidence_sha256": governance.get("evidence_sha256"),
        "all_governance_gates_passed": all_gates_passed,
        # Scope boundary: promotion is timestamp semantics only.
        "freshness_verified": False,
        "price_correctness_verified": False,
        "source_independence_verified": False,
        "current_price_use_authorized": False,
        "cmis_provider_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
        "warnings": [
            (
                "Timestamp-unit verification is evidence-bound to the accepted "
                "Oracle V2 promotion policy and does not establish freshness."
            ),
            (
                "The accepted max_difference_ms is the observed maximum in the "
                "approved bounded evidence baseline, not an upstream guarantee."
            ),
            (
                "Oracle V2 relay slots remain same-system redundancy and are "
                "not independent market sources."
            ),
        ],
        "errors": (
            []
            if status == "ok"
            else list(governance.get("errors") or [])
        ),
    }


def _write_output(result: Mapping[str, Any], output_path: str | None):
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rpc-url",
        default=os.getenv("X1_RPC_URL", DEFAULT_X1_RPC_URL),
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=DEFAULT_HISTORY_LIMIT,
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        result = evaluate_live_timestamp_unit_promotion(
            rpc_url=args.rpc_url,
            history_limit=args.history_limit,
        )
    except Exception as exc:
        result = {
            "service": SERVICE,
            "version": VERSION,
            "chain": CHAIN,
            "status": "error",
            "reason": "promotion_evaluation_failed",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "timestamp_unit_verified": False,
            "freshness_verified": False,
            "price_correctness_verified": False,
            "source_independence_verified": False,
            "current_price_use_authorized": False,
            "cmis_provider_promoted": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    _write_output(result, args.output)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
