"""Deterministic X1 on-chain trade semantics for CMIS.

This module promotes no provider label on trust alone. It verifies a transaction
through X1 RPC, identifies known XDEX/XenDEX programs, computes exact token
balance deltas from raw integer amounts, and can match one X1.Ninja BUY/SELL row
to an exact pool/vault leg inside a multi-leg transaction.

No LLM logic belongs here. This module is read-only and never signs or submits
transactions.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .rpc import DEFAULT_X1_RPC_URL, X1RPCError, rpc_request

# X1 protocol constants.
DEFAULT_X1_RPC = DEFAULT_X1_RPC_URL

# IMPORTANT: keep XDEX and XenDEX distinct.
#
# XDEX_MAINNET_OBSERVED_PROGRAM_ID was observed in a real X1 mainnet swap
# returned by X1.Ninja and independently fetched from X1 RPC:
#   signature F4HMz4Y6...k5bnxsP, slot 71338200, 2026-08-13T14:43:31Z.
# Treat this as an empirically observed XDEX program identity, not as an
# X1-Labs-owned registry assertion.
XDEX_MAINNET_OBSERVED_PROGRAM_ID = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"

# X1 Labs Explorer currently labels these as XenDEX programs on MainnetBeta.
XENDEX_AMM_PROGRAM_ID = "7EEuq61z9VKdkUzj7G36xGd7ncyz8KBtUwAWVjypYQHf"
XENDEX_STAKING_PROGRAM_ID = "E279H61mv8i4kc6P66HD8cSe4fApsEeZsf9rE1qxRPQc"

WXNT_MINT = "So11111111111111111111111111111111111111112"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
LAMPORTS_PER_XNT = Decimal("1000000000")

PROGRAM_LABELS = {
    XDEX_MAINNET_OBSERVED_PROGRAM_ID: "XDEX AMM (mainnet-observed)",
    XENDEX_AMM_PROGRAM_ID: "XenDEX AMM (X1 Explorer-registered)",
    XENDEX_STAKING_PROGRAM_ID: "XenDEX staking (X1 Explorer-registered)",
}

# Known quote-like assets that can make BUY/SELL inference stronger.
DEFAULT_QUOTE_MINTS = (WXNT_MINT, USDC_X_MINT)


@dataclass(frozen=True)
class TokenDelta:
    account_index: int
    account: str
    owner: str
    mint: str
    decimals: int
    pre_amount_raw: int
    post_amount_raw: int
    delta_raw: int
    delta_ui: Decimal
    post_ui: Decimal

    def to_jsonable(self) -> Dict[str, Any]:
        out = asdict(self)
        out["delta_ui"] = str(self.delta_ui)
        out["post_ui"] = str(self.post_ui)
        return out


@dataclass(frozen=True)
class OwnerMintDelta:
    owner: str
    mint: str
    decimals: int
    delta_ui: Decimal


@dataclass(frozen=True)
class PoolLegMatch:
    side: str
    owner: str
    asset_mint: str
    asset_account: str
    asset_amount: Decimal
    quote_mint: str
    quote_account: str
    quote_amount: Decimal
    amount_match: bool
    evidence: str

    def to_jsonable(self) -> Dict[str, Any]:
        out = asdict(self)
        out["asset_amount"] = str(self.asset_amount)
        out["quote_amount"] = str(self.quote_amount)
        return out


@dataclass
class VerificationReport:
    signature: str
    rpc_url: str
    found: bool
    succeeded: bool
    slot: Optional[int]
    block_time: Optional[int]
    block_time_iso: Optional[str]
    fee_lamports: Optional[int]
    primary_signer: Optional[str]
    dex_protocol: str
    xdex_amm_invoked: bool
    xendex_amm_invoked: bool
    xendex_staking_invoked: bool
    program_ids: List[str]
    token_deltas: List[TokenDelta]
    signer_token_deltas: List[OwnerMintDelta]
    signer_native_xnt_delta: Optional[Decimal]
    signer_native_xnt_delta_before_fee: Optional[Decimal]
    inferred_side: str
    inferred_asset_mint: Optional[str]
    inferred_quote_mint: Optional[str]
    inferred_quote_amount: Optional[Decimal]
    pool_leg_match: Optional[PoolLegMatch]
    verification_basis: str
    inference_reason: str
    expected_side: Optional[str]
    expected_mint: Optional[str]
    expectation_match: Optional[bool]
    verification_level: str




def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)



def account_key_info(tx: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Return (all pubkeys in message order, signer pubkeys)."""
    message = ((tx.get("transaction") or {}).get("message") or {})
    raw_keys = message.get("accountKeys") or []
    pubkeys: List[str] = []
    signers: List[str] = []

    for index, item in enumerate(raw_keys):
        if isinstance(item, dict):
            pubkey = str(item.get("pubkey") or "")
            signer = bool(item.get("signer"))
        else:
            pubkey = str(item)
            # In raw account-key format signer metadata is absent. The fee payer
            # is conventionally account 0, so retain it as a safe fallback only.
            signer = index == 0

        pubkeys.append(pubkey)
        if signer and pubkey:
            signers.append(pubkey)

    return pubkeys, signers


