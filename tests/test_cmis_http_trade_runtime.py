import json
import threading
import unittest
from decimal import Decimal
from urllib.request import Request, urlopen

from liquidity_scout.cmis import http as cmis_http
from liquidity_scout.cmis.trade_gateway import TradeAwareCMISGateway
from liquidity_scout.providers.x1.transaction_semantics import (
    PoolLegMatch,
    VerificationReport,
)


def verified_report(*args, **kwargs):
    return VerificationReport(
        signature="sig",
        rpc_url="rpc",
        found=True,
        succeeded=True,
        slot=1,
        block_time=1786632211,
        block_time_iso="2026-08-13T14:43:31+00:00",
        fee_lamports=0,
        primary_signer="signer",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=["sEsY"],
        token_deltas=[],
        signer_token_deltas=[],
        signer_native_xnt_delta=Decimal("0"),
        signer_native_xnt_delta_before_fee=Decimal("0"),
        inferred_side="BUY",
        inferred_asset_mint="asset",
        inferred_quote_mint="quote",
        inferred_quote_amount=Decimal("1"),
        pool_leg_match=PoolLegMatch(
            side="BUY",
            owner="pool",
            asset_mint="asset",
            asset_account="asset_account",
            asset_amount=Decimal("1"),
            quote_mint="quote",
            quote_account="quote_account",
            quote_amount=Decimal("1"),
            amount_match=True,
            evidence="exact",
        ),
        verification_basis="EXACT_POOL_LEG_AMOUNTS",
        inference_reason="exact",
        expected_side="BUY",
        expected_mint=None,
        expectation_match=True,
        verification_level="PROVIDER_SIDE_ONCHAIN_CONFIRMED",
    )


class RunningTradeServer:
    def __init__(self):
        gateway = object.__new__(TradeAwareCMISGateway)
        gateway.x1_trade_rpc_url = "rpc"
        gateway.x1_trade_verifier = verified_report
        self.server = cmis_http.create_server(
            host="127.0.0.1",
            port=0,
            gateway=gateway,
            api_key="",
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}/v1/cmis"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class CMISHTTPTradeRuntimeTests(unittest.TestCase):
    def test_trade_verification_round_trip_over_http(self):
        payload = {
            "service": "trade_verification",
            "chain": "x1",
            "params": {
                "event": {
                    "type": "buy",
                    "txHash": "sig",
                    "poolAddress": "pool",
                    "slot": 1,
                    "timestamp": "2026-08-13T14:43:31.000Z",
                    "amountToken": "1",
                    "amountNative": "1",
                }
            },
        }

        with RunningTradeServer() as running:
            request = Request(
                running.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                body = json.loads(response.read().decode("utf-8"))
                status_code = response.status

        self.assertEqual(status_code, 200)
        self.assertEqual(body["service"], "trade_verification")
        self.assertEqual(body["chain"], "x1")
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["data"]["side"], "BUY")
        self.assertTrue(body["data"]["side_verified"])
        self.assertTrue(body["data"]["identity"]["identity_verified"])
        self.assertEqual(
            body["data"]["verification_basis"],
            "EXACT_POOL_LEG_AMOUNTS",
        )
        self.assertEqual(
            body["data"]["verification_level"],
            "PROVIDER_SIDE_ONCHAIN_CONFIRMED",
        )


if __name__ == "__main__":
    unittest.main()
