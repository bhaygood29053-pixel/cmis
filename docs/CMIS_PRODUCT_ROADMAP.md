# CMIS Product & Premium Service Roadmap

Last reconciled: 2026-09-03 (America/New_York)

This is the authoritative living CMIS roadmap. Open branches and provider investigations are not accepted capability until their contract, CI, review, and merge gates pass.

## Product naming invariant

The public-facing product name is **ROBERTA — Verified On-Chain Intelligence**. The former working product name **X1 Intelligence Service** is retired. **CMIS** remains the deterministic backend/repository identity, while X1 Scout and Solana Scout remain chain-specialist component names. Product naming does not change the authority path, capability promotion state, verification semantics, or execution boundary.

## Canonical architecture

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

The repository began as Liquidity Scout. The `liquidity_scout` Python namespace remains a compatibility implementation detail; it is not a separate authority layer.

Roberta owns orchestration/final synthesis and bounded learning-workflow coordination. Chain Scouts own chain-specific planning/interpretation. CMIS owns deterministic verified facts, evidence, risk, capability eligibility, historical intelligence, and bounded analysis-only pre-trade calculations. Providers remain beneath CMIS.

Fresh accepted CMIS/provider facts override remembered, retained, source-mastery, Pyramid, or conversational live values. Missing evidence remains unknown/unavailable and is never zero-filled. Risk remains separate from Proof Score.

## Current accepted roadmap state

Accepted milestones on `main`:

