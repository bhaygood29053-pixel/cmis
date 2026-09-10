from copy import deepcopy

import pytest

from liquidity_scout.services.cmis_tokenized_equity_market_activity import (
    REQUIRED_METRICS,
    TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT,
    build_tokenized_equity_market_activity,
)
from liquidity_scout.services.cmis_tokenized_equity_provenance import (
    build_tokenized_equity_provenance,
)


EVALUATED_AT = "2026-09-10T12:05:00Z"
WINDOW_START = "2026-09-09T12:05:00Z"
WINDOW_END = "2026-09-10T12:05:00Z"
FACT_TIME = "2026-09-10T12:04:00Z"


def _provenance():
    return build_tokenized_equity_provenance(
        token={"chain": "x1", "asset_id": "EQ-MINT-001", "asset_id_kind": "mint"},
        underlying_security={"security_id": "US0000000001", "security_id_kind": "isin"},
        representation_type="tokenized_security_representation",
        issuer={"name": "Example Issuer"},
    )


def _source(*, source_class="indexer", transaction_id=None, suffix="1"):
    result = {
        "provider_id": f"provider-{suffix}",
        "source_class": source_class,
        "source_url": f"https://evidence.example/observation/{suffix}",
        "observation_id": f"obs-{suffix}",
        "retrieved_at": EVALUATED_AT,
        "content_sha256": "a" * 64,
    }
    if transaction_id is not None:
        result["transaction_id"] = transaction_id
    return result


def _snapshot(value, semantic, *, source=None, fact_time=FACT_TIME):
    return {
        "state": "OBSERVED",
        "semantic": semantic,
        "value": value,
        "fact_time": fact_time,
        "sources": [source or _source()],
    }


def _window(value, semantic, *, source=None, start=WINDOW_START, end=WINDOW_END):
    return {
        "state": "OBSERVED",
        "semantic": semantic,
        "value": value,
        "window_start": start,
        "window_end": end,
        "sources": [source or _source()],
    }


def _metrics():
    return {
        "liquidity_usd": _snapshot("1000.50", "liquidity_snapshot"),
        "trade_volume_usd": _window("250.25", "executed_trade_volume"),
        "trade_count": _window(3, "executed_trade_count"),
        "transfer_count": _window(7, "token_transfer_count"),
        "holder_count": _snapshot(50, "holder_snapshot"),
        "price_usd": _snapshot("42.10", "reference_price"),
        "bridge_inflow_units": _window("5", "bridge_inflow"),
        "bridge_outflow_units": _window("1", "bridge_outflow"),
    }


def _scope(**overrides):
    value = {
        "scope_kind": "pool",
        "chain": "x1",
        "scope_id": "POOL-ACCOUNT-001",
        "scope_id_kind": "account",
        "program_id": "XDEX-PROGRAM-001",
        "coverage_complete_for_scope": True,
        "coverage_basis": "exact pool history over requested bounded window",
    }
    value.update(overrides)
    return value


def _build(*, metrics=None, scope=None, provenance=None, max_age_seconds=300):
    return build_tokenized_equity_market_activity(
        tokenized_equity_provenance=provenance or _provenance(),
        scope=scope or _scope(),
        metrics=metrics or _metrics(),
        evaluated_at=EVALUATED_AT,
        max_age_seconds=max_age_seconds,
    )


def test_happy_path_keeps_all_market_semantics_separate():
    record = _build()

    assert record["contract"] == TOKENIZED_EQUITY_MARKET_ACTIVITY_CONTRACT
    assert tuple(record["metrics"]) == REQUIRED_METRICS
    assert record["metrics"]["liquidity_usd"]["semantic"] == "liquidity_snapshot"
    assert record["metrics"]["trade_volume_usd"]["semantic"] == "executed_trade_volume"
    assert record["metrics"]["trade_count"]["value"] == 3
    assert record["metrics"]["transfer_count"]["value"] == 7
    assert record["metrics"]["trade_count"]["value"] != record["metrics"]["transfer_count"]["value"]
    assert record["metrics"]["trade_volume_usd"]["window"]["seconds"] == 86400
    assert record["metrics"]["price_usd"]["semantic"] == "reference_price"
    assert record["metrics"]["price_usd"]["freshness"]["state"] == "FRESH"
    assert record["verification"]["accepted_tokenized_equity_provenance_bound"] is True
    assert record["verification"]["metric_semantics_kept_separate"] is True
    assert record["verification"]["global_market_coverage_verified"] is False
    assert record["boundaries"]["liquidity_equals_volume"] is False
    assert record["boundaries"]["transfer_equals_trade"] is False
    assert record["boundaries"]["bridge_flow_equals_exchange_volume"] is False
    assert record["boundaries"]["bridge_flow_proves_adoption"] is False
    assert record["boundaries"]["quoted_or_reference_price_equals_executed_price"] is False
    assert record["execution_authorized"] is False
    assert record["public_service_promoted"] is False
    assert record["scout_reliance_promoted"] is False


def test_zero_is_bounded_to_exact_scope_not_global_market():
    metrics = _metrics()
    metrics["trade_volume_usd"] = _window("0", "executed_trade_volume")
    metrics["trade_count"] = _window(0, "executed_trade_count")
    record = _build(metrics=metrics)

    assert record["metrics"]["trade_volume_usd"]["bounded_zero_observed"] is True
    assert record["metrics"]["trade_count"]["bounded_zero_observed"] is True
    assert record["scope"]["scope_kind"] == "pool"
    assert record["verification"]["global_market_coverage_verified"] is False
    assert record["boundaries"]["bounded_zero_equals_global_zero"] is False


