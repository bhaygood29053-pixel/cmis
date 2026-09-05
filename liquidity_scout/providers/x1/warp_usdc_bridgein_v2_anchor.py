"""Exact X1 Warp BridgeInV2 anchor for the observed USDC -> USDC.X transfer.

This contract is intentionally fixture-scoped. It verifies only the exact
observed destination transaction shape needed to establish destination mint
amount semantics for one real bridge event. It does not infer route-wide
reserve sufficiency or current USDC.X/USD equivalence by itself.
"""

from __future__ import annotations

from typing import Any

CONTRACT = "warp_usdc_bridgein_v2_anchor/v1"
WARP_PROGRAM_ID = "6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD"
USDC_X_MINT = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
DESTINATION_TX_SIGNATURE = (
    "4PMmzc8Hy1qq7i5AQ2FGRgEi32ZS1DcZS9y7b86xfqaX7wNiFC2t5FWBddj8SsE5cMGW5zfkRRaTFmMgy5ChiuqG"
)
DESTINATION_SLOT = 68029675
BRIDGEIN_V2_DISCRIMINATOR = bytes.fromhex("671b568b6dbd35f6")
EXPECTED_SOURCE_SEQ = 72058030190379936
EXPECTED_AMOUNT_RAW = 24007049
EXPECTED_SOURCE_TIMESTAMP = 1785414786
EXPECTED_DECIMALS = 6


def verify_usdc_bridgein_v2_anchor(
    *,
    signature: Any,
    slot: Any,
    program_id: Any,
    instruction_data_hex: Any,
    mint_to_mint: Any,
    mint_to_amount_raw: Any,
) -> dict[str, Any]:
    if str(signature or "").strip() != DESTINATION_TX_SIGNATURE:
        raise ValueError("destination transaction signature mismatch")
    if int(slot) != DESTINATION_SLOT:
        raise ValueError("destination slot mismatch")
    if str(program_id or "").strip() != WARP_PROGRAM_ID:
        raise ValueError("Warp program id mismatch")
    if str(mint_to_mint or "").strip() != USDC_X_MINT:
        raise ValueError("USDC.X mint mismatch")

    try:
        data = bytes.fromhex(str(instruction_data_hex or "").replace(" ", ""))
    except ValueError as exc:
        raise ValueError("instruction_data_hex must be valid hex") from exc
    if len(data) != 96:
        raise ValueError("BridgeInV2 anchor instruction must be exactly 96 bytes")
    if data[:8] != BRIDGEIN_V2_DISCRIMINATOR:
        raise ValueError("BridgeInV2 discriminator mismatch")

    source_seq = int.from_bytes(data[8:16], "little", signed=False)
    amount_raw = int.from_bytes(data[80:88], "little", signed=False)
    source_timestamp = int.from_bytes(data[88:96], "little", signed=False)

    try:
        mint_amount = int(mint_to_amount_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("mint_to_amount_raw must be an integer") from exc

    verified = bool(
        source_seq == EXPECTED_SOURCE_SEQ
        and amount_raw == EXPECTED_AMOUNT_RAW
        and mint_amount == EXPECTED_AMOUNT_RAW
        and source_timestamp == EXPECTED_SOURCE_TIMESTAMP
    )

    return {
        "contract": CONTRACT,
        "destination_tx_signature": DESTINATION_TX_SIGNATURE,
        "destination_slot": DESTINATION_SLOT,
        "program_id": WARP_PROGRAM_ID,
        "destination_mint": USDC_X_MINT,
        "source_seq": source_seq,
        "source_seq_verified": source_seq == EXPECTED_SOURCE_SEQ,
        "instruction_amount_raw": amount_raw,
        "mint_to_amount_raw": mint_amount,
        "amount_raw_match_verified": amount_raw == mint_amount == EXPECTED_AMOUNT_RAW,
        "amount": f"{EXPECTED_AMOUNT_RAW / (10 ** EXPECTED_DECIMALS):.6f}",
        "decimals": EXPECTED_DECIMALS,
        "source_timestamp": source_timestamp,
        "source_timestamp_verified": source_timestamp == EXPECTED_SOURCE_TIMESTAMP,
        "destination_mint_amount_semantics_verified": verified,
        "route_wide_backing_verified": False,
        "current_usdcx_usd_equivalence_verified": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT",
    "DESTINATION_SLOT",
    "DESTINATION_TX_SIGNATURE",
    "EXPECTED_AMOUNT_RAW",
    "EXPECTED_SOURCE_SEQ",
    "USDC_X_MINT",
    "WARP_PROGRAM_ID",
    "verify_usdc_bridgein_v2_anchor",
]
