import unittest

from liquidity_scout.cmis.evidence_quality_gateway import EvidenceQualityMixin
from liquidity_scout.cmis.instant_x1_scan_gateway import InstantX1ScanMixin
from liquidity_scout.cmis.runtime_gateway import (
    INSTANT_X1_SCAN_SERVICE,
    RuntimeCMISGateway,
    SUPPORTED_SERVICES,
)
from liquidity_scout.services.cmis_contract import build_service_envelope
from liquidity_scout.services.cmis_instant_x1_scan import (
    CONTRACT_VERSION,
    HISTORY_METRICS,
    build_instant_x1_scan_response,
)


MINT = "MintScan111"


def identity_envelope(status="ok"):
    return build_service_envelope(
        "asset_lookup",
        "x1",
        status,
        asset={"symbol": "SCAN", "name": "Scan Token", "mint": MINT},
        data={
            "resolved_by": "mint",
            "match_quality": 100,
            "identity_key": f"mint:{MINT}",
            "normalized_identity": {
                "identity_root": "mint",
                "mint": MINT,
                "normalized_onchain_identity_verified": True,
            },
            "identity_reconciliation": {
                "state": "agreement",
                "conflicting_fields": [],
            },
        },
        confidence={
            "complete": status == "ok",
            "verified_checks": 1 if status == "ok" else 0,
            "total_checks": 1,
        },
        sources=[{"source": "X1.Ninja/XDEX", "role": "asset_lookup"}],
        observed_at=1000,
    )


def market_envelope(*, holders_verified=False):
    completeness = {
        "price": True,
        "liquidity": True,
        "volume_24h": True,
        "transactions_24h": True,
        "holders": holders_verified,
    }
    return build_service_envelope(
        "market_report",
        "x1",
        "ok" if holders_verified else "partial",
        asset={"symbol": "SCAN", "name": "Scan Token", "mint": MINT},
        data={
            "symbol": "SCAN",
            "name": "Scan Token",
            "mint": MINT,
            "price_usd": 1.0,
            "liquidity_usd": 5000.0,
            "volume_24h_usd": 1200.0,
            "transactions_24h": 42,
            "#LPs": 2,
            "lp_count": 2,
            "holders": 17 if holders_verified else None,
            "holders_reported": 17,
            "holders_observed": [17, 17],
            "holder_semantics": {
                "counted_entity": "unverified" if not holders_verified else "wallet",
                "coverage": "unverified" if not holders_verified else "complete",
            },
            "market_cap_usd_reported": 100000.0,
            "market_cap_verified": False,
            "fdv_usd_reported": 120000.0,
            "fdv_verified": False,
            "completeness": completeness,
            "provenance": {
                "source": "X1.Ninja/XDEX",
                "catalog_last_refresh_unix": 1000,
            },
        },
        confidence={
            "complete": holders_verified,
            "core_market_complete": True,
            "verified_checks": 4 + int(holders_verified),
            "total_checks": 5,
        },
        sources=[{
            "source": "X1.Ninja/XDEX",
            "role": "market_report",
            "observed_at": 1000,
        }],
        observed_at=1000,
        warnings=(
            []
            if holders_verified
            else [{"code": "holders_incomplete", "message": "holder semantics unverified"}]
        ),
    )


def tokenomics_envelope():
    return build_service_envelope(
        "tokenomics",
        "x1",
        "partial",
        asset={"symbol": "SCAN", "name": "Scan Token", "mint": MINT},
        data={
            "mint": MINT,
            "symbol": "SCAN",
            "name": "Scan Token",
            "current_total_supply": "1000000",
            "raw_supply": "1000000000000",
            "decimals": 6,
            "supply_verified": True,
            "rpc_decimals_consistent": True,
            "mint_authority": None,
            "mint_authority_verified": True,
            "mint_authority_state": "disabled",
            "freeze_authority": None,
            "freeze_authority_verified": True,
            "freeze_authority_state": "disabled",
            "future_minting_possible": False,
            "circulating_supply": None,
            "circulating_supply_verified": False,
            "maximum_supply": None,
            "maximum_supply_verified": False,
            "token_activity": {
                "available": False,
                "activity_verified": False,
                "coverage_scope": None,
                "coverage_verified": False,
                "lifetime_coverage_verified": False,
                "mint_events_observed": None,
                "burn_events_observed": None,
                "minted_tokens_observed": None,
                "burned_tokens_observed": None,
                "net_issuance_verified": False,
                "net_issuance_tokens": None,
                "verification_reasons": ["token_activity_not_supplied"],
            },
        },
        confidence={
            "complete": False,
            "verified_checks": 3,
            "total_checks": 4,
        },
        sources=[
            {"source": "x1_rpc", "role": "tokenomics.current_supply"},
            {"source": "x1_rpc", "role": "tokenomics.mint_account"},
        ],
        warnings=[
            {"code": "circulating_supply_unverified"},
            {"code": "maximum_supply_unverified"},
        ],
    )


