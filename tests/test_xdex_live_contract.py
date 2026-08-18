import json
import os
import time
import unittest
from collections.abc import Mapping

from liquidity_scout.providers.x1 import XDEXReadOnlyProvider
from liquidity_scout.providers.x1.candidate_pool_role import verify_candidate_pool_role


RUN_LIVE = os.getenv("RUN_XDEX_LIVE_TESTS") == "1"
REQUIRE_LIVE_PAIR = os.getenv("XDEX_LIVE_REQUIRE_QUOTE_PAIR") == "1"
_NATIVE_XNT_SYMBOLS = {"XNT", "WXNT"}
_NATIVE_XNT_MINTS = {"So11111111111111111111111111111111111111112"}

# Pinned, previously accepted CMIS XDEX structural-evidence anchor. The live
# probe re-verifies this exact pool on-chain every run before trusting the
# catalog's API-side token identifiers. These constants are evidence scope, not
# a claim that this is the only XDEX program or pool on X1.
_XDEX_PROGRAM_ID = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
_XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
_XENCAT_POOL_ADDRESS = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"

_REDACTED_KEY_FRAGMENTS = (
    "transaction",
    "serialized",
    "signature",
    "secret",
    "private",
    "keypair",
    "wallet",
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _token_address(token):
    """Return the pool token's public API address, preferring address over mint."""
    if not isinstance(token, Mapping):
        return None
    return _text(token.get("address") or token.get("mint"))


def _token_mint(token):
    """Return the token's on-chain mint metadata when the catalog supplies it."""
    if not isinstance(token, Mapping):
        return None
    return _text(token.get("mint") or token.get("address"))


def _is_native_xnt_side(token):
    if not isinstance(token, Mapping):
        return False
    symbol = (_text(token.get("symbol")) or "").upper()
    name = (_text(token.get("name")) or "").casefold()
    address = _token_address(token)
    mint = _token_mint(token)
    return (
        symbol in _NATIVE_XNT_SYMBOLS
        or "wrapped xnt" in name
        or address in _NATIVE_XNT_MINTS
        or mint in _NATIVE_XNT_MINTS
    )


def select_non_native_live_pool_pair(pools):
    """Select one exact catalog pool without using XNT/WXNT as either side."""

    for pool in pools:
        if not isinstance(pool, Mapping):
            continue
        base = pool.get("baseToken")
        quote = pool.get("quoteToken")
        if not isinstance(base, Mapping) or not isinstance(quote, Mapping):
            continue
        if _is_native_xnt_side(base) or _is_native_xnt_side(quote):
            continue

        base_address = _token_address(base)
        quote_address = _token_address(quote)
        if not base_address or not quote_address or base_address == quote_address:
            continue

        return {
            "pool_address": _text(pool.get("address")),
            "base_address": base_address,
            "quote_address": quote_address,
            "base_symbol": _text(base.get("symbol")),
            "quote_symbol": _text(quote.get("symbol")),
        }
    return None


def select_catalog_pair_for_verified_pool(
    catalog_pools,
    structural_report,
    *,
    target_mint,
    expected_pool_address,
):
    """Resolve API identifiers only after the exact pool role re-verifies on-chain.

    This is intentionally a two-source join: the chain report proves the exact
    pool's program/size/mint/vault structure; the XDEX catalog contributes only
    the API-side identifiers used for a read-only quote request.
    """

    if not isinstance(structural_report, Mapping):
        return None
    if structural_report.get("summary", {}).get(
        "pool_state_structural_role_verified"
    ) is not True:
        return None

    report_address = _text(structural_report.get("account"))
    expected_pool_address = _text(expected_pool_address)
    target_mint = _text(target_mint)
    if (
        not report_address
        or report_address != expected_pool_address
        or not target_mint
    ):
        return None

    decoded = structural_report.get("decoded_state")
    decoded = decoded if isinstance(decoded, Mapping) else {}
    mint_0 = _text(decoded.get("mint_0"))
    mint_1 = _text(decoded.get("mint_1"))
    if target_mint not in {mint_0, mint_1}:
        return None
    counter_mint = mint_1 if mint_0 == target_mint else mint_0
    if not counter_mint:
        return None

    for pool in catalog_pools:
        if not isinstance(pool, Mapping):
            continue
        if _text(pool.get("address")) != expected_pool_address:
            continue
        base = pool.get("baseToken")
        quote = pool.get("quoteToken")
        if not isinstance(base, Mapping) or not isinstance(quote, Mapping):
            continue

        base_mint = _token_mint(base)
        quote_mint = _token_mint(quote)
        if base_mint == target_mint:
            target_token, counter_token = base, quote
        elif quote_mint == target_mint:
            target_token, counter_token = quote, base
        else:
            continue

        # If the chain says the counter leg is native/wrapped XNT, require the
        # catalog to label that same leg as XNT. This does not promote the
        # catalog's address as canonical; it merely permits transport probing.
        if counter_mint in _NATIVE_XNT_MINTS and not _is_native_xnt_side(counter_token):
            continue

        target_api_address = _token_address(target_token)
        counter_api_address = _token_address(counter_token)
        if (
            not target_api_address
            or not counter_api_address
            or target_api_address == counter_api_address
        ):
            continue

        return {
            "pool_address": expected_pool_address,
            "base_address": target_api_address,
            "quote_address": counter_api_address,
            "base_symbol": _text(target_token.get("symbol")),
            "quote_symbol": _text(counter_token.get("symbol")),
            "target_mint": target_mint,
            "onchain_counter_mint": counter_mint,
            "counter_catalog_mint": _token_mint(counter_token),
            "counter_catalog_address": _text(counter_token.get("address")),
        }
    return None


def _public_evidence(value, *, depth=0):
    """Return bounded public quote evidence while stripping transaction-like fields."""

    if depth > 6:
        return "<depth-limit>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.casefold()
            if any(fragment in lowered for fragment in _REDACTED_KEY_FRAGMENTS):
                cleaned[key_text] = "<redacted-non-analysis-field>"
                continue
            cleaned[key_text] = _public_evidence(item, depth=depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_public_evidence(item, depth=depth + 1) for item in value[:25]]
    return f"<{type(value).__name__}>"


class XDEXLivePairSelectionTests(unittest.TestCase):
    def test_selects_exact_non_native_pool_pair(self):
        pools = [
            {
                "address": "P_XNT",
                "baseToken": {"symbol": "AGI", "mint": "AGI_MINT"},
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "mint": "XNT_ID",
                },
            },
            {
                "address": "P_USDC_AGI",
                "baseToken": {"symbol": "USDC", "mint": "USDC_MINT"},
                "quoteToken": {"symbol": "AGI", "mint": "AGI_MINT"},
            },
        ]

        pair = select_non_native_live_pool_pair(pools)

        self.assertEqual(
            pair,
            {
                "pool_address": "P_USDC_AGI",
                "base_address": "USDC_MINT",
                "quote_address": "AGI_MINT",
                "base_symbol": "USDC",
                "quote_symbol": "AGI",
            },
        )

    def test_prefers_explicit_public_address_over_mint_metadata(self):
        pools = [
            {
                "address": "P_ADDRESS_FIRST",
                "baseToken": {
                    "symbol": "AAA",
                    "address": "AAA_PUBLIC_ADDRESS",
                    "mint": "AAA_MINT_METADATA",
                },
                "quoteToken": {
                    "symbol": "BBB",
                    "address": "BBB_PUBLIC_ADDRESS",
                    "mint": "BBB_MINT_METADATA",
                },
            }
        ]

        pair = select_non_native_live_pool_pair(pools)

        self.assertEqual(pair["base_address"], "AAA_PUBLIC_ADDRESS")
        self.assertEqual(pair["quote_address"], "BBB_PUBLIC_ADDRESS")

    def test_returns_none_when_only_xnt_pairs_exist(self):
        pools = [
            {
                "address": "P_ONLY",
                "baseToken": {"symbol": "USDC", "mint": "USDC_MINT"},
                "quoteToken": {"symbol": "XNT", "mint": "XNT_ID"},
            }
        ]

        self.assertIsNone(select_non_native_live_pool_pair(pools))

    def test_verified_pool_join_uses_catalog_transport_identity_only_after_chain_proof(self):
        structural = {
            "account": _XENCAT_POOL_ADDRESS,
            "decoded_state": {
                "mint_0": _XENCAT_MINT,
                "mint_1": next(iter(_NATIVE_XNT_MINTS)),
            },
            "summary": {"pool_state_structural_role_verified": True},
        }
        catalog = [
            {
                "address": _XENCAT_POOL_ADDRESS,
                "baseToken": {"symbol": "XENCAT", "mint": _XENCAT_MINT},
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "address": "XNT_API_ID",
                    "mint": next(iter(_NATIVE_XNT_MINTS)),
                },
            }
        ]

        pair = select_catalog_pair_for_verified_pool(
            catalog,
            structural,
            target_mint=_XENCAT_MINT,
            expected_pool_address=_XENCAT_POOL_ADDRESS,
        )

        self.assertEqual(pair["base_address"], _XENCAT_MINT)
        self.assertEqual(pair["quote_address"], "XNT_API_ID")
        self.assertEqual(pair["onchain_counter_mint"], next(iter(_NATIVE_XNT_MINTS)))

        structural["summary"]["pool_state_structural_role_verified"] = False
        self.assertIsNone(
            select_catalog_pair_for_verified_pool(
                catalog,
                structural,
                target_mint=_XENCAT_MINT,
                expected_pool_address=_XENCAT_POOL_ADDRESS,
            )
        )


