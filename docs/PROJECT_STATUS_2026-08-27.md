# CMIS Project Status — 2026-08-27

## Executive status

CMIS remains the deterministic freshness-sensitive verification/intelligence backend beneath Roberta's Chain Scouts.

The accepted capability contract on `main` is **1.13.0**. The project is beyond the first public Verified Intelligence promotion and is now focused on provider-gap hardening, evidence depth, historical coverage, and narrowly verified read-only X1 provider evidence.

Controlled Execution remains locked/not started.


## Strategic roadmap update — 2026-08-28

CMIS is reprioritized toward the deterministic X1 services needed by Roberta's flagship product: Instant X1 Scan fields, a fresh X1.Ninja developer-API verification track, explicit holder/wallet intelligence promotion, an immutable Discovery Ledger, Early Warning service contracts, deterministic Compare support, bounded X1 ecosystem/network brief inputs, and a future developer intelligence API. X1 is the flagship CMIS surface. Solana remains maintained for accepted read-only capability and portability testing, while Solana product expansion and release are deferred to a future phase.

This is a **priority/product-direction update only**. It does not change accepted capability, promotion, evidence, risk, authority, or execution state on its own. Roadmap ownership: issue #318.

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
- Current CMIS capability contract: **1.13.0**.
- X1 `instant_x1_scan/v1`: bounded read-only ROBERTA-facing composition service introduced in CMIS 1.13.0. It composes accepted identity, market, tokenomics, local verified history, deterministic risk, Evidence Receipt, and Proof Score while leaving unverified holder/current-concentration facts explicit and execution unauthorized.

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

The selected production RPC path is the Official X1 RPC. #301's self-hosted-node contract/probes remain available but live self-hosted verification is deferred/optional; CMIS makes no RPC-redundancy or market-source-independence claim from that path. Issue #304 holder semantics is complete via PR #305. Issue #306 bounded Solana observed-pair liquidity and 24h-volume aggregation is complete via PR #307. Issue #308 Solana market observation freshness semantics is complete via PR #310. Issue #311 applies the accepted CMIS Jupiter current-price freshness policy in PR #312: max age 60 seconds and future skew 5 seconds. Issue #313 is complete via PR #314: an exact USDC/USD Pyth Core sponsored push-feed fixture is read through canonical Solana RPC and verifies feed/account/full-verification/price/confidence/exponent/Unix-second publish_time with a separate 60-second/5-second Pyth source policy. Issue #315 is implemented in PR #316 with an explicit five-second Jupiter–Pyth same-time operator window. When both source-specific freshness gates are FRESH and the exact fact-time delta is <=5 seconds, CMIS may verify cross-source time identity. Source independence, price-construction equivalence, current-price promotion, and execution authority remain false.

## Roberta dependency/status

Roberta's Learning System Phases 1-10 and autonomous source-grounded Learning Plane controller are accepted on Roberta `main`.

That learning state never overrides CMIS for current prices, liquidity, supply, wallet state, provider health, token authorities, current risk, or other freshness-sensitive facts. Static learning and curriculum-scoped learned concepts are not CMIS/provider trust.

The compact cross-project authority baseline is synchronized in `ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md`.

## Roadmap now

### 1. Productize X1 for Roberta

- Instant X1 Scan contract is implemented under #322 as `instant_x1_scan/v1` in CMIS 1.13.0;
- next: validate the documented X1.Ninja developer API as a fresh candidate provider under normal CMIS evidence/freshness/scope/independence rules;
- then advance holder/wallet intelligence promotion, Discovery Ledger, Early Warning, Compare, X1 Daily Brief inputs, and the later developer intelligence API through separate accepted gates.

### 2. Maintain Solana; release later

- preserve the accepted read-only Solana provider/runtime/test surface and regression coverage;
- defer broad Solana product expansion and release to a future phase;
- retain #317 Jupiter/Pyth source-independence and price-construction compatibility as future evidence work rather than the active implementation priority.

### 3. Continue evidence-depth work

- provider/source independence where required by active X1 services;
- historical redundancy/completeness diagnostics;
- holder/token-account semantics without beneficial-owner overclaim;
- exact route/pool/provider scope preservation.

### 3. Keep public-service promotion separately gated

No internal deterministic primitive becomes a Scout-callable service without a new accepted CMIS contract and separate Roberta/Scout adoption-readiness gate.

### 4. Controlled Execution

Still locked/not started.

## Core rule

**CMIS may strengthen verified evidence and intelligence, but every new provider fact, public service, Scout-reliance state, and execution capability remains separately proven and separately gated.**
