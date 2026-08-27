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

Still not accepted:

```text
freshness_policy_complete = false
freshness_verified = false
current_price_use_authorized = false
source_independence_verified = false
price_correctness_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

The next gate is an explicit freshness-policy decision with provenance for `max_age_ms`, `max_future_skew_ms`, and `minimum_eligible_slots`. Observed slot ages must not be used to back-fit those thresholds. Five relay slots remain same-system redundancy rather than five independent market sources.

## Active provider-gap work

Issue #30 remains the read-only/fail-closed provider-gap track.

Open branches:

- PR #242 — Warp Bridge proof-origin binding;
- PR #229 — bounded authenticated X1Scroll `getHealth`/`getSlot` access classification;
- PR #227 — FortiBlox provider-contract research.

These remain unaccepted until their exact evidence, contract, review, and merge gates pass.

## Roberta dependency/status

Roberta's Learning System Phases 1-10 and autonomous source-grounded Learning Plane controller are accepted on Roberta `main`.

That learning state never overrides CMIS for current prices, liquidity, supply, wallet state, provider health, token authorities, current risk, or other freshness-sensitive facts. Static learning and curriculum-scoped learned concepts are not CMIS/provider trust.

The compact cross-project authority baseline is synchronized in `ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md`.

## Roadmap now

### 1. Finish Oracle V2 freshness governance

- choose explicit freshness thresholds with provenance;
- keep timestamp semantics, freshness, price correctness, and source independence as separate facts;
- promote no current price until every downstream gate passes.

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
