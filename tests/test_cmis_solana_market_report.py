import unittest

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.cmis.solana_market_gateway import SolanaMarketReportMixin
from liquidity_scout.providers.solana.dexscreener import DexScreenerSourceError
from liquidity_scout.providers.solana.jupiter import JupiterSourceError
from liquidity_scout.providers.solana.rpc import SPL_TOKEN_PROGRAM_ID

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PAIR_A = "9wFFmGphT3QHkVbMvE8q2w4P5Y6L7N8R9S1T2U3V4W5"
PAIR_B = "8vEEmGphT3QHkVbMvE8q2w4P5Y6L7N8R9S1T2U3V4W5"
QUOTE = "So11111111111111111111111111111111111111112"


class FakeRPCProvider:
    chain = "solana"

    def __init__(self):
        self.calls = []
        self.freshness_calls = []

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

    def get_block_time(self, block_id):
        self.freshness_calls.append(("getBlockTime", block_id))
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getBlockTime",
            "block_id": block_id,
            "block_time_available": True,
            "block_time_unix": 1900,
            "block_time_verified": True,
            "finality_verified": False,
        }

    def get_slot(self):
        self.freshness_calls.append(("getSlot", "confirmed"))
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getSlot",
            "slot": 2100,
            "commitment": "confirmed",
            "slot_verified": True,
        }


class FakeJupiterProvider:
    chain = "solana"

    def __init__(self, *, price="1", error=None, available=True):
        self.price = price
        self.error = error
        self.available = available
        self.calls = []

    def get_price(self, mint):
        self.calls.append(mint)
        if self.error is not None:
            raise self.error
        if not self.available:
            return {
                "chain": "solana",
                "source": "jupiter_price_v3",
                "mint": mint,
                "price_available": False,
                "reason": "jupiter_price_unavailable",
                "freshness_verified": False,
            }
        return {
            "chain": "solana",
            "source": "jupiter_price_v3",
            "mint": mint,
            "price_available": True,
            "usd_price": self.price,
            "currency": "USD",
            "block_id": 2000,
            "decimals": 6,
            "token_created_at": None,
            "liquidity_usd_source_value": "999999",
            "price_change_24h_percent_source_value": "3.5",
            "scope": "jupiter_price_v3",
            "collection_started_at_unix": 2000.0,
            "collection_completed_at_unix": 2001.0,
            "collection_time_verified": True,
            "observed_at": None,
            "freshness_verified": False,
        }


class FakeDexProvider:
    chain = "solana"

    def __init__(self, *, pairs=None, error=None):
        self.pairs = pairs if pairs is not None else [pair_record(PAIR_A, price="1.005")]
        self.error = error
        self.calls = []

    def get_token_pairs(self, mint):
        self.calls.append(mint)
        if self.error is not None:
            raise self.error
        return {
            "chain": "solana",
            "source": "dexscreener_token_pairs_v1",
            "mint": mint,
            "pairs_available": bool(self.pairs),
            "pairs": [dict(item) for item in self.pairs],
            "pair_count_observed": len(self.pairs),
            "scope": "pair_scoped_dexscreener_observations",
            "collection_started_at_unix": 2001.0,
            "collection_completed_at_unix": 2002.0,
            "collection_time_verified": True,
            "freshness_verified": False,
            "solana_wide_coverage_verified": False,
            "aggregate_price_selected": False,
            "aggregate_liquidity_calculated": False,
            "aggregate_volume_calculated": False,
        }


