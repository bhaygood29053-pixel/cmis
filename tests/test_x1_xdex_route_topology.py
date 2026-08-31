import base64
import json
import unittest
from decimal import Decimal
from pathlib import Path

from liquidity_scout.providers.x1.transaction_semantics import (
    TokenDelta,
    VerificationReport,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)
from liquidity_scout.providers.x1.xdex_route_topology import (
    TOPOLOGY_MULTI_POOL_CYCLIC,
    TOPOLOGY_UNKNOWN_MULTI_AMM,
    aggregate_xdex_route_topologies,
    characterize_xdex_route_topology,
    decode_swap_base_input_program_data,
)


TARGET_POOL = "GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x"
ASSET_MINT = "EFPkbXTdr3c7aRbCEKoJDYdbbzgzVDBShYGybP3gQwmy"
COUNTER_MINT = "So11111111111111111111111111111111111111112"
ASSET_VAULT = "ERCBkeo8uhWHp6rQ6hwz8Ges69wcJqKmW3siWgE4jXPh"
COUNTER_VAULT = "FESXWxjJhHVaGDXTA8n4xjDVSfvC6wxGT1BhBRKchYy7"
OWNER = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "x1_issue374_route_topology.json"
)
FIXTURES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

HOLDOUT_SIGNATURES = {
    "RDBLhJbVdM1RVhN1QgMahFvte41bbU7isLaYFMof3LUzapcbj12h1fSnoKnntUUZVNF7TwgFnTyyAoL6oBCVLXz",
    "4WvXzuEUfvhzFLKjhaGJMXEmszNAycaui7WAcwvUWqbq3NguDf3XuwKDA79fVyWdNZryE3c5gtThfGEuiNVxYVef",
    "2Fme6XWWsYtEyzWsfb66bhDj9vUZ5ARjUb9rHoGWrxVCGZ5YSWXadVKLZmQpuhMKGK9wSts8Z4nw6QRiBExZvyZ8",
    "2iTzopFmpEKesMMLJ5cENNbG3dCEKky4azDbvZ9zVcEVXLBRkrrUgiPRSKz87WnNuLED7pn1dVJ4oHBAAMWa8YJE",
}


def identity_resolver(pool_address, *, rpc_url):
    return {
        "chain": "x1",
        "pool_address": pool_address,
        "asset_mint": ASSET_MINT,
        "asset_vault": ASSET_VAULT,
        "counter_mint": COUNTER_MINT,
        "counter_vault": COUNTER_VAULT,
        "shared_owner": OWNER,
        "identity_verified": True,
    }


def token_delta(account, mint, raw, ui):
    return TokenDelta(
        account_index=1,
        account=account,
        owner=OWNER,
        mint=mint,
        decimals=9,
        pre_amount_raw=0,
        post_amount_raw=raw,
        delta_raw=raw,
        delta_ui=Decimal(ui),
        post_ui=Decimal(ui),
    )


