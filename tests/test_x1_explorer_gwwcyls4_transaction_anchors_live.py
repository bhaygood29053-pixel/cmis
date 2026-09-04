import json
import os
import unittest
from decimal import Decimal
from pathlib import Path

from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.transaction_semantics import (
    account_key_info,
    compute_token_deltas,
    fetch_transaction,
    verify_transaction,
)


RUN_LIVE = os.getenv("RUN_X1_EXPLORER_GWWCYLS4_ANCHORS_LIVE") == "1"
FIXTURE = Path(__file__).parent / "fixtures" / "gwwcyls4_explorer_page1_20260904.json"
POOL_SPACE = 637
VAULT_0_OFFSET = 72
VAULT_1_OFFSET = 104
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200
LAMPORTS_PER_XNT = Decimal("1000000000")


def _text(value):
    text = str(value or "").strip()
    return text or None


def _balance_at(tx, *, account, mint):
    keys, _signers = account_key_info(tx)
    try:
        index = keys.index(account)
    except ValueError:
        return {
            "account": account,
            "mint": mint,
            "account_index": None,
            "pre_raw": None,
            "post_raw": None,
            "delta_raw": None,
            "decimals": None,
            "pre_ui": None,
            "post_ui": None,
            "delta_ui": None,
            "balance_metadata_present": False,
        }

    meta = tx.get("meta") or {}
    pre = None
    post = None
    for item in meta.get("preTokenBalances") or []:
        if (
            isinstance(item, dict)
            and item.get("accountIndex") == index
            and _text(item.get("mint")) == mint
        ):
            pre = item
            break
    for item in meta.get("postTokenBalances") or []:
        if (
            isinstance(item, dict)
            and item.get("accountIndex") == index
            and _text(item.get("mint")) == mint
        ):
            post = item
            break

    def amount(item):
        ui = (item or {}).get("uiTokenAmount") or {}
        raw = ui.get("amount")
        decimals = ui.get("decimals")
        if raw is None or decimals is None:
            return None, None
        return int(raw), int(decimals)

    pre_raw, pre_decimals = amount(pre)
    post_raw, post_decimals = amount(post)
    decimals = post_decimals if post_decimals is not None else pre_decimals
    if decimals is None or pre_raw is None or post_raw is None:
        return {
            "account": account,
            "mint": mint,
            "account_index": index,
            "pre_raw": pre_raw,
            "post_raw": post_raw,
            "delta_raw": None,
            "decimals": decimals,
            "pre_ui": None,
            "post_ui": None,
            "delta_ui": None,
            "balance_metadata_present": False,
        }

    scale = Decimal(10) ** decimals
    delta_raw = post_raw - pre_raw
    return {
        "account": account,
        "mint": mint,
        "account_index": index,
        "pre_raw": pre_raw,
        "post_raw": post_raw,
        "delta_raw": delta_raw,
        "decimals": decimals,
        "pre_ui": format(Decimal(pre_raw) / scale, "f"),
        "post_ui": format(Decimal(post_raw) / scale, "f"),
        "delta_ui": format(Decimal(delta_raw) / scale, "f"),
        "balance_metadata_present": True,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_EXPLORER_GWWCYLS4_ANCHORS_LIVE=1 for fixed Explorer transaction evidence",
)
class X1ExplorerGwwCyLS4AnchorsLiveTests(unittest.TestCase):
    def test_user_exported_signatures_reconstruct_exact_pool_vault_deltas(self):
        fixture = json.loads(FIXTURE.read_text())
        pool = fixture["pool_address"]
        rows = fixture["rows"]
        self.assertEqual(len(rows), 10)

        state = fetch_account_state(pool)
        data = state.get("data")
        self.assertIsInstance(data, bytes)
        self.assertEqual(len(data), POOL_SPACE)
        vault_0 = extract_pubkey_at(data, VAULT_0_OFFSET)
        vault_1 = extract_pubkey_at(data, VAULT_1_OFFSET)
        mint_0 = extract_pubkey_at(data, MINT_0_OFFSET)
        mint_1 = extract_pubkey_at(data, MINT_1_OFFSET)

        evidence_rows = []
        for anchor in rows:
            signature = anchor["signature"]
            tx = fetch_transaction(signature)
            self.assertIsInstance(tx, dict, f"transaction unavailable: {signature}")
            report = verify_transaction(
                tx,
                signature=signature,
                rpc_url="https://rpc.mainnet.x1.xyz",
            )
            self.assertTrue(report.found)
            self.assertTrue(report.succeeded)
            self.assertEqual(report.slot, anchor["slot"])

            account_keys, _signers = account_key_info(tx)
            pool_in_message_accounts = pool in account_keys
            vault_0_state = _balance_at(tx, account=vault_0, mint=mint_0)
            vault_1_state = _balance_at(tx, account=vault_1, mint=mint_1)
            vault_0_delta = vault_0_state.get("delta_raw")
            vault_1_delta = vault_1_state.get("delta_raw")
            both_vaults_changed = bool(
                isinstance(vault_0_delta, int)
                and isinstance(vault_1_delta, int)
                and vault_0_delta != 0
                and vault_1_delta != 0
            )
            opposite_sign_vault_deltas = bool(
                both_vaults_changed
                and ((vault_0_delta > 0) != (vault_1_delta > 0))
            )

            explorer_amount_lamports = (
                Decimal(anchor["amount_xnt"]) * LAMPORTS_PER_XNT
            )
            explorer_amount_equals_exported_fee = (
                explorer_amount_lamports == Decimal(anchor["fee_lamports"])
            )
            rpc_fee_matches_export = (
                report.fee_lamports == anchor["fee_lamports"]
            )

            token_deltas = [
                delta.to_jsonable()
                for delta in compute_token_deltas(tx)
            ]
            evidence_rows.append({
                "signature": signature,
                "explorer_slot": anchor["slot"],
                "rpc_slot": report.slot,
                "block_time": report.block_time,
                "block_time_iso": report.block_time_iso,
                "explorer_type": anchor["type"],
                "explorer_amount_xnt": anchor["amount_xnt"],
                "explorer_fee_lamports": anchor["fee_lamports"],
                "rpc_fee_lamports": report.fee_lamports,
                "explorer_amount_equals_exported_fee": explorer_amount_equals_exported_fee,
                "rpc_fee_matches_export": rpc_fee_matches_export,
                "pool_in_message_accounts": pool_in_message_accounts,
                "xdex_amm_invoked": report.xdex_amm_invoked,
                "dex_protocol": report.dex_protocol,
                "vault_0": vault_0_state,
                "vault_1": vault_1_state,
                "both_pool_vaults_changed": both_vaults_changed,
                "opposite_sign_pool_vault_deltas": opposite_sign_vault_deltas,
                "token_deltas": token_deltas,
            })

        chronological = sorted(evidence_rows, key=lambda row: row["rpc_slot"])
        continuity = []
        for left, right in zip(chronological, chronological[1:]):
            checks = {}
            for side in ("vault_0", "vault_1"):
                left_post = left[side].get("post_raw")
                right_pre = right[side].get("pre_raw")
                checks[side] = bool(
                    left_post is not None
                    and right_pre is not None
                    and left_post == right_pre
                )
            continuity.append({
                "from_signature": left["signature"],
                "to_signature": right["signature"],
                "from_slot": left["rpc_slot"],
                "to_slot": right["rpc_slot"],
                "vault_0_contiguous": checks["vault_0"],
                "vault_1_contiguous": checks["vault_1"],
                "both_vaults_contiguous": checks["vault_0"] and checks["vault_1"],
            })

        evidence = {
            "schema": "x1_explorer_gwwcyls4_transaction_anchor_evidence.v1",
            "chain": "x1",
            "pool_address": pool,
            "pool_state_slot_at_evaluation": state.get("context_slot"),
            "pool_owner": state.get("owner"),
            "vault_0": vault_0,
            "vault_1": vault_1,
            "mint_0": mint_0,
            "mint_1": mint_1,
            "anchor_count": len(evidence_rows),
            "all_slots_match_export": all(
                row["rpc_slot"] == row["explorer_slot"] for row in evidence_rows
            ),
            "all_rpc_fees_match_export": all(
                row["rpc_fee_matches_export"] for row in evidence_rows
            ),
            "explorer_amount_equals_fee_count": sum(
                row["explorer_amount_equals_exported_fee"] for row in evidence_rows
            ),
            "xdex_invoked_count": sum(row["xdex_amm_invoked"] for row in evidence_rows),
            "pool_message_account_count": sum(
                row["pool_in_message_accounts"] for row in evidence_rows
            ),
            "both_vaults_changed_count": sum(
                row["both_pool_vaults_changed"] for row in evidence_rows
            ),
            "opposite_sign_vault_delta_count": sum(
                row["opposite_sign_pool_vault_deltas"] for row in evidence_rows
            ),
            "continuity_pairs": continuity,
            "fully_contiguous_pair_count": sum(
                row["both_vaults_contiguous"] for row in continuity
            ),
            "transactions": evidence_rows,
            "explorer_amount_semantics_verified_as_pool_flow": False,
            "transaction_vault_delta_evidence_verified": True,
            "liquidity_fact_time_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 GWWCYLS4 EXPLORER TRANSACTION ANCHOR EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertTrue(evidence["all_slots_match_export"])
        self.assertTrue(evidence["all_rpc_fees_match_export"])
        self.assertFalse(evidence["explorer_amount_semantics_verified_as_pool_flow"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
