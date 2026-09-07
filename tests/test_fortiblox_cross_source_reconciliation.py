import unittest

from liquidity_scout.providers.x1.fortiblox_cross_source_reconciliation import (
    AGREE,
    CONTRACT_VERSION,
    DISAGREE,
    EVIDENCE_INCOMPLETE,
    NOT_COMPARABLE,
    SCOPE_MISMATCH,
    FortiBloxCrossSourceReconciliationError,
    accepted_fortiblox_token_field_evidence,
    reconcile_fortiblox_cross_source,
)
from liquidity_scout.providers.x1.fortiswap import normalize_tokens_response


MINT = "Token111111111111111111111111111111111111111"


def fortiblox(*, price=1.0, volume=1000.0, sources=None):
    return normalize_tokens_response(
        {
            "updatedAt": 1788770000000,
            "refreshing": False,
            "warming": False,
            "tokens": [
                {
                    "mint": MINT,
                    "symbol": "TST",
                    "name": "Test",
                    "decimals": 9,
                    "priceUsd": price,
                    "volume24hUsd": volume,
                    "sources": list(sources or []),
                    "trust": "verified",
                }
            ],
            "errors": [],
        }
    )


def reference(
    source_id,
    *,
    price=1.0,
    price_semantics=True,
    price_freshness=True,
    price_comparable=True,
    volume=1000.0,
    volume_semantics=True,
    volume_freshness=True,
    volume_comparable=True,
    volume_window_seconds=86400,
    volume_scope_id="x1:TST:exact-current-pool-universe",
    cmis_verified=False,
    source_independence_verified=False,
):
    return {
        "source_id": source_id,
        "mint": MINT,
        "price_usd": price,
        "price_comparable": price_comparable,
        "price_semantics_verified": price_semantics,
        "price_freshness_verified": price_freshness,
        "price_observed_at_ms": 1788770000000,
        "volume_24h_usd": volume,
        "volume_comparable": volume_comparable,
        "volume_semantics_verified": volume_semantics,
        "volume_freshness_verified": volume_freshness,
        "volume_window_seconds": volume_window_seconds,
        "volume_scope_id": volume_scope_id,
        "cmis_verified": cmis_verified,
        "source_independence_verified": source_independence_verified,
        "execution_authorized": False,
    }


def fully_comparable_fortiblox_evidence():
    return {
        "price_semantics_verified": True,
        "price_freshness_verified": True,
        "volume_semantics_verified": True,
        "volume_freshness_verified": True,
        "volume_window_seconds": 86400,
        "volume_scope_id": "x1:TST:exact-current-pool-universe",
        "execution_authorized": False,
    }