- **CMIS Phase 10 — Solana read-only provider foundation: COMPLETE.**
- **Evidence Receipts + Proof Score: COMPLETE.**
- **X1 evidence gaps: explicitly classified/fail-closed.**
- **Deterministic pre-trade trade-size analysis: COMPLETE.**
- **CMIS Phase 11 — read-only Verified Intelligence foundation: COMPLETE.**
- **CMIS Phase 12 — first narrow public-service / Scout-reliance promotion: COMPLETE for X1 `concentration_change_intelligence/v1`.**
- **Deterministic descriptive intelligence classification: COMPLETE, internal/read-only/non-promoted.**
- **Deterministic direct wallet-relationship evidence with explicit non-ownership semantics: COMPLETE, internal/read-only/non-promoted.**
- **Deterministic concentration-threshold alert evidence (#263/#264): COMPLETE, internal/read-only/non-promoted.**
- **Persistent concentration Early Warning foundation (#396 / public #397 / protected `cmis-core` #15): COMPLETE, internal/read-only/non-promoted.** Exactly two distinct compatible CMIS-owned concentration-change intelligence observations are required; strict fact-time order, persistence-window bounds, latest-evidence freshness, duplicate/replay rejection, and exact Evidence Receipt / Proof Score lineage are enforced. `WATCH`/`CLEAR` are warning states, not risk severity.
- **CMIS deterministic engineering workflow / three-axis review: ADOPTED and repository-authoritative.**
- **X1 all-available verified historical profiles and overlapping pair comparison: COMPLETE under `historical_compare` modes in CMIS `1.10.0`.**
- **X1 exact-mint normalized asset identity: COMPLETE under `x1_asset_identity/v1` in CMIS `1.11.0`.** Exact mint is the fungible identity root; Metaplex and XDEX descriptors remain separately sourced; same-mint descriptor conflict is partial; XDEX unavailability is not misreported as mint absence.
- **Cross-chain asset provenance foundation: COMPLETE under `cross_chain_asset_provenance/v1` via Issue #402 / PR #403.** The primitive validates exact chain-scoped origin/current identities, ordered cross-chain hop continuity, representation depth, and bridge/custody dependency labels while rejecting symbol/name identity shortcuts. It is structural evidence only: live bridge state, backing, custody truth, source independence, supply/flow, public-service promotion, Scout reliance, and execution remain unverified/unauthorized.
- **Verified Bridge Route Evidence / Warp Qualification foundation: COMPLETE internally via Issue #405 / PR #406 under `bridge_route_evidence/v1` and `warp_bridge_qualification/v1`.** Exact provenance-hop route id, source/destination chain-scoped asset identity, exact source URL binding, source-vs-collection timestamps, freshness, deterministic evidence identity, and candidate route/backing/custody fields are fail-closed. Warp itself is **not provider-qualified**: `warp_qualified=false`, `qualification_state=blocked_endpoint_semantics`, and the accepted Warp semantic-contract registry has zero entries. Issue #407 is the next exact gate.
- **X1 verified-provider historical price backfill: COMPLETE under the bounded CMIS `1.12.0` contract.** Backfill is price-only and preserves non-independence, non-archive-completeness, non-continuity, historical stable-quote uncertainty, and non-lifetime-completeness limits.
- **Oracle V2 structural X1 contract verification and freshness governance: COMPLETE for the accepted bounded evidence contracts.** Timestamp-unit semantics are verified as Unix milliseconds; the explicit current-price freshness policy is selected/applied (`max_age_ms=60000`, `max_future_skew_ms=5000`, `minimum_eligible_slots=3`). The latest live run classified all 30 relay slots stale, so current-price authority remains unpromoted.
- **CMIS capability contract: `1.18.0`.** Burn Intelligence (`burn_intelligence/v1`) remains accepted under 1.15.0, Discovery Intelligence (`discovery_intelligence/v1`) under 1.16.0, field-scoped current-market freshness under 1.17.0, and pull-only Concentration Warning Intelligence (`concentration_warning_intelligence/v1`) under 1.18.0.
- **Instant X1 Scan: COMPLETE as `instant_x1_scan/v3`.** v3 wraps the accepted v2 scan rather than forking identity/history/tokenomics/risk logic, and adds only `x1_current_market_freshness/v1`. Price freshness can be verified under explicit provider fact-time/value-linkage gates; liquidity, rolling 24h volume, and rolling transaction freshness remain unverified under 1.17.
- **Six-phase public-shell/private-core migration: COMPLETE.** Protected CMIS implementation is removed from active public branch/tag history, public package boundaries fail closed without the required private core, and no public reconstruction fallback is accepted.
- **Roberta adoption/readiness of the promoted X1 concentration-change service: COMPLETE.**
- **Paired Roberta PR #226 / CMIS PR #269 architecture/source-of-truth reconciliation: COMPLETE.**
- **Roberta autonomous Learning Plane upstream dependency: ACCEPTED on Roberta `main` via PR #228; post-merge Roberta source/roadmap reconciliation is accepted via PR #231.**
- **Parallel X1 provider-gap work (#30): OPEN, read-only/fail-closed.**
- **Controlled transaction execution: UNAUTHORIZED / not an active CMIS milestone.**

**Concentration Warning Intelligence v1 is accepted end-to-end through ROBERTA.** CMIS 1.18 remains the deterministic warning authority; public ROBERTA #318 and protected `roberta-core` #28 preserve the same pull-only WATCH/CLEAR evidence through X1 Scout and the Canonical Decision Object without recomputation. Push/delivery mechanisms remain a separate future gate.

## Phase 11 foundation

The core `intelligence_foundation` remains read-only and non-promoted as a group:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
```

Accepted primitives include:

- exact top-account concentration observations and compatible numeric changes;
- neutral wallet-activity facts;
- sanitized sparse historical intelligence and compatible-series comparison;
- evidence-bound conclusions with content-addressed Evidence Receipts / Proof Scores;
- deterministic explicit-policy concentration-threshold evaluation.

These primitives do not automatically become public Scout services and do not authorize behavioral/ownership labels.

## Phase 12 first promoted intelligence service

CMIS `1.9.0` promotes exactly one narrow X1 wrapper:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
execution_authorized = false
```

Solana remains unavailable/non-callable/non-promoted for this service.

The wrapper resolves canonical CMIS-owned intelligence evidence internally and revalidates it before returning facts/proof. Caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, provider assertions, behavioral labels, or replacement verification state are rejected as trust shortcuts.

The service does not establish unique-holder totals or beneficial owners. Token-account concentration remains token-account concentration. Optional threshold output is deterministic policy evaluation, not risk. Proof Score is not risk.

## Post-Phase-12 internal deterministic foundations

Three additional contracts are accepted on `main` without public-service or Scout-reliance promotion:

1. **Descriptive intelligence classification** — classifies only the exact verified concentration direction supported by canonical CMIS evidence and does not infer behavior, ownership, intent, fraud, manipulation, scam, or risk.
2. **Direct wallet-relationship evidence** — represents verified observed direct token-transfer interactions between exact chain identities and explicitly preserves non-ownership/non-beneficial-owner semantics.
3. **Concentration-threshold alert evidence** — evaluates one canonical concentration-change evidence object against exact chain/asset identity, explicit `basis_points` threshold units, deterministic GT/GTE comparator semantics, canonical freshness, single-observation persistence, and content-addressed evidence/alert identity.
4. **Persistent concentration Early Warning evidence** — requires exactly two distinct compatible CMIS-owned concentration-change intelligence evidence ids, strict increasing fact-time order, explicit persistence-window and latest-age policies, verified Receipt freshness with no unresolved fields, duplicate/replay protection, preserved Receipt/Proof lineage, deterministic `cw_...` identity, and `WATCH`/`CLEAR` state. It remains non-promoted and non-deliverable.

These foundations remain equivalent to:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

They do not change the capability manifest and do not grant Roberta or a Chain Scout a new callable service.

## Verified-data foundation

### X1 / XDEX

X1 is the mature CMIS surface. Accepted capabilities include, where exact evidence contracts permit:

- asset/pool identity;
- exact-mint X1 identity normalization using verified Metaplex Token Metadata plus separately preserved exact-mint XDEX market representation under `x1_asset_identity/v1`;
- market reporting/ranking;
- tokenomics/authority evidence;
- transaction/trade verification tooling;
- persisted verification evidence;
- deterministic risk;
- historical comparison, including explicit-window, all-available verified-observation profiles, and overlapping pair comparison;
- bounded activity;
- trade-size analysis;
- selected exact-route price-impact/fee facts;
- fail-closed quote/history semantic gates.

For fungible X1 tokens, exact mint remains the canonical identity root. Metaplex name/symbol/URI are descriptive on-chain metadata; XDEX name/symbol are provider market representation. Agreement does not establish legitimacy or safety, different mints are never reconciled by labels, and provider outage remains distinct from proven absence.

Program-, pool-, route-, provider-, token-account-, or sample-scoped evidence remains distinct from asset-wide/global truth.

### Solana

Solana Phase 10 remains a bounded read-only provider/runtime foundation beneath the same CMIS architecture. Accepted components include:

- exact-mint identity;
- SPL Token / Token-2022 handling;
- canonical supply/authority evidence;
- configured Jupiter/Helius/DEX Screener evidence;
- deterministic cross-source price/supply checks;
- canonical top-20 normalization for largest-token-account results while preserving provider-returned cardinality;
- provenance-safe history;
- bounded/partial market/tokenomics/risk/history services.

Solana does not inherit X1 capabilities or promotion state.

## CMIS 1.10.0 historical intelligence extension

The existing `historical_compare` public service now supports:

- `window` — existing explicit 24h / 7d / 30d deterministic metric comparison;
- `all_available` — one asset summarized across every verified observation currently stored by CMIS;
- `all_available_pair` — two assets compared only over their overlapping verified CMIS observation window with aligned-anchor tolerance.

The runtime CMIS gateway accumulates verified price, liquidity, 24h volume, 24h transaction count, and holder observations with duplicate throttling. Full-history output includes exact stored start/end times, observation counts, sampled minima/maxima/change, sampled price drawdown, and observed gap diagnostics.

### CMIS 1.12.0 verified provider-price backfill

A bounded verified-provider price backfill may now extend the stored price series. CMIS accepts only XDEX historical close observations that match the exact provider pair/time scope and cross-check against the corresponding X1.Ninja OHLCV close. Direct configured USD-stable quote pools are preferred; an asset/XNT plus XNT/USD-stable two-leg path is allowed only when both legs pass the same checks. Imported observations retain source, pair, quote-unit, and evidence metadata in a dedicated store; conflicting same-timestamp provider prices fail closed.

This remains **partial provider-history coverage**, not complete lifetime history. Liquidity and volume history are not imported. Provider source independence, archive/range completeness, continuous coverage, and historical stable-quote one-dollar behavior remain unverified. `full_asset_lifetime_verified=false` and `continuous_coverage_verified=false` remain authoritative unless separate gates prove otherwise.

## Active X1 provider-gap track — Issue #30

Provider-gap work remains read-only and fail-closed. Closed research branches and historical provider claims do not create accepted capability.

### Closed provider-candidate cleanup

- **PR #242 — Warp Bridge:** closed as not currently verifiable. No exact provenance-approved machine-readable read contract is accepted.
- **PR #229 — X1Scroll:** closed and removed from CMIS integration scope because the required API key was unavailable; the verification job stopped before any provider request.
- **PR #227 — FortiBlox:** closed/archive candidate research. No exact reproducible provider-owned endpoint/response contract is accepted.

### Issue #272 — Oracle V2 read-only price evidence ⚠️ Freshness governance complete; current price still unavailable

CMIS has independently verified the declared X1 program/state contract shape through X1 RPC, including executable program identity, state ownership, PDA/layout, six-asset × five-relay structure, decimals, stored Oracle key, and Unix-ms timestamp semantics.

The accepted production freshness policy is explicit and provenance-bearing:

```text
max_age_ms = 60000
max_future_skew_ms = 5000
minimum_eligible_slots = 3
```

The latest live governance run applied that policy successfully and classified all 30 observed relay slots as stale. Therefore no Oracle V2 current-price median was eligible and:

```text
freshness_policy_complete = true
freshness_policy_applied = true
freshness_verified = true
current_price_use_authorized = false
price_correctness_verified = false
source_independence_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

Five relay slots remain same-system redundancy, not five independent market sources. The next Oracle gate occurs only when policy-eligible live slots appear: rerun the freshness evidence, then perform exact same-fact identity/unit/time comparison against accepted CMIS X1 evidence. Do not weaken the policy to manufacture eligibility.

### Existing non-promotional observations

Recent bounded evidence still shows:

- tested X1.Ninja SSE credential: HTTP 403 / access denied;
- XENCAT holder-looking provider candidate: 116;
- RPC token-account candidate: 180;
- unique token-account-authority candidate: 174.

Those observations do **not** establish:

- SSE event semantics;
- holder totals;
- wallet identity;
- beneficial ownership;
- provider/RPC enumeration completeness;
- source independence.

Warp Bridge machine-readable operational state remains unavailable until an exact provenance-approved read contract and semantic fixture are accepted.
The accepted `cross_chain_asset_provenance/v1`, `bridge_route_evidence/v1`, and `warp_bridge_qualification/v1` foundations now define the deterministic identity, route, source, timestamp, backing, and custody gates any future Warp evidence must satisfy. They do **not** verify current Warp operational state. Issue #407 owns the remaining exact-endpoint semantic-contract blocker.

## Public-shell/private-core migration closure

The six-phase CMIS public-shell/private-core migration is complete. Active public branch/tag history was rewritten to remove protected implementation paths, steady-state public package boundaries fail closed without the required private core, and migration-era public reconstruction is no longer a normal runtime/test path. This migration changes source protection and deployment packaging only; it does not promote a service, add provider authority, alter proof/risk semantics, or authorize execution.

## Evidence quality and proof rules

Evidence Receipts preserve provenance, verification state, scope, freshness, disagreements, limitations, unresolved fields, and content-addressed identity.

Core rules:

1. Provider output is candidate evidence until accepted verification exists.
2. Unknown remains unknown.
3. Missing evidence is not zero or false.
4. Source independence is explicit fact-specific evidence; distinct labels do not prove it.
5. Same-fact agreement and source independence are separate dimensions.
6. `independent_agreement_verified` requires both accepted same-fact agreement and accepted independence.
7. Proof Score remains separate from risk.
8. Route/pool/provider/sample scope is not global asset scope.
9. Chain provenance is never erased by cross-chain normalization.
10. Inference requires a separately accepted contract.
11. Learning/retention state is not a provider-verification shortcut.
12. No autonomous execution by implication.

## Pre-trade analysis

`pre_trade_check` remains analysis only.

Accepted behavior may include requested notional, verified liquidity context, notional-to-liquidity ratio, explicit versioned trade-size policy, freshness handling, and selected route-scoped facts only where exact identity/source/freshness/semantic/unit/proof requirements pass.

Current distinctions include:

- exact route-scoped price impact may be usable where its proof contract passes;
- bounded exact execution-fee/model evidence may be usable only within its proven scope;
- quote-side curve behavior is not automatically an executed hidden fee;
- quote slippage tolerance is not expected execution slippage;
- route quality, fill quality, transaction simulation, and generic execution quality remain unavailable unless separately proven.

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Roberta Learning Plane dependency

Roberta Learning System Phases 1-10 are accepted on Roberta `main`. Hardened Phase 10 verified retention is implemented under its narrow deterministic contract. Exact active retained lessons may be classified as `verified_learned_knowledge`, but the classification preserves `operational_trust_authorized=false`, `source_truth_authorized=false`, `live_state_authorized=false`, `cmis_provider_trust_authorized=false`, `governance_mutation_authorized=false`, `wallet_authorized=false`, and `execution_authorized=false`.

Roberta PR #228 merged on 2026-08-26 and accepted the first end-to-end autonomous source-grounded Learning Plane controller. After explicit source selection, Roberta may bind immutable provenance, create/resume a frozen source plan, generate and independently verify source-grounded targets, publish deterministic exercise banks, run canonical source-stage exams, remediate failures, run separate closed-book retention and transfer checks, promote only curriculum-scoped verified concepts, preserve immutable failure evidence, resume safely from durable state, and run a final source capstone.

For *Mastering Blockchain, Fourth Edition*, accepted prebuilt banks reach Stage 8 / Market Structure. Stages 9-14 are not yet separately accepted prebuilt repository banks, although the autonomous controller may generate missing banks at runtime under its validation contract. Bank availability is not mastery; the source is mastered only after every required frozen stage and the final capstone pass in the authoritative ledger.

This Learning Plane is upstream reasoning/knowledge capability, not a new CMIS authority channel. Static learning state never overrides fresh accepted CMIS/provider evidence, never establishes source independence or provider trust, and never changes CMIS capability/promotion/risk/execution semantics.

## Strategic product roadmap — X1 productization (adopted 2026-08-28)

Roadmap ownership: issue #318.

CMIS is now prioritized around the verified data and intelligence services required for **Roberta to become the leading X1 intelligence analyst**. X1 remains the flagship CMIS surface. Solana remains a maintained read-only portability/test surface, while Solana product expansion and release are deferred to a future phase rather than competing with near-term X1 productization.

### Productization priorities

1. **Instant X1 Scan support — COMPLETE through CMIS 1.17 / PR #386.** `instant_x1_scan/v3` preserves accepted exact identity, market, tokenomics, verified history, supported-pair lifetime, deterministic risk, and runtime evidence quality, while adding deterministic field-scoped current-market freshness without global freshness promotion.
2. **X1.Ninja developer API validation — next.** — open a fresh provider-verification track for the currently available machine-readable developer API. Treat all responses as candidate evidence until identity, units, freshness, scope, reproducibility, same-fact semantics, and independence are explicitly proven. Prior SSE 403 evidence does not automatically apply to a different documented API contract.
3. **Holder and wallet intelligence promotion** — promote useful concentration, direct-wallet-relationship, and related deterministic foundations only through explicit public/Scout-reliance contracts. Direct interactions must not be relabeled as beneficial ownership, common control, intent, fraud, or manipulation.
4. **Deterministic Token Burn Intelligence — Issue #368 / CMIS 1.15.0.** First-class `burn_intelligence/v1` promotion is implemented: exact-mint, read-only, cumulative verified-observed burn plus **1h / 24h / 7d / 30d** windows, event counts, 24h/7d/30d equal-period comparisons, issuance context, circulation context, and verified burn-time valuation. Complete lifetime burn remains claimable only when archive/signature/history completeness is independently proven; otherwise cumulative burn remains explicitly bounded to verified observed coverage.
5. **Discovery Intelligence — ACCEPTED under CMIS 1.16.0 / PR #391.** The immutable Discovery Ledger is now promoted through bounded read-only `discovery_intelligence/v1`, exposing first and most-recent verified fact-time observations, verified observation count, sparse coverage bounds, and elapsed observed history. First verified observation is explicitly **not** token launch time, archive completeness, or continuous lifetime coverage.
6. **Field-scoped current-market freshness — COMPLETE under CMIS 1.17 / public #386 + protected `cmis-core` #9.** Collection recency is separate from provider fact time. Price freshness may be verified only when the explicit CMIS gates pass. Liquidity, rolling 24h volume, and rolling transactions remain freshness-unverified until field-specific fact-time contracts exist.
7. **Early Warning services — ACTIVE NEXT GATE.** Advance one warning family at a time only after explicit multi-observation persistence, delivery, replay/deduplication, freshness, identity, and severity-semantics contracts are accepted.
8. **Deterministic Compare services** — support first-class current-vs-history and entity-vs-entity comparisons without recomputing facts outside the canonical evidence store.
9. **X1 ecosystem/network brief inputs** — expose bounded verified market, network, validator, protocol, and ecosystem observations needed for a Roberta daily intelligence brief, one field at a time under exact provenance and scope.
10. **Machine ROBERTA support contracts** — after service contracts stabilize, CMIS should expose only the deterministic backend services/evidence needed by a separately owned Machine ROBERTA interface. The external agent/DApp API, schemas, authentication, quotas, and SDK belong to Roberta; CMIS must not become the general agent product. Premium/access policy must never change truth, verification, Proof Score, risk, or evidence semantics.

### Scope discipline

- Do not rebuild complete explorers, portfolio trackers, staking interfaces, charting terminals, or generic DEX screeners inside CMIS.
- Prefer exact machine-readable ecosystem providers when they reduce commodity indexing work, but preserve CMIS as the verification/trust boundary.
- X1 receives the clear majority of near-term chain-specific product work.
- Solana maintenance continues for accepted read-only capability, regression coverage, and cross-chain portability. Solana product expansion and release are deferred to a future phase unless bounded work materially improves shared CMIS abstractions.
- Proof Score remains separate from risk. Unknown remains unknown. Source independence must be proven, not inferred from provider labels.
- No roadmap item authorizes transaction construction, signing, broadcasting, custody, swaps, bridge value transfer, or autonomous value movement.

This roadmap update changes **priority and product direction only**. It does not promote any currently internal service, declare X1.Ninja verified, or change the accepted CMIS capability contract by itself.

## Human/Machine ROBERTA evidence-support roadmap — planned

CMIS owns the deterministic evidence capabilities required by both Human ROBERTA and Machine ROBERTA. It does **not** own their presentation, conversational policy, external machine-client envelope, authentication, SDK, or user personalization.

Canonical split:

```text
Human ROBERTA / Machine ROBERTA
              |
            Roberta
              |
          Chain Scout
              |
             CMIS
              |
     verified provider/source
```

CMIS should expose one accepted fact/evidence contract that both Roberta faces can consume. Human and Machine Roberta must not receive different truth semantics merely because their presentation differs.

### 1. Execution-quality and realized-slippage evidence

Current accepted distinction remains:

- quote slippage tolerance semantics: verified/corroborated for tested XDEX quote scope;
- exact route-scoped price impact: usable only where the accepted proof contract passes;
- bounded fee evidence: usable only within exact proven scope;
- **expected execution slippage: unavailable** until separately proven.

The roadmap for closing that gap is:

#### Stage A — quote-to-executed-swap matcher

Create a read-only deterministic matcher that can bind, only when evidence is sufficient:

- exact chain;
- exact token-in/token-out mints;
- exact pool;
- exact AMM configuration;
- trade direction;
- requested input;
- quote observation time/slot;
- quoted expected output;
- quote minimum output / tolerance;
- executed transaction signature;
- execution time/slot;
- actual output;
- explicit fees;
- accepted source/proof lineage.

Ambiguous or unmatched quote/execution pairs must fail closed. No transaction preparation or simulation may be used as an execution shortcut.

#### Stage B — realized-slippage ledger

Persist content-addressed realized execution observations with exact provenance.

At minimum preserve:

- quote expected output;
- actual output;
- realized slippage;
- trade size;
- route/pool depth context;
- direction;
- fee evidence;
- observation and execution times;
- evidence scope;
- Evidence Receipt / Proof Score identities where supported;
- limitations and unresolved fields.

Sparse observations remain sparse. Missing quote/fill history is not interpolated.

#### Stage C — comparable-trade statistics

Once enough verified observations exist, expose deterministic descriptive statistics for compatible cohorts, potentially including:

- sample count;
- median realized slippage;
- percentile ranges;
- trade-size-to-pool-depth buckets;
- direction-specific behavior;
- pool/config-specific behavior;
- observation-window bounds.

Cohorts must not mix incompatible route, pool, AMM config, unit, direction, or semantic scopes merely to increase sample size.

#### Stage D — expected execution-slippage contract

Only after a separately accepted adequacy/validation contract proves that the historical sample supports prediction may CMIS promote an expected-execution-slippage capability.

Any promoted output must preserve:

- exact model/statistical method identity and version;
- input scope;
- sample size;
- calibration/validation evidence;
- expected range rather than false precision where appropriate;
- freshness/market-regime limitations;
- unresolved evidence;
- explicit distinction from user-selected slippage tolerance;
- `analysis_only=true`;
- `execution_authorized=false`.

Until that promotion gate passes, expected execution slippage remains unavailable.

### X1 Token Burn Intelligence — Issue #368

CMIS should promote the existing generic X1 burn-scanner/provider foundation into a versioned, exact-mint burn-intelligence service. Candidate public contract name:

```text
token_burn_intelligence/v1
```

This name is roadmap intent only until an explicit service contract is reviewed and accepted.

The service should answer, for an exact X1 mint:

- how many tokens CMIS has **verified as burned across all proven available coverage**;
- how many tokens were burned in the trailing **24 hours**;
- how many tokens were burned in the trailing **7 days**;
- how many tokens were burned in the trailing **30 days**;
- burn-event counts for cumulative, 24h, 7d, and 30d scopes;
- **period-over-period burn percentage change** for 24h, 7d, and 30d;
- the exact immediately preceding equal-length period amount used as each percentage-change denominator;
- exact coverage start/end;
- exact evaluation/as-of time;
- scan/archive completeness state;
- evidence provenance, limitations, Evidence Receipt, and Proof Score where supported.

#### Burn semantics

Count only deterministic accepted on-chain token-destruction semantics for the exact mint, such as verified SPL Token `Burn` / `BurnChecked`-equivalent instructions under the accepted X1 parser contract.

Do **not** count a transfer to a so-called dead/burn address as a token burn merely because a provider, explorer, project, or user labels the address that way. Any non-standard destruction mechanism requires its own separately accepted semantic proof.

Burn identity is rooted in the exact mint. Symbol/name lookup may assist resolution, but ticker/name equality never defines which asset was burned.

Each burn event should be uniquely keyed so the same transaction/instruction cannot be double-counted across rescans or providers. The canonical event identity should include enough exact transaction/instruction position information to make persistence idempotent.

#### Cumulative total vs. complete lifetime total

The contract must distinguish:

```text
verified_burned_observed
```

from:

```text
complete_lifetime_burn
```

A cumulative scan may report every burn CMIS has verified within its proven available history. It may set a field equivalent to:

```text
lifetime_total_burn_verified = true
```

only when complete token-lifetime/archive/signature traversal is independently proven.

Otherwise:

```text
lifetime_total_burn_verified = false
```

and the cumulative amount remains explicitly coverage-bounded. The UI must not relabel it as the token's definitive lifetime burn.

#### Rolling-window semantics

Trailing windows should be computed relative to one explicit canonical UTC `as_of` time:

```text
24h = (as_of - 24 hours, as_of]
7d  = (as_of - 7 days, as_of]
30d = (as_of - 30 days, as_of]
```

Only burn events with accepted canonical transaction/block time may enter those buckets. Events with missing, malformed, ambiguous, or unverified time remain outside time-window totals and must surface as unresolved rather than being guessed into a window.

Window output should preserve both:

- burned token amount;
- burn-event count.

#### Period-over-period percentage change

For each burn window, CMIS should compare the current window with the **immediately preceding equal-length window**:

```text
current 24h vs previous 24h
current 7d  vs previous 7d
current 30d vs previous 30d
```

For current burn amount `C` and prior burn amount `P`:

```text
percent_change = ((C - P) / P) * 100
```

The returned record must preserve:

- current-period burn amount;
- prior-period burn amount;
- absolute change;
- percentage change;
- direction (`INCREASED`, `DECREASED`, `UNCHANGED`, or explicit non-numeric state);
- exact current/prior window bounds;
- coverage status for both windows.

A numeric percentage is valid only when both comparison windows have compatible sufficient verified coverage.

Zero-denominator behavior must fail closed:

- prior = 0 and current > 0 -> `percent_change = null`, with an explicit state such as `NEW_BURN_ACTIVITY`; never report infinity;
- prior = 0 and current = 0 -> zero-to-zero behavior must be explicitly defined by the accepted contract before returning numeric `0%`;
- missing/incomplete prior-window evidence -> `percent_change = null` with an explicit insufficient-coverage state.

This percentage describes **change in burn activity**, not percent of supply burned. Supply-based ratios remain separate fields.

#### Supply relationship

Current verified supply may be exposed alongside burn intelligence when available, and CMIS may derive an explicitly labeled ratio such as:

```text
verified_observed_burn / current_verified_supply
```

but it must not call that value “percent of original supply burned” unless original/genesis supply is independently proven.

Likewise, supply decline is not automatically equivalent to cumulative burns, and cumulative burns are not the same as net supply change when minting can also occur. Burn instructions and mint instructions must remain separate facts.

#### Historical persistence and incremental scans

The accepted provider-owned activity/event parser and existing `x1_burn_scan.py` foundation should be reused rather than creating a second burn parser.

The production design should support:

- durable content-addressed/idempotent burn observations;
- incremental rescans from the last verified position;
- bounded backfill toward earliest available history;
- explicit gap detection;
- exact signatures/transactions scanned;
- no double counting when windows overlap;
- deterministic regeneration of 24h/7d/30d aggregates from accepted event records.

#### Roberta consumption

After explicit CMIS public-service and X1 Scout-reliance promotion, Roberta should be able to answer questions such as:

- “How much AGI has been burned?”
- “How much AGI was burned in the last 24 hours?”
- “Show AGI burns for 24h, 7d, and 30d.”
- “Is the burn rate accelerating?”
- “Compare XNT and AGI burn activity.”

The last two require compatible multi-period/compare evidence and must not be inferred from incomplete or incomparable coverage.

This capability is read-only:

```text
analysis_only = true
execution_authorized = false
```

It grants no authority to construct or submit burn transactions.

### 2. Discovery Ledger

CMIS should own the immutable evidence ledger supporting Roberta's **Discovery / first-observation** workflow.

For each supported X1 subject, preserve separately:

- first verified identity observation;
- first verified market observation;
- first verified liquidity observation;
- first verified activity observation;
- subsequent verified observations;
- exact fact/source time;
- source and verification method;
- evidence/proof lineage;
- known observation gaps.

The service must distinguish:

```text
first_verified_observation
```

from:

```text
asset_inception
token_launch
market_creation
```

unless those stronger claims are separately proven.

Human Roberta may say “ROBERTA first verified this asset on …”. Machine Roberta may receive the exact timestamp and `asset_inception_verified=false`. CMIS remains the source of the underlying fact.

### 3. Early Warning evidence and service contracts

CMIS should develop deterministic warning primitives only from accepted multi-observation evidence.

Candidate warning families include:

- liquidity decline or deterioration;
- concentration change;
- unusual activity under an explicit deterministic statistical/threshold contract;
- identity/metadata/authority changes;
- evidence-quality degradation;
- provider disagreement;
- stale/freshness deterioration;
- future execution-quality/slippage deterioration after its evidence contract exists.

Each warning contract must define:

- subject and exact metric;
- unit;
- comparison window;
- persistence requirements;
- comparator/baseline;
- severity policy identity/version;
- freshness;
- replay/deduplication semantics;
- evidence provenance;
- unknown/partial behavior.

Warning severity is policy, not an inferred behavioral accusation or market-risk score unless an accepted risk contract explicitly says otherwise.

No warning may silently become:

- manipulation;
- insider activity;
- fraud/scam;
- beneficial ownership;
- intent;
- causality;
- imminent price prediction.

Public-service / Scout-reliance promotion remains a separate gate for each warning family.

### 4. Deterministic Compare support

CMIS should expose comparison-ready deterministic evidence rather than forcing Roberta to build a second fact layer.

Comparison support should preserve:

- exact subjects;
- compatible metric/unit definitions;
- aligned or explicitly non-aligned fact times;
- overlapping verified historical windows where required;
- per-subject source/provenance;
- missing-data asymmetry;
- evidence-quality differences;
- exact limitations.

Roberta may synthesize “which is stronger on dimension X,” but CMIS should not invent a universal winner/score unless a separately accepted deterministic policy defines one.

### 5. X1 ecosystem/network brief inputs

CMIS should expose bounded reusable inputs for Roberta's X1 Brief one field/service at a time.

Candidate evidence domains include:

- verified market/liquidity/activity aggregates with explicit universe coverage;
- new/first-observed assets from the Discovery Ledger;
- material liquidity/concentration/activity changes;
- provider/evidence-health state;
- accepted network/validator/protocol observations where exact providers and semantics are proven.

CMIS should not become the prose briefing product. Roberta owns prioritization, narrative synthesis, and user presentation.

### 6. Machine ROBERTA backend requirements

To support a stable Machine ROBERTA surface, CMIS services should continue strengthening:

- versioned contracts;
- explicit capability classification per chain/service;
- deterministic unavailable/partial/conflict states;
- stable reason/state codes where CMIS owns the underlying condition;
- exact timestamps/freshness;
- exact chain/asset/pool/route scope;
- request/result traceability where appropriate;
- Evidence Receipt / Proof Score attachment;
- deterministic error semantics;
- read-only idempotence where applicable.

CMIS does not own the external `roberta_intelligence/v1` envelope, API keys, agent identity, quotas, SDK, human-vs-machine rendering, or personalization policy.

### 7. No universal score at the CMIS layer

CMIS must not collapse market depth, activity, history, concentration, risk, evidence strength, and execution evidence into one opaque universal score.

Return the deterministic dimensions separately. Roberta may provide a recommendation using explicit policy while preserving the dimensions and their provenance.

### 8. Cross-project acceptance rule

For a new Human/Machine ROBERTA feature that depends on CMIS:

1. CMIS proves and, where required, promotes the exact backend fact/evidence service;
2. X1 Scout adopts the service under an explicit minimum-contract/capability gate;
3. Roberta maps the accepted result into the Canonical ROBERTA Decision Object;
4. Human and Machine renderers must preserve the same underlying facts/unknowns;
5. no step implies execution authority.

## Product direction

### Verified Data

Continue field-level X1 and Solana verification without weakening truth standards.

Near-term provider-gap priorities:

- holder-semantics/completeness correction #304 is complete via PR #305 without relabeling token accounts/authorities as holders or beneficial owners;
- Official X1 RPC remains the selected production RPC path; self-hosted redundancy is optional/deferred and does not establish market-source independence;
- historical redundancy/source-independence remains a future evidence-depth option rather than a blocker;
- #306 observed eligible-pair liquidity/24h-volume aggregation is complete via PR #307 with pair-universe completeness explicitly unverified;
- #308 Solana market observation freshness semantics is complete via PR #310: Jupiter blockId may be anchored to canonical Solana block time;
- #311 Solana Jupiter current-price freshness policy is complete via PR #312 with explicit CMIS operator bounds of 60 seconds max age and 5 seconds future skew;
- #313 timestamped Pyth Core secondary Solana price evidence is complete via PR #314 for one exact USDC/USD fixture through canonical Solana RPC; source-specific Pyth freshness is deterministic and Jupiter/Pyth numerical/fact-time-delta evidence is available;
- #315 Jupiter–Pyth cross-source time-identity governance is implemented in PR #316 with an explicit five-second same-time operator window; exact same-time eligibility may now be verified while source independence, price-construction equivalence, and current-price promotion remain false;
- #317 provider/source-independence and price-construction compatibility analysis is retained as deferred Solana evidence work; it is not the active near-term implementation priority while X1 productization is underway;
- Oracle V2 #272 remains parked until policy-eligible live slots appear; then current-price correctness and source-independence gates may resume.

### Verified Intelligence

Accepted:

- Phase 11 foundation;
- first Phase 12 promoted X1 service;
- deterministic descriptive classification;
- deterministic direct wallet relationships;
- deterministic concentration-threshold alert evidence.

No broader public/Scout promotion is active. Any future alert/public wrapper requires a separate promotion contract and separate Roberta/Scout adoption/readiness gate.

### Early Warning

The single-observation alert primitive and the two-observation persistent concentration warning foundation are complete internally. Issue #396 / public PR #397 / protected `cmis-core` #15 prove exact subject compatibility, strict ordering, bounded persistence, current evidence freshness, duplicate/replay safety, and preserved Evidence Receipt / Proof Score lineage.

The pull-only public service is now accepted as `concentration_warning_intelligence/v1` under CMIS 1.18 through public #400 and protected `cmis-core` #16. The **next gate is X1 Scout / ROBERTA adoption**, not additional hidden inference. Push delivery remains separately unauthorized.

No warning state may silently become behavioral intent, ownership, manipulation/fraud attribution, risk severity, causality, or imminent-price prediction.

### Cross-Chain Intelligence

- X1: mature active foundation;
- FortiSwap read-only provider foundation is accepted via Issue #413 / PR #414: machine discovery plus token, token-detail, router-volume, and quote normalization; provider trust/confidence/safety remain assertions, bridge semantics remain unqualified, and no transaction build/send/signing authority is granted;
- Solana: read-only foundation complete and maturing field-by-field;
- Ethereum: future explicit provider/verification milestone only;
- bridge/stablecoin/capital-flow evidence: future, only after exact source semantics are accepted.

### Premium / export direction

Investigation/evidence export and premium access remain future product candidates after deterministic services stabilize. Premium access must never alter the definition of truth, verification, Proof Score, risk, or execution authority.

## Recommended implementation sequence

Completed:

1. deterministic pre-trade trade-size policy;
2. Phase 11 concentration/wallet/history/evidence foundation;
3. bounded XDEX quote/history semantic work;
4. pinned historical executed-fee reconstruction;
5. route-scoped pre-trade evidence seam;
6. explicit concentration-threshold evaluator;
7. Phase 12 X1 `concentration_change_intelligence/v1` promotion + Roberta adoption/readiness;
8. deterministic descriptive classification with behavioral/ownership interpretation excluded;
9. deterministic direct wallet-relationship evidence with explicit non-ownership semantics;
10. deterministic concentration-threshold alert evidence foundation;
11. paired Roberta #226 / CMIS #269 architecture/source-of-truth reconciliation;
12. reconcile CMIS documentation with accepted Roberta PR #228 / PR #231 Learning Plane state.

Current implementation sequence:

13. reconcile provider-gap and Oracle status after #298/#299 and close completed timestamp-governance issues;
14. retain #301 self-hosted-node verification as optional/deferred infrastructure after selecting Official X1 RPC as the production path;
15. correct holder/token-account/authority semantics under #304 without beneficial-owner overclaim — complete via PR #305;
16. aggregate Solana observed eligible-pair liquidity/24h volume under #306 while preserving incomplete pair-universe scope — complete via PR #307;
17. verify Solana market observation freshness semantics under #308 without treating token/pair creation timestamps or collection time as market-fact freshness — complete via PR #310;
18. define/apply the source-specific Jupiter current-price freshness policy under #311 — complete via PR #312 with 60-second max age / 5-second future skew CMIS governance;
19. verify timestamped Pyth Core secondary Solana price evidence under #313 — complete via PR #314 for one exact USDC/USD sponsored push-feed fixture;
20. define an explicit Jupiter–Pyth cross-source maximum fact-time-delta policy under #315 — implemented in PR #316 with a five-second CMIS same-time window;
21. evaluate Jupiter–Pyth provider/source independence and price-construction compatibility before any Solana current-price promotion gate;
22. keep Oracle V2 #272 non-promoted until policy-eligible live slots exist, then resume same-fact price-correctness and source-independence gates.

Future candidates — **not active milestones until separately accepted**:

23. deterministic X1 Token Burn Intelligence under Issue #368, including exact-mint cumulative verified-observed burn plus trailing 24h/7d/30d totals and completeness semantics;
24. read-only quote-to-executed-swap matching and a content-addressed realized-slippage ledger;
25. comparable-trade execution-quality statistics under exact route/pool/config/direction semantics;
26. expected execution-slippage promotion only after a separate evidence-adequacy and validation gate;
27. immutable X1 Discovery Ledger / first-verified-observation service;
28. deterministic Early Warning service families, each with explicit persistence/freshness/severity/replay contracts and separate public/Scout promotion;
29. first-class deterministic Compare support that preserves compatible scope/time/provenance;
30. bounded X1 ecosystem/network brief inputs for Roberta synthesis;
31. any additional public alert/Scout-reliance promotion;
32. deeper XDEX route/execution evidence without transaction preparation as a proof shortcut;
33. separate Solana current-price promotion only after time identity and independence/price-construction gates;
34. further field-by-field Solana maturity;
35. Ethereum under an explicit capability/acceptance plan;
36. investigation/evidence export and premium access.

None authorizes execution.

## Governance

The repository-authoritative engineering process is [`CMIS_ENGINEERING_WORKFLOW.md`](./CMIS_ENGINEERING_WORKFLOW.md).

Meaningful changes require:

1. roadmap/issue ownership;
2. contract/spec before code when semantics/authority change;
3. narrow tracer-bullet slicing;
4. behavior-first deterministic testing;
5. exact-head/full applicable CI;
6. independent **Spec / Contract**, **Code / Architecture**, and **Authority / Evidence Safety** review;
7. no merge while any required review axis is blocked;
8. post-merge README/roadmap/source-of-truth reconciliation.

The canonical evidence system remains the Evidence Receipt / Proof Score / provenance architecture. LLM judgment and Learning Plane state are not the trust root for CMIS fact/proof/risk/intelligence truth.

## Relationship to Roberta

```text
CMIS verifies what the evidence supports.
Chain Scouts investigate and interpret within their chain.
Roberta coordinates, learns within bounded static-source rules, and explains.
```

The paired Roberta #226 / CMIS #269 source-sync reconciliation is merged. Roberta PR #228's autonomous Learning Plane and subsequent source/roadmap reconciliation are accepted on Roberta `main`. Roberta's accepted MB4E prebuilt bank construction remains through Stage 8 / Market Structure, while operator-local source mastery is complete at 14/14 required stages plus the required final capstone. Runtime-generated Stages 9-14 remain mastery evidence rather than separately accepted prebuilt repository banks.

Roberta may synthesize accepted CMIS results but must not recalculate CMIS truth/proof, silently upgrade inference to fact, collapse risk and evidence quality into one score, or treat internal non-promoted foundations as callable services.

Human ROBERTA and Machine ROBERTA are two Roberta-owned presentation/client surfaces over the same accepted intelligence. CMIS must provide identical underlying fact/evidence semantics to both; it does not own the Human renderer, Machine external schema, API authentication, quotas, SDK, saved user policies, or agent action authority.

Roberta's Learning System, autonomous Learning Plane, retained lessons, Pyramid training state, memory, policy, and human approval do not override CMIS for freshness-sensitive market/blockchain facts and do not authorize CMIS execution.

## Execution boundary

No accepted CMIS roadmap item authorizes:

- transaction construction as an execution path;
- signing;
- broadcasting;
- custody;
- live trading/swaps;
- bridge value transfer;
- autonomous value movement.

Controlled Execution remains unauthorized.

## Live reconciliation — 2026-09-03 America/New_York

- **Historical Coverage Proof, Burn, Discovery, WHAT CHANGED?, and Field-Scoped Freshness: COMPLETE.**
- **EARLY WARNING — COMPLETE THROUGH PULL-ONLY ROBERTA ADOPTION.** CMIS #399 / public #400 / protected `cmis-core` #16 promote `concentration_warning_intelligence/v1` under CMIS 1.18. ROBERTA public #318 / protected `roberta-core` #28 / Issue #317 preserve the canonical WATCH/CLEAR warning through X1 Scout and the shared Human/Machine Decision Object without recomputation or risk promotion.
- **Push warning delivery: NOT AUTHORIZED / DEFERRED.** No subscriptions, background polling, Telegram push, webhooks, retry/acknowledgement queues, or execution authority are part of the accepted warning milestone.
- **CROSS-CHAIN / WARP: SEMANTIC QUALIFICATION ACCEPTED FOR EXACT CONFIG ROUTES.** CMIS Issue #407 now has an exact official-app endpoint and deterministic response-body fixture for `GET https://app.bridge.x1.xyz/api/bridge/config`. The accepted `warp_config/exact-mint-pair/v1` semantic contract verifies exact source/destination mint identity through provenance, active/paused route state from chain+token pause fields, provider-declared native/non-native representation topology, explicit guardian quorum dependency, and `fetchedAt` millisecond fact time. The exact wSOL -> wSOL.X fixture qualifies under `warp_bridge_qualification/v1`. This does **not** verify reserve sufficiency, legal custody, guardian honesty, public-service promotion, Scout reliance, or execution; `execution_authorized=false`. After exact-head CI and merge, #409 Bridge Supply + Flow Intelligence is the next CMIS cross-chain build.
- **WARP ON-CHAIN FALLBACK: ACCEPTED INVENTORY FOUNDATION.** Issue #419 / PR #423 are complete on `main`. Exact-head live zero-byte `getProgramAccounts` evidence verified 11,036 Warp-owned accounts on Solana and 10,983 on X1, with 49 exact cross-chain pubkey overlaps. Shared rare structural families include 170-byte accounts (7 per chain) and one 236-, 321-, and 335-byte account per chain. These are structural observations only: account roles/layout/route semantics remain unverified, #407 stays open, and `execution_authorized=false`.
- **FORTISWAP PROVIDER: ACCEPTED READ-ONLY FOUNDATION.** Issue #413 / PR #414 are complete on `main`. CMIS now has bounded FortiSwap machine-discovery, token, token-detail, router-volume, and quote normalization with exact provider-host qualification and deterministic CI. FortiSwap assertions are not CMIS truth; bridge semantics remain unqualified; #407/#409/#410 remain independently gated; `execution_authorized=false`.
- **CMIS #363:** parallel read-only delayed-vault/X1.Ninja research; not the flagship blocker.
- `execution_authorized=false`.
