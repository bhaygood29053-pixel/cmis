import unittest

from liquidity_scout.providers.x1.agents_radio import (
    BOOTSTRAP_CURATED,
    CATALOG_OBSERVED,
    DEPLOYMENT_EVENT,
    RADIO_REGISTERED,
    X1_AGENTS_RADIO_CATALOG_PATH,
    X1AgentsRadioAPIError,
    X1AgentsRadioProvider,
    fetch_catalog,
    parse_bootstrap,
    parse_catalog,
    parse_deployments,
    parse_health,
)


XDEX_PROGRAM_ID = (
    "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
)

RADIO_PROGRAM_ID = (
    "4Ai4Ps8YsrLfshU9xvkf9pobiVhewELdbXEZA7zaZ8E3"
)


class FakeJSONResponse:
    def __init__(self, payload, *, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class RecordingGet:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append(
            {
                "url": url,
                **kwargs,
            }
        )
        return self.responses.pop(0)


class X1AgentsRadioProviderTests(unittest.TestCase):
    def test_health_is_discovery_registry_health(self):
        parsed = parse_health(
            {
                "status": "ok",
                "program": RADIO_PROGRAM_ID,
                "treasury": "Treasury111",
                "registered_programs": 2,
                "active_subscribers": 5,
                "last_digest_at": 1787697116713,
            }
        )

        self.assertTrue(parsed["operational"])
        self.assertEqual(
            parsed["scope"],
            "provider_discovery_registry",
        )
        self.assertEqual(
            parsed["registry_program_id"],
            RADIO_PROGRAM_ID,
        )
        self.assertEqual(
            parsed["registered_programs"],
            2,
        )
        self.assertEqual(
            parsed["last_digest_at"],
            1787697116713,
        )

    def test_bootstrap_preserves_distinct_evidence_tiers(self):
        parsed = parse_bootstrap(
            {
                "network": "x1-mainnet",
                "schema_version": "2.0.0",
                "generated_at": (
                    "2026-08-26T18:30:58.389Z"
                ),
                "core_protocols": [
                    {
                        "program_id": XDEX_PROGRAM_ID,
                        "name": "XDEX",
                        "category": "dex",
                        "priority": "critical",
                    }
                ],
                "registered_programs": [
                    {
                        "program_id": RADIO_PROGRAM_ID,
                        "name": "X1 Radio Registry",
                    }
                ],
                "skills": [],
                "metadata": {},
                "registry": {},
                "api": {},
            }
        )

        self.assertEqual(
            parsed["program_count"],
            2,
        )

        xdex = next(
            item
            for item in parsed["programs"]
            if item["program_id"] == XDEX_PROGRAM_ID
        )

        radio = next(
            item
            for item in parsed["programs"]
            if item["program_id"] == RADIO_PROGRAM_ID
        )

        self.assertEqual(
            xdex["evidence_tier"],
            BOOTSTRAP_CURATED,
        )
        self.assertEqual(
            radio["evidence_tier"],
            RADIO_REGISTERED,
        )

        self.assertFalse(
            xdex["cmis_identity_promoted"]
        )
        self.assertFalse(
            xdex["onchain_account_verified"]
        )
        self.assertFalse(
            xdex["onchain_executable_verified"]
        )

    def test_bootstrap_network_mismatch_fails_closed(self):
        with self.assertRaises(
            X1AgentsRadioAPIError
        ):
            parse_bootstrap(
                {
                    "network": "solana-mainnet",
                    "generated_at": (
                        "2026-08-26T18:30:58.389Z"
                    ),
                }
            )

    def test_catalog_provider_verified_flag_is_not_promoted(self):
        parsed = parse_catalog(
            {
                "generated_at": (
                    "2026-08-26T18:30:58.560Z"
                ),
                "count": 1,
                "total_note": (
                    "provider observational counts"
                ),
                "programs": [
                    {
                        "program_id": XDEX_PROGRAM_ID,
                        "name": "XDEX",
                        "name_source": "curated",
                        "category": "DEX",
                        "framework": "anchor",
                        "status": "live",
                        "website": "https://xdex.xyz",
                        "verified": False,
                        "bytecode_instructions": [
                            "Initialize",
                            "Deposit",
                            "Withdraw",
                            "SwapBaseInput",
                        ],
                        "tx_count_24h": 1994,
                    }
                ],
            }
        )

        program = parsed["programs"][0]

        self.assertEqual(
            program["evidence_tier"],
            CATALOG_OBSERVED,
        )
        self.assertIs(
            program["provider_verified_claim"],
            False,
        )
        self.assertFalse(
            program["cmis_identity_promoted"]
        )
        self.assertEqual(
            program["raw"]["tx_count_24h"],
            1994,
        )
        self.assertIn(
            "SwapBaseInput",
            program["raw"]["bytecode_instructions"],
        )

    def test_catalog_count_mismatch_fails_closed(self):
        with self.assertRaises(
            X1AgentsRadioAPIError
        ):
            parse_catalog(
                {
                    "generated_at": (
                        "2026-08-26T18:30:58.560Z"
                    ),
                    "count": 2,
                    "programs": [
                        {
                            "program_id": XDEX_PROGRAM_ID,
                        }
                    ],
                }
            )

    def test_deployment_event_is_observational(self):
        parsed = parse_deployments(
            {
                "count": 1,
                "events": [
                    {
                        "type": "upgraded",
                        "program_id": (
                            "4RAa5RWXS3iYpfMEgMAKcHzGJeG2Er"
                            "XLgTYqAFRJ5Kta"
                        ),
                        "slot": 74366131,
                        "prev_slot": 74352409,
                        "detected_at": (
                            "2026-08-26T11:30:58.507Z"
                        ),
                        "name": "Jar",
                        "name_source": (
                            "instruction-vocabulary"
                        ),
                        "category": "Token",
                        "tx_count_24h": None,
                    }
                ],
            }
        )

        event = parsed["events"][0]

        self.assertEqual(
            event["evidence_tier"],
            DEPLOYMENT_EVENT,
        )
        self.assertEqual(
            event["event_type"],
            "upgraded",
        )
        self.assertEqual(
            event["slot"],
            74366131,
        )
        self.assertEqual(
            event["prev_slot"],
            74352409,
        )
        self.assertFalse(
            event["cmis_identity_promoted"]
        )

    def test_catalog_fetch_uses_exact_read_only_contract(self):
        payload = {
            "generated_at": (
                "2026-08-26T18:30:58.560Z"
            ),
            "count": 0,
            "programs": [],
        }

        get = RecordingGet(
            [FakeJSONResponse(payload)]
        )

        result = fetch_catalog(get=get)

        self.assertEqual(
            get.calls[0]["url"],
            (
                "https://x1agentsradio.xyz"
                + X1_AGENTS_RADIO_CATALOG_PATH
            ),
        )
        self.assertEqual(
            get.calls[0]["headers"],
            {"accept": "application/json"},
        )
        self.assertEqual(
            get.calls[0]["timeout"],
            15,
        )
        self.assertEqual(
            result["count"],
            0,
        )

    def test_http_failure_fails_closed(self):
        get = RecordingGet(
            [
                FakeJSONResponse(
                    {},
                    error=RuntimeError(
                        "service unavailable"
                    ),
                )
            ]
        )

        with self.assertRaises(
            X1AgentsRadioAPIError
        ):
            fetch_catalog(get=get)

    def test_provider_delegates_injected_transport(self):
        get = RecordingGet(
            [
                FakeJSONResponse(
                    {
                        "status": "ok",
                        "program": RADIO_PROGRAM_ID,
                        "registered_programs": 2,
                        "active_subscribers": 5,
                    }
                )
            ]
        )

        provider = X1AgentsRadioProvider(
            get=get
        )

        result = provider.get_health()

        self.assertTrue(result["operational"])
        self.assertEqual(len(get.calls), 1)


if __name__ == "__main__":
    unittest.main()
