#!/usr/bin/env python3
"""Run the dedicated XONE/XNT conversion scraper."""

from __future__ import annotations

import argparse
import json

from liquidity_scout.providers.xone_xnt import XoneXntConversionScraper, source_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect candidate XONE -> XNT conversion evidence without promoting it to CMIS truth."
    )
    parser.add_argument("source_id", choices=source_ids())
    parser.add_argument("url", nargs="?")
    parser.add_argument("--sitemap", action="store_true", help="Discover and scrape ranked sitemap candidates.")
    parser.add_argument("--max-urls", type=int, default=20)
    parser.add_argument("--max-claims", type=int, default=100)
    args = parser.parse_args()

    scraper = XoneXntConversionScraper()
    if args.sitemap:
        result = scraper.scrape_sitemap_candidates(
            args.source_id,
            sitemap_url=args.url,
            max_urls=args.max_urls,
            max_claims_per_url=min(args.max_claims, 100),
        )
    else:
        if not args.url:
            parser.error("url is required unless --sitemap uses the registered source sitemap")
        result = scraper.scrape_url(
            args.source_id,
            args.url,
            max_claims=args.max_claims,
        )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
