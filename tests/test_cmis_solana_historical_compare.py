import os
import tempfile
import unittest

from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.cmis.solana_historical_gateway import SolanaHistoricalCompareMixin
from liquidity_scout.cmis.solana_market_gateway import SolanaMarketReportMixin
from liquidity_scout.cmis.solana_observation_ledger import (
    JUPITER_SCOPE,
    JUPITER_SOURCE,
    PRICE_USD,
    SolanaObservationLedger,
)
from liquidity_scout.providers.solana.rpc import SPL_TOKEN_PROGRAM_ID

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"
PAIR = "11111111111111111111111111111111"
DAY = 86400


class MutableClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class FakeRPCProvider:
    chain = "solana"

    def __init__(self):
        self.calls = []

    def get_mint_account(self, mint):
        self.calls.append(mint)
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getAccountInfo(jsonParsed)",
            "mint": mint,
            "context_slot": 1000,
            "owner_program_id": SPL_TOKEN_PROGRAM_ID,
            "parsed_program": "spl-token",
            "program_kind": "legacy_spl_token",
            "program_identity_verified": True,
            "amount_raw": "1000000",
            "decimals": 6,
            "mint_authority": None,
            "freeze_authority": None,
            "is_initialized": True,
            "extension_names": [],
            "mint_state_verified": True,
        }


class FakeJupiterProvider:
    chain = "solana"

    def __init__(self, prices, *, block_ids=None):
        self.prices = list(prices)
        self.block_ids = list(block_ids or range(2000, 2000 + len(self.prices)))
        self.calls = []

    def get_price(self, mint):
        index = len(self.calls)
        self.calls.append(mint)
        price = self.prices[min(index, len(self.prices) - 1)]
        block_id = self.block_ids[min(index, len(self.block_ids) - 1)]
        return {
            "chain": "solana",
            "source": JUPITER_SOURCE,
            "mint": mint,
            "price_available": True,
            "usd_price": price,
            "currency": "USD",
            "block_id": block_id,
            "decimals": 6,
            "token_created_at": None,
            "liquidity_usd_source_value": None,
            "price_change_24h_percent_source_value": None,
            "scope": JUPITER_SCOPE,
            "observed_at": None,
            "freshness_verified": False,
        }


class FakeDexProvider:
    chain = "solana"

    def __init__(self, prices, *, role="base"):
        self.prices = list(prices)
        self.role = role
        self.calls = []

    def get_token_pairs(self, mint):
        index = len(self.calls)
        self.calls.append(mint)
        price = self.prices[min(index, len(self.prices) - 1)]
        is_base = self.role == "base"
        pair = {
            "pair_address": PAIR,
            "dex_id": "testdex",
            "base_token": {
                "address": mint if is_base else QUOTE,
                "name": "Token",
                "symbol": "TOK",
            },
            "quote_token": {
                "address": QUOTE if is_base else mint,
                "name": "Quote",
                "symbol": "Q",
            },
            "requested_mint_role": self.role,
            "price_subject_address": mint if is_base else QUOTE,
            "price_is_for_requested_mint": is_base,
            "price_usd": price,
            "price_native": None,
            "liquidity_usd": "1000",
            "liquidity_base": None,
            "liquidity_quote": None,
            "volume": {"h24": "100"},
            "transactions": {"h24": {"buys": 10, "sells": 5}},
            "price_change": {"h24": "1"},
            "fdv": None,
            "market_cap": None,
            "pair_created_at_ms": 1,
        }
        return {
            "chain": "solana",
            "source": "dexscreener_token_pairs_v1",
            "mint": mint,
            "pairs_available": True,
            "pairs": [pair],
            "pair_count_observed": 1,
            "scope": "pair_scoped_dexscreener_observations",
            "freshness_verified": False,
            "solana_wide_coverage_verified": False,
            "aggregate_price_selected": False,
            "aggregate_liquidity_calculated": False,
            "aggregate_volume_calculated": False,
        }


class SolanaHistoryGateway(
    SolanaHistoricalCompareMixin,
    SolanaMarketReportMixin,
    SolanaAssetLookupMixin,
    BaseCMISGateway,
):
    pass


def make_gateway(
    *,
    ledger,
    clock,
    max_distance=3600,
    rpc=None,
    jupiter=None,
    dex=None,
):
    return SolanaHistoryGateway(
        solana_observation_ledger=ledger,
        solana_history_max_distance_seconds=max_distance,
        solana_history_clock=clock,
        solana_rpc_provider=rpc if rpc is not None else FakeRPCProvider(),
        solana_jupiter_provider=(
            jupiter if jupiter is not None else FakeJupiterProvider(["1", "1.2"])
        ),
        solana_dexscreener_provider=(
            dex if dex is not None else FakeDexProvider(["1.001", "1.201"])
        ),
        solana_price_max_relative_difference="0.01",
    )


