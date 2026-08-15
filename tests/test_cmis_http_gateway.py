import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from liquidity_scout.cmis import http as cmis_http


class StubGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        return {
            "service": request.get("service") or "cmis_gateway",
            "chain": request.get("chain") or "unknown",
            "status": "ok",
            "asset": {},
            "data": {"echo_asset": request.get("asset")},
            "risk": None,
            "confidence": {},
            "sources": [],
            "observed_at": None,
            "warnings": [],
            "errors": [],
        }


class RunningServer:
    def __init__(self, *, api_key=""):
        self.gateway = StubGateway()
        self.server = cmis_http.create_server(
            host="127.0.0.1",
            port=0,
            gateway=self.gateway,
            api_key=api_key,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def post_json(url, payload, *, api_key=None):
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class CMISHTTPGatewayTests(unittest.TestCase):
    def test_localhost_post_round_trip_reaches_gateway(self):
        with RunningServer() as running:
            status, response = post_json(
                running.base_url + "/v1/cmis",
                {
                    "service": "market_report",
                    "chain": "x1",
                    "asset": "AGI",
                    "params": {},
                },
            )

        self.assertEqual(status, 200)
        self.assertEqual(response["service"], "market_report")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["data"]["echo_asset"], "AGI")
        self.assertEqual(running.gateway.requests[0]["asset"], "AGI")

    def test_capabilities_expose_service_contract(self):
        with RunningServer() as running:
            with urlopen(
                running.base_url + "/v1/cmis/capabilities",
                timeout=2,
            ) as raw:
                response = json.loads(raw.read().decode("utf-8"))

        self.assertEqual(response["version"], 1)
        self.assertEqual(response["request_path"], "/v1/cmis")
        self.assertEqual(len(response["supported_services"]), 7)
        self.assertEqual(response["supported_chains"], ["x1"])
        self.assertIn("solana", response["known_chains"])

    def test_bearer_auth_is_enforced_when_configured(self):
        with RunningServer(api_key="test-secret") as running:
            with self.assertRaises(HTTPError) as unauthorized:
                post_json(
                    running.base_url + "/v1/cmis",
                    {"service": "rank", "chain": "x1", "params": {}},
                )
            self.assertEqual(unauthorized.exception.code, 401)

            status, response = post_json(
                running.base_url + "/v1/cmis",
                {"service": "rank", "chain": "x1", "params": {}},
                api_key="test-secret",
            )

        self.assertEqual(status, 200)
        self.assertEqual(response["service"], "rank")
        self.assertEqual(len(running.gateway.requests), 1)

    def test_invalid_json_returns_http_400_without_dispatch(self):
        with RunningServer() as running:
            request = Request(
                running.base_url + "/v1/cmis",
                data=b"{not-json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as invalid:
                urlopen(request, timeout=2)
            body = json.loads(invalid.exception.read().decode("utf-8"))

        self.assertEqual(invalid.exception.code, 400)
        self.assertEqual(body["error"]["code"], "invalid_json")
        self.assertEqual(running.gateway.requests, [])

    def test_non_loopback_bind_requires_api_key(self):
        with self.assertRaises(RuntimeError):
            cmis_http._validate_bind("0.0.0.0", "")

        cmis_http._validate_bind("0.0.0.0", "configured")
        cmis_http._validate_bind("127.0.0.1", "")


if __name__ == "__main__":
    unittest.main()
