#!/usr/bin/env python3
"""Build the Phase-2 deterministic route snapshot from the accepted live probe.

The Phase-1 probe remains the only network collector. This wrapper consumes only
its normalized parsed quote and independent X1-RPC verification, then appends a
provider-agnostic `xdex_multi_hop_route_snapshot/v1` object to the evidence
artifact. No prepare/sign/broadcast/execution path is introduced.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from probe_xdex_multi_hop_quote import ARTIFACT_PATH, main as run_phase1_probe
from liquidity_scout.services.cmis_xdex_multi_hop_route_snapshot import (
    CONTRACT_VERSION,
    build_xdex_multi_hop_route_snapshot,
)


def main() -> None:
    run_phase1_probe()
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    parsed_quote = artifact.get("parsed_quote")
    verification = artifact.get("onchain_verification")
    snapshot = build_xdex_multi_hop_route_snapshot(parsed_quote, verification)
    artifact["route_snapshot"] = snapshot
    artifact["phase2_contract_version"] = CONTRACT_VERSION
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "PASS",
        "contract_version": snapshot["contract_version"],
        "hop_count": snapshot["hop_count"],
        "slot_span": snapshot["observation_window"]["slot_span"],
        "aggregate_hop_output_verified": snapshot["route_output"]["aggregate_hop_output_verified"],
        "provider_routing_fee_transform_verified": snapshot["provider_routing_fee_transform"]["arithmetic_transform_verified"],
        "provider_fee_business_semantics_verified": snapshot["provider_routing_fee_transform"]["business_semantics_verified"],
        "price_impact_status": snapshot["price_impact"]["status"],
        "minimum_received_status": snapshot["minimum_received"]["status"],
        "network_fee_status": snapshot["network_fee"]["status"],
        "route_optimality_verified": snapshot["route_optimality_verified"],
        "provider_raw_json_exposed": snapshot["provider_raw_json_exposed"],
        "execution_authorized": snapshot["execution_authorized"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
