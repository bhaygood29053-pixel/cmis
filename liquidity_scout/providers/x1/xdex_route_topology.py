"""Characterize XDEX route topology for exact X1 pool transactions.

Issue #374 diagnostic layer.

This module is intentionally read-only and diagnostic. It does not change the
accepted #360/#363 fail-closed swap classifier. It only attempts to prove that
recognized XDEX AMM instructions form a fully resolved route, and that the
requested target pool occurs exactly once with uniquely attributable exact
vault effects.

The `Program data:` payload layout used here is accepted only when all of the
following hold together:

- payload length and event discriminator match the observed SwapBaseInput event;
- the decoded candidate pool and both candidate mint addresses are present in
  the corresponding recognized outer XDEX instruction account list;
- recognized instruction count and selected-pool count reconcile with the
  existing transaction-pool membership proof;
- every recognized XDEX instruction has exactly one bound event;
- route-leg mint endpoints connect exactly in transaction order.

The fixed byte offsets therefore remain evidence-bound structural decoding,
not a generic statement about unrelated programs or future XDEX event versions.
"""

from __future__ import annotations

import base64
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from liquidity_scout.providers.x1.routed_multi_amm_ambiguity import (
    _collect_source_aware_occurrences,
    _default_identity_resolver,
    _exact_vault_delta,
    _normalized_occurrence,
    _selected_pool_occurrence,
)
from liquidity_scout.providers.x1.rpc import DEFAULT_X1_RPC_URL
from liquidity_scout.providers.x1.transaction_pool_membership import (
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    VerificationReport,
    account_key_info,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    fetch_transaction,
    verify_transaction,
)
from liquidity_scout.providers.x1.vault_pair_correlation import (
    _resolve_account_ref,
    _resolve_program_id,
)


VERSION = "1.0"

SWAP_BASE_INPUT_EVENT_LENGTH = 153
SWAP_BASE_INPUT_EVENT_DISCRIMINATOR = bytes.fromhex("40c6cde8260871e2")
SWAP_BASE_INPUT_POOL_SLICE = slice(8, 40)
SWAP_BASE_INPUT_INPUT_MINT_SLICE = slice(89, 121)
SWAP_BASE_INPUT_OUTPUT_MINT_SLICE = slice(121, 153)

TOPOLOGY_SINGLE_POOL = "single_pool"
TOPOLOGY_MULTI_POOL_CONNECTED = "multi_pool_connected_route"
TOPOLOGY_MULTI_POOL_CYCLIC = "multi_pool_cyclic_route"
TOPOLOGY_UNKNOWN_MULTI_AMM = "unknown_multi_amm"

ORDER_ORIGIN_UNKNOWN = "unknown"