def verifier_for(signature):
    fixture = FIXTURES[signature]

    def verify(transaction, *, signature, rpc_url):
        return VerificationReport(
            signature=signature,
            rpc_url=rpc_url,
            found=True,
            succeeded=True,
            slot=fixture["slot"],
            block_time=fixture["block_time"],
            block_time_iso=None,
            fee_lamports=1,
            primary_signer="Signer111",
            dex_protocol="XDEX",
            xdex_amm_invoked=True,
            xendex_amm_invoked=False,
            xendex_staking_invoked=False,
            program_ids=[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
            token_deltas=[
                token_delta(ASSET_VAULT, ASSET_MINT, -100, "-0.000000100"),
                token_delta(
                    COUNTER_VAULT,
                    COUNTER_MINT,
                    50,
                    "0.000000050",
                ),
            ],
            signer_token_deltas=[],
            signer_native_xnt_delta=None,
            signer_native_xnt_delta_before_fee=None,
            inferred_side="UNKNOWN",
            inferred_asset_mint=None,
            inferred_quote_mint=None,
            inferred_quote_amount=None,
            pool_leg_match=None,
            verification_basis="TRANSACTION_ONLY",
            inference_reason="issue374_fixture",
            expected_side=None,
            expected_mint=None,
            expectation_match=None,
            verification_level="ONCHAIN_CONFIRMED",
        )

    return verify


def transaction_for(signature, *, contaminate_vault=False):
    fixture = FIXTURES[signature]
    outer = []
    logs = []

    for index, (leg, payload) in enumerate(
        zip(fixture["legs"], fixture["program_data"])
    ):
        accounts = [
            leg["pool"],
            leg["input_mint"],
            leg["output_mint"],
            f"RouteAccount{index}",
        ]
        if leg["pool"] == TARGET_POOL:
            accounts.extend([ASSET_VAULT, COUNTER_VAULT])
        elif contaminate_vault and index == 0:
            accounts.append(ASSET_VAULT)

        outer.append({
            "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
            "accounts": accounts,
        })
        logs.extend([
            f"Program {XDEX_MAINNET_OBSERVED_PROGRAM_ID} invoke [1]",
            "Program log: Instruction: SwapBaseInput",
            f"Program data: {payload}",
            f"Program {XDEX_MAINNET_OBSERVED_PROGRAM_ID} success",
        ])

    return {
        "transaction": {
            "signatures": [signature],
            "message": {"instructions": outer},
        },
        "meta": {
            "innerInstructions": [],
            "logMessages": logs,
        },
    }


def membership_for(signature):
    target_index = len(FIXTURES[signature]["legs"]) - 1

    def prove(**kwargs):
        return {
            "transaction_pool_membership_verified": True,
            "recognized_amm_instruction_count": len(
                FIXTURES[signature]["legs"]
            ),
            "selected_pool_instruction_count": 1,
            "selected_pool_instruction_evidence": [{
                "group_index": None,
                "instruction_index": target_index,
                "program_id": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                "scope": "outer",
            }],
        }

    return prove


def run_fixture(
    signature,
    *,
    transaction=None,
    occurrence_collector=None,
    event_collector=None,
):
    tx = transaction or transaction_for(signature)

    def fetcher(requested_signature, *, rpc_url):
        if requested_signature != signature:
            raise AssertionError("unexpected fixture signature")
        return tx

    kwargs = {}
    if occurrence_collector is not None:
        kwargs["occurrence_collector"] = occurrence_collector
    if event_collector is not None:
        kwargs["event_collector"] = event_collector

    return characterize_xdex_route_topology(
        signature=signature,
        pool_address=TARGET_POOL,
        rpc_url="rpc",
        identity_resolver=identity_resolver,
        transaction_fetcher=fetcher,
        transaction_verifier=verifier_for(signature),
        membership_prover=membership_for(signature),
        **kwargs,
    )


class XdexRouteTopologyTests(unittest.TestCase):
    def test_development_set_excludes_holdout_signatures(self):
        self.assertEqual(len(FIXTURES), 8)
        self.assertTrue(HOLDOUT_SIGNATURES.isdisjoint(FIXTURES))

    def test_eight_issue363_rejections_are_verified_cyclic_routes(self):
        rows = []
        for signature, fixture in FIXTURES.items():
            with self.subTest(signature=signature):
                result = run_fixture(signature)
                rows.append(result)

                self.assertEqual(
                    result["execution_topology"],
                    TOPOLOGY_MULTI_POOL_CYCLIC,
                )
                self.assertTrue(result["route_topology_verified"])
                self.assertTrue(result["route_connected"])
                self.assertTrue(result["route_cyclic"])
                self.assertTrue(result["route_pool_addresses_unique"])
                self.assertTrue(result["target_pool_leg_verified"])
                self.assertEqual(result["target_pool_leg_count"], 1)
                self.assertTrue(
                    result["target_vault_delta_attribution_verified"]
                )
                self.assertTrue(result["exact_vault_deltas_verified"])
                self.assertTrue(
                    result["routed_target_leg_evidence_complete"]
                )
                self.assertEqual(result["order_origin"], "unknown")
                self.assertFalse(result["twap_execution_verified"])
                self.assertFalse(result["limit_order_execution_verified"])
                self.assertFalse(result["take_profit_execution_verified"])
                self.assertFalse(result["stop_loss_execution_verified"])
                self.assertFalse(result["classification_change_authorized"])
                self.assertTrue(
                    result["existing_fail_closed_block_should_remain"]
                )
                self.assertFalse(result["cmis_promotable"])
                self.assertFalse(result["execution_authorized"])

                decoded = [
                    {
                        "pool": leg["pool_address"],
                        "input_mint": leg["input_mint"],
                        "output_mint": leg["output_mint"],
                    }
                    for leg in result["route_legs"]
                ]
                self.assertEqual(decoded, fixture["legs"])

        aggregate = aggregate_xdex_route_topologies(rows)
        self.assertEqual(aggregate["status"], "verified")
        self.assertEqual(aggregate["signature_count"], 8)
        self.assertEqual(
            aggregate["topology_counts"],
            {TOPOLOGY_MULTI_POOL_CYCLIC: 8},
        )
        self.assertTrue(aggregate["all_route_topologies_verified"])
        self.assertTrue(aggregate["all_target_pool_legs_verified"])
        self.assertTrue(aggregate["all_target_vault_attribution_verified"])
        self.assertTrue(
            aggregate["all_routed_target_leg_evidence_complete"]
        )
        self.assertFalse(aggregate["classification_change_authorized"])
        self.assertFalse(aggregate["departure_pattern_verified"])

    def test_decoder_rejects_wrong_length_and_discriminator(self):
        good = next(iter(FIXTURES.values()))["program_data"][0]
        decoded = decode_swap_base_input_program_data(good)
        self.assertEqual(decoded["raw_length"], 153)
        self.assertEqual(
            decoded["event_discriminator_hex"],
            "40c6cde8260871e2",
        )

        with self.assertRaisesRegex(ValueError, "valid base64"):
            decode_swap_base_input_program_data("%%%")

        raw = base64.b64decode(good)
        with self.assertRaisesRegex(ValueError, "length"):
            decode_swap_base_input_program_data(
                base64.b64encode(raw[:-1]).decode()
            )

        tampered = bytes([raw[0] ^ 1]) + raw[1:]
        with self.assertRaisesRegex(ValueError, "discriminator"):
            decode_swap_base_input_program_data(
                base64.b64encode(tampered).decode()
            )

    def test_decoded_event_must_bind_to_instruction_accounts(self):
        signature = next(iter(FIXTURES))
        tx = transaction_for(signature)
        tx["transaction"]["message"]["instructions"][0]["accounts"][0] = (
            "WrongPool111"
        )
        with self.assertRaisesRegex(
            ValueError,
            "decoded XDEX pool is not bound",
        ):
            run_fixture(signature, transaction=tx)

    def test_disconnected_bound_route_remains_unknown(self):
        signature = next(iter(FIXTURES))
        tx = transaction_for(signature)
        fixture = FIXTURES[signature]
        expected = fixture["legs"]

        occurrences = []
        events = []
        for index, leg in enumerate(expected):
            row = {
                "program_id": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                "scope": "outer",
                "parent_outer_instruction_index": None,
                "source_group_position": None,
                "instruction_index": index,
                "accounts": [
                    leg["pool"],
                    leg["input_mint"],
                    leg["output_mint"],
                ],
            }
            if leg["pool"] == TARGET_POOL:
                row["accounts"].extend([ASSET_VAULT, COUNTER_VAULT])
            occurrences.append(row)
            events.append({
                "pool_address": leg["pool"],
                "input_mint": leg["input_mint"],
                "output_mint": leg["output_mint"],
                "event_discriminator_hex": "40c6cde8260871e2",
                "raw_length": 153,
            })

        broken_mint = "BrokenMint111"
        occurrences[0]["accounts"].append(broken_mint)
        events[0]["output_mint"] = broken_mint

        result = run_fixture(
            signature,
            transaction=tx,
            occurrence_collector=lambda transaction: occurrences,
            event_collector=lambda transaction: events,
        )
        self.assertEqual(
            result["execution_topology"],
            TOPOLOGY_UNKNOWN_MULTI_AMM,
        )
        self.assertFalse(result["route_topology_verified"])
        self.assertFalse(result["route_connected"])
        self.assertTrue(result["route_connectivity_breaks"])
        self.assertFalse(result["routed_target_leg_evidence_complete"])
        self.assertFalse(result["classification_change_authorized"])

    def test_additional_exact_vault_touch_blocks_target_attribution(self):
        signature = next(iter(FIXTURES))
        tx = transaction_for(signature, contaminate_vault=True)
        result = run_fixture(signature, transaction=tx)

        self.assertTrue(result["route_topology_verified"])
        self.assertTrue(result["target_pool_leg_verified"])
        self.assertFalse(
            result["target_vault_delta_attribution_verified"]
        )
        self.assertFalse(result["routed_target_leg_evidence_complete"])
        self.assertEqual(
            result["target_vault_delta_attribution"]["warning"],
            "additional_exact_vault_instruction_touch_ambiguity",
        )
        self.assertFalse(result["classification_change_authorized"])

    def test_missing_program_data_fails_closed(self):
        signature = next(iter(FIXTURES))
        tx = transaction_for(signature)
        logs = tx["meta"]["logMessages"]
        data_index = next(
            index
            for index, line in enumerate(logs)
            if line.startswith("Program data: ")
        )
        del logs[data_index]

        with self.assertRaisesRegex(
            ValueError,
            "Program-data event unavailable",
        ):
            run_fixture(signature, transaction=tx)


if __name__ == "__main__":
    unittest.main()