def all_available_history_envelope():
    metric = lambda current, first, change, drawdown=None: {
        "status": "ok",
        "reason": None,
        "observation_count": 3,
        "current_value": current,
        "current_verified": True,
        "first_value": first,
        "first_observed_at": 100,
        "last_value": current,
        "last_observed_at": 1000,
        "total_change_pct": change,
        "minimum_value": min(current, first),
        "maximum_value": max(current, first),
        "sampled_max_drawdown_pct": drawdown,
        "continuous_coverage_verified": False,
    }
    return build_service_envelope(
        "historical_compare",
        "x1",
        "partial",
        asset={"symbol": "SCAN", "mint": MINT},
        data={
            "status": "partial",
            "mode": "all_available",
            "coverage_scope": "cmis_stored_verified_observations",
            "first_verified_observed_at": 100,
            "last_verified_observed_at": 1000,
            "available_metric_count": 4,
            "multi_point_metric_count": 4,
            "asset_lifetime_start_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "provider_history_imported": True,
            "provider_price_history": {
                "available": True,
                "usable_observation_count": 24,
                "first_observed_at": 100,
                "last_observed_at": 1000,
            },
            "provider_history_backfill": {
                "status": "partial",
                "provider_history_imported": True,
                "stored_verified_provider_observation_count": 24,
                "full_asset_lifetime_verified": False,
                "continuous_coverage_verified": False,
            },
            "metrics": {
                "price": {
                    **metric(1.0, 0.8, 25.0, -8.0),
                    "coverage_seconds": 900,
                    "observed_gap_count": 0,
                    "largest_observed_gap_seconds": 300,
                    "gap_threshold_seconds": 129600,
                    "provider_backfill_observation_count": 24,
                    "provider_history_imported": True,
                },
                "liquidity": metric(5000.0, 4000.0, 25.0),
                "volume": metric(1200.0, 1000.0, 20.0),
                "transactions": metric(42.0, 30.0, 40.0),
            },
        },
        confidence={"complete": False, "verified_checks": 2, "total_checks": 3},
        sources=[{"source": "historical_db", "role": "historical_compare.all_available"}],
        warnings=[{"code": "asset_lifetime_coverage_unverified"}],
    )


def risk_history_envelope():
    return build_service_envelope(
        "historical_compare",
        "x1",
        "ok",
        asset={"symbol": "SCAN", "mint": MINT},
        data={
            "status": "ok",
            "metric": "price",
            "period": "24h",
            "current_value": 1.0,
            "historical_value": 0.9,
            "current_verified": True,
            "historical_verified": True,
            "change_pct": 11.111111,
            "current_observed_at": 1000,
            "historical_observed_at": 900,
            "source": "historical_db",
        },
        confidence={"complete": True, "verified_checks": 3, "total_checks": 3},
        sources=[{"source": "historical_db", "role": "historical_compare.baseline"}],
    )


