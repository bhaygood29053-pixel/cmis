import copy
import unittest

from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    build_tokenized_equity_provenance,
)
from liquidity_scout.services.cmis_tokenized_equity_rights import (
    REQUIRED_DIMENSIONS,
    TOKENIZED_EQUITY_RIGHTS_CONTRACT,
    build_tokenized_equity_rights,
)


class TokenizedEquityRightsTests(unittest.TestCase):
    def _provenance(self):
        return build_tokenized_equity_provenance(
            token={
                "chain": "x1",
                "asset_id": "Eq11111111111111111111111111111111111111111",
                "asset_id_kind": "mint",
            },
            underlying_security={
                "security_id": "US0000000001",
                "security_id_kind": "isin",
            },
            representation_type="tokenized_security_representation",
            issuer={
                "name": "Example Issuer LLC",
                "legal_entity_id": "549300EXAMPLE00000001",
                "legal_entity_id_kind": "lei",
            },
            backing_model="issuer-described custody arrangement",
            custody_model="issuer-described custodian",
        )

    def _unknown_dimensions(self):
        return {
            dimension: {
                "state": "UNKNOWN",
                "summary": "No decisive authoritative evidence is bound yet.",
                "evidence": [],
                "conditions": [],
            }
            for dimension in REQUIRED_DIMENSIONS
        }

    def _evidence(self, *, source_class="offering_document", suffix="1"):
        return {
            "evidence_id": f"rights-evidence-{suffix}",
            "source_class": source_class,
            "source_url": f"https://issuer.example/rights/{suffix}",
            "document_id": f"document-{suffix}",
            "section": "Holder Rights",
            "fact_time": "2026-09-10T12:00:00Z",
            "retrieved_at": "2026-09-10T12:05:00Z",
            "content_sha256": "a" * 64,
        }

    def test_all_unknown_is_safe_non_promoted_record(self):
        result = build_tokenized_equity_rights(
            tokenized_equity_provenance=self._provenance(),
            dimensions=self._unknown_dimensions(),
        )

        self.assertEqual(result["contract"], TOKENIZED_EQUITY_RIGHTS_CONTRACT)
        self.assertEqual(result["summary"]["unknown_dimension_count"], 9)
        self.assertEqual(result["summary"]["decisive_dimension_count"], 0)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["verification"]["legal_effect_independently_adjudicated"])
        self.assertFalse(result["boundaries"]["provenance_establishes_holder_rights"])
        self.assertFalse(
            result["boundaries"]["marketing_material_can_independently_verify_rights"]
        )

    def test_authoritative_evidence_can_bind_verified_state_without_legal_adjudication(self):
        dimensions = self._unknown_dimensions()
        dimensions["voting_rights"] = {
            "state": "VERIFIED",
            "summary": "The cited governing material states a bounded voting entitlement.",
            "evidence": [self._evidence()],
            "conditions": [],
        }

        result = build_tokenized_equity_rights(
            tokenized_equity_provenance=self._provenance(),
            dimensions=dimensions,
        )
        voting = result["dimensions"]["voting_rights"]

        self.assertEqual(voting["state"], "VERIFIED")
        self.assertTrue(voting["evidence_binding_verified"])
        self.assertFalse(voting["legal_effect_adjudicated"])
        self.assertTrue(voting["evidence"][0]["authoritative_for_decisive_state"])
        self.assertEqual(result["summary"]["verified_dimension_count"], 1)

    def test_marketing_only_cannot_create_decisive_right_state(self):
        dimensions = self._unknown_dimensions()
        dimensions["dividend_treatment"] = {
            "state": "VERIFIED",
            "summary": "Marketing material claims distributions.",
            "evidence": [self._evidence(source_class="marketing_material")],
            "conditions": [],
        }

        with self.assertRaisesRegex(ValueError, "requires authoritative evidence"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=self._provenance(),
                dimensions=dimensions,
            )

    def test_conditional_state_requires_explicit_conditions(self):
        dimensions = self._unknown_dimensions()
        dimensions["redemption_rights"] = {
            "state": "CONDITIONAL",
            "summary": "Redemption depends on stated eligibility conditions.",
            "evidence": [self._evidence()],
            "conditions": [],
        }

        with self.assertRaisesRegex(ValueError, "requires conditions"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=self._provenance(),
                dimensions=dimensions,
            )

        dimensions["redemption_rights"]["conditions"] = [
            "Holder must satisfy the cited eligibility terms."
        ]
        result = build_tokenized_equity_rights(
            tokenized_equity_provenance=self._provenance(),
            dimensions=dimensions,
        )
        self.assertEqual(
            result["dimensions"]["redemption_rights"]["state"], "CONDITIONAL"
        )

    def test_denied_and_not_applicable_states_also_require_authoritative_evidence(self):
        for state in ("DENIED", "NOT_APPLICABLE"):
            dimensions = self._unknown_dimensions()
            dimensions["underlying_ownership"] = {
                "state": state,
                "summary": f"Bounded claim state: {state}.",
                "evidence": [],
                "conditions": [],
            }
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "requires authoritative evidence"):
                    build_tokenized_equity_rights(
                        tokenized_equity_provenance=self._provenance(),
                        dimensions=dimensions,
                    )

    def test_every_required_dimension_must_be_present_and_extras_are_rejected(self):
        dimensions = self._unknown_dimensions()
        dimensions.pop("custody_structure")
        with self.assertRaisesRegex(ValueError, "missing required entries"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=self._provenance(),
                dimensions=dimensions,
            )

        dimensions = self._unknown_dimensions()
        dimensions["price_target"] = {
            "state": "UNKNOWN",
            "summary": "Not a rights dimension.",
            "evidence": [],
            "conditions": [],
        }
        with self.assertRaisesRegex(ValueError, "unsupported entries"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=self._provenance(),
                dimensions=dimensions,
            )

    def test_provenance_cannot_pre_assert_holder_rights_or_execution(self):
        provenance = self._provenance()
        provenance["verification"]["holder_rights_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot pre-assert holder rights"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=provenance,
                dimensions=self._unknown_dimensions(),
            )

        provenance = self._provenance()
        provenance["execution_authorized"] = True
        with self.assertRaisesRegex(ValueError, "execution_authorized=false"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=provenance,
                dimensions=self._unknown_dimensions(),
            )

    def test_evidence_requires_https_hash_and_timezone_fact_time(self):
        base = self._unknown_dimensions()
        for field, value, message in (
            ("source_url", "http://issuer.example/rights", "absolute https URL"),
            ("content_sha256", "not-a-hash", "64 lowercase hex"),
            ("fact_time", "2026-09-10T12:00:00", "include timezone"),
        ):
            dimensions = copy.deepcopy(base)
            evidence = self._evidence()
            evidence[field] = value
            dimensions["issuer_counterparty"] = {
                "state": "VERIFIED",
                "summary": "Issuer identity is bound to authoritative evidence.",
                "evidence": [evidence],
                "conditions": [],
            }
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, message):
                    build_tokenized_equity_rights(
                        tokenized_equity_provenance=self._provenance(),
                        dimensions=dimensions,
                    )

    def test_duplicate_evidence_id_within_dimension_is_rejected(self):
        dimensions = self._unknown_dimensions()
        evidence = self._evidence()
        dimensions["jurisdiction_scope"] = {
            "state": "VERIFIED",
            "summary": "Jurisdiction scope is evidence-bound.",
            "evidence": [evidence, copy.deepcopy(evidence)],
            "conditions": [],
        }
        with self.assertRaisesRegex(ValueError, "duplicate evidence_id"):
            build_tokenized_equity_rights(
                tokenized_equity_provenance=self._provenance(),
                dimensions=dimensions,
            )


if __name__ == "__main__":
    unittest.main()
