# Current CMIS Project Status

Current reconciliation: **2026-09-06 12:00 America/New_York**.

## Accepted platform

- current capability contract: `1.27.0`;
- current flagship scan: `instant_x1_scan/v6`;
- universal public response freshness: `cmis_response_freshness/v1` on every CMIS response;
- Burn, Discovery, WHAT CHANGED? upstream facts, history, identity, deterministic risk, pre-trade analysis, concentration intelligence, and field-scoped freshness remain accepted under their established contracts;
- Bridge-to-XDEX utilization and cross-chain provenance are promoted for X1 Scout reliance;
- `trade_price_impact_intelligence/v1` is accepted through CMIS #498 / PR #530 + protected `cmis-core` #33;
- `large_trade_discovery/v1` is promoted through public PRs #532/#533 + protected `cmis-core` #35;
- GENIUS Act `regulatory_evidence/v1` is promoted under CMIS 1.26 through public PR #540 + protected `cmis-core` #43;
- CMIS Web Discovery v1-v11 remains accepted as bounded discovery below the verification boundary.

## Latest accepted live gate

### Protected cmis-core #41 — live Large-Trade → #498 handoff

**ACCEPTED.** The exact dedicated live workflow passed on run #7 at protected head `9ff63bcac15d9bd7f46868489f444508ed126c06`. PR #41 then merged as `f659f53f3d565bd5886dfae3e1a12370100cddc9`, and Issue #40 closed completed.

The accepted proof covers:

`Large-Trade ranking -> returned result -> protected materializer -> exact wallet/direction/execution evidence -> public #498 composition -> stored tpi evidence -> rebuilt ready handoff -> same evidence resolves through #498`.

The proof remains provider-scoped, pool-local, read-only, and fail-closed. It does not establish real-world wallet identity, whole-market causality, every-X1-DEX coverage, automatic risk conclusions, recommendations, or execution authority.

## Regulatory state

CMIS owns the current freshness-aware regulatory evidence service. It preserves primary-law/regulator provenance, rulemaking state, jurisdiction/framework scope, exact X1 asset identity, and evidence freshness.

It does **not** authorize:

- legal advice;
- COMPLIANT / NON_COMPLIANT labels;
- automatic token/issuer risk conclusions;
- execution.

ROBERTA adoption remains a separate upstream consumer gate.

## Website / ROBERTA dependency

ROBERTA regulatory adoption is accepted end to end through public PR #368, protected `roberta-core` PR #69, and reconciliation PR #369. Website claims must remain synchronized to accepted ROBERTA capabilities and preserve X1 Scout → CMIS as the authority path.

## Parallel work

Provider-gap research, X1Scroll fallback qualification, delayed-departure research, Theo transport work, and historical provider investigations remain parallel unless a separately accepted roadmap gate promotes them.

`execution_authorized=false`
