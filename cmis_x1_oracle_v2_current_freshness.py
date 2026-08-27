#!/usr/bin/env python3
"""Read-only Oracle V2 current-slot freshness evaluator.

The evaluator consumes the accepted Unix-ms timestamp-unit evidence, reads the
current verified Oracle state, injects a CMIS-owned UTC observation time, and
classifies/aggregates each asset through the existing deterministic freshness
policy primitives.

No production freshness thresholds are defined here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

from cmis_x1_oracle_v2_probe import (
    ASSETS,
    DECIMALS,
    probe_oracle_v2,
)
from liquidity_scout.providers.x1.oracle_v2_policy import (
    aggregate_oracle_v2_slots,
    normalize_oracle_v2_freshness_policy,
)
from liquidity_scout.providers.x1.oracle_v2_timestamp_unit_evidence import (
    accepted_oracle_v2_timestamp_unit_evidence,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL


SERVICE = "x1_oracle_v2_current_slot_freshness"
VERSION = "1.0"
CHAIN = "x1"


def _utc_unix_ms(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    utc_value = value.astimezone(timezone.utc)
    return int(utc_value.timestamp() * 1000)


def _load_policy_file(path: str | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError("freshness policy JSON must be an object")
    return value


def evaluate_current_oracle_v2_freshness(
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    rpc_provider=None,
    freshness_policy: Mapping[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate current Oracle V2 slots with verified timestamp semantics."""
    explicit_observed_at = observed_at is not None
    if explicit_observed_at:
        # Validate deterministic test/caller injection before any RPC work.
        _utc_unix_ms(observed_at)

    timestamp_unit_evidence = accepted_oracle_v2_timestamp_unit_evidence()
    policy = normalize_oracle_v2_freshness_policy(freshness_policy)

    structural = probe_oracle_v2(
        rpc_url=rpc_url,
        rpc_provider=rpc_provider,
        observed_at=observed_at if explicit_observed_at else None,
    )

    # For live evaluation, capture the observation clock only after the state
    # RPC read completes. Otherwise an Oracle update landing during the read
    # could be compared against a pre-read clock and appear spuriously future.
    if not explicit_observed_at:
        observed_at = datetime.now(timezone.utc)
    observed_at_ms = _utc_unix_ms(observed_at)

    if structural.get("status") != "verified_contract_shape":
        return {
            "service": SERVICE,
            "version": VERSION,
            "chain": CHAIN,
            "status": "unavailable",
            "reason": "oracle_contract_shape_not_verified",
            "observed_at": observed_at.isoformat(),
            "observed_at_ms": observed_at_ms,
            "timestamp_unit_evidence": timestamp_unit_evidence,
            "timestamp_unit_verified": True,
            "freshness_policy": policy,
            "freshness_policy_applied": False,
            "freshness_verified": False,
            "assets": {},
            "slot_age_observations": [],
            "current_price_use_authorized": False,
            "cmis_provider_promoted": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "source_independence_verified": False,
            "price_correctness_verified": False,
            "execution_authorized": False,
            "warnings": [],
            "errors": ["oracle_contract_shape_not_verified"],
        }

    observations = structural.get("slot_observations")
    if not isinstance(observations, list):
        observations = []

    slot_age_observations = []
    by_asset = {asset: [] for asset in ASSETS}

    for item in observations:
        if not isinstance(item, Mapping):
            continue

        asset = item.get("asset")
        relay_index = item.get("relay_index")
        price_raw = item.get("price_raw")
        timestamp_raw = item.get("timestamp_raw")

        signed_age_ms = None
        future_offset_ms = None
        if (
            isinstance(timestamp_raw, int)
            and not isinstance(timestamp_raw, bool)
            and timestamp_raw > 0
        ):
            signed_age_ms = observed_at_ms - timestamp_raw
            if signed_age_ms < 0:
                future_offset_ms = -signed_age_ms

        age_record = {
            "asset": asset,
            "relay_index": relay_index,
            "price_raw": price_raw,
            "timestamp_raw": timestamp_raw,
            "observed_at_ms": observed_at_ms,
            "signed_age_ms": signed_age_ms,
            "future_offset_ms": future_offset_ms,
            "timestamp_unit": "unix_ms",
            "timestamp_unit_verified": True,
        }
        slot_age_observations.append(age_record)

        if asset in by_asset:
            by_asset[asset].append({
                "relay_index": relay_index,
                "price_raw": price_raw,
                "timestamp_raw": timestamp_raw,
            })

    asset_results = {}
    for asset in ASSETS:
        result = aggregate_oracle_v2_slots(
            by_asset[asset],
            observed_at_ms=observed_at_ms,
            policy=policy,
            timestamp_unit_evidence=timestamp_unit_evidence,
            decimals=DECIMALS,
        )
        asset_results[asset] = result

    policy_complete = policy["policy_complete"]
    freshness_policy_applied = bool(policy_complete)

    statuses = [result.get("status") for result in asset_results.values()]
    if not policy_complete:
        status = "unavailable"
        reason = "freshness_policy_incomplete"
    elif statuses and all(value == "ok" for value in statuses):
        status = "ok"
        reason = "all_assets_satisfy_explicit_freshness_policy"
    elif any(value in {"ok", "partial"} for value in statuses):
        status = "partial"
        reason = "some_assets_have_policy_eligible_slots"
    else:
        status = "unavailable"
        reason = "no_assets_have_policy_eligible_slots"

    positive_ages = [
        item["signed_age_ms"]
        for item in slot_age_observations
        if isinstance(item.get("signed_age_ms"), int)
    ]

    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": CHAIN,
        "status": status,
        "reason": reason,
        "observed_at": observed_at.isoformat(),
        "observed_at_ms": observed_at_ms,
        "observation_clock_source": (
            "explicit_injected"
            if explicit_observed_at
            else "post_rpc_runtime"
        ),
        "timestamp_unit_evidence": timestamp_unit_evidence,
        "timestamp_unit_verified": True,
        "freshness_policy": policy,
        "freshness_policy_applied": freshness_policy_applied,
        # This means CMIS has an explicit complete policy and has deterministically
        # classified the current state. It does not mean every slot is fresh.
        "freshness_verified": freshness_policy_applied,
        "structural_evidence": {
            "status": structural.get("status"),
            "observed_at": structural.get("observed_at"),
            "program": structural.get("program"),
            "state": structural.get("state"),
            "expected": structural.get("expected"),
            "checks": structural.get("checks"),
        },
        "slot_age_observations": slot_age_observations,
        "age_summary": {
            "slot_count": len(slot_age_observations),
            "positive_timestamp_age_count": len(positive_ages),
            "minimum_signed_age_ms": (
                min(positive_ages) if positive_ages else None
            ),
            "maximum_signed_age_ms": (
                max(positive_ages) if positive_ages else None
            ),
        },
        "assets": asset_results,
        # Even a policy-qualified median is candidate evidence only.
        "current_price_use_authorized": False,
        "cmis_provider_promoted": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "source_independence_verified": False,
        "price_correctness_verified": False,
        "execution_authorized": False,
        "warnings": [
            (
                "No production freshness thresholds are supplied by this "
                "service; an incomplete policy fails closed."
            ),
            (
                "Freshness verification classifies time validity only. It does "
                "not establish price correctness or independent source agreement."
            ),
            (
                "Oracle V2 relay slots are same-system redundancy and are not "
                "independent market sources."
            ),
            (
                "A policy-qualified candidate median does not authorize current "
                "price use, provider promotion, Scout reliance, or execution."
            ),
        ],
        "errors": [],
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
        "--freshness-policy-file",
        help=(
            "Optional explicit JSON policy. No policy defaults are supplied. "
            "The runtime observation clock remains internally injected."
        ),
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        policy = _load_policy_file(args.freshness_policy_file)
        result = evaluate_current_oracle_v2_freshness(
            rpc_url=args.rpc_url,
            freshness_policy=policy,
        )
    except Exception as exc:
        result = {
            "service": SERVICE,
            "version": VERSION,
            "chain": CHAIN,
            "status": "error",
            "reason": "current_freshness_evaluation_failed",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "timestamp_unit_verified": True,
            "freshness_policy_applied": False,
            "freshness_verified": False,
            "current_price_use_authorized": False,
            "cmis_provider_promoted": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "source_independence_verified": False,
            "price_correctness_verified": False,
            "execution_authorized": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    _write_output(result, args.output)
    return 0 if result.get("status") in {"ok", "partial", "unavailable"} else 1


if __name__ == "__main__":
    sys.exit(main())
