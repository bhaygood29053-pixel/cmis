import os
import tempfile
import unittest

from liquidity_scout.cmis.evidence import build_evidence_observation
from liquidity_scout.cmis.evidence_ledger import VerificationEvidenceLedger
from liquidity_scout.providers.x1.ninja_reserve_semantics import PROOF_STATUS
from liquidity_scout.providers.x1.reserve_crosscheck import run_x1_reserve_crosscheck
from liquidity_scout.providers.x1.reserve_persistence import (
    persist_x1_reserve_crosscheck_evidence,
)
from liquidity_scout.providers.x1.reserve_verification import verify_x1_pool_reserve
from liquidity_scout.services.cmis_verification_evidence_persistence import (
    persist_verification_evidence,
)


POOL = "pool111"
ASSET_MINT = "mint111"
ASSET_VAULT = "vault111"
COUNTER_MINT = "mint222"
COUNTER_VAULT = "vault222"
OWNER = "owner111"


def observation(source, *, subject="pool:pool111:vault:vault111:mint:mint111", fresh=True):
    return build_evidence_observation(
        chain="x1",
        fact_type="pool_reserve",
        subject_id=subject,
        source=source,
        source_role="market_provider" if source == "X1.Ninja" else "onchain_verifier",
        observed_at=1000.0,
        block_slot=None if source == "X1.Ninja" else 123456,
        raw_identifier="pool.pooledBase" if source == "X1.Ninja" else ASSET_VAULT,
        raw_value="42.5" if source == "X1.Ninja" else "42500000",
        normalized_value="42.5",
        unit="TOKEN_UNITS",
        calculation_version="persistence-test-1",
        identity_verified=True,
        semantics_verified=True,
        freshness_verified=fresh,
        warnings=[] if fresh else ["freshness_not_verified"],
    )


def verifier_result(*, fresh=True):
    return verify_x1_pool_reserve(
        observation("X1.Ninja", fresh=fresh),
        observation("X1 RPC", fresh=fresh),
    )


def pool_detail():
    return {
        "chain": "x1",
        "pool_address_requested": POOL,
        "raw_response": {
            "pool": {
                "pooledBase": "42.5",
                "pooledQuote": "9",
            }
        },
    }


def vault_identity():
    return {
        "service": "x1_pool_vault_identity",
        "version": "1.0",
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET_MINT,
        "asset_vault": ASSET_VAULT,
        "counter_mint": COUNTER_MINT,
        "counter_vault": COUNTER_VAULT,
        "shared_owner": OWNER,
        "identity_verified": True,
        "cmis_promotable": False,
        "rejection_reasons": [],
    }


def semantic_manifest():
    return {
        "proof_status": PROOF_STATUS,
        "proof_version": "persistence-test-1",
        "pool_address": POOL,
        "evidence_refs": ["test://semantic-proof"],
        "asset": {
            "field_path": "pool.pooledBase",
            "unit": "token_units",
            "decimals": 6,
            "mint": ASSET_MINT,
            "vault": ASSET_VAULT,
        },
        "counter": {
            "field_path": "pool.pooledQuote",
            "unit": "token_units",
            "decimals": 6,
            "mint": COUNTER_MINT,
            "vault": COUNTER_VAULT,
        },
    }


def rpc_balances():
    return {
        "asset": {
            "chain": "x1",
            "source": "X1 RPC",
            "method": "getTokenAccountBalance",
            "account": ASSET_VAULT,
            "slot": 123456,
            "amount": "42500000",
            "decimals": 6,
        },
        "counter": {
            "chain": "x1",
            "source": "X1 RPC",
            "method": "getTokenAccountBalance",
            "account": COUNTER_VAULT,
            "slot": 123457,
            "amount": "9000000",
            "decimals": 6,
        },
    }


def crosscheck(*, fresh=True, missing_counter=False):
    balances = rpc_balances()
    if missing_counter:
        del balances["counter"]
    return run_x1_reserve_crosscheck(
        pool_detail(),
        vault_identity(),
        semantic_manifest(),
        balances,
        observed_at=1000.0,
        observation_scope_verified=fresh,
    )


