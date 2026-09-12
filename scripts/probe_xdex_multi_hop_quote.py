#!/usr/bin/env python3
"""Read-only live probe for XDEX multi-hop quote semantics.

Candidate paths are discovered from X1 mainnet XDEX program state rather than
the public XDEX pool catalog, which is known to be legitimately empty while
quote endpoints remain available. The probe calls only the public quote route;
it never calls prepare, signs, broadcasts, or moves value.
"""
from __future__ import annotations

import base64
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import requests

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.rpc import rpc_request

MULTI_HOP_QUOTE_URL = "https://api.xdex.xyz/api/xdex/swap/multi-hop/quote"
TRADE_NETWORK = "X1 Mainnet"
VENUE = "all"
MAX_HOPS = 6
TIMEOUT = 20
ARTIFACT_PATH = Path("artifacts/xdex_multi_hop_probe.json")
XDEX_PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL_SIZE = 637
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200
CONFIG_OFFSET = 8


def _get_json(url: str, *, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{url} returned non-object JSON")
    return body


def _pubkey(data: bytes, offset: int) -> str:
    return encode_base58_pubkey(data[offset : offset + 32])


def _decode_program_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict) or not str(row.get("pubkey") or "").strip():
        return None
    account = row.get("account")
    if not isinstance(account, dict):
        return None
    raw = account.get("data")
    encoded = raw[0] if isinstance(raw, list) and raw else None
    if not isinstance(encoded, str):
        return None
    try:
        data = base64.b64decode(encoded)
    except Exception:
        return None
    if len(data) != POOL_SIZE:
        return None
    mint_0 = _pubkey(data, MINT_0_OFFSET)
    mint_1 = _pubkey(data, MINT_1_OFFSET)
    if not mint_0 or not mint_1 or mint_0 == mint_1:
        return None
    return {
        "pool": str(row["pubkey"]),
        "amm_config": _pubkey(data, CONFIG_OFFSET),
        "mint_0": mint_0,
        "mint_1": mint_1,
    }


def _load_onchain_pool_graph():
    slot_before = rpc_request("getSlot", [{"commitment": "confirmed"}])
    result = rpc_request(
        "getProgramAccounts",
        [
            XDEX_PROGRAM,
            {
                "encoding": "base64",
                "commitment": "confirmed",
                "filters": [{"dataSize": POOL_SIZE}],
            },
        ],
        timeout=TIMEOUT,
    )
    slot_after = rpc_request("getSlot", [{"commitment": "confirmed"}])
    rows = result.get("value") if isinstance(result, dict) and "value" in result else result
    if not isinstance(rows, list):
        raise RuntimeError("X1 RPC XDEX pool inventory did not return a list")

    pools: list[dict[str, Any]] = []
    graph: dict[str, set[str]] = defaultdict(set)
    direct: set[frozenset[str]] = set()
    pools_by_edge: dict[frozenset[str], list[str]] = defaultdict(list)
    for row in rows:
        decoded = _decode_program_row(row)
        if not decoded:
            continue
        pools.append(decoded)
        left = decoded["mint_0"]
        right = decoded["mint_1"]
        edge = frozenset((left, right))
        graph[left].add(right)
        graph[right].add(left)
        direct.add(edge)
        pools_by_edge[edge].append(decoded["pool"])

    if not graph:
        raise RuntimeError(f"X1 RPC produced no usable {POOL_SIZE}-byte XDEX pool graph")
    return pools, graph, direct, pools_by_edge, slot_before, slot_after


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


def _path_pool_candidates(path, pools_by_edge):
    return [
        sorted(pools_by_edge.get(frozenset((left, right)), []))
        for left, right in zip(path, path[1:])
    ]


def _candidate_pairs(graph, direct):
    tokens = sorted(graph, key=lambda token: (-len(graph[token]), token))
    candidates = []
    for i, left in enumerate(tokens[:140]):
        for right in tokens[i + 1 : 180]:
            if frozenset((left, right)) in direct:
                continue
            path = _shortest_path(graph, left, right, max_edges=3)
            if path is None or len(path) < 3:
                continue
            degree_score = len(graph[left]) + len(graph[right])
            candidates.append((len(path), -degree_score, left, right, path))
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
        "discovery_source": "X1 RPC getProgramAccounts XDEX 637-byte pool state",
        "xdex_program": XDEX_PROGRAM,
        "endpoint": MULTI_HOP_QUOTE_URL,
        "pool_count": None,
        "token_count": None,
        "candidate_count": None,
        "rpc_slot_before": None,
        "rpc_slot_after": None,
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
        artifact["failure_stage"] = "x1_rpc_pool_graph"
        pools, graph, direct, pools_by_edge, slot_before, slot_after = _load_onchain_pool_graph()
        artifact["pool_count"] = len(pools)
        artifact["token_count"] = len(graph)
        artifact["rpc_slot_before"] = slot_before
        artifact["rpc_slot_after"] = slot_after

        artifact["failure_stage"] = "candidate_discovery"
        candidates = _candidate_pairs(graph, direct)
        artifact["candidate_count"] = len(candidates)
        if not candidates:
            raise RuntimeError("no indirect 2-3 hop candidate pair found in on-chain XDEX pool graph")

        artifact["failure_stage"] = "multi_hop_quote"
        selected = None
        for token_in, token_out, graph_path in candidates:
            graph_pool_candidates = _path_pool_candidates(graph_path, pools_by_edge)
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
                        "graph_pool_candidates": graph_pool_candidates,
                        "transport_error": type(exc).__name__,
                        "transport_message": str(exc)[:300],
                    })
                    continue
                attempt = {
                    "request": params,
                    "graph_path": graph_path,
                    "graph_pool_candidates": graph_pool_candidates,
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
            raise RuntimeError("XDEX multi-hop quote endpoint returned no successful route for bounded on-chain candidate search")
    except Exception as exc:
        artifact["fatal_error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        artifact["attempt_count"] = len(attempts)
        artifact["attempt_summaries"] = [
            {
                "request": item.get("request"),
                "graph_path": item.get("graph_path"),
                "graph_pool_candidates": item.get("graph_pool_candidates"),
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
            "rpc_slot_before": artifact["rpc_slot_before"],
            "rpc_slot_after": artifact["rpc_slot_after"],
        }, sort_keys=True))
        raise SystemExit(2)

    selected = artifact["selected"]
    print(json.dumps({
        "status": "PASS",
        "request": selected["request"],
        "graph_hops": len(selected["graph_path"]) - 1,
        "response_keys": selected["response_keys"],
        "rpc_slot_before": artifact["rpc_slot_before"],
        "rpc_slot_after": artifact["rpc_slot_after"],
        "read_only": True,
        "execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
