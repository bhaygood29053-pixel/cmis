from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{path}: expected exactly one match, found {count}: {old!r}"
        )
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


capabilities = "liquidity_scout/cmis/capabilities.py"
replace_once(
    capabilities,
    """from liquidity_scout.services.cmis_wallet_relationship_request import (
    REQUEST_CONTRACT_VERSION as WALLET_RELATIONSHIP_REQUEST_CONTRACT_VERSION,
)
""",
    """from liquidity_scout.services.cmis_wallet_relationship_request import (
    REQUEST_CONTRACT_VERSION as WALLET_RELATIONSHIP_REQUEST_CONTRACT_VERSION,
)
from liquidity_scout.services.cmis_tokenized_equity_intelligence import (
    CONTRACT_VERSION as TOKENIZED_EQUITY_INTELLIGENCE_CONTRACT_VERSION,
    MATERIALIZATION_CONTRACT_VERSION as TOKENIZED_EQUITY_INTELLIGENCE_MATERIALIZATION_CONTRACT_VERSION,
    SERVICE as TOKENIZED_EQUITY_INTELLIGENCE_SERVICE,
)
from liquidity_scout.services.cmis_tokenized_equity_intelligence_request import (
    REQUEST_CONTRACT_VERSION as TOKENIZED_EQUITY_INTELLIGENCE_REQUEST_CONTRACT_VERSION,
)
""",
)
replace_once(
    capabilities,
    'CMIS_CONTRACT_VERSION = "1.29.0"',
    'CMIS_CONTRACT_VERSION = "1.30.0"',
)
replace_once(
    capabilities,
    '    "x1_intelligence_brief_inputs",\n    "wallet_relationship_intelligence",\n',
    '    "x1_intelligence_brief_inputs",\n    "tokenized_equity_intelligence",\n    "wallet_relationship_intelligence",\n',
)

helper = '''def _tokenized_equity_intelligence_capability(*, available: bool) -> dict[str, Any]:
    if not available:
        return {
            "state": "unavailable",
            "callable": False,
            "read_only": True,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "service_contract_version": TOKENIZED_EQUITY_INTELLIGENCE_CONTRACT_VERSION,
            "request_contract_version": TOKENIZED_EQUITY_INTELLIGENCE_REQUEST_CONTRACT_VERSION,
            "materialization_contract_version": TOKENIZED_EQUITY_INTELLIGENCE_MATERIALIZATION_CONTRACT_VERSION,
            "requirements": [],
            "limitations": ["tokenized_equity_intelligence_not_available_for_chain"],
            "live_x1_equity_deployment_verified": False,
            "live_robinhood_x1_route_verified": False,
            "proof_score_separate_from_risk": True,
            "execution_authorized": False,
        }
    return {
        "state": "bounded",
        "callable": True,
        "read_only": True,
        "public_service_promoted": True,
        "scout_reliance_promoted": True,
        "service_contract_version": TOKENIZED_EQUITY_INTELLIGENCE_CONTRACT_VERSION,
        "request_contract_version": TOKENIZED_EQUITY_INTELLIGENCE_REQUEST_CONTRACT_VERSION,
        "materialization_contract_version": TOKENIZED_EQUITY_INTELLIGENCE_MATERIALIZATION_CONTRACT_VERSION,
        "requirements": [
            "exact_x1_asset_mint_identity",
            "optional_exact_underlying_security_selector",
            "cmis_owned_tokenized_equity_record_resolver",
            "accepted_tokenized_equity_provenance_v1",
            "accepted_cross_chain_equity_provenance_v1",
            "accepted_tokenized_equity_rights_v1",
            "accepted_tokenized_equity_market_activity_v1",
            "accepted_tokenized_equity_evidence_quality_v1",
            "caller_fact_evidence_provider_injection_rejected",
            "protected_evidence_receipt_and_proof_score_attachment",
        ],
        "limitations": [
            "service_availability_does_not_prove_x1_tokenized_equity_deployment",
            "missing_subject_or_component_is_evidence_required_not_zero",
            "ticker_or_name_is_not_security_or_token_identity",
            "robinhood_chain_to_x1_route_unverified_without_direct_accepted_evidence",
            "rights_evidence_is_not_legal_adjudication",
            "token_transfer_is_not_securities_ownership_transfer_without_legal_structure",
            "wrapped_representation_is_not_underlying_equity",
            "liquidity_is_not_volume",
            "transfer_is_not_trade",
            "bridge_flow_is_not_adoption",
            "reference_price_is_not_executed_price",
            "proof_score_is_not_risk",
            "no_automatic_legal_compliance_risk_or_investment_conclusion",
            "no_execution_authorization",
            "x1_only_initial_scope",
        ],
        "live_x1_equity_deployment_verified": False,
        "live_robinhood_x1_route_verified": False,
        "proof_score_separate_from_risk": True,
        "execution_authorized": False,
    }


'''
replace_once(
    capabilities,
    "def _wallet_relationship_capability(*, available: bool) -> dict[str, Any]:\n",
    helper + "def _wallet_relationship_capability(*, available: bool) -> dict[str, Any]:\n",
)
replace_once(
    capabilities,
    "        WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=True),\n",
    "        TOKENIZED_EQUITY_INTELLIGENCE_SERVICE: _tokenized_equity_intelligence_capability(\n            available=True\n        ),\n        WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=True),\n",
)
replace_once(
    capabilities,
    "        WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=False),\n",
    "        TOKENIZED_EQUITY_INTELLIGENCE_SERVICE: _tokenized_equity_intelligence_capability(\n            available=False\n        ),\n        WALLET_RELATIONSHIP_SERVICE: _wallet_relationship_capability(available=False),\n",
)

