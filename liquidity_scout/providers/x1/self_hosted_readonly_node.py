"""Deterministic contract for an operator-controlled X1 read-only node.

The self-hosted node is infrastructure redundancy beneath the X1 Provider. It
may verify the same X1 chain facts through a separately operated RPC endpoint,
but it is not an independent market-price source merely because the endpoint or
process is separate.

This module keeps network collection small and explicit while making all
comparison/promotion semantics deterministic and fail closed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import shlex
from typing import Any, Callable, Mapping, Sequence

from liquidity_scout.providers.x1.rpc import X1RPCError, rpc_request


CHAIN = "x1"
SELF_HOSTED_SOURCE = "self-hosted X1 read-only node"
CANONICAL_SOURCE = "official X1 RPC"
FINALIZED = "finalized"

REQUIRED_READ_ONLY_FLAGS = (
    "--full-rpc-api",
    "--enable-rpc-transaction-history",
    "--enable-extended-tx-metadata-storage",
    "--rpc-pubsub-enable-block-subscription",
)


@dataclass(frozen=True)
class StartupConfigurationEvidence:
    provenance: str | None
    observed_flags: tuple[str, ...]
    missing_required_flags: tuple[str, ...]
    startup_configuration_verified: bool
    running_process_configuration_verified: bool = False


@dataclass(frozen=True)
class RpcIdentityEvidence:
    candidate_genesis_hash: str | None
    canonical_genesis_hash: str | None
    network_identity_verified: bool
    candidate_version: Mapping[str, Any] | None
    version_shape_verified: bool
    endpoint_url_redacted: bool = True


@dataclass(frozen=True)
class HistoricalRpcComparison:
    status: str
    signature: str | None
    slot: int | None
    compared_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    same_fact_identity_verified: bool
    commitment: str
    infrastructure_agreement_verified: bool
    market_source_independence_verified: bool = False
    archival_completeness_verified: bool = False
    retention_verified: bool = False


@dataclass(frozen=True)
class BlockPubsubSession:
    acknowledgement_verified: bool
    subscription_id: int | None
    slots: tuple[int, ...]
    duplicate_slots: tuple[int, ...]
    out_of_order: bool
    malformed_message_count: int
    commitment: str
    stream_contract_verified: bool


@dataclass(frozen=True)
class BlockPubsubReconnectEvaluation:
    status: str
    first_session_verified: bool
    second_session_verified: bool
    reconnect_acknowledged: bool
    slot_discontinuities: tuple[tuple[int, int], ...]
    canonical_backfill_complete: bool
    missing_block_notifications: tuple[int, ...]
    duplicate_slots: tuple[int, ...]
    out_of_order: bool
    dropped_event_detection_verified: bool
    market_source_independence_verified: bool = False
    cmis_promotable: bool = False


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_version(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    return dict(value)


def evaluate_startup_configuration(
    command_or_flags: str | Sequence[str] | None,
    *,
    provenance: str | None,
) -> StartupConfigurationEvidence:
    """Verify only the supplied startup-configuration artifact.

    This does not prove that the currently running remote process was launched
    with the supplied flags. That separate fact remains false.
    """
    provenance_text = _text(provenance) or None
    if command_or_flags is None:
        tokens: tuple[str, ...] = ()
    elif isinstance(command_or_flags, str):
        try:
            tokens = tuple(shlex.split(command_or_flags))
        except ValueError:
            tokens = ()
    elif isinstance(command_or_flags, Sequence):
        tokens = tuple(_text(value) for value in command_or_flags if _text(value))
    else:
        raise TypeError("command_or_flags must be text, a sequence, or None")

    observed = tuple(sorted({token for token in tokens if token.startswith("--")}))
    missing = tuple(flag for flag in REQUIRED_READ_ONLY_FLAGS if flag not in tokens)
    verified = bool(provenance_text and tokens and not missing)
    return StartupConfigurationEvidence(
        provenance=provenance_text,
        observed_flags=observed,
        missing_required_flags=missing,
        startup_configuration_verified=verified,
    )


def evaluate_rpc_identity(
    *,
    candidate_genesis_hash: Any,
    canonical_genesis_hash: Any,
    candidate_version: Any,
) -> RpcIdentityEvidence:
    candidate = _text(candidate_genesis_hash) or None
    canonical = _text(canonical_genesis_hash) or None
    version = _safe_version(candidate_version)
    return RpcIdentityEvidence(
        candidate_genesis_hash=candidate,
        canonical_genesis_hash=canonical,
        network_identity_verified=bool(candidate and canonical and candidate == canonical),
        candidate_version=version,
        version_shape_verified=version is not None,
    )


def _normalize_signature_page(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    rows: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            return None
        signature = _text(raw.get("signature"))
        slot = _nonnegative_int(raw.get("slot"))
        if not signature or slot is None or "err" not in raw:
            return None
        block_time = raw.get("blockTime")
        if block_time is not None and (
            isinstance(block_time, bool)
            or not isinstance(block_time, (int, float))
            or block_time < 0
        ):
            return None
        confirmation = _text(raw.get("confirmationStatus")) or None
        rows.append(
            {
                "signature": signature,
                "slot": slot,
                "err": raw.get("err"),
                "block_time": block_time,
                "confirmation_status": confirmation,
            }
        )
    return rows


def _normalize_transaction(value: Any, *, signature: str) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    slot = _nonnegative_int(value.get("slot"))
    block_time = value.get("blockTime")
    if slot is None:
        return None
    if block_time is not None and (
        isinstance(block_time, bool)
        or not isinstance(block_time, (int, float))
        or block_time < 0
    ):
        return None

    transaction = value.get("transaction")
    meta = value.get("meta")
    if not isinstance(transaction, Mapping) or not isinstance(meta, Mapping):
        return None
    signatures = transaction.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return None
    if _text(signatures[0]) != signature:
        return None

    return {
        "slot": slot,
        "block_time": block_time,
        "err": meta.get("err"),
        "signature": signature,
    }


def compare_historical_rpc_sample(
    *,
    candidate_history: Any,
    candidate_transaction: Any,
    candidate_block_time: Any,
    canonical_transaction: Any,
    canonical_block_time: Any,
    commitment: str = FINALIZED,
) -> HistoricalRpcComparison:
    """Compare one self-hosted historical sample to canonical X1 RPC.

    Agreement here is infrastructure agreement about the same chain fact. It
    intentionally does not establish independent market-source evidence.
    """
    commitment = _text(commitment).lower()
    if commitment != FINALIZED:
        return HistoricalRpcComparison(
            status="INSUFFICIENT_EVIDENCE",
            signature=None,
            slot=None,
            compared_fields=(),
            conflicts=("commitment",),
            same_fact_identity_verified=False,
            commitment=commitment or "",
            infrastructure_agreement_verified=False,
        )

    rows = _normalize_signature_page(candidate_history)
    if rows is None:
        return HistoricalRpcComparison(
            status="INSUFFICIENT_EVIDENCE",
            signature=None,
            slot=None,
            compared_fields=(),
            conflicts=("candidate_history_shape",),
            same_fact_identity_verified=False,
            commitment=commitment,
            infrastructure_agreement_verified=False,
        )

    candidate_row = next(
        (
            row
            for row in rows
            if row["err"] is None
            and row["confirmation_status"] == FINALIZED
        ),
        None,
    )
    if candidate_row is None:
        return HistoricalRpcComparison(
            status="INSUFFICIENT_EVIDENCE",
            signature=None,
            slot=None,
            compared_fields=(),
            conflicts=("finalized_success_sample",),
            same_fact_identity_verified=False,
            commitment=commitment,
            infrastructure_agreement_verified=False,
        )

    signature = candidate_row["signature"]
    candidate_tx = _normalize_transaction(candidate_transaction, signature=signature)
    canonical_tx = _normalize_transaction(canonical_transaction, signature=signature)
    candidate_time = candidate_block_time
    canonical_time = canonical_block_time

    if candidate_tx is None or canonical_tx is None:
        return HistoricalRpcComparison(
            status="INSUFFICIENT_EVIDENCE",
            signature=signature,
            slot=candidate_row["slot"],
            compared_fields=(),
            conflicts=("transaction_shape",),
            same_fact_identity_verified=False,
            commitment=commitment,
            infrastructure_agreement_verified=False,
        )
    if (
        isinstance(candidate_time, bool)
        or not isinstance(candidate_time, (int, float))
        or candidate_time < 0
        or isinstance(canonical_time, bool)
        or not isinstance(canonical_time, (int, float))
        or canonical_time < 0
    ):
        return HistoricalRpcComparison(
            status="INSUFFICIENT_EVIDENCE",
            signature=signature,
            slot=candidate_row["slot"],
            compared_fields=(),
            conflicts=("block_time_shape",),
            same_fact_identity_verified=False,
            commitment=commitment,
            infrastructure_agreement_verified=False,
        )

    fields = ("slot", "block_time", "err", "signature")
    conflicts: list[str] = []
    if candidate_row["slot"] != candidate_tx["slot"]:
        conflicts.append("candidate_history_transaction_slot")
    if candidate_tx["slot"] != canonical_tx["slot"]:
        conflicts.append("slot")
    if candidate_tx["block_time"] != canonical_tx["block_time"]:
        conflicts.append("transaction_block_time")
    if candidate_time != canonical_time:
        conflicts.append("block_time")
    if candidate_tx["block_time"] is not None and candidate_time != candidate_tx["block_time"]:
        conflicts.append("candidate_transaction_getBlockTime")
    if canonical_tx["block_time"] is not None and canonical_time != canonical_tx["block_time"]:
        conflicts.append("canonical_transaction_getBlockTime")
    if candidate_tx["err"] != canonical_tx["err"]:
        conflicts.append("err")
    if candidate_tx["signature"] != canonical_tx["signature"]:
        conflicts.append("signature")

    same_fact = not any(
        name in conflicts
        for name in (
            "candidate_history_transaction_slot",
            "slot",
            "signature",
        )
    )
    status = "AGREEMENT" if same_fact and not conflicts else "CONFLICT"
    return HistoricalRpcComparison(
        status=status,
        signature=signature,
        slot=candidate_tx["slot"],
        compared_fields=fields,
        conflicts=tuple(conflicts),
        same_fact_identity_verified=same_fact,
        commitment=commitment,
        infrastructure_agreement_verified=status == "AGREEMENT",
    )


def classify_block_pubsub_session(
    messages: Sequence[Mapping[str, Any]],
    *,
    request_id: int,
    commitment: str = FINALIZED,
) -> BlockPubsubSession:
    """Classify one sanitized blockSubscribe session transcript."""
    commitment = _text(commitment).lower()
    subscription_id: int | None = None
    ack = False
    slots: list[int] = []
    malformed = 0

    for message in messages:
        if not isinstance(message, Mapping):
            malformed += 1
            continue

        if message.get("jsonrpc") != "2.0":
            malformed += 1
            continue

        if message.get("id") == request_id:
            result = _nonnegative_int(message.get("result"))
            if result is None:
                malformed += 1
            else:
                subscription_id = result
                ack = True
            continue

        if message.get("method") != "blockNotification":
            continue
        params = message.get("params")
        if not isinstance(params, Mapping):
            malformed += 1
            continue
        if subscription_id is None or params.get("subscription") != subscription_id:
            malformed += 1
            continue
        result = params.get("result")
        if not isinstance(result, Mapping):
            malformed += 1
            continue
        context = result.get("context")
        if not isinstance(context, Mapping):
            malformed += 1
            continue
        slot = _nonnegative_int(context.get("slot"))
        if slot is None:
            malformed += 1
            continue
        slots.append(slot)

    duplicates = tuple(sorted({slot for slot in slots if slots.count(slot) > 1}))
    out_of_order = any(current < previous for previous, current in zip(slots, slots[1:]))
    verified = bool(
        commitment == FINALIZED
        and ack
        and subscription_id is not None
        and slots
        and malformed == 0
        and not out_of_order
    )
    return BlockPubsubSession(
        acknowledgement_verified=ack,
        subscription_id=subscription_id,
        slots=tuple(slots),
        duplicate_slots=duplicates,
        out_of_order=out_of_order,
        malformed_message_count=malformed,
        commitment=commitment,
        stream_contract_verified=verified,
    )


def evaluate_block_pubsub_reconnect(
    first: BlockPubsubSession,
    second: BlockPubsubSession,
    *,
    canonical_block_presence: Mapping[int, bool | None],
) -> BlockPubsubReconnectEvaluation:
    """Evaluate reconnect/gap evidence without treating skipped slots as drops.

    A discontinuity is a candidate gap only. It becomes a missing notification
    only if canonical RPC independently says an intermediate slot has a block.
    Unknown canonical presence keeps dropped-event detection unverified.
    """
    if not isinstance(first, BlockPubsubSession) or not isinstance(second, BlockPubsubSession):
        raise TypeError("first and second must be BlockPubsubSession values")
    if not isinstance(canonical_block_presence, Mapping):
        raise TypeError("canonical_block_presence must be a mapping")

    slots = list(first.slots) + list(second.slots)
    discontinuities: list[tuple[int, int]] = []
    for left, right in zip(slots, slots[1:]):
        if right > left + 1:
            discontinuities.append((left, right))

    notified = set(slots)
    missing_notifications: list[int] = []
    backfill_complete = True
    for left, right in discontinuities:
        for slot in range(left + 1, right):
            presence = canonical_block_presence.get(slot)
            if presence is None:
                backfill_complete = False
            elif presence is True and slot not in notified:
                missing_notifications.append(slot)

    duplicates = tuple(
        sorted(set(first.duplicate_slots) | set(second.duplicate_slots) | {
            slot for slot in set(first.slots) & set(second.slots)
        })
    )
    out_of_order = first.out_of_order or second.out_of_order
    sessions_verified = first.stream_contract_verified and second.stream_contract_verified
    reconnect_ack = first.acknowledgement_verified and second.acknowledgement_verified
    dropped_verified = bool(
        sessions_verified
        and reconnect_ack
        and backfill_complete
        and not out_of_order
    )

    if not sessions_verified or not reconnect_ack:
        status = "INSUFFICIENT_EVIDENCE"
    elif missing_notifications:
        status = "CONFLICT"
    elif not backfill_complete:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "AGREEMENT"

    return BlockPubsubReconnectEvaluation(
        status=status,
        first_session_verified=first.stream_contract_verified,
        second_session_verified=second.stream_contract_verified,
        reconnect_acknowledged=reconnect_ack,
        slot_discontinuities=tuple(discontinuities),
        canonical_backfill_complete=backfill_complete,
        missing_block_notifications=tuple(sorted(set(missing_notifications))),
        duplicate_slots=duplicates,
        out_of_order=out_of_order,
        dropped_event_detection_verified=dropped_verified,
    )


def _rpc_call(
    method: str,
    params: list[Any],
    *,
    url: str,
    rpc_call: Callable[..., Any],
) -> Any:
    return rpc_call(method, params, rpc_url=url)


def collect_self_hosted_rpc_evidence(
    *,
    rpc_url: str,
    canonical_rpc_url: str,
    probe_address: str,
    history_limit: int = 25,
    rpc_call: Callable[..., Any] = rpc_request,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Collect a sanitized bounded RPC comparison.

    URLs are intentionally omitted from returned evidence.
    """
    rpc_url = _text(rpc_url)
    canonical_rpc_url = _text(canonical_rpc_url)
    probe_address = _text(probe_address)
    if not rpc_url:
        raise ValueError("self-hosted X1 RPC URL is required")
    if not canonical_rpc_url:
        raise ValueError("canonical X1 RPC URL is required")
    if not probe_address:
        raise ValueError("probe address is required")
    if isinstance(history_limit, bool) or not isinstance(history_limit, int) or not 1 <= history_limit <= 100:
        raise ValueError("history_limit must be an integer from 1 to 100")

    observed_at = observed_at or datetime.now(timezone.utc)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    observed_iso = observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    candidate_genesis = _rpc_call("getGenesisHash", [], url=rpc_url, rpc_call=rpc_call)
    canonical_genesis = _rpc_call("getGenesisHash", [], url=canonical_rpc_url, rpc_call=rpc_call)
    candidate_version = _rpc_call("getVersion", [], url=rpc_url, rpc_call=rpc_call)
    identity = evaluate_rpc_identity(
        candidate_genesis_hash=candidate_genesis,
        canonical_genesis_hash=canonical_genesis,
        candidate_version=candidate_version,
    )

    health = _rpc_call("getHealth", [], url=rpc_url, rpc_call=rpc_call)
    slot = _rpc_call(
        "getSlot",
        [{"commitment": FINALIZED}],
        url=rpc_url,
        rpc_call=rpc_call,
    )
    history = _rpc_call(
        "getSignaturesForAddress",
        [
            probe_address,
            {"commitment": FINALIZED, "limit": history_limit},
        ],
        url=rpc_url,
        rpc_call=rpc_call,
    )
    rows = _normalize_signature_page(history)
    selected = next(
        (
            row
            for row in (rows or [])
            if row["err"] is None and row["confirmation_status"] == FINALIZED
        ),
        None,
    )

    comparison: HistoricalRpcComparison
    if selected is None:
        comparison = compare_historical_rpc_sample(
            candidate_history=history,
            candidate_transaction=None,
            candidate_block_time=None,
            canonical_transaction=None,
            canonical_block_time=None,
        )
    else:
        signature = selected["signature"]
        selected_slot = selected["slot"]
        tx_params = [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": FINALIZED,
                "maxSupportedTransactionVersion": 0,
            },
        ]
        candidate_tx = _rpc_call("getTransaction", tx_params, url=rpc_url, rpc_call=rpc_call)
        canonical_tx = _rpc_call(
            "getTransaction", tx_params, url=canonical_rpc_url, rpc_call=rpc_call
        )
        candidate_time = _rpc_call(
            "getBlockTime", [selected_slot], url=rpc_url, rpc_call=rpc_call
        )
        canonical_time = _rpc_call(
            "getBlockTime", [selected_slot], url=canonical_rpc_url, rpc_call=rpc_call
        )
        comparison = compare_historical_rpc_sample(
            candidate_history=history,
            candidate_transaction=candidate_tx,
            candidate_block_time=candidate_time,
            canonical_transaction=canonical_tx,
            canonical_block_time=canonical_time,
        )

    slot_ok = _nonnegative_int(slot) is not None
    health_ok = health == "ok"
    rpc_contract_verified = bool(
        identity.network_identity_verified
        and identity.version_shape_verified
        and health_ok
        and slot_ok
        and comparison.infrastructure_agreement_verified
    )

    return {
        "service": "x1_self_hosted_readonly_node_probe",
        "chain": CHAIN,
        "status": "ok" if rpc_contract_verified else "partial",
        "observed_at": observed_iso,
        "source_role": "operator_controlled_x1_rpc_redundancy",
        "endpoint_url_redacted": True,
        "identity": asdict(identity),
        "rpc": {
            "health_result": health if isinstance(health, str) else None,
            "health_verified": health_ok,
            "finalized_slot": slot if slot_ok else None,
            "slot_verified": slot_ok,
            "history_limit": history_limit,
            "history_row_count": len(rows) if rows is not None else None,
            "history_sample": asdict(comparison),
            "rpc_contract_verified": rpc_contract_verified,
        },
        "scope": {
            "history_sample_verified": comparison.infrastructure_agreement_verified,
            "archival_completeness_verified": False,
            "continuous_coverage_verified": False,
            "retention_verified": False,
            "streaming_verified": False,
            "market_source_independence_verified": False,
            "cmis_provider_promoted": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        },
        "warnings": [
            "Self-hosted node agreement is infrastructure redundancy, not independent market-price evidence.",
            "A bounded successful history sample does not prove archive completeness or continuous retention.",
            "Streaming remains unverified until a separate blockSubscribe live transcript/reconnect/backfill probe passes.",
        ],
    }


__all__ = [
    "BlockPubsubReconnectEvaluation",
    "BlockPubsubSession",
    "CANONICAL_SOURCE",
    "FINALIZED",
    "HistoricalRpcComparison",
    "REQUIRED_READ_ONLY_FLAGS",
    "RpcIdentityEvidence",
    "SELF_HOSTED_SOURCE",
    "StartupConfigurationEvidence",
    "classify_block_pubsub_session",
    "collect_self_hosted_rpc_evidence",
    "compare_historical_rpc_sample",
    "evaluate_block_pubsub_reconnect",
    "evaluate_rpc_identity",
    "evaluate_startup_configuration",
]