class _ScanBase:
    def __init__(self):
        self.history_calls = []
        self.lookup = identity_envelope()
        self.market = market_envelope()
        self.tokenomics = tokenomics_envelope()
        self.provider_backfill_calls = []

    def _asset_lookup(self, _asset):
        return self.lookup

    def _market_report(self, _asset):
        return self.market

    def _tokenomics(self, _asset, params):
        self.tokenomics_params = dict(params)
        return self.tokenomics

    def _maybe_backfill_verified_xdex_price_history(self, market, **kwargs):
        self.provider_backfill_calls.append((market, dict(kwargs)))
        return {
            "status": "partial",
            "reason": "verified_provider_price_history_backfilled",
            "provider_history_imported": True,
            "stored_verified_provider_observation_count": 24,
            "first_imported_observed_at": 100,
            "last_imported_observed_at": 1000,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
        }

    def _historical_from_market(self, question, market, **kwargs):
        self.history_calls.append((question, market, dict(kwargs)))
        if kwargs.get("mode") == "all_available":
            return all_available_history_envelope()
        return risk_history_envelope()

    def _propagate_upstream(self, service, upstream):
        return build_service_envelope(
            service,
            upstream.get("chain") or "x1",
            upstream.get("status") or "unavailable",
            asset=upstream.get("asset"),
            data={"upstream_service": upstream.get("service")},
            warnings=upstream.get("warnings") or [],
            errors=upstream.get("errors") or [],
        )

    def _gateway_error(self, service, chain, code, message, **_kwargs):
        return build_service_envelope(
            service,
            chain,
            "error",
            errors=[{"code": code, "message": message}],
        )

    def _chain_unavailable(self, service, chain):
        return build_service_envelope(
            service,
            chain,
            "unavailable",
            warnings=[{
                "code": "chain_provider_not_implemented",
                "message": "not implemented",
            }],
        )

    def dispatch(self, request):
        return self._gateway_error(
            request.get("service") or "unknown",
            request.get("chain") or "unknown",
            "unsupported_service",
            "unsupported",
        )


class _ScanGateway(
    EvidenceQualityMixin,
    InstantX1ScanMixin,
    _ScanBase,
):
    pass


