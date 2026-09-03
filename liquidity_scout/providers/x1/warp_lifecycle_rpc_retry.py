"""Bounded RPC transport for #441 finalized getTransaction evidence.

The Solana public RPC reliably serves the required historical transaction
bodies individually but can return unresolved members when large JSON-RPC
batches exceed its public rate behavior. For that exact endpoint this helper
serializes finalized getTransaction reads with conservative pacing and bounded
retries. Other RPCs retain batch transport with bounded retry of unresolved
members.

This changes retrieval mechanics only. Any transaction still unresolved after
bounded retries remains an evidence failure in the lifecycle collector.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, Callable

import requests

MAX_ITEM_ATTEMPTS = 4
RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
SOLANA_PUBLIC_RPC_URL = "https://api.mainnet-beta.solana.com"
SOLANA_ITEM_PACING_SECONDS = 0.35


class _CombinedResponse:
    def __init__(self, *, rows: list[Any], status_code: int = 200):
        self._rows = rows
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> list[Any]:
        return self._rows


def _needs_retry(row: Any) -> bool:
    return (
        not isinstance(row, Mapping)
        or row.get("error") is not None
        or "result" not in row
        or row.get("result") is None
    )


def _single_request_with_retry(
    url: str,
    request: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None,
    timeout: int | float | None,
    post: Callable[..., Any],
    sleep: Callable[[float], None],
) -> Any:
    last_row: Any = None
    for attempt in range(MAX_ITEM_ATTEMPTS):
        try:
            response = post(
                url,
                json=dict(request),
                headers=dict(headers or {}),
                timeout=timeout,
            )
            response.raise_for_status()
            row = response.json()
            last_row = row
            if not _needs_retry(row):
                return row
        except Exception as exc:
            last_row = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": "transport_retry_exhausted",
                    "message": type(exc).__name__,
                },
            }
        if attempt < MAX_ITEM_ATTEMPTS - 1:
            sleep(RETRY_DELAYS_SECONDS[attempt])
    return last_row


def _paced_solana_batch(
    url: str,
    requests_batch: list[Any],
    *,
    headers: Mapping[str, str] | None,
    timeout: int | float | None,
    post: Callable[..., Any],
    sleep: Callable[[float], None],
) -> _CombinedResponse:
    rows: list[Any] = []
    for index, request in enumerate(requests_batch):
        if not isinstance(request, Mapping):
            rows.append(None)
            continue
        if index:
            sleep(SOLANA_ITEM_PACING_SECONDS)
        rows.append(
            _single_request_with_retry(
                url,
                request,
                headers=headers,
                timeout=timeout,
                post=post,
                sleep=sleep,
            )
        )
    return _CombinedResponse(rows=rows)


def resilient_get_transaction_post(
    url: str,
    *,
    json: Any,
    headers: Mapping[str, str] | None = None,
    timeout: int | float | None = None,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Return exact getTransaction rows with bounded transport resilience.

    For the canonical Solana public endpoint, batch members are requested one at
    a time with conservative pacing because direct diagnostics proved the exact
    historical bodies are available individually while large batch members can
    fail transiently. For other endpoints, the original batch is preserved and
    only unresolved rows are retried individually.
    """

    if not isinstance(json, list):
        return post(url, json=json, headers=headers, timeout=timeout)

    if str(url).rstrip("/") == SOLANA_PUBLIC_RPC_URL:
        return _paced_solana_batch(
            url,
            json,
            headers=headers,
            timeout=timeout,
            post=post,
            sleep=sleep,
        )

    response = post(url, json=json, headers=headers, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, list):
        return response

    by_id: dict[Any, Any] = {}
    for row in body:
        if isinstance(row, Mapping):
            by_id[row.get("id")] = row

    combined: list[Any] = []
    for request in json:
        if not isinstance(request, Mapping):
            combined.append(None)
            continue
        request_id = request.get("id")
        row = by_id.get(request_id)
        if _needs_retry(row):
            row = _single_request_with_retry(
                url,
                request,
                headers=headers,
                timeout=timeout,
                post=post,
                sleep=sleep,
            )
        combined.append(row)

    return _CombinedResponse(rows=combined)


__all__ = [
    "MAX_ITEM_ATTEMPTS",
    "RETRY_DELAYS_SECONDS",
    "SOLANA_ITEM_PACING_SECONDS",
    "SOLANA_PUBLIC_RPC_URL",
    "resilient_get_transaction_post",
]
