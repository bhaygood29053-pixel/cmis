#!/usr/bin/env python3
"""Operator CLI for passive X1 Explorer browser/network capture.

This command requires the optional Playwright operator dependency. It prints
only the sanitized x1_explorer_browser_capture/v1 result to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys

from liquidity_scout.providers.web_discovery import (
    X1_EXPLORER_BROWSER_DEFAULT_DWELL_SECONDS,
    X1_EXPLORER_BROWSER_DEFAULT_MAX_NETWORK_EVENTS,
    X1_EXPLORER_BROWSER_DEFAULT_NAVIGATION_TIMEOUT_MS,
    capture_x1_explorer_page_network,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Passively observe one supported X1 Explorer mainnet page and "
            "emit sanitized CMIS Web Discovery network observations."
        )
    )
    parser.add_argument(
        "page_url",
        help="Exact supported https://explorer.mainnet.x1.xyz/... route",
    )
    parser.add_argument(
        "--navigation-timeout-ms",
        type=int,
        default=X1_EXPLORER_BROWSER_DEFAULT_NAVIGATION_TIMEOUT_MS,
    )
    parser.add_argument(
        "--dwell-seconds",
        type=float,
        default=X1_EXPLORER_BROWSER_DEFAULT_DWELL_SECONDS,
    )
    parser.add_argument(
        "--max-network-events",
        type=int,
        default=X1_EXPLORER_BROWSER_DEFAULT_MAX_NETWORK_EVENTS,
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the Chromium window while preserving passive/no-click behavior.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = capture_x1_explorer_page_network(
            args.page_url,
            navigation_timeout_ms=args.navigation_timeout_ms,
            dwell_seconds=args.dwell_seconds,
            max_network_events=args.max_network_events,
            headless=not args.headed,
        )
    except Exception as exc:
        print(f"X1 Explorer browser capture failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
