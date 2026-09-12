#!/usr/bin/env python3
"""Read-only live probe for XDEX multi-hop quote semantics.

The probe discovers candidate pairs from XDEX's public pool list, selects pairs
that have no direct pool but do have a short graph path, and calls the public
multi-hop quote endpoint. It writes the exact observed request/response to a
JSON artifact for contract pinning. It never calls prepare, signs, broadcasts,
or moves value.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import requests

POOL_LIST_URL = "https://api.xdex.xyz/api/xendex/pool/list"
MULTI_HOP_QUOTE_URL = "https://api.xdex.xyz/api/xdex/swap/multi-hop/quote"
POOL_NETWORK = "mainnet"
TRADE_NETWORK = "X1 Mainnet"
VENUE = "all"
MAX_HOPS = 6
TIMEOUT = 20


def _token_address(token: Any) -> str | None:
    if not isinstance(token, dict):
        return None
    for key in ("address", "mint"):
        value = token.get(key)
        if isinstance(value, str) and value.strip() == value and value:
            return value
    return None


def _get_json(url: str, *, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{url} returned non-object JSON")
    return body


def _load_pool_graph() -> tuple[list[dict[str, Any]], dict[str, set[str]], set[frozenset[str]]]:
    body = _get_json(POOL_LIST_URL, params={"network": POOL_NETWORK})
    if body.get("success") is not True or not isinstance(body.get("data"), list):
        raise RuntimeError(f"XDEX pool list contract changed: {json.dumps(body)[:1000]}")
    rows = [row for row in body["data"] if isinstance(row, dict)]
    graph: dict[str, set[str]] = defaultdict(set)
    direct: set[frozenset[str]] = set()
    for row in rows:
        left = _token_address(row.get("baseToken"))
        right = _token_address(row.get("quoteToken"))
        if not left or not right or left == right:
            continue
        graph[left].add(right)
        graph[right].add(left)
        direct.add(frozenset((left, right)))
    if not graph:
        raise RuntimeError("XDEX pool list produced no usable token graph")
    return rows, graph, direct


def _shortest_path(graph: dict[str, set[str]], start: str, target: str, max_edges: int = 3) -> list[str] | None:
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        edges = len(path) - 1
        if edges >= max_edges:
            continue
        for nxt in graph.get(node, ()):
            if nxt == target:
                return [*path, nxt]
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, [*path, nxt]))
    return None


def _candidate_pairs(graph: dict[str, set[str]], direct: set[frozenset[str]]) -> list[tuple[str, str, list[str]]]:
    tokens = sorted(graph, key=lambda token: (-len(graph[token]), token))
    candidates: list[tuple[int, int, str, str, list[str]]] = []
    for i, left in enumerate(tokens[:120]):
        for right in tokens[i + 1 : 160]:
            if frozenset((left, right)) in direct:
                continue
            path = _shortest_path(graph, left, right, max_edges=3)
            if path is None or len(path) < 3:
                continue
            score = len(graph[left]) + len(graph[right])
            candidates.append((len(path), -score, left, right, path))
    candidates.sort()
    return [(left, right, path) for _, _, left, right, path in candidates[:80]]


def _is_success(body: dict[str, Any]) -> bool:
    if body.get("success") is True and isinstance(body.get("data"), dict):
        return True
    # Preserve a second possible explicit object contract without promoting it:
    # if XDEX returns a direct route object, the artifact captures it for review.
    return any(key in body for key in ("route", "path", "hops")) and not body.get("error")


def main() -> None:
    rows, graph, direct = _load_pool_graph()
    candidates = _candidate_pairs(graph, direct)
    if not candidates:
        raise RuntimeError("no indirect 2-3 hop candidate pair found in current XDEX pool graph")

    attempts: list[dict[str, Any]] = []
    amounts = ("1", "0.1", "10")
    selected: dict[str, Any] | None = None
    for token_in, token_out, graph_path in candidates:
        for amount in amounts:
            params = {
                "token_in": token_in,
                "token_out": token_out,
                "token_in_amount": amount,
                "venue": VENUE,
                "max_hops": str(MAX_HOPS),
                "network": TRADE_NETWORK,
            }
            try:
                body = _get_json(MULTI_HOP_QUOTE_URL, params=params)
            except Exception as exc:  # bounded discovery; keep trying other pairs
                attempts.append({"request": params, "graph_path": graph_path, "transport_error": type(exc).__name__})
                continue
            attempt = {
                "request": params,
                "graph_path": graph_path,
                "response_keys": sorted(body),
                "success": _is_success(body),
                "response": body,
            }
            attempts.append(attempt)
            if attempt["success"]:
                selected = attempt
                break
        if selected is not None:
            break

    artifact = {
        "schema": "xdex_multi_hop_live_probe.v1",
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pool_count": len(rows),
        "token_count": len(graph),
        "endpoint": MULTI_HOP_QUOTE_URL,
        "selected": selected,
        "attempt_count": len(attempts),
        "attempt_summaries": [
            {
                "request": item.get("request"),
                "graph_path": item.get("graph_path"),
                "response_keys": item.get("response_keys"),
                "success": item.get("success", False),
                "transport_error": item.get("transport_error"),
            }
            for item in attempts
        ],
        "read_only": True,
        "prepare_called": False,
        "execution_authorized": False,
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/xdex_multi_hop_probe.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8"
    )
    if selected is None:
        raise RuntimeError("XDEX multi-hop quote endpoint returned no successful route for bounded candidate search")

    print(json.dumps({
        "status": "PASS",
        "endpoint": MULTI_HOP_QUOTE_URL,
        "request": selected["request"],
        "graph_hops": len(selected["graph_path"]) - 1,
        "response_keys": selected["response_keys"],
        "read_only": True,
        "execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