def _instruction_program_id(instruction: Dict[str, Any], account_keys: Sequence[str]) -> Optional[str]:
    direct = instruction.get("programId")
    if isinstance(direct, str):
        return direct
    if isinstance(direct, dict):
        return str(direct.get("pubkey") or direct.get("address") or "") or None

    index = instruction.get("programIdIndex")
    if isinstance(index, int) and 0 <= index < len(account_keys):
        return account_keys[index]
    return None


def collect_program_ids(tx: Dict[str, Any]) -> List[str]:
    account_keys, _ = account_key_info(tx)
    message = ((tx.get("transaction") or {}).get("message") or {})
    meta = tx.get("meta") or {}

    ids: List[str] = []

    def add_from(instructions: Iterable[Dict[str, Any]]) -> None:
        for inst in instructions:
            if not isinstance(inst, dict):
                continue
            pid = _instruction_program_id(inst, account_keys)
            if pid and pid not in ids:
                ids.append(pid)

    add_from(message.get("instructions") or [])

    for group in meta.get("innerInstructions") or []:
        if isinstance(group, dict):
            add_from(group.get("instructions") or [])

    return ids


def _token_amount(balance: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    if not balance:
        return 0, 0
    ui = balance.get("uiTokenAmount") or {}
    try:
        amount = int(ui.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    try:
        decimals = int(ui.get("decimals") or 0)
    except (TypeError, ValueError):
        decimals = 0
    return amount, decimals


def compute_token_deltas(tx: Dict[str, Any]) -> List[TokenDelta]:
    """Compute per-token-account pre/post deltas from transaction metadata."""
    account_keys, _ = account_key_info(tx)
    meta = tx.get("meta") or {}
    pre_balances = meta.get("preTokenBalances") or []
    post_balances = meta.get("postTokenBalances") or []

    # Key by (accountIndex, mint). This safely handles the rare case where an
    # account index appears with different mint metadata across pre/post state.
    pre: Dict[Tuple[int, str], Dict[str, Any]] = {}
    post: Dict[Tuple[int, str], Dict[str, Any]] = {}

    for item in pre_balances:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("accountIndex", -1))
        mint = str(item.get("mint") or "")
        if idx >= 0 and mint:
            pre[(idx, mint)] = item

    for item in post_balances:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("accountIndex", -1))
        mint = str(item.get("mint") or "")
        if idx >= 0 and mint:
            post[(idx, mint)] = item

    rows: List[TokenDelta] = []
    for key in sorted(set(pre) | set(post), key=lambda x: (x[0], x[1])):
        idx, mint = key
        before = pre.get(key)
        after = post.get(key)
        pre_raw, pre_decimals = _token_amount(before)
        post_raw, post_decimals = _token_amount(after)
        decimals = post_decimals if after is not None else pre_decimals
        delta_raw = post_raw - pre_raw
        if delta_raw == 0:
            continue

        scale = Decimal(10) ** decimals
        owner = str((after or {}).get("owner") or (before or {}).get("owner") or "")
        account = account_keys[idx] if 0 <= idx < len(account_keys) else f"accountIndex:{idx}"

        rows.append(
            TokenDelta(
                account_index=idx,
                account=account,
                owner=owner or account,
                mint=mint,
                decimals=decimals,
                pre_amount_raw=pre_raw,
                post_amount_raw=post_raw,
                delta_raw=delta_raw,
                delta_ui=Decimal(delta_raw) / scale,
                post_ui=Decimal(post_raw) / scale,
            )
        )

    return rows


