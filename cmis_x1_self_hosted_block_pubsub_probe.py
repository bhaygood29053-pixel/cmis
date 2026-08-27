#!/usr/bin/env python3
"""Collect sanitized X1 blockSubscribe reconnect/backfill evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import websocket

from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL, X1RPCError, rpc_request
from liquidity_scout.providers.x1.self_hosted_readonly_node import (
    FINALIZED,
    classify_block_pubsub_session,
    evaluate_block_pubsub_reconnect,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe finalized blockSubscribe reconnect/gap semantics on a self-hosted X1 node."
    )
    parser.add_argument("--ws-url", required=True)
    parser.add_argument(
        "--canonical-rpc-url",
        default=DEFAULT_X1_RPC_URL,
    )
    parser.add_argument("--notifications-per-session", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    parser.add_argument("--maximum-backfill-span", type=int, default=64)
    parser.add_argument("--output", required=True)
    return parser


def _collect_session(
    ws_url: str,
    *,
    request_id: int,
    notifications: int,
    timeout: float,
):
    if notifications < 1:
        raise ValueError("notifications-per-session must be at least 1")

    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "blockSubscribe",
        "params": [
            "all",
            {
                "commitment": FINALIZED,
                "encoding": "json",
                "transactionDetails": "none",
                "showRewards": False,
            },
        ],
    }

    messages = []
    notification_count = 0
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        ws.send(json.dumps(request, separators=(",", ":")))
        while notification_count < notifications:
            raw = ws.recv()
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                messages.append(parsed)
                if parsed.get("method") == "blockNotification":
                    notification_count += 1
    finally:
        ws.close()

    return messages


def _canonical_backfill(
    discontinuities,
    *,
    canonical_rpc_url: str,
    maximum_backfill_span: int,
):
    presence = {}
    for left, right in discontinuities:
        gap_size = right - left - 1
        if gap_size <= 0:
            continue
        if gap_size > maximum_backfill_span:
            for slot in range(left + 1, right):
                presence[slot] = None
            continue
        try:
            blocks = rpc_request(
                "getBlocks",
                [left + 1, right - 1, {"commitment": FINALIZED}],
                rpc_url=canonical_rpc_url,
            )
        except X1RPCError:
            for slot in range(left + 1, right):
                presence[slot] = None
            continue

        if not isinstance(blocks, list) or any(
            isinstance(slot, bool) or not isinstance(slot, int) or slot < 0
            for slot in blocks
        ):
            for slot in range(left + 1, right):
                presence[slot] = None
            continue

        produced = set(blocks)
        for slot in range(left + 1, right):
            presence[slot] = slot in produced

    return presence


def main() -> int:
    args = _parser().parse_args()
    if args.maximum_backfill_span < 1:
        raise SystemExit("--maximum-backfill-span must be at least 1")

    first_messages = _collect_session(
        args.ws_url,
        request_id=101,
        notifications=args.notifications_per_session,
        timeout=args.timeout,
    )
    first = classify_block_pubsub_session(
        first_messages,
        request_id=101,
        commitment=FINALIZED,
    )

    time.sleep(max(0.0, args.reconnect_delay))

    second_messages = _collect_session(
        args.ws_url,
        request_id=102,
        notifications=args.notifications_per_session,
        timeout=args.timeout,
    )
    second = classify_block_pubsub_session(
        second_messages,
        request_id=102,
        commitment=FINALIZED,
    )

    all_slots = list(first.slots) + list(second.slots)
    discontinuities = []
    for left, right in zip(all_slots, all_slots[1:]):
        if right > left + 1:
            discontinuities.append((left, right))

    backfill = _canonical_backfill(
        discontinuities,
        canonical_rpc_url=args.canonical_rpc_url,
        maximum_backfill_span=args.maximum_backfill_span,
    )
    evaluation = evaluate_block_pubsub_reconnect(
        first,
        second,
        canonical_block_presence=backfill,
    )

    evidence = {
        "service": "x1_self_hosted_block_pubsub_probe",
        "chain": "x1",
        "status": (
            "ok"
            if evaluation.status == "AGREEMENT"
            and evaluation.dropped_event_detection_verified
            else "partial"
        ),
        "source_role": "operator_controlled_x1_block_pubsub_redundancy",
        "endpoint_url_redacted": True,
        "commitment": FINALIZED,
        "first_session": asdict(first),
        "second_session": asdict(second),
        "reconnect": asdict(evaluation),
        "scope": {
            "streaming_verified": (
                evaluation.status == "AGREEMENT"
                and evaluation.dropped_event_detection_verified
            ),
            "retention_verified": False,
            "archival_completeness_verified": False,
            "market_source_independence_verified": False,
            "cmis_provider_promoted": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        },
        "warnings": [
            "Block PubSub redundancy is infrastructure evidence, not independent market-price evidence.",
            "Canonical getBlocks backfill is bounded to observed reconnect discontinuities and proves no archive completeness.",
            "Endpoint URLs and raw block payloads are intentionally omitted.",
        ],
    }

    Path(args.output).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
