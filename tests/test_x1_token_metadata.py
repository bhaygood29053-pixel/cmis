import base64
import unittest

from liquidity_scout.providers.x1.token_metadata import (
    METADATA_MINT_OFFSET,
    SOURCE,
    TOKEN_METADATA_EXPECTED_LOADER,
    TOKEN_METADATA_PROGRAM_ID,
    X1TokenMetadataProvider,
    get_token_metadata_for_mint,
    parse_metadata_accounts_result,
    parse_metadata_bytes,
    parse_token_metadata_program_account_result,
)


ZERO_PUBKEY = "11111111111111111111111111111111"


def borsh_string(value):
    raw = value.encode("utf-8")
    return len(raw).to_bytes(4, "little") + raw


def metadata_bytes(
    *,
    name="Example Token",
    symbol="EX",
    uri="https://example.invalid/token.json",
    is_mutable=True,
    token_standard=2,
):
    raw = bytearray()
    raw.append(4)  # MetadataV1 discriminator
    raw.extend(bytes(32))  # update authority
    raw.extend(bytes(32))  # mint
    raw.extend(borsh_string(name))
    raw.extend(borsh_string(symbol))
    raw.extend(borsh_string(uri))
    raw.extend((0).to_bytes(2, "little"))  # seller fee basis points
    raw.append(0)  # creators = None
    raw.append(0)  # primary_sale_happened = false
    raw.append(1 if is_mutable else 0)
    raw.append(0)  # edition_nonce = None
    if token_standard is None:
        raw.append(0)
    else:
        raw.extend((1, token_standard))
    return bytes(raw)


def metadata_rpc_row(raw=None, *, owner=TOKEN_METADATA_PROGRAM_ID, executable=False):
    payload = metadata_bytes() if raw is None else raw
    return {
        "pubkey": "MetadataAccount111",
        "account": {
            "owner": owner,
            "executable": executable,
            "lamports": 123,
            "data": [base64.b64encode(payload).decode("ascii"), "base64"],
        },
    }


def program_result(
    *,
    exists=True,
    executable=True,
    owner=TOKEN_METADATA_EXPECTED_LOADER,
    context_slot=12345,
):
    return {
        "context": {"slot": context_slot} if context_slot is not None else {},
        "value": (
            {
                "owner": owner,
                "executable": executable,
                "lamports": 1,
                "data": ["", "base64"],
            }
            if exists
            else None
        ),
    }


