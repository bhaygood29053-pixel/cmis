import os
import tempfile
import unittest

from liquidity_scout.cmis.solana_observation_ledger import (
    DEX_PAIR_SCOPE,
    DEX_SOURCE,
    JUPITER_SCOPE,
    JUPITER_SOURCE,
    LIQUIDITY_USD,
    PRICE_USD,
    SolanaObservationLedger,
    sanitize_solana_observation,
)

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"
PAIR = "11111111111111111111111111111111"


def jupiter(*, identity=True, semantics=True, value="1"):
    return {
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
        "value": value,
        "provider_observed_at": None,
        "provider_block_id": 10,
        "provider_block_slot": None,
        "identity_verified": identity,
        "semantics_verified": semantics,
        "freshness_verified": False,
    }


class SolanaObservationLedgerTrustTests(unittest.TestCase):
    def test_nearest_ignores_closer_unverified_identity_and_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SolanaObservationLedger(os.path.join(directory, "history.db"))
            ledger.store(jupiter(value="0.9"), collected_at=900)
            ledger.store(jupiter(identity=False, value="1.0"), collected_at=999)
            ledger.store(jupiter(semantics=False, value="1.1"), collected_at=1000)

            result = ledger.nearest(
                mint=MINT,
                metric=PRICE_USD,
                source=JUPITER_SOURCE,
                scope=JUPITER_SCOPE,
                subject_id=MINT,
                target_time=1000,
                max_distance_seconds=200,
            )

            self.assertIsNotNone(result)
            self.assertEqual(result["observation"]["value"], "0.9")
            self.assertTrue(result["observation"]["identity_verified"])
            self.assertTrue(result["observation"]["semantics_verified"])

    def test_verified_zero_pair_liquidity_is_preserved_as_explicit_zero(self):
        safe = sanitize_solana_observation(
            {
                "chain": "solana",
                "mint": MINT,
                "metric": LIQUIDITY_USD,
                "source": DEX_SOURCE,
                "scope": DEX_PAIR_SCOPE,
                "subject_id": PAIR,
                "pair_address": PAIR,
                "requested_mint_role": "base",
                "base_mint": MINT,
                "quote_mint": QUOTE,
                "value": "0.0000",
                "provider_observed_at": None,
                "provider_block_id": None,
                "provider_block_slot": None,
                "identity_verified": True,
                "semantics_verified": True,
                "freshness_verified": False,
            },
            collected_at=1000,
        )
        self.assertEqual(safe["value"], "0")


if __name__ == "__main__":
    unittest.main()
