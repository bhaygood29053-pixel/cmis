from unittest.mock import patch

from liquidity_scout.services.cmis_instant_x1_scan_v6 import (
    build_instant_x1_scan_v6_response,
)


def _v5_response():
    return {
        "status": "partial",
        "data": {
            "contract_version": "instant_x1_scan/v5",
            "sections": {
                "identity": {
                    "status": "ok",
                    "verified": True,
                    "identity_key": "native:xnt",
                    "symbol": "XNT",
                },
                "holder_concentration": {
                    "holders": None,
                    "holders_verified": False,
                    "holders_state": "not_applicable",
                    "holders_reason": "xnt_is_native_currency_not_spl_holder_population",
                    "holder_semantics": {
                        "state": "not_applicable",
                        "counted_entity": "native_xnt_account_address",
                        "token_holder_count_applicable": False,
                    },
                    "top_account_concentration": {
                        "value": None,
                        "verified": False,
                        "state": "unavailable",
                        "reason": "native_xnt_account_concentration_not_verified",
                        "basis": "top_20_native_xnt_accounts_percent_of_circulating_xnt",
                        "counted_entity": "native_xnt_account_address",
                    },
                    "native_account_concentration": {
                        "verified": False,
                        "counted_entity": "native_xnt_account_address",
                        "holder_count_state": "not_applicable",
                    },
                },
                "history": {
                    "mode": "all_available",
                    "available_metric_count": 0,
                    "metrics": {"price": {"observation_count": 0}},
                    "price_lifetime_coverage": {},
                    "provider_history_imported": False,
                    "full_supported_pair_lifetime_verified": False,
                    "continuous_pair_price_coverage_verified": False,
                    "provider_range_complete_verified": False,
                    "historical_quote_usd_equivalence_verified": False,
                    "full_usd_lifetime_verified": False,
                },
            },
            "limitations": [],
            "execution_authorized": False,
        },
    }


def test_v6_preserves_native_xnt_collection_failure_without_changing_holder_applicability():
    failure = {
        "native_account_concentration_verified": False,
        "cmis_promotable": False,
        "counted_entity": "native_xnt_account_address",
        "holder_count_state": "not_applicable",
        "collection_state": "failed",
        "collection_failure_code": "native_xnt_account_concentration_collection_failed",
        "collection_failure_type": "TimeoutError",
        "execution_authorized": False,
    }

    with patch(
        "liquidity_scout.services.cmis_instant_x1_scan_v6.build_instant_x1_scan_v5_response",
        return_value=_v5_response(),
    ):
        result = build_instant_x1_scan_v6_response(
            {}, {}, {}, {}, {}, native_distribution=failure
        )

    holder = result["data"]["sections"]["holder_concentration"]
    assert holder["holders_state"] == "not_applicable"
    assert holder["holders_reason"] == "xnt_is_native_currency_not_spl_holder_population"
    assert holder["holders"] is None
    assert holder["holders_verified"] is False

    concentration = holder["top_account_concentration"]
    assert concentration["verified"] is False
    assert concentration["state"] == "unavailable"
    assert concentration["reason"] == "native_xnt_account_concentration_collection_failed"

    diagnostic = holder["native_account_concentration"]
    assert diagnostic["verified"] is False
    assert diagnostic["collection_state"] == "failed"
    assert diagnostic["collection_failure_code"] == "native_xnt_account_concentration_collection_failed"
    assert diagnostic["collection_failure_type"] == "TimeoutError"
    assert diagnostic["execution_authorized"] is False

    assert result["data"]["execution_authorized"] is False


def test_v6_does_not_promote_exception_messages_or_invent_holder_population():
    failure = {
        "native_account_concentration_verified": False,
        "cmis_promotable": False,
        "counted_entity": "native_xnt_account_address",
        "holder_count_state": "not_applicable",
        "collection_state": "failed",
        "collection_failure_code": "native_xnt_account_concentration_collection_failed",
        "collection_failure_type": "RuntimeError",
        "message": "provider secret-bearing diagnostic must not leak",
        "execution_authorized": False,
    }

    with patch(
        "liquidity_scout.services.cmis_instant_x1_scan_v6.build_instant_x1_scan_v5_response",
        return_value=_v5_response(),
    ):
        result = build_instant_x1_scan_v6_response(
            {}, {}, {}, {}, {}, native_distribution=failure
        )

    holder = result["data"]["sections"]["holder_concentration"]
    assert "message" not in holder["native_account_concentration"]
    assert holder["holders_state"] == "not_applicable"
    assert holder["holders"] is None
