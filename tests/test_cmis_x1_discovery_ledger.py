import unittest

from liquidity_scout.cmis.discovery_ledger import (
    DISCOVERY_LEDGER_CONTRACT_VERSION,
    DiscoveryLedgerContractError,
    DiscoveryLedgerV1,
    DiscoveryObservationV1,
    replay_discovery_observations,
)


MINT_A = "11111111111111111111111111111111"
MINT_B = "22222222222222222222222222222222"
KIND = "verified_market_observation"


def observation(
    *,
    mint=MINT_A,
    fact_time=200,
    fact_verified=True,
    recorded_at=300,
    source="cmis_fixture",
    verification_state="verified",
    identity_verified=True,
    chain="x1",
    receipt="er_fixture",
    proof="ps_fixture",
):
    return DiscoveryObservationV1.create(
        mint=mint,
        observation_kind=KIND,
        fact_time_unix=fact_time,
        fact_time_verified=fact_verified,
        recorded_at_unix=recorded_at,
        source_id=source,
        source_role="verified_fixture",
        source_scope=f"mint:{mint}",
        verification_state=verification_state,
        evidence_receipt_id=receipt,
        proof_score_id=proof,
        limitations=("asset_lifetime_not_implied",),
        warnings=(),
        identity_verified=identity_verified,
        chain=chain,
    )


