from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration
from liquidity_scout.cmis.concentration_change import compare_top_account_concentration
from liquidity_scout.cmis.evidence_receipt import build_evidence_receipt
from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle
from liquidity_scout.cmis.proof_score import build_proof_score
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway, SUPPORTED_SERVICES
from liquidity_scout.services.cmis_verified_intelligence import SERVICE


def canonical_bundle():
    observed_at = "2026-08-18T12:00:00Z"
    envelope = {
        "service": "market_report",
        "chain": "x1",
        "status": "ok",
        "asset": {"canonical_id": "mint-1", "mint": "mint-1"},
        "data": {
            "scope": "asset_exact",
            "asset_identity_verified": True,
            "field_semantics_verified": True,
            "freshness_verified": True,
            "source_independence_verified": True,
            "cmis_promotable": True,
            "verification": {"status": "AGREEMENT", "code": "runtime_test"},
            "observations": {
                "primary": {"source": "X1.Ninja", "observed_at": observed_at},
                "verifier": {"source": "X1 RPC", "observed_at": observed_at},
            },
        },
        "risk": None,
        "confidence": {},
        "sources": [{"source": "X1.Ninja", "observed_at": observed_at}],
        "observed_at": observed_at,
        "warnings": [],
        "errors": [],
    }
    receipt = build_evidence_receipt(envelope)
    evidence = {"evidence_receipt": receipt, "proof_score": build_proof_score(receipt)}

    before = build_top_account_concentration(
        chain="x1",
        asset_id="mint-1",
        source="X1.Ninja",
        supply_raw=1000,
        supply_decimals=0,
        requested_account_limit=2,
        accounts=[
            {"address": "acct-a", "amount": 250, "decimals": 0},
            {"address": "acct-b", "amount": 150, "decimals": 0},
        ],
        supply_identity_verified=True,
        account_identity_verified=True,
    )
    after = build_top_account_concentration(
        chain="x1",
        asset_id="mint-1",
        source="X1.Ninja",
        supply_raw=1000,
        supply_decimals=0,
        requested_account_limit=2,
        accounts=[
            {"address": "acct-a", "amount": 300, "decimals": 0},
            {"address": "acct-b", "amount": 150, "decimals": 0},
        ],
        supply_identity_verified=True,
        account_identity_verified=True,
    )
    change = compare_top_account_concentration(
        before=before,
        after=after,
        before_observed_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
        after_observed_at=datetime(2026, 8, 18, 13, tzinfo=timezone.utc),
    )
    return build_intelligence_evidence_bundle(
        conclusion_type="top_account_concentration_change",
        conclusion=change,
        evidence_bundles=[evidence],
    )


class RuntimeConcentrationIntelligenceTests(unittest.TestCase):
    def gateway(self, directory):
        return RuntimeCMISGateway(
            verification_evidence_db_path=str(Path(directory) / "verification.sqlite3"),
            intelligence_evidence_db_path=str(Path(directory) / "intelligence.sqlite3"),
        )

    def test_runtime_stores_internal_evidence_and_serves_promoted_x1_contract(self):
        bundle = canonical_bundle()
        with TemporaryDirectory() as directory:
            gateway = self.gateway(directory)
            stored = gateway.store_intelligence_evidence(bundle, recorded_at=123.0)
            response = gateway.dispatch(
                {
                    "service": SERVICE,
                    "chain": "x1",
                    "params": {
                        "asset_id": "mint-1",
                        "intelligence_evidence_id": bundle["intelligence_evidence_id"],
                    },
                }
            )

        self.assertIn(SERVICE, SUPPORTED_SERVICES)
        self.assertTrue(stored["inserted"])
        self.assertEqual(response["status"], "ok")
        self.assertTrue(response["data"]["public_service_promoted"])
        self.assertTrue(response["data"]["scout_reliance_promoted"])
        self.assertEqual(
            response["data"]["accepted_conclusion_type"],
            "top_account_concentration_change",
        )
        self.assertEqual(response["data"]["facts"]["direction"], "INCREASE")
        self.assertIsNone(response["risk"])
        self.assertFalse(response["data"]["execution_authorized"])
        self.assertIn("evidence_receipt", response)
        self.assertIn("proof_score", response)
        self.assertTrue(response["evidence_receipt"]["receipt_id"].startswith("er_"))

    def test_runtime_does_not_accept_caller_supplied_intelligence_evidence(self):
        bundle = canonical_bundle()
        with TemporaryDirectory() as directory:
            gateway = self.gateway(directory)
            gateway.store_intelligence_evidence(bundle)
            response = gateway.dispatch(
                {
                    "service": SERVICE,
                    "chain": "x1",
                    "params": {
                        "asset_id": "mint-1",
                        "intelligence_evidence_id": bundle["intelligence_evidence_id"],
                        "intelligence_evidence": bundle,
                    },
                }
            )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "caller_intelligence_evidence_not_accepted",
        )
        self.assertIn("evidence_receipt", response)
        self.assertIn("proof_score", response)

    def test_runtime_missing_record_and_solana_fail_closed(self):
        missing_id = "ie_" + "a" * 64
        with TemporaryDirectory() as directory:
            gateway = self.gateway(directory)
            missing = gateway.dispatch(
                {
                    "service": SERVICE,
                    "chain": "x1",
                    "params": {
                        "asset_id": "mint-1",
                        "intelligence_evidence_id": missing_id,
                    },
                }
            )
            solana = gateway.dispatch(
                {
                    "service": SERVICE,
                    "chain": "solana",
                    "params": {
                        "asset_id": "mint-1",
                        "intelligence_evidence_id": missing_id,
                    },
                }
            )

        self.assertEqual(missing["status"], "unavailable")
        self.assertEqual(missing["warnings"][0]["code"], "intelligence_evidence_not_found")
        self.assertEqual(solana["status"], "unavailable")
        self.assertEqual(
            solana["warnings"][0]["code"],
            "concentration_change_intelligence_chain_not_promoted",
        )
        self.assertFalse(solana["data"]["scout_reliance_promoted"])

    def test_old_broad_service_name_and_public_store_endpoint_are_not_runtime_services(self):
        with TemporaryDirectory() as directory:
            gateway = self.gateway(directory)
            broad = gateway.dispatch(
                {"service": "verified_intelligence", "chain": "x1", "params": {}}
            )
            store = gateway.dispatch(
                {"service": "intelligence_evidence_store", "chain": "x1", "params": {}}
            )

        self.assertEqual(broad["status"], "error")
        self.assertEqual(store["status"], "error")
        self.assertNotIn("verified_intelligence", SUPPORTED_SERVICES)
        self.assertNotIn("intelligence_evidence_store", SUPPORTED_SERVICES)

    def test_runtime_rejects_invalid_internal_ledger_dependency(self):
        with self.assertRaisesRegex(
            ValueError,
            "must provide callable get and store methods",
        ):
            RuntimeCMISGateway(
                verification_evidence_db_path=":memory:",
                intelligence_evidence_ledger=object(),
            )


if __name__ == "__main__":
    unittest.main()
