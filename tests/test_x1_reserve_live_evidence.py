import unittest

from liquidity_scout.providers.x1.reserve_live_evidence import (
    collect_x1_reserve_live_evidence,
)
from liquidity_scout.providers.x1.rpc_token_account import ENCODING, RPC_METHOD, RPC_SOURCE


POOL = "pool111"
OWNER = "owner111"
ASSET_VAULT = "asset-vault"
ASSET_MINT = "asset-mint"
COUNTER_VAULT = "counter-vault"
COUNTER_MINT = "counter-mint"


def role_specs():
    return {
        "asset": {
            "vault": ASSET_VAULT,
            "mint": ASSET_MINT,
            "decimals": 6,
            "provider_field_path": "pool.pooledBase",
        },
        "counter": {
            "vault": COUNTER_VAULT,
            "mint": COUNTER_MINT,
            "decimals": 9,
            "provider_field_path": "pool.pooledQuote",
        },
    }


def pool_detail(address, *, api_key=None):
    return {
        "chain": "x1",
        "source": "X1.Ninja Developer API",
        "pool_address_requested": address,
        "observed_at": 100.5,
        "raw_response": {
            "pool": {
                "pooledBase": "1146902.928865",
                "pooledQuote": "49.575383312",
                "lastSyncedAt": "2026-08-17T11:32:35.037Z",
            },
            "lastUpdated": 1786966355037,
        },
        "cmis_promotable": False,
    }


def balance(account, *, rpc_url=None, commitment="confirmed"):
    if account == ASSET_VAULT:
        return {
            "chain": "x1",
            "source": "X1 RPC",
            "method": "getTokenAccountBalance",
            "account": account,
            "slot": 72254502,
            "amount": "1146902928865",
            "decimals": 6,
            "ui_amount_string": "1146902.928865",
            "cmis_promotable": False,
        }
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getTokenAccountBalance",
        "account": account,
        "slot": 72254503,
        "amount": "49575383312",
        "decimals": 9,
        "ui_amount_string": "49.575383312",
        "cmis_promotable": False,
    }


def identity(account, *, rpc_url=None, commitment="confirmed"):
    is_asset = account == ASSET_VAULT
    return {
        "chain": "x1",
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "encoding": ENCODING,
        "account": account,
        "slot": 72254502 if is_asset else 72254503,
        "mint": ASSET_MINT if is_asset else COUNTER_MINT,
        "authority": OWNER,
        "token_account_fields_parsed": True,
        "cmis_promotable": False,
    }


def clock():
    values = iter([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
    return lambda: next(values)


class X1ReserveLiveEvidenceTests(unittest.TestCase):
    def test_collects_bounded_provider_rpc_bundle_without_promotion(self):
        result = collect_x1_reserve_live_evidence(
            POOL,
            role_specs(),
            shared_authority=OWNER,
            pool_detail_fetcher=pool_detail,
            balance_fetcher=balance,
            identity_fetcher=identity,
            clock=clock(),
        )

        self.assertEqual(result["pool_address"], POOL)
        self.assertEqual(result["collection"]["started_at"], 100.0)
        self.assertEqual(result["collection"]["ended_at"], 106.0)
        self.assertEqual(result["collection"]["duration_seconds"], 6.0)
        self.assertEqual(len(result["collection"]["sequence"]), 5)
        self.assertEqual(
            result["provider"]["last_synced_at"],
            "2026-08-17T11:32:35.037Z",
        )
        self.assertEqual(result["provider"]["last_updated"], 1786966355037)
        self.assertEqual(
            result["roles"]["asset"]["provider_raw_value"],
            "1146902.928865",
        )
        self.assertEqual(
            result["roles"]["counter"]["rpc_balance"]["amount"],
            "49575383312",
        )
        self.assertTrue(result["rpc_identity_verified"])
        self.assertTrue(result["rpc_decimals_match"])
        self.assertFalse(result["reserve_field_semantics_verified"])
        self.assertFalse(result["observation_scope_verified"])
        self.assertFalse(result["value_agreement_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertIn(
            "observation_scope_not_verified_by_collector",
            result["warnings"],
        )

    def test_identity_mismatch_is_recorded_without_false_promotion(self):
        def wrong_identity(account, *, rpc_url=None, commitment="confirmed"):
            item = identity(account, rpc_url=rpc_url, commitment=commitment)
            if account == ASSET_VAULT:
                item["mint"] = "other-mint"
            return item

        result = collect_x1_reserve_live_evidence(
            POOL,
            role_specs(),
            shared_authority=OWNER,
            pool_detail_fetcher=pool_detail,
            balance_fetcher=balance,
            identity_fetcher=wrong_identity,
            clock=clock(),
        )

        self.assertFalse(result["rpc_identity_verified"])
        self.assertFalse(
            result["roles"]["asset"]["rpc_identity_verification"][
                "identity_verified"
            ]
        )
        self.assertIn(
            "mint_identity_mismatch",
            result["roles"]["asset"]["rpc_identity_verification"][
                "rejection_reasons"
            ],
        )
        self.assertFalse(result["cmis_promotable"])

    def test_decimal_mismatch_is_recorded_without_semantic_inference(self):
        def wrong_balance(account, *, rpc_url=None, commitment="confirmed"):
            item = balance(account, rpc_url=rpc_url, commitment=commitment)
            if account == COUNTER_VAULT:
                item["decimals"] = 6
            return item

        result = collect_x1_reserve_live_evidence(
            POOL,
            role_specs(),
            shared_authority=OWNER,
            pool_detail_fetcher=pool_detail,
            balance_fetcher=wrong_balance,
            identity_fetcher=identity,
            clock=clock(),
        )

        self.assertFalse(result["rpc_decimals_match"])
        self.assertFalse(result["roles"]["counter"]["rpc_decimals_match"])
        self.assertFalse(result["reserve_field_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_missing_provider_field_path_fails_closed(self):
        specs = role_specs()
        specs["asset"]["provider_field_path"] = "pool.missing"
        with self.assertRaisesRegex(ValueError, "provider field path is missing"):
            collect_x1_reserve_live_evidence(
                POOL,
                specs,
                shared_authority=OWNER,
                pool_detail_fetcher=pool_detail,
                balance_fetcher=balance,
                identity_fetcher=identity,
                clock=clock(),
            )

    def test_pool_identity_mismatch_fails_closed(self):
        def wrong_pool(address, *, api_key=None):
            item = pool_detail(address, api_key=api_key)
            item["pool_address_requested"] = "other-pool"
            return item

        with self.assertRaisesRegex(ValueError, "does not match requested pool"):
            collect_x1_reserve_live_evidence(
                POOL,
                role_specs(),
                shared_authority=OWNER,
                pool_detail_fetcher=wrong_pool,
                balance_fetcher=balance,
                identity_fetcher=identity,
                clock=clock(),
            )

    def test_role_specs_are_explicit_and_required(self):
        with self.assertRaisesRegex(ValueError, "counter role specification is required"):
            collect_x1_reserve_live_evidence(
                POOL,
                {"asset": role_specs()["asset"]},
                shared_authority=OWNER,
                pool_detail_fetcher=pool_detail,
                balance_fetcher=balance,
                identity_fetcher=identity,
                clock=clock(),
            )

    def test_invalid_clock_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "invalid timestamp"):
            collect_x1_reserve_live_evidence(
                POOL,
                role_specs(),
                shared_authority=OWNER,
                pool_detail_fetcher=pool_detail,
                balance_fetcher=balance,
                identity_fetcher=identity,
                clock=lambda: True,
            )


if __name__ == "__main__":
    unittest.main()
