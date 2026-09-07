#!/usr/bin/env python3
"""Operator CLI for bounded FortiBlox multi-page browser/network inventory."""

from __future__ import annotations

import argparse
import json
import sys

from liquidity_scout.providers.web_discovery import (
    FORTIBLOX_ROUTE_INVENTORY_DEFAULT_CAPTURE_DWELL_SECONDS,
    FORTIBLOX_ROUTE_INVENTORY_DEFAULT_MAX_CAPTURE_PAGES,
    FORTIBLOX_ROUTE_INVENTORY_DEFAULT_MAX_DISCOVERED_ROUTES,
    FORTIBLOX_ROUTE_INVENTORY_DEFAULT_MAX_NETWORK_EVENTS_PER_PAGE,
    FORTIBLOX_ROUTE_INVENTORY_DEFAULT_ROUTE_DISCOVERY_DWELL_SECONDS,
    capture_fortiblox_route_inventory,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover same-host FortiBlox navigation routes without clicking "
            "and passively capture sanitized network observations."
        )
    )
    parser.add_argument(
        "page_url",
        nargs="?",
        default="https://app.fortiblox.com/",
    )
    parser.add_argument(
        "--max-routes",
        type=int,
        default=FORTIBLOX_ROUTE_INVENTORY_DEFAULT_MAX_DISCOVERED_ROUTES,
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=FORTIBLOX_ROUTE_INVENTORY_DEFAULT_MAX_CAPTURE_PAGES,
    )
    parser.add_argument(
        "--route-discovery-dwell-seconds",
        type=float,
        default=FORTIBLOX_ROUTE_INVENTORY_DEFAULT_ROUTE_DISCOVERY_DWELL_SECONDS,
    )
    parser.add_argument(
        "--capture-dwell-seconds",
        type=float,
        default=FORTIBLOX_ROUTE_INVENTORY_DEFAULT_CAPTURE_DWELL_SECONDS,
    )
    parser.add_argument(
        "--max-network-events-per-page",
        type=int,
        default=FORTIBLOX_ROUTE_INVENTORY_DEFAULT_MAX_NETWORK_EVENTS_PER_PAGE,
    )
    parser.add_argument("--headed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = capture_fortiblox_route_inventory(
            args.page_url,
            max_routes=args.max_routes,
            max_pages=args.max_pages,
            route_discovery_dwell_seconds=args.route_discovery_dwell_seconds,
            capture_dwell_seconds=args.capture_dwell_seconds,
            max_network_events_per_page=args.max_network_events_per_page,
            headless=not args.headed,
        )
    except Exception as exc:
        print(f"FortiBlox multi-page inventory failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