class X1DiscoveryLedgerV1Tests(unittest.TestCase):
    def test_first_verified_observation_uses_verified_fact_time(self):
        first = observation(fact_time=100, recorded_at=500, source="first")
        later = observation(fact_time=200, recorded_at=300, source="later")
        ledger = DiscoveryLedgerV1().append(later).append(first)

        selected = ledger.first_verified_observation(
            mint=MINT_A,
            observation_kind=KIND,
        )

        self.assertEqual(selected, first)
        self.assertEqual(
            ledger.first_verified_observed_at(
                mint=MINT_A,
                observation_kind=KIND,
            ),
            100,
        )

    def test_later_arriving_earlier_fact_time_displaces_pointer_without_mutation(self):
        original = observation(fact_time=200, recorded_at=210, source="original")
        ledger1 = DiscoveryLedgerV1().append(original)
        original_payload = original.to_mapping()

        earlier = observation(fact_time=100, recorded_at=500, source="backfill")
        ledger2 = ledger1.append(earlier)

        self.assertEqual(len(ledger1.observations), 1)
        self.assertEqual(original.to_mapping(), original_payload)
        self.assertEqual(len(ledger2.observations), 2)
        self.assertEqual(
            ledger2.first_verified_observed_at(
                mint=MINT_A,
                observation_kind=KIND,
            ),
            100,
        )

    def test_missing_or_unverified_fact_time_is_retained_but_not_first(self):
        missing = observation(
            fact_time=None,
            fact_verified=False,
            source="missing-time",
        )
        unverified_time = observation(
            fact_time=50,
            fact_verified=False,
            source="unverified-time",
        )
        ledger = DiscoveryLedgerV1().append(missing).append(unverified_time)

        self.assertEqual(len(ledger.observations), 2)
        self.assertIsNone(
            ledger.first_verified_observed_at(
                mint=MINT_A,
                observation_kind=KIND,
            )
        )

    def test_partial_or_conflict_observations_do_not_establish_first_verified_time(self):
        partial = observation(
            fact_time=10,
            verification_state="partial",
            source="partial",
        )
        conflict = observation(
            fact_time=5,
            verification_state="conflict",
            source="conflict",
        )
        verified = observation(
            fact_time=100,
            verification_state="verified",
            source="verified",
        )
        ledger = replay_discovery_observations([partial, conflict, verified])

        self.assertEqual(
            ledger.first_verified_observed_at(
                mint=MINT_A,
                observation_kind=KIND,
            ),
            100,
        )

    def test_exact_duplicate_is_idempotent(self):
        item = observation()
        ledger1 = DiscoveryLedgerV1().append(item)
        ledger2 = ledger1.append(item)

        self.assertIs(ledger2, ledger1)
        self.assertEqual(len(ledger2.observations), 1)

    def test_supplied_content_id_tamper_fails_closed(self):
        item = observation()
        payload = item.to_mapping()
        payload["source_id"] = "tampered-source"

        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "content_id does not match",
        ):
            DiscoveryObservationV1.from_mapping(payload)

    def test_same_time_tie_uses_content_id_only_for_deterministic_replay(self):
        left = observation(fact_time=100, recorded_at=200, source="source-a")
        right = observation(fact_time=100, recorded_at=201, source="source-b")
        expected = min((left, right), key=lambda item: item.content_id)

        ledger_a = replay_discovery_observations([left, right])
        ledger_b = replay_discovery_observations([right, left])

        self.assertEqual(
            ledger_a.first_verified_observation(
                mint=MINT_A,
                observation_kind=KIND,
            ),
            expected,
        )
        self.assertEqual(
            ledger_b.first_verified_observation(
                mint=MINT_A,
                observation_kind=KIND,
            ),
            expected,
        )

    def test_unverified_identity_and_cross_chain_records_are_rejected(self):
        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "verified X1 mint identity",
        ):
            observation(identity_verified=False)

        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "X1-only",
        ):
            observation(chain="solana")

    def test_subject_id_must_equal_verified_mint(self):
        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "subject_id must equal",
        ):
            DiscoveryObservationV1.create(
                mint=MINT_A,
                subject_id=MINT_B,
                observation_kind=KIND,
                fact_time_unix=100,
                fact_time_verified=True,
                recorded_at_unix=200,
                source_id="fixture",
                source_role="verified_fixture",
                source_scope=f"mint:{MINT_A}",
                verification_state="verified",
            )

    def test_timestamp_contract_is_strict_integer_seconds(self):
        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "fact_time_unix must be a non-negative integer",
        ):
            DiscoveryObservationV1.create(
                mint=MINT_A,
                observation_kind=KIND,
                fact_time_unix=100.5,
                fact_time_verified=True,
                recorded_at_unix=200,
                source_id="fixture",
                source_role="verified_fixture",
                source_scope=f"mint:{MINT_A}",
                verification_state="verified",
            )

        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "recorded_at_unix must be a non-negative integer",
        ):
            DiscoveryObservationV1.create(
                mint=MINT_A,
                observation_kind=KIND,
                fact_time_unix=100,
                fact_time_verified=True,
                recorded_at_unix=True,
                source_id="fixture",
                source_role="verified_fixture",
                source_scope=f"mint:{MINT_A}",
                verification_state="verified",
            )

    def test_verified_fact_time_requires_a_fact_time(self):
        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "fact_time_verified=true requires fact_time_unix",
        ):
            observation(fact_time=None, fact_verified=True)

    def test_proof_metadata_is_preserved_without_risk_or_execution_authority(self):
        item = observation(receipt="er_abc", proof="ps_abc")
        payload = item.to_mapping()

        self.assertEqual(payload["evidence_receipt_id"], "er_abc")
        self.assertEqual(payload["proof_score_id"], "ps_abc")
        self.assertNotIn("risk", payload)
        self.assertFalse(payload["execution_authorized"])

        with self.assertRaisesRegex(
            DiscoveryLedgerContractError,
            "execution_authorized=false",
        ):
            DiscoveryObservationV1.create(
                mint=MINT_A,
                observation_kind=KIND,
                fact_time_unix=100,
                fact_time_verified=True,
                recorded_at_unix=200,
                source_id="fixture",
                source_role="verified_fixture",
                source_scope=f"mint:{MINT_A}",
                verification_state="verified",
                execution_authorized=True,
            )

    def test_ledger_serialization_and_replay_are_deterministic(self):
        items = [
            observation(fact_time=200, recorded_at=300, source="a"),
            observation(fact_time=100, recorded_at=400, source="b"),
        ]
        ledger = replay_discovery_observations(items)
        serialized = ledger.to_mapping()

        self.assertEqual(
            serialized["contract_version"],
            DISCOVERY_LEDGER_CONTRACT_VERSION,
        )
        self.assertTrue(serialized["read_only"])
        self.assertFalse(serialized["public_service_promoted"])
        self.assertFalse(serialized["scout_reliance_promoted"])
        self.assertFalse(serialized["execution_authorized"])

        restored = DiscoveryLedgerV1.from_mapping(serialized)
        self.assertEqual(restored.to_mapping(), serialized)
        self.assertEqual(restored.observations, ledger.observations)

    def test_tampered_serialized_ledger_state_fails_closed(self):
        ledger = DiscoveryLedgerV1().append(observation())
        serialized = ledger.to_mapping()
        serialized["observations"][0]["source_role"] = "tampered"

        with self.assertRaises(DiscoveryLedgerContractError):
            DiscoveryLedgerV1.from_mapping(serialized)


if __name__ == "__main__":
    unittest.main()
