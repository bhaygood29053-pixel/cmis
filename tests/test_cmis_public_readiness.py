import unittest
from unittest.mock import patch

from urllib.request import Request

from scripts.check_cmis_public_readiness import (
    IDENTITY_CONTRACT,
    PreflightError,
    _base_url,
    _read_json,
    check_public_deployment,
)


def capabilities(*, limitations=None):
    return {
        "service": "cmis_gateway",
        "contract_version": "1.11.0",
        "chains": {
            "x1": {
                "services": {
                    "asset_lookup": {
                        "state": "supported",
                        "callable": True,
                        "requirements": [],
                        "limitations": limitations
                        or [
                            "exact_mint_is_canonical_fungible_identity_root",
                            "same_mint_descriptor_conflicts_return_partial",
                            "xdex_unavailable_is_not_metaplex_only",
                            "symbol_or_name_never_reconciles_different_mints",
                        ],
                        "identity_contract_version": IDENTITY_CONTRACT,
                        "exact_mint_normalization": True,
                        "normalized_identity_root": "mint",
                        "metaplex_xdex_reconciliation": True,
                    }
                }
            }
        },
    }


class CMISPublicReadinessTests(unittest.TestCase):
    def test_public_url_requires_https(self):
        with self.assertRaisesRegex(PreflightError, "https"):
            _base_url("http://cmis.example.com")

    def test_public_url_rejects_loopback(self):
        with self.assertRaisesRegex(PreflightError, "loopback"):
            _base_url("https://127.0.0.1")

    @patch(
        "scripts.check_cmis_public_readiness.socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ],
    )
    def test_public_url_requires_origin_only(self, _):
        with self.assertRaisesRegex(PreflightError, "origin"):
            _base_url("https://cmis.example.com/v1/cmis")

    @patch(
        "scripts.check_cmis_public_readiness.socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("10.0.0.8", 443)),
        ],
    )
    def test_public_url_rejects_private_dns_resolution(self, _):
        with self.assertRaisesRegex(PreflightError, "globally routable"):
            _base_url("https://cmis.example.com")

    @patch(
        "scripts.check_cmis_public_readiness._base_url",
        return_value="https://cmis.example.com",
    )
    def test_public_deployment_requires_bearer_key(self, _):
        with self.assertRaisesRegex(PreflightError, "CMIS_API_KEY"):
            check_public_deployment(
                base_url="https://cmis.example.com",
                api_key="",
            )

    @patch("scripts.check_cmis_public_readiness.urlopen")
    def test_read_json_rejects_redirects(self, urlopen_mock):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def geturl(self):
                return "https://other.example.com/healthz"

            def read(self):
                return b'{"service":"cmis_gateway","status":"ok"}'

        urlopen_mock.return_value = Response()
        with self.assertRaisesRegex(PreflightError, "redirected"):
            _read_json(
                Request("https://cmis.example.com/healthz", method="GET"),
                timeout=1,
                expected_status=200,
            )

    @patch(
        "scripts.check_cmis_public_readiness._base_url",
        return_value="https://cmis.example.com",
    )
    def test_public_deployment_rejects_weak_bearer_key(self, _):
        with self.assertRaisesRegex(PreflightError, "at least 32"):
            check_public_deployment(
                base_url="https://cmis.example.com",
                api_key="too-short",
            )

    @patch(
        "scripts.check_cmis_public_readiness._base_url",
        return_value="https://cmis.example.com",
    )
    @patch("scripts.check_cmis_public_readiness._read_json")
    def test_public_deployment_accepts_exact_identity_contract(self, read_json, _):
        read_json.side_effect = [
            {"service": "cmis_gateway", "status": "ok"},
            {
                "status": "error",
                "error": {"code": "unauthorized"},
            },
            capabilities(),
        ]

        result = check_public_deployment(
            base_url="https://cmis.example.com",
            api_key="s".repeat(32),
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["cmis_contract_version"], "1.11.0")
        self.assertEqual(result["identity_contract_version"], IDENTITY_CONTRACT)
        self.assertEqual(result["normalized_identity_root"], "mint")
        self.assertEqual(read_json.call_count, 3)

    @patch(
        "scripts.check_cmis_public_readiness._base_url",
        return_value="https://cmis.example.com",
    )
    @patch("scripts.check_cmis_public_readiness._read_json")
    def test_public_deployment_rejects_malformed_limitations(self, read_json, _):
        malformed = capabilities()
        malformed["chains"]["x1"]["services"]["asset_lookup"]["limitations"] = [
            {"code": "not-text"}
        ]
        read_json.side_effect = [
            {"service": "cmis_gateway", "status": "ok"},
            {
                "status": "error",
                "error": {"code": "unauthorized"},
            },
            malformed,
        ]

        with self.assertRaisesRegex(PreflightError, "limitations are malformed"):
            check_public_deployment(
                base_url="https://cmis.example.com",
                api_key="s".repeat(32),
            )

    @patch(
        "scripts.check_cmis_public_readiness._base_url",
        return_value="https://cmis.example.com",
    )
    @patch("scripts.check_cmis_public_readiness._read_json")
    def test_public_deployment_fails_on_weakened_identity_contract(self, read_json, _):
        weakened = capabilities(
            limitations=[
                "exact_mint_is_canonical_fungible_identity_root",
                "same_mint_descriptor_conflicts_return_partial",
                "symbol_or_name_never_reconciles_different_mints",
            ]
        )
        read_json.side_effect = [
            {"service": "cmis_gateway", "status": "ok"},
            {
                "status": "error",
                "error": {"code": "unauthorized"},
            },
            weakened,
        ]

        with self.assertRaisesRegex(PreflightError, "limitations are missing"):
            check_public_deployment(
                base_url="https://cmis.example.com",
                api_key="s".repeat(32),
            )


if __name__ == "__main__":
    unittest.main()
