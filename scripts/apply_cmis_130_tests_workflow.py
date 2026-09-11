from pathlib import Path


path = Path(".github/workflows/tests.yml")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one workflow match, found {count}: {old!r}")
    text = text.replace(old, new, 1)


replace_once(
    '              "x1_intelligence_brief_inputs",\n              "wallet_relationship_intelligence",\n',
    '              "x1_intelligence_brief_inputs",\n              "tokenized_equity_intelligence",\n              "wallet_relationship_intelligence",\n',
)
replace_once(
    "      - name: Validate CMIS 1.29 capability and Instant X1 Scan v6 history contract\n",
    "      - name: Validate CMIS 1.30 capability and Instant X1 Scan v6 history contract\n",
)
replace_once(
    "          assert 'CMIS_CONTRACT_VERSION = \"1.29.0\"' in capabilities\n",
    "          assert 'CMIS_CONTRACT_VERSION = \"1.30.0\"' in capabilities\n",
)
replace_once(
    '          print("CMIS_129_CAPABILITY_AND_INSTANT_X1_SCAN_V6=PASS")\n',
    '          print("CMIS_130_CAPABILITY_AND_INSTANT_X1_SCAN_V6=PASS")\n',
)
replace_once(
    "      - name: Validate CMIS 1.29 regression expectations\n",
    "      - name: Validate CMIS 1.30 regression expectations\n",
)
replace_once(
    "          assert 'self.assertEqual(CMIS_CONTRACT_VERSION, \"1.29.0\")' in capabilities_test\n",
    "          assert 'self.assertEqual(CMIS_CONTRACT_VERSION, \"1.30.0\")' in capabilities_test\n",
)
replace_once(
    "          assert 'response[\"contract_version\"], \"1.29.0\"' in http_test\n",
    "          assert 'response[\"contract_version\"], \"1.30.0\"' in http_test\n",
)
replace_once(
    '          print("CMIS_129_REGRESSION_EXPECTATIONS=PASS")\n',
    '          print("CMIS_130_REGRESSION_EXPECTATIONS=PASS")\n',
)
replace_once(
    "      - name: Test X1 Intelligence Brief CMIS 1.29 capability promotion\n        env:\n          PYTHONPATH: .\n        run: python -m pytest -q tests/test_cmis_x1_intelligence_brief_capability_v129.py\n",
    "      - name: Test X1 Intelligence Brief preservation under CMIS 1.30\n        env:\n          PYTHONPATH: .\n        run: python -m pytest -q tests/test_cmis_x1_intelligence_brief_capability_v129.py\n\n      - name: Test Tokenized Equity Intelligence CMIS 1.30 capability promotion\n        env:\n          PYTHONPATH: .\n        run: python -m pytest -q tests/test_cmis_tokenized_equity_intelligence_contract.py tests/test_cmis_tokenized_equity_capability_v130.py tests/test_cmis_tokenized_equity_evidence_quality.py\n",
)

# The release workflow itself must no longer assert the prior release as current.
if 'CMIS_CONTRACT_VERSION = "1.29.0"' in text:
    raise SystemExit("stale current CMIS 1.29 capability assertion remains")
if 'response["contract_version"], "1.29.0"' in text:
    raise SystemExit("stale current CMIS 1.29 HTTP assertion remains")

path.write_text(text, encoding="utf-8")
