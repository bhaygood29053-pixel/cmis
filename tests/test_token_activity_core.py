import unittest

from liquidity_scout.tokenomics import (
    extract_token_events,
    scale_raw_amount,
    summarize_token_events,
)


MINT = "MintA"


def parsed_ix(kind, *, mint=MINT, amount="1", checked=False):
    info = {
        "mint": mint,
        "account": "TokenAccountA",
        "authority": "AuthorityA",
    }
    if checked:
        info["tokenAmount"] = {"amount": amount}
    else:
        info["amount"] = amount
    return {
        "parsed": {
            "type": kind,
            "info": info,
        }
    }


def tx(*top, inner=None, err=None, block_time=1700000000):
    inner_groups = []
    if inner is not None:
        inner_groups.append({"index": 0, "instructions": list(inner)})
    return {
        "blockTime": block_time,
        "meta": {
            "err": err,
            "innerInstructions": inner_groups,
        },
        "transaction": {
            "message": {
                "instructions": list(top),
            }
        },
    }


def coverage(**overrides):
    value = {
        "signatures_scanned": 2,
        "transactions_retrieved": 2,
        "rpc_errors": 0,
        "selection_complete": True,
        "max_signatures": 2,
        "history_exhausted": False,
    }
    value.update(overrides)
    return value


class TokenActivityExtractionTests(unittest.TestCase):
    def test_extracts_top_level_and_inner_mint_burn_events(self):
        transaction = tx(
            parsed_ix("mintTo", amount="2500000"),
            parsed_ix("burnChecked", amount="500000", checked=True),
            inner=[
                parsed_ix("mintToChecked", amount="125000", checked=True),
                parsed_ix("burn", amount="25000"),
            ],
        )

        events = extract_token_events(transaction, MINT)

        self.assertEqual(
            [(event["kind"], event["raw_amount"]) for event in events],
            [
                ("mint", "2500000"),
                ("burn", "500000"),
                ("mint", "125000"),
                ("burn", "25000"),
            ],
        )
        self.assertEqual(events[0]["location"], "top:0")
        self.assertEqual(events[2]["location"], "inner:0:0")
        self.assertEqual(events[0]["block_time"], 1700000000)

    def test_wrong_mint_and_unrelated_instructions_are_ignored(self):
        transaction = tx(
            parsed_ix("mintTo", mint="OtherMint", amount="100"),
            parsed_ix("transfer", amount="100"),
            parsed_ix("burn", amount="50"),
        )

        events = extract_token_events(transaction, MINT)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "burn")
        self.assertEqual(events[0]["raw_amount"], "50")

    def test_failed_transaction_is_never_counted(self):
        transaction = tx(
            parsed_ix("mintTo", amount="100"),
            parsed_ix("burn", amount="50"),
            err={"InstructionError": [0, "Custom"]},
        )

        self.assertEqual(extract_token_events(transaction, MINT), [])

    def test_missing_success_metadata_is_never_counted(self):
        transaction = tx(parsed_ix("mintTo", amount="100"))
        del transaction["meta"]["err"]

        self.assertEqual(extract_token_events(transaction, MINT), [])

    def test_malformed_amount_is_not_coerced_to_zero(self):
        transaction = tx(
            parsed_ix("mintTo", amount="not-a-number"),
            parsed_ix("burn", amount="0"),
        )

        events = extract_token_events(transaction, MINT)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "burn")
        self.assertEqual(events[0]["raw_amount"], "0")


class TokenActivitySummaryTests(unittest.TestCase):
    def test_exact_scaling_handles_huge_and_signed_values(self):
        self.assertEqual(
            scale_raw_amount("123456789012345678901234567890", 9),
            "123456789012345678901.23456789",
        )
        self.assertEqual(scale_raw_amount("-1500000", 6), "-1.5")
        self.assertEqual(scale_raw_amount("0", 9), "0")
        self.assertEqual(scale_raw_amount(0, 9), "0")

    def test_verified_bounded_coverage_emits_net_issuance(self):
        events = [
            {"kind": "mint", "raw_amount": "2500000"},
            {"kind": "mint", "raw_amount": "500000"},
            {"kind": "burn", "raw_amount": "1250000"},
        ]

        report = summarize_token_events(
            events,
            mint=MINT,
            decimals=6,
            coverage=coverage(),
        )

        self.assertTrue(report["coverage_verified"])
        self.assertTrue(report["amounts_verified"])
        self.assertTrue(report["activity_verified"])
        self.assertEqual(report["minted_raw_observed"], "3000000")
        self.assertEqual(report["burned_raw_observed"], "1250000")
        self.assertEqual(report["minted_tokens_observed"], "3")
        self.assertEqual(report["burned_tokens_observed"], "1.25")
        self.assertEqual(report["net_issuance_raw"], "1750000")
        self.assertEqual(report["net_issuance_tokens"], "1.75")

    def test_rpc_gap_preserves_observed_totals_but_withholds_net(self):
        report = summarize_token_events(
            [
                {"kind": "mint", "raw_amount": "2000000"},
                {"kind": "burn", "raw_amount": "500000"},
            ],
            mint=MINT,
            decimals=6,
            coverage=coverage(
                transactions_retrieved=1,
                rpc_errors=1,
            ),
        )

        self.assertEqual(report["minted_tokens_observed"], "2")
        self.assertEqual(report["burned_tokens_observed"], "0.5")
        self.assertFalse(report["coverage_verified"])
        self.assertFalse(report["activity_verified"])
        self.assertIsNone(report["net_issuance_raw"])
        self.assertIsNone(report["net_issuance_tokens"])
        self.assertIn(
            "not retrieved",
            report["coverage_unverified_reason"],
        )

    def test_zero_and_negative_net_are_distinct_from_unavailable(self):
        zero_report = summarize_token_events(
            [],
            mint=MINT,
            decimals=6,
            coverage=coverage(
                signatures_scanned=0,
                transactions_retrieved=0,
                max_signatures=0,
            ),
        )
        self.assertTrue(zero_report["activity_verified"])
        self.assertEqual(zero_report["net_issuance_tokens"], "0")

        negative_report = summarize_token_events(
            [
                {"kind": "mint", "raw_amount": "1000000"},
                {"kind": "burn", "raw_amount": "2500000"},
            ],
            mint=MINT,
            decimals=6,
            coverage=coverage(),
        )
        self.assertEqual(negative_report["net_issuance_tokens"], "-1.5")

        unavailable_report = summarize_token_events(
            [{"kind": "mint", "raw_amount": "1000000"}],
            mint=MINT,
            decimals=None,
            coverage=coverage(),
        )
        self.assertFalse(unavailable_report["amounts_verified"])
        self.assertIsNone(unavailable_report["net_issuance_tokens"])

    def test_malformed_event_blocks_verified_net_issuance(self):
        report = summarize_token_events(
            [
                {"kind": "mint", "raw_amount": "1000000"},
                {"kind": "burn", "raw_amount": "bad"},
            ],
            mint=MINT,
            decimals=6,
            coverage=coverage(),
        )

        self.assertEqual(report["minted_tokens_observed"], "1")
        self.assertEqual(report["burned_tokens_observed"], "0")
        self.assertEqual(report["malformed_events"], 1)
        self.assertFalse(report["amounts_verified"])
        self.assertFalse(report["activity_verified"])
        self.assertIsNone(report["net_issuance_tokens"])


if __name__ == "__main__":
    unittest.main()