def pair_record(
    address,
    *,
    price="1.005",
    requested_role="base",
    liquidity="1000",
    volume="250",
):
    is_base = requested_role == "base"
    return {
        "pair_address": address,
        "dex_id": "testdex",
        "base_token": {
            "address": MINT if is_base else QUOTE,
            "name": "Token",
            "symbol": "TOK",
        },
        "quote_token": {
            "address": QUOTE if is_base else MINT,
            "name": "Quote",
            "symbol": "Q",
        },
        "requested_mint_role": requested_role,
        "price_subject_address": MINT if is_base else QUOTE,
        "price_is_for_requested_mint": is_base,
        "price_usd": price,
        "price_native": None,
        "liquidity_usd": liquidity,
        "liquidity_base": None,
        "liquidity_quote": None,
        "volume": {"h24": volume},
        "transactions": {"h24": {"buys": 10, "sells": 8}},
        "price_change": {"h24": "2.5"},
        "fdv": None,
        "market_cap": None,
        "pair_created_at_ms": 123456789,
    }


class SolanaMarketGateway(
    SolanaMarketReportMixin,
    SolanaAssetLookupMixin,
    BaseCMISGateway,
):
    pass


def gateway(*, rpc=None, jupiter=None, dex=None, tolerance="0.01"):
    return SolanaMarketGateway(
        solana_rpc_provider=rpc if rpc is not None else FakeRPCProvider(),
        solana_jupiter_provider=jupiter,
        solana_dexscreener_provider=dex,
        solana_price_max_relative_difference=tolerance,
    )


def request(subject, *, asset=MINT, params=None):
    payload = {
        "service": "market_report",
        "chain": "solana",
        "asset": asset,
    }
    if params is not None:
        payload["params"] = params
    return subject.dispatch(payload)


