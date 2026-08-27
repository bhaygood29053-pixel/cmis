# CMIS Project Status — 2026-08-27

## Executive status

CMIS remains the deterministic freshness-sensitive verification/intelligence backend beneath Roberta's Chain Scouts.

The accepted capability contract on `main` is **1.12.0**. The project is beyond the first public Verified Intelligence promotion and is now focused on provider-gap hardening, evidence depth, historical coverage, and narrowly verified read-only X1 provider evidence.

Controlled Execution remains locked/not started.

## Accepted on CMIS `main`

- Phase 10 Solana read-only provider foundation: complete.
- Evidence Receipts + Proof Score: complete and separate from risk.
- Deterministic pre-trade trade-size analysis: complete, analysis-only.
- Phase 11 Verified Intelligence foundation: complete, read-only/non-promoted as a group.
- Phase 12 X1 `concentration_change_intelligence/v1`: complete/promoted for its exact X1 concentration-change scope.
- Deterministic descriptive concentration-direction classification: complete, internal/read-only/non-promoted.
- Direct wallet-relationship evidence: complete, internal/read-only/non-promoted, explicit non-ownership semantics.
- Concentration-threshold alert evidence: complete, internal/read-only/non-promoted.
- X1 `historical_compare` `all_available` and `all_available_pair`: complete from CMIS 1.10.0.
- X1 exact-mint normalized identity `x1_asset_identity/v1`: complete from CMIS 1.11.0.
- Verified provider historical price backfill: complete under the bounded CMIS 1.12.0 contract, price-only with explicit non-independence/non-completeness limits.
- Current CMIS capability contract: **1.12.0**.

There is still no accepted next public alert/intelligence promotion by implication.

## Oracle V2 status

Oracle V2 has advanced materially under Issue #272 while remaining non-promoted as a current-price source.

Accepted/read-only evidence now establishes:

- live X1 executable program identity;
- expected state PDA and owner;
- exact 618-byte state layout and discriminator;
- six assets × five relay slots;
- decimals and stored Oracle public key;
- timestamp-unit semantics promoted as Unix milliseconds under the accepted evidence-bound policy;
- deterministic current-slot age calculation from the verified timestamp unit.

Freshness governance is now accepted and applied:

```text
max_age_ms = 60000
max_future_skew_ms = 5000
minimum_eligible_slots = 3
freshness_policy_complete = true
freshness_policy_applied = true
freshness_verified = true
```

The latest live run classified all 30 observed relay slots as stale, so no current-price median was eligible. Still not accepted:

```text
current_price_use_authorized = false
source_independence_verified = false
price_correctness_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

The next Oracle gate is conditional on new policy-eligible live slots. If they appear, rerun the accepted freshness evidence and then perform exact same-fact identity/unit/time price comparison. Five relay slots remain same-system redundancy rather than five independent market sources.

## Active provider-gap work

Issue #30 remains the read-only/fail-closed provider-gap track.

Recent cleanup is complete:

- PR #242 — Warp Bridge closed as not currently verifiable;
- PR #229 — X1Scroll closed and removed from CMIS integration scope;
- PR #227 — FortiBlox closed/archive candidate research;
- PR #299 — repository/provider-state reconciliation for X1Scroll merged.

The next new technical item is bounded verification of the official/self-hosted X1 read-only node for history and streaming redundancy. This must not be mislabeled as independent market-price evidence merely because it is a separate node deployment.

## Roberta dependency/status

Roberta's Learning System Phases 1-10 and autonomous source-grounded Learning Plane controller are accepted on Roberta `main`.

That learning state never overrides CMIS for current prices, liquidity, supply, wallet state, provider health, token authorities, current risk, or other freshness-sensitive facts. Static learning and curriculum-scoped learned concepts are not CMIS/provider trust.

The compact cross-project authority baseline is synchronized in `ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md`.

## Roadmap now

### 1. Verify self-hosted X1 history/streaming redundancy

- verify exact node configuration/identity and bounded read-only RPC history methods;
- verify block subscription commitment/finality, reconnect, ordering, duplicates, gaps, and backfill behavior;
- preserve infrastructure redundancy separately from market-source independence.

### 2. Continue evidence-depth work

- provider/source independence;
- historical redundancy/completeness diagnostics;
- holder/token-account semantics without beneficial-owner overclaim;
- exact route/pool/provider scope preservation;
- field-by-field Solana maturity.

### 3. Keep public-service promotion separately gated

No internal deterministic primitive becomes a Scout-callable service without a new accepted CMIS contract and separate Roberta/Scout adoption-readiness gate.

### 4. Controlled Execution

Still locked/not started.

## Core rule

**CMIS may strengthen verified evidence and intelligence, but every new provider fact, public service, Scout-reliance state, and execution capability remains separately proven and separately gated.**
