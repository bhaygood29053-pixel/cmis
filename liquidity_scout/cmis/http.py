"""Minimal HTTP transport for the external CMIS gateway.

Default bind is loopback-only. A non-loopback bind requires ``CMIS_API_KEY``
and Bearer authentication, preventing accidental unauthenticated exposure of
provider-backed CMIS services.

Run locally with::

    python -m liquidity_scout.cmis.http

External Scout request::

    POST /v1/cmis
    Content-Type: application/json

    {"service":"market_report","chain":"x1","asset":"AGI","params":{}}
"""

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from .gateway import KNOWN_CHAINS, SUPPORTED_CHAINS
from .trade_gateway import SUPPORTED_SERVICES, TradeAwareCMISGateway


# The HTTP runtime uses the trade-aware gateway. TradeAwareCMISGateway extends
# EvidenceAwareCMISGateway, preserving the existing market/risk behavior while
# adding deterministic trade_verification.
CMISGateway = TradeAwareCMISGateway

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 1_048_576
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _api_key(value: Optional[str] = None) -> str:
    if value is not None:
        return str(value).strip()
    return os.getenv("CMIS_API_KEY", "").strip()


def _validate_bind(host: str, api_key: str) -> None:
    if str(host).strip().lower() not in _LOOPBACK_HOSTS and not api_key:
        raise RuntimeError(
            "CMIS_API_KEY is required when CMIS binds to a non-loopback host."
        )


def make_handler(gateway: CMISGateway, *, api_key: str = ""):
    """Create one request-handler class bound to a gateway instance."""
    required_key = str(api_key or "").strip()

    class CMISRequestHandler(BaseHTTPRequestHandler):
        server_version = "CMIS/1"

        def _send_json(self, status_code: int, payload: Any) -> None:
            body = _json_bytes(payload)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not required_key:
                return True
            header = str(self.headers.get("Authorization") or "")
            prefix = "Bearer "
            if not header.startswith(prefix):
                return False
            supplied = header[len(prefix):].strip()
            return bool(supplied) and hmac.compare_digest(supplied, required_key)

        def _require_authorized(self) -> bool:
            if self._authorized():
                return True
            self._send_json(
                401,
                {
                    "status": "error",
                    "error": {
                        "code": "unauthorized",
                        "message": "A valid CMIS Bearer token is required.",
                    },
                },
            )
            return False

        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path == "/healthz":
                self._send_json(
                    200,
                    {
                        "service": "cmis_gateway",
                        "status": "ok",
                        "supported_services": list(SUPPORTED_SERVICES),
                        "supported_chains": list(SUPPORTED_CHAINS),
                        "known_chains": list(KNOWN_CHAINS),
                    },
                )
                return

            if self.path == "/v1/cmis/capabilities":
                if not self._require_authorized():
                    return
                self._send_json(
                    200,
                    {
                        "service": "cmis_gateway",
                        "version": 1,
                        "request_path": "/v1/cmis",
                        "supported_services": list(SUPPORTED_SERVICES),
                        "supported_chains": list(SUPPORTED_CHAINS),
                        "known_chains": list(KNOWN_CHAINS),
                    },
                )
                return

            self._send_json(
                404,
                {
                    "status": "error",
                    "error": {"code": "not_found", "message": "Unknown CMIS path."},
                },
            )

        def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != "/v1/cmis":
                self._send_json(
                    404,
                    {
                        "status": "error",
                        "error": {"code": "not_found", "message": "Unknown CMIS path."},
                    },
                )
                return
            if not self._require_authorized():
                return

            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "0")
            except ValueError:
                length = -1

            if length <= 0:
                self._send_json(
                    400,
                    {
                        "status": "error",
                        "error": {
                            "code": "request_body_required",
                            "message": "A JSON request body is required.",
                        },
                    },
                )
                return
            if length > MAX_REQUEST_BYTES:
                self._send_json(
                    413,
                    {
                        "status": "error",
                        "error": {
                            "code": "request_too_large",
                            "message": "CMIS request body exceeds the configured limit.",
                        },
                    },
                )
                return

            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(
                    400,
                    {
                        "status": "error",
                        "error": {
                            "code": "invalid_json",
                            "message": "Request body must contain valid UTF-8 JSON.",
                        },
                    },
                )
                return

            response = gateway.dispatch(request)
            self._send_json(200, response)

        def log_message(self, format, *args):  # noqa: A003
            # Keep the default concise server log; authorization headers and
            # request bodies are never logged here.
            super().log_message(format, *args)

    return CMISRequestHandler


def create_server(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    gateway: Optional[CMISGateway] = None,
    api_key: Optional[str] = None,
) -> ThreadingHTTPServer:
    key = _api_key(api_key)
    _validate_bind(host, key)
    handler = make_handler(gateway or CMISGateway(), api_key=key)
    return ThreadingHTTPServer((host, int(port)), handler)


def serve(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    gateway: Optional[CMISGateway] = None,
    api_key: Optional[str] = None,
) -> None:
    server = create_server(
        host=host,
        port=port,
        gateway=gateway,
        api_key=api_key,
    )
    print(f"CMIS gateway listening on http://{host}:{server.server_port}/v1/cmis")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve the read-only CMIS Scout integration gateway."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("CMIS_HOST", DEFAULT_HOST),
        help="Bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CMIS_PORT", str(DEFAULT_PORT))),
        help=f"Bind port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "MAX_REQUEST_BYTES",
    "create_server",
    "make_handler",
    "serve",
]
