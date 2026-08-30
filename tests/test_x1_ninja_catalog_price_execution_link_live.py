import json
import os
import time
import unittest

from liquidity_scout.providers.x1.ninja_catalog_price_execution_link import (
    aggregate_catalog_price_links,
    collect_ninja_catalog_price_snapshot,
    select_bounded_xnt_catalog_pools,
    verify_catalog_price_transition,
)
from liquidity_scout.providers.x1.ninja_pool_catalog import (
    fetch_pool_catalog_raw,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_CATALOG_PRICE_LINK_LIVE") == "1"
MAX_SNAPSHOTS = int(os.getenv("X1_NINJA_CATALOG_LINK_MAX_SNAPSHOTS", "36"))
POLL_SECONDS = int(os.getenv("X1_NINJA_CATALOG_LINK_POLL_SECONDS", "10"))
CATALOG_LIMIT = int(os.getenv("X1_NINJA_CATALOG_LINK_LIMIT", "100"))
MAX_POOLS = int(os.getenv("X1_NINJA_CATALOG_LINK_MAX_POOLS", "30"))


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_CATALOG_PRICE_LINK_LIVE=1 to run read-only evidence",
)
class NinjaCatalogPriceExecutionLinkLiveTests(unittest.TestCase):
    def test_capture_five_catalog_price_update_links_or_remain_partial(self):
        initial = fetch_pool_catalog_raw(limit=CATALOG_LIMIT)
        rows = initial["raw_response"].get("pools") or []
        addresses = select_bounded_xnt_catalog_pools(
            rows,
            maximum_pools=MAX_POOLS,
        )
        self.assertTrue(addresses, "No bounded exact-XNT catalog pools found")

        snapshots = []
        verified_events = []
        seen_signatures = set()
        diagnostics = []

        for index in range(MAX_SNAPSHOTS):
            current = collect_ninja_catalog_price_snapshot(
                pool_addresses=addresses,
                catalog_limit=CATALOG_LIMIT,
            )
            snapshots.append(current)

            if len(snapshots) >= 2:
                before = snapshots[-2]
                after = snapshots[-1]
                for address in addresses:
                    try:
                        event = verify_catalog_price_transition(
                            before=before,
                            after=after,
                            pool_address=address,
                        )
                    except Exception as exc:
                        diagnostics.append({
                            "pool_address": address,
                            "snapshot_index": index,
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        continue

                    if event["status"] == "verified":
                        signature = event["matched_transaction"]["signature"]
                        if signature not in seen_signatures:
                            seen_signatures.add(signature)
                            verified_events.append(event)
                    elif event.get("price_changed") is True:
                        diagnostics.append({
                            "pool_address": address,
                            "snapshot_index": index,
                            "status": event["status"],
                            "eligible_signature_count": event.get(
                                "eligible_signature_count"
                            ),
                            "verified_swap_candidate_count": event.get(
                                "verified_swap_candidate_count"
                            ),
                            "matching_execution_price_count": event.get(
                                "matching_execution_price_count"
                            ),
                        })

                if len(verified_events) >= 5:
                    break

            if index < MAX_SNAPSHOTS - 1:
                time.sleep(POLL_SECONDS)

        aggregate = aggregate_catalog_price_links(
            verified_events,
            minimum_verified_events=5,
        )

        print(
            "[X1.Ninja catalog price execution-link evidence] "
            + json.dumps({
                "snapshot_count": len(snapshots),
                "monitored_pool_count": len(addresses),
                "poll_seconds": POLL_SECONDS,
                "aggregate": aggregate,
                "diagnostics": diagnostics,
            }, sort_keys=True, default=str)
        )

        # Evidence workflow remains operationally green even if the bounded
        # window catches fewer than five uniquely linkable price changes.
        # Promotion is determined only by aggregate status/flags.
        self.assertIn(aggregate["status"], {"verified", "partial", "unavailable"})
        if aggregate["status"] == "verified":
            self.assertEqual(aggregate["verified_event_count"], 5)
            self.assertTrue(
                aggregate["catalog_price_execution_link_verified"]
            )
            self.assertTrue(aggregate["event_ordering_verified"])
        else:
            self.assertFalse(
                aggregate["catalog_price_execution_link_verified"]
            )

        self.assertFalse(aggregate["provider_fact_time_verified"])
        self.assertFalse(aggregate["update_source_semantics_verified"])
        self.assertFalse(aggregate["freshness_verified"])
        self.assertFalse(
            aggregate["universal_catalog_price_semantics_verified"]
        )
        self.assertFalse(aggregate["price_usd_semantics_verified"])
        self.assertFalse(aggregate["liquidity_semantics_verified"])
        self.assertFalse(aggregate["cmis_promotable"])
        self.assertFalse(aggregate["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
