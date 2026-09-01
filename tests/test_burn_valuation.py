import unittest

from liquidity_scout.tokenomics.burn_valuation import (
    FACT_TIME_POLICY,
    VALUATION_CONTRACT,
    build_burn_valuation,
)


MINT = "MintA"
NOW = 10_000_000


def burn(event_key, raw_amount, block_time):
    return {
        "event_key": event_key,
        "kind": "burn",
        "raw_amount": str(raw_amount),
        "block_time": block_time,
    }


def price(unit, price, fact_time, *, source="historical source", **overrides):
    value = {
        "unit": unit,
        "price": str(price),
        "price_verified": True,
        "historical_price_verified": True,
        "unit_verified": True,
        "price_fact_time": fact_time,
        "price_observed_at": fact_time + 10,
        "fact_time_policy": FACT_TIME_POLICY,
        "source": source,
    }
    value.update(overrides)
    return value


def evidence(events):
    return {
        "mint": MINT,
        "decimals": 6,
        "contract": VALUATION_CONTRACT,
        "contract_verified": True,
        "source": "CMIS verified burn-time price evidence",
        "events": events,
    }


def event_evidence(event_key, raw_amount, block_time, *, native=None, usd=None):
    result = {
        "event_key": event_key,
        "mint": MINT,
        "raw_amount": str(raw_amount),
        "burn_block_time": block_time,
    }
    if native is not None:
        result["native"] = native
    if usd is not None:
        result["usd"] = usd
    return result


def windows():
    return {
        label: {"status": "ok"}
        for label in ("1h", "24h", "7d", "30d")
    }


