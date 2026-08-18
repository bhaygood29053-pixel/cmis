import json
import os
import time
import unittest
from collections.abc import Mapping

from liquidity_scout.providers.x1 import XDEXReadOnlyProvider
from liquidity_scout.providers.x1.verified_program_pool_set import (
    verify_recognized_program_asset_pool_set,
)


RUN_LIVE = os.getenv("RUN_XDEX_LIVE_TESTS") == "1"
REQUIRE_LIVE_PAIR = os.getenv("XDEX_LIVE_REQUIRE_QUOTE_PAIR") == "1"
_NATIVE_XNT_SYMBOLS = {"XNT", "WXNT"}
_NATIVE_XNT_MINTS = {"So11111111111111111111111111111111111111112"}
# Existing CMIS evidence work has structurally verified the XENCAT XDEX-program
# pool set for this exact mint. It is used only as a read-only live-discovery
# anchor when the public XDEX pool list exposes no usable non-XNT pair.
_XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
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


def select_verified_onchain_live_pool_pair(report, *, target_mint):
    """Select a non-XNT pair only from a fully verified XDEX program pool set."""

    if not isinstance(report, Mapping):
        return None
    if report.get("summary", {}).get(
        "recognized_program_asset_pool_set_structurally_verified"
    ) is not True:
        return None

    target_mint = _text(target_mint)
    if not target_mint:
        return None

    for pool in report.get("pools") or []:
        if not isinstance(pool, Mapping):
            continue
        if pool.get("pool_state_structural_role_verified") is not True:
            continue
        mint_0 = _text(pool.get("mint_0"))
        mint_1 = _text(pool.get("mint_1"))
        if not mint_0 or not mint_1 or mint_0 == mint_1:
            continue
        if target_mint == mint_0:
            counter_mint = mint_1
        elif target_mint == mint_1:
            counter_mint = mint_0
        else:
            continue
        if target_mint in _NATIVE_XNT_MINTS or counter_mint in _NATIVE_XNT_MINTS:
            continue
        return {
            "pool_address": _text(pool.get("pool_address")),
            "base_address": target_mint,
            "quote_address": counter_mint,
            "base_symbol": None,
            "quote_symbol": None,
        }
    return None