class FortiBloxCrossSourceReconciliationTests(unittest.TestCase):
    def test_default_accepted_boundary_allows_price_comparison_not_volume_promotion(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(
                price=1.0,
                volume=1000,
                sources=["xdex"],
            ),
            references=[
                reference(
                    "xdex",
                    price=1.003,
                    volume_comparable=False,
                )
            ],
            fortiblox_field_evidence=accepted_fortiblox_token_field_evidence(),
        )

        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        row = result["reconciliations"][0]
        self.assertEqual(row["price"]["state"], AGREE)
        self.assertFalse(row["price"]["current_fact_corroboration"])
        self.assertEqual(row["volume_24h_usd"]["state"], NOT_COMPARABLE)
        self.assertTrue(row["upstream_overlap_with_fortiblox"])
        self.assertFalse(row["source_independence_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["fortiblox_cmis_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_exact_volume_scope_can_reconcile_when_separately_proven(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(price=1.0, volume=1000),
            references=[
                reference(
                    "x1_ninja",
                    price=0.999,
                    volume=1005,
                )
            ],
            fortiblox_field_evidence=fully_comparable_fortiblox_evidence(),
        )

        row = result["reconciliations"][0]
        self.assertEqual(row["price"]["state"], AGREE)
        self.assertTrue(row["price"]["current_fact_corroboration"])
        self.assertEqual(row["volume_24h_usd"]["state"], AGREE)
        self.assertTrue(row["volume_24h_usd"]["current_fact_corroboration"])
        self.assertEqual(result["overall_state"], "CORROBORATED")
        self.assertEqual(result["agreement_count"], 2)
        self.assertEqual(result["current_fact_corroboration_count"], 2)
        self.assertFalse(result["cmis_verification_promoted_from_agreement"])

    def test_material_price_disagreement_is_preserved_and_cmis_authority_wins(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(price=1.0, volume=1000),
            references=[
                reference(
                    "cmis",
                    price=1.10,
                    volume=1000,
                    cmis_verified=True,
                )
            ],
            fortiblox_field_evidence=fully_comparable_fortiblox_evidence(),
        )

        row = result["reconciliations"][0]
        self.assertEqual(row["price"]["state"], DISAGREE)
        self.assertEqual(
            row["price"]["reason"],
            "material_price_disagreement",
        )
        self.assertTrue(row["reference_cmis_verified"])
        self.assertTrue(row["cmis_authority_preserved"])
        self.assertTrue(result["cmis_reference_authoritative"])
        self.assertEqual(result["overall_state"], "DISAGREEMENT")
        self.assertEqual(
            result["disagreements"][0]["source_id"],
            "cmis",
        )
        self.assertFalse(result["fortiblox_cmis_verified"])
        self.assertFalse(result["risk_conclusion_authorized"])

    def test_unverified_reference_price_semantics_is_incomplete(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(),
            references=[
                reference(
                    "xdex",
                    price_semantics=False,
                    volume_comparable=False,
                )
            ],
            fortiblox_field_evidence=accepted_fortiblox_token_field_evidence(),
        )

        price = result["reconciliations"][0]["price"]
        self.assertEqual(price["state"], EVIDENCE_INCOMPLETE)
        self.assertEqual(
            price["reason"],
            "reference_price_semantics_not_verified",
        )
        self.assertEqual(result["overall_state"], "EVIDENCE_INCOMPLETE")

    def test_volume_scope_mismatch_fails_closed_without_numeric_comparison(self):
        ref = reference(
            "x1_ninja",
            volume=1000,
            volume_scope_id="x1:TST:other-pool-universe",
        )
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(),
            references=[ref],
            fortiblox_field_evidence=fully_comparable_fortiblox_evidence(),
        )

        volume = result["reconciliations"][0]["volume_24h_usd"]
        self.assertEqual(volume["state"], SCOPE_MISMATCH)
        self.assertEqual(volume["reason"], "volume_scope_id_not_aligned")
        self.assertNotIn("absolute_error", volume)

    def test_fortiblox_volume_semantics_default_to_incomplete(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(),
            references=[reference("x1_ninja")],
            fortiblox_field_evidence=accepted_fortiblox_token_field_evidence(),
        )

        volume = result["reconciliations"][0]["volume_24h_usd"]
        self.assertEqual(volume["state"], EVIDENCE_INCOMPLETE)
        self.assertEqual(
            volume["reason"],
            "fortiblox_volume_semantics_not_verified",
        )

    def test_upstream_overlap_never_becomes_source_independence(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(
                sources=["XDEX", "other-provider"]
            ),
            references=[
                reference(
                    "xdex",
                    source_independence_verified=True,
                    volume_comparable=False,
                ),
                reference(
                    "x1_ninja",
                    source_independence_verified=True,
                    volume_comparable=False,
                ),
            ],
            fortiblox_field_evidence=accepted_fortiblox_token_field_evidence(),
        )

        rows = {row["source_id"]: row for row in result["reconciliations"]}
        self.assertTrue(rows["xdex"]["upstream_overlap_with_fortiblox"])
        self.assertFalse(rows["x1_ninja"]["upstream_overlap_with_fortiblox"])
        self.assertTrue(rows["xdex"]["reference_source_independence_claim"])
        self.assertFalse(rows["xdex"]["source_independence_verified"])
        self.assertFalse(result["same_fact_agreement_is_source_independence"])
        self.assertFalse(result["source_independence_verified"])

    def test_explicit_not_comparable_state_is_preserved(self):
        result = reconcile_fortiblox_cross_source(
            mint=MINT,
            fortiblox_tokens_observation=fortiblox(),
            references=[
                reference(
                    "xdex",
                    price_comparable=False,
                    volume_comparable=False,
                )
            ],
            fortiblox_field_evidence=fully_comparable_fortiblox_evidence(),
        )

        row = result["reconciliations"][0]
        self.assertEqual(row["price"]["state"], NOT_COMPARABLE)
        self.assertEqual(row["volume_24h_usd"]["state"], NOT_COMPARABLE)
        self.assertEqual(result["overall_state"], "EVIDENCE_INCOMPLETE")

    def test_identity_mismatch_fails_before_comparison(self):
        bad = reference("xdex")
        bad["mint"] = "OtherMint111111111111111111111111111111111"

        with self.assertRaises(FortiBloxCrossSourceReconciliationError):
            reconcile_fortiblox_cross_source(
                mint=MINT,
                fortiblox_tokens_observation=fortiblox(),
                references=[bad],
                fortiblox_field_evidence=accepted_fortiblox_token_field_evidence(),
            )

    def test_duplicate_reference_source_fails_closed(self):
        with self.assertRaises(FortiBloxCrossSourceReconciliationError):
            reconcile_fortiblox_cross_source(
                mint=MINT,
                fortiblox_tokens_observation=fortiblox(),
                references=[reference("xdex"), reference("xdex")],
                fortiblox_field_evidence=accepted_fortiblox_token_field_evidence(),
            )


if __name__ == "__main__":
    unittest.main()