replace_once(
    "liquidity_scout/cmis/__init__.py",
    '    "x1_intelligence_brief_inputs",\n    "wallet_relationship_intelligence",\n',
    '    "x1_intelligence_brief_inputs",\n    "tokenized_equity_intelligence",\n    "wallet_relationship_intelligence",\n',
)
replace_once(
    "liquidity_scout/services/cmis_tokenized_equity_intelligence.py",
    "PROMOTED = False",
    "PROMOTED = True",
)

for path in (
    "tests/test_cmis_capabilities.py",
    "tests/test_cmis_http_gateway.py",
    "tests/test_cmis_wallet_relationship_capability_v128.py",
):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if "1.29.0" not in text:
        raise SystemExit(f"{path}: expected 1.29.0 release assertion")
    p.write_text(text.replace("1.29.0", "1.30.0"), encoding="utf-8")

brief_test = Path("tests/test_cmis_x1_intelligence_brief_capability_v129.py")
text = brief_test.read_text(encoding="utf-8")
if "1.29.0" not in text:
    raise SystemExit("brief capability test missing 1.29 release assertion")
text = text.replace("1.29.0", "1.30.0")
old = "    assert services[-2:] == (SERVICE, WALLET_SERVICE)\n"
new = "    assert services[-3] == SERVICE\n    assert services[-1] == WALLET_SERVICE\n"
if text.count(old) != 1:
    raise SystemExit("brief service-order assertion drift")
brief_test.write_text(text.replace(old, new, 1), encoding="utf-8")

contract_test = Path("tests/test_cmis_tokenized_equity_intelligence_contract.py")
text = contract_test.read_text(encoding="utf-8")
for old, new in (
    (
        '    assert response["public_service_promoted"] is False\n',
        '    assert response["public_service_promoted"] is True\n',
    ),
    (
        '    assert response["scout_reliance_promoted"] is False\n',
        '    assert response["scout_reliance_promoted"] is True\n',
    ),
    (
        '    assert response["runtime_capability_promoted"] is False\n',
        '    assert response["runtime_capability_promoted"] is True\n',
    ),
):
    if text.count(old) != 1:
        raise SystemExit(f"tokenized contract assertion drift: {old!r}")
    text = text.replace(old, new, 1)
contract_test.write_text(text, encoding="utf-8")
