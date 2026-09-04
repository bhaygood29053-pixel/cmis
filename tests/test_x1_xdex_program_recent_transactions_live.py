import json
import os
import unittest
from collections import Counter
from pathlib import Path

from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    account_key_info,
    collect_program_ids,
    compute_token_deltas,
    fetch_transaction,
)


RUN_LIVE = os.getenv("RUN_X1_XDEX_PROGRAM_TX_CLASSIFIER_LIVE") == "1"
FIXTURE = Path(__file__).parent / "fixtures" / "xdex_program_recent_20260904.json"
BPF_UPGRADEABLE_LOADER = "BPFLoaderUpgradeab1e11111111111111111111111"

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


def _inner_instruction_count(tx):
    meta = tx.get("meta") or {}
    total = 0
    for group in meta.get("innerInstructions") or []:
        if not isinstance(group, dict):
            continue
        instructions = group.get("instructions") or []
        total += len(instructions)
    return total


def _top_level_count(tx):
    message = ((tx.get("transaction") or {}).get("message") or {})
    return len(message.get("instructions") or [])


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_XDEX_PROGRAM_TX_CLASSIFIER_LIVE=1 for recent XDEX-program evidence",
)
class X1XdexProgramTransactionClassifierLiveTests(unittest.TestCase):
    def test_classify_recent_program_transactions_and_pool_intersections(self):
        fixture = json.loads(FIXTURE.read_text())
        self.assertEqual(fixture["program_account"], XDEX_MAINNET_OBSERVED_PROGRAM_ID)
        rows = fixture["rows"]
        self.assertEqual(len(rows), 25)

        program_info = rpc_request(
            "getAccountInfo",
            [
                XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                {"encoding": "base64", "commitment": "confirmed"},
            ],
        )
        self.assertIsInstance(program_info, dict)
        program_value = program_info.get("value")
        self.assertIsInstance(program_value, dict)
        self.assertEqual(program_value.get("owner"), BPF_UPGRADEABLE_LOADER)

        evidence_rows = []
        for anchor in rows:
            tx = fetch_transaction(anchor["signature"])
            self.assertIsInstance(tx, dict, f"transaction unavailable: {anchor['signature']}")
            meta = tx.get("meta") or {}
            succeeded = meta.get("err") is None
            account_keys, signers = account_key_info(tx)
            programs = collect_program_ids(tx)
            names = _instruction_names(meta.get("logMessages") or [])
            token_deltas = compute_token_deltas(tx)
            pool_hits = [pool for pool in POOL_SET if pool in account_keys]

            observed_cu = meta.get("computeUnitsConsumed")
            observed_fee = int(meta.get("fee") or 0)
            top_count = _top_level_count(tx)
            inner_count = _inner_instruction_count(tx)

            evidence_rows.append({
                "signature": anchor["signature"],
                "slot": tx.get("slot"),
                "anchor_slot": anchor["slot"],
                "fee_lamports": observed_fee,
                "anchor_fee_lamports": anchor["fee_lamports"],
                "compute_units": observed_cu,
                "anchor_compute_units": anchor["compute_units"],
                "top_level_instruction_count": top_count,
                "anchor_top_level_instruction_count": anchor["top_level_instructions"],
                "inner_instruction_count": inner_count,
                "anchor_inner_instruction_count": anchor["inner_instructions"],
                "succeeded": succeeded,
                "rpc_error": meta.get("err"),
                "signers": signers,
                "primary_signer": signers[0] if signers else None,
                "program_ids": programs,
                "xdex_invoked": XDEX_MAINNET_OBSERVED_PROGRAM_ID in programs,
                "instruction_names": names,
                "five_pool_hits": pool_hits,
                "five_pool_hit_labels": [POOL_SET[pool] for pool in pool_hits],
                "token_delta_count": len(token_deltas),
                "token_mints_changed": sorted({delta.mint for delta in token_deltas}),
                "block_time": tx.get("blockTime"),
            })

        instruction_counter = Counter()
        signer_counter = Counter()
        shape_counter = Counter()
        pool_counter = Counter()
        for row in evidence_rows:
            for name in row["instruction_names"]:
                instruction_counter[name] += 1
            if row["primary_signer"]:
                signer_counter[row["primary_signer"]] += 1
            shape_counter[
                (
                    row["top_level_instruction_count"],
                    row["inner_instruction_count"],
                    row["anchor_compute_units"],
                )
            ] += 1
            for pool in row["five_pool_hits"]:
                pool_counter[pool] += 1

        groups = {}
        for row in evidence_rows:
            key = "/".join(row["instruction_names"]) or "NO_ANCHOR_INSTRUCTION_NAME"
            group = groups.setdefault(key, {
                "count": 0,
                "compute_units": [],
                "shapes": [],
                "signers": [],
                "five_pool_hits": [],
                "signatures": [],
            })
            group["count"] += 1
            group["compute_units"].append(row["compute_units"])
            group["shapes"].append(
                [row["top_level_instruction_count"], row["inner_instruction_count"]]
            )
            if row["primary_signer"] not in group["signers"]:
                group["signers"].append(row["primary_signer"])
            for pool in row["five_pool_hits"]:
                if pool not in group["five_pool_hits"]:
                    group["five_pool_hits"].append(pool)
            group["signatures"].append(row["signature"])

        successful_count = sum(row["succeeded"] for row in evidence_rows)
        failed_count = len(evidence_rows) - successful_count
        explorer_stats = fixture.get("explorer_recent_stats") or {}

        evidence = {
            "schema": "x1_xdex_program_recent_transaction_classification.v1",
            "chain": "x1",
            "program_account": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
            "program_owner": program_value.get("owner"),
            "program_owner_is_upgradeable_loader": (
                program_value.get("owner") == BPF_UPGRADEABLE_LOADER
            ),
            "program_account_is_human_wallet": False,
            "anchor_count": len(evidence_rows),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "explorer_expected_successful": explorer_stats.get("successful"),
            "explorer_expected_failed": explorer_stats.get("failed"),
            "success_failure_split_matches_explorer": (
                successful_count == explorer_stats.get("successful")
                and failed_count == explorer_stats.get("failed")
            ),
            "all_slots_match": all(
                row["slot"] == row["anchor_slot"] for row in evidence_rows
            ),
            "all_fees_match": all(
                row["fee_lamports"] == row["anchor_fee_lamports"] for row in evidence_rows
            ),
            "compute_unit_match_count": sum(
                row["compute_units"] == row["anchor_compute_units"]
                for row in evidence_rows
            ),
            "top_level_count_match_count": sum(
                row["top_level_instruction_count"] == row["anchor_top_level_instruction_count"]
                for row in evidence_rows
            ),
            "inner_count_match_count": sum(
                row["inner_instruction_count"] == row["anchor_inner_instruction_count"]
                for row in evidence_rows
            ),
            "xdex_invoked_count": sum(row["xdex_invoked"] for row in evidence_rows),
            "instruction_name_counts": dict(instruction_counter),
            "primary_signer_counts": dict(signer_counter),
            "five_pool_hit_counts": dict(pool_counter),
            "instruction_groups": groups,
            "transactions": evidence_rows,
            "liquidity_refresh_instruction_semantics_verified": False,
            "liquidity_fact_time_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 RECENT XDEX PROGRAM TRANSACTION CLASSIFICATION")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(evidence["program_owner_is_upgradeable_loader"])
        self.assertTrue(evidence["success_failure_split_matches_explorer"])
        self.assertTrue(evidence["all_slots_match"])
        self.assertTrue(evidence["all_fees_match"])
        self.assertEqual(evidence["xdex_invoked_count"], len(evidence_rows))
        self.assertFalse(evidence["liquidity_refresh_instruction_semantics_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()