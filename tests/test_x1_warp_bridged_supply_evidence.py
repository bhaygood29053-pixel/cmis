import unittest

from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    USDC_ROUTE_ID,
    USDC_SOURCE_MINT,
    USDC_X_DESTINATION_MINT,
    WSOL_ROUTE_ID,
    WSOL_SOURCE_MINT,
    WSOL_X_DESTINATION_MINT,
    WarpBridgedSupplyEvidenceError,
    build_warp_bridged_supply_evidence,
    derive_mint_authority_pda,
    derive_vault_pda,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTICS_CONTRACT,
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
    WARP_PROGRAM_ID,
)


def route():
    return {
        "contract": WARP_CONFIG_SEMANTICS_CONTRACT,
        "semantic_contract_id": WARP_CONFIG_SEMANTIC_CONTRACT_ID,
        "program_id": WARP_PROGRAM_ID,
        "route_id": WSOL_ROUTE_ID,
        "source": {
            "chain": "solana",
            "asset_id": WSOL_SOURCE_MINT,
            "asset_id_kind": "mint",
        },
        "destination": {
            "chain": "x1",
            "asset_id": WSOL_X_DESTINATION_MINT,
            "asset_id_kind": "mint",
        },
        "source_is_native": True,
        "destination_is_native": False,
        "route_decimals": 9,
    }


def source_observation(*, amount=1234567890, observed_at=1000.0, decimals=9):
    vault = derive_vault_pda(WSOL_SOURCE_MINT)
    return {
        "chain": "solana",
        "source_mint": WSOL_SOURCE_MINT,
        "vault_pda": vault["address"],
        "vault_bump": vault["bump"],
        "vault_token_account": "VaultToken111111111111111111111111111111111",
        "token_account_program_owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "token_account_mint": WSOL_SOURCE_MINT,
        "token_account_authority": vault["address"],
        "amount_raw": amount,
        "decimals": decimals,
        "observation_slot": 10,
        "observed_at": observed_at,
        "identity_verified": True,
    }


def destination_observation(*, amount=1234567890, observed_at=1005.0, decimals=9):
    authority = derive_mint_authority_pda(WSOL_X_DESTINATION_MINT)
    return {
        "chain": "x1",
        "destination_mint": WSOL_X_DESTINATION_MINT,
        "mint_program_owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "mint_authority": authority["address"],
        "expected_warp_mint_authority": authority["address"],
        "mint_authority_bump": authority["bump"],
        "raw_supply": amount,
        "decimals": decimals,
        "mint_observation_slot": 20,
        "mint_observed_at": observed_at - 1,
        "supply_observation_slot": 21,
        "supply_observed_at": observed_at,
        "authority_verified": True,
        "supply_crosscheck_verified": True,
    }