def aggregate_owner_mint_deltas(rows: Sequence[TokenDelta]) -> List[OwnerMintDelta]:
    totals: Dict[Tuple[str, str, int], Decimal] = {}
    for row in rows:
        key = (row.owner, row.mint, row.decimals)
        totals[key] = totals.get(key, Decimal(0)) + row.delta_ui

    out = [
        OwnerMintDelta(owner=k[0], mint=k[1], decimals=k[2], delta_ui=v)
        for k, v in totals.items()
        if v != 0
    ]
    out.sort(key=lambda x: (x.owner, x.mint))
    return out


def signer_native_delta(tx: Dict[str, Any], primary_signer: Optional[str]) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    if not primary_signer:
        return None, None

    account_keys, _ = account_key_info(tx)
    try:
        idx = account_keys.index(primary_signer)
    except ValueError:
        return None, None

    meta = tx.get("meta") or {}
    pre = meta.get("preBalances") or []
    post = meta.get("postBalances") or []
    if idx >= len(pre) or idx >= len(post):
        return None, None

    delta_lamports = int(post[idx]) - int(pre[idx])
    delta_xnt = Decimal(delta_lamports) / LAMPORTS_PER_XNT

    fee = int(meta.get("fee") or 0)
    # Add the fee back to expose the signer's approximate economic native-token
    # movement. Rent/account-creation effects can still be present, so this is
    # supporting evidence rather than a standalone proof of trade direction.
    before_fee = Decimal(delta_lamports + fee) / LAMPORTS_PER_XNT
    return delta_xnt, before_fee


def _quantized_amount(value: Decimal, decimals: int) -> Decimal:
    quantum = Decimal(1).scaleb(-decimals)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _provider_amount_matches(expected: Decimal, observed: Decimal, decimals: int) -> bool:
    """Compare provider float-like values at the chain token's native precision."""
    return _quantized_amount(abs(expected), decimals) == abs(observed)


def match_provider_pool_leg(
    token_rows: Sequence[TokenDelta],
    expected_side: Optional[str],
    expected_token_amount: Optional[Decimal],
    expected_native_amount: Optional[Decimal],
    quote_mints: Sequence[str],
) -> Optional[PoolLegMatch]:
    """Match one provider trade row to an exact on-chain pool/vault leg.

    X1.Ninja's BUY/SELL row can be one leg inside a larger routed/arbitrage
    transaction. In that case wallet-level net deltas are not a safe semantic
    target. This matcher instead looks for an asset/quote pair with the exact
    provider amounts, expected pool-side signs, and the same token-account owner.

    Provider BUY => pool loses asset and gains quote.
    Provider SELL => pool gains asset and loses quote.
    """
    if not expected_side or expected_token_amount is None or expected_native_amount is None:
        return None

    side = expected_side.upper()
    if side not in {"BUY", "SELL"}:
        return None

    quote_set = set(quote_mints)
    asset_sign = -1 if side == "BUY" else 1
    quote_sign = 1 if side == "BUY" else -1

    asset_candidates: List[TokenDelta] = []
    quote_candidates: List[TokenDelta] = []
    for row in token_rows:
        if row.mint in quote_set:
            if (row.delta_ui > 0) != (quote_sign > 0):
                continue
            if _provider_amount_matches(expected_native_amount, row.delta_ui, row.decimals):
                quote_candidates.append(row)
        else:
            if (row.delta_ui > 0) != (asset_sign > 0):
                continue
            if _provider_amount_matches(expected_token_amount, row.delta_ui, row.decimals):
                asset_candidates.append(row)

    same_owner_pairs = [
        (asset, quote)
        for asset in asset_candidates
        for quote in quote_candidates
        if asset.owner and asset.owner == quote.owner
    ]

    # Ambiguity is deliberately not promoted. Exact amount + common owner must
    # isolate one pool/vault leg.
    if len(same_owner_pairs) != 1:
        return None

    asset, quote = same_owner_pairs[0]
    return PoolLegMatch(
        side=side,
        owner=asset.owner,
        asset_mint=asset.mint,
        asset_account=asset.account,
        asset_amount=abs(asset.delta_ui),
        quote_mint=quote.mint,
        quote_account=quote.account,
        quote_amount=abs(quote.delta_ui),
        amount_match=True,
        evidence=(
            f"Exact provider {side} leg matched on-chain at token precision: "
            f"asset {abs(asset.delta_ui)} {asset.mint} and quote "
            f"{abs(quote.delta_ui)} {quote.mint} changed with the expected "
            f"pool-side signs under common owner {asset.owner}."
        ),
    )


