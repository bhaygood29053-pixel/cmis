"""CMIS v1.4.10.1 — deterministic X1 AMM operation classification.

This module classifies recognized canonical-pool AMM transactions only from
on-chain transaction structure and exact integer token flows.

REMOVE_LIQUIDITY requires both canonical reserves OUT, an LP-token burn, and
exact transfers from both canonical vaults in the same outer AMM instruction.
ADD_LIQUIDITY requires both canonical reserves IN, LP-token minting, and exact
transfers into both canonical vaults in the same outer AMM instruction.
Anything else remains UNKNOWN and fails closed.

No symbol ordering, balance size, provider side label, ranking, or LLM inference
is used. This module is read-only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.vault_pair_correlation import (
    collect_recognized_amm_instruction_occurrences,
)

VERSION = "1.4.10.1"

SWAP_BUY = "SWAP_BUY"
SWAP_SELL = "SWAP_SELL"
ADD_LIQUIDITY = "ADD_LIQUIDITY"
REMOVE_LIQUIDITY = "REMOVE_LIQUIDITY"
UNKNOWN = "UNKNOWN"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _raw_amount(info: Mapping[str, Any]) -> int | None:
    token_amount = info.get("tokenAmount")
    value = token_amount.get("amount") if isinstance(token_amount, Mapping) else info.get("amount")
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _parsed_instruction(raw: Any) -> tuple[str | None, dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return None, {}
    parsed = raw.get("parsed")
    if not isinstance(parsed, Mapping):
        return None, {}
    kind = _text(parsed.get("type"))
    info = parsed.get("info")
    return kind, dict(info) if isinstance(info, Mapping) else {}


def _inner_instructions_for_outer_index(
    tx: Mapping[str, Any],
    outer_instruction_index: int,
) -> list[Mapping[str, Any]]:
    meta = tx.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    out: list[Mapping[str, Any]] = []
    for group in _sequence(meta.get("innerInstructions")):
        if not isinstance(group, Mapping):
            continue
        index = group.get("index")
        if isinstance(index, int) and not isinstance(index, bool) and index == outer_instruction_index:
            for raw in _sequence(group.get("instructions")):
                if isinstance(raw, Mapping):
                    out.append(raw)
    return out


def _canonical_outer_occurrence(
    tx: Mapping[str, Any],
    *,
    pool_address: str,
    asset_account: str,
    counter_account: str,
    expected_program_id: str,
    occurrence_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any] | None, list[str]]:
    matches = []
    for raw in list(occurrence_provider(tx) or []):
        if not isinstance(raw, Mapping):
            continue
        if _text(raw.get("program_id")) != expected_program_id:
            continue
        accounts = [_text(item) for item in _sequence(raw.get("accounts"))]
        accounts = [item for item in accounts if item]
        if not all(value in accounts for value in (pool_address, asset_account, counter_account)):
            continue
        if raw.get("scope") not in (None, "outer"):
            continue
        instruction_index = raw.get("instruction_index")
        if isinstance(instruction_index, bool) or not isinstance(instruction_index, int) or instruction_index < 0:
            continue
        matches.append(
            {
                "program_id": expected_program_id,
                "scope": "outer",
                "instruction_index": instruction_index,
                "accounts": accounts,
                "pool_position": accounts.index(pool_address),
                "asset_position": accounts.index(asset_account),
                "counter_position": accounts.index(counter_account),
            }
        )

    if len(matches) == 1:
        return matches[0], []
    if not matches:
        return None, ["canonical_outer_amm_instruction_not_isolated"]
    return None, ["canonical_outer_amm_instruction_ambiguous"]


def _transfer_evidence(instructions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for raw in instructions:
        kind, info = _parsed_instruction(raw)
        if kind not in {"transfer", "transferChecked"}:
            continue
        amount = _raw_amount(info)
        source = _text(info.get("source"))
        destination = _text(info.get("destination"))
        if not source or not destination or amount is None:
            continue
        out.append(
            {
                "type": kind,
                "source": source,
                "destination": destination,
                "authority": _text(info.get("authority") or info.get("owner")),
                "mint": _text(info.get("mint")),
                "amount_raw": amount,
            }
        )
    return out


def _burn_evidence(instructions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for raw in instructions:
        kind, info = _parsed_instruction(raw)
        if kind not in {"burn", "burnChecked"}:
            continue
        amount = _raw_amount(info)
        account = _text(info.get("account"))
        mint = _text(info.get("mint"))
        if not account or not mint or amount is None or amount <= 0:
            continue
        out.append(
            {
                "type": kind,
                "account": account,
                "mint": mint,
                "authority": _text(info.get("authority") or info.get("owner")),
                "amount_raw": amount,
            }
        )
    return out


def _mint_evidence(instructions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for raw in instructions:
        kind, info = _parsed_instruction(raw)
        if kind not in {"mintTo", "mintToChecked"}:
            continue
        amount = _raw_amount(info)
        destination = _text(info.get("account") or info.get("destination"))
        mint = _text(info.get("mint"))
        if not destination or not mint or amount is None or amount <= 0:
            continue
        out.append(
            {
                "type": kind,
                "destination": destination,
                "mint": mint,
                "authority": _text(info.get("mintAuthority") or info.get("authority") or info.get("owner")),
                "amount_raw": amount,
            }
        )
    return out


def _exact_transfer(
    transfers: Sequence[Mapping[str, Any]],
    *,
    source: str | None = None,
    destination: str | None = None,
    mint: str,
    amount_raw: int,
    authority: str | None = None,
) -> dict[str, Any] | None:
    matches = []
    for raw in transfers:
        if source is not None and _text(raw.get("source")) != source:
            continue
        if destination is not None and _text(raw.get("destination")) != destination:
            continue
        # A plain SPL transfer does not carry mint identity. Fail closed unless
        # the parsed instruction independently exposes the expected mint.
        if _text(raw.get("mint")) != mint:
            continue
        if raw.get("amount_raw") != amount_raw:
            continue
        if authority is not None and _text(raw.get("authority")) != authority:
            continue
        matches.append(dict(raw))
    return matches[0] if len(matches) == 1 else None


def classify_liquidity_operation(
    tx: Mapping[str, Any],
    *,
    pool_address: str,
    asset_mint: str,
    counter_mint: str,
    asset_account: str,
    counter_account: str,
    shared_owner: str,
    expected_program_id: str,
    asset_delta_raw: int,
    counter_delta_raw: int,
    occurrence_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] = (
        collect_recognized_amm_instruction_occurrences
    ),
) -> dict[str, Any]:
    """Classify ADD/REMOVE liquidity or return UNKNOWN, fail-closed."""

    reasons: list[str] = []
    occurrence, occurrence_reasons = _canonical_outer_occurrence(
        tx,
        pool_address=pool_address,
        asset_account=asset_account,
        counter_account=counter_account,
        expected_program_id=expected_program_id,
        occurrence_provider=occurrence_provider,
    )
    reasons.extend(occurrence_reasons)
    if occurrence is None:
        return {
            "operation_class": UNKNOWN,
            "operation_classified": False,
            "proven_non_swap": False,
            "evidence": None,
            "rejection_reasons": reasons,
        }

    inner = _inner_instructions_for_outer_index(tx, occurrence["instruction_index"])
    if not inner:
        reasons.append("amm_inner_instruction_context_missing")

    transfers = _transfer_evidence(inner)
    burns = _burn_evidence(inner)
    mints = _mint_evidence(inner)
    amm_accounts = set(occurrence["accounts"])
    reserve_mints = {asset_mint, counter_mint}

    if asset_delta_raw < 0 and counter_delta_raw < 0:
        lp_burns = [
            raw for raw in burns
            if raw["account"] in amm_accounts and raw["mint"] not in reserve_mints
        ]
        if len(lp_burns) != 1:
            reasons.append("unique_lp_token_burn_not_proven")

        asset_transfer = _exact_transfer(
            transfers,
            source=asset_account,
            mint=asset_mint,
            amount_raw=abs(asset_delta_raw),
            authority=shared_owner,
        )
        counter_transfer = _exact_transfer(
            transfers,
            source=counter_account,
            mint=counter_mint,
            amount_raw=abs(counter_delta_raw),
            authority=shared_owner,
        )
        if asset_transfer is None:
            reasons.append("exact_asset_reserve_out_transfer_not_proven")
        if counter_transfer is None:
            reasons.append("exact_counter_reserve_out_transfer_not_proven")

        if not reasons:
            return {
                "operation_class": REMOVE_LIQUIDITY,
                "operation_classified": True,
                "proven_non_swap": True,
                "evidence": {
                    "structural_fingerprint": {
                        "program_id": occurrence["program_id"],
                        "pool_position": occurrence["pool_position"],
                        "asset_position": occurrence["asset_position"],
                        "counter_position": occurrence["counter_position"],
                    },
                    "lp_token_burn": lp_burns[0],
                    "asset_reserve_transfer": asset_transfer,
                    "counter_reserve_transfer": counter_transfer,
                    "reserve_flow": {"asset_reserve": "OUT", "counter_reserve": "OUT"},
                },
                "rejection_reasons": [],
            }

    elif asset_delta_raw > 0 and counter_delta_raw > 0:
        lp_mints = [
            raw for raw in mints
            if raw["destination"] in amm_accounts and raw["mint"] not in reserve_mints
        ]
        if len(lp_mints) != 1:
            reasons.append("unique_lp_token_mint_not_proven")

        asset_transfer = _exact_transfer(
            transfers,
            destination=asset_account,
            mint=asset_mint,
            amount_raw=asset_delta_raw,
        )
        counter_transfer = _exact_transfer(
            transfers,
            destination=counter_account,
            mint=counter_mint,
            amount_raw=counter_delta_raw,
        )
        if asset_transfer is None:
            reasons.append("exact_asset_reserve_in_transfer_not_proven")
        if counter_transfer is None:
            reasons.append("exact_counter_reserve_in_transfer_not_proven")

        if not reasons:
            return {
                "operation_class": ADD_LIQUIDITY,
                "operation_classified": True,
                "proven_non_swap": True,
                "evidence": {
                    "structural_fingerprint": {
                        "program_id": occurrence["program_id"],
                        "pool_position": occurrence["pool_position"],
                        "asset_position": occurrence["asset_position"],
                        "counter_position": occurrence["counter_position"],
                    },
                    "lp_token_mint": lp_mints[0],
                    "asset_reserve_transfer": asset_transfer,
                    "counter_reserve_transfer": counter_transfer,
                    "reserve_flow": {"asset_reserve": "IN", "counter_reserve": "IN"},
                },
                "rejection_reasons": [],
            }
    else:
        reasons.append("canonical_reserve_signs_not_liquidity_operation_shape")

    return {
        "operation_class": UNKNOWN,
        "operation_classified": False,
        "proven_non_swap": False,
        "evidence": {
            "structural_fingerprint": {
                "program_id": occurrence["program_id"],
                "pool_position": occurrence["pool_position"],
                "asset_position": occurrence["asset_position"],
                "counter_position": occurrence["counter_position"],
            }
        },
        "rejection_reasons": list(dict.fromkeys(reasons)),
    }


__all__ = [
    "ADD_LIQUIDITY",
    "REMOVE_LIQUIDITY",
    "SWAP_BUY",
    "SWAP_SELL",
    "UNKNOWN",
    "VERSION",
    "classify_liquidity_operation",
]