def select_verified_catalog_xnt_pair(catalog_pools, report, *, target_mint):
    """Use XDEX's API-side XNT identity only for an independently verified pool.

    The catalog decides the API request identifiers; the on-chain program-pool
    proof decides whether the exact pool address is accepted. Neither source is
    allowed to prove the other's semantics by itself.
    """

    if not isinstance(report, Mapping):
        return None
    if report.get("summary", {}).get(
        "recognized_program_asset_pool_set_structurally_verified"
    ) is not True:
        return None

    verified_addresses = {
        _text(pool.get("pool_address"))
        for pool in report.get("pools") or []
        if isinstance(pool, Mapping)
        and pool.get("pool_state_structural_role_verified") is True
        and _text(pool.get("pool_address"))
    }
    target_mint = _text(target_mint)
    if not target_mint or not verified_addresses:
        return None

    for pool in catalog_pools:
        if not isinstance(pool, Mapping):
            continue
        pool_address = _text(pool.get("address"))
        if not pool_address or pool_address not in verified_addresses:
            continue
        base = pool.get("baseToken")
        quote = pool.get("quoteToken")
        if not isinstance(base, Mapping) or not isinstance(quote, Mapping):
            continue

        base_mint = _token_mint(base)
        quote_mint = _token_mint(quote)
        if base_mint == target_mint and _is_native_xnt_side(quote):
            target_token, xnt_token = base, quote
        elif quote_mint == target_mint and _is_native_xnt_side(base):
            target_token, xnt_token = quote, base
        else:
            continue

        target_api_address = _token_address(target_token)
        xnt_api_address = _token_address(xnt_token)
        if (
            not target_api_address
            or not xnt_api_address
            or target_api_address == xnt_api_address
        ):
            continue

        return {
            "pool_address": pool_address,
            "base_address": target_api_address,
            "quote_address": xnt_api_address,
            "base_symbol": _text(target_token.get("symbol")),
            "quote_symbol": _text(xnt_token.get("symbol")),
            "target_mint": target_mint,
            "xnt_catalog_mint": _token_mint(xnt_token),
            "xnt_catalog_address": _text(xnt_token.get("address")),
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

    def test_selects_only_from_fully_verified_onchain_pool_set(self):
        report = {
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": True,
            },
            "pools": [
                {
                    "pool_address": "P_XNT",
                    "mint_0": _XENCAT_MINT,
                    "mint_1": next(iter(_NATIVE_XNT_MINTS)),
                    "pool_state_structural_role_verified": True,
                },
                {
                    "pool_address": "P_VERIFIED",
                    "mint_0": "COUNTER_MINT",
                    "mint_1": _XENCAT_MINT,
                    "pool_state_structural_role_verified": True,
                },
            ],
        }

        pair = select_verified_onchain_live_pool_pair(
            report,
            target_mint=_XENCAT_MINT,
        )

        self.assertEqual(pair["pool_address"], "P_VERIFIED")
        self.assertEqual(pair["base_address"], _XENCAT_MINT)
        self.assertEqual(pair["quote_address"], "COUNTER_MINT")

    def test_rejects_partial_onchain_pool_set(self):
        report = {
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": False,
            },
            "pools": [
                {
                    "pool_address": "P_PARTIAL",
                    "mint_0": _XENCAT_MINT,
                    "mint_1": "COUNTER_MINT",
                    "pool_state_structural_role_verified": True,
                }
            ],
        }

        self.assertIsNone(
            select_verified_onchain_live_pool_pair(
                report,
                target_mint=_XENCAT_MINT,
            )
        )

    def test_catalog_xnt_pair_requires_same_verified_pool_address(self):
        catalog = [
            {
                "address": "P_VERIFIED",
                "baseToken": {"symbol": "XENCAT", "mint": _XENCAT_MINT},
                "quoteToken": {
                    "symbol": "XNT",
                    "name": "Wrapped XNT",
                    "address": "XNT_API_ID",
                    "mint": next(iter(_NATIVE_XNT_MINTS)),
                },
            }
        ]
        report = {
            "summary": {
                "recognized_program_asset_pool_set_structurally_verified": True,
            },
            "pools": [
                {
                    "pool_address": "P_VERIFIED",
                    "mint_0": _XENCAT_MINT,
                    "mint_1": next(iter(_NATIVE_XNT_MINTS)),
                    "pool_state_structural_role_verified": True,
                }
            ],
        }

        pair = select_verified_catalog_xnt_pair(
            catalog,
            report,
            target_mint=_XENCAT_MINT,
        )

        self.assertEqual(pair["pool_address"], "P_VERIFIED")
        self.assertEqual(pair["base_address"], _XENCAT_MINT)
        self.assertEqual(pair["quote_address"], "XNT_API_ID")
        self.assertEqual(pair["xnt_catalog_mint"], next(iter(_NATIVE_XNT_MINTS)))

        report["pools"][0]["pool_address"] = "OTHER_POOL"
        self.assertIsNone(
            select_verified_catalog_xnt_pair(
                catalog,
                report,
                target_mint=_XENCAT_MINT,
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

        cls.live_pair = select_non_native_live_pool_pair(pools)
        cls.live_pair_source = "xdex_public_pool_list"
        verified_pool_set = None

        if cls.live_pair is None:
            try:
                verified_pool_set = verify_recognized_program_asset_pool_set(
                    asset_mint=_XENCAT_MINT,
                    catalog_pools=pools,
                )
                print(
                    "[XDEX verified pool-set evidence] "
                    + json.dumps(
                        _public_evidence(
                            {
                                "status": verified_pool_set.get("status"),
                                "program_id": verified_pool_set.get("program_id"),
                                "summary": verified_pool_set.get("summary"),
                                "pools": verified_pool_set.get("pools"),
                            }
                        ),
                        sort_keys=True,
                        default=str,
                    )
                )
            except Exception as exc:
                print(
                    "[XDEX live probe] verified on-chain pool-set fallback failed: "
                    f"{type(exc).__name__}: {exc}"
                )

            cls.live_pair = select_verified_onchain_live_pool_pair(
                verified_pool_set,
                target_mint=_XENCAT_MINT,
            )
            cls.live_pair_source = "verified_onchain_xdex_program_pool_set"

        if cls.live_pair is None and verified_pool_set is not None:
            cls.live_pair = select_verified_catalog_xnt_pair(
                pools,
                verified_pool_set,
                target_mint=_XENCAT_MINT,
            )
            cls.live_pair_source = "verified_pool_plus_xdex_catalog_xnt_identity"

        if cls.live_pair is None:
            message = (
                "No usable quote pair was proven by the public XDEX list plus "
                "the independently verified on-chain XDEX program pool set."
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
