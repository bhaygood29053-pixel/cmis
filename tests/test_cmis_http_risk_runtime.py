import unittest
from unittest.mock import patch

from liquidity_scout.cmis import http
from liquidity_scout.cmis_private_core import PrivateCoreUnavailable


class FakePrivateGateway:
    pass


class CMISHTTPRiskRuntimeTests(unittest.TestCase):
    def _contract(self):
        return {
            "contract": "cmis-private-core/v1",
            "source": "private",
            "gateway_class": FakePrivateGateway,
            "supported_services": tuple(http.SUPPORTED_SERVICES),
            "supported_chains": tuple(http.SUPPORTED_CHAINS),
            "known_chains": tuple(http.KNOWN_CHAINS),
        }

    def test_default_http_runtime_loads_private_gateway_lazily(self):
        with patch.object(http, "load_runtime_contract", return_value=self._contract()) as load:
            server = http.create_server(host="127.0.0.1", port=0, api_key="")
            try:
                load.assert_called_once_with()
            finally:
                server.server_close()

    def test_default_http_runtime_rejects_private_contract_drift(self):
        contract = self._contract()
        contract["supported_services"] = ()
        with patch.object(http, "load_runtime_contract", return_value=contract):
            with self.assertRaises(PrivateCoreUnavailable):
                http.create_server(host="127.0.0.1", port=0, api_key="")


if __name__ == "__main__":
    unittest.main()
