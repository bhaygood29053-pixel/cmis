import base64
import unittest

from liquidity_scout.providers.x1.warp_onchain_inventory import WARP_PROGRAM_ID
from liquidity_scout.providers.x1.warp_rare_account_capture import (
    CONTRACT as RARE_CAPTURE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_semantic_layout_discovery import (
    ACCOUNT_LAYOUTS,
    CONTRACT,
    WarpSemanticLayoutError,
    anchor_account_discriminator,
    classify_rare_account,
    discover_warp_semantic_layout,
    find_program_address,
)


ZERO_PK = bytes(32)
MINT = bytes.fromhex("11" * 32)


def cap(chain, pubkey, space, raw):
    return {
        "contract": RARE_CAPTURE_CONTRACT,
        "chain": chain,
        "pubkey": pubkey,
        "program_id": WARP_PROGRAM_ID,
        "owner_verified": True,
        "data_length_verified": True,
        "non_executable_verified": True,
        "inventory_space": space,
        "data_base64": base64.b64encode(raw).decode("ascii"),
    }


def registry_raw():
    pubkey, bump = find_program_address([b"token_registry", MINT])
    raw = bytearray(anchor_account_discriminator("TokenRegistryEntry"))
    raw += MINT
    raw += bytes([6])
    raw += bytes([1])
    raw += b"USDC" + bytes(8)
    raw += bytes([0])
    raw += (10_000_000_000).to_bytes(8, "little")
    raw += (123_000_000).to_bytes(8, "little")
    raw += (1_700_000_000).to_bytes(8, "little", signed=True)
    raw += (10_000_000).to_bytes(8, "little")
    raw += (5_000_000_000).to_bytes(8, "little")
    raw += bytes([bump])
    raw += (1_000_000).to_bytes(8, "little")
    raw += (25).to_bytes(2, "little")
    raw += ZERO_PK
    raw += (0).to_bytes(8, "little")
    raw += (0).to_bytes(8, "little", signed=True)
    raw += bytes(16)
    assert len(raw) == 170
    return pubkey, bytes(raw)


def roles_raw():
    pubkey, bump = find_program_address([b"roles"])
    raw = bytearray(anchor_account_discriminator("Roles"))
    for value in (bytes.fromhex("22" * 32), bytes.fromhex("33" * 32), bytes.fromhex("44" * 32)):
        raw += bytes([1]) + value
    raw += bytes([bump])
    raw += bytes(128)
    assert len(raw) == 236
    return pubkey, bytes(raw)


def guardian_raw():
    pubkey, bump = find_program_address([b"guardian_set"])
    raw = bytearray(anchor_account_discriminator("GuardianSet"))
    raw += (3).to_bytes(4, "little")
    raw += bytes([7])
    raw += bytes([5])
    for index in range(9):
        raw += bytes([index + 1]) * 32
    raw += bytes([bump])
    raw += bytes(32)
    assert len(raw) == 335
    return pubkey, bytes(raw)


def config_raw(chain_id):
    pubkey, bump = find_program_address([b"config"])
    raw = bytearray(anchor_account_discriminator("Config"))
    raw += bytes.fromhex("55" * 32)
    raw += bytes([0])
    for index in range(5):
        raw += bytes([index + 10]) * 32
    raw += bytes([5])
    raw += bytes([3])
    raw += (100).to_bytes(8, "little")
    raw += (200).to_bytes(8, "little")
    raw += (5000).to_bytes(8, "little")
    raw += (25).to_bytes(2, "little")
    raw += bytes.fromhex("66" * 32)
    raw += bytes([bump])
    raw += (0).to_bytes(8, "little", signed=True)
    raw += ZERO_PK
    raw += bytes([0])  # PauseReason::None
    raw += bytes([chain_id])
    raw += bytes([1])
    raw += bytes(14)
    raw += bytes(321 - len(raw))
    assert len(raw) == 321
    return pubkey, bytes(raw)


class WarpSemanticLayoutDiscoveryTests(unittest.TestCase):
    def test_anchor_discriminators_match_live_families(self):
        expected = {
            "TokenRegistryEntry": "c5344915bfef2a86",
            "Roles": "b12511c9f29ed441",
            "Config": "9b0caae01efacc82",
            "GuardianSet": "784d4a622253607d",
        }
        for name, hex_value in expected.items():
            self.assertEqual(anchor_account_discriminator(name).hex(), hex_value)
            self.assertEqual(ACCOUNT_LAYOUTS[name]["discriminator_hex"], hex_value)

    def test_fixed_pda_derivations_match_live_singletons(self):
        self.assertEqual(
            find_program_address([b"config"]),
            ("48Po6qAHRJojbXH7KRqt6s5GfNfs9VEGccfqYEHmubEi", 255),
        )
        self.assertEqual(
            find_program_address([b"guardian_set"]),
            ("837ujVePfx3EB5CibC4FAAZJf5CTpiVXCE41BNBJoB3x", 253),
        )
        self.assertEqual(
            find_program_address([b"roles"]),
            ("HFWg6MpqBr446bGUqDxpr3sCQ5B92uCbTj7RUZa2aS6v", 255),
        )

    def test_token_registry_identity_requires_discriminator_size_and_pda(self):
        pubkey, raw = registry_raw()
        result = classify_rare_account(cap("solana", pubkey, 170, raw))
        self.assertEqual(result["account_name"], "TokenRegistryEntry")
        self.assertTrue(result["account_type_identity_verified"])
        self.assertTrue(result["pda_identity_verified"])
        self.assertEqual(result["decoded_fields"]["decimals"], 6)
        self.assertEqual(result["decoded_fields"]["symbol_candidate"], "USDC")
        self.assertFalse(result["field_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_roles_identity_and_bump(self):
        pubkey, raw = roles_raw()
        result = classify_rare_account(cap("x1", pubkey, 236, raw))
        self.assertEqual(result["account_name"], "Roles")
        self.assertTrue(result["pda_bump_verified"])
        self.assertFalse(result["account_role_verified"])

    def test_guardian_set_identity_and_cardinality(self):
        pubkey, raw = guardian_raw()
        result = classify_rare_account(cap("x1", pubkey, 335, raw))
        self.assertEqual(result["account_name"], "GuardianSet")
        self.assertEqual(result["decoded_fields"]["guardian_set_index_candidate"], 3)
        self.assertEqual(result["decoded_fields"]["num_guardians_candidate"], 7)
        self.assertEqual(result["decoded_fields"]["threshold_candidate"], 5)
        self.assertFalse(result["field_semantics_verified"])

    def test_config_identity_and_chain_candidate(self):
        pubkey, raw = config_raw(1)
        result = classify_rare_account(cap("x1", pubkey, 321, raw))
        self.assertEqual(result["account_name"], "Config")
        self.assertEqual(result["decoded_fields"]["chain_id_candidate"], 1)
        self.assertEqual(result["decoded_fields"]["threshold_candidate"], 3)
        self.assertFalse(result["semantic_contract_accepted"])

    def test_wrong_discriminator_fails_closed(self):
        pubkey, raw = registry_raw()
        damaged = bytes([raw[0] ^ 1]) + raw[1:]
        with self.assertRaisesRegex(WarpSemanticLayoutError, "discriminator"):
            classify_rare_account(cap("solana", pubkey, 170, damaged))

    def test_wrong_pda_fails_closed(self):
        _, raw = config_raw(0)
        with self.assertRaisesRegex(WarpSemanticLayoutError, "derived PDA"):
            classify_rare_account(
                cap("solana", "11111111111111111111111111111111", 321, raw)
            )

    def test_missing_raw_material_fails_closed(self):
        pubkey, raw = guardian_raw()
        capture = cap("solana", pubkey, 335, raw)
        capture["data_base64"] = None
        with self.assertRaisesRegex(WarpSemanticLayoutError, "data_base64"):
            classify_rare_account(capture)

    def test_discovery_requires_singletons_on_both_chains(self):
        registry_pubkey, registry = registry_raw()
        roles_pubkey, roles = roles_raw()
        guardian_pubkey, guardian = guardian_raw()
        config_pubkey, sol_config = config_raw(0)
        _, x1_config = config_raw(1)

        result = discover_warp_semantic_layout(
            {
                "contract": RARE_CAPTURE_CONTRACT,
                "solana_capture": {
                    "chain": "solana",
                    "captures": [
                        cap("solana", registry_pubkey, 170, registry),
                        cap("solana", roles_pubkey, 236, roles),
                        cap("solana", config_pubkey, 321, sol_config),
                        cap("solana", guardian_pubkey, 335, guardian),
                    ],
                },
                "x1_capture": {
                    "chain": "x1",
                    "captures": [
                        cap("x1", registry_pubkey, 170, registry),
                        cap("x1", roles_pubkey, 236, roles),
                        cap("x1", config_pubkey, 321, x1_config),
                        cap("x1", guardian_pubkey, 335, guardian),
                    ],
                },
            }
        )

        self.assertEqual(result["contract"], CONTRACT)
        self.assertTrue(result["account_type_identity_verified"])
        self.assertTrue(result["pda_identity_verified"])
        self.assertEqual(
            result["comparison"]["config_chain_id_candidates"],
            {"solana": 0, "x1": 1},
        )
        self.assertFalse(result["field_semantics_verified"])
        self.assertFalse(result["account_role_verified"])
        self.assertFalse(result["route_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
