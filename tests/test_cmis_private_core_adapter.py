from __future__ import annotations

import unittest
from unittest.mock import patch

from liquidity_scout import cmis_private_core


class CMISPrivateCoreAdapterTests(unittest.TestCase):
    def test_private_core_is_mandatory_after_phase3_cutover(self):
        self.assertTrue(cmis_private_core.private_core_required())

    def test_missing_private_distribution_always_fails_closed(self):
        with patch.object(cmis_private_core, "_load_private_api", return_value=None):
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

        with patch.object(
            cmis_private_core,
            "_load_private_api",
            return_value=FakePrivateAPI,
        ):
            with self.assertRaises(cmis_private_core.PrivateCoreUnavailable):
                cmis_private_core.load_runtime_contract()

    def test_status_reports_no_public_fallback(self):
        with patch.object(cmis_private_core, "_load_private_api", return_value=None):
            status = cmis_private_core.private_core_status()

        self.assertEqual(
            status,
            {
                "available": False,
                "required": True,
                "source": "unavailable",
                "expected_contract": "cmis-private-core/v1",
            },
        )


if __name__ == "__main__":
    unittest.main()
