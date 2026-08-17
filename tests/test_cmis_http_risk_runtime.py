import unittest

from liquidity_scout.cmis import http
from liquidity_scout.cmis.risk_evidence_gateway import EvidenceAwareCMISGateway
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.cmis.verification_gateway import CMISGateway as VerificationCMISGateway


class CMISHTTPRiskRuntimeTests(unittest.TestCase):
    def test_default_http_runtime_uses_composed_gateway(self):
        self.assertIs(http.CMISGateway, RuntimeCMISGateway)
        self.assertTrue(issubclass(http.CMISGateway, TradeAwareCMISGateway))
        self.assertTrue(issubclass(http.CMISGateway, EvidenceAwareCMISGateway))
        self.assertTrue(issubclass(http.CMISGateway, VerificationCMISGateway))


if __name__ == "__main__":
    unittest.main()