def infer_side(
    primary_signer: Optional[str],
    signer_deltas: Sequence[OwnerMintDelta],
    token_rows: Sequence[TokenDelta],
    native_before_fee: Optional[Decimal],
    expected_mint: Optional[str],
    quote_mints: Sequence[str],
) -> Tuple[str, Optional[str], Optional[str], Optional[Decimal], str]:
    """Infer trade direction from signer + transaction-wide balance evidence.

    Strong BUY/SELL proof can come from either:
      1. a direct signer quote-token delta, or
      2. a wrapped/native route where the signer moves native XNT while a
         non-signer pool/vault receives or sends a known quote token and the
         asset-side token movement conserves exactly.

    The second path is important for XDEX swaps that wrap XNT inside the same
    transaction, because the signer's wallet may never show a WXNT token delta.
    """
    if not primary_signer:
        return "UNKNOWN", None, None, None, "No signer could be identified."

    by_mint = {
        d.mint: d.delta_ui
        for d in signer_deltas
        if d.owner == primary_signer and d.delta_ui != 0
    }
    quote_set = set(quote_mints)

    # Aggregate non-signer movements by mint. These are typically pool/vault
    # movements, but we avoid assuming ownership semantics that are not proven.
    nonsigner_by_mint: Dict[str, Decimal] = {}
    for row in token_rows:
        if row.owner == primary_signer:
            continue
        nonsigner_by_mint[row.mint] = (
            nonsigner_by_mint.get(row.mint, Decimal(0)) + row.delta_ui
        )

    def direct_quote_evidence(asset_mint: str, asset_delta: Decimal):
        for quote_mint, quote_delta in by_mint.items():
            if quote_mint not in quote_set:
                continue
            if asset_delta > 0 and quote_delta < 0:
                return (
                    "BUY",
                    asset_mint,
                    quote_mint,
                    abs(quote_delta),
                    f"Signer gained asset while directly losing quote mint {quote_mint}.",
                )
            if asset_delta < 0 and quote_delta > 0:
                return (
                    "SELL",
                    asset_mint,
                    quote_mint,
                    abs(quote_delta),
                    f"Signer lost asset while directly gaining quote mint {quote_mint}.",
                )
        return None

    def routed_native_quote_evidence(asset_mint: str, asset_delta: Decimal):
        """Recognize native XNT <-> WXNT routing with exact asset conservation."""
        nonsigner_asset_delta = nonsigner_by_mint.get(asset_mint, Decimal(0))

        # BUY: signer gains asset, counterparties lose exactly that asset,
        # a quote vault gains quote, and native XNT leaves the signer.
        if (
            asset_delta > 0
            and nonsigner_asset_delta == -asset_delta
            and native_before_fee is not None
            and native_before_fee < 0
        ):
            for quote_mint in quote_mints:
                quote_delta = nonsigner_by_mint.get(quote_mint, Decimal(0))
                if quote_delta > 0:
                    return (
                        "BUY",
                        asset_mint,
                        quote_mint,
                        quote_delta,
                        "Signer gained the asset; non-signer accounts lost the exact "
                        "same asset amount; a known quote mint increased on the "
                        "non-signer side; and native XNT decreased. This is consistent "
                        "with an in-transaction native-XNT -> wrapped-quote swap route.",
                    )

        # SELL: signer loses asset, counterparties gain exactly that asset,
        # a quote vault loses quote, and native XNT returns to the signer.
        if (
            asset_delta < 0
            and nonsigner_asset_delta == -asset_delta
            and native_before_fee is not None
            and native_before_fee > 0
        ):
            for quote_mint in quote_mints:
                quote_delta = nonsigner_by_mint.get(quote_mint, Decimal(0))
                if quote_delta < 0:
                    return (
                        "SELL",
                        asset_mint,
                        quote_mint,
                        abs(quote_delta),
                        "Signer lost the asset; non-signer accounts gained the exact "
                        "same asset amount; a known quote mint decreased on the "
                        "non-signer side; and native XNT increased. This is consistent "
                        "with an in-transaction wrapped-quote -> native-XNT swap route.",
                    )
        return None

    target_mint = expected_mint
    if target_mint and target_mint in by_mint:
        target_delta = by_mint[target_mint]

        direct = direct_quote_evidence(target_mint, target_delta)
        if direct:
            return direct

        routed = routed_native_quote_evidence(target_mint, target_delta)
        if routed:
            return routed

        if target_delta > 0 and native_before_fee is not None and native_before_fee < 0:
            return (
                "LIKELY_BUY",
                target_mint,
                None,
                None,
                "Signer gained the expected asset while native XNT decreased; "
                "quote-side token evidence was insufficient for deterministic proof.",
            )
        if target_delta < 0 and native_before_fee is not None and native_before_fee > 0:
            return (
                "LIKELY_SELL",
                target_mint,
                None,
                None,
                "Signer lost the expected asset while native XNT increased; "
                "quote-side token evidence was insufficient for deterministic proof.",
            )

        return (
            "UNKNOWN",
            target_mint,
            None,
            None,
            "Expected asset changed, but quote-side movement was insufficient "
            "for deterministic side classification.",
        )

    # No expected mint: independently identify a non-quote signer asset.
    asset_changes = [(m, v) for m, v in by_mint.items() if m not in quote_set]

    for asset_mint, asset_delta in asset_changes:
        direct = direct_quote_evidence(asset_mint, asset_delta)
        if direct:
            return direct

    for asset_mint, asset_delta in asset_changes:
        routed = routed_native_quote_evidence(asset_mint, asset_delta)
        if routed:
            return routed

    if len(asset_changes) == 1 and native_before_fee is not None:
        asset_mint, asset_delta = asset_changes[0]
        if asset_delta > 0 and native_before_fee < 0:
            return (
                "LIKELY_BUY",
                asset_mint,
                None,
                None,
                "Signer gained one non-quote token while native XNT decreased.",
            )
        if asset_delta < 0 and native_before_fee > 0:
            return (
                "LIKELY_SELL",
                asset_mint,
                None,
                None,
                "Signer lost one non-quote token while native XNT increased.",
            )

    return (
        "UNKNOWN",
        None,
        None,
        None,
        "Signer balance changes do not form a clean quote-token swap pattern.",
    )


