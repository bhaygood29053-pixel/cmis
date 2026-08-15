import inspect
import unittest
from unittest.mock import patch

import agi_burn_scan
import x1_burn_scan
import x1_burn_scan_v2
import xdex_asset_lookup
import xdex_catalog_probe
from liquidity_scout.market.client import (
    XDEXCatalog as legacy_market_catalog,
    fetch_all_pools as legacy_fetch_all_pools,
)
from liquidity_scout.providers.x1.activity_scanner import (
    X1ActivityScanner,
    collect_signature_window as provider_collect_signature_window,
    initialize_activity_db as provider_initialize_activity_db,
    open_activity_db as provider_open_activity_db,
    scan_token_activity as provider_scan_token_activity,
)
from liquidity_scout.providers.x1.health import X1HealthProvider
from liquidity_scout.providers.x1.market import (
    X1Provider,
    XDEXCatalog as provider_market_catalog,
    fetch_all_pools as provider_fetch_all_pools,
)
from liquidity_scout.providers.x1.network import X1NetworkProvider
from liquidity_scout.providers.x1.network_history import X1NetworkHistoryProvider
from liquidity_scout.providers.x1.rpc import (
    X1RPCProvider,
    get_mint_info as provider_get_mint_info,
    get_token_supply as provider_get_token_supply,
    rpc_request as provider_rpc_request,
)
from liquidity_scout.providers.x1.supply import X1SupplyProvider
from liquidity_scout.tokenomics.rpc import (
    get_mint_info as legacy_get_mint_info,
    get_token_supply as legacy_get_token_supply,
    rpc_request as legacy_rpc_request,
)
from liquidity_scout.tokenomics.scanner import (
    collect_signature_window as legacy_collect_signature_window,
    initialize_activity_db as legacy_initialize_activity_db,
    open_activity_db as legacy_open_activity_db,
    scan_token_activity as legacy_scan_token_activity,
)


class CMISStep3X1ProviderSignoffTests(unittest.TestCase):
    def test_required_x1_provider_capabilities_exist(self):
        providers = (
            X1Provider,
            X1RPCProvider,
            X1SupplyProvider,
            X1NetworkProvider,
            X1NetworkHistoryProvider,
            X1HealthProvider,
            X1ActivityScanner,
        )
        self.assertEqual(len(providers), 7)
        for provider in providers:
            self.assertEqual(provider.chain, "x1")

    def test_market_compatibility_path_is_provider_owned(self):
        self.assertIs(legacy_market_catalog, provider_market_catalog)
        self.assertIs(legacy_fetch_all_pools, provider_fetch_all_pools)

    def test_rpc_compatibility_path_is_provider_owned(self):
        self.assertIs(legacy_rpc_request, provider_rpc_request)
        self.assertIs(legacy_get_token_supply, provider_get_token_supply)
        self.assertIs(legacy_get_mint_info, provider_get_mint_info)

    def test_activity_compatibility_path_is_provider_owned(self):
        self.assertIs(
            legacy_collect_signature_window,
            provider_collect_signature_window,
        )
        self.assertIs(
            legacy_initialize_activity_db,
            provider_initialize_activity_db,
        )
        self.assertIs(legacy_open_activity_db, provider_open_activity_db)
        self.assertIs(legacy_scan_token_activity, provider_scan_token_activity)

    def test_generic_burn_cli_has_no_raw_x1_http_transport(self):
        source = inspect.getsource(x1_burn_scan)
        self.assertNotIn("import requests", source)
        self.assertNotIn("requests.post", source)
        self.assertNotIn('"jsonrpc": "2.0"', source)
        self.assertIn("X1RPCProvider", source)
        self.assertIn("X1ActivityScanner", source)

    def test_agi_burn_utility_has_no_hardcoded_mint_or_rpc_transport(self):
        source = inspect.getsource(agi_burn_scan)
        self.assertNotIn("AGI_MINT", source)
        self.assertNotIn("rpc.mainnet.x1.xyz", source)
        self.assertNotIn("requests", source)

        with patch.object(agi_burn_scan, "run_token_scan", return_value={}) as scan:
            agi_burn_scan.main()
        scan.assert_called_once_with(
            "AGI",
            workers=agi_burn_scan.WORKERS,
            max_signatures=None,
            db_file=agi_burn_scan.DB_FILE,
        )

    def test_v2_burn_cli_uses_provider_and_never_marks_lifetime_cache_complete(self):
        source = inspect.getsource(x1_burn_scan_v2)
        self.assertNotIn("ThreadPoolExecutor", source)
        self.assertNotIn("scan_state", source)
        self.assertNotIn("full_history_complete", source)
        self.assertNotIn("base.rpc(", source)
        self.assertIn("X1RPCProvider", source)
        self.assertIn("X1ActivityScanner", source)
        self.assertIn("Lifetime coverage: UNVERIFIED", source)

    def test_asset_lookup_collection_delegates_to_market_provider(self):
        marker = ([{"address": "P1"}], "1.23")
        with patch.object(
            xdex_asset_lookup,
            "provider_fetch_all_pools",
            return_value=marker,
        ) as fetch:
            result = xdex_asset_lookup.fetch_all_pools()
        self.assertEqual(result, marker)
        fetch.assert_called_once_with()

        source = inspect.getsource(xdex_asset_lookup)
        self.assertNotIn("import requests", source)
        self.assertNotIn("requests.get", source)
        self.assertNotIn("api.x1.ninja/v1/pools", source)

    def test_catalog_probe_uses_market_provider_contract(self):
        source = inspect.getsource(xdex_catalog_probe)
        self.assertNotIn("import requests", source)
        self.assertNotIn("requests.get", source)
        self.assertIn("X1Provider", source)
        self.assertIn("market_catalog", source)

    def test_shared_services_do_not_own_http_transport(self):
        import liquidity_scout.services.cmis_asset_lookup as asset_lookup
        import liquidity_scout.services.cmis_historical as historical
        import liquidity_scout.services.cmis_market as market
        import liquidity_scout.services.cmis_pre_trade as pre_trade
        import liquidity_scout.services.cmis_rank as rank
        import liquidity_scout.services.cmis_risk as risk
        import liquidity_scout.services.cmis_tokenomics as tokenomics

        for module in (
            asset_lookup,
            historical,
            market,
            pre_trade,
            rank,
            risk,
            tokenomics,
        ):
            source = inspect.getsource(module)
            self.assertNotIn("import requests", source, module.__name__)
            self.assertNotIn("requests.get", source, module.__name__)
            self.assertNotIn("requests.post", source, module.__name__)


if __name__ == "__main__":
    unittest.main()
