import unittest

from liquidity_scout.cmis import http
from liquidity_scout.cmis.risk_evidence_gateway import EvidenceAwareCMISGateway
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway


class CMISHTTPRiskRuntimeTests(unittest.TestCase):
    def test_default_http_runtime_uses_trade_aware_evidence_gateway(self):
        self.assertIs(http.CMISGateway, TradeAwareCMISGateway)
        self.assertTrue(issubclass(http.CMISGateway, EvidenceAwareCMISGateway))


if __name__ == "__main__":
    unittest.main()