def verify_transaction(
    tx: Optional[Dict[str, Any]],
    signature: str,
    rpc_url: str,
    expected_side: Optional[str] = None,
    expected_mint: Optional[str] = None,
    expected_token_amount: Optional[Decimal] = None,
    expected_native_amount: Optional[Decimal] = None,
    quote_mints: Sequence[str] = DEFAULT_QUOTE_MINTS,
) -> VerificationReport:
    expected_side = expected_side.upper() if expected_side else None

    if tx is None:
        return VerificationReport(
            signature=signature,
            rpc_url=rpc_url,
            found=False,
            succeeded=False,
            slot=None,
            block_time=None,
            block_time_iso=None,
            fee_lamports=None,
            primary_signer=None,
            dex_protocol="UNRESOLVED",
            xdex_amm_invoked=False,
            xendex_amm_invoked=False,
            xendex_staking_invoked=False,
            program_ids=[],
            token_deltas=[],
            signer_token_deltas=[],
            signer_native_xnt_delta=None,
            signer_native_xnt_delta_before_fee=None,
            inferred_side="UNKNOWN",
            inferred_asset_mint=None,
            inferred_quote_mint=None,
            inferred_quote_amount=None,
            pool_leg_match=None,
            verification_basis="NONE",
            inference_reason="Transaction was not found at the requested commitment.",
            expected_side=expected_side,
            expected_mint=expected_mint,
            expectation_match=None,
            verification_level="NOT_FOUND",
        )

    meta = tx.get("meta") or {}
    succeeded = meta.get("err") is None
    program_ids = collect_program_ids(tx)
    token_rows = compute_token_deltas(tx)
    owner_rows = aggregate_owner_mint_deltas(token_rows)
    _, signers = account_key_info(tx)
    primary_signer = signers[0] if signers else None
    native_delta, native_before_fee = signer_native_delta(tx, primary_signer)

    inferred_side, inferred_asset_mint, inferred_quote_mint, inferred_quote_amount, reason = infer_side(
        primary_signer,
        owner_rows,
        token_rows,
        native_before_fee,
        expected_mint,
        quote_mints,
    )

    pool_leg = match_provider_pool_leg(
        token_rows,
        expected_side,
        expected_token_amount,
        expected_native_amount,
        quote_mints,
    )

    match: Optional[bool] = None
    verification_basis = "TRANSACTION_ONLY"
    if expected_side:
        if pool_leg is not None:
            match = pool_leg.side == expected_side
            verification_basis = "EXACT_POOL_LEG_AMOUNTS"
            inferred_side = pool_leg.side
            inferred_asset_mint = pool_leg.asset_mint
            inferred_quote_mint = pool_leg.quote_mint
            inferred_quote_amount = pool_leg.quote_amount
            reason = pool_leg.evidence
        else:
            normalized_inferred = inferred_side.replace("LIKELY_", "")
            if normalized_inferred in ("BUY", "SELL"):
                match = normalized_inferred == expected_side
                verification_basis = "SIGNER_OR_ROUTED_BALANCE_DIRECTION"
            else:
                # UNKNOWN is unresolved, not contradictory.
                match = None
                verification_basis = "UNRESOLVED_MULTI_LEG_OR_INSUFFICIENT_EVIDENCE"

    xdex_amm = XDEX_MAINNET_OBSERVED_PROGRAM_ID in program_ids
    xendex_amm = XENDEX_AMM_PROGRAM_ID in program_ids
    xendex_staking = XENDEX_STAKING_PROGRAM_ID in program_ids
    recognized_dex = xdex_amm or xendex_amm

    if xdex_amm and xendex_amm:
        dex_protocol = "XDEX+XENDEX"
    elif xdex_amm:
        dex_protocol = "XDEX"
    elif xendex_amm:
        dex_protocol = "XENDEX"
    else:
        dex_protocol = "UNRESOLVED"

    if not succeeded:
        level = "CHAIN_FAILED"
    elif not recognized_dex:
        level = "CHAIN_CONFIRMED_NON_RECOGNIZED_DEX_OR_UNRESOLVED"
    elif not token_rows:
        level = "RECOGNIZED_DEX_CONFIRMED_NO_TOKEN_DELTAS"
    elif expected_side and pool_leg is not None and match is True:
        level = "PROVIDER_SIDE_ONCHAIN_CONFIRMED"
    elif expected_side and match is True and inferred_side in ("BUY", "SELL"):
        level = "PROVIDER_SIDE_ONCHAIN_CONFIRMED"
    elif expected_side and match is True:
        level = "PROVIDER_SIDE_ONCHAIN_SUPPORTED"
    elif expected_side and match is False:
        level = "PROVIDER_ONCHAIN_DIRECTION_MISMATCH"
    elif expected_side and match is None:
        level = "PROVIDER_SIDE_ONCHAIN_UNRESOLVED"
    elif recognized_dex:
        level = "DEX_ONCHAIN_CONFIRMED"
    else:
        level = "CHAIN_CONFIRMED"

    block_time = tx.get("blockTime")
    block_time_iso = None
    if isinstance(block_time, int):
        block_time_iso = datetime.fromtimestamp(block_time, tz=timezone.utc).isoformat()

    return VerificationReport(
        signature=signature,
        rpc_url=rpc_url,
        found=True,
        succeeded=succeeded,
        slot=tx.get("slot"),
        block_time=block_time,
        block_time_iso=block_time_iso,
        fee_lamports=int(meta.get("fee") or 0),
        primary_signer=primary_signer,
        dex_protocol=dex_protocol,
        xdex_amm_invoked=xdex_amm,
        xendex_amm_invoked=xendex_amm,
        xendex_staking_invoked=xendex_staking,
        program_ids=program_ids,
        token_deltas=token_rows,
        signer_token_deltas=[d for d in owner_rows if primary_signer and d.owner == primary_signer],
        signer_native_xnt_delta=native_delta,
        signer_native_xnt_delta_before_fee=native_before_fee,
        inferred_side=inferred_side,
        inferred_asset_mint=inferred_asset_mint,
        inferred_quote_mint=inferred_quote_mint,
        inferred_quote_amount=inferred_quote_amount,
        pool_leg_match=pool_leg,
        verification_basis=verification_basis,
        inference_reason=reason,
        expected_side=expected_side,
        expected_mint=expected_mint,
        expectation_match=match,
        verification_level=level,
    )