class CountingLedger:
    def __init__(self, receipt=None, error=None):
        self.calls = []
        self.receipt = receipt
        self.error = error

    def store(self, envelope, *, recorded_at=None):
        self.calls.append((envelope, recorded_at))
        if self.error is not None:
            raise self.error
        return self.receipt


class VerificationEvidencePersistenceTests(unittest.TestCase):
    def test_generic_helper_stores_only_sanitized_wrapper_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = VerificationEvidenceLedger(os.path.join(tmp, "evidence.db"))
            result = persist_verification_evidence(
                verifier_result(fresh=True),
                ledger,
                chain="x1",
                observed_at=1000.0,
                recorded_at=1001.0,
            )

            self.assertTrue(result["stored"])
            self.assertEqual(result["envelope"]["status"], "ok")
            self.assertEqual(
                result["envelope"]["data"]["fact"]["normalized_value"],
                "42.5",
            )
            stored = ledger.get(result["storage"]["evidence_id"])

        self.assertIsNotNone(stored)
        self.assertEqual(stored["recorded_at"], 1001.0)
        self.assertEqual(stored["envelope"], result["envelope"])

    def test_generic_helper_persists_nonpromotable_agreement_without_fact_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = VerificationEvidenceLedger(os.path.join(tmp, "evidence.db"))
            result = persist_verification_evidence(
                verifier_result(fresh=False),
                ledger,
                chain="x1",
                observed_at=1000.0,
                recorded_at=1001.0,
            )

        self.assertTrue(result["stored"])
        self.assertEqual(result["envelope"]["status"], "partial")
        self.assertFalse(result["envelope"]["data"]["cmis_promotable"])
        self.assertIsNone(result["envelope"]["data"]["fact"]["normalized_value"])
        self.assertEqual(
            result["envelope"]["data"]["observations"]["primary"]["normalized_value"],
            "42.5",
        )
        self.assertEqual(result["envelope"]["data"]["data_quality"]["quality"], "LOW")

    def test_invalid_wrapper_result_never_reaches_ledger(self):
        ledger = CountingLedger(
            receipt={"evidence_id": "should-not-store", "inserted": True, "recorded_at": 1.0}
        )
        result = persist_verification_evidence(
            {
                "verification": {
                    "status": "INSUFFICIENT_EVIDENCE",
                    "code": "MISSING",
                    "agreement": None,
                },
                "data_quality": None,
                "cmis_promotable": False,
            },
            ledger,
        )

        self.assertFalse(result["stored"])
        self.assertEqual(result["error"]["code"], "verification_evidence_not_storable")
        self.assertEqual(ledger.calls, [])

    def test_ledger_failure_is_sanitized(self):
        ledger = CountingLedger(error=RuntimeError("secret-provider-detail"))
        result = persist_verification_evidence(
            verifier_result(fresh=True),
            ledger,
            recorded_at=1.0,
        )

        self.assertFalse(result["stored"])
        self.assertEqual(
            result["error"]["code"],
            "verification_evidence_persistence_failed",
        )
        self.assertNotIn("secret-provider-detail", str(result))

    def test_invalid_ledger_receipt_fails_closed(self):
        ledger = CountingLedger(
            receipt={"evidence_id": "ve_bad", "inserted": True, "recorded_at": float("inf")}
        )
        result = persist_verification_evidence(
            verifier_result(fresh=True),
            ledger,
            recorded_at=1.0,
        )

        self.assertFalse(result["stored"])
        self.assertEqual(
            result["error"]["code"],
            "verification_evidence_persistence_receipt_invalid",
        )

    def test_reserve_adapter_persists_two_independent_promotable_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = VerificationEvidenceLedger(os.path.join(tmp, "evidence.db"))
            result = persist_x1_reserve_crosscheck_evidence(
                crosscheck(fresh=True),
                ledger,
                observed_at=1000.0,
                recorded_at=1002.0,
            )

            self.assertTrue(result["complete"])
            self.assertEqual(result["stored_count"], 2)
            self.assertEqual(result["stored_roles"], ["asset", "counter"])
            self.assertNotEqual(
                result["roles"]["asset"]["storage"]["evidence_id"],
                result["roles"]["counter"]["storage"]["evidence_id"],
            )
            asset_stored = ledger.latest(
                chain="x1",
                fact_type="pool_reserve",
                subject_id=f"pool:{POOL}:vault:{ASSET_VAULT}:mint:{ASSET_MINT}",
            )
            counter_stored = ledger.latest(
                chain="x1",
                fact_type="pool_reserve",
                subject_id=f"pool:{POOL}:vault:{COUNTER_VAULT}:mint:{COUNTER_MINT}",
            )

        self.assertEqual(asset_stored["envelope"]["status"], "ok")
        self.assertEqual(
            asset_stored["envelope"]["data"]["fact"]["normalized_value"],
            "42.5",
        )
        self.assertEqual(counter_stored["envelope"]["data"]["fact"]["normalized_value"], "9")
        self.assertFalse(result["cmis_promotable"])

    def test_reserve_adapter_persists_low_quality_agreement_without_promoting_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = VerificationEvidenceLedger(os.path.join(tmp, "evidence.db"))
            result = persist_x1_reserve_crosscheck_evidence(
                crosscheck(fresh=False),
                ledger,
                observed_at=1000.0,
                recorded_at=1002.0,
            )

        self.assertTrue(result["complete"])
        for role in ("asset", "counter"):
            envelope = result["roles"][role]["envelope"]
            self.assertEqual(envelope["status"], "partial")
            self.assertFalse(envelope["data"]["cmis_promotable"])
            self.assertIsNone(envelope["data"]["fact"]["normalized_value"])
            self.assertEqual(envelope["data"]["data_quality"]["quality"], "LOW")

    def test_reserve_adapter_keeps_valid_leg_when_other_leg_never_reaches_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = VerificationEvidenceLedger(os.path.join(tmp, "evidence.db"))
            result = persist_x1_reserve_crosscheck_evidence(
                crosscheck(fresh=True, missing_counter=True),
                ledger,
                observed_at=1000.0,
                recorded_at=1002.0,
            )

            rows = ledger.find(chain="x1")

        self.assertFalse(result["complete"])
        self.assertEqual(result["stored_roles"], ["asset"])
        self.assertEqual(result["stored_count"], 1)
        self.assertTrue(result["roles"]["asset"]["stored"])
        self.assertFalse(result["roles"]["counter"]["stored"])
        self.assertEqual(
            result["roles"]["counter"]["error"]["code"],
            "verification_evidence_not_storable",
        )
        self.assertEqual(len(rows), 1)

    def test_repeat_persistence_is_content_idempotent(self):
        verified = crosscheck(fresh=True)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = VerificationEvidenceLedger(os.path.join(tmp, "evidence.db"))
            first = persist_x1_reserve_crosscheck_evidence(
                verified,
                ledger,
                observed_at=1000.0,
                recorded_at=1002.0,
            )
            second = persist_x1_reserve_crosscheck_evidence(
                verified,
                ledger,
                observed_at=1000.0,
                recorded_at=1003.0,
            )
            rows = ledger.find(chain="x1")

        self.assertEqual(len(rows), 2)
        for role in ("asset", "counter"):
            self.assertTrue(first["roles"][role]["storage"]["inserted"])
            self.assertFalse(second["roles"][role]["storage"]["inserted"])
            self.assertEqual(
                first["roles"][role]["storage"]["evidence_id"],
                second["roles"][role]["storage"]["evidence_id"],
            )

    def test_reserve_adapter_rejects_wrong_upstream_contract(self):
        with self.assertRaisesRegex(ValueError, "x1_reserve_crosscheck"):
            persist_x1_reserve_crosscheck_evidence(
                {"service": "other", "chain": "x1", "roles": {}},
                None,
            )


if __name__ == "__main__":
    unittest.main()
