"""Opt-in read-only XNT positive-balance population evidence."""

import json
import os
import time
import unittest

from liquidity_scout.providers.x1.positive_balance_population_evidence import (
    evaluate_x1_positive_balance_population_bracket,
    verify_x1_positive_balance_population_series,
)
from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    fetch_token_accounts_by_mint_raw,
)
from liquidity_scout.providers.x1.rpc_token_supply import fetch_token_supply_raw


RUN_LIVE = os.getenv("RUN_X1_POSITIVE_BALANCE_POPULATION_LIVE") == "1"
XNT_MINT = "So11111111111111111111111111111111111111112"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_POSITIVE_BALANCE_POPULATION_LIVE=1 to run read-only evidence",
)
class X1PositiveBalancePopulationLiveTests(unittest.TestCase):
    def test_repeated_xnt_supply_conservation_population_evidence(self):
        observations = []

        for index in range(3):
            supply_before = fetch_token_supply_raw(XNT_MINT)
            enumeration = fetch_token_accounts_by_mint_raw(
                XNT_MINT,
                token_program_id=TOKEN_PROGRAM,
            )
            supply_after = fetch_token_supply_raw(XNT_MINT)
            observation = evaluate_x1_positive_balance_population_bracket(
                enumeration,
                supply_before,
                supply_after,
                max_bracket_span=100,
            )
            observations.append(observation)

            summary = {
                "index": index,
                "status": observation["status"],
                "enumeration_slot": observation["enumeration_slot"],
                "supply_before_slot": observation["supply_before_slot"],
                "supply_after_slot": observation["supply_after_slot"],
                "supply_bracket_span": observation["supply_bracket_span"],
                "mint_supply_stable_across_bracket": observation[
                    "mint_supply_stable_across_bracket"
                ],
                "supply_conservation_observed": observation[
                    "supply_conservation_observed"
                ],
                "positive_balance_token_account_count": observation[
                    "positive_balance_token_account_count"
                ],
                "unique_positive_balance_authority_address_count": observation[
                    "unique_positive_balance_authority_address_count"
                ],
                "authority_address_distribution": observation[
                    "authority_address_distribution"
                ],
                "positive_balance_population_candidate_complete": observation[
                    "positive_balance_population_candidate_complete"
                ],
                "errors": observation["errors"],
            }
            print(
                "[XNT positive-balance population observation] "
                + json.dumps(summary, sort_keys=True)
            )
            if index < 2:
                time.sleep(2)

        series = verify_x1_positive_balance_population_series(observations)
        print(
            "[XNT positive-balance population series] "
            + json.dumps(series, sort_keys=True)
        )

        self.assertEqual(series["observation_count"], 3)
        self.assertFalse(series["holder_semantics_verified"])
        self.assertFalse(series["beneficial_owner_identity_verified"])
        self.assertFalse(series["cmis_promotable"])
        self.assertFalse(series["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