def fetch_transaction(
    signature: str,
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    retries: int = 4,
    timeout: int = 25,
    request=rpc_request,
) -> Optional[Dict[str, Any]]:
    """Fetch one parsed X1 transaction at confirmed commitment."""
    signature = str(signature or "").strip()
    if not signature:
        raise ValueError("transaction signature is required")
    return request(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
        rpc_url=rpc_url,
        retries=retries,
        timeout=timeout,
    )


def verify_signature(
    signature: str,
    *,
    rpc_url: str = DEFAULT_X1_RPC_URL,
    expected_side: Optional[str] = None,
    expected_mint: Optional[str] = None,
    expected_token_amount: Optional[Decimal] = None,
    expected_native_amount: Optional[Decimal] = None,
    quote_mints: Sequence[str] = DEFAULT_QUOTE_MINTS,
    retries: int = 4,
    timeout: int = 25,
    request=rpc_request,
) -> VerificationReport:
    """Fetch and deterministically verify one X1 transaction signature."""
    tx = fetch_transaction(
        signature,
        rpc_url=rpc_url,
        retries=retries,
        timeout=timeout,
        request=request,
    )
    return verify_transaction(
        tx,
        signature=signature,
        rpc_url=rpc_url,
        expected_side=expected_side,
        expected_mint=expected_mint,
        expected_token_amount=expected_token_amount,
        expected_native_amount=expected_native_amount,
        quote_mints=quote_mints,
    )