class WarpBridgedSupplyEvidenceTests(unittest.TestCase):
    def test_equal_exact_vault_and_wrapped_supply_promotes_bounded_supply_evidence(self):
        result = build_warp_bridged_supply_evidence(
            route_observation=route(),
            source_vault=source_observation(),
            destination_mint=destination_observation(),
            evaluated_at=1010.0,
        )
        self.assertTrue(result["source"]["identity_verified"])
        self.assertTrue(result["destination"]["identity_verified"])
        self.assertTrue(result["decimals_verified"])
        self.assertTrue(result["observation_time_compatible"])
        self.assertTrue(result["source_vault_balance_equals_destination_supply"])
        self.assertTrue(result["current_backing_closure_verified"])
        self.assertTrue(result["bridged_supply_verified"])
        self.assertEqual(result["amount_raw"], 1234567890)
        self.assertEqual(result["amount"], "1.23456789")
        self.assertTrue(result["supply_evidence"]["verified"])
        self.assertTrue(result["supply_evidence"]["semantic_contract_accepted"])
        self.assertFalse(result["provider_tvl_label_promoted"])
        self.assertFalse(result["third_party_idl_semantics_promoted"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_balance_mismatch_stays_unverified(self):
        result = build_warp_bridged_supply_evidence(
            route_observation=route(),
            source_vault=source_observation(amount=10),
            destination_mint=destination_observation(amount=11),
            evaluated_at=1010.0,
        )
        self.assertFalse(result["source_vault_balance_equals_destination_supply"])
        self.assertFalse(result["bridged_supply_verified"])
        self.assertIsNone(result["supply_evidence"])
        self.assertIsNone(result["amount_raw"])

    def test_wrong_mint_authority_stays_unverified(self):
        dest = destination_observation()
        dest["mint_authority"] = "WrongAuthority111111111111111111111111111111"
        dest["authority_verified"] = False
        result = build_warp_bridged_supply_evidence(
            route_observation=route(),
            source_vault=source_observation(),
            destination_mint=dest,
            evaluated_at=1010.0,
        )
        self.assertFalse(result["destination"]["identity_verified"])
        self.assertFalse(result["bridged_supply_verified"])

    def test_source_vault_identity_mismatch_stays_unverified(self):
        source = source_observation()
        source["token_account_authority"] = "WrongVault1111111111111111111111111111111111"
        source["identity_verified"] = False
        result = build_warp_bridged_supply_evidence(
            route_observation=route(),
            source_vault=source,
            destination_mint=destination_observation(),
            evaluated_at=1010.0,
        )
        self.assertFalse(result["source"]["identity_verified"])
        self.assertFalse(result["bridged_supply_verified"])

    def test_decimal_mismatch_stays_unverified(self):
        result = build_warp_bridged_supply_evidence(
            route_observation=route(),
            source_vault=source_observation(decimals=9),
            destination_mint=destination_observation(decimals=8),
            evaluated_at=1010.0,
        )
        self.assertFalse(result["decimals_verified"])
        self.assertFalse(result["bridged_supply_verified"])

    def test_observation_skew_stays_unverified(self):
        result = build_warp_bridged_supply_evidence(
            route_observation=route(),
            source_vault=source_observation(observed_at=1000.0),
            destination_mint=destination_observation(observed_at=1201.0),
            evaluated_at=1300.0,
            max_observation_skew_seconds=120.0,
        )
        self.assertFalse(result["observation_time_compatible"])
        self.assertFalse(result["bridged_supply_verified"])

    def test_non_native_source_is_rejected(self):
        r = route()
        r["source_is_native"] = False
        with self.assertRaises(WarpBridgedSupplyEvidenceError):
            build_warp_bridged_supply_evidence(
                route_observation=r,
                source_vault=source_observation(),
                destination_mint=destination_observation(),
                evaluated_at=1010.0,
            )


    def test_usdc_to_usdcx_route_uses_same_exact_backing_closure_contract(self):
        source_vault = derive_vault_pda(USDC_SOURCE_MINT)
        mint_authority = derive_mint_authority_pda(USDC_X_DESTINATION_MINT)
        route_observation = {
            "contract": WARP_CONFIG_SEMANTICS_CONTRACT,
            "semantic_contract_id": WARP_CONFIG_SEMANTIC_CONTRACT_ID,
            "program_id": WARP_PROGRAM_ID,
            "route_id": USDC_ROUTE_ID,
            "source": {
                "chain": "solana",
                "asset_id": USDC_SOURCE_MINT,
                "asset_id_kind": "mint",
            },
            "destination": {
                "chain": "x1",
                "asset_id": USDC_X_DESTINATION_MINT,
                "asset_id_kind": "mint",
            },
            "source_is_native": True,
            "destination_is_native": False,
            "route_decimals": 6,
        }
        source = {
            "chain": "solana",
            "source_mint": USDC_SOURCE_MINT,
            "vault_pda": source_vault["address"],
            "vault_bump": source_vault["bump"],
            "vault_token_account": "UsdcVaultToken111111111111111111111111111111",
            "token_account_program_owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "token_account_mint": USDC_SOURCE_MINT,
            "token_account_authority": source_vault["address"],
            "amount_raw": 24007049,
            "decimals": 6,
            "observation_slot": 10,
            "observed_at": 1000.0,
            "identity_verified": True,
        }
        destination = {
            "chain": "x1",
            "destination_mint": USDC_X_DESTINATION_MINT,
            "mint_program_owner": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
            "mint_authority": mint_authority["address"],
            "expected_warp_mint_authority": mint_authority["address"],
            "mint_authority_bump": mint_authority["bump"],
            "raw_supply": 24007049,
            "decimals": 6,
            "mint_observation_slot": 20,
            "mint_observed_at": 1004.0,
            "supply_observation_slot": 21,
            "supply_observed_at": 1005.0,
            "authority_verified": True,
            "supply_crosscheck_verified": True,
        }
        result = build_warp_bridged_supply_evidence(
            route_observation=route_observation,
            source_vault=source,
            destination_mint=destination,
            evaluated_at=1010.0,
        )
        self.assertTrue(result["current_backing_closure_verified"])
        self.assertTrue(result["bridged_supply_verified"])
        self.assertEqual(result["amount_raw"], 24007049)
        self.assertEqual(result["amount"], "24.007049")
        self.assertFalse(result["execution_authorized"])

    def test_pda_derivations_are_deterministic_and_distinct(self):
        vault_a = derive_vault_pda(WSOL_SOURCE_MINT)
        vault_b = derive_vault_pda(WSOL_SOURCE_MINT)
        authority = derive_mint_authority_pda(WSOL_X_DESTINATION_MINT)
        self.assertEqual(vault_a, vault_b)
        self.assertNotEqual(vault_a["address"], authority["address"])


if __name__ == "__main__":
    unittest.main()
