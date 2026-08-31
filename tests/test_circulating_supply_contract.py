import unittest

from liquidity_scout.tokenomics.circulating_supply import (
    CIRCULATION_CONTRACT,
    build_circulating_supply_metrics,
)


MINT = "MintA"
SLOT = 123456


def evidence(**overrides):
    value = {
        "mint": MINT,
        "decimals": 6,
        "contract": CIRCULATION_CONTRACT,
        "contract_verified": True,
        "contract_source": "verified exclusion policy registry",
        "exclusion_universe_complete": True,
        "exclusion_universe_source": "complete exclusion inventory",
        "total_supply_verified": True,
        "total_supply_raw": "100000000",
        "total_supply_source": "X1 RPC getTokenSupply",
        "total_supply_observation_slot": 123456,
        "observation_slot": SLOT,
        "observed_at": 1700000000,
        "observation_time_verified": True,
        "source": "CMIS circulation evidence",
        "exclusions": [
            {
                "account": "ExcludedA",
                "mint": MINT,
                "raw_balance": "20000000",
                "account_identity_verified": True,
                "balance_verified": True,
                "circulation_exclusion_verified": True,
                "exclusion_reason": "verified_non_circulating_treasury",
                "observation_slot": SLOT,
                "source": "X1 RPC token account evidence A",
            },
            {
                "account": "ExcludedB",
                "mint": MINT,
                "raw_balance": "5000000",
                "account_identity_verified": True,
                "balance_verified": True,
                "circulation_exclusion_verified": True,
                "exclusion_reason": "verified_locked_non_circulating",
                "observation_slot": SLOT,
                "source": "X1 RPC token account evidence B",
            },
        ],
    }
    value.update(overrides)
    return value


_DEFAULT = object()


def build(value=_DEFAULT, **kwargs):
    params = {
        "mint": MINT,
        "decimals": 6,
        "current_total_raw": "100000000",
        "current_total_supply_verified": True,
        "current_total_observation_slot": SLOT,
        "current_total_source": "X1 RPC getTokenSupply",
    }
    params.update(kwargs)
    return build_circulating_supply_metrics(
        evidence() if value is _DEFAULT else value,
        **params,
    )


class CirculatingSupplyContractTests(unittest.TestCase):
    def test_complete_verified_exclusion_contract_computes_ratio(self):
        report = build()

        self.assertTrue(report["available"])
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["circulating_supply_verified"])
        self.assertTrue(report["current_total_supply_verified"])
        self.assertEqual(report["total_supply_raw"], "100000000")
        self.assertEqual(report["total_supply"], "100")
        self.assertEqual(report["excluded_supply_raw"], "25000000")
        self.assertEqual(report["excluded_supply"], "25")
        self.assertEqual(report["circulating_supply_raw"], "75000000")
        self.assertEqual(report["circulating_supply"], "75")
        self.assertEqual(report["circulating_to_total_supply_ratio"], "0.75")
        self.assertEqual(report["ratio_state"], "AVAILABLE")
        self.assertEqual(report["exclusion_count"], 2)
        self.assertEqual(report["observation_slot"], SLOT)
        self.assertEqual(report["observed_at"], 1700000000)
        self.assertTrue(report["observation_time_verified"])

    def test_empty_complete_exclusion_universe_allows_full_circulation(self):
        report = build(evidence(exclusions=[]))

        self.assertTrue(report["circulating_supply_verified"])
        self.assertEqual(report["excluded_supply_raw"], "0")
        self.assertEqual(report["circulating_supply_raw"], "100000000")
        self.assertEqual(report["circulating_to_total_supply_ratio"], "1")

    def test_zero_total_supply_has_null_ratio_not_infinity(self):
        report = build(
            evidence(
                total_supply_raw="0",
                exclusions=[],
            ),
            current_total_raw="0",
        )

        self.assertTrue(report["circulating_supply_verified"])
        self.assertEqual(report["circulating_supply"], "0")
        self.assertIsNone(report["circulating_to_total_supply_ratio"])
        self.assertEqual(report["ratio_state"], "ZERO_TOTAL_SUPPLY")

    def test_missing_contract_does_not_infer_from_total_supply(self):
        report = build(None)

        self.assertFalse(report["circulating_supply_verified"])
        self.assertTrue(report["current_total_supply_verified"])
        self.assertEqual(report["total_supply_raw"], "100000000")
        self.assertEqual(report["total_supply"], "100")
        self.assertEqual(report["current_total_source"], "X1 RPC getTokenSupply")
        self.assertEqual(
            report["reason"],
            "circulating_supply_contract_not_supplied",
        )
        self.assertIsNone(report["circulating_supply"])

    def test_incomplete_exclusion_universe_fails_closed(self):
        report = build(
            evidence(exclusion_universe_complete=False)
        )

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_exclusion_universe_incomplete",
        )

    def test_missing_rpc_total_supply_slot_fails_closed(self):
        report = build(
            current_total_observation_slot=None,
        )

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "current_total_supply_slot_unverified",
        )

    def test_rpc_total_supply_slot_must_match_exclusion_snapshot(self):
        report = build(
            current_total_observation_slot=SLOT + 1,
        )

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_rpc_total_supply_slot_mismatch",
        )

    def test_total_supply_observation_slot_must_match(self):
        report = build(
            evidence(total_supply_observation_slot=SLOT + 1)
        )

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_total_supply_slot_mismatch",
        )

    def test_total_supply_mismatch_fails_closed(self):
        report = build(
            evidence(total_supply_raw="99999999")
        )

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_total_supply_mismatch",
        )

    def test_duplicate_exclusion_account_fails_closed(self):
        value = evidence()
        value["exclusions"] = [
            dict(value["exclusions"][0]),
            dict(value["exclusions"][0]),
        ]

        report = build(value)

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_exclusion_account_invalid",
        )

    def test_exclusion_slot_mismatch_fails_closed(self):
        value = evidence()
        value["exclusions"] = [dict(value["exclusions"][0])]
        value["exclusions"][0]["observation_slot"] = SLOT + 1

        report = build(value)

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_exclusion_slot_mismatch",
        )

    def test_unverified_exclusion_semantics_fail_closed(self):
        value = evidence()
        value["exclusions"] = [dict(value["exclusions"][0])]
        value["exclusions"][0]["circulation_exclusion_verified"] = False

        report = build(value)

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_exclusion_semantics_unverified",
        )

    def test_exclusions_cannot_exceed_current_total_supply(self):
        value = evidence()
        value["exclusions"] = [dict(value["exclusions"][0])]
        value["exclusions"][0]["raw_balance"] = "100000001"

        report = build(value)

        self.assertFalse(report["circulating_supply_verified"])
        self.assertEqual(
            report["reason"],
            "circulating_supply_exclusions_exceed_total_supply",
        )

    def test_unverified_observation_time_is_withheld_but_slot_can_verify(self):
        report = build(
            evidence(
                observed_at=1700000000,
                observation_time_verified=False,
            )
        )

        self.assertTrue(report["circulating_supply_verified"])
        self.assertIsNone(report["observed_at"])
        self.assertFalse(report["observation_time_verified"])


if __name__ == "__main__":
    unittest.main()