def request(gateway, *, asset=MINT, params=None):
    return gateway.dispatch(
        {
            "service": "historical_compare",
            "chain": "solana",
            "asset": asset,
            "params": params
            if params is not None
            else {
                "metric": PRICE_USD,
                "period_seconds": DAY,
                "source": JUPITER_SOURCE,
            },
        }
    )


def seed_jupiter(ledger, *, price="1", collected_at=100000, verified=True):
    return ledger.store(
        {
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
            "value": price,
            "provider_observed_at": None,
            "provider_block_id": 1999,
            "provider_block_slot": None,
            "identity_verified": verified,
            "semantics_verified": verified,
            "freshness_verified": False,
        },
        collected_at=collected_at,
    )


class CMISSolanaHistoricalCompareTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.ledger = SolanaObservationLedger(
            os.path.join(self.tempdir.name, "solana-history.db")
        )
        self.clock = MutableClock(100000)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_runtime_composes_history_before_market_and_identity(self):
        self.assertTrue(issubclass(RuntimeCMISGateway, SolanaHistoricalCompareMixin))
        mro = RuntimeCMISGateway.__mro__
        self.assertLess(mro.index(SolanaHistoricalCompareMixin), mro.index(SolanaMarketReportMixin))
        self.assertLess(mro.index(SolanaHistoricalCompareMixin), mro.index(SolanaAssetLookupMixin))

    def test_missing_ledger_fails_before_provider_calls(self):
        rpc = FakeRPCProvider()
        jupiter = FakeJupiterProvider(["1"])
        dex = FakeDexProvider(["1"])
        gateway = make_gateway(
            ledger=None,
            clock=self.clock,
            rpc=rpc,
            jupiter=jupiter,
            dex=dex,
        )

        response = request(gateway)

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["warnings"][0]["code"], "solana_observation_ledger_not_configured")
        self.assertEqual(rpc.calls, [])
        self.assertEqual(jupiter.calls, [])
        self.assertEqual(dex.calls, [])

    def test_missing_distance_policy_fails_before_provider_calls(self):
        rpc = FakeRPCProvider()
        gateway = make_gateway(
            ledger=self.ledger,
            clock=self.clock,
            max_distance=None,
            rpc=rpc,
        )
        response = request(gateway)

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["warnings"][0]["code"], "solana_history_distance_policy_not_configured")
        self.assertEqual(rpc.calls, [])

    def test_distance_window_cannot_overlap_current_time(self):
        rpc = FakeRPCProvider()
        gateway = make_gateway(
            ledger=self.ledger,
            clock=self.clock,
            max_distance=DAY,
            rpc=rpc,
        )
        response = request(gateway)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_history_window_overlaps_current")
        self.assertEqual(rpc.calls, [])

    def test_metric_source_and_unknown_params_fail_before_provider_calls(self):
        cases = [
            {"metric": "liquidity_usd", "period_seconds": DAY, "source": JUPITER_SOURCE},
            {"metric": PRICE_USD, "period_seconds": DAY, "source": "dexscreener_token_pairs_v1"},
            {"metric": PRICE_USD, "period_seconds": 0, "source": JUPITER_SOURCE},
            {"metric": PRICE_USD, "period_seconds": DAY, "source": JUPITER_SOURCE, "max_distance_seconds": 999},
        ]
        for params in cases:
            with self.subTest(params=params):
                rpc = FakeRPCProvider()
                response = request(
                    make_gateway(ledger=self.ledger, clock=self.clock, rpc=rpc),
                    params=params,
                )
                self.assertEqual(response["status"], "error")
                self.assertEqual(rpc.calls, [])

    def test_first_request_seeds_history_but_does_not_compare_to_itself(self):
        gateway = make_gateway(ledger=self.ledger, clock=self.clock)
        response = request(gateway)

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["warnings"][0]["code"], "solana_historical_baseline_unavailable")
        self.assertEqual(response["data"]["current_value"], "1")
        self.assertEqual(response["data"]["timestamp_basis"], "collection_time")
        self.assertFalse(response["data"]["current_freshness_verified"])
        records = self.ledger.find(
            mint=MINT,
            metric=PRICE_USD,
            source=JUPITER_SOURCE,
            scope=JUPITER_SCOPE,
            subject_id=MINT,
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["observation"]["collected_at"], 100000.0)

    def test_second_request_compares_same_source_collection_exactly_one_day_later(self):
        gateway = make_gateway(ledger=self.ledger, clock=self.clock)
        first = request(gateway)
        self.assertEqual(first["status"], "unavailable")

        self.clock.value += DAY
        second = request(gateway)

        self.assertEqual(second["status"], "partial")
        data = second["data"]
        self.assertEqual(data["current_value"], "1.2")
        self.assertEqual(data["historical_value"], "1")
        self.assertEqual(data["absolute_change"], "0.2")
        self.assertEqual(data["change_pct"], "20")
        self.assertEqual(data["historical_distance_seconds"], 0.0)
        self.assertEqual(data["timestamp_basis"], "collection_time")
        self.assertTrue(data["source_consistency_verified"])
        self.assertTrue(data["scope_consistency_verified"])
        self.assertTrue(data["subject_consistency_verified"])
        self.assertTrue(data["comparison_semantics_verified"])
        self.assertFalse(data["provider_observation_time_verified"])
        self.assertFalse(data["cmis_promotable"])
        self.assertEqual(second["confidence"]["verified_checks"], 4)
        self.assertEqual(second["confidence"]["total_checks"], 7)

    def test_unverified_historical_observation_is_not_eligible_baseline(self):
        seed_jupiter(self.ledger, collected_at=100000, verified=False)
        self.clock.value = 100000 + DAY
        response = request(
            make_gateway(
                ledger=self.ledger,
                clock=self.clock,
                jupiter=FakeJupiterProvider(["1.2"]),
                dex=FakeDexProvider(["1.201"]),
            )
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["warnings"][0]["code"], "solana_historical_baseline_unavailable")

    def test_baseline_outside_distance_policy_is_unavailable(self):
        seed_jupiter(self.ledger, collected_at=100000 + 4000)
        self.clock.value = 100000 + DAY
        response = request(make_gateway(ledger=self.ledger, clock=self.clock))

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["warnings"][0]["code"], "solana_historical_baseline_unavailable")

    def test_current_cross_source_conflict_is_preserved_without_blocking_same_source_history(self):
        seed_jupiter(self.ledger, collected_at=100000)
        self.clock.value = 100000 + DAY
        response = request(
            make_gateway(
                ledger=self.ledger,
                clock=self.clock,
                jupiter=FakeJupiterProvider(["1.2"]),
                dex=FakeDexProvider(["2.0"]),
            )
        )

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["current_market_crosscheck_status"], "CONFLICT")
        self.assertFalse(response["data"]["cmis_promotable"])
        self.assertIn(
            "solana_current_price_cross_source_conflict",
            [warning["code"] for warning in response["warnings"]],
        )

    def test_symbol_input_fails_closed_and_does_not_seed_history(self):
        rpc = FakeRPCProvider()
        gateway = make_gateway(ledger=self.ledger, clock=self.clock, rpc=rpc)
        response = request(gateway, asset="USDC")

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["upstream_service"], "market_report")
        self.assertIn(
            "solana_asset_lookup_requires_exact_mint",
            [warning["code"] for warning in response["warnings"]],
        )
        self.assertEqual(rpc.calls, [])
        self.assertEqual(self.ledger.find(mint=MINT), [])

    def test_insufficient_market_crosscheck_propagates_without_seeding_history(self):
        rpc = FakeRPCProvider()
        dex = FakeDexProvider(["9"], role="quote")
        response = request(
            make_gateway(
                ledger=self.ledger,
                clock=self.clock,
                rpc=rpc,
                dex=dex,
            )
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["upstream_service"], "market_report")
        self.assertEqual(self.ledger.find(mint=MINT), [])

    def test_missing_jupiter_block_id_fails_closed_without_persistence(self):
        response = request(
            make_gateway(
                ledger=self.ledger,
                clock=self.clock,
                jupiter=FakeJupiterProvider(["1"], block_ids=[None]),
                dex=FakeDexProvider(["1.001"]),
            )
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_jupiter_block_contract_invalid")
        self.assertEqual(self.ledger.find(mint=MINT), [])

    def test_invalid_clock_fails_before_provider_calls(self):
        rpc = FakeRPCProvider()
        clock = MutableClock(float("nan"))
        response = request(
            make_gateway(
                ledger=self.ledger,
                clock=clock,
                rpc=rpc,
            )
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_history_clock_invalid")
        self.assertEqual(rpc.calls, [])


if __name__ == "__main__":
    unittest.main()
