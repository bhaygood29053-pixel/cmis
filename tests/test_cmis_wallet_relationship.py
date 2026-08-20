from copy import deepcopy
import unittest

from liquidity_scout.cmis.wallet_activity import build_wallet_activity_observation
from liquidity_scout.cmis.wallet_relationship import (
    INTERACTION_TYPE,
    RELATIONSHIP_KIND,
    SCHEMA,
    SUMMARY_SCHEMA,
    build_direct_wallet_relationship,
    summarize_direct_wallet_relationships,
    validate_direct_wallet_relationship,
    validate_direct_wallet_relationship_summary,
)


def transfer_observation(
    *,
    wallet="wallet-a",
    counterparty="wallet-b",
    activity_type="TRANSFER_OUT",
    transaction_signature="tx-1",
    observed_at="2026-08-20T12:00:00Z",
    chain="x1",
    asset_id="mint-1",
    amount="10",
    unit="raw-token-units",
    source="CMIS test source",
    verification_method="deterministic_test_fixture",
    evidence_scope="bounded_test_window",
    block_slot=100,
):
    amount_verified = amount is not None
    return build_wallet_activity_observation(
        chain=chain,
        wallet=wallet,
        activity_type=activity_type,
        transaction_signature=transaction_signature,
        observed_at=observed_at,
        source=source,
        verification_method=verification_method,
        evidence_scope=evidence_scope,
        asset_id=asset_id,
        block_slot=block_slot,
        asset_amount=amount,
        asset_unit=unit if amount_verified else None,
        counterparty=counterparty,
        wallet_identity_verified=True,
        asset_identity_verified=True,
        transaction_identity_verified=True,
        amount_verified=amount_verified,
        transfer_direction_verified=True,
        counterparty_verified=True,
    )


def resolver_for(*observations):
    by_id = {item["observation_id"]: item for item in observations}
    return lambda observation_id: by_id.get(observation_id)