def test_incomplete_scope_never_marks_zero_as_bounded_complete_observation():
    metrics = _metrics()
    metrics["trade_count"] = _window(0, "executed_trade_count")
    record = _build(metrics=metrics, scope=_scope(coverage_complete_for_scope=False))
    assert record["metrics"]["trade_count"]["bounded_zero_observed"] is False


def test_metric_semantics_cannot_be_relabelled():
    metrics = _metrics()
    metrics["transfer_count"]["semantic"] = "executed_trade_count"
    with pytest.raises(ValueError, match="token_transfer_count"):
        _build(metrics=metrics)

    metrics = _metrics()
    metrics["liquidity_usd"]["semantic"] = "executed_trade_volume"
    with pytest.raises(ValueError, match="liquidity_snapshot"):
        _build(metrics=metrics)


def test_reference_price_does_not_require_or_gain_execution_semantics():
    record = _build()
    price = record["metrics"]["price_usd"]
    assert price["semantic"] == "reference_price"
    assert all(source["transaction_id"] is None for source in price["sources"])
    assert record["boundaries"]["quoted_or_reference_price_equals_executed_price"] is False


def test_executed_price_requires_transaction_bound_chain_evidence():
    metrics = _metrics()
    metrics["price_usd"] = _snapshot(
        "42.25",
        "executed_trade_price",
        source=_source(source_class="venue_api"),
    )
    with pytest.raises(ValueError, match="transaction-bound"):
        _build(metrics=metrics)

    metrics["price_usd"] = _snapshot(
        "42.25",
        "executed_trade_price",
        source=_source(source_class="onchain_rpc", transaction_id="TX-001"),
    )
    record = _build(metrics=metrics)
    assert record["metrics"]["price_usd"]["semantic"] == "executed_trade_price"
    assert record["metrics"]["price_usd"]["sources"][0]["transaction_id"] == "TX-001"


def test_bridge_flow_remains_distinct_from_volume_and_adoption():
    record = _build()
    assert record["metrics"]["bridge_inflow_units"]["value"] == "5"
    assert record["metrics"]["trade_volume_usd"]["value"] == "250.25"
    assert record["boundaries"]["bridge_flow_equals_exchange_volume"] is False
    assert record["boundaries"]["bridge_flow_proves_adoption"] is False


def test_stale_metric_is_preserved_as_stale_not_refreshed_by_retrieval_time():
    metrics = _metrics()
    metrics["liquidity_usd"] = _snapshot(
        "1000",
        "liquidity_snapshot",
        fact_time="2026-09-10T11:00:00Z",
    )
    record = _build(metrics=metrics, max_age_seconds=300)
    assert record["metrics"]["liquidity_usd"]["freshness"]["state"] == "STALE"
    assert record["summary"]["stale_metric_count"] >= 1


def test_unknown_metric_cannot_smuggle_value_or_sources():
    metrics = _metrics()
    metrics["holder_count"] = {
        "state": "UNKNOWN",
        "semantic": "holder_snapshot",
        "value": 10,
    }
    with pytest.raises(ValueError, match="cannot carry observed value"):
        _build(metrics=metrics)

    metrics["holder_count"] = {
        "state": "UNKNOWN",
        "semantic": "holder_snapshot",
    }
    record = _build(metrics=metrics)
    assert record["metrics"]["holder_count"]["value"] is None
    assert record["metrics"]["holder_count"]["freshness"]["state"] == "UNKNOWN"


def test_exact_scope_identity_and_chain_binding_are_required():
    with pytest.raises(ValueError, match="scope.chain"):
        _build(scope=_scope(chain="robinhood_chain"))
    with pytest.raises(ValueError, match="label identity"):
        _build(scope=_scope(scope_id_kind="ticker"))
    with pytest.raises(ValueError, match="program_id"):
        _build(scope=_scope(program_id=None))


def test_missing_or_extra_metrics_fail_closed():
    metrics = _metrics()
    metrics.pop("holder_count")
    with pytest.raises(ValueError, match="missing required"):
        _build(metrics=metrics)

    metrics = _metrics()
    metrics["adoption_score"] = {"state": "UNKNOWN", "semantic": "adoption"}
    with pytest.raises(ValueError, match="unsupported"):
        _build(metrics=metrics)


def test_future_fact_time_fails_closed():
    metrics = _metrics()
    metrics["liquidity_usd"] = _snapshot(
        "1000",
        "liquidity_snapshot",
        fact_time="2026-09-10T12:06:00Z",
    )
    with pytest.raises(ValueError, match="future"):
        _build(metrics=metrics)


def test_unaccepted_or_execution_enabled_provenance_fails_closed():
    provenance = _provenance()
    provenance["execution_authorized"] = True
    with pytest.raises(ValueError, match="execution_authorized=false"):
        _build(provenance=provenance)

    provenance = _provenance()
    provenance["contract"] = "tokenized_equity_provenance/v999"
    with pytest.raises(ValueError, match="accepted"):
        _build(provenance=provenance)


def test_asset_scope_declaration_still_does_not_verify_global_coverage():
    record = _build(
        scope=_scope(
            scope_kind="asset",
            scope_id="EQ-MINT-001",
            scope_id_kind="mint",
            program_id=None,
            coverage_complete_for_scope=True,
            coverage_basis="provider declares full asset index coverage",
        )
    )
    assert record["verification"]["scope_coverage_declared_complete"] is True
    assert record["verification"]["global_market_coverage_verified"] is False
