#!/usr/bin/env python3
"""Read exact-semantics JSON reports and run CMIS v1.4.11 qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from liquidity_scout.providers.x1.cross_pool_trusted_semantics import (
    qualify_cross_pool_trusted_semantics,
)


def _load_report(path: str):
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify multiple CMIS exact-pool reports for v1.4.11 trusted "
            "semantics promotion. Promotion remains internal/read-only."
        )
    )
    parser.add_argument(
        "reports",
        nargs="+",
        help="Paths to v1.4.10.3-or-newer exact-pool semantics JSON reports",
    )
    args = parser.parse_args()

    reports = [_load_report(path) for path in args.reports]
    result = qualify_cross_pool_trusted_semantics(reports)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
