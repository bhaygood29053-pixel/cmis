import unittest

from liquidity_scout.providers.x1.reserve_scope_artifact import (
    build_x1_reserve_scope_artifact,
)


def bundle():
    return {
        "service": "x1_reserve_live_evidence",
        "version": "1.0",
        "chain": "x1",
        "pool_address": "pool111",
        "collection": {
            "started_at": 100.0,
            "ended_at": 106.0,
            "duration_seconds": 6.0,
            "sequence": [
                {
                    "step": "provider_pool_detail",
                    "completed_at": 101.0,
                    "provider_observed_at": 100.5,
                    "secret_extra": "do-not-copy",
                },
                {"step": "asset_rpc_balance", "completed_at": 102.0, "slot": 10},
            ],
        },
        "provider": {
            "source": "X1.Ninja Developer API",
            "observed_at": 100.5,
            "last_synced_at": "1970-01-01T00:01:40Z",
            "last_updated": 1234567890,
            "pool_detail": {
                "raw_response": {"secret_transport_payload": True},
                "api_key": "never-copy",
            },
        },
        "roles": {
            "asset": {
                "expected": {
                    "vault": "asset-vault",
                    "mint": "asset-mint",
                    "decimals": 6,
                    "shared_authority": "owner111",
                    "provider_field_path": "pool.pooledBase",
                },
                "provider_raw_value": "42.5",
                "rpc_balance": {
                    "source": "X1 RPC",
                    "method": "getTokenAccountBalance",
                    "rpc_url": "https://rpc.example",
                    "account": "asset-vault",
                    "slot": 10,
                    "amount": "42500000",
                    "decimals": 6,
                    "ui_amount_string": "42.5",
                    "raw_response": {"secret": True},
                },
                "rpc_identity_observation": {
                    "source": "X1 RPC",
                    "method": "getAccountInfo",
                    "encoding": "jsonParsed",
                    "account": "asset-vault",
                    "slot": 10,
                    "mint": "asset-mint",
                    "authority": "owner111",
                    "raw_response": {"secret": True},
                },
                "rpc_identity_verification": {
                    "identity_verified": True,
                    "rejection_reasons": [],
                },
                "rpc_decimals_match": True,
            },
            "counter": {
                "expected": {
                    "vault": "counter-vault",
                    "mint": "counter-mint",
                    "decimals": 9,
                    "shared_authority": "owner111",
                    "provider_field_path": "pool.pooledQuote",
                },
                "provider_raw_value": "9",
                "rpc_balance": {
                    "source": "X1 RPC",
                    "method": "getTokenAccountBalance",
                    "account": "counter-vault",
                    "slot": 11,
                    "amount": "9000000000",
                    "decimals": 9,
                    "ui_amount_string": "9",
                },
                "rpc_identity_observation": {
                    "source": "X1 RPC",
                    "method": "getAccountInfo",
                    "encoding": "jsonParsed",
                    "account": "counter-vault",
                    "slot": 12,
                    "mint": "counter-mint",
                    "authority": "owner111",
                },
                "rpc_identity_verification": {
                    "identity_verified": True,
                    "rejection_reasons": [],
                },
                "rpc_decimals_match": True,
            },
        },
        "rpc_identity_verified": True,
        "rpc_decimals_match": True,
        "reserve_field_semantics_verified": False,
        "value_agreement_verified": False,
        "cmis_promotable": False,
        "warnings": ["bundle-warning"],
        "errors": [],
    }


def scope():
    return {
        "service": "x1_reserve_scope_measurements",
        "version": "1.0",
        "chain": "x1",
        "status": "ok",
        "pool_address": "pool111",
        "metrics": {
            "collection_started_at": 100.0,
            "collection_ended_at": 106.0,
            "collection_duration_seconds": 6.0,
            "collection_sequence_monotonic": True,
            "provider_observed_at": 100.5,
            "provider_observed_within_collection": True,
            "provider_reported_last_synced_at": "1970-01-01T00:01:40Z",
            "provider_reported_last_synced_epoch_seconds": 100.0,
            "provider_reported_last_synced_age_at_collection_end_seconds": 6.0,
            "provider_last_updated_raw": 1234567890,
            "rpc_min_slot": 10,
            "rpc_max_slot": 12,
            "rpc_slot_span": 2,
            "roles": {
                "asset": {
                    "balance_slot": 10,
                    "identity_slot": 10,
                    "balance_identity_slot_delta": 0,
                    "balance_identity_same_slot": True,
                    "rpc_identity_verified": True,
                    "rpc_decimals_match": True,
                },
                "counter": {
                    "balance_slot": 11,
                    "identity_slot": 12,
                    "balance_identity_slot_delta": 1,
                    "balance_identity_same_slot": False,
                    "rpc_identity_verified": True,
                    "rpc_decimals_match": True,
                },
            },
        },
        "evidence_flags": {
            "collection_bounds_monotonic": True,
            "rpc_identity_verified": True,
            "rpc_decimals_match": True,
        },
        "freshness_verified": False,
        "observation_scope_verified": False,
        "cmis_promotable": False,
        "warnings": ["scope-warning"],
        "errors": [],
    }


