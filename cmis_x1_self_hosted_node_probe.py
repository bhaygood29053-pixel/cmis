#!/usr/bin/env python3
"""Run a bounded sanitized RPC probe against a self-hosted X1 read-only node."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.self_hosted_readonly_node import (
    collect_self_hosted_rpc_evidence,
    evaluate_startup_configuration,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect bounded read-only self-hosted X1 RPC redundancy evidence."
    )
    parser.add_argument("--rpc-url", required=True, help="Self-hosted X1 RPC URL.")
    parser.add_argument(
        "--canonical-rpc-url",
        default=DEFAULT_X1_RPC_URL,
        help="Accepted canonical X1 RPC comparison URL.",
    )
    parser.add_argument(
        "--probe-address",
        required=True,
        help="Address with finalized history used only for bounded identity comparison.",
    )
    parser.add_argument("--history-limit", type=int, default=25)
    parser.add_argument(
        "--startup-command-file",
        help="Optional operator-captured startup command/config artifact.",
    )
    parser.add_argument(
        "--startup-config-provenance",
        help="Required provenance label if --startup-command-file is supplied.",
    )
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()

    evidence = collect_self_hosted_rpc_evidence(
        rpc_url=args.rpc_url,
        canonical_rpc_url=args.canonical_rpc_url,
        probe_address=args.probe_address,
        history_limit=args.history_limit,
    )

    if args.startup_command_file:
        text = Path(args.startup_command_file).read_text(encoding="utf-8")
        config = evaluate_startup_configuration(
            text,
            provenance=args.startup_config_provenance,
        )
        evidence["startup_configuration"] = asdict(config)
    else:
        evidence["startup_configuration"] = asdict(
            evaluate_startup_configuration(None, provenance=None)
        )
        evidence["warnings"].append(
            "No startup-configuration artifact was supplied; runtime startup flags remain unverified."
        )

    path = Path(args.output)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
