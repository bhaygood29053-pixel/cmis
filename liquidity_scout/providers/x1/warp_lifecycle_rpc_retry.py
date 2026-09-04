"""Bounded RPC transport for #441 finalized getTransaction evidence.

The Solana public RPC serves the required historical transaction bodies but
large 50-member JSON-RPC batches have returned intermittent unresolved members.
For the canonical Solana endpoint this helper uses small paced micro-batches,
then retries only unresolved members individually with bounded backoff.

This changes retrieval mechanics only. Every required transaction body remains
mandatory; any member still unresolved after bounded retries fails the original
lifecycle collector.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, Callable

import requests

MAX_ITEM_ATTEMPTS = 5
RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0)
SOLANA_PUBLIC_RPC_URL = "https://api.mainnet-beta.solana.com"
SOLANA_MICRO_BATCH_SIZE = 5
SOLANA_MICRO_BATCH_PACING_SECONDS = 0.6


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


def _rows_by_id(body: Any) -> dict[Any, Any]:
    if not isinstance(body, list):
        return {}
    result: dict[Any, Any] = {}
    for row in body:
        if isinstance(row, Mapping):
            result[row.get("id")] = row
    return result


def _paced_solana_micro_batches(
    url: str,
    requests_batch: list[Any],
    *,
    headers: Mapping[str, str] | None,
    timeout: int | float | None,
    post: Callable[..., Any],
    sleep: Callable[[float], None],
) -> _CombinedResponse:
    combined: list[Any] = []

    for offset in range(0, len(requests_batch), SOLANA_MICRO_BATCH_SIZE):
        if offset:
            sleep(SOLANA_MICRO_BATCH_PACING_SECONDS)

        chunk = requests_batch[offset : offset + SOLANA_MICRO_BATCH_SIZE]
        valid_requests = [row for row in chunk if isinstance(row, Mapping)]
        by_id: dict[Any, Any] = {}

        if valid_requests:
            try:
                response = post(
                    url,
                    json=[dict(row) for row in valid_requests],
                    headers=dict(headers or {}),
                    timeout=timeout,
                )
                response.raise_for_status()
                by_id = _rows_by_id(response.json())
            except Exception:
                # The individual retry path below remains the only fallback.
                by_id = {}

        for request in chunk:
            if not isinstance(request, Mapping):
                combined.append(None)
                continue
            row = by_id.get(request.get("id"))
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

    The canonical Solana public endpoint receives five-member paced
    micro-batches. Only unresolved members are retried individually. Other
    endpoints retain the caller's batch and use the same bounded member retry.
    """

    if not isinstance(json, list):
        return post(url, json=json, headers=headers, timeout=timeout)

    if str(url).rstrip("/") == SOLANA_PUBLIC_RPC_URL:
        return _paced_solana_micro_batches(
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

    by_id = _rows_by_id(body)
    combined: list[Any] = []
    for request in json:
        if not isinstance(request, Mapping):
            combined.append(None)
            continue
        row = by_id.get(request.get("id"))
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
    "SOLANA_MICRO_BATCH_PACING_SECONDS",
    "SOLANA_MICRO_BATCH_SIZE",
    "SOLANA_PUBLIC_RPC_URL",
    "resilient_get_transaction_post",
]
