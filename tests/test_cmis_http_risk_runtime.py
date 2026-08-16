import unittest

from liquidity_scout.cmis import http
from liquidity_scout.cmis.risk_evidence_gateway import EvidenceAwareCMISGateway


class CMISHTTPRiskRuntimeTests(unittest.TestCase):
    def test_default_http_runtime_uses_evidence_aware_gateway(self):
        self.assertIs(http.CMISGateway, EvidenceAwareCMISGateway)


if __name__ == "__main__":
    unittest.main()
