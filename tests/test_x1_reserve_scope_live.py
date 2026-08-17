"""Opt-in live XENCAT/XNT reserve scope evidence probe.

The optional JSON artifact is intentionally sanitized by the provider artifact
contract: it contains public pool/vault/mint identifiers, provider reserve
values, RPC amounts/slots, and deterministic scope measurements needed for
replay, but excludes credentials and raw HTTP/RPC response payloads. The probe
never marks freshness or CMIS promotion.
"""

import json
import os
import unittest

from liquidity_scout.providers.x1.reserve_live_evidence import (
    collect_x1_reserve_live_evidence,
)
from liquidity_scout.providers.x1.reserve_scope_artifact import (
    build_x1_reserve_scope_artifact,
)
from liquidity_scout.providers.x1.reserve_scope_measurements import (
    measure_x1_reserve_scope,
)


RUN_LIVE = os.getenv("RUN_X1_RESERVE_SCOPE_LIVE") == "1"
OUTPUT_PATH = os.getenv("X1_RESERVE_SCOPE_OUTPUT")

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
        artifact = build_x1_reserve_scope_artifact(bundle, scope)

        rendered = json.dumps(artifact, indent=2, sort_keys=True, default=str)
        print("X1 XENCAT/XNT bounded reserve scope probe")
        print(rendered)

        if OUTPUT_PATH:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.write("\n")
            print(f"Sanitized reserve scope evidence written to: {OUTPUT_PATH}")

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

        self.assertEqual(artifact["evidence_type"], "x1_reserve_scope_evidence")
        self.assertTrue(artifact["artifact_sanitized"])
        self.assertEqual(artifact["pool_address"], POOL)
        self.assertTrue(artifact["identity"]["shared_authority_consistent"])
        self.assertEqual(artifact["identity"]["shared_authority"], SHARED_AUTHORITY)
        self.assertFalse(artifact["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