class X1TokenMetadataProviderTests(unittest.TestCase):
    def test_minimum_metadata_parser_preserves_descriptive_identity_boundaries(self):
        parsed = parse_metadata_bytes(
            metadata_bytes(),
            expected_mint=ZERO_PUBKEY,
        )

        self.assertEqual(parsed["key"], "MetadataV1")
        self.assertEqual(parsed["mint"], ZERO_PUBKEY)
        self.assertEqual(parsed["metadata_update_authority"], ZERO_PUBKEY)
        self.assertEqual(parsed["name"], "Example Token")
        self.assertEqual(parsed["symbol"], "EX")
        self.assertEqual(parsed["uri"], "https://example.invalid/token.json")
        self.assertTrue(parsed["is_mutable"])
        self.assertEqual(parsed["token_standard"], "Fungible")
        self.assertTrue(parsed["descriptive_identity_only"])
        self.assertFalse(parsed["spl_mint_authority_verified"])
        self.assertFalse(parsed["spl_freeze_authority_verified"])

    def test_metadata_parser_rejects_requested_mint_mismatch(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            parse_metadata_bytes(
                metadata_bytes(),
                expected_mint="DifferentMint111",
            )

    def test_metadata_parser_rejects_truncated_account(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            parse_metadata_bytes(metadata_bytes()[:70])

    def test_metadata_parser_rejects_wrong_account_discriminator(self):
        raw = bytearray(metadata_bytes())
        raw[0] = 1

        with self.assertRaisesRegex(ValueError, "MetadataV1"):
            parse_metadata_bytes(bytes(raw))

    def test_program_account_parser_preserves_loader_and_executable_evidence(self):
        parsed = parse_token_metadata_program_account_result(program_result())

        self.assertEqual(parsed["program_id"], TOKEN_METADATA_PROGRAM_ID)
        self.assertTrue(parsed["program_exists"])
        self.assertTrue(parsed["executable"])
        self.assertTrue(parsed["program_executable_verified"])
        self.assertEqual(
            parsed["loader_owner"],
            TOKEN_METADATA_EXPECTED_LOADER,
        )
        self.assertTrue(parsed["loader_owner_verified"])
        self.assertTrue(parsed["context_slot_verified"])
        self.assertEqual(parsed["context_slot"], 12345)
        self.assertEqual(parsed["source"], SOURCE)

    def test_program_account_parser_rejects_missing_context_slot(self):
        with self.assertRaisesRegex(ValueError, "context slot"):
            parse_token_metadata_program_account_result(
                program_result(context_slot=None)
            )

    def test_program_loader_mismatch_is_not_verified(self):
        parsed = parse_token_metadata_program_account_result(
            program_result(owner="WrongLoader111")
        )

        self.assertFalse(parsed["loader_owner_verified"])
        self.assertFalse(parsed["program_executable_verified"])

    def test_program_account_parser_preserves_missing_program_as_unverified(self):
        parsed = parse_token_metadata_program_account_result(
            program_result(exists=False)
        )

        self.assertFalse(parsed["program_exists"])
        self.assertFalse(parsed["program_executable_verified"])
        self.assertIsNone(parsed["loader_owner"])

    def test_exact_mint_metadata_result_requires_one_program_owned_account(self):
        result = {
            "context": {"slot": 54321},
            "value": [metadata_rpc_row()],
        }

        parsed = parse_metadata_accounts_result(
            result,
            mint=ZERO_PUBKEY,
        )

        self.assertTrue(parsed["metadata_found"])
        self.assertTrue(parsed["identity_verified"])
        self.assertEqual(parsed["metadata_account"], "MetadataAccount111")
        self.assertEqual(parsed["account_owner"], TOKEN_METADATA_PROGRAM_ID)
        self.assertEqual(parsed["context_slot"], 54321)
        self.assertEqual(parsed["mint"], ZERO_PUBKEY)
        self.assertEqual(parsed["symbol"], "EX")

    def test_missing_exact_mint_metadata_stays_unavailable(self):
        parsed = parse_metadata_accounts_result(
            {"context": {"slot": 1}, "value": []},
            mint=ZERO_PUBKEY,
        )

        self.assertFalse(parsed["metadata_found"])
        self.assertFalse(parsed["identity_verified"])
        self.assertIsNone(parsed["metadata_account"])
        self.assertEqual(parsed["mint"], ZERO_PUBKEY)

    def test_duplicate_exact_mint_metadata_fails_closed(self):
        result = {
            "context": {"slot": 2},
            "value": [
                metadata_rpc_row(),
                {**metadata_rpc_row(), "pubkey": "MetadataAccount222"},
            ]
        }

        with self.assertRaisesRegex(ValueError, "multiple"):
            parse_metadata_accounts_result(result, mint=ZERO_PUBKEY)

    def test_wrong_metadata_account_owner_fails_closed(self):
        result = {
            "context": {"slot": 3},
            "value": [metadata_rpc_row(owner="WrongProgram111")],
        }

        with self.assertRaisesRegex(ValueError, "owner"):
            parse_metadata_accounts_result(result, mint=ZERO_PUBKEY)

    def test_executable_metadata_state_account_fails_closed(self):
        result = {
            "context": {"slot": 4},
            "value": [metadata_rpc_row(executable=True)],
        }

        with self.assertRaisesRegex(ValueError, "executable"):
            parse_metadata_accounts_result(result, mint=ZERO_PUBKEY)

    def test_metadata_result_rejects_missing_context_slot(self):
        with self.assertRaisesRegex(ValueError, "context slot"):
            parse_metadata_accounts_result(
                {"context": {}, "value": [metadata_rpc_row()]},
                mint=ZERO_PUBKEY,
            )

    def test_provider_uses_exact_mint_filter_at_canonical_offset(self):
        calls = []

        def requester(method, params, **kwargs):
            calls.append((method, params, kwargs))
            if method == "getAccountInfo":
                return program_result()
            if method == "getProgramAccounts":
                return {
                    "context": {"slot": 20000},
                    "value": [metadata_rpc_row()],
                }
            raise AssertionError(f"unexpected method {method}")

        result = get_token_metadata_for_mint(
            ZERO_PUBKEY,
            rpc_url="https://rpc.example",
            requester=requester,
        )

        self.assertEqual(calls[0][0], "getAccountInfo")
        self.assertEqual(calls[0][1][0], TOKEN_METADATA_PROGRAM_ID)
        self.assertEqual(calls[1][0], "getProgramAccounts")
        self.assertEqual(calls[1][1][0], TOKEN_METADATA_PROGRAM_ID)

        config = calls[1][1][1]
        self.assertTrue(config["withContext"])
        self.assertEqual(
            config["filters"],
            [{
                "memcmp": {
                    "offset": METADATA_MINT_OFFSET,
                    "bytes": ZERO_PUBKEY,
                }
            }],
        )
        self.assertEqual(calls[1][2]["rpc_url"], "https://rpc.example")

        self.assertTrue(result["read_only"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["identity_verified"])
        self.assertEqual(result["metadata"]["mint"], ZERO_PUBKEY)

    def test_provider_refuses_metadata_lookup_when_program_is_non_executable(self):
        calls = []

        def requester(method, params, **kwargs):
            calls.append(method)
            return program_result(executable=False)

        with self.assertRaisesRegex(ValueError, "identity is not verified"):
            get_token_metadata_for_mint(
                ZERO_PUBKEY,
                requester=requester,
            )

        self.assertEqual(calls, ["getAccountInfo"])

    def test_provider_refuses_wrong_program_loader(self):
        calls = []

        def requester(method, params, **kwargs):
            calls.append(method)
            return program_result(owner="WrongLoader111")

        with self.assertRaisesRegex(ValueError, "identity is not verified"):
            get_token_metadata_for_mint(
                ZERO_PUBKEY,
                requester=requester,
            )

        self.assertEqual(calls, ["getAccountInfo"])

    def test_provider_facade_is_read_only_and_chain_specific(self):
        def requester(method, params, **kwargs):
            if method == "getAccountInfo":
                return program_result()
            return {
                "context": {"slot": 9},
                "value": [metadata_rpc_row()],
            }

        provider = X1TokenMetadataProvider(
            rpc_url="https://rpc.example",
            requester=requester,
        )

        self.assertEqual(provider.chain, "x1")
        self.assertEqual(provider.source, SOURCE)
        self.assertEqual(provider.program_id, TOKEN_METADATA_PROGRAM_ID)

        result = provider.get_metadata(ZERO_PUBKEY)
        self.assertTrue(result["identity_verified"])


if __name__ == "__main__":
    unittest.main()