class InstantX1ScanTests(unittest.TestCase):
    def test_builder_preserves_compact_verified_and_unverified_fields(self):
        from liquidity_scout.services.cmis_risk import build_risk_check_response

        risk = build_risk_check_response(
            market_envelope()["data"],
            tokenomics_envelope()["data"],
            risk_history_envelope()["data"],
            chain="x1",
            observed_at=1000,
        )
        response = build_instant_x1_scan_response(
            identity_envelope(),
            market_envelope(),
            tokenomics_envelope(),
            all_available_history_envelope(),
            risk,
        )

        self.assertEqual(response["service"], "instant_x1_scan")
        self.assertEqual(response["data"]["contract_version"], CONTRACT_VERSION)
        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"]["mint"], MINT)
        sections = response["data"]["sections"]

        self.assertTrue(sections["identity"]["verified"])
        self.assertEqual(sections["market"]["price_usd"], 1.0)
        self.assertTrue(sections["market"]["price_verified"])
        self.assertEqual(sections["market"]["#LPs"], 2)
        self.assertEqual(sections["market"]["market_cap_usd_reported"], 100000.0)
        self.assertFalse(sections["market"]["market_cap_verified"])

        self.assertEqual(
            sections["tokenomics"]["current_total_supply"],
            "1000000",
        )
        self.assertTrue(sections["tokenomics"]["supply_verified"])
        self.assertTrue(sections["tokenomics"]["mint_authority_verified"])
        self.assertFalse(
            sections["tokenomics"]["circulating_supply_verified"]
        )

        holder = sections["holder_concentration"]
        self.assertIsNone(holder["holders"])
        self.assertFalse(holder["holders_verified"])
        self.assertEqual(holder["holders_reported"], 17)
        self.assertFalse(holder["top_account_concentration"]["verified"])
        self.assertEqual(
            holder["top_account_concentration"]["state"],
            "unavailable",
        )

        history = sections["history"]
        self.assertEqual(
            history["coverage_scope"],
            "cmis_stored_verified_observations",
        )
        self.assertEqual(history["metrics"]["price"]["observation_count"], 3)
        self.assertEqual(history["metrics"]["price"]["total_change_pct"], 25.0)
        self.assertFalse(history["full_asset_lifetime_verified"])
        self.assertTrue(history["provider_history_imported"])
        self.assertEqual(
            history["coverage_scope"],
            "cmis_verified_observations_with_bounded_provider_price_backfill",
        )
        self.assertEqual(
            history["metrics"]["price"]["provider_backfill_observation_count"],
            24,
        )

        self.assertEqual(sections["risk"]["recommendation"], "WARN")
        self.assertFalse(sections["risk"]["score_verified"])
        self.assertFalse(response["data"]["execution_authorized"])
        self.assertTrue(
            response["data"]["sections"]["evidence"][
                "proof_score_separate_from_risk"
            ]
        )

    def test_runtime_composition_uses_bounded_price_backfill_without_onchain_expansion(self):
        gateway = _ScanGateway()
        response = gateway.dispatch({
            "service": "instant_x1_scan",
            "chain": "x1",
            "asset": "SCAN",
            "params": {},
        })

        self.assertEqual(response["status"], "partial")
        self.assertEqual(len(gateway.provider_backfill_calls), 1)
        _market, backfill_kwargs = gateway.provider_backfill_calls[0]
        self.assertEqual(backfill_kwargs["lookback_days"], 300)
        self.assertEqual(backfill_kwargs["min_refresh_seconds"], 21600)
        self.assertEqual(backfill_kwargs["rel_tolerance"], 0.005)
        self.assertEqual(len(gateway.history_calls), 2)

        question, _market, kwargs = gateway.history_calls[0]
        self.assertIsNone(question)
        self.assertEqual(kwargs["mode"], "all_available")
        self.assertEqual(tuple(kwargs["metrics"]), HISTORY_METRICS)
        self.assertFalse(kwargs["include_onchain_coverage"])
        self.assertFalse(kwargs["include_supply_lookup"])

        question, _market, kwargs = gateway.history_calls[1]
        self.assertEqual(question, "Has price changed in the last 24 hours?")
        self.assertEqual(kwargs["mode"], "window")
        self.assertFalse(kwargs["include_onchain_coverage"])
        self.assertFalse(kwargs["include_supply_lookup"])
        history_section = response["data"]["sections"]["history"]
        self.assertTrue(history_section["provider_history_imported"])
        self.assertEqual(
            history_section["provider_history_backfill"]["status"],
            "partial",
        )

        self.assertEqual(gateway.tokenomics_params, {})
        self.assertIn("evidence_receipt", response)
        self.assertIn("proof_score", response)
        self.assertFalse(response["proof_score"]["risk_considered"])
        self.assertTrue(response["proof_score"]["risk_separate"])
        self.assertEqual(
            response["data"]["sections"]["risk"]["recommendation"],
            response["risk"]["recommendation"],
        )

    def test_holder_verification_can_complete_only_existing_holder_gate(self):
        from liquidity_scout.services.cmis_risk import build_risk_check_response

        market = market_envelope(holders_verified=True)
        risk = build_risk_check_response(
            market["data"],
            tokenomics_envelope()["data"],
            risk_history_envelope()["data"],
            chain="x1",
        )
        response = build_instant_x1_scan_response(
            identity_envelope(),
            market,
            tokenomics_envelope(),
            all_available_history_envelope(),
            risk,
        )

        self.assertTrue(
            response["data"]["sections"]["holder_concentration"][
                "holders_verified"
            ]
        )
        self.assertEqual(
            response["data"]["sections"]["holder_concentration"]["holders"],
            17,
        )
        self.assertFalse(
            response["data"]["sections"]["holder_concentration"][
                "top_account_concentration"
            ]["verified"]
        )

    def test_unknown_scan_params_fail_closed(self):
        response = _ScanGateway().dispatch({
            "service": "instant_x1_scan",
            "chain": "x1",
            "asset": "SCAN",
            "params": {"market_report": {"price_usd": 999}},
        })
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "unsupported_scan_params",
        )

    def test_caller_supplied_risk_policy_must_be_mapping(self):
        response = _ScanGateway().dispatch({
            "service": "instant_x1_scan",
            "chain": "x1",
            "asset": "SCAN",
            "params": {"risk_policy": "PASS"},
        })
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "invalid_risk_policy")

    def test_asset_prerequisite_failure_propagates_without_market_collection(self):
        gateway = _ScanGateway()
        gateway.lookup = build_service_envelope(
            "asset_lookup",
            "x1",
            "ambiguous",
            warnings=[{"code": "asset_ambiguous"}],
        )
        response = gateway.dispatch({
            "service": "instant_x1_scan",
            "chain": "x1",
            "asset": "SCAN",
            "params": {},
        })
        self.assertEqual(response["status"], "ambiguous")
        self.assertEqual(response["data"]["upstream_service"], "asset_lookup")
        self.assertEqual(gateway.history_calls, [])

    def test_solana_scan_is_explicitly_unavailable(self):
        response = _ScanGateway().dispatch({
            "service": "instant_x1_scan",
            "chain": "solana",
            "asset": "So111",
            "params": {},
        })
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["chain"], "solana")

    def test_runtime_public_service_registration(self):
        self.assertIn(INSTANT_X1_SCAN_SERVICE, SUPPORTED_SERVICES)
        self.assertTrue(issubclass(RuntimeCMISGateway, InstantX1ScanMixin))


if __name__ == "__main__":
    unittest.main()
