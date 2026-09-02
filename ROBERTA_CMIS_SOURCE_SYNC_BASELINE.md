# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-01 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public Roberta and CMIS repositories. Repository-local roadmap, contract, status, and private-core documents remain authoritative for implementation details.

## Product identity and authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the canonical public-facing product name.
- X1 Scout, Solana Scout, and CMIS remain architectural component names beneath Roberta.
- Canonical authority path: `User / transport -> Roberta -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- Roberta owns orchestration, policy coordination, specialist selection, learning coordination, approval boundaries, and final synthesis.
- Chain Scouts own chain-specific planning and interpretation; they do not manufacture facts.
- CMIS owns deterministic freshness-sensitive facts, evidence, Evidence Receipts, Proof Scores, risk, capability state, historical intelligence, and bounded analysis-only pre-trade calculations.
- Fresh accepted CMIS/provider evidence overrides remembered, retained, RAG, source-mastery, Pyramid, or conversational live values when freshness matters.
- Missing evidence remains unknown/unavailable and is never converted into zero, false, or a model estimate.
- Proof Score remains separate from risk.
- Controlled Execution remains locked/not started. `execution_authorized=false` remains invariant.

## Current synchronized accepted state

### ROBERTA public + protected core

Current accepted public head observed before this baseline update: `c5c1ecc3b106d6a2111156b09a4d24f1c910bd4b`.
Current accepted protected `roberta-core` head observed before this baseline update: `822d0be6537f9dba8cb5dc12a6b947f24ca75e0b`.

Accepted product milestones include:

- CMIS capability boundary `1.13.0` through X1 Scout;
- first-class X1 `instant_x1_scan/v1` adoption through the existing Roberta -> X1 Scout -> CMIS path;
- deterministic `instant_x1_scan_product_view/v1` projection with unknown/unverified values preserved;
- deterministic `x1_compare/v1` product contract and first-class X1 Compare workflow;
- accepted public Canonical ROBERTA Decision Object v1 contract plus protected `roberta_decision/v1` implementation;
- deterministic Human ROBERTA and Machine ROBERTA projections from the same canonical Decision Object for the first Instant X1 Scan tracer bullet;
- Machine projection contract `roberta_intelligence/v1` with explicit null/unavailable preservation and bounded evidence depth;
- no new ROBERTA trade-decision policy in the Decision Object tracer: source risk recommendation is preserved, `reason_codes=[]`, and `policy_applied=false`;
- merged and hardened X1 Scout `x1_burn_intelligence/v1` tracer plus protected Canonical ROBERTA Decision Object / Human-Machine BURN integration;
- Learning System Phases 1-10, autonomous source-grounded Learning Plane, mastered-run replay protection, authoritative read-only training telemetry, and bounded scheduler/queue foundation;
- repaired protected-core CI that validates Python 3.11, Python 3.12, and the pinned public-shell overlay rather than testing the protected overlay as a standalone host;
- public-shell/private-core migration closure.

Roberta does not gain a direct provider or direct product-level CMIS shortcut from these milestones. Human/Machine presentation remains a projection layer, not a competing fact/risk authority.

### CMIS public `main`

Current accepted public head observed before this baseline update: `9392eb45983eea816701babbe39b29c2d85850f4`.

Current capability contract advances to `1.15.0` with first-class X1 Burn Intelligence. Accepted milestones include:

- `concentration_change_intelligence/v1` as the narrow promoted X1 intelligence wrapper;
- `historical_compare` modes `window`, `all_available`, and `all_available_pair`;
- `x1_asset_identity/v1` exact-mint identity normalization;
- bounded verified-provider historical price backfill semantics;
- X1 `instant_x1_scan/v1`, read-only/composition-only and fail-closed;
- first-class X1 `burn_intelligence/v1`, preserving deterministic 1h/24h/7d/30d burn windows, burn event/count amounts, burn-to-emission and net-issuance state, 24h/7d/30d period-over-period burn change, coverage, circulation context, and burn-time valuation without recomputation;
- verified scanner fact-time coverage wired into CMIS tokenomics burn metrics;
- deterministic circulating-supply evidence based only on a complete independently verified excluded-token-account universe, while preserving verified total supply if circulation is unavailable;
- deterministic historical burn-time valuation under `verified_burn_time_price_evidence_v1`, requiring exact verified burn identity and exact compatible burn-time price fact time, with native/XNT and USD completeness independently gated and no current-price/nearest-price/interpolation fallback;
- public-shell/private-core migration closure.

Accepted burn metrics do not imply complete lifetime burn coverage. Current on-chain supply is not reduced a second time by burn totals. Burn valuation is complete only where every burn event in the asserted scope has compatible verified price evidence for the denomination being claimed.

## Active cross-project work

### 1. Roberta burn-intelligence consumption

CMIS burn arithmetic, coverage semantics, period-over-period changes, circulating-supply context, and exact burn-time valuation are accepted upstream. The first X1 Scout `x1_burn_intelligence/v1` tracer is merged on Roberta `main`.

ROBERTA PR #295 is merged, and protected `roberta-core` #23 maps BURN into the Canonical ROBERTA Decision Object and Human/Machine renderers. Roberta must preserve CMIS amounts, comparison denominators/states, valuation completeness, Evidence Receipt / Proof Score lineage, and unknown/partial states without recalculating burns or historical prices.

Burn output must not be squeezed into Instant X1 Scan semantics by implication.

### 2. CMIS delayed catalog-departure evidence — PR #363

PR #363 remains open. Reconciled exact head: `208756f4880a9d6e47d377b19abab37701a83f2a`.

- the five-independent-departure floor remains fixed;
- the pre-BEFORE lookback remains 900 seconds with max 100 signatures per exact vault;
- unique-latest-swap and fail-closed ambiguity requirements remain unchanged;
- current collection settings may monitor up to 150 pools, collect up to 400 snapshots, and target 40 price-only candidates; 40 candidates is a collection target, not a promotion threshold;
- routed/multi-AMM evidence does not authorize classifier widening without a separately accepted deterministic contract.

Do not merge #363 merely to obtain a green workflow. Its live evidence gate must satisfy the accepted contract.

### 3. XDEX automated-order/routed-family investigation — Issue #374

Issue #374 remains diagnostic-only. Bounded routed-target evidence does not authorize TWAP, limit, take-profit, stop-loss, or other user-level execution-family labels without family-specific deterministic evidence. `classification_change_authorized=false` remains authoritative.

### 4. X1 Discovery Ledger

Public CMIS PR #365 and protected `cmis-core` PR #6 remain pending.

The intended `x1_discovery_ledger/v1` foundation preserves exact X1 mint identity, immutable first/subsequent verified observation semantics, verified fact time separate from recorded time, deterministic replay/idempotency, Evidence Receipt / Proof Score lineage, and explicit non-lifetime/non-launch semantics.

The public/private boundary must not be weakened to bypass protected-runtime validation requirements.

### 5. Roberta Learning Plane operational hardening

Protected `roberta-core` PR #10 is accepted: bounded scheduler admission plus durable restart-safe queue state.

Protected `roberta-core` PR #11 remains pending for deterministic one-cycle worker orchestration. It is not an always-on daemon and does not yet make the production autonomous-training controller the default worker. Cooperative budget checkpoints, production controller integration, and broader background scheduling/load-throttling remain separately gated.

### 6. Roberta transport

Native Telegram adapter PR #264 remains pending. Telegram is a transport boundary only: requests must route through Roberta/private-core orchestration, never directly to CMIS or a provider. No OpenClaw dependency is accepted.

## Near-term synchronized roadmap

1. **Burn intelligence productization:** promote CMIS `burn_intelligence/v1` as the canonical first-class source, then switch X1 Scout to that dedicated CMIS service while preserving the accepted Canonical Decision Object and Human/Machine projections without Roberta-side fact recomputation.
2. **Decision Object expansion:** keep SCAN, COMPARE, BURN, and later Discovery/Watch workflows on one canonical intelligence basis, adding adapters one at a time.
3. **Delayed price evidence:** resolve #363 using the existing strict evidence thresholds; consume routed target-leg evidence only through a separately reviewed classifier change if the evidence supports it.
4. **Discovery:** finish public #365 + protected `cmis-core` #6, then build Scout-facing discovery/history workflows only after the foundation is accepted.
5. **Early Warning / What Changed?:** build deterministic CMIS evidence contracts on accepted Discovery/history primitives; keep presentation/policy in Roberta.
6. **Execution-quality evidence:** accumulate quote-to-executed-swap matching, realized-slippage evidence, and comparable-trade statistics before any expected-slippage contract is considered.
7. **Learning operations:** complete bounded one-cycle orchestration and cooperative budget checkpoints before any broader unattended background scheduler.
8. **Solana:** maintain as a secondary read-only portability track; X1 capability/promotion state does not transfer automatically.
9. **Controlled Execution:** remains locked/not started.

## Provider and evidence boundary

Oracle V2 structural and freshness-governance evidence does not currently authorize it as a CMIS current-price source. Provider fact-time, freshness, same-fact source independence, priceUsd, USD-liquidity/TVL, complete archive coverage, and complete asset-lifetime claims remain unavailable unless separately proven by their exact contracts.

Distinct provider labels do not prove source independence. Agreement and independence remain separate evidence dimensions.

## Runtime split status

Both projects have completed the public-shell/private-core migration and historical source cleanup. Protected implementation belongs in `roberta-core` / `cmis-core`; public repos carry contracts, public orchestration/shell surfaces, evidence rules, documentation, and fail-closed integration boundaries. Source protection changes packaging only and never promote facts, risk, services, wallets, or execution authority.

## Core sync rule

**Roberta may learn, orchestrate, and project accepted intelligence; CMIS may verify changing chain facts. Neither learning, presentation, diagnostics, roadmap state, nor an open PR self-promotes into a new authority boundary. Fresh accepted CMIS/provider evidence wins for freshness-sensitive state, and every public-service, Scout-reliance, operational-trust, wallet, or execution promotion remains separately gated.**

## Live repository reconciliation — 2026-09-01 11:20 America/New_York

These heads were observed after the repository-local roadmap/status updates and immediately before this mirrored baseline commit:

- CMIS public `main`: `9392eb45983eea816701babbe39b29c2d85850f4`
- ROBERTA public `main`: `c5c1ecc3b106d6a2111156b09a4d24f1c910bd4b`
- protected `roberta-core` `main`: `822d0be6537f9dba8cb5dc12a6b947f24ca75e0b`
- protected `cmis-core` `main`: `b044a651e8aa99337365e6114e10df1c2fd6e9ee`

### Live synchronized gate state

- **CMIS burn valuation:** PR #377 is merged/accepted.
- **ROBERTA BURN productization:** PR #295 is open, clean, and CI green; this is the immediate ROBERTA product gate.
- **CMIS delayed departure evidence:** PR #363 is open; deterministic tests are green while the live X1.Ninja Delayed Vault Departure Evidence workflow remains in progress. Strict evidence thresholds remain unchanged.
- **Discovery Ledger:** CMIS public #365 is clean and public tests pass; protected `cmis-core` #6 still has failing private-core CI, so the pair is not accepted.
- **Learning Plane:** protected `roberta-core` #11 still has failing private-core CI; broader unattended scheduling remains blocked.
- **Telegram:** ROBERTA #264 remains open and dirty/non-mergeable. Telegram is transport only and no OpenClaw dependency is accepted.
- **Controlled Execution:** locked/not started; `execution_authorized=false`.

### Synchronized priority order

1. Accept ROBERTA #295 and complete the BURN Decision Object tracer over CMIS-owned burn evidence.
2. Keep CMIS #363 running under the existing evidence contract; diagnose failures without weakening thresholds.
3. Repair `cmis-core` #6 CI and accept Discovery Ledger public/private pair.
4. Repair `roberta-core` #11 CI and accept bounded one-cycle training orchestration.
5. Add Discovery, WHAT CHANGED?, and Early Warning only after their CMIS evidence foundations are accepted.
6. Accumulate execution-quality evidence before any expected-slippage contract.
7. Rebase/repair Telegram after the core intelligence gates.
8. Keep Solana secondary/read-only and Controlled Execution locked.
