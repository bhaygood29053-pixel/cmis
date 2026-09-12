#!/usr/bin/env python3
"""Read-only live probe for XDEX multi-hop quote semantics."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
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
ARTIFACT_PATH = Path("artifacts/xdex_multi_hop_probe.json")


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


def _load_pool_graph():
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
        sample_keys = sorted(rows[0]) if rows else []
        raise RuntimeError(
            f"XDEX pool list produced no usable token graph; rows={len(rows)} sample_keys={sample_keys}"
        )
    return rows, graph, direct


def _shortest_path(graph, start, target, max_edges=3):
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if len(path) - 1 >= max_edges:
            continue
        for nxt in graph.get(node, ()):
            if nxt == target:
                return [*path, nxt]
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, [*path, nxt]))
    return None


def _candidate_pairs(graph, direct):
    tokens = sorted(graph, key=lambda token: (-len(graph[token]), token))
    candidates = []
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


def _is_success(body):
    if body.get("success") is True and isinstance(body.get("data"), dict):
        return True
    return any(key in body for key in ("route", "path", "hops")) and not body.get("error")


def _write(artifact):
    ARTIFACT_PATH.parent.mkdir(exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")


def main():
    artifact = {
        "schema": "xdex_multi_hop_live_probe.v1",
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pool_list_endpoint": POOL_LIST_URL,
        "endpoint": MULTI_HOP_QUOTE_URL,
        "pool_count": None,
        "token_count": None,
        "candidate_count": None,
        "selected": None,
        "attempt_count": 0,
        "attempt_summaries": [],
        "failure_stage": None,
        "fatal_error": None,
        "read_only": True,
        "prepare_called": False,
        "execution_authorized": False,
    }
    attempts = []
    try:
        artifact["failure_stage"] = "pool_graph"
        rows, graph, direct = _load_pool_graph()
        artifact["pool_count"] = len(rows)
        artifact["token_count"] = len(graph)

        artifact["failure_stage"] = "candidate_discovery"
        candidates = _candidate_pairs(graph, direct)
        artifact["candidate_count"] = len(candidates)
        if not candidates:
            raise RuntimeError("no indirect 2-3 hop candidate pair found in current XDEX pool graph")

        artifact["failure_stage"] = "multi_hop_quote"
        selected = None
        for token_in, token_out, graph_path in candidates:
            for amount in ("1", "0.1", "10"):
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
                except Exception as exc:
                    attempts.append({
                        "request": params,
                        "graph_path": graph_path,
                        "transport_error": type(exc).__name__,
                        "transport_message": str(exc)[:300],
                    })
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
        artifact["selected"] = selected
        artifact["failure_stage"] = None if selected is not None else "multi_hop_quote"
        if selected is None:
            raise RuntimeError("XDEX multi-hop quote endpoint returned no successful route for bounded candidate search")
    except Exception as exc:
        artifact["fatal_error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        artifact["attempt_count"] = len(attempts)
        artifact["attempt_summaries"] = [
            {
                "request": item.get("request"),
                "graph_path": item.get("graph_path"),
                "response_keys": item.get("response_keys"),
                "success": item.get("success", False),
                "transport_error": item.get("transport_error"),
                "transport_message": item.get("transport_message"),
            }
            for item in attempts
        ]
        _write(artifact)

    if artifact["selected"] is None:
        print(json.dumps({
            "status": "EVIDENCE_REQUIRED",
            "failure_stage": artifact["failure_stage"],
            "fatal_error": artifact["fatal_error"],
            "pool_count": artifact["pool_count"],
            "token_count": artifact["token_count"],
            "candidate_count": artifact["candidate_count"],
            "attempt_count": artifact["attempt_count"],
        }, sort_keys=True))
        raise SystemExit(2)

    selected = artifact["selected"]
    print(json.dumps({
        "status": "PASS",
        "request": selected["request"],
        "graph_hops": len(selected["graph_path"]) - 1,
        "response_keys": selected["response_keys"],
        "read_only": True,
        "execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
