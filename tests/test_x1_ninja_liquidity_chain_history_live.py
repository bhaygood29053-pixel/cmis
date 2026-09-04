import json
import os
import unittest

from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_CHAIN_HISTORY_LIVE") == "1"
PROGRAM_0_OFFSET = 232
PROGRAM_1_OFFSET = 264
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200

POOLS = [
    ("GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x", "original_fail_4.07pct"),
    ("GdKcXA1Q78Bquke5jyZUR1C8YMN6VYT9AUheN1RwKLfe", "original_fail_3.46pct"),
    ("Ec3Keyy1yemycLRjh8PgkKiDJaD3w77UBLViwtB5zmSJ", "original_fail_6.57pct"),
    ("7deZorr98nLdZhpmSdUgu8WY4NAjSpeLDGxHzaTAxrUg", "original_control_exact"),
    ("EcmFn1chD6T9rE3XctPUDxjcqEDT3n2YeQJH627rSCD5", "original_control_exact"),
]


def _text(value):
    text = str(value or "").strip()
    return text or None


def _classify_logs(logs):
    text = "\n".join(str(line) for line in (logs or [])).lower()
    names = {
        "swap": ("instruction: swap", "swap_base_input", "swap_base_output"),
        "deposit": ("instruction: deposit",),
        "withdraw": ("instruction: withdraw",),
        "collect_protocol_fee": ("instruction: collectprotocolfee", "collect_protocol_fee"),
        "collect_fund_fee": ("instruction: collectfundfee", "collect_fund_fee"),
        "collect_creator_fee": ("instruction: collectcreatorfee", "collect_creator_fee"),
        "initialize": ("instruction: initialize",),
        "update_pool_status": ("instruction: updatepoolstatus", "update_pool_status"),
    }
    return [
        name for name, needles in names.items()
        if any(needle in text for needle in needles)
    ]


def _mint_probe(mint):
    raw = rpc_request(
        "getAccountInfo",
        [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}],
    )
    value = raw.get("value") if isinstance(raw, dict) else None
    if not isinstance(value, dict):
        return {"mint": mint, "exists": False}
    data = value.get("data")
    parsed = data.get("parsed") if isinstance(data, dict) else None
    info = parsed.get("info") if isinstance(parsed, dict) else None
    extensions = info.get("extensions") if isinstance(info, dict) else None
    return {
        "mint": mint,
        "exists": True,
        "program_owner": _text(value.get("owner")),
        "parsed_type": _text(parsed.get("type")) if isinstance(parsed, dict) else None,
        "extensions": extensions if isinstance(extensions, list) else [],
        "has_transfer_fee_extension": any(
            "transferfee" in str(item).lower()
            for item in (extensions or [])
        ),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_CHAIN_HISTORY_LIVE=1 for read-only pool history evidence",
)
class X1NinjaLiquidityChainHistoryLiveTests(unittest.TestCase):
    def test_compare_failing_and_control_pool_history(self):
        output = []
        for pool, label in POOLS:
            state = fetch_account_state(pool)
            data = state.get("data")
            self.assertIsInstance(data, bytes)
            self.assertEqual(len(data), 637)
            mint_0 = extract_pubkey_at(data, MINT_0_OFFSET)
            mint_1 = extract_pubkey_at(data, MINT_1_OFFSET)
            program_0 = extract_pubkey_at(data, PROGRAM_0_OFFSET)
            program_1 = extract_pubkey_at(data, PROGRAM_1_OFFSET)
            if mint_0 == WRAPPED_XNT_MINT:
                asset_mint = mint_1
                asset_program = program_1
            elif mint_1 == WRAPPED_XNT_MINT:
                asset_mint = mint_0
                asset_program = program_0
            else:
                raise AssertionError(f"{pool} has no wrapped-XNT side")

            history = rpc_request(
                "getSignaturesForAddress",
                [pool, {"limit": 30, "commitment": "confirmed"}],
            )
            self.assertIsInstance(history, list)

            class_counts = {}
            recent = []
            fetch_failures = []
            for item in history:
                if not isinstance(item, dict) or item.get("err") is not None:
                    continue
                signature = _text(item.get("signature"))
                if not signature:
                    continue
                try:
                    tx = rpc_request(
                        "getTransaction",
                        [
                            signature,
                            {
                                "encoding": "jsonParsed",
                                "commitment": "confirmed",
                                "maxSupportedTransactionVersion": 0,
                            },
                        ],
                    )
                except Exception as exc:
                    fetch_failures.append(f"{type(exc).__name__}: {exc}")
                    continue
                if not isinstance(tx, dict):
                    continue
                meta = tx.get("meta") or {}
                classes = _classify_logs(meta.get("logMessages") or [])
                for name in classes:
                    class_counts[name] = class_counts.get(name, 0) + 1
                recent.append({
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "block_time": tx.get("blockTime"),
                    "classes": classes,
                    "success": meta.get("err") is None,
                })

            mint_evidence = _mint_probe(asset_mint)
            output.append({
                "pool_address": pool,
                "original_461_class": label,
                "asset_mint": asset_mint,
                "asset_token_program_from_pool_state": asset_program,
                "mint_probe": mint_evidence,
                "returned_signature_count": len(history),
                "fetched_transaction_count": len(recent),
                "instruction_class_counts": class_counts,
                "fee_collection_observed": any(
                    class_counts.get(name, 0) > 0
                    for name in (
                        "collect_protocol_fee",
                        "collect_fund_fee",
                        "collect_creator_fee",
                    )
                ),
                "liquidity_change_observed": bool(
                    class_counts.get("deposit", 0)
                    or class_counts.get("withdraw", 0)
                ),
                "recent_transactions": recent,
                "transaction_fetch_failures": fetch_failures,
            })

        evidence = {
            "schema": "x1_liquidity_461_chain_history.v1",
            "chain": "x1",
            "sample_count": len(output),
            "history_limit_per_pool": 30,
            "pools": output,
            "onchain_accounting_explanation_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 FAILING VS CONTROL CHAIN HISTORY")
        print(json.dumps(evidence, sort_keys=True, default=str))
        self.assertEqual(len(output), 5)
        self.assertFalse(evidence["onchain_accounting_explanation_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
