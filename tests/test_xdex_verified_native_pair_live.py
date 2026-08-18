"""Opt-in read-only XDEX contract probe for one structurally verified native pair.

This probe exists because the public XDEX pool-list can legitimately be empty while
read-only quote/history endpoints still accept exact mint identifiers. The pair is
therefore established from the already verified XDEX program pool state, then the
live provider response is checked only for observable identity/schema properties.
No quote, impact, fee, route-quality, or fill semantic is promoted by this test.
"""

import json
import os
import time
import unittest
from collections.abc import Mapping

from liquidity_scout.providers.x1 import XDEXReadOnlyProvider
from liquidity_scout.providers.x1.candidate_pool_role import verify_candidate_pool_role


RUN_LIVE = os.getenv("RUN_XDEX_LIVE_TESTS") == "1"

_XDEX_PROGRAM_ID = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
_XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
_XENCAT_POOL_ADDRESS = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
_NATIVE_XNT_MINT = "So11111111111111111111111111111111111111112"
_REDACTED_KEY_FRAGMENTS = (
    "transaction",
    "serialized",
    "signature",
    "secret",
    "private",
    "keypair",
    "wallet",
)


def _public_evidence(value, *, depth=0):
    if depth > 6:
        return "<depth-limit>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.casefold()
            if any(fragment in lowered for fragment in _REDACTED_KEY_FRAGMENTS):
                cleaned[key_text] = "<redacted-non-analysis-field>"
            else:
                cleaned[key_text] = _public_evidence(item, depth=depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_public_evidence(item, depth=depth + 1) for item in value[:25]]
    return f"<{type(value).__name__}>"


def _counter_mint(structural_report):
    decoded = structural_report.get("decoded_state")
    if not isinstance(decoded, Mapping):
        return None
    mint_0 = str(decoded.get("mint_0") or "").strip()
    mint_1 = str(decoded.get("mint_1") or "").strip()
    if _XENCAT_MINT == mint_0:
        return mint_1
    if _XENCAT_MINT == mint_1:
        return mint_0
    return None


@unittest.skipUnless(
    RUN_LIVE,
    "Set RUN_XDEX_LIVE_TESTS=1 to probe the live read-only XDEX contract.",
)
class XDEXVerifiedNativePairLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = verify_candidate_pool_role(
            account=_XENCAT_POOL_ADDRESS,
            target_mint=_XENCAT_MINT,
            program_id=_XDEX_PROGRAM_ID,
            signature_limit=1,
        )
        cls.assertTrue = staticmethod(unittest.TestCase().assertTrue)
        if report.get("summary", {}).get("pool_state_structural_role_verified") is not True:
            raise RuntimeError("Pinned XENCAT pool failed structural re-verification.")
        counter = _counter_mint(report)
        if counter != _NATIVE_XNT_MINT:
            raise RuntimeError(
                "Pinned XENCAT pool did not re-verify the expected native-XNT counter mint."
            )

        cls.provider = XDEXReadOnlyProvider(timeout=20)
        identity_probe = cls.provider.swap_quote(
            _XENCAT_MINT,
            counter,
            1,
            is_exact_amount_in=True,
        )
        if identity_probe.get("inputMint") != _XENCAT_MINT:
            raise RuntimeError("XDEX quote response did not preserve the requested input mint.")
        if identity_probe.get("outputMint") != counter:
            raise RuntimeError("XDEX quote response did not preserve the requested output mint.")
        if not str(identity_probe.get("amm_config_address") or "").strip():
            raise RuntimeError("XDEX quote response omitted its AMM config identity.")

        cls.base_address = _XENCAT_MINT
        cls.quote_address = counter
        print(
            "[XDEX verified native-pair identity evidence] "
            + json.dumps(
                _public_evidence(
                    {
                        "pool": _XENCAT_POOL_ADDRESS,
                        "base_address": cls.base_address,
                        "quote_address": cls.quote_address,
                        "structural_role_verified": True,
                        "identity_probe": identity_probe,
                        "quote_semantics_verified": False,
                    }
                ),
                sort_keys=True,
                default=str,
            )
        )

    def test_live_token_price_returns_public_mapping(self):
        data = self.provider.token_price(self.base_address)
        self.assertIsInstance(data, dict)
        self.assertTrue(data)
        print(
            "[XDEX token-price evidence] "
            + json.dumps(_public_evidence(data), sort_keys=True, default=str)
        )

    def test_live_history_exposes_candidate_time_and_price_fields(self):
        time_to = int(time.time())
        time_from = time_to - (7 * 24 * 60 * 60)
        points = self.provider.price_history(
            self.base_address,
            self.quote_address,
            time_from=time_from,
            time_to=time_to,
        )
        self.assertIsInstance(points, list)
        self.assertTrue(points, "XDEX returned no history points for the verified pair.")
        for point in points[:10]:
            self.assertIsInstance(point, Mapping)
            self.assertTrue("timestamp" in point or "time" in point)
            self.assertIn("price", point)
        print(
            "[XDEX history candidate-field evidence] "
            + json.dumps(_public_evidence(points[:3]), sort_keys=True, default=str)
        )

    def test_live_quote_preserves_identity_and_candidate_fields(self):
        observations = []
        for amount in (1, 2):
            data = self.provider.swap_quote(
                self.base_address,
                self.quote_address,
                amount,
                is_exact_amount_in=True,
            )
            self.assertEqual(data.get("inputMint"), self.base_address)
            self.assertEqual(data.get("outputMint"), self.quote_address)
            self.assertEqual(data.get("inputAmount"), amount)
            self.assertIn("outputAmount", data)
            self.assertIn("rate", data)
            self.assertIn("priceImpactPct", data)
            self.assertTrue(str(data.get("amm_config_address") or "").strip())
            observations.append(data)
        print(
            "[XDEX quote candidate-field evidence] "
            + json.dumps(_public_evidence(observations), sort_keys=True, default=str)
        )
        # Scaling/field presence is observable. Meaning, fee decomposition, route quality,
        # fill semantics, and CMIS promotion remain unverified by this test.


if __name__ == "__main__":
    unittest.main()