@unittest.skipUnless(
    RUN_LIVE,
    "Set RUN_XDEX_LIVE_TESTS=1 to probe the live read-only XDEX contract.",
)
class XDEXLiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        discovery_provider = XDEXReadOnlyProvider(timeout=20)
        try:
            pools = discovery_provider.pool_list()
        except Exception as exc:
            if REQUIRE_LIVE_PAIR:
                raise RuntimeError(
                    f"Cannot load the public XDEX pool list for required contract probing: {exc}"
                ) from exc
            raise unittest.SkipTest(
                f"Cannot load the public XDEX pool list for contract probing: {exc}"
            ) from exc

        # Keep the former non-native route if XDEX ever exposes one. Otherwise
        # re-verify the pinned XENCAT pool directly against the accepted XDEX
        # structural contract and use the catalog only for API transport IDs.
        cls.live_pair = select_non_native_live_pool_pair(pools)
        cls.live_pair_source = "xdex_public_pool_list_non_native"

        if cls.live_pair is None:
            try:
                structural_report = verify_candidate_pool_role(
                    account=_XENCAT_POOL_ADDRESS,
                    target_mint=_XENCAT_MINT,
                    program_id=_XDEX_PROGRAM_ID,
                    signature_limit=1,
                )
                print(
                    "[XDEX pinned pool role evidence] "
                    + json.dumps(
                        _public_evidence(
                            {
                                "account": structural_report.get("account"),
                                "program_id": structural_report.get("program_id"),
                                "decoded_state": structural_report.get("decoded_state"),
                                "vaults": structural_report.get("vaults"),
                                "summary": structural_report.get("summary"),
                            }
                        ),
                        sort_keys=True,
                        default=str,
                    )
                )
            except Exception as exc:
                structural_report = None
                print(
                    "[XDEX live probe] pinned pool re-verification failed: "
                    f"{type(exc).__name__}: {exc}"
                )

            cls.live_pair = select_catalog_pair_for_verified_pool(
                pools,
                structural_report,
                target_mint=_XENCAT_MINT,
                expected_pool_address=_XENCAT_POOL_ADDRESS,
            )
            cls.live_pair_source = "verified_xencat_pool_plus_catalog_transport_identity"

        if cls.live_pair is None:
            message = (
                "No usable quote pair was proven. The pinned XENCAT pool must "
                "re-verify on-chain and the exact same pool must expose API-side "
                "token identifiers in the XDEX catalog."
            )
            if REQUIRE_LIVE_PAIR:
                raise RuntimeError(message)
            raise unittest.SkipTest(message)

        print(
            "[XDEX live probe] source="
            f"{cls.live_pair_source} pair_evidence="
            + json.dumps(_public_evidence(cls.live_pair), sort_keys=True, default=str)
        )

    def setUp(self):
        self.provider = XDEXReadOnlyProvider(timeout=20)

    def test_live_token_price_returns_mapping(self):
        data = self.provider.token_price(self.live_pair["base_address"])

        self.assertIsInstance(data, dict)
        self.assertTrue(data)
        print(
            "[XDEX token-price evidence] "
            + json.dumps(_public_evidence(data), sort_keys=True, default=str)
        )

    def test_live_history_exposes_candidate_timestamp_and_price_fields(self):
        time_to = int(time.time())
        time_from = time_to - (7 * 24 * 60 * 60)
        points = self.provider.price_history(
            self.live_pair["base_address"],
            self.live_pair["quote_address"],
            time_from=time_from,
            time_to=time_to,
        )

        self.assertIsInstance(points, list)
        self.assertTrue(
            points,
            "XDEX returned no history points; cannot verify history field semantics.",
        )
        print(
            "[XDEX history evidence] "
            + json.dumps(_public_evidence(points[:3]), sort_keys=True, default=str)
        )
        for point in points[:10]:
            self.assertTrue(
                "timestamp" in point or "time" in point,
                f"history point lacks timestamp/time: {point}",
            )
            self.assertIn(
                "price",
                point,
                f"history point lacks price: {point}",
            )

    def test_live_quote_exposes_candidate_read_only_fields(self):
        observations = []
        for amount in (1, 2):
            data = self.provider.swap_quote(
                self.live_pair["base_address"],
                self.live_pair["quote_address"],
                amount,
                is_exact_amount_in=True,
            )
            self.assertIn("outputAmount", data)
            self.assertIn("rate", data)
            if "priceImpactPct" in data:
                self.assertIsNotNone(data["priceImpactPct"])
            observations.append({"inputAmount": amount, "response": _public_evidence(data)})

        print(
            "[XDEX quote evidence] "
            + json.dumps(observations, sort_keys=True, default=str)
        )


if __name__ == "__main__":
    unittest.main()
