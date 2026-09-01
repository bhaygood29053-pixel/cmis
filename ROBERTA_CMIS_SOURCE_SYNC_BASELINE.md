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

### ROBERTA public `main`

Current accepted public head at reconciliation: `ef62246b49ef9ecca3d3e7546691e86e89bb0818`.

Accepted product milestones include:

- CMIS capability boundary `1.13.0` through X1 Scout;
- first-class X1 `instant_x1_scan/v1` adoption through the existing Roberta -> X1 Scout -> CMIS path;
- deterministic `instant_x1_scan_product_view/v1` Human-facing projection with unknown/unverified values preserved;
- deterministic `x1_compare/v1` product contract;
- first-class X1 Compare workflow using two validated Instant X1 Scan views and, only for explicit full-history intent, one capability-gated CMIS `all_available_pair` request;
- Human ROBERTA + Machine ROBERTA two-face roadmap under one canonical intelligence/decision layer;
- planned BURN workflow consumption of accepted CMIS burn intelligence without Roberta recomputation;
- Learning System Phases 1-10, autonomous source-grounded Learning Plane, mastered-run replay protection, and authoritative read-only training telemetry;
- public-shell/private-core migration closure.

Roberta does not gain a direct provider or direct product-level CMIS shortcut from these milestones.

### CMIS public `main`

Current accepted public head at reconciliation: `aba62285c3074f2d0628111eb33a8db0e9725782`.

Current capability contract remains `1.13.0`. Accepted milestones include:

- `concentration_change_intelligence/v1` as the narrow promoted X1 intelligence wrapper;
- `historical_compare` modes `window`, `all_available`, and `all_available_pair`;
- `x1_asset_identity/v1` exact-mint identity normalization;
- bounded verified-provider historical price backfill semantics;
- X1 `instant_x1_scan/v1`, read-only/composition-only and fail-closed;
- deterministic X1 burn metrics for 1h/24h/7d/30d windows, burn event/count amounts, burn-to-emission and net-issuance state, and 24h/7d/30d period-over-period burn change;
- verified scanner fact-time coverage wired into CMIS tokenomics burn metrics;
- deterministic circulating-supply evidence based only on a complete independently verified excluded-token-account universe, while preserving verified total supply if circulation is unavailable;
- deterministic historical burn-time valuation under `verified_burn_time_price_evidence_v1`, requiring exact verified burn identity and exact compatible burn-time price fact time, with native/XNT and USD completeness independently gated and no current-price/nearest-price/interpolation fallback;
- public-shell/private-core migration closure.

Accepted burn metrics do not imply complete lifetime burn coverage. Current on-chain supply is not reduced a second time by burn totals. Burn valuation is complete only where every burn event in the asserted scope has compatible verified price evidence for the denomination being claimed.

## Active cross-project work

### 1. Roberta burn-intelligence consumption

CMIS PR #377 is accepted on `main`. Historical burn-time valuation now belongs to CMIS and remains evidence-bound and fail-closed.

The next burn-product gate is a separately reviewed X1 Scout/Roberta consumption path for BURN and WHAT CHANGED? views. Roberta must preserve CMIS amounts, period-over-period changes, valuation completeness, Evidence Receipt / Proof Score lineage, and unknown/partial states without recalculating burn or price values.

### 2. CMIS delayed catalog-departure evidence — PR #363

PR #363 remains open. Reconciled exact head: `208756f4880a9d6e47d377b19abab37701a83f2a`.

- deterministic/full Liquidity Scout tests are green on that head;
- X1.Ninja Delayed Vault Departure Evidence remains an evidence-accumulation gate, not a software-success shortcut;
- the five-independent-departure floor, fixed 900-second pre-BEFORE lookback, max 100 signatures per exact vault, unique-latest-swap rule, and fail-closed ambiguity handling remain unchanged;
- current collection settings may monitor up to 150 pools, collect up to 400 snapshots, and target 40 price-only candidates; 40 candidates is a collection target, not a promotion threshold;
- routed/multi-AMM evidence does not authorize classifier widening without a separately accepted deterministic contract.

Do not merge #363 until its exact-head live evidence gate and review requirements are satisfied. Do not lower evidence thresholds merely to obtain a passing workflow.

### 3. XDEX automated-order/routed-family investigation — Issue #374

Issue #374 remains open and diagnostic-only. Bounded routed-target evidence does not authorize TWAP, limit, take-profit, stop-loss, or other user-level execution-family labels without family-specific deterministic evidence. `classification_change_authorized=false` remains authoritative.

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

1. **X1 flagship productization:** keep Instant X1 Scan and Compare as accepted Roberta foundations; build the canonical Roberta Decision Object and Human/Machine renderers without creating a second fact authority.
2. **Burn intelligence productization:** add a separately gated X1 Scout/Roberta consumption path for accepted CMIS burn metrics and burn-time valuation, then expose BURN and WHAT CHANGED? views without Roberta-side recomputation.
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

**Roberta may learn and orchestrate; CMIS may verify changing chain facts. Neither learning, diagnostics, roadmap state, nor an open PR self-promotes into a new authority boundary. Fresh accepted CMIS/provider evidence wins for freshness-sensitive state, and every public-service, Scout-reliance, operational-trust, wallet, or execution promotion remains separately gated.**
