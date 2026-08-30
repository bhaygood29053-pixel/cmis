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
    verify_delayed_catalog_price_transition,
)
from liquidity_scout.providers.x1.ninja_pool_catalog import (
    fetch_pool_catalog_raw,
)
from liquidity_scout.providers.x1.ninja_vault_activity_correlation import (
    aggregate_vault_activity_evidence,
    verify_vault_activity_transition,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_VAULT_ACTIVITY_LIVE") == "1"
MAX_SNAPSHOTS = int(os.getenv("X1_NINJA_VAULT_MAX_SNAPSHOTS", "30"))
POLL_SECONDS = int(os.getenv("X1_NINJA_VAULT_POLL_SECONDS", "10"))
CATALOG_LIMIT = int(os.getenv("X1_NINJA_VAULT_CATALOG_LIMIT", "100"))
MAX_POOLS = int(os.getenv("X1_NINJA_VAULT_MAX_POOLS", "15"))
TARGET_EVENTS = int(os.getenv("X1_NINJA_VAULT_TARGET_EVENTS", "5"))


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_VAULT_ACTIVITY_LIVE=1 to run read-only evidence",
)
class NinjaVaultActivityLiveTests(unittest.TestCase):
    def test_unexplained_catalog_updates_against_exact_vault_histories(self):
        initial = fetch_pool_catalog_raw(limit=CATALOG_LIMIT)
        rows = initial["raw_response"].get("pools") or []
        addresses = select_bounded_xnt_catalog_pools(
            rows,
            maximum_pools=MAX_POOLS,
        )
        self.assertTrue(addresses, "No exact-XNT pools found in bounded catalog")

        snapshots = []
        vault_events = []
        strict_verified = 0
        delayed_verified = 0
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
                            "snapshot_index": index,
                            "pool_address": address,
                            "stage": "strict",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        continue

                    if strict.get("price_changed") is not True:
                        continue
                    if strict.get(
                        "catalog_price_execution_link_verified"
                    ) is True:
                        strict_verified += 1
                        continue

                    try:
                        delayed = verify_delayed_catalog_price_transition(
                            before=before,
                            after=after,
                            pool_address=address,
                        )
                    except Exception as exc:
                        diagnostics.append({
                            "snapshot_index": index,
                            "pool_address": address,
                            "stage": "delayed",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        delayed = None

                    if (
                        isinstance(delayed, dict)
                        and delayed.get(
                            "delayed_catalog_price_execution_link_verified"
                        ) is True
                    ):
                        delayed_verified += 1
                        continue

                    try:
                        vault_event = verify_vault_activity_transition(
                            before=before,
                            after=after,
                            pool_address=address,
                        )
                    except Exception as exc:
                        diagnostics.append({
                            "snapshot_index": index,
                            "pool_address": address,
                            "stage": "vault_activity",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        continue

                    if vault_event.get(
                        "vault_history_complete_for_window"
                    ) is True:
                        vault_events.append(vault_event)

                if len(vault_events) >= TARGET_EVENTS:
                    break

            if index < MAX_SNAPSHOTS - 1:
                time.sleep(POLL_SECONDS)

        aggregate = aggregate_vault_activity_evidence(
            vault_events,
            minimum_events=5,
        )

        classification_counts = {}
        for event in vault_events:
            for key, value in event.get(
                "transaction_classification_counts", {}
            ).items():
                classification_counts[key] = (
                    classification_counts.get(key, 0) + value
                )

        public = {
            "snapshot_count": len(snapshots),
            "monitored_pool_count": len(addresses),
            "strict_verified_event_count": strict_verified,
            "delayed_verified_event_count": delayed_verified,
            "vault_event_count": len(vault_events),
            "transaction_classification_counts": classification_counts,
            "aggregate": aggregate,
            "diagnostics": diagnostics,
        }
        print(
            "[X1.Ninja vault-activity correlation evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertIn(
            aggregate["status"],
            {"verified", "partial", "unavailable"},
        )
        if len(vault_events) >= 5:
            self.assertTrue(aggregate["all_vault_histories_complete"])

        self.assertFalse(
            aggregate["catalog_price_execution_link_verified"]
        )
        self.assertFalse(
            aggregate["catalog_price_reserve_ratio_link_verified"]
        )
        self.assertFalse(
            aggregate["catalog_price_active_reserve_link_verified"]
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
