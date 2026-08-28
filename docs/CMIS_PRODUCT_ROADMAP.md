# CMIS Product & Premium Service Roadmap

Last reconciled: 2026-08-28 (America/New_York)

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
- **CMIS deterministic engineering workflow / three-axis review: ADOPTED and repository-authoritative.**
- **X1 all-available verified historical profiles and overlapping pair comparison: COMPLETE under `historical_compare` modes in CMIS `1.10.0`.**
- **X1 exact-mint normalized asset identity: COMPLETE under `x1_asset_identity/v1` in CMIS `1.11.0`.** Exact mint is the fungible identity root; Metaplex and XDEX descriptors remain separately sourced; same-mint descriptor conflict is partial; XDEX unavailability is not misreported as mint absence.
- **X1 verified-provider historical price backfill: COMPLETE under the bounded CMIS `1.12.0` contract.** Backfill is price-only and preserves non-independence, non-archive-completeness, non-continuity, historical stable-quote uncertainty, and non-lifetime-completeness limits.
- **Oracle V2 structural X1 contract verification and freshness governance: COMPLETE for the accepted bounded evidence contracts.** Timestamp-unit semantics are verified as Unix milliseconds; the explicit current-price freshness policy is selected/applied (`max_age_ms=60000`, `max_future_skew_ms=5000`, `minimum_eligible_slots=3`). The latest live run classified all 30 relay slots stale, so current-price authority remains unpromoted.
- **CMIS capability contract: `1.13.0`.**
- **Instant X1 Scan: IMPLEMENTED under #322 as `instant_x1_scan/v1`.** The service is X1-only, read-only, composition-only, local-history-only, and fail-closed for unverified holder/current-concentration facts; Proof Score remains separate from deterministic risk.
- **Roberta adoption/readiness of the promoted X1 concentration-change service: COMPLETE.**
- **Paired Roberta PR #226 / CMIS PR #269 architecture/source-of-truth reconciliation: COMPLETE.**
- **Roberta autonomous Learning Plane upstream dependency: ACCEPTED on Roberta `main` via PR #228; post-merge Roberta source/roadmap reconciliation is accepted via PR #231.**
- **Parallel X1 provider-gap work (#30): OPEN, read-only/fail-closed.**
- **Controlled transaction execution: UNAUTHORIZED / not an active CMIS milestone.**

There is currently **no accepted next public alert service, Scout-reliance promotion, or broader Verified Intelligence promotion milestone**. Any next promotion requires a separate issue/spec/roadmap gate.

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

Warp Bridge machine-readable operational state remains unavailable until an exact provenance-approved read contract is accepted.

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

1. **Instant X1 Scan support — implemented under #322 / CMIS 1.13.0.** The compact `instant_x1_scan/v1` service composes exact identity, market, tokenomics, CMIS-stored verified history, deterministic risk, and runtime evidence quality. Unverified holder/current-concentration facts remain explicit unknown/partial values.
2. **X1.Ninja developer API validation — next.** — open a fresh provider-verification track for the currently available machine-readable developer API. Treat all responses as candidate evidence until identity, units, freshness, scope, reproducibility, same-fact semantics, and independence are explicitly proven. Prior SSE 403 evidence does not automatically apply to a different documented API contract.
3. **Holder and wallet intelligence promotion** — promote useful concentration, direct-wallet-relationship, and related deterministic foundations only through explicit public/Scout-reliance contracts. Direct interactions must not be relabeled as beneficial ownership, common control, intent, fraud, or manipulation.
4. **Discovery Ledger** — add an immutable first-observation record plus subsequent verified observations for supported X1 assets/entities, preserving exact source/fact-time/proof lineage so later performance and assessment-quality analysis can be reproduced.
5. **Early Warning services** — advance concentration/liquidity/wallet/activity warning candidates only after explicit multi-observation persistence, delivery, replay/deduplication, freshness, identity, and severity-semantics contracts are accepted.
6. **Deterministic Compare services** — support first-class current-vs-history and entity-vs-entity comparisons without recomputing facts outside the canonical evidence store.
7. **X1 ecosystem/network brief inputs** — expose bounded verified market, network, validator, protocol, and ecosystem observations needed for a Roberta daily intelligence brief, one field at a time under exact provenance and scope.
8. **Developer intelligence API** — after service contracts stabilize, prepare a bounded developer-facing CMIS/Roberta intelligence surface for other X1 applications. Premium/access policy must never change truth, verification, Proof Score, or risk semantics.

### Scope discipline

- Do not rebuild complete explorers, portfolio trackers, staking interfaces, charting terminals, or generic DEX screeners inside CMIS.
- Prefer exact machine-readable ecosystem providers when they reduce commodity indexing work, but preserve CMIS as the verification/trust boundary.
- X1 receives the clear majority of near-term chain-specific product work.
- Solana maintenance continues for accepted read-only capability, regression coverage, and cross-chain portability. Solana product expansion and release are deferred to a future phase unless bounded work materially improves shared CMIS abstractions.
- Proof Score remains separate from risk. Unknown remains unknown. Source independence must be proven, not inferred from provider labels.
- No roadmap item authorizes transaction construction, signing, broadcasting, custody, swaps, bridge value transfer, or autonomous value movement.

This roadmap update changes **priority and product direction only**. It does not promote any currently internal service, declare X1.Ninja verified, or change the accepted CMIS capability contract by itself.

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

The first internal alert evidence foundation is complete. Future candidates may include multi-observation persistence, delivery semantics, or public service promotion only after a separate accepted contract proves exact evidence/freshness/identity/replay semantics.

No alert state may silently become behavioral intent, manipulation/fraud attribution, risk severity, or imminent-price prediction.

### Cross-Chain Intelligence

- X1: mature active foundation;
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

23. any public alert/Scout-reliance promotion;
24. deeper XDEX route/execution evidence without transaction preparation as a proof shortcut;
25. separate Solana current-price promotion only after time identity and independence/price-construction gates;
26. further field-by-field Solana maturity;
27. Ethereum under an explicit capability/acceptance plan;
28. investigation/evidence export and premium access.

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

The paired Roberta #226 / CMIS #269 source-sync reconciliation is merged. Roberta PR #228's autonomous Learning Plane and PR #231's post-merge source/roadmap synchronization are also merged on Roberta `main`. Roberta's accepted MB4E prebuilt bank construction reaches Stage 8 / Market Structure; Stages 9-14 plus the final capstone remain outstanding source-mastery work rather than prerequisites for the existence of the autonomous controller.

Roberta may synthesize accepted CMIS results but must not recalculate CMIS truth/proof, silently upgrade inference to fact, collapse risk and evidence quality into one score, or treat internal non-promoted foundations as callable services.

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
