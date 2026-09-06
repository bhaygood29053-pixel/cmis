from decimal import Decimal

from liquidity_scout.providers.x1.ninja_liquidity_unit_semantics import (
    VERSION,
    evaluate_x1_ninja_liquidity_unit_semantics,
)


def _live_513(**overrides):
    values = {
        "provider_liquidity": "725.7858651168269",
        "provider_xnt_price_usd": "0.3517496668516707",
        "rpc_xnt_reserve": "1031.679534501",
        "rpc_asset_reserve": "202234331.244878089",
        "reference_usdcx_per_xnt": "0.3517496668516706787549193935",
        "source_usdc_usd_price": "0.99988399",
        "exact_pool_identity_verified": True,
        "wrapped_xnt_position_verified": True,
        "reference_pool_identity_verified": True,
        "current_usdcx_usd_equivalence_verified": True,
    }
    values.update(overrides)
    return evaluate_x1_ninja_liquidity_unit_semantics(**values)


def test_live_513_provider_nominal_basis_is_exact_while_independent_usd_differs():
    result = _live_513()

    assert result["contract_version"] == VERSION
    assert result["status"] == "verified"
    assert result["provider_numerical_unit"] == "USDC.X_nominal_quote_basis"

    nominal = result["provider_nominal_basis"]
    assert nominal["provider_reference_basis_matches_rpc"] is True
    assert nominal["provider_nominal_liquidity_semantics_verified"] is True
    assert nominal["provider_liquidity_comparison"]["within_tolerance"] is True
    assert (
        Decimal(nominal["derived_provider_nominal_liquidity"])
        == Decimal("725.7858651168269159802816414")
    )
    assert nominal["independently_verified_external_usd"] is False

    independent = result["independent_current_usd"]
    assert independent["independent_usd_valuation_verified"] is True
    assert (
        Decimal(independent["independent_liquidity_usd"])
        < Decimal("725.7858651168269")
    )
    assert independent["provider_vs_independent_usd"]["within_tolerance"] is False
    assert (
        Decimal(independent["provider_vs_independent_usd"]["relative_error"])
        > Decimal("1e-4")
    )

    assert result["stable_name_implies_one_usd"] is False
    assert result["provider_price_reused_as_independent_usd_proof"] is False
    assert result["provider_fact_time_verified"] is False
    assert result["source_independence_verified"] is False
    assert result["execution_authorized"] is False


def test_exact_one_usdc_usd_makes_nominal_and_independent_values_converge():
    result = _live_513(source_usdc_usd_price="1")
    nominal = Decimal(
        result["provider_nominal_basis"]["derived_provider_nominal_liquidity"]
    )
    independent = Decimal(
        result["independent_current_usd"]["independent_liquidity_usd"]
    )

    # Provider reference basis and exact RPC reference ratio differ only by the
    # accepted reference comparison rounding.
    relative = abs(nominal - independent) / independent
    assert relative <= Decimal("1e-6")
    assert result["independent_current_usd"]["provider_vs_independent_usd"][
        "within_tolerance"
    ] is True


def test_nominal_semantics_can_verify_without_claiming_independent_usd():
    result = _live_513(current_usdcx_usd_equivalence_verified=False)

    assert result["provider_nominal_basis"][
        "provider_nominal_liquidity_semantics_verified"
    ] is True
    assert result["independent_current_usd"][
        "independent_usd_valuation_verified"
    ] is False
    assert result["status"] == "partial"
    assert result["execution_authorized"] is False


def test_wrong_provider_reference_basis_fails_nominal_semantics():
    result = _live_513(provider_xnt_price_usd="0.36")

    assert result["provider_nominal_basis"][
        "provider_reference_basis_matches_rpc"
    ] is False
    assert result["provider_nominal_basis"][
        "provider_nominal_liquidity_semantics_verified"
    ] is False


def test_material_provider_liquidity_mismatch_fails_nominal_semantics():
    result = _live_513(provider_liquidity="800")

    assert result["provider_nominal_basis"]["provider_liquidity_comparison"][
        "within_tolerance"
    ] is False
    assert result["provider_nominal_basis"][
        "provider_nominal_liquidity_semantics_verified"
    ] is False


def test_identity_failure_blocks_both_semantic_claims():
    result = _live_513(exact_pool_identity_verified=False)

    assert result["provider_nominal_basis"][
        "provider_nominal_liquidity_semantics_verified"
    ] is False
    assert result["independent_current_usd"][
        "independent_usd_valuation_verified"
    ] is False
    assert result["execution_authorized"] is False
