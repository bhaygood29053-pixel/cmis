import json
import os
import unittest
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_native_semantics import (
    QUOTE_PER_BASE,
    verify_ninja_price_native_semantics,
)
from liquidity_scout.providers.x1.xdex import fetch_pool_list


RUN_LIVE = os.getenv("RUN_X1_NINJA_PRICE_NATIVE_LIVE") == "1"


def _u64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data, offset):
    return encode_base58_pubkey(data[offset : offset + 32])


def _active_ratio_probe(pool_address, provider_price):
    state = fetch_account_state(pool_address)
    data = state.get("data")
    if not isinstance(data, bytes) or len(data) != 637:
        return {"status": "unavailable"}

    vault0 = _pubkey(data, 72)
    vault1 = _pubkey(data, 104)
    mint0 = _pubkey(data, 168)
    mint1 = _pubkey(data, 200)
    decimals0 = data[331]
    decimals1 = data[332]

    v0 = get_token_account_info(vault0)
    v1 = get_token_account_info(vault1)
    if v0.get("mint") != mint0 or v1.get("mint") != mint1:
        return {"status": "mint_mismatch"}

    active0_raw = int(v0["raw_amount"]) - _u64(data, 341) - _u64(data, 357) - _u64(data, 397)
    active1_raw = int(v1["raw_amount"]) - _u64(data, 349) - _u64(data, 365) - _u64(data, 405)
    active0 = Decimal(active0_raw) / (Decimal(10) ** decimals0)
    active1 = Decimal(active1_raw) / (Decimal(10) ** decimals1)
    ratio = active0 / active1
    observed = Decimal(str(provider_price))
    absolute_error = abs(observed - ratio)
    relative_error = absolute_error / abs(ratio) if ratio else None
    return {
        "status": "ok",
        "active_reserve_0": format(active0, "f"),
        "active_reserve_1": format(active1, "f"),
        "active_quote_per_base_ratio": format(ratio, "f"),
        "provider_priceNative": format(observed, "f"),
        "absolute_error": format(absolute_error, "f"),
        "relative_error": format(relative_error, "e") if relative_error is not None else None,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_PRICE_NATIVE_LIVE=1 to run read-only evidence",
)
class NinjaPriceNativeSemanticsLiveTests(unittest.TestCase):
    def test_live_price_native_matches_one_verified_reserve_ratio(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        xdex_pools = fetch_pool_list(network="X1 Mainnet")

        self.assertTrue(ninja_pools, "X1.Ninja returned no current pools")
        self.assertTrue(xdex_pools, "XDEX returned no X1 Mainnet pools")

        result = verify_ninja_price_native_semantics(
            ninja_pools=ninja_pools,
            xdex_pools=xdex_pools,
            min_verified_pools=5,
            max_samples=5,
            signature_limit=1,
        )

        public = {
            "status": result["status"],
            "sample_count": result["sample_count"],
            "verified_sample_count": result["verified_sample_count"],
            "minimum_verified_pool_count": result[
                "minimum_verified_pool_count"
            ],
            "stable_direction": result["stable_direction"],
            "price_native_pair_direction_verified": result[
                "price_native_pair_direction_verified"
            ],
            "price_native_reserve_ratio_verified": result[
                "price_native_reserve_ratio_verified"
            ],
            "price_native_semantics_verified": result[
                "price_native_semantics_verified"
            ],
            "price_native_unit_verified": result[
                "price_native_unit_verified"
            ],
            "price_native_is_usd_verified": result[
                "price_native_is_usd_verified"
            ],
            "comparison_policy": result["comparison_policy"],
            "samples": result["samples"],
            "semantics": result["semantics"],
            "cmis_promotable": result["cmis_promotable"],
            "execution_authorized": result["execution_authorized"],
        }
        print(
            "[X1.Ninja priceNative semantic evidence] "
            + json.dumps(public, sort_keys=True, default=str)
        )

        if result["status"] != "verified":
            active = []
            for sample in result["samples"]:
                address = sample.get("pool_address")
                price = sample.get("provider_priceNative")
                if address and price is not None:
                    active.append({
                        "pool_address": address,
                        **_active_ratio_probe(address, price),
                    })
            print(
                "[X1.Ninja priceNative active-reserve diagnostic] "
                + json.dumps(active, sort_keys=True, default=str)
            )

        # Current live evidence is deliberately partial: some pools match
        # quote/base essentially exactly while at least one current pool does
        # not match either instantaneous reserve ratio. Do not widen tolerance
        # to force promotion. A future full 5/5 match requires fresh review.
        self.assertEqual(result["status"], "partial")
        self.assertGreaterEqual(result["verified_sample_count"], 1)
        self.assertLess(result["verified_sample_count"], 5)
        self.assertIsNone(result["stable_direction"])
        self.assertFalse(result["price_native_pair_direction_verified"])
        self.assertFalse(result["price_native_reserve_ratio_verified"])
        self.assertFalse(result["price_native_semantics_verified"])
        self.assertFalse(result["price_native_unit_verified"])
        self.assertFalse(result["price_native_is_usd_verified"])

        matched = [
            row["unique_matching_direction"]
            for row in result["samples"]
            if row.get("unique_matching_direction") is not None
        ]
        self.assertTrue(matched)
        self.assertTrue(all(direction == QUOTE_PER_BASE for direction in matched))
        self.assertTrue(
            any(
                "price_native_does_not_match_verified_reserve_ratio"
                in row.get("rejection_reasons", [])
                for row in result["samples"]
            )
        )

        self.assertTrue(all(v is False for v in result["semantics"].values()))
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
