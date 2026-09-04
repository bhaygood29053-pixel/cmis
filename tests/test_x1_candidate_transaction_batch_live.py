import json
import os
import unittest
from collections import Counter
from pathlib import Path

from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    account_key_info,
    collect_program_ids,
    compute_token_deltas,
    fetch_transaction,
)

RUN_LIVE = os.getenv("RUN_X1_CANDIDATE_TX_BATCH_LIVE") == "1"
FIXTURE = Path(__file__).parent / "fixtures" / "xdex_candidate_batch_20260904_1647.json"

POOL_SET = {
    "GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x": "original_fail_4.07pct",
    "GdKcXA1Q78Bquke5jyZUR1C8YMN6VYT9AUheN1RwKLfe": "original_fail_3.46pct_recovered_once",
    "Ec3Keyy1yemycLRjh8PgkKiDJaD3w77UBLViwtB5zmSJ": "original_fail_6.57pct",
    "7deZorr98nLdZhpmSdUgu8WY4NAjSpeLDGxHzaTAxrUg": "original_control_exact",
    "EcmFn1chD6T9rE3XctPUDxjcqEDT3n2YeQJH627rSCD5": "original_control_exact",
}

def _instruction_names(logs):
    names = []
    for line in logs or []:
        text = str(line or "")
        marker = "Program log: Instruction: "
        if marker in text:
            name = text.split(marker, 1)[1].strip()
            if name and name not in names:
                names.append(name)
    return names

@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_CANDIDATE_TX_BATCH_LIVE=1 for user candidate transaction evidence",
)
class X1CandidateTransactionBatchLiveTests(unittest.TestCase):
    def test_classify_user_candidate_batch(self):
        fixture = json.loads(FIXTURE.read_text())
        rows = fixture["rows"]
        self.assertEqual(len(rows), fixture["row_count"])

        evidence_rows = []
        for anchor in rows:
            tx = fetch_transaction(anchor["signature"])
            self.assertIsInstance(tx, dict, f"transaction unavailable: {anchor['signature']}")
            meta = tx.get("meta") or {}
            account_keys, signers = account_key_info(tx)
            programs = collect_program_ids(tx)
            names = _instruction_names(meta.get("logMessages") or [])
            token_deltas = compute_token_deltas(tx)
            pool_hits = [pool for pool in POOL_SET if pool in account_keys]

            evidence_rows.append({
                "signature": anchor["signature"],
                "slot": tx.get("slot"),
                "anchor_slot": anchor["slot"],
                "succeeded": meta.get("err") is None,
                "rpc_error": meta.get("err"),
                "primary_signer": signers[0] if signers else None,
                "program_ids": programs,
                "xdex_invoked": XDEX_MAINNET_OBSERVED_PROGRAM_ID in programs,
                "instruction_names": names,
                "five_pool_hits": pool_hits,
                "five_pool_hit_labels": [POOL_SET[p] for p in pool_hits],
                "token_delta_count": len(token_deltas),
                "token_mints_changed": sorted({delta.mint for delta in token_deltas}),
                "compute_units": meta.get("computeUnitsConsumed"),
                "fee_lamports": int(meta.get("fee") or 0),
                "block_time": tx.get("blockTime"),
            })

        instruction_counter = Counter()
        signer_counter = Counter()
        pool_counter = Counter()
        for row in evidence_rows:
            for name in row["instruction_names"]:
                instruction_counter[name] += 1
            if row["primary_signer"]:
                signer_counter[row["primary_signer"]] += 1
            for pool in row["five_pool_hits"]:
                pool_counter[pool] += 1

        xdex_rows = [row for row in evidence_rows if row["xdex_invoked"]]
        non_swap_xdex_rows = [
            row for row in xdex_rows
            if not any(name == "SwapBaseInput" for name in row["instruction_names"])
        ]
        target_rows = [row for row in evidence_rows if row["five_pool_hits"]]

        evidence = {
            "schema": "x1_461_user_candidate_transaction_batch.v1",
            "chain": "x1",
            "anchor_count": len(evidence_rows),
            "all_slots_match": all(
                row["slot"] == row["anchor_slot"] for row in evidence_rows
            ),
            "successful_count": sum(row["succeeded"] for row in evidence_rows),
            "xdex_invoked_count": len(xdex_rows),
            "non_swap_xdex_count": len(non_swap_xdex_rows),
            "five_pool_hit_count": len(target_rows),
            "instruction_name_counts": dict(instruction_counter),
            "primary_signer_counts": dict(signer_counter),
            "five_pool_hit_counts": dict(pool_counter),
            "non_swap_xdex_transactions": non_swap_xdex_rows,
            "five_pool_transactions": target_rows,
            "transactions": evidence_rows,
            "liquidity_refresh_instruction_semantics_verified": False,
            "liquidity_fact_time_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 USER CANDIDATE TRANSACTION BATCH")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(evidence["all_slots_match"])
        self.assertFalse(evidence["liquidity_refresh_instruction_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])

if __name__ == "__main__":
    unittest.main()
