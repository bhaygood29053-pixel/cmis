import json
import os
import sqlite3
import tempfile
import unittest

from liquidity_scout.cmis.solana_observation_ledger import (
    DEX_PAIR_SCOPE,
    DEX_SOURCE,
    JUPITER_SCOPE,
    JUPITER_SOURCE,
    LIQUIDITY_USD,
    PRICE_USD,
    RPC_SOURCE,
    RPC_SUPPLY_SCOPE,
    TOTAL_SUPPLY_RAW,
    VOLUME_24H_USD,
    SolanaObservationLedger,
    sanitize_solana_observation,
)

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"
PAIR_A = "11111111111111111111111111111111"
PAIR_B = "SysvarRent111111111111111111111111111111111"


def jupiter_observation(**overrides):
    value = {
        "chain": "solana",
        "mint": MINT,
        "metric": PRICE_USD,
        "source": JUPITER_SOURCE,
        "scope": JUPITER_SCOPE,
        "subject_id": MINT,
        "pair_address": None,
        "requested_mint_role": None,
        "base_mint": None,
        "quote_mint": None,
        "value": "1.230000",
        "provider_observed_at": None,
        "provider_block_id": 123456,
        "provider_block_slot": None,
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": False,
    }
    value.update(overrides)
    return value


def dex_observation(
    *,
    metric=PRICE_USD,
    pair=PAIR_A,
    requested_role="base",
    value="1.23",
    **overrides,
):
    requested_mint = MINT if requested_role == "base" else QUOTE
    subject = MINT if metric == PRICE_USD else pair
    base = MINT
    quote = QUOTE
    record = {
        "chain": "solana",
        "mint": requested_mint,
        "metric": metric,
        "source": DEX_SOURCE,
        "scope": DEX_PAIR_SCOPE,
        "subject_id": subject,
        "pair_address": pair,
        "requested_mint_role": requested_role,
        "base_mint": base,
        "quote_mint": quote,
        "value": value,
        "provider_observed_at": None,
        "provider_block_id": None,
        "provider_block_slot": None,
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": False,
    }
    record.update(overrides)
    return record


def rpc_supply_observation(**overrides):
    value = {
        "chain": "solana",
        "mint": MINT,
        "metric": TOTAL_SUPPLY_RAW,
        "source": RPC_SOURCE,
        "scope": RPC_SUPPLY_SCOPE,
        "subject_id": MINT,
        "pair_address": None,
        "requested_mint_role": None,
        "base_mint": None,
        "quote_mint": None,
        "value": "001234500",
        "provider_observed_at": None,
        "provider_block_id": None,
        "provider_block_slot": 999,
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": False,
    }
    value.update(overrides)
    return value


class SolanaObservationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "solana-history.db")
        self.ledger = SolanaObservationLedger(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_jupiter_price_round_trip_preserves_exact_dimensions(self):
        stored = self.ledger.store(jupiter_observation(), collected_at=1000.0)
        loaded = self.ledger.get(stored["observation_id"])

        self.assertTrue(stored["inserted"])
        self.assertEqual(stored["timestamp_basis"], "collection_time")
        self.assertIsNotNone(loaded)
        observation = loaded["observation"]
        self.assertEqual(observation["chain"], "solana")
        self.assertEqual(observation["mint"], MINT)
        self.assertEqual(observation["metric"], PRICE_USD)
        self.assertEqual(observation["source"], JUPITER_SOURCE)
        self.assertEqual(observation["scope"], JUPITER_SCOPE)
        self.assertEqual(observation["subject_id"], MINT)
        self.assertEqual(observation["value"], "1.23")
        self.assertEqual(observation["unit"], "USD_PER_TOKEN")
        self.assertEqual(observation["provider_block_id"], 123456)
        self.assertEqual(observation["collected_at"], 1000.0)
        self.assertEqual(observation["timestamp_basis"], "collection_time")
        self.assertFalse(observation["freshness_verified"])

    def test_exact_duplicate_is_idempotent_but_new_collection_time_is_new_history(self):
        first = self.ledger.store(jupiter_observation(), collected_at=1000.0)
        duplicate = self.ledger.store(jupiter_observation(), collected_at=1000.0)
        later = self.ledger.store(jupiter_observation(), collected_at=2000.0)

        self.assertTrue(first["inserted"])
        self.assertFalse(duplicate["inserted"])
        self.assertEqual(first["observation_id"], duplicate["observation_id"])
        self.assertTrue(later["inserted"])
        self.assertNotEqual(first["observation_id"], later["observation_id"])

    def test_same_numeric_value_from_jupiter_and_dex_has_distinct_identity(self):
        jupiter = self.ledger.store(jupiter_observation(value="1.23"), collected_at=1000)
        dex = self.ledger.store(dex_observation(value="1.23"), collected_at=1000)

        self.assertNotEqual(jupiter["observation_id"], dex["observation_id"])

    def test_dex_base_pair_price_preserves_pair_and_price_subject(self):
        stored = self.ledger.store(dex_observation(), collected_at=1000)
        observation = self.ledger.get(stored["observation_id"])["observation"]

        self.assertEqual(observation["pair_address"], PAIR_A)
        self.assertEqual(observation["requested_mint_role"], "base")
        self.assertEqual(observation["base_mint"], MINT)
        self.assertEqual(observation["quote_mint"], QUOTE)
        self.assertEqual(observation["subject_id"], MINT)
        self.assertEqual(observation["source_role"], "market.pair_price")

    def test_quote_side_pair_price_is_never_relabelled_as_requested_mint_price(self):
        record = dex_observation(requested_role="quote", value="9.5")
        stored = self.ledger.store(record, collected_at=1000)
        observation = self.ledger.get(stored["observation_id"])["observation"]

        self.assertEqual(observation["mint"], QUOTE)
        self.assertEqual(observation["requested_mint_role"], "quote")
        self.assertEqual(observation["subject_id"], MINT)
        self.assertNotEqual(observation["subject_id"], observation["mint"])

        not_requested_price = self.ledger.nearest(
            mint=QUOTE,
            metric=PRICE_USD,
            source=DEX_SOURCE,
            scope=DEX_PAIR_SCOPE,
            subject_id=QUOTE,
            pair_address=PAIR_A,
            target_time=1000,
            max_distance_seconds=10,
        )
        self.assertIsNone(not_requested_price)

        actual_base_price = self.ledger.nearest(
            mint=QUOTE,
            metric=PRICE_USD,
            source=DEX_SOURCE,
            scope=DEX_PAIR_SCOPE,
            subject_id=MINT,
            pair_address=PAIR_A,
            target_time=1000,
            max_distance_seconds=10,
        )
        self.assertIsNotNone(actual_base_price)
        self.assertEqual(actual_base_price["observation"]["value"], "9.5")

    def test_pair_liquidity_and_volume_require_pair_as_subject(self):
        for metric in (LIQUIDITY_USD, VOLUME_24H_USD):
            with self.subTest(metric=metric):
                stored = self.ledger.store(
                    dex_observation(metric=metric, value="2500"),
                    collected_at=1000,
                )
                observation = self.ledger.get(stored["observation_id"])["observation"]
                self.assertEqual(observation["subject_id"], PAIR_A)
                self.assertEqual(observation["pair_address"], PAIR_A)

                with self.assertRaises(ValueError):
                    self.ledger.store(
                        dex_observation(
                            metric=metric,
                            value="2500",
                            subject_id=MINT,
                        ),
                        collected_at=1001,
                    )

    def test_nearest_never_mixes_jupiter_with_dex(self):
        self.ledger.store(jupiter_observation(value="1"), collected_at=1000)
        self.ledger.store(dex_observation(value="2"), collected_at=1001)

        jupiter = self.ledger.nearest(
            mint=MINT,
            metric=PRICE_USD,
            source=JUPITER_SOURCE,
            scope=JUPITER_SCOPE,
            subject_id=MINT,
            target_time=1001,
            max_distance_seconds=10,
        )
        dex = self.ledger.nearest(
            mint=MINT,
            metric=PRICE_USD,
            source=DEX_SOURCE,
            scope=DEX_PAIR_SCOPE,
            subject_id=MINT,
            pair_address=PAIR_A,
            target_time=1000,
            max_distance_seconds=10,
        )

        self.assertEqual(jupiter["observation"]["value"], "1")
        self.assertEqual(jupiter["observation"]["source"], JUPITER_SOURCE)
        self.assertEqual(dex["observation"]["value"], "2")
        self.assertEqual(dex["observation"]["source"], DEX_SOURCE)

    def test_nearest_never_mixes_dex_pairs(self):
        self.ledger.store(dex_observation(pair=PAIR_A, value="1"), collected_at=1000)
        self.ledger.store(dex_observation(pair=PAIR_B, value="2"), collected_at=1001)

        pair_a = self.ledger.nearest(
            mint=MINT,
            metric=PRICE_USD,
            source=DEX_SOURCE,
            scope=DEX_PAIR_SCOPE,
            subject_id=MINT,
            pair_address=PAIR_A,
            target_time=1001,
            max_distance_seconds=10,
        )
        pair_b = self.ledger.nearest(
            mint=MINT,
            metric=PRICE_USD,
            source=DEX_SOURCE,
            scope=DEX_PAIR_SCOPE,
            subject_id=MINT,
            pair_address=PAIR_B,
            target_time=1000,
            max_distance_seconds=10,
        )

        self.assertEqual(pair_a["observation"]["pair_address"], PAIR_A)
        self.assertEqual(pair_a["observation"]["value"], "1")
        self.assertEqual(pair_b["observation"]["pair_address"], PAIR_B)
        self.assertEqual(pair_b["observation"]["value"], "2")

    def test_nearest_respects_maturity_distance_and_reports_collection_time_basis(self):
        self.ledger.store(jupiter_observation(), collected_at=1000)

        self.assertIsNone(
            self.ledger.nearest(
                mint=MINT,
                metric=PRICE_USD,
                source=JUPITER_SOURCE,
                scope=JUPITER_SCOPE,
                subject_id=MINT,
                target_time=2000,
                max_distance_seconds=100,
            )
        )
        near = self.ledger.nearest(
            mint=MINT,
            metric=PRICE_USD,
            source=JUPITER_SOURCE,
            scope=JUPITER_SCOPE,
            subject_id=MINT,
            target_time=1050,
            max_distance_seconds=100,
        )
        self.assertEqual(near["distance_seconds"], 50.0)
        self.assertEqual(near["timestamp_basis"], "collection_time")
        self.assertEqual(near["observation"]["timestamp_basis"], "collection_time")

    def test_rpc_total_supply_preserves_base_units_and_slot(self):
        stored = self.ledger.store(rpc_supply_observation(), collected_at=1000)
        observation = self.ledger.get(stored["observation_id"])["observation"]

        self.assertEqual(observation["value"], "1234500")
        self.assertEqual(observation["unit"], "TOKEN_BASE_UNITS")
        self.assertEqual(observation["provider_block_slot"], 999)
        self.assertEqual(observation["subject_id"], MINT)
        self.assertEqual(observation["scope"], RPC_SUPPLY_SCOPE)

    def test_find_can_filter_without_erasing_provenance(self):
        self.ledger.store(jupiter_observation(value="1"), collected_at=1000)
        self.ledger.store(dex_observation(value="2"), collected_at=1001)

        records = self.ledger.find(
            mint=MINT,
            source=DEX_SOURCE,
            scope=DEX_PAIR_SCOPE,
            pair_address=PAIR_A,
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["observation"]["source"], DEX_SOURCE)
        self.assertEqual(records[0]["observation"]["pair_address"], PAIR_A)

    def test_invalid_chain_identity_source_scope_and_values_fail_closed(self):
        cases = [
            jupiter_observation(chain="x1"),
            jupiter_observation(mint="not-a-mint"),
            jupiter_observation(source="unknown"),
            jupiter_observation(scope="asset_wide"),
            jupiter_observation(value="0"),
            jupiter_observation(value="nan"),
            dex_observation(pair_address=None),
            rpc_supply_observation(value="1.2"),
            rpc_supply_observation(provider_block_slot=None),
        ]
        for record in cases:
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    self.ledger.store(record, collected_at=1000)

    def test_boolean_and_nonfinite_time_or_block_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.store(jupiter_observation(), collected_at=True)
        with self.assertRaises(ValueError):
            self.ledger.store(jupiter_observation(), collected_at=float("inf"))
        with self.assertRaises(ValueError):
            self.ledger.store(jupiter_observation(provider_block_id=True), collected_at=1000)
        with self.assertRaises(ValueError):
            self.ledger.store(
                jupiter_observation(provider_observed_at=float("nan")),
                collected_at=1000,
            )

    def test_arbitrary_secret_bearing_fields_are_rejected_and_never_persisted(self):
        secret = "https://provider.invalid/?api-key=SUPERSECRET"
        record = jupiter_observation()
        record["transport_url"] = secret

        with self.assertRaises(ValueError):
            self.ledger.store(record, collected_at=1000)

        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT observation_json FROM solana_observations"
            ).fetchall()
        self.assertEqual(rows, [])
        with open(self.db_path, "rb") as handle:
            self.assertNotIn(b"SUPERSECRET", handle.read())

    def test_sanitizer_derives_role_and_unit_instead_of_accepting_caller_labels(self):
        safe = sanitize_solana_observation(jupiter_observation(), collected_at=1000)
        self.assertEqual(safe["source_role"], "market.price_source")
        self.assertEqual(safe["unit"], "USD_PER_TOKEN")

        record = jupiter_observation()
        record["unit"] = "FAKE_UNIT"
        with self.assertRaises(ValueError):
            sanitize_solana_observation(record, collected_at=1000)

    def test_dex_pair_creation_time_is_not_an_observation_timestamp_field(self):
        record = dex_observation()
        record["pair_created_at_ms"] = 123456789
        with self.assertRaises(ValueError):
            self.ledger.store(record, collected_at=1000)

    def test_json_projection_contains_no_unexpected_transport_fields(self):
        stored = self.ledger.store(jupiter_observation(), collected_at=1000)
        loaded = self.ledger.get(stored["observation_id"])["observation"]
        serialized = json.dumps(loaded, sort_keys=True)

        self.assertNotIn("url", serialized.lower())
        self.assertNotIn("headers", serialized.lower())
        self.assertNotIn("api_key", serialized.lower())


if __name__ == "__main__":
    unittest.main()