class BurnValuationContractTests(unittest.TestCase):
    def test_complete_native_and_usd_valuation(self):
        events = [
            burn("burn-a", 1_000_000, NOW - 100),
            burn("burn-b", 2_000_000, NOW - 200),
        ]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    native=price("XNT", "2", NOW - 100, source="native-a"),
                    usd=price("USD", "3", NOW - 100, source="usd-a"),
                ),
                event_evidence(
                    "burn-b",
                    2_000_000,
                    NOW - 200,
                    native=price("XNT", "2.5", NOW - 200, source="native-b"),
                    usd=price("USD", "4", NOW - 200, source="usd-b"),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertTrue(report["available"])
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["valuation_coverage_complete"])
        self.assertEqual(report["burned_observed"], "3")
        self.assertEqual(
            report["verified_native_value_destroyed_observed"],
            "7",
        )
        self.assertEqual(
            report["verified_usd_value_destroyed_observed"],
            "11",
        )
        self.assertEqual(report["native"]["valued_burn_amount"], "3")
        self.assertEqual(report["native"]["unvalued_burn_amount"], "0")
        self.assertEqual(report["usd"]["complete_value_destroyed"], "11")
        self.assertEqual(report["windows"]["24h"]["status"], "ok")

    def test_verified_values_preserve_precision_beyond_fifty_digits(self):
        large_price = (
            "123456789012345678901234567890"
            "123456789012345678901234567890"
        )
        events = [
            burn("burn-a", 3_000_000, NOW - 100),
            burn("burn-b", 1_000_000, NOW - 200),
        ]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    3_000_000,
                    NOW - 100,
                    usd=price("USD", large_price, NOW - 100),
                ),
                event_evidence(
                    "burn-b",
                    1_000_000,
                    NOW - 200,
                    usd=price("USD", "1", NOW - 200),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        expected_product = str(3 * int(large_price))
        expected_total = str(int(expected_product) + 1)
        self.assertEqual(
            report["events"][0]["usd"]["value_destroyed"],
            expected_product,
        )
        self.assertEqual(
            report["verified_usd_value_destroyed_observed"],
            expected_total,
        )
        self.assertEqual(
            report["usd"]["complete_value_destroyed"],
            expected_total,
        )

    def test_partial_usd_coverage_exposes_unvalued_burn_amount(self):
        events = [
            burn("burn-a", 1_000_000, NOW - 100),
            burn("burn-b", 2_000_000, NOW - 200),
        ]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    usd=price("USD", "3", NOW - 100),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["status"], "partial")
        self.assertFalse(report["valuation_coverage_complete"])
        self.assertEqual(report["usd"]["status"], "partial")
        self.assertEqual(report["usd"]["burn_events_valued"], 1)
        self.assertEqual(report["usd"]["valued_burn_amount"], "1")
        self.assertEqual(report["usd"]["unvalued_burn_amount"], "2")
        self.assertEqual(report["verified_usd_value_destroyed_observed"], "3")
        self.assertIsNone(report["usd"]["complete_value_destroyed"])
        self.assertEqual(report["native"]["status"], "unavailable")

    def test_current_or_nearby_price_cannot_substitute_for_exact_burn_time(self):
        events = [burn("burn-a", 1_000_000, NOW - 100)]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    usd=price("USD", "3", NOW - 99),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["status"], "unavailable")
        self.assertFalse(report["usd"]["valuation_coverage_complete"])
        self.assertEqual(report["usd"]["unvalued_burn_amount"], "1")
        self.assertIsNone(report["verified_usd_value_destroyed_observed"])

    def test_configured_stable_quote_without_verified_usd_unit_is_rejected(self):
        events = [burn("burn-a", 1_000_000, NOW - 100)]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    usd=price(
                        "USD",
                        "3",
                        NOW - 100,
                        unit_verified=False,
                        source="configured stable quote only",
                    ),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["usd"]["status"], "unavailable")
        self.assertEqual(
            report["events"][0]["usd"]["reason"],
            "usd_historical_price_unverified",
        )

    def test_price_observation_time_cannot_precede_fact_time(self):
        events = [burn("burn-a", 1_000_000, NOW - 100)]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    usd=price(
                        "USD",
                        "3",
                        NOW - 100,
                        price_observed_at=NOW - 101,
                    ),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["usd"]["status"], "unavailable")
        self.assertEqual(
            report["events"][0]["usd"]["reason"],
            "usd_price_observation_time_malformed",
        )

    def test_unverified_burn_window_does_not_fabricate_zero_valuation(self):
        burn_windows = windows()
        burn_windows["1h"] = {"status": "unavailable"}

        report = build_burn_valuation(
            [burn("burn-a", 1_000_000, NOW - 100)],
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    native=price("XNT", "2", NOW - 100),
                    usd=price("USD", "3", NOW - 100),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=burn_windows,
        )

        window = report["windows"]["1h"]
        self.assertEqual(window["status"], "unavailable")
        self.assertIsNone(window["native"]["valued_burn_raw"])
        self.assertIsNone(window["native"]["valued_burn_amount"])
        self.assertIsNone(window["usd"]["valued_burn_raw"])
        self.assertIsNone(window["usd"]["valued_burn_amount"])

    def test_native_and_usd_are_independent_semantics(self):
        events = [burn("burn-a", 1_500_000, NOW - 100)]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    1_500_000,
                    NOW - 100,
                    native=price("XNT", "2", NOW - 100),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["native"]["verified_value_destroyed"], "3")
        self.assertTrue(report["native"]["valuation_coverage_complete"])
        self.assertEqual(report["usd"]["status"], "unavailable")
        self.assertFalse(report["usd"]["valuation_coverage_complete"])

    def test_event_identity_mismatch_fails_closed(self):
        events = [burn("burn-a", 1_000_000, NOW - 100)]
        report = build_burn_valuation(
            events,
            evidence([
                event_evidence(
                    "burn-a",
                    999_999,
                    NOW - 100,
                    usd=price("USD", "3", NOW - 100),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertFalse(report["available"])
        self.assertEqual(
            report["reason"],
            "burn_valuation_event_identity_mismatch",
        )

    def test_duplicate_or_unknown_evidence_fails_closed(self):
        events = [burn("burn-a", 1_000_000, NOW - 100)]
        duplicate = event_evidence("burn-a", 1_000_000, NOW - 100)
        report = build_burn_valuation(
            events,
            evidence([duplicate, dict(duplicate)]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )
        self.assertEqual(
            report["reason"],
            "burn_valuation_event_evidence_duplicate_or_unkeyed",
        )

        unknown = build_burn_valuation(
            events,
            evidence([
                event_evidence("other", 1_000_000, NOW - 100),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )
        self.assertEqual(
            unknown["reason"],
            "burn_valuation_unknown_event_evidence",
        )

    def test_missing_event_kind_fails_closed_without_raising(self):
        malformed = {
            "event_key": "burn-a",
            "raw_amount": "1000000",
            "block_time": NOW - 100,
        }
        report = build_burn_valuation(
            [malformed],
            evidence([]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertFalse(report["available"])
        self.assertEqual(
            report["reason"],
            "burn_event_payload_malformed",
        )

    def test_missing_or_non_list_event_collection_fails_closed(self):
        for malformed in (None, {}, (), ""):
            with self.subTest(events=malformed):
                report = build_burn_valuation(
                    malformed,
                    evidence([]),
                    mint=MINT,
                    decimals=6,
                    observed_at=NOW,
                    burn_events_verified=True,
                    burn_windows=windows(),
                )

                self.assertFalse(report["available"])
                self.assertEqual(
                    report["reason"],
                    "burn_event_payload_malformed",
                )

    def test_unsupported_event_kind_fails_closed(self):
        malformed = burn("transfer-a", 1_000_000, NOW - 100)
        malformed["kind"] = "transfer"
        report = build_burn_valuation(
            [malformed],
            evidence([]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertFalse(report["available"])
        self.assertEqual(report["reason"], "burn_event_payload_malformed")

    def test_unsupported_price_exponent_fails_closed_without_raising(self):
        report = build_burn_valuation(
            [burn("burn-a", 1_000_000, NOW - 100)],
            evidence([
                event_evidence(
                    "burn-a",
                    1_000_000,
                    NOW - 100,
                    usd=price("USD", "1e1000000", NOW - 100),
                ),
            ]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(
            report["events"][0]["usd"]["reason"],
            "usd_price_numeric_range_unsupported",
        )

    def test_unverified_burn_events_cannot_be_valued(self):
        report = build_burn_valuation(
            [burn("burn-a", 1_000_000, NOW - 100)],
            evidence([]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=False,
            burn_windows=windows(),
        )

        self.assertFalse(report["available"])
        self.assertEqual(
            report["reason"],
            "burn_events_unverified_for_valuation",
        )

    def test_zero_burn_window_can_be_complete_zero_when_burn_window_is_verified(self):
        report = build_burn_valuation(
            [],
            evidence([]),
            mint=MINT,
            decimals=6,
            observed_at=NOW,
            burn_events_verified=True,
            burn_windows=windows(),
        )

        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["valuation_coverage_complete"])
        self.assertEqual(report["native"]["complete_value_destroyed"], "0")
        self.assertEqual(report["usd"]["complete_value_destroyed"], "0")
        self.assertEqual(report["windows"]["1h"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