class CMISWalletRelationshipTests(unittest.TestCase):
    def test_valid_direct_transfer_relationship_is_evidence_bound_and_non_ownership(self):
        observation = transfer_observation()
        result = build_direct_wallet_relationship(
            observation["observation_id"],
            observation_resolver=resolver_for(observation),
        )

        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["relationship_kind"], RELATIONSHIP_KIND)
        self.assertEqual(result["interaction_type"], INTERACTION_TYPE)
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["asset_id"], "mint-1")
        self.assertEqual(result["sender"], "wallet-a")
        self.assertEqual(result["recipient"], "wallet-b")
        self.assertEqual(result["transaction_signature"], "tx-1")
        self.assertEqual(result["asset_amount"], "10")
        self.assertEqual(result["asset_unit"], "raw-token-units")
        self.assertEqual(
            result["evidence"]["wallet_activity_observation_id"],
            observation["observation_id"],
        )
        self.assertTrue(result["evidence"]["wallet_activity_revalidated"])
        self.assertFalse(result["evidence"]["evidence_receipt_binding_available"])
        self.assertEqual(result["evidence"]["evidence_receipt_ids"], [])
        self.assertFalse(result["evidence"]["proof_score_binding_available"])
        self.assertEqual(result["evidence"]["proof_score_records"], [])
        self.assertFalse(result["ownership_inference_added"])
        self.assertFalse(result["beneficial_ownership_inference_added"])
        self.assertFalse(result["behavioral_interpretation_added"])
        self.assertFalse(result["intent_interpretation_added"])
        self.assertIsNone(result["risk_interpretation"])
        self.assertTrue(result["proof_strength_separate_from_risk"])
        self.assertFalse(result["complete_history_claimed"])
        self.assertFalse(result["complete_graph_coverage_claimed"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_transfer_in_and_transfer_out_preserve_exact_direction(self):
        outbound = transfer_observation(
            wallet="wallet-a",
            counterparty="wallet-b",
            activity_type="TRANSFER_OUT",
            transaction_signature="tx-out",
        )
        inbound = transfer_observation(
            wallet="wallet-a",
            counterparty="wallet-b",
            activity_type="TRANSFER_IN",
            transaction_signature="tx-in",
        )
        resolver = resolver_for(outbound, inbound)

        sent = build_direct_wallet_relationship(
            outbound["observation_id"], observation_resolver=resolver
        )
        received = build_direct_wallet_relationship(
            inbound["observation_id"], observation_resolver=resolver
        )

        self.assertEqual((sent["sender"], sent["recipient"]), ("wallet-a", "wallet-b"))
        self.assertEqual(
            (received["sender"], received["recipient"]), ("wallet-b", "wallet-a")
        )
        self.assertNotEqual(
            sent["relationship_evidence_id"], received["relationship_evidence_id"]
        )

    def test_same_identity_text_on_different_chains_fails_closed_when_aggregated(self):
        x1 = transfer_observation(chain="x1", transaction_signature="tx-x1")
        solana = transfer_observation(
            chain="solana",
            transaction_signature="tx-solana",
            observed_at="2026-08-20T12:05:00Z",
        )
        resolver = resolver_for(x1, solana)

        with self.assertRaisesRegex(ValueError, "incompatible chain/asset/direction"):
            summarize_direct_wallet_relationships(
                [x1["observation_id"], solana["observation_id"]],
                observation_resolver=resolver,
            )

    def test_same_wallet_pair_on_different_assets_remains_separate_evidence(self):
        first = transfer_observation(asset_id="mint-1", transaction_signature="tx-1")
        second = transfer_observation(
            asset_id="mint-2",
            transaction_signature="tx-2",
            observed_at="2026-08-20T12:05:00Z",
        )
        resolver = resolver_for(first, second)
        relationship_a = build_direct_wallet_relationship(
            first["observation_id"], observation_resolver=resolver
        )
        relationship_b = build_direct_wallet_relationship(
            second["observation_id"], observation_resolver=resolver
        )

        self.assertNotEqual(
            relationship_a["relationship_evidence_id"],
            relationship_b["relationship_evidence_id"],
        )
        with self.assertRaisesRegex(ValueError, "incompatible chain/asset/direction"):
            summarize_direct_wallet_relationships(
                [first["observation_id"], second["observation_id"]],
                observation_resolver=resolver,
            )

    def test_unverified_or_ambiguous_direction_fails_closed(self):
        observation = transfer_observation()
        tampered = deepcopy(observation)
        tampered["verification"]["transfer_direction_verified"] = False

        with self.assertRaises(ValueError):
            build_direct_wallet_relationship(
                observation["observation_id"],
                observation_resolver=lambda observation_id: tampered,
            )

    def test_missing_amount_stays_unknown_instead_of_zero(self):
        observation = transfer_observation(amount=None, unit=None)
        result = build_direct_wallet_relationship(
            observation["observation_id"],
            observation_resolver=resolver_for(observation),
        )

        self.assertIsNone(result["asset_amount"])
        self.assertIsNone(result["asset_unit"])
        self.assertIn("missing_amounts_are_not_zero_filled", result["limitations"])

    def test_resolver_failure_does_not_reflect_arbitrary_exception_text(self):
        observation = transfer_observation()

        def resolver(_):
            raise RuntimeError("https://user:secret@example.invalid/private")

        with self.assertRaisesRegex(
            ValueError,
            r"failed \(RuntimeError\)",
        ) as raised:
            build_direct_wallet_relationship(
                observation["observation_id"],
                observation_resolver=resolver,
            )

        self.assertNotIn("secret", str(raised.exception))
        self.assertNotIn("example.invalid", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_tampered_transaction_or_invalid_evidence_identity_fails_closed(self):
        observation = transfer_observation()
        tampered = deepcopy(observation)
        tampered["transaction_signature"] = "tx-tampered"

        with self.assertRaises(ValueError):
            build_direct_wallet_relationship(
                observation["observation_id"],
                observation_resolver=lambda observation_id: tampered,
            )
        with self.assertRaisesRegex(ValueError, "canonical wa_ content id"):
            build_direct_wallet_relationship(
                "not-an-observation-id",
                observation_resolver=resolver_for(observation),
            )

    def test_duplicate_source_evidence_cannot_inflate_interaction_count(self):
        sender_view = transfer_observation(
            wallet="wallet-a",
            counterparty="wallet-b",
            activity_type="TRANSFER_OUT",
            transaction_signature="tx-1",
        )
        recipient_view = transfer_observation(
            wallet="wallet-b",
            counterparty="wallet-a",
            activity_type="TRANSFER_IN",
            transaction_signature="tx-1",
        )
        resolver = resolver_for(sender_view, recipient_view)

        summary = summarize_direct_wallet_relationships(
            [
                sender_view["observation_id"],
                sender_view["observation_id"],
                recipient_view["observation_id"],
            ],
            observation_resolver=resolver,
        )

        self.assertEqual(summary["schema"], SUMMARY_SCHEMA)
        self.assertEqual(summary["verified_direct_interaction_count"], 1)
        self.assertEqual(summary["relationship_evidence_count"], 2)
        self.assertEqual(summary["duplicate_relationship_evidence_collapsed"], 1)
        self.assertEqual(
            len(summary["interaction_evidence"][0]["relationship_evidence_ids"]), 2
        )

    def test_compatible_bounded_aggregation_has_deterministic_first_last_and_count(self):
        first = transfer_observation(
            transaction_signature="tx-1",
            observed_at="2026-08-20T12:00:00Z",
            block_slot=100,
        )
        second = transfer_observation(
            transaction_signature="tx-2",
            observed_at="2026-08-20T13:00:00Z",
            block_slot=101,
        )
        resolver = resolver_for(first, second)

        summary = summarize_direct_wallet_relationships(
            [second["observation_id"], first["observation_id"]],
            observation_resolver=resolver,
        )

        self.assertEqual(summary["verified_direct_interaction_count"], 2)
        self.assertEqual(summary["first_observed_interaction"], "2026-08-20T12:00:00Z")
        self.assertEqual(summary["last_observed_interaction"], "2026-08-20T13:00:00Z")
        self.assertEqual(summary["transaction_signatures"], ["tx-1", "tx-2"])
        self.assertFalse(summary["complete_history_claimed"])
        self.assertFalse(summary["complete_graph_coverage_claimed"])

        rebuilt = validate_direct_wallet_relationship_summary(
            summary,
            observation_resolver=resolver,
        )
        self.assertEqual(rebuilt, summary)

    def test_incompatible_scope_or_units_fail_closed(self):
        first = transfer_observation(transaction_signature="tx-1")
        other_scope = transfer_observation(
            transaction_signature="tx-2",
            observed_at="2026-08-20T12:05:00Z",
            evidence_scope="different_bounded_window",
        )
        other_unit = transfer_observation(
            transaction_signature="tx-3",
            observed_at="2026-08-20T12:10:00Z",
            unit="ui-token-units",
        )
        resolver = resolver_for(first, other_scope, other_unit)

        with self.assertRaisesRegex(ValueError, "incompatible chain/asset/direction"):
            summarize_direct_wallet_relationships(
                [first["observation_id"], other_scope["observation_id"]],
                observation_resolver=resolver,
            )
        with self.assertRaisesRegex(ValueError, "incompatible asset units"):
            summarize_direct_wallet_relationships(
                [first["observation_id"], other_unit["observation_id"]],
                observation_resolver=resolver,
            )

    def test_conflicting_duplicate_material_fails_closed(self):
        first = transfer_observation(transaction_signature="tx-1", amount="10")
        conflicting = transfer_observation(
            wallet="wallet-b",
            counterparty="wallet-a",
            activity_type="TRANSFER_IN",
            transaction_signature="tx-1",
            amount="11",
        )
        resolver = resolver_for(first, conflicting)

        with self.assertRaisesRegex(ValueError, "disagrees on material transfer facts"):
            summarize_direct_wallet_relationships(
                [first["observation_id"], conflicting["observation_id"]],
                observation_resolver=resolver,
            )

    def test_caller_cannot_replace_relationship_with_behavior_or_ownership_claim(self):
        observation = transfer_observation()
        resolver = resolver_for(observation)
        relationship = build_direct_wallet_relationship(
            observation["observation_id"], observation_resolver=resolver
        )

        forbidden_labels = (
            "COMMON_OWNER",
            "INSIDER",
            "WHALE",
            "BOT",
            "COORDINATED",
            "ACCUMULATOR",
            "DISTRIBUTOR",
            "MANIPULATOR",
            "SCAM",
        )
        for label in forbidden_labels:
            with self.subTest(label=label):
                tampered = deepcopy(relationship)
                tampered["relationship_kind"] = label
                with self.assertRaisesRegex(
                    ValueError, "deterministic canonical record"
                ):
                    validate_direct_wallet_relationship(
                        tampered,
                        observation_resolver=resolver,
                    )

    def test_validation_rebuilds_exact_record_and_hard_boundaries_remain_off(self):
        observation = transfer_observation()
        resolver = resolver_for(observation)
        relationship = build_direct_wallet_relationship(
            observation["observation_id"], observation_resolver=resolver
        )

        self.assertEqual(
            validate_direct_wallet_relationship(
                relationship,
                observation_resolver=resolver,
            ),
            relationship,
        )
        for field in (
            "ownership_inference_added",
            "beneficial_ownership_inference_added",
            "behavioral_interpretation_added",
            "intent_interpretation_added",
            "provider_assertion_promoted",
            "public_service_promoted",
            "scout_reliance_promoted",
            "cmis_promotable",
            "execution_authorized",
        ):
            self.assertFalse(relationship[field])
        self.assertIsNone(relationship["risk_interpretation"])
        self.assertTrue(relationship["proof_strength_separate_from_risk"])


if __name__ == "__main__":
    unittest.main()
