import base64
import json
import os
import unittest

from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.rpc import rpc_request
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    account_key_info,
    collect_program_ids,
    fetch_transaction,
)

from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT

RUN_LIVE = os.getenv("RUN_X1_461_CANDIDATE_ACCOUNT_LIVE") == "1"
ADDRESS = "AAoKjyzkykEmaULghjbGRJPzRjYYSaRRpyJTcZroReSs"
POOL_SPACE = 637
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200

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
    "set RUN_X1_461_CANDIDATE_ACCOUNT_LIVE=1 for read-only account evidence",
)
class X1461CandidateAccountLiveTests(unittest.TestCase):
    def test_identify_account_and_recent_xdex_activity(self):
        raw = rpc_request(
            "getAccountInfo",
            [ADDRESS, {"encoding": "base64", "commitment": "confirmed"}],
        )
        target_value = raw.get("value") if isinstance(raw, dict) else None
        self.assertIsInstance(target_value, dict, "account not found on X1")

        encoded = (target_value.get("data") or [None])[0]
        data = base64.b64decode(encoded) if isinstance(encoded, str) else b""
        owner = target_value.get("owner")

        signatures = rpc_request(
            "getSignaturesForAddress",
            [ADDRESS, {"limit": 30, "commitment": "confirmed"}],
        )
        self.assertIsInstance(signatures, list)

        tx_rows = []
        all_message_accounts = set()
        for item in signatures:
            if not isinstance(item, dict):
                continue
            signature = item.get("signature")
            if not isinstance(signature, str):
                continue
            tx = fetch_transaction(signature)
            if not isinstance(tx, dict):
                continue
            meta = tx.get("meta") or {}
            keys, signers = account_key_info(tx)
            all_message_accounts.update(keys)
            programs = collect_program_ids(tx)
            tx_rows.append({
                "signature": signature,
                "slot": tx.get("slot"),
                "block_time": tx.get("blockTime"),
                "succeeded": meta.get("err") is None,
                "rpc_error": meta.get("err"),
                "primary_signer": signers[0] if signers else None,
                "address_in_message": ADDRESS in keys,
                "message_accounts": keys,
                "xdex_invoked": XDEX_MAINNET_OBSERVED_PROGRAM_ID in programs,
                "program_ids": programs,
                "instruction_names": _instruction_names(meta.get("logMessages") or []),
                "compute_units": meta.get("computeUnitsConsumed"),
                "fee_lamports": meta.get("fee"),
            })

        account_list = sorted(all_message_accounts)
        account_info = {}
        for offset in range(0, len(account_list), 100):
            batch = account_list[offset:offset + 100]
            result = rpc_request(
                "getMultipleAccounts",
                [batch, {"encoding": "base64", "commitment": "confirmed"}],
            )
            values = result.get("value") if isinstance(result, dict) else None
            self.assertIsInstance(values, list)
            self.assertEqual(len(values), len(batch))
            for account, account_value in zip(batch, values):
                account_info[account] = account_value

        pool_candidates = []
        for account, account_value in account_info.items():
            if not isinstance(account_value, dict):
                continue
            if account_value.get("owner") != XDEX_MAINNET_OBSERVED_PROGRAM_ID:
                continue
            data_value = account_value.get("data")
            encoded = data_value[0] if isinstance(data_value, list) and data_value else None
            if not isinstance(encoded, str):
                continue
            decoded = base64.b64decode(encoded)
            if len(decoded) != POOL_SPACE:
                continue

            mint_0 = extract_pubkey_at(decoded, MINT_0_OFFSET)
            mint_1 = extract_pubkey_at(decoded, MINT_1_OFFSET)
            tx_hits = [
                row for row in tx_rows
                if account in row.get("message_accounts", [])
            ]
            pool_candidates.append({
                "pool_address": account,
                "mint_0": mint_0,
                "mint_1": mint_1,
                "contains_wrapped_xnt": WRAPPED_XNT_MINT in (mint_0, mint_1),
                "recent_signer_tx_hit_count": len(tx_hits),
                "recent_signer_slots": sorted({
                    row["slot"] for row in tx_hits if isinstance(row.get("slot"), int)
                }),
            })

        pool_candidates.sort(
            key=lambda row: (
                row["recent_signer_tx_hit_count"],
                row["contains_wrapped_xnt"],
            ),
            reverse=True,
        )

        evidence = {
            "schema": "x1_461_candidate_account_probe.v2",
            "chain": "x1",
            "address": ADDRESS,
            "exists": True,
            "owner": owner,
            "lamports": target_value.get("lamports"),
            "executable": target_value.get("executable"),
            "rent_epoch": target_value.get("rentEpoch"),
            "data_size_bytes": len(data),
            "recent_signature_count": len(signatures),
            "fetched_transaction_count": len(tx_rows),
            "successful_transaction_count": sum(row["succeeded"] for row in tx_rows),
            "xdex_invoked_count": sum(row["xdex_invoked"] for row in tx_rows),
            "instruction_name_counts": {},
            "unique_message_account_count": len(account_list),
            "xdex_pool_candidate_count": len(pool_candidates),
            "wrapped_xnt_pool_candidate_count": sum(
                row["contains_wrapped_xnt"] for row in pool_candidates
            ),
            "xdex_pool_candidates": pool_candidates,
            "recent_transactions": tx_rows,
            "account_role_verified": False,
            "liquidity_fact_time_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        counts = {}
        for row in tx_rows:
            for name in row["instruction_names"]:
                counts[name] = counts.get(name, 0) + 1
        evidence["instruction_name_counts"] = counts

        print("X1 #461 CANDIDATE ACCOUNT PROBE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertFalse(evidence["account_role_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])

if __name__ == "__main__":
    unittest.main()