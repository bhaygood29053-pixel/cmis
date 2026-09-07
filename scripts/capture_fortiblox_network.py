#!/usr/bin/env python3
"""Operator CLI for passive FortiBlox App browser/network capture."""

from __future__ import annotations

import argparse
import json
import sys

from liquidity_scout.providers.web_discovery import (
    FORTIBLOX_BROWSER_DEFAULT_DWELL_SECONDS,
    FORTIBLOX_BROWSER_DEFAULT_MAX_NETWORK_EVENTS,
    FORTIBLOX_BROWSER_DEFAULT_NAVIGATION_TIMEOUT_MS,
    capture_fortiblox_page_network,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Passively observe one app.fortiblox.com page and emit sanitized "
            "CMIS Web Discovery network observations."
        )
    )
    parser.add_argument(
        "page_url",
        nargs="?",
        default="https://app.fortiblox.com/",
        help="Exact https://app.fortiblox.com/... page to observe",
    )
    parser.add_argument(
        "--navigation-timeout-ms",
        type=int,
        default=FORTIBLOX_BROWSER_DEFAULT_NAVIGATION_TIMEOUT_MS,
    )
    parser.add_argument(
        "--dwell-seconds",
        type=float,
        default=FORTIBLOX_BROWSER_DEFAULT_DWELL_SECONDS,
    )
    parser.add_argument(
        "--max-network-events",
        type=int,
        default=FORTIBLOX_BROWSER_DEFAULT_MAX_NETWORK_EVENTS,
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show Chromium while preserving passive/no-click behavior.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = capture_fortiblox_page_network(
            args.page_url,
            navigation_timeout_ms=args.navigation_timeout_ms,
            dwell_seconds=args.dwell_seconds,
            max_network_events=args.max_network_events,
            headless=not args.headed,
        )
    except Exception as exc:
        print(f"FortiBlox browser capture failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
