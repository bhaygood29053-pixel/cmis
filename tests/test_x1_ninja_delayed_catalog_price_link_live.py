import json
import os
import time
import unittest

from liquidity_scout.providers.x1.ninja_catalog_price_execution_link import (
    collect_ninja_catalog_price_snapshot,
    select_bounded_xnt_catalog_pools,
    verify_catalog_price_transition,
)
from liquidity_scout.providers.x1.ninja_delayed_catalog_price_link import (
    aggregate_delayed_catalog_price_links,
    verify_delayed_catalog_price_transition,
)
from liquidity_scout.providers.x1.ninja_pool_catalog import (
    fetch_pool_catalog_raw,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_DELAYED_CATALOG_LINK_LIVE") == "1"
MAX_SNAPSHOTS = int(os.getenv("X1_NINJA_DELAYED_LINK_MAX_SNAPSHOTS", "36"))
POLL_SECONDS = int(os.getenv("X1_NINJA_DELAYED_LINK_POLL_SECONDS", "10"))
CATALOG_LIMIT = int(os.getenv("X1_NINJA_DELAYED_LINK_LIMIT", "100"))
MAX_POOLS = int(os.getenv("X1_NINJA_DELAYED_LINK_MAX_POOLS", "30"))


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_DELAYED_CATALOG_LINK_LIVE=1 to run read-only evidence",
)
class NinjaDelayedCatalogPriceLinkLiveTests(unittest.TestCase):
    def test_bounded_delayed_price_link_evidence(self):
        initial = fetch_pool_catalog_raw(limit=CATALOG_LIMIT)
        rows = initial["raw_response"].get("pools") or []
        addresses = select_bounded_xnt_catalog_pools(
            rows,
            maximum_pools=MAX_POOLS,
        )
        self.assertTrue(addresses, "No bounded exact-XNT pools found")

        snapshots = []
        delayed_events = []
        strict_verified = []
        seen_delayed_signatures = set()
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
                        strict = verify_catalog_price_transition(
                            before=before,
                            after=after,
                            pool_address=address,
                        )
                    except Exception as exc:
                        diagnostics.append({
                            "pool_address": address,
                            "snapshot_index": index,
                            "stage": "strict",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        continue

                    if strict.get("price_changed") is not True:
                        continue
                    if strict.get(
                        "catalog_price_execution_link_verified"
                    ) is True:
                        strict_verified.append(strict)
                        continue

                    try:
                        delayed = verify_delayed_catalog_price_transition(
                            before=before,
                            after=after,
                            pool_address=address,
                        )
                    except Exception as exc:
                        diagnostics.append({
                            "pool_address": address,
                            "snapshot_index": index,
                            "stage": "delayed",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        continue

                    delayed_events.append(delayed)
                    if delayed.get(
                        "delayed_catalog_price_execution_link_verified"
                    ) is True:
                        signature = delayed[
                            "matched_transaction"
                        ]["signature"]
                        seen_delayed_signatures.add(signature)

                if len(seen_delayed_signatures) >= 5:
                    break

            if index < MAX_SNAPSHOTS - 1:
                time.sleep(POLL_SECONDS)

        aggregate = aggregate_delayed_catalog_price_links(
            delayed_events,
            minimum_verified_events=5,
        )

        public = {
            "snapshot_count": len(snapshots),
            "monitored_pool_count": len(addresses),
            "strict_verified_event_count": len(strict_verified),
            "delayed_event_attempt_count": len(delayed_events),
            "distinct_delayed_signature_count": len(
                seen_delayed_signatures
            ),
            "aggregate": aggregate,
            "diagnostics": diagnostics,
        }
        print(
            "[X1.Ninja delayed catalog price-link evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertIn(
            aggregate["status"],
            {"verified", "partial", "unavailable"},
        )
        if aggregate["status"] == "verified":
            self.assertGreaterEqual(
                aggregate["verified_delayed_event_count"],
                5,
            )
            self.assertTrue(
                aggregate[
                    "delayed_catalog_price_execution_link_verified"
                ]
            )
            self.assertTrue(aggregate["incorporation_lag_observed"])
        else:
            self.assertFalse(
                aggregate[
                    "delayed_catalog_price_execution_link_verified"
                ]
            )

        self.assertFalse(
            aggregate["incorporation_lag_policy_verified"]
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
