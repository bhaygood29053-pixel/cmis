import json
import os
import unittest

from liquidity_scout.providers.x1.reserve_live_evidence import (
    collect_x1_reserve_live_evidence,
)
from liquidity_scout.providers.x1.reserve_scope_measurements import (
    measure_x1_reserve_scope,
)


RUN_LIVE = os.getenv("RUN_X1_RESERVE_SCOPE_LIVE") == "1"

POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
ASSET_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
ASSET_VAULT = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"
COUNTER_MINT = "So11111111111111111111111111111111111111112"
COUNTER_VAULT = "7khUrkZN7Y6VgoSR8pASMFjHcKwqdh2cd6NRctXyjSZC"
SHARED_AUTHORITY = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"

ROLE_SPECS = {
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


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_RESERVE_SCOPE_LIVE=1 to run the read-only reserve scope probe",
)
class X1ReserveScopeLiveTests(unittest.TestCase):
    def test_live_xencat_xnt_scope_measurements_without_freshness_promotion(self):
        bundle = collect_x1_reserve_live_evidence(
            POOL,
            ROLE_SPECS,
            shared_authority=SHARED_AUTHORITY,
        )
        scope = measure_x1_reserve_scope(bundle)

        diagnostic = {
            "pool_address": bundle["pool_address"],
            "collection": bundle["collection"],
            "provider": {
                "observed_at": bundle["provider"]["observed_at"],
                "last_synced_at": bundle["provider"]["last_synced_at"],
                "last_updated": bundle["provider"]["last_updated"],
            },
            "roles": {
                role: {
                    "provider_field_path": bundle["roles"][role]["expected"][
                        "provider_field_path"
                    ],
                    "provider_raw_value": bundle["roles"][role][
                        "provider_raw_value"
                    ],
                    "rpc_balance_slot": bundle["roles"][role]["rpc_balance"].get(
                        "slot"
                    ),
                    "rpc_balance_amount": bundle["roles"][role]["rpc_balance"].get(
                        "amount"
                    ),
                    "rpc_balance_decimals": bundle["roles"][role][
                        "rpc_balance"
                    ].get("decimals"),
                    "rpc_identity_slot": bundle["roles"][role][
                        "rpc_identity_observation"
                    ].get("slot"),
                    "rpc_identity_verified": bundle["roles"][role][
                        "rpc_identity_verification"
                    ].get("identity_verified"),
                    "rpc_decimals_match": bundle["roles"][role][
                        "rpc_decimals_match"
                    ],
                }
                for role in ("asset", "counter")
            },
            "scope_status": scope["status"],
            "scope_metrics": scope["metrics"],
            "scope_warnings": scope["warnings"],
            "scope_errors": scope["errors"],
            "freshness_verified": scope["freshness_verified"],
            "observation_scope_verified": scope["observation_scope_verified"],
            "cmis_promotable": scope["cmis_promotable"],
        }
        print("X1 XENCAT/XNT bounded reserve scope probe")
        print(json.dumps(diagnostic, indent=2, sort_keys=True, default=str))

        self.assertEqual(bundle["service"], "x1_reserve_live_evidence")
        self.assertEqual(bundle["pool_address"], POOL)
        self.assertTrue(bundle["rpc_identity_verified"])
        self.assertTrue(bundle["rpc_decimals_match"])
        self.assertFalse(bundle["reserve_field_semantics_verified"])
        self.assertFalse(bundle["observation_scope_verified"])
        self.assertFalse(bundle["value_agreement_verified"])
        self.assertFalse(bundle["cmis_promotable"])

        self.assertIn(scope["status"], {"ok", "partial"})
        self.assertEqual(scope["errors"], [])
        self.assertTrue(scope["evidence_flags"]["rpc_identity_verified"])
        self.assertTrue(scope["evidence_flags"]["rpc_decimals_match"])
        self.assertFalse(scope["freshness_verified"])
        self.assertFalse(scope["observation_scope_verified"])
        self.assertFalse(scope["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