def report_to_dict(report: VerificationReport) -> Dict[str, Any]:
    """Return a JSON-safe representation suitable for CMIS evidence records."""
    return {
        "signature": report.signature,
        "rpc_url": report.rpc_url,
        "found": report.found,
        "succeeded": report.succeeded,
        "slot": report.slot,
        "block_time": report.block_time,
        "block_time_iso": report.block_time_iso,
        "fee_lamports": report.fee_lamports,
        "primary_signer": report.primary_signer,
        "dex_protocol": report.dex_protocol,
        "xdex_amm_invoked": report.xdex_amm_invoked,
        "xendex_amm_invoked": report.xendex_amm_invoked,
        "xendex_staking_invoked": report.xendex_staking_invoked,
        "program_ids": list(report.program_ids),
        "token_deltas": [x.to_jsonable() for x in report.token_deltas],
        "signer_token_deltas": [
            {
                "owner": x.owner,
                "mint": x.mint,
                "decimals": x.decimals,
                "delta_ui": str(x.delta_ui),
            }
            for x in report.signer_token_deltas
        ],
        "signer_native_xnt_delta": (
            None if report.signer_native_xnt_delta is None
            else str(report.signer_native_xnt_delta)
        ),
        "signer_native_xnt_delta_before_fee": (
            None if report.signer_native_xnt_delta_before_fee is None
            else str(report.signer_native_xnt_delta_before_fee)
        ),
        "inferred_side": report.inferred_side,
        "inferred_asset_mint": report.inferred_asset_mint,
        "inferred_quote_mint": report.inferred_quote_mint,
        "inferred_quote_amount": (
            None if report.inferred_quote_amount is None
            else str(report.inferred_quote_amount)
        ),
        "pool_leg_match": (
            None if report.pool_leg_match is None
            else report.pool_leg_match.to_jsonable()
        ),
        "verification_basis": report.verification_basis,
        "inference_reason": report.inference_reason,
        "expected_side": report.expected_side,
        "expected_mint": report.expected_mint,
        "expectation_match": report.expectation_match,
        "verification_level": report.verification_level,
    }


__all__ = [
    "DEFAULT_QUOTE_MINTS",
    "PoolLegMatch",
    "TokenDelta",
    "VerificationReport",
    "USDC_X_MINT",
    "WXNT_MINT",
    "XDEX_MAINNET_OBSERVED_PROGRAM_ID",
    "XENDEX_AMM_PROGRAM_ID",
    "XENDEX_STAKING_PROGRAM_ID",
    "account_key_info",
    "aggregate_owner_mint_deltas",
    "collect_program_ids",
    "compute_token_deltas",
    "fetch_transaction",
    "infer_side",
    "match_provider_pool_leg",
    "report_to_dict",
    "signer_native_delta",
    "verify_signature",
    "verify_transaction",
]
