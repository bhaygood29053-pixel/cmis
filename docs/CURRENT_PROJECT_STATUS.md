# Current CMIS Project Status

Current reconciliation: **2026-09-06 12:00 America/New_York**.

## Accepted platform

- current capability contract: `1.26.0`;
- current flagship scan: `instant_x1_scan/v6`;
- Burn, Discovery, WHAT CHANGED? upstream facts, history, identity, deterministic risk, pre-trade analysis, concentration intelligence, and field-scoped freshness remain accepted under their established contracts;
- Bridge-to-XDEX utilization and cross-chain provenance are promoted for X1 Scout reliance;
- `trade_price_impact_intelligence/v1` is accepted through CMIS #498 / PR #530 + protected `cmis-core` #33;
- `large_trade_discovery/v1` is promoted through public PRs #532/#533 + protected `cmis-core` #35;
- GENIUS Act `regulatory_evidence/v1` is promoted under CMIS 1.26 through public PR #540 + protected `cmis-core` #43;
- CMIS Web Discovery v1-v11 remains accepted as bounded discovery below the verification boundary.

## Active acceptance gate

### Protected cmis-core #41 — live Large-Trade → #498 handoff

The deterministic protected suite is green, but the exact dedicated live workflow is still running.

Acceptance requires a real live result to prove:

`Large-Trade ranking -> returned result -> protected materializer -> exact wallet/direction/execution evidence -> public #498 composition -> stored tpi evidence -> rebuilt ready handoff -> same evidence resolves through #498`.

Until that exact live run passes, **PR #41 must not be merged** and the deterministic CI pass must not be treated as equivalent evidence.

## Regulatory state

CMIS owns the current freshness-aware regulatory evidence service. It preserves primary-law/regulator provenance, rulemaking state, jurisdiction/framework scope, exact X1 asset identity, and evidence freshness.

It does **not** authorize:

- legal advice;
- COMPLIANT / NON_COMPLIANT labels;
- automatic token/issuer risk conclusions;
- execution.

ROBERTA adoption remains a separate upstream consumer gate.

## Website / ROBERTA dependency

The ROBERTA public website already exposes the current human-facing token, comparison, risk, trade, wallet, history, burn, and generic-question experience. Live regulatory evidence is not yet advertised as an end-to-end website service because ROBERTA public #368 and protected `roberta-core` #68 remain the adoption boundary.

## Parallel work

Provider-gap research, X1Scroll fallback qualification, delayed-departure research, Theo transport work, and historical provider investigations remain parallel unless a separately accepted roadmap gate promotes them.

`execution_authorized=false`
