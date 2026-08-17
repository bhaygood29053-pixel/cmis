import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from liquidity_scout.cmis import http as cmis_http
from liquidity_scout.cmis.evidence import build_evidence_observation
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.providers.x1.reserve_verification import verify_x1_pool_reserve
from liquidity_scout.services.cmis_verification_evidence import (
    build_verification_evidence_response,
)


SUBJECT = "x1:pool111:mint111:vault111"


class ExplodingMarketProvider:
    chain = "x1"

    def __init__(self):
        self.refresh_calls = 0

    def refresh_if_needed(self):
        self.refresh_calls += 1
        raise AssertionError("verification_evidence must not collect market data")


def observation(source, *, slot):
    return build_evidence_observation(
        chain="x1",
        fact_type="pool_reserve",
        subject_id=SUBJECT,
        source=source,
        source_role="market_provider" if source == "X1.Ninja" else "onchain_verifier",
        observed_at=1000.0,
        block_slot=slot,
        raw_identifier="pool.pooledBase" if source == "X1.Ninja" else "vault111",
        raw_value="42",
        normalized_value="42",
        unit="TOKEN_UNITS",
        calculation_version="http-runtime-test-1",
        identity_verified=True,
        semantics_verified=True,
        freshness_verified=True,
        warnings=[],
    )


def evidence_envelope():
    verified = verify_x1_pool_reserve(
        observation("X1.Ninja", slot=100),
        observation("X1 RPC", slot=101),
    )
    return build_verification_evidence_response(
        verified,
        chain="x1",
        asset={"symbol": "REF", "mint": "mint111"},
        observed_at=1001.0,
    )


class RunningServer:
    def __init__(self, gateway):
        self.server = cmis_http.create_server(
            host="127.0.0.1",
            port=0,
            gateway=gateway,
            api_key="",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

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


def post_json(url, payload):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class CMISHTTPVerificationRuntimeTests(unittest.TestCase):
    def test_runtime_uses_internal_configured_ledger_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "nested", "verification.db")
            with patch.dict(
                os.environ,
                {"CMIS_VERIFICATION_EVIDENCE_DB": db_path},
            ):
                gateway = RuntimeCMISGateway(
                    x1_market_provider=ExplodingMarketProvider(),
                )

            self.assertEqual(gateway.verification_evidence_ledger.db_path, db_path)
            self.assertTrue(os.path.exists(db_path))

    def test_exact_evidence_lookup_round_trips_over_http_without_market_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            market = ExplodingMarketProvider()
            gateway = RuntimeCMISGateway(
                x1_market_provider=market,
                verification_evidence_db_path=os.path.join(tmp, "evidence.db"),
            )
            stored = gateway.verification_evidence_ledger.store(
                evidence_envelope(),
                recorded_at=1002.0,
            )

            with RunningServer(gateway) as running:
                status, body = post_json(
                    running.url,
                    {
                        "service": "verification_evidence",
                        "chain": "x1",
                        "params": {"evidence_id": stored["evidence_id"]},
                    },
                )

        self.assertEqual(status, 200)
        self.assertEqual(body["service"], "verification_evidence")
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["data"]["fact"]["subject_id"], SUBJECT)
        self.assertEqual(body["data"]["fact"]["normalized_value"], "42")
        self.assertEqual(
            body["data"]["retrieval"]["evidence_id"],
            stored["evidence_id"],
        )
        self.assertEqual(market.refresh_calls, 0)

    def test_http_request_cannot_select_ledger_path_or_smuggle_asset_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            market = ExplodingMarketProvider()
            gateway = RuntimeCMISGateway(
                x1_market_provider=market,
                verification_evidence_db_path=os.path.join(tmp, "evidence.db"),
            )

            with RunningServer(gateway) as running:
                _, db_path_attempt = post_json(
                    running.url,
                    {
                        "service": "verification_evidence",
                        "chain": "x1",
                        "params": {
                            "evidence_id": "ve_missing",
                            "db_path": "/tmp/attacker.db",
                        },
                    },
                )
                _, asset_attempt = post_json(
                    running.url,
                    {
                        "service": "verification_evidence",
                        "chain": "x1",
                        "asset": "AGI",
                        "params": {"evidence_id": "ve_missing"},
                    },
                )
                _, missing = post_json(
                    running.url,
                    {
                        "service": "verification_evidence",
                        "chain": "x1",
                        "params": {"evidence_id": "ve_missing"},
                    },
                )

        self.assertEqual(db_path_attempt["status"], "error")
        self.assertEqual(
            db_path_attempt["errors"][0]["code"],
            "verification_evidence_params_not_allowed",
        )
        self.assertEqual(asset_attempt["status"], "error")
        self.assertEqual(
            asset_attempt["errors"][0]["code"],
            "verification_evidence_request_fields_not_allowed",
        )
        self.assertEqual(missing["status"], "unavailable")
        self.assertEqual(market.refresh_calls, 0)


if __name__ == "__main__":
    unittest.main()
