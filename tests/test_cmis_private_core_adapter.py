from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from liquidity_scout import cmis_private_core


class CMISPrivateCoreAdapterTests(unittest.TestCase):
    def test_public_transition_fallback_remains_available_during_phase3(self):
        with patch.object(cmis_private_core, "_load_private_api", return_value=None):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CMIS_PRIVATE_CORE_REQUIRED", None)
                contract = cmis_private_core.load_runtime_contract()

        self.assertEqual(contract["source"], "public-transition")
        self.assertEqual(
            contract["contract"],
            cmis_private_core.PUBLIC_TRANSITION_CONTRACT,
        )
        self.assertTrue(callable(contract["gateway_class"]))

    def test_required_mode_fails_closed_without_private_distribution(self):
        with patch.object(cmis_private_core, "_load_private_api", return_value=None):
            with patch.dict(os.environ, {"CMIS_PRIVATE_CORE_REQUIRED": "1"}):
                with self.assertRaises(cmis_private_core.PrivateCoreUnavailable):
                    cmis_private_core.load_runtime_contract()

    def test_private_contract_must_match_expected_version(self):
        class FakePrivateAPI:
            @staticmethod
            def runtime_contract():
                return {
                    "contract": "wrong/v1",
                    "gateway_class": object,
                    "supported_services": (),
                    "supported_chains": (),
                    "known_chains": (),
                }

        with patch.object(cmis_private_core, "_load_private_api", return_value=FakePrivateAPI):
            with self.assertRaises(cmis_private_core.PrivateCoreUnavailable):
                cmis_private_core.load_runtime_contract()


if __name__ == "__main__":
    unittest.main()
