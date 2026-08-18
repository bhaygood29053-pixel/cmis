import base64
import unittest

from liquidity_scout.providers.x1.candidate_pool_role import (
    encode_base58_pubkey,
    extract_pubkey_at,
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.pool_state_fingerprint import decode_base58_pubkey


PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
MINT_A = "So11111111111111111111111111111111111111112"
MINT_B = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
VAULT_A = "7khUrkZN7Y6VgoSR8pASMFjHcKwqdh2cd6NRctXyjSZC"
VAULT_B = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"
AUTHORITY = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"
OTHER_AUTHORITY = "11111111111111111111111111111111"


def _state_bytes():
    data = bytearray(637)
    data[72:104] = decode_base58_pubkey(VAULT_A)
    data[104:136] = decode_base58_pubkey(VAULT_B)
    data[168:200] = decode_base58_pubkey(MINT_A)
    data[200:232] = decode_base58_pubkey(MINT_B)
    return bytes(data)


def _requester(method, params, *, rpc_url):
    if method == "getAccountInfo":
        data = _state_bytes()
        return {
            "context": {"slot": 123},
            "value": {
                "owner": PROGRAM,
                "space": 637,
                "lamports": 1,
                "executable": False,
                "rentEpoch": 0,
                "data": [base64.b64encode(data).decode("ascii"), "base64"],
            },
        }
    if method == "getSignaturesForAddress":
        return []
    raise AssertionError(f"unexpected RPC method {method}")


def _token_fetcher(authority_for_b=AUTHORITY, mint_for_b=MINT_B):
    def fetch(account, *, rpc_url):
        if account == VAULT_A:
            return {
                "account_exists": True,
                "identity_verified": True,
                "mint": MINT_A,
                "token_authority": AUTHORITY,
                "program_owner": "TokenProgram",
                "parsed_type": "account",
            }
        if account == VAULT_B:
            return {
                "account_exists": True,
                "identity_verified": True,
                "mint": mint_for_b,
                "token_authority": authority_for_b,
                "program_owner": "TokenProgram",
                "parsed_type": "account",
            }
        raise AssertionError(f"unexpected vault {account}")

    return fetch


class CandidatePoolRoleTests(unittest.TestCase):
    def test_base58_roundtrip_for_pubkey_slots(self):
        raw = decode_base58_pubkey(MINT_B)
        self.assertEqual(encode_base58_pubkey(raw), MINT_B)
        data = bytearray(100)
        data[32:64] = raw
        self.assertEqual(extract_pubkey_at(bytes(data), 32), MINT_B)

    def test_structural_pool_role_verifies_with_aligned_vaults(self):
        report = verify_candidate_pool_role(
            account=POOL,
            target_mint=MINT_B,
            program_id=PROGRAM,
            requester=_requester,
            token_account_fetcher=_token_fetcher(),
            transaction_fetcher=lambda *args, **kwargs: None,
            signature_limit=1,
        )

        summary = report["summary"]
        self.assertTrue(summary["state_integrity_verified"])
        self.assertTrue(summary["program_owner_verified"])
        self.assertTrue(summary["account_space_verified"])
        self.assertTrue(summary["target_mint_present"])
        self.assertTrue(summary["both_vaults_verified"])
        self.assertTrue(summary["shared_vault_authority_verified"])
        self.assertTrue(summary["pool_state_structural_role_verified"])
        self.assertFalse(summary["recent_recognized_instruction_coupling_observed"])
        self.assertFalse(summary["global_onchain_pool_discovery_proven"])

    def test_wrong_vault_mint_fails_closed(self):
        report = verify_candidate_pool_role(
            account=POOL,
            target_mint=MINT_B,
            program_id=PROGRAM,
            requester=_requester,
            token_account_fetcher=_token_fetcher(mint_for_b=MINT_A),
            transaction_fetcher=lambda *args, **kwargs: None,
            signature_limit=1,
        )

        self.assertFalse(report["summary"]["both_vaults_verified"])
        self.assertFalse(
            report["summary"]["pool_state_structural_role_verified"]
        )

    def test_split_vault_authority_fails_closed(self):
        report = verify_candidate_pool_role(
            account=POOL,
            target_mint=MINT_B,
            program_id=PROGRAM,
            requester=_requester,
            token_account_fetcher=_token_fetcher(
                authority_for_b=OTHER_AUTHORITY
            ),
            transaction_fetcher=lambda *args, **kwargs: None,
            signature_limit=1,
        )

        self.assertTrue(report["summary"]["both_vaults_verified"])
        self.assertFalse(
            report["summary"]["shared_vault_authority_verified"]
        )
        self.assertFalse(
            report["summary"]["pool_state_structural_role_verified"]
        )


if __name__ == "__main__":
    unittest.main()
