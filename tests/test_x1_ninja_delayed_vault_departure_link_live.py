import json
import os
import time
import unittest
from decimal import Decimal, InvalidOperation

from liquidity_scout.providers.x1.ninja_catalog_price_execution_link import (
    collect_ninja_catalog_price_snapshot,
    select_bounded_xnt_catalog_pools,
)
from liquidity_scout.providers.x1.ninja_delayed_vault_departure_link import (
    UNAVAILABLE_OR_INCOMPLETE,
    aggregate_delayed_vault_departure_links,
    verify_delayed_vault_departure_link,
)
from liquidity_scout.providers.x1.ninja_pool_catalog import (
    fetch_pool_catalog_raw,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_DELAYED_DEPARTURE_LIVE") == "1"
MAX_SNAPSHOTS = int(
    os.getenv("X1_NINJA_DELAYED_DEPARTURE_MAX_SNAPSHOTS", "80")
)
POLL_SECONDS = int(
    os.getenv("X1_NINJA_DELAYED_DEPARTURE_POLL_SECONDS", "8")
)
CATALOG_LIMIT = int(
    os.getenv("X1_NINJA_DELAYED_DEPARTURE_CATALOG_LIMIT", "100")
)
MAX_POOLS = int(
    os.getenv("X1_NINJA_DELAYED_DEPARTURE_MAX_POOLS", "30")
)
TARGET_DEPARTURES = int(
    os.getenv("X1_NINJA_DELAYED_DEPARTURE_TARGET_EVENTS", "5")
)


def _provider(snapshot, pool_address):
    rows = snapshot.get("pools") or []
    for row in rows:
        if (
            isinstance(row, dict)
            and row.get("pool_address") == pool_address
            and row.get("status") == "ok"
            and isinstance(row.get("provider"), dict)
        ):
            return row["provider"]
    return None


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _catalog_price_only_candidate(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    before_price = _decimal(before.get("priceNative"))
    after_price = _decimal(after.get("priceNative"))
    before_base = _decimal(before.get("pooledBase"))
    after_base = _decimal(after.get("pooledBase"))
    before_quote = _decimal(before.get("pooledQuote"))
    after_quote = _decimal(after.get("pooledQuote"))
    if None in {
        before_price,
        after_price,
        before_base,
        after_base,
        before_quote,
        after_quote,
    }:
        return False
    return bool(
        before_price != after_price
        and before_base == after_base
        and before_quote == after_quote
    )


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_DELAYED_DEPARTURE_LIVE=1 to run read-only evidence",
)
class NinjaDelayedVaultDepartureLiveTests(unittest.TestCase):
    def test_bounded_delayed_vault_departure_pattern(self):
        initial = fetch_pool_catalog_raw(limit=CATALOG_LIMIT)
        rows = initial["raw_response"].get("pools") or []
        addresses = select_bounded_xnt_catalog_pools(
            rows,
            maximum_pools=MAX_POOLS,
        )
        self.assertTrue(
            addresses,
            "No exact-XNT pools found in bounded catalog",
        )

        snapshots = []
        evidence_events = []
        diagnostics = []
        seen_event_keys = set()
        price_only_candidate_count = 0

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
                    before_provider = _provider(before, address)
                    after_provider = _provider(after, address)
                    if not _catalog_price_only_candidate(
                        before_provider,
                        after_provider,
                    ):
                        continue

                    price_only_candidate_count += 1
                    try:
                        result = verify_delayed_vault_departure_link(
                            before=before,
                            after=after,
                            pool_address=address,
                        )
                    except Exception as exc:
                        event_key = (
                            f"{address}:snapshot:{index}:verification_exception"
                        )
                        evidence_events.append({
                            "event_key": event_key,
                            "pool_address": address,
                            "status": "unavailable",
                            "outcome": UNAVAILABLE_OR_INCOMPLETE,
                            "price_only_reserve_ratio_departure_verified": False,
                            "delayed_vault_swap_execution_link_verified": False,
                            "departure_lag_observed": False,
                            "warning": "verification_exception",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        diagnostics.append({
                            "snapshot_index": index,
                            "pool_address": address,
                            "stage": "verification_exception",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        continue

                    if result.get(
                        "price_only_reserve_ratio_departure_verified"
                    ) is True:
                        key = result.get("event_key")
                        if key and key not in seen_event_keys:
                            seen_event_keys.add(key)
                            evidence_events.append(result)
                    else:
                        diagnostics.append({
                            "snapshot_index": index,
                            "pool_address": address,
                            "stage": "not_verified_departure",
                            "status": result.get("status"),
                            "outcome": result.get("outcome"),
                            "warnings": result.get("warnings"),
                        })

                verified_departure_count = sum(
                    1
                    for row in evidence_events
                    if row.get(
                        "price_only_reserve_ratio_departure_verified"
                    ) is True
                )
                if verified_departure_count >= TARGET_DEPARTURES:
                    break

            if index < MAX_SNAPSHOTS - 1:
                time.sleep(POLL_SECONDS)

        aggregate = aggregate_delayed_vault_departure_links(
            evidence_events,
            minimum_verified_departures=5,
        )
        verified_departure_count = sum(
            1
            for row in evidence_events
            if row.get(
                "price_only_reserve_ratio_departure_verified"
            ) is True
        )

        public = {
            "snapshot_count": len(snapshots),
            "monitored_pool_count": len(addresses),
            "catalog_price_only_candidate_count": (
                price_only_candidate_count
            ),
            "verified_departure_count": verified_departure_count,
            "aggregate": aggregate,
            "diagnostics": diagnostics,
        }
        print(
            "[X1.Ninja delayed vault departure evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        self.assertEqual(aggregate["status"], "verified")
        self.assertTrue(
            aggregate["price_only_reserve_ratio_departure_verified"]
        )
        self.assertTrue(
            aggregate["delayed_vault_swap_execution_link_verified"]
        )
        self.assertTrue(aggregate["departure_pattern_verified"])

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
