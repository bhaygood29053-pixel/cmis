import unittest

from liquidity_scout.cmis.evidence import (
    AGREEMENT,
    CONFLICT,
    INSUFFICIENT_EVIDENCE,
    VALUES_DISAGREE,
)
from liquidity_scout.providers.x1.ninja_reserve_semantics import PROOF_STATUS
from liquidity_scout.providers.x1.reserve_crosscheck import (
    OBSERVED_AT_MISSING,
    RPC_BALANCE_MISSING,
    SEMANTIC_PROOF_REJECTED,
    run_x1_reserve_crosscheck,
)
from liquidity_scout.providers.x1.reserve_evidence import BASE_UNITS, TOKEN_UNITS


POOL = "pool111"
ASSET_MINT = "mint111"
ASSET_VAULT = "vault111"
COUNTER_MINT = "mint222"
COUNTER_VAULT = "vault222"
OWNER = "owner111"


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
        "proof_version": "test-1",
        "pool_address": POOL,
        "evidence_refs": ["test://semantic-proof"],
        "asset": {
            "field_path": "pool.pooledBase",
            "unit": TOKEN_UNITS,
            "decimals": 6,
            "mint": ASSET_MINT,
            "vault": ASSET_VAULT,
        },
        "counter": {
            "field_path": "pool.pooledQuote",
            "unit": TOKEN_UNITS,
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


class X1ReserveCrosscheckTests(unittest.TestCase):
    def test_two_leg_agreement_is_promotable_only_with_verified_observation_scope(self):
        result = run_x1_reserve_crosscheck(
            pool_detail(),
            vault_identity(),
            semantic_manifest(),
            rpc_balances(),
            observed_at=1000.0,
            observation_scope_verified=True,
        )

        self.assertEqual(result["overall_verification"], AGREEMENT)
        self.assertTrue(result["cmis_promotable"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["errors"], [])

        for role in ("asset", "counter"):
            self.assertTrue(result["roles"][role]["evidence"]["evidence_ready"])
            self.assertEqual(
                result["roles"][role]["verification"]["verification"]["status"],
                AGREEMENT,
            )
            self.assertEqual(
                result["roles"][role]["verification"]["data_quality"]["quality"],
                "HIGH",
            )
            self.assertTrue(result["roles"][role]["cmis_promotable"])

    def test_explicit_base_unit_provider_contract_is_supported_without_inference(self):
        detail = pool_detail()
        detail["raw_response"]["pool"]["pooledQuote"] = "9000000"
        manifest = semantic_manifest()
        manifest["counter"]["unit"] = BASE_UNITS

        result = run_x1_reserve_crosscheck(
            detail,
            vault_identity(),
            manifest,
            rpc_balances(),
            observed_at=1000.0,
            observation_scope_verified=True,
        )

        counter_evidence = result["roles"]["counter"]["evidence"]
        self.assertEqual(result["overall_verification"], AGREEMENT)
        self.assertEqual(counter_evidence["provider"]["raw_value"], "9000000")
        self.assertEqual(counter_evidence["provider"]["normalized_value"], "9")
        self.assertEqual(counter_evidence["rpc"]["normalized_value"], "9")

    def test_exact_agreement_without_verified_observation_scope_stays_non_promotable(self):
        result = run_x1_reserve_crosscheck(
            pool_detail(),
            vault_identity(),
            semantic_manifest(),
            rpc_balances(),
            observed_at=1000.0,
        )

        self.assertEqual(result["overall_verification"], AGREEMENT)
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["warnings"], ["observation_scope_unverified"])
        for role in ("asset", "counter"):
            verification = result["roles"][role]["verification"]
            self.assertEqual(verification["verification"]["status"], AGREEMENT)
            self.assertEqual(verification["data_quality"]["quality"], "LOW")
            self.assertIn(
                "FRESHNESS_UNVERIFIED",
                verification["data_quality"]["reasons"],
            )

    def test_claimed_observation_scope_without_observed_at_fails_closed(self):
        result = run_x1_reserve_crosscheck(
            pool_detail(),
            vault_identity(),
            semantic_manifest(),
            rpc_balances(),
            observed_at=None,
            observation_scope_verified=True,
        )

        self.assertEqual(result["overall_verification"], AGREEMENT)
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertIn("observation_scope_unverified", result["warnings"])
        self.assertIn(
            f"observation_scope:{OBSERVED_AT_MISSING}",
            result["errors"],
        )
        for role in ("asset", "counter"):
            self.assertFalse(
                result["roles"][role]["verification"]["data_quality"][
                    "freshness_verified"
                ]
            )

    def test_one_conflicting_leg_makes_overall_result_conflict(self):
        balances = rpc_balances()
        balances["asset"]["amount"] = "42500001"

        result = run_x1_reserve_crosscheck(
            pool_detail(),
            vault_identity(),
            semantic_manifest(),
            balances,
            observed_at=1000.0,
            observation_scope_verified=True,
        )

        self.assertEqual(result["overall_verification"], CONFLICT)
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(
            result["roles"]["asset"]["verification"]["verification"]["code"],
            VALUES_DISAGREE,
        )
        self.assertEqual(
            result["roles"]["counter"]["verification"]["verification"]["status"],
            AGREEMENT,
        )

    def test_rejected_semantic_proof_blocks_both_legs(self):
        manifest = semantic_manifest()
        manifest["proof_status"] = "asserted_only"

        result = run_x1_reserve_crosscheck(
            pool_detail(),
            vault_identity(),
            manifest,
            rpc_balances(),
            observed_at=1000.0,
            observation_scope_verified=True,
        )

        self.assertEqual(result["overall_verification"], INSUFFICIENT_EVIDENCE)
        self.assertFalse(result["cmis_promotable"])
        self.assertIn(
            "semantic_proof:semantic_proof_status_unproven",
            result["errors"],
        )
        for role in ("asset", "counter"):
            self.assertIsNone(result["roles"][role]["evidence"])
            self.assertEqual(
                result["roles"][role]["verification"]["verification"]["code"],
                SEMANTIC_PROOF_REJECTED,
            )

    def test_missing_rpc_leg_fails_closed_without_losing_other_leg(self):
        balances = rpc_balances()
        del balances["counter"]

        result = run_x1_reserve_crosscheck(
            pool_detail(),
            vault_identity(),
            semantic_manifest(),
            balances,
            observed_at=1000.0,
            observation_scope_verified=True,
        )

        self.assertEqual(result["overall_verification"], INSUFFICIENT_EVIDENCE)
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(
            result["roles"]["asset"]["verification"]["verification"]["status"],
            AGREEMENT,
        )
        self.assertEqual(
            result["roles"]["counter"]["verification"]["verification"]["code"],
            RPC_BALANCE_MISSING,
        )
        self.assertIn(f"counter_rpc:{RPC_BALANCE_MISSING}", result["errors"])

    def test_recorded_xencat_xnt_values_replay_as_exact_agreement_but_not_freshness_proof(self):
        """Regression for the read-only XENCAT/XNT evidence observed 2026-08-17.

        The values and account identities below were independently observed via
        X1.Ninja pool detail and direct X1 RPC. The observations were not proven
        to share one common observation scope, so this replay must not promote.
        """
        xencat_pool = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
        xencat_mint = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
        xencat_vault = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"
        xnt_mint = "So11111111111111111111111111111111111111112"
        xnt_vault = "7khUrkZN7Y6VgoSR8pASMFjHcKwqdh2cd6NRctXyjSZC"
        authority = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"

        live_pool_detail = {
            "chain": "x1",
            "pool_address_requested": xencat_pool,
            "raw_response": {
                "pool": {
                    "pooledBase": "1146902.928865",
                    "pooledQuote": "49.575383312",
                }
            },
        }
        live_identity = {
            "chain": "x1",
            "pool_address": xencat_pool,
            "asset_mint": xencat_mint,
            "asset_vault": xencat_vault,
            "counter_mint": xnt_mint,
            "counter_vault": xnt_vault,
            "shared_owner": authority,
            "identity_verified": True,
        }
        live_manifest = {
            "proof_status": PROOF_STATUS,
            "proof_version": "xencat-xnt-recorded-live-proof-v1",
            "pool_address": xencat_pool,
            "evidence_refs": [
                "github-actions://x1-live-verify/32027108070",
                "x1-rpc://slots/72254502-72254503",
            ],
            "asset": {
                "field_path": "pool.pooledBase",
                "unit": TOKEN_UNITS,
                "decimals": 6,
                "mint": xencat_mint,
                "vault": xencat_vault,
            },
            "counter": {
                "field_path": "pool.pooledQuote",
                "unit": TOKEN_UNITS,
                "decimals": 9,
                "mint": xnt_mint,
                "vault": xnt_vault,
            },
        }
        live_rpc = {
            "asset": {
                "chain": "x1",
                "source": "X1 RPC",
                "method": "getTokenAccountBalance",
                "account": xencat_vault,
                "slot": 72254502,
                "amount": "1146902928865",
                "decimals": 6,
            },
            "counter": {
                "chain": "x1",
                "source": "X1 RPC",
                "method": "getTokenAccountBalance",
                "account": xnt_vault,
                "slot": 72254503,
                "amount": "49575383312",
                "decimals": 9,
            },
        }

        result = run_x1_reserve_crosscheck(
            live_pool_detail,
            live_identity,
            live_manifest,
            live_rpc,
            observed_at=None,
            observation_scope_verified=False,
        )

        self.assertEqual(result["overall_verification"], AGREEMENT)
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(
            result["roles"]["asset"]["evidence"]["provider"]["normalized_value"],
            "1146902.928865",
        )
        self.assertEqual(
            result["roles"]["asset"]["evidence"]["rpc"]["normalized_value"],
            "1146902.928865",
        )
        self.assertEqual(
            result["roles"]["counter"]["evidence"]["provider"]["normalized_value"],
            "49.575383312",
        )
        self.assertEqual(
            result["roles"]["counter"]["evidence"]["rpc"]["normalized_value"],
            "49.575383312",
        )

    def test_inputs_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "rpc_balances must be a mapping"):
            run_x1_reserve_crosscheck(
                pool_detail(),
                vault_identity(),
                semantic_manifest(),
                [],
                observed_at=1,
            )


if __name__ == "__main__":
    unittest.main()