def all_keys(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(str(key).casefold())
            found.update(all_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(all_keys(child))
    return found


class X1ReserveScopeArtifactTests(unittest.TestCase):
    def test_builds_sanitized_replayable_artifact_without_promotion(self):
        result = build_x1_reserve_scope_artifact(bundle(), scope())

        self.assertEqual(result["evidence_type"], "x1_reserve_scope_evidence")
        self.assertEqual(result["pool_address"], "pool111")
        self.assertTrue(result["artifact_sanitized"])
        self.assertFalse(result["cmis_promotable"])
        self.assertTrue(result["identity"]["shared_authority_consistent"])
        self.assertEqual(result["identity"]["shared_authority"], "owner111")
        self.assertEqual(
            result["roles"]["asset"]["provider_raw_value"],
            "42.5",
        )
        self.assertEqual(
            result["roles"]["asset"]["rpc_balance"]["amount"],
            "42500000",
        )
        self.assertEqual(result["scope"]["metrics"]["rpc_slot_span"], 2)
        self.assertIn("bundle-warning", result["warnings"])
        self.assertIn("scope-warning", result["warnings"])

    def test_raw_transport_and_secret_shaped_fields_are_not_copied(self):
        result = build_x1_reserve_scope_artifact(bundle(), scope())
        keys = all_keys(result)

        for forbidden in (
            "raw_response",
            "rpc_url",
            "api_key",
            "authorization",
            "headers",
            "secret_extra",
        ):
            self.assertNotIn(forbidden, keys)

    def test_upstream_promotion_claims_never_promote_artifact(self):
        input_bundle = bundle()
        input_scope = scope()
        input_bundle["cmis_promotable"] = True
        input_scope["cmis_promotable"] = True
        input_scope["freshness_verified"] = True
        input_scope["observation_scope_verified"] = True

        result = build_x1_reserve_scope_artifact(input_bundle, input_scope)

        self.assertTrue(
            result["verification_state"]["upstream_bundle_cmis_promotable"]
        )
        self.assertTrue(
            result["verification_state"]["upstream_scope_cmis_promotable"]
        )
        self.assertTrue(result["verification_state"]["freshness_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_identity_rejection_reasons_are_preserved(self):
        input_bundle = bundle()
        verification = input_bundle["roles"]["asset"][
            "rpc_identity_verification"
        ]
        verification["identity_verified"] = False
        verification["rejection_reasons"] = ["mint_identity_mismatch"]

        result = build_x1_reserve_scope_artifact(input_bundle, scope())

        self.assertFalse(result["roles"]["asset"]["rpc_identity"]["identity_verified"])
        self.assertEqual(
            result["roles"]["asset"]["rpc_identity"]["rejection_reasons"],
            ["mint_identity_mismatch"],
        )

    def test_inconsistent_expected_authority_is_recorded_not_hidden(self):
        input_bundle = bundle()
        input_bundle["roles"]["counter"]["expected"][
            "shared_authority"
        ] = "other-owner"

        result = build_x1_reserve_scope_artifact(input_bundle, scope())

        self.assertFalse(result["identity"]["shared_authority_consistent"])
        self.assertIsNone(result["identity"]["shared_authority"])
        self.assertIn(
            "expected_shared_authority_inconsistent_or_missing",
            result["warnings"],
        )
        self.assertFalse(result["cmis_promotable"])

    def test_scope_pool_must_match_bundle(self):
        input_scope = scope()
        input_scope["pool_address"] = "other-pool"

        with self.assertRaisesRegex(ValueError, "does not match bundle"):
            build_x1_reserve_scope_artifact(bundle(), input_scope)

    def test_service_contracts_are_required(self):
        input_bundle = bundle()
        input_bundle["service"] = "other"
        with self.assertRaisesRegex(ValueError, "unexpected reserve evidence"):
            build_x1_reserve_scope_artifact(input_bundle, scope())

        input_scope = scope()
        input_scope["service"] = "other"
        with self.assertRaisesRegex(ValueError, "unexpected reserve scope"):
            build_x1_reserve_scope_artifact(bundle(), input_scope)

    def test_inputs_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "bundle must be a mapping"):
            build_x1_reserve_scope_artifact([], scope())
        with self.assertRaisesRegex(TypeError, "scope must be a mapping"):
            build_x1_reserve_scope_artifact(bundle(), [])


if __name__ == "__main__":
    unittest.main()
