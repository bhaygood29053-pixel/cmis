#!/usr/bin/env python3
"""Operational runner for lead-driven XONE/XNT primary artifact resolution.

This runner intentionally performs no network discovery. A lead must already
exist as a local JSON object containing retrieved artifact text and provenance.
Without --lead-json it emits the accepted NO_LEAD state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from liquidity_scout.providers.xone_xnt import (
    no_lead_resolution,
    resolve_primary_allocation_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve one already-retrieved XONE/XNT primary allocation "
            "artifact lead. No network discovery is performed."
        )
    )
    parser.add_argument(
        "--lead-json",
        help="Local JSON file containing one explicit artifact lead.",
    )
    parser.add_argument(
        "--observed-at",
        type=float,
        default=None,
        help="Observation time for NO_LEAD output; defaults to current time.",
    )
    args = parser.parse_args()

    if args.lead_json:
        path = Path(args.lead_json)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("lead JSON must contain one object")
        result = resolve_primary_allocation_artifact(payload)
    else:
        observed_at = (
            args.observed_at
            if args.observed_at is not None
            else time.time()
        )
        result = no_lead_resolution(observed_at=observed_at)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