class CMISSolanaMarketReportTests(unittest.TestCase):
    def test_runtime_composes_market_before_other_solana_layers(self):
        self.assertTrue(issubclass(RuntimeCMISGateway, SolanaMarketReportMixin))
        mro = RuntimeCMISGateway.__mro__
        self.assertLess(mro.index(SolanaMarketReportMixin), mro.index(SolanaAssetLookupMixin))

    def test_agreement_is_partial_and_never_promoted_to_verified_price(self):
        rpc = FakeRPCProvider()
        jupiter = FakeJupiterProvider(price="1")
        dex = FakeDexProvider(pairs=[pair_record(PAIR_A, price="1.005")])
        response = request(gateway(rpc=rpc, jupiter=jupiter, dex=dex))

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"], {"chain": "solana", "mint": MINT})
        self.assertEqual(response["data"]["price_usd_source_value"], "1")
        self.assertFalse(response["data"]["price_verified"])
        crosscheck = response["data"]["price_crosscheck"]
        self.assertEqual(crosscheck["status"], AGREEMENT)
        self.assertFalse(crosscheck["cmis_promotable"])
        self.assertFalse(crosscheck["freshness_verified"])
        self.assertFalse(crosscheck["observation_scope_verified"])
        self.assertIsNone(response["data"]["asset_wide_liquidity_usd"])
        self.assertFalse(response["data"]["asset_wide_liquidity_verified"])
        self.assertIsNone(response["data"]["asset_wide_volume_24h_usd"])
        self.assertFalse(response["data"]["asset_wide_volume_24h_verified"])
        self.assertEqual(rpc.calls, [MINT])
        self.assertEqual(jupiter.calls, [MINT])
        self.assertEqual(dex.calls, [MINT])

    def test_jupiter_block_time_is_exposed_without_shared_freshness_promotion(self):
        rpc = FakeRPCProvider()
        response = request(
            gateway(
                rpc=rpc,
                jupiter=FakeJupiterProvider(price="1"),
                dex=FakeDexProvider(),
            )
        )

        freshness = response["data"]["market_freshness"]
        self.assertTrue(freshness["jupiter"]["block_id_semantics_verified"])
        self.assertTrue(freshness["jupiter"]["block_time_verified"])
        self.assertTrue(freshness["jupiter"]["provider_fact_time_verified"])
        self.assertEqual(freshness["jupiter"]["provider_fact_time_unix"], 1900)
        self.assertEqual(freshness["jupiter"]["fact_age_seconds_candidate"], 101.0)
        self.assertEqual(freshness["jupiter"]["reference_commitment"], "confirmed")
        self.assertFalse(freshness["jupiter"]["finality_verified"])
        self.assertFalse(freshness["dexscreener"]["provider_fact_time_verified"])
        self.assertFalse(freshness["cross_source_time_identity_verified"])
        self.assertFalse(freshness["freshness_policy_complete"])
        self.assertFalse(freshness["freshness_verified"])
        self.assertFalse(freshness["current_price_promotable"])
        self.assertFalse(response["data"]["price_verified"])
        self.assertEqual(
            rpc.freshness_calls,
            [("getBlockTime", 2000), ("getSlot", "confirmed")],
        )

    def test_pair_observations_preserve_scope_with_bounded_observed_pair_aggregation(self):
        dex = FakeDexProvider(
            pairs=[
                pair_record(PAIR_A, price="1.001", liquidity="1000", volume="250"),
                pair_record(PAIR_B, price="0.999", liquidity="2000", volume="500"),
            ]
        )
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        observations = response["data"]["pair_observations"]
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0]["liquidity_usd"], "1000")
        self.assertEqual(observations[1]["liquidity_usd"], "2000")
        self.assertEqual(observations[0]["volume_24h"], "250")
        self.assertEqual(observations[1]["volume_24h"], "500")
        self.assertEqual(response["data"]["observed_pair_count"], 2)
        self.assertEqual(response["data"]["#LPs"], 2)
        self.assertEqual(response["data"]["observed_pair_liquidity_usd"], "3000")
        self.assertEqual(response["data"]["observed_pair_volume_24h_usd"], "750")
        self.assertNotIn("liquidity_usd", response["data"])
        self.assertNotIn("volume_24h_usd", response["data"])
        aggregate = response["data"]["observed_pair_aggregation"]
        self.assertTrue(aggregate["pair_identity_deduplicated"])
        self.assertTrue(aggregate["liquidity_rows_complete"])
        self.assertTrue(aggregate["volume_rows_complete"])
        self.assertFalse(aggregate["pair_universe_complete"])
        self.assertFalse(aggregate["asset_wide_liquidity_verified"])
        self.assertFalse(aggregate["asset_wide_volume_verified"])
        self.assertFalse(aggregate["market_source_independence_verified"])
        self.assertIsNone(response["data"]["asset_wide_liquidity_usd"])
        self.assertIsNone(response["data"]["asset_wide_volume_24h_usd"])

    def test_missing_pair_metric_is_not_zero_and_marks_observed_subtotal_partial(self):
        complete = pair_record(
            PAIR_A,
            price="1.001",
            liquidity="1000",
            volume="250",
        )
        missing = pair_record(
            PAIR_B,
            price="0.999",
            liquidity=None,
            volume=None,
        )
        dex = FakeDexProvider(pairs=[complete, missing])
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["data"]["observed_pair_count"], 2)
        self.assertEqual(response["data"]["observed_pair_liquidity_usd"], "1000")
        self.assertEqual(response["data"]["observed_pair_volume_24h_usd"], "250")
        aggregate = response["data"]["observed_pair_aggregation"]
        self.assertFalse(aggregate["liquidity_rows_complete"])
        self.assertFalse(aggregate["volume_rows_complete"])
        self.assertEqual(aggregate["liquidity_value_pair_count"], 1)
        self.assertEqual(aggregate["volume_24h_value_pair_count"], 1)
        codes = {item["code"] for item in response["warnings"]}
        self.assertIn("solana_observed_pair_liquidity_partial", codes)
        self.assertIn("solana_observed_pair_volume_partial", codes)

    def test_exact_duplicate_pair_identity_is_counted_once(self):
        first = pair_record(
            PAIR_A,
            price="1.001",
            liquidity="1000",
            volume="250",
        )
        dex = FakeDexProvider(pairs=[first, dict(first)])
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["data"]["pair_count_observed"], 2)
        self.assertEqual(response["data"]["observed_pair_count"], 1)
        self.assertEqual(response["data"]["#LPs"], 1)
        self.assertEqual(response["data"]["observed_pair_liquidity_usd"], "1000")
        self.assertEqual(response["data"]["observed_pair_volume_24h_usd"], "250")
        aggregate = response["data"]["observed_pair_aggregation"]
        self.assertEqual(aggregate["duplicate_pair_addresses"], [PAIR_A])
        self.assertEqual(aggregate["conflicting_duplicate_pair_addresses"], [])

    def test_conflicting_duplicate_pair_is_excluded_fail_closed(self):
        first = pair_record(
            PAIR_A,
            price="1.001",
            liquidity="1000",
            volume="250",
        )
        second = pair_record(
            PAIR_A,
            price="1.001",
            liquidity="2000",
            volume="500",
        )
        dex = FakeDexProvider(pairs=[first, second])
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["data"]["observed_pair_count"], 0)
        self.assertEqual(response["data"]["#LPs"], 0)
        self.assertIsNone(response["data"]["observed_pair_liquidity_usd"])
        self.assertIsNone(response["data"]["observed_pair_volume_24h_usd"])
        aggregate = response["data"]["observed_pair_aggregation"]
        self.assertEqual(
            aggregate["conflicting_duplicate_pair_addresses"],
            [PAIR_A],
        )
        self.assertFalse(aggregate["liquidity_rows_complete"])
        self.assertFalse(aggregate["volume_rows_complete"])

    def test_wrong_mint_pair_is_excluded_from_observed_pair_aggregate(self):
        wrong = pair_record(PAIR_A, price="1.001", liquidity="1000", volume="250")
        wrong["base_token"] = {
            "address": "WrongBaseMint",
            "name": "Wrong",
            "symbol": "WRONG",
        }
        wrong["quote_token"] = {
            "address": "WrongQuoteMint",
            "name": "Wrong quote",
            "symbol": "WQ",
        }
        dex = FakeDexProvider(pairs=[wrong])
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["data"]["observed_pair_count"], 0)
        self.assertEqual(response["data"]["#LPs"], 0)
        self.assertIsNone(response["data"]["observed_pair_liquidity_usd"])
        self.assertIsNone(response["data"]["observed_pair_volume_24h_usd"])
        self.assertEqual(
            response["data"]["observed_pair_aggregation"]["pair_rows_excluded"],
            1,
        )

    def test_malformed_numeric_metric_is_not_coerced_into_aggregate(self):
        malformed = pair_record(
            PAIR_A,
            price="1.001",
            liquidity="not-a-number",
            volume="-1",
        )
        dex = FakeDexProvider(pairs=[malformed])
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["data"]["observed_pair_count"], 1)
        self.assertIsNone(response["data"]["observed_pair_liquidity_usd"])
        self.assertIsNone(response["data"]["observed_pair_volume_24h_usd"])
        aggregate = response["data"]["observed_pair_aggregation"]
        self.assertFalse(aggregate["liquidity_rows_complete"])
        self.assertFalse(aggregate["volume_rows_complete"])

    def test_one_outlier_pair_makes_crosscheck_conflict_without_cherry_picking(self):
        dex = FakeDexProvider(
            pairs=[
                pair_record(PAIR_A, price="1.001"),
                pair_record(PAIR_B, price="1.2"),
            ]
        )
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["price_crosscheck"]["status"], CONFLICT)
        self.assertFalse(response["data"]["price_verified"])
        self.assertEqual(
            len(response["data"]["price_crosscheck"]["comparisons"]),
            2,
        )
        self.assertIn(
            "solana_price_cross_source_conflict",
            [item["code"] for item in response["warnings"]],
        )

    def test_quote_only_pair_price_is_not_reassigned_to_requested_mint(self):
        dex = FakeDexProvider(
            pairs=[pair_record(PAIR_A, requested_role="quote", price="9")]
        )
        response = request(
            gateway(jupiter=FakeJupiterProvider(price="1"), dex=dex)
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["data"]["price_crosscheck"]["status"],
            INSUFFICIENT_EVIDENCE,
        )
        observation = response["data"]["pair_observations"][0]
        self.assertEqual(observation["requested_mint_role"], "quote")
        self.assertFalse(observation["price_is_for_requested_mint"])
        self.assertFalse(response["data"]["price_verified"])

    def test_jupiter_source_liquidity_is_not_promoted_to_asset_wide_liquidity(self):
        response = request(
            gateway(
                jupiter=FakeJupiterProvider(price="1"),
                dex=FakeDexProvider(),
            )
        )

        self.assertNotEqual(
            response["data"]["asset_wide_liquidity_usd"],
            "999999",
        )
        self.assertIsNone(response["data"]["asset_wide_liquidity_usd"])

    def test_symbol_input_fails_closed_before_any_market_call(self):
        rpc = FakeRPCProvider()
        jupiter = FakeJupiterProvider()
        dex = FakeDexProvider()
        response = request(
            gateway(rpc=rpc, jupiter=jupiter, dex=dex),
            asset="USDC",
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["upstream_service"], "asset_lookup")
        self.assertEqual(rpc.calls, [])
        self.assertEqual(jupiter.calls, [])
        self.assertEqual(dex.calls, [])

    def test_missing_market_provider_fails_closed(self):
        rpc = FakeRPCProvider()
        response = request(
            gateway(rpc=rpc, jupiter=None, dex=FakeDexProvider())
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "solana_jupiter_provider_not_configured",
        )
        self.assertEqual(rpc.calls, [MINT])

    def test_missing_tolerance_does_not_query_market_providers(self):
        rpc = FakeRPCProvider()
        jupiter = FakeJupiterProvider()
        dex = FakeDexProvider()
        response = request(
            gateway(
                rpc=rpc,
                jupiter=jupiter,
                dex=dex,
                tolerance=None,
            )
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "solana_price_crosscheck_policy_not_configured",
        )
        self.assertEqual(jupiter.calls, [])
        self.assertEqual(dex.calls, [])

    def test_nonempty_params_fail_before_any_provider_call(self):
        rpc = FakeRPCProvider()
        jupiter = FakeJupiterProvider()
        dex = FakeDexProvider()
        response = request(
            gateway(rpc=rpc, jupiter=jupiter, dex=dex),
            params={"max_relative_difference": "0.01"},
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "solana_market_report_params_not_supported",
        )
        self.assertEqual(rpc.calls, [])
        self.assertEqual(jupiter.calls, [])
        self.assertEqual(dex.calls, [])

    def test_jupiter_exception_text_is_not_reflected(self):
        secret = "https://jupiter.invalid/?api-key=SECRET"
        jupiter = FakeJupiterProvider(
            error=JupiterSourceError(f"failed at {secret}")
        )
        response = request(gateway(jupiter=jupiter, dex=FakeDexProvider()))

        self.assertEqual(response["status"], "unavailable")
        self.assertNotIn(secret, str(response))

    def test_dex_exception_text_is_not_reflected(self):
        secret = "https://dex.invalid/?secret=SECRET"
        dex = FakeDexProvider(
            error=DexScreenerSourceError(f"failed at {secret}")
        )
        response = request(gateway(jupiter=FakeJupiterProvider(), dex=dex))

        self.assertEqual(response["status"], "unavailable")
        self.assertNotIn(secret, str(response))

    def test_invalid_tolerance_configuration_is_rejected(self):
        for value in (-0.1, 1.1, True, "nan", "not-a-number"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    gateway(
                        jupiter=FakeJupiterProvider(),
                        dex=FakeDexProvider(),
                        tolerance=value,
                    )


if __name__ == "__main__":
    unittest.main()