_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _exact_vault_delta_attribution(
    *,
    transaction: Mapping[str, Any],
    identity: Mapping[str, Any],
    membership: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove target-vault deltas are not contaminated by another instruction."""

    selected = membership.get("selected_pool_instruction_evidence")
    if (
        not isinstance(selected, Sequence)
        or isinstance(selected, (str, bytes))
        or len(selected) != 1
        or not isinstance(selected[0], Mapping)
    ):
        return {
            "transaction_wide_vault_delta_attribution_verified": False,
            "warning": "unique_selected_pool_instruction_evidence_required",
            "additional_exact_vault_instruction_touches": [],
        }

    selected_row = selected[0]
    selected_scope = _text(selected_row.get("scope"))
    selected_index = selected_row.get("instruction_index")
    if (
        selected_scope != "outer"
        or isinstance(selected_index, bool)
        or not isinstance(selected_index, int)
        or selected_index < 0
    ):
        return {
            "transaction_wide_vault_delta_attribution_verified": False,
            "warning": "selected_inner_amm_vault_delta_attribution_unavailable",
            "selected_scope": selected_scope,
            "selected_instruction_index": selected_index,
            "additional_exact_vault_instruction_touches": [],
        }

    account_keys, _ = account_key_info(dict(transaction))
    exact_vaults = {
        _text(identity.get("asset_vault")),
        _text(identity.get("counter_vault")),
    }
    exact_vaults.discard(None)
    if len(exact_vaults) != 2:
        raise ValueError("exact vault identity unavailable for attribution")

    touches: list[dict[str, Any]] = []

    def inspect(
        instruction: Any,
        *,
        scope: str,
        parent_outer_index: int | None,
        instruction_index: int,
    ) -> None:
        if not isinstance(instruction, Mapping):
            return

        raw_accounts = instruction.get("accounts")
        if not isinstance(raw_accounts, Sequence) or isinstance(
            raw_accounts, (str, bytes)
        ):
            raw_accounts = []
        accounts = []
        for raw in raw_accounts:
            address = _resolve_account_ref(raw, account_keys)
            if not address:
                raise ValueError(
                    "instruction account reference unresolved during "
                    "exact-vault attribution"
                )
            accounts.append(address)

        parsed = instruction.get("parsed")
        parsed_type = (
            _text(parsed.get("type"))
            if isinstance(parsed, Mapping)
            else None
        )
        parsed_info = (
            parsed.get("info")
            if isinstance(parsed, Mapping)
            and isinstance(parsed.get("info"), Mapping)
            else {}
        )
        parsed_endpoints = [
            address
            for address in (
                _text(parsed_info.get(field))
                for field in ("source", "destination", "account")
            )
            if address
        ]

        referenced = set(accounts)
        referenced.update(parsed_endpoints)
        touched = sorted(exact_vaults.intersection(referenced))
        if not touched:
            return

        touches.append({
            "scope": scope,
            "parent_outer_instruction_index": parent_outer_index,
            "instruction_index": instruction_index,
            "program_id": _resolve_program_id(instruction, account_keys),
            "parsed_type": parsed_type,
            "exact_vaults_touched": touched,
        })

    raw_tx = transaction.get("transaction")
    raw_tx = raw_tx if isinstance(raw_tx, Mapping) else {}
    message = raw_tx.get("message")
    message = message if isinstance(message, Mapping) else {}
    outer = message.get("instructions")
    outer = (
        outer
        if isinstance(outer, Sequence)
        and not isinstance(outer, (str, bytes))
        else []
    )
    for index, instruction in enumerate(outer):
        if index == selected_index:
            continue
        inspect(
            instruction,
            scope="outer",
            parent_outer_index=index,
            instruction_index=index,
        )

    meta = transaction.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    inner_groups = meta.get("innerInstructions")
    inner_groups = (
        inner_groups
        if isinstance(inner_groups, Sequence)
        and not isinstance(inner_groups, (str, bytes))
        else []
    )
    for group in inner_groups:
        if not isinstance(group, Mapping):
            continue
        parent_index = group.get("index")
        instructions = group.get("instructions")
        instructions = (
            instructions
            if isinstance(instructions, Sequence)
            and not isinstance(instructions, (str, bytes))
            else []
        )
        if parent_index == selected_index:
            continue
        for instruction_index, instruction in enumerate(instructions):
            inspect(
                instruction,
                scope="inner",
                parent_outer_index=(
                    parent_index
                    if isinstance(parent_index, int)
                    and not isinstance(parent_index, bool)
                    else None
                ),
                instruction_index=instruction_index,
            )

    return {
        "transaction_wide_vault_delta_attribution_verified": not touches,
        "warning": (
            None
            if not touches
            else "additional_exact_vault_instruction_touch_ambiguity"
        ),
        "selected_scope": selected_scope,
        "selected_outer_instruction_index": selected_index,
        "additional_exact_vault_instruction_touches": touches,
    }


def _b58encode(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise ValueError("base58 input must be non-empty bytes")
    zero_prefix = 0
    for byte in raw:
        if byte == 0:
            zero_prefix += 1
        else:
            break

    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded

    return ("1" * zero_prefix) + encoded


def decode_swap_base_input_program_data(value: str) -> dict[str, Any]:
    """Decode the evidence-bound identity portion of one SwapBaseInput event."""

    value = _text(value)
    if not value:
        raise ValueError("SwapBaseInput program data is required")

    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("SwapBaseInput program data must be valid base64") from exc

    if len(raw) != SWAP_BASE_INPUT_EVENT_LENGTH:
        raise ValueError("unexpected SwapBaseInput program data length")
    if raw[:8] != SWAP_BASE_INPUT_EVENT_DISCRIMINATOR:
        raise ValueError("unexpected SwapBaseInput event discriminator")

    pool = _b58encode(raw[SWAP_BASE_INPUT_POOL_SLICE])
    input_mint = _b58encode(raw[SWAP_BASE_INPUT_INPUT_MINT_SLICE])
    output_mint = _b58encode(raw[SWAP_BASE_INPUT_OUTPUT_MINT_SLICE])

    if not pool or not input_mint or not output_mint:
        raise ValueError("SwapBaseInput identity fields unavailable")

    return {
        "event_discriminator_hex": raw[:8].hex(),
        "raw_length": len(raw),
        "pool_address": pool,
        "input_mint": input_mint,
        "output_mint": output_mint,
    }


def _collect_swap_base_input_program_data(
    transaction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Collect exactly one outer XDEX SwapBaseInput event per invocation.

    The log parser tracks the active invocation stack so Program-data emitted
    by nested CPI programs is not attributed to XDEX. A SwapBaseInput outer
    invocation must emit exactly one matching Program-data event before its
    success line. A second XDEX Program-data event in the same invocation is
    ambiguous and fails closed.
    """

    meta = transaction.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    logs = meta.get("logMessages")
    if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
        raise ValueError("transaction log messages unavailable")

    rows: list[dict[str, Any]] = []
    stack: list[str] = []
    active_swap: dict[str, Any] | None = None

    def parse_invoke(line: str) -> tuple[str, int] | None:
        if not line.startswith("Program ") or " invoke [" not in line:
            return None
        prefix, depth_text = line.rsplit(" invoke [", 1)
        if not depth_text.endswith("]"):
            return None
        program_id = prefix[len("Program "):].strip()
        try:
            depth = int(depth_text[:-1])
        except ValueError as exc:
            raise ValueError("program invocation depth unavailable") from exc
        if not program_id or depth < 1:
            raise ValueError("program invocation identity unavailable")
        return program_id, depth

    def parse_completion(line: str) -> tuple[str, bool] | None:
        if not line.startswith("Program "):
            return None
        if line.endswith(" success"):
            return line[len("Program "):-len(" success")].strip(), True
        marker = " failed"
        if marker in line:
            return line[len("Program "):line.index(marker)].strip(), False
        return None

    for raw_line in logs:
        line = _text(raw_line)
        if not line:
            continue

        invoked = parse_invoke(line)
        if invoked is not None:
            program_id, depth = invoked
            if depth != len(stack) + 1:
                raise ValueError("program invocation stack depth unavailable")
            stack.append(program_id)

            if program_id == XDEX_MAINNET_OBSERVED_PROGRAM_ID:
                if depth != 1:
                    raise ValueError(
                        "inner XDEX SwapBaseInput route invocation is not accepted"
                    )
                if active_swap is not None:
                    raise ValueError("overlapping XDEX invocation is ambiguous")
                active_swap = {
                    "instruction_seen": False,
                    "swap_base_input": False,
                    "program_data_count": 0,
                }
            continue

        current_program = stack[-1] if stack else None
        if (
            current_program == XDEX_MAINNET_OBSERVED_PROGRAM_ID
            and active_swap is not None
            and line.startswith("Program log: Instruction:")
        ):
            if active_swap["instruction_seen"]:
                raise ValueError("multiple XDEX instruction logs in one invocation")
            active_swap["instruction_seen"] = True
            active_swap["swap_base_input"] = (
                line == "Program log: Instruction: SwapBaseInput"
            )
            continue

        if (
            current_program == XDEX_MAINNET_OBSERVED_PROGRAM_ID
            and active_swap is not None
            and line.startswith("Program data: ")
        ):
            if not active_swap["swap_base_input"]:
                continue
            active_swap["program_data_count"] += 1
            if active_swap["program_data_count"] > 1:
                raise ValueError(
                    "multiple SwapBaseInput Program-data events in one invocation"
                )
            rows.append(
                decode_swap_base_input_program_data(
                    line[len("Program data: "):]
                )
            )
            continue

        completed = parse_completion(line)
        if completed is not None:
            program_id, succeeded = completed
            if not stack or stack[-1] != program_id:
                raise ValueError("program invocation completion stack mismatch")

            if program_id == XDEX_MAINNET_OBSERVED_PROGRAM_ID:
                if active_swap is None:
                    raise ValueError("XDEX invocation state unavailable")
                if not succeeded:
                    raise ValueError("XDEX SwapBaseInput invocation failed")
                if active_swap["swap_base_input"]:
                    if active_swap["program_data_count"] != 1:
                        raise ValueError(
                            "SwapBaseInput Program-data event unavailable"
                        )
                active_swap = None

            stack.pop()
            continue

    if active_swap is not None:
        raise ValueError("unterminated XDEX invocation")
    if stack:
        raise ValueError("unterminated program invocation stack")

    return rows

def _validate_identity(
    identity_raw: Mapping[str, Any],
    *,
    requested_pool: str,
) -> dict[str, Any]:
    identity = dict(identity_raw)
    required = (
        "pool_address",
        "asset_mint",
        "asset_vault",
        "counter_mint",
        "counter_vault",
        "shared_owner",
    )
    if identity.get("identity_verified") is not True or any(
        not _text(identity.get(name)) for name in required
    ):
        raise ValueError("exact verified pool/vault identity required")
    if identity.get("pool_address") != requested_pool:
        raise ValueError("resolved pool identity does not match requested pool")
    return identity


def _deduplicate_occurrences(
    raw_occurrences: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        _normalized_occurrence(row)
        for row in raw_occurrences
        if isinstance(row, Mapping)
    ]
    keys: set[tuple[Any, ...]] = set()
    normalized: list[dict[str, Any]] = []
    for row in rows:
        accounts = row.get("accounts")
        account_tuple = tuple(accounts) if isinstance(accounts, list) else tuple()
        key = (
            row.get("program_id"),
            row.get("scope"),
            row.get("parent_outer_instruction_index"),
            row.get("instruction_index"),
            account_tuple,
        )
        if key in keys:
            raise ValueError(
                "duplicate recognized AMM representation must remain diagnostic"
            )
        keys.add(key)
        normalized.append(row)
    return normalized


def _bind_events_to_occurrences(
    *,
    occurrences: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if len(occurrences) != len(events):
        raise ValueError("recognized XDEX instruction/event count mismatch")

    sorted_occurrences = sorted(
        (dict(row) for row in occurrences),
        key=lambda row: row.get("instruction_index", -1),
    )

    legs: list[dict[str, Any]] = []
    for route_index, (occurrence, event) in enumerate(
        zip(sorted_occurrences, events)
    ):
        if occurrence.get("scope") != "outer":
            raise ValueError("only outer XDEX route legs are accepted")
        instruction_index = occurrence.get("instruction_index")
        if (
            isinstance(instruction_index, bool)
            or not isinstance(instruction_index, int)
            or instruction_index < 0
        ):
            raise ValueError("outer XDEX instruction index unavailable")

        accounts = occurrence.get("accounts")
        if not isinstance(accounts, Sequence) or isinstance(
            accounts, (str, bytes)
        ):
            raise ValueError("recognized XDEX instruction accounts unavailable")
        account_set = {str(value) for value in accounts}

        pool = _text(event.get("pool_address"))
        input_mint = _text(event.get("input_mint"))
        output_mint = _text(event.get("output_mint"))
        if not pool or not input_mint or not output_mint:
            raise ValueError("decoded XDEX route identity unavailable")

        if pool not in account_set:
            raise ValueError("decoded XDEX pool is not bound to instruction accounts")
        if input_mint not in account_set or output_mint not in account_set:
            raise ValueError("decoded XDEX mint endpoint is not bound to instruction")

        legs.append({
            "route_index": route_index,
            "instruction_index": instruction_index,
            "program_id": occurrence.get("program_id"),
            "pool_address": pool,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "event_discriminator_hex": event.get("event_discriminator_hex"),
            "event_raw_length": event.get("raw_length"),
            "instruction_identity_bound": True,
        })

    return legs


def _route_connectivity(legs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not legs:
        return {
            "connected": False,
            "cyclic": False,
            "breaks": [],
        }

    breaks: list[dict[str, Any]] = []
    for index in range(len(legs) - 1):
        left = legs[index]
        right = legs[index + 1]
        if left.get("output_mint") != right.get("input_mint"):
            breaks.append({
                "left_route_index": index,
                "left_output_mint": left.get("output_mint"),
                "right_route_index": index + 1,
                "right_input_mint": right.get("input_mint"),
            })

    connected = not breaks
    cyclic = bool(
        connected
        and legs[0].get("input_mint")
        and legs[0].get("input_mint") == legs[-1].get("output_mint")
    )
    return {
        "connected": connected,
        "cyclic": cyclic,
        "breaks": breaks,
    }


def characterize_xdex_route_topology(
    *,
    signature: str,
    pool_address: str,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    identity_resolver: Callable[..., Mapping[str, Any]] = (
        _default_identity_resolver
    ),
    transaction_fetcher: Callable[..., Mapping[str, Any] | None] = (
        fetch_transaction
    ),
    transaction_verifier: Callable[..., VerificationReport] = (
        verify_transaction
    ),
    membership_prover: Callable[..., Mapping[str, Any]] = (
        prove_transaction_pool_membership
    ),
    occurrence_collector: Callable[
        [Mapping[str, Any]], Sequence[Mapping[str, Any]]
    ] = _collect_source_aware_occurrences,
    event_collector: Callable[
        [Mapping[str, Any]], Sequence[Mapping[str, Any]]
    ] = _collect_swap_base_input_program_data,
) -> dict[str, Any]:
    """Characterize one exact XDEX transaction without changing #363 policy."""

    signature = _text(signature)
    pool_address = _text(pool_address)
    if not signature:
        raise ValueError("signature is required")
    if not pool_address:
        raise ValueError("pool_address is required")

    identity_raw = identity_resolver(pool_address, rpc_url=rpc_url)
    if not isinstance(identity_raw, Mapping):
        raise ValueError("exact pool identity unavailable")
    identity = _validate_identity(identity_raw, requested_pool=pool_address)

    transaction = transaction_fetcher(signature, rpc_url=rpc_url)
    if not isinstance(transaction, Mapping):
        raise ValueError("transaction unavailable")

    report = transaction_verifier(
        transaction,
        signature=signature,
        rpc_url=rpc_url,
    )
    if not isinstance(report, VerificationReport):
        raise TypeError("transaction verifier must return VerificationReport")
    if report.signature != signature:
        raise ValueError("verification report signature mismatch")
    if report.found is not True or report.succeeded is not True:
        raise ValueError("transaction must be found and successful")

    membership_raw = membership_prover(
        verification_report=report,
        pool_identity=identity,
        transaction=transaction,
    )
    if not isinstance(membership_raw, Mapping):
        raise ValueError("transaction-pool membership evidence unavailable")
    membership = dict(membership_raw)
    if membership.get("transaction_pool_membership_verified") is not True:
        raise ValueError("exact transaction-to-pool membership unverified")

    raw_occurrences = occurrence_collector(transaction)
    if not isinstance(raw_occurrences, Sequence) or isinstance(
        raw_occurrences, (str, bytes)
    ):
        raise ValueError("recognized AMM instruction evidence unavailable")
    occurrences = _deduplicate_occurrences(raw_occurrences)

    selected_occurrences = [
        row for row in occurrences
        if _selected_pool_occurrence(row, identity)
    ]

    if membership.get("recognized_amm_instruction_count") != len(occurrences):
        raise ValueError("membership recognized-instruction count mismatch")
    if membership.get("selected_pool_instruction_count") != len(
        selected_occurrences
    ):
        raise ValueError("membership selected-pool instruction count mismatch")

    if any(row.get("scope") != "outer" for row in occurrences):
        raise ValueError("inner recognized XDEX route instruction is unresolved")

    raw_events = event_collector(transaction)
    if not isinstance(raw_events, Sequence) or isinstance(
        raw_events, (str, bytes)
    ):
        raise ValueError("SwapBaseInput event evidence unavailable")
    events = [dict(row) for row in raw_events if isinstance(row, Mapping)]

    legs = _bind_events_to_occurrences(
        occurrences=occurrences,
        events=events,
    )
    connectivity = _route_connectivity(legs)

    target_legs = [
        row for row in legs
        if row.get("pool_address") == pool_address
    ]
    selected_indices = {
        row.get("instruction_index")
        for row in selected_occurrences
    }
    target_indices = {
        row.get("instruction_index")
        for row in target_legs
    }

    target_leg_unique = bool(
        len(target_legs) == 1
        and len(selected_occurrences) == 1
        and target_indices == selected_indices
    )
    target_leg = target_legs[0] if len(target_legs) == 1 else None
    exact_target_mints = {
        identity["asset_mint"],
        identity["counter_mint"],
    }
    target_mints_verified = bool(
        target_leg
        and {
            target_leg.get("input_mint"),
            target_leg.get("output_mint"),
        } == exact_target_mints
    )
    target_pool_leg_verified = bool(
        target_leg_unique and target_mints_verified
    )

    attribution = _exact_vault_delta_attribution(
        transaction=transaction,
        identity=identity,
        membership=membership,
    )
    target_vault_attribution_verified = bool(
        attribution.get(
            "transaction_wide_vault_delta_attribution_verified"
        )
        is True
    )

    asset_delta = _exact_vault_delta(
        report,
        account=str(identity["asset_vault"]),
        mint=str(identity["asset_mint"]),
    )
    counter_delta = _exact_vault_delta(
        report,
        account=str(identity["counter_vault"]),
        mint=str(identity["counter_mint"]),
    )
    exact_vault_deltas_verified = bool(
        asset_delta
        and counter_delta
        and asset_delta["delta_raw"] != 0
        and counter_delta["delta_raw"] != 0
        and asset_delta["owner"] == identity["shared_owner"]
        and counter_delta["owner"] == identity["shared_owner"]
    )

    recognized_count = len(legs)
    if recognized_count == 1 and target_pool_leg_verified:
        topology = TOPOLOGY_SINGLE_POOL
        topology_verified = True
    elif recognized_count > 1 and connectivity["connected"]:
        topology = (
            TOPOLOGY_MULTI_POOL_CYCLIC
            if connectivity["cyclic"]
            else TOPOLOGY_MULTI_POOL_CONNECTED
        )
        topology_verified = True
    else:
        topology = TOPOLOGY_UNKNOWN_MULTI_AMM
        topology_verified = False

    route_pool_addresses = [row["pool_address"] for row in legs]
    route_pool_addresses_unique = len(route_pool_addresses) == len(
        set(route_pool_addresses)
    )
    routed_target_leg_evidence_complete = bool(
        recognized_count > 1
        and topology_verified
        and target_pool_leg_verified
        and target_vault_attribution_verified
        and exact_vault_deltas_verified
    )

    return {
        "service": "x1_xdex_route_topology",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if topology_verified else "partial",
        "signature": signature,
        "slot": report.slot,
        "block_time": report.block_time,
        "pool_address": pool_address,
        "identity": identity,
        "recognized_amm_instruction_count": recognized_count,
        "selected_pool_instruction_count": len(selected_occurrences),
        "route_leg_count": len(legs),
        "route_legs": legs,
        "route_pool_addresses": route_pool_addresses,
        "route_pool_addresses_unique": route_pool_addresses_unique,
        "route_connected": connectivity["connected"],
        "route_cyclic": connectivity["cyclic"],
        "route_connectivity_breaks": connectivity["breaks"],
        "execution_topology": topology,
        "route_topology_verified": topology_verified,
        "target_pool_leg_count": len(target_legs),
        "target_pool_leg": target_leg,
        "target_pool_leg_verified": target_pool_leg_verified,
        "target_vault_delta_attribution": attribution,
        "target_vault_delta_attribution_verified": (
            target_vault_attribution_verified
        ),
        "exact_vault_deltas_verified": exact_vault_deltas_verified,
        "asset_vault_delta": asset_delta,
        "counter_vault_delta": counter_delta,
        "routed_target_leg_evidence_complete": (
            routed_target_leg_evidence_complete
        ),
        "order_origin": ORDER_ORIGIN_UNKNOWN,
        "direct_order_origin_verified": False,
        "twap_execution_verified": False,
        "limit_order_execution_verified": False,
        "take_profit_execution_verified": False,
        "stop_loss_execution_verified": False,
        "classification_change_authorized": False,
        "existing_fail_closed_block_should_remain": True,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def aggregate_xdex_route_topologies(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize route diagnostics without changing #363 semantics."""

    values = [dict(row) for row in rows if isinstance(row, Mapping)]
    topology_counts = Counter(
        str(row.get("execution_topology") or "unknown")
        for row in values
    )
    all_verified = bool(
        values and all(row.get("route_topology_verified") is True for row in values)
    )
    all_target_legs = bool(
        values and all(row.get("target_pool_leg_verified") is True for row in values)
    )
    all_vault_attribution = bool(
        values
        and all(
            row.get("target_vault_delta_attribution_verified") is True
            for row in values
        )
    )
    all_evidence_complete = bool(
        values
        and all(
            row.get("routed_target_leg_evidence_complete") is True
            for row in values
        )
    )

    return {
        "service": "x1_xdex_route_topology_aggregate",
        "version": VERSION,
        "chain": "x1",
        "status": "verified" if all_verified else (
            "partial" if values else "unavailable"
        ),
        "signature_count": len(values),
        "topology_counts": dict(topology_counts),
        "all_route_topologies_verified": all_verified,
        "all_target_pool_legs_verified": all_target_legs,
        "all_target_vault_attribution_verified": all_vault_attribution,
        "all_routed_target_leg_evidence_complete": all_evidence_complete,
        "classification_change_authorized": False,
        "departure_pattern_verified": False,
        "provider_fact_time_verified": False,
        "update_source_semantics_verified": False,
        "freshness_verified": False,
        "price_usd_semantics_verified": False,
        "liquidity_semantics_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
        "rows": values,
    }


__all__ = [
    "ORDER_ORIGIN_UNKNOWN",
    "SWAP_BASE_INPUT_EVENT_DISCRIMINATOR",
    "SWAP_BASE_INPUT_EVENT_LENGTH",
    "TOPOLOGY_MULTI_POOL_CONNECTED",
    "TOPOLOGY_MULTI_POOL_CYCLIC",
    "TOPOLOGY_SINGLE_POOL",
    "TOPOLOGY_UNKNOWN_MULTI_AMM",
    "VERSION",
    "aggregate_xdex_route_topologies",
    "characterize_xdex_route_topology",
    "decode_swap_base_input_program_data",
]
