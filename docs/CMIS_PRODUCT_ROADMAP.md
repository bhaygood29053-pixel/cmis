# CMIS Product & Premium Service Roadmap

## Purpose

CMIS (Cross-Chain Market Intelligence Service) is the deterministic evidence, verification, normalization, historical-intelligence, and risk layer beneath Liquidity Scout, Roberta, chain-specific Scouts, and future external agents.

Liquidity Scout remains the market-intelligence product users interact with. Roberta remains the higher-level reasoning and coordination layer. CMIS supplies trusted, machine-readable evidence to both.

The long-term goal is to make CMIS a premium blockchain-intelligence service that converts raw market and on-chain activity into **verified, explainable, auditable, and machine-consumable intelligence**.

Core principle:

> Premium users may receive more depth, history, speed, automation, analytics, and access, but never a weaker or different definition of truth.

Verification standards remain consistent across every service tier.

---

## Roadmap status — 2026-08-18

The original product-sequence numbering in this document predates the later GitHub execution-phase numbering. They are not a one-to-one mapping.

Accepted execution milestones:

> **CMIS Phase 10 — Solana Provider read-only foundation: COMPLETE.**
>
> **Post-Phase-10 evidence-quality milestone — Evidence Receipts + Proof Score: COMPLETE.**
>
> **Remaining X1 evidence gaps — CLASSIFIED at an explicit fail-closed capability boundary.**
>
> **Deterministic pre-trade trade-size/impact milestone — COMPLETE.**
>
> **CMIS Phase 11 — read-only Verified Intelligence foundation: COMPLETE.**

Phase 10 completion is recorded in [`PHASE_10_COMPLETION.md`](./PHASE_10_COMPLETION.md) and GitHub Issue #78. The final production-composition change was merged in PR #158.

CMIS contract `1.7.0` added deterministic evidence receipts, deterministic proof scoring, evidence-quality metadata in normal runtime envelopes, and machine-readable evidence-quality requirements in the capability manifest. This work was merged in PR #166.

The remaining X1 evidence gaps are no longer an ambiguous backlog. PR #167 established an explicit machine-readable capability boundary classifying each tracked fact as `verified`, `bounded`, or `unavailable`. The human-readable boundary is documented in [`X1_EVIDENCE_CAPABILITY_BOUNDARY.md`](./X1_EVIDENCE_CAPABILITY_BOUNDARY.md). An unavailable capability may be reconsidered when a new provider/evidence contract is actually proven, but CMIS must not infer it in the meantime.

The deterministic pre-trade trade-size/impact milestone tracked in GitHub Issue #99 is complete. CMIS evaluates requested notional against verified liquidity where available, applies versioned trade-size policy, and keeps price-impact, slippage, route-quality, and fee fields explicitly unavailable where their semantics are not proven. The work remains analysis-only and does not authorize execution.

Phase 11 completion is recorded in [`PHASE_11_COMPLETION.md`](./PHASE_11_COMPLETION.md) and GitHub Issue #171. PRs #170, #172, #176, and #177 established top-account concentration primitives, neutral wallet-activity facts, sanitized sparse historical intelligence storage/comparison, and evidence-bound intelligence conclusions.

CMIS contract `1.8.0` adds a discoverable read-only `intelligence_foundation` capability boundary. The Phase 11 primitives remain outside the public `supported_services` surface, and automatic downstream Scout reliance remains unpromoted until a new accepted service contract explicitly authorizes it.

The accepted system now has:

- a mature X1/XDEX deterministic market and verification foundation;
- normal CMIS runtime service composition;
- versioned Scout ↔ CMIS capability discovery;
- persisted verification evidence;
- deterministic X1 trade verification and bounded verified-activity coverage;
- deterministic risk and bounded pre-trade analysis;
- deterministic, versioned trade-size analysis against verified liquidity;
- deterministic evidence receipts and proof scores attached to CMIS service envelopes;
- an explicit X1 evidence-capability boundary for remaining provider limitations;
- a read-only Solana provider/runtime foundation beneath the same CMIS contract;
- read-only Solana live acceptance in GitHub Actions;
- exact top-account concentration observations and numeric concentration-change primitives;
- neutral verified wallet-activity facts without behavioral labels;
- sanitized sparse historical intelligence storage and compatible-series comparison;
- evidence-bound Phase 11 conclusions with content-addressed receipts, proof scores, and conclusion fingerprints;
- explicit separation of provider-reported observations from independently verified observations;
- explicit non-promotion of Phase 11 primitives into new public services or automatic Scout dependencies.

No new post-Phase-11 execution milestone is active in this roadmap yet. Future public-service exposure, automatic Scout reliance, behavioral intelligence, alerting, relationship graphs, or additional cross-chain expansion must begin under a separately accepted contract with explicit evidence and safety gates.

This roadmap does **not** authorize execution. Signing, custody, broadcasting, and autonomous value movement remain separate future boundaries.

---

## 1. Stable architecture

```text
Users / Agents
      |
      +--> Liquidity Scout
      |
      +--> Roberta
      |
      +--> Chain Scouts / external agents
                    |
                    v
                  CMIS
                    |
       +------------+-------------+
       |            |             |
       v            v             v
 Market sources   Chain RPC   Historical stores
       |            |             |
       +------------+-------------+
                    |
                    v
      Verified canonical intelligence
```

CMIS owns:

- deterministic collection and normalization;
- direct blockchain verification where available;
- source comparison and conflict handling;
- explicit confidence and verification state;
- historical evidence storage;
- deterministic risk features;
- proof/evidence records;
- deterministic evidence receipts and proof scores;
- cross-chain canonical schemas;
- capability eligibility contracts;
- future premium intelligence APIs and alerts.

CMIS does **not** own:

- unsupported predictions presented as facts;
- model-invented market values;
- autonomous trade authorization;
- claims about intent that cannot be proven from evidence.

Roberta and Liquidity Scout may explain and reason over CMIS results, but must not rewrite deterministic facts or recompute CMIS proof strength as a second source of truth.

---

## 2. Completed foundation

### X1/XDEX verification and runtime — COMPLETE / ACTIVE

The X1 path can independently evaluate provider candidates against X1 RPC and recognized XDEX evidence.

Accepted capabilities include, where the evidence contract permits:

- exact asset identity;
- market reports and rankings;
- tokenomics and authority facts;
- successful transaction confirmation;
- chain slot/timestamp identity checks;
- recognized XDEX program detection;
- token-account delta analysis;
- exact pool-leg matching;
- deterministic BUY/SELL verification;
- provider-vs-chain reconciliation;
- bounded verified asset activity;
- persisted verification evidence;
- deterministic risk checks;
- bounded, analysis-only pre-trade checks;
- fail-closed behavior for incomplete or contradictory evidence.

Program-scoped completeness remains distinct from global/all-X1 completeness. CMIS does not promote a narrower evidence scope into a broader claim without proof.

### X1 evidence capability boundary — COMPLETE / ACTIVE

The remaining X1 evidence questions now have explicit machine-readable states rather than an open-ended assumption that every provider gap must eventually become verified.

Accepted examples include:

- canonical native-XNT translation: `verified`;
- token-account concentration: `bounded` and not equivalent to holder/wallet concentration;
- requested-slot same-fact historical comparison: `bounded` where source independence is explicit;
- X1.Ninja SSE access handshake: `bounded`, while live-event semantics remain unavailable;
- exact bridge candidate-URL provenance: `bounded`, while operational/route/fee/capacity/lifecycle facts remain unavailable;
- direct XDEX history and quote semantics: `unavailable` until their response semantics are proven.

See [`X1_EVIDENCE_CAPABILITY_BOUNDARY.md`](./X1_EVIDENCE_CAPABILITY_BOUNDARY.md).

### CMIS capability/runtime contract — COMPLETE / ACTIVE

The CMIS runtime exposes a versioned machine-readable capability contract. Chain/service combinations are explicitly classified as supported, bounded, partial, or unavailable.

The manifest advertises evidence-receipt schema 1, proof-score schema 1, that risk remains separate from proof, and that missing evidence remains unknown rather than becoming a fabricated false/zero value.

Under contract `1.8.0`, the manifest also advertises the bounded read-only Phase 11 `intelligence_foundation` while explicitly keeping those primitives outside the public supported-service surface and outside automatic Scout reliance.

This prevents downstream Scouts from assuming that a service or evidence quality exists merely because another chain supports it or because an internal deterministic primitive exists.

See [`CMIS_CAPABILITY_CONTRACT.md`](./CMIS_CAPABILITY_CONTRACT.md).

### Evidence Receipts and Proof Score — COMPLETE / ACTIVE

CMIS now attaches deterministic evidence-quality metadata to completed service envelopes without changing the underlying service result.

Evidence receipts preserve available provenance, verification state, evidence scope, freshness indicators, disagreements, limitations, and unresolved fields. They summarize evidence already present in the CMIS result; they do not fetch a second provider, invent missing semantics, or promote a provider assertion into independent proof.

Proof scores are deterministic/reproducible and keep proof strength separate from risk. Missing proof lowers or limits evidence quality rather than being converted into a safe value.

### Deterministic pre-trade trade-size/impact analysis — COMPLETE / ACTIVE

GitHub Issue #99 is complete.

CMIS now:

- evaluates requested notional rather than carrying it only as conversational context;
- computes notional-to-liquidity ratio when verified liquidity is available;
- applies a deterministic, versioned trade-size policy;
- fails closed when liquidity evidence is missing or conflicting;
- exposes price-impact, slippage, route-quality, fee, and simulation capabilities only where their semantics are actually verified, otherwise keeping them explicitly unavailable;
- remains analysis-only with no signing, broadcasting, custody, trade execution, or autonomous value movement.

### Phase 10 Solana read-only foundation — COMPLETE

Solana is implemented beneath the same CMIS architecture rather than as a separate intelligence stack.

Accepted Phase 10 components include:

- exact-mint identity through canonical Solana RPC;
- SPL Token and Token-2022 program identity checks;
- canonical total supply;
- mint/freeze authority facts;
- RPC slot/context provenance;
- optional largest-token-account concentration evidence that is not holder-total coverage;
- Jupiter read-only source evidence when configured;
- Helius indexed evidence when configured;
- DEX Screener pair-scoped market evidence;
- deterministic cross-source price and supply gates;
- provenance-safe Solana observation history;
- bounded/partial `asset_lookup`, `tokenomics`, `market_report`, `risk_check`, and narrow `historical_compare` services;
- environment-owned production composition, disabled by default;
- live read-only runtime acceptance.

Solana ranking, pre-trade execution modeling, trade verification, verified asset-wide activity, signing, broadcasting, and custody remain unavailable until separately implemented and promoted.

### Phase 11 read-only Verified Intelligence foundation — COMPLETE

Phase 11 is complete and documented in [`PHASE_11_COMPLETION.md`](./PHASE_11_COMPLETION.md).

Accepted primitives include:

- exact top-account concentration observations with raw rational evidence;
- compatible-scope numeric concentration-change comparison;
- neutral verified wallet balance, transfer, trade-direction, LP-action, and deployer-originated activity facts where the required evidence is independently established;
- bounded activity windows, first/last observed activity, transaction counts, and verified volume with explicit units;
- sanitized persistence of concentration, wallet activity, liquidity, supply, price, and activity observations;
- compatible-series historical comparison ordered by canonical observation time;
- explicit sparse-history semantics with no interpolation or zero filling;
- evidence-bound intelligence conclusions using exact CMIS Evidence Receipts and recomputed Proof Scores;
- content-addressed observation, receipt, conclusion, and evidence-bundle identities;
- explicit separation of provider-reported observations from verifier observations.

Phase 11 does **not** promote whale, insider, bot, market-maker, accumulator, distributor, ownership, relationship, scam, manipulation, or behavioral-intent claims. The primitives remain read-only foundations and are not automatically public services or Scout dependencies.

---

## 3. Product direction

CMIS progresses through four capability layers.

### Layer A — Verified Data

Foundation largely established on X1 and partially established on Solana:

- asset identity;
- market reports;
- liquidity evidence;
- trade verification;
- tokenomics;
- authority status;
- historical comparisons;
- deterministic risk checks;
- bounded pre-trade analysis;
- evidence receipts;
- proof scoring and evidence-quality metadata.

### Layer B — Verified Intelligence

The **read-only deterministic foundation is now established** for selected Phase 11 primitives, but higher-level classifications remain deferred until separately contracted and proven.

Accepted foundation:

- top-account concentration facts and compatible numeric change;
- neutral wallet activity facts;
- provenance-safe sparse historical intelligence storage/comparison;
- evidence-bound intelligence conclusions.

Potential future layers, not yet promoted:

- wallet behavior profiles;
- wallet relationship graphs;
- verified whale activity;
- liquidity deterioration analysis;
- token-distribution changes;
- abnormal mint/burn/authority behavior;
- historical pattern interpretation;
- cross-source disagreement intelligence beyond the accepted deterministic evidence layer.

Any future classification must preserve fact/proof/risk/inference boundaries and requires a new accepted service contract before public or automatic Scout reliance.

### Layer C — Early Warning

Future premium monitoring:

- real-time risk thresholds;
- suspicious wallet-cluster movement;
- rapid liquidity removal;
- deployer/insider-linked distribution signals where defensible;
- unusual minting or authority changes;
- abnormal market-structure changes;
- historical-risk-pattern acceleration;
- configurable alerts and webhooks.

### Layer D — Cross-Chain Intelligence

- X1 foundation: active;
- Solana read-only foundation: Phase 10 complete;
- Ethereum: future provider/verification expansion;
- chain-neutral canonical schemas;
- bridge and stablecoin-flow analysis;
- cross-chain capital-flow intelligence;
- chain-by-chain proof provenance.

---

## 4. Premium capability roadmap

### 4.1 Evidence Receipts and Proof Metadata — COMPLETE / ACTIVE

CMIS now produces deterministic structured evidence receipts for normal service results. The current schema records the applicable chain/service/status, available source/provenance observations, verification outcome, scope/freshness evidence, warnings/limitations, unresolved fields, and deterministic receipt identity.

This is an evidence-summary contract, not a second verifier. Future work may deepen fact-specific receipt content while preserving the same fail-closed rule.

### 4.2 CMIS Proof Score — COMPLETE / ACTIVE

CMIS now produces a deterministic/reproducible proof score from the evidence receipt.

Rules remain:

- missing evidence never becomes high confidence;
- intent remains distinct from observable behavior;
- proof strength and risk are separate dimensions;
- a risky asset can have strongly verified facts;
- Roberta/Scouts may explain the score but do not recompute it into a second authoritative proof grade.

### 4.3 Wallet Intelligence — READ-ONLY FOUNDATION COMPLETE / INTERPRETIVE LAYERS DEFERRED

Phase 11 completed the deterministic wallet-activity foundation before behavior labels. Accepted primitives include observed balance changes, verified transfer direction, independently verified BUY/SELL direction, verified LP actions, independently established deployer-originated transfers, bounded observation windows, transaction counts, first/last observed activity, and verified volume with explicit units.

The foundation does **not** yet authorize behavior profiles such as:

- whale/large participant;
- early buyer;
- accumulator/distributor;
- LP provider as an inferred persistent identity;
- high-frequency or bot-like behavior;
- deployer-linked candidate beyond independently established deployer-originated events;
- market-maker-like behavior;
- newly funded wallet as a behavioral classification;
- historically profitable behavior.

Any future classification must state the evidence, observation window, proof strength, uncertainty, and whether the output is fact, heuristic, or inference. Public service exposure or automatic Scout reliance requires a new accepted contract.

### 4.4 Wallet Relationship Graphs

Potential relationship evidence includes common funding sources, deployer distributions, synchronized activity, common LP participation, shared counterparties, bridge flows, and recurring transaction sequences.

Association evidence must not be mislabeled as proof of common ownership.

### 4.5 Historical Scam & Manipulation Pattern Intelligence

Build a cross-chain historical pattern library for liquidity rugs, insider exits, wash trading, Sybil activity, mint/freeze abuse, slow rugs, liquidity manipulation, artificial bot activity, and coordinated dumping.

The output should report risk-pattern similarity and evidence, not unsupported accusations that a project is definitively fraudulent.

### 4.6 Real-Time Early Warning Service

Premium monitoring may eventually track assets, pools, wallets, and ecosystems for conditions such as:

- liquidity deterioration;
- deployer-linked distribution;
- related-wallet selling;
- LP removal acceleration;
- unusual issuance;
- authority changes;
- verified whale accumulation/distribution;
- source disagreement/staleness;
- historical-risk-pattern thresholds.

Alerts should explain what changed, when, why the rule fired, supporting evidence, confidence, risk impact, and whether the condition persists.

### 4.7 Verified Whale Intelligence

Whale intelligence should distinguish trade vs transfer vs LP vs bridge activity, verify BUY/SELL direction when possible, measure size relative to liquidity/volume, and incorporate historical behavior and relationships without inventing intent.

### 4.8 Macro & Market-Regime Intelligence

Future macro inputs may include rates, Treasury yields, inflation, labor, central-bank liquidity, money supply, dollar strength, credit spreads, equities, BTC/ETH conditions, stablecoin flows, DEX activity, and chain-specific activity.

CMIS should timestamp/normalize the facts; Roberta may reason probabilistically over them.

### 4.9 Cross-Chain Capital-Flow Intelligence

As Solana matures and Ethereum is added, CMIS should distinguish directly observed cross-chain flow evidence from inferred capital rotation.

### 4.10 Investigation Mode

Allow a user/agent to submit a token, wallet, transaction, pool, or project for a structured evidence package covering identity, authority state, supply/liquidity history, wallet relationships, whale activity, suspicious sequences, mint/burn events, historical pattern matches, risk findings, evidence receipts, and unresolved questions.

### 4.11 Developer & Agent Intelligence API

Potential future access patterns include API keys, quotas, pay-per-call, subscriptions, webhooks, streaming feeds, agent/MCP access, bulk screening, and evidence export.

The existing `/v1/cmis` service envelope and capability contract remain the architectural foundation unless a dedicated convenience endpoint has a clear justification.

---

## 5. Proposed service tiers

### CMIS Public

- basic asset/market information;
- basic deterministic verification;
- limited history/query volume;
- standard freshness.

### CMIS Pro

- verified trade intelligence;
- advanced tokenomics/risk;
- whale intelligence;
- wallet behavior profiles;
- longer history;
- macro/regime intelligence;
- configurable alerts;
- higher usage limits.

### CMIS Intelligence

- wallet relationship graphs;
- historical risk-pattern engine;
- cross-chain capital flows;
- investigation mode;
- advanced evidence receipts/exports;
- premium APIs and agent access.

### CMIS Institutional

- high-throughput API;
- bulk wallet/token screening;
- custom risk policies;
- webhooks/streaming;
- long-term evidence retention;
- audit logs;
- service-level objectives;
- organization access controls;
- custom integrations/models.

Tier boundaries are product-planning concepts only and never change the underlying verification standard.

---

## 6. Recommended implementation sequence from the current boundary

Do not build premium analytics faster than the evidence foundation can support them.

### Completed immediate work

1. GitHub Issue #99 — deterministic pre-trade trade-size and impact analysis: **COMPLETE**.
2. Phase 11 top-account concentration primitives: **COMPLETE**.
3. Phase 11 wallet activity facts before labels: **COMPLETE**.
4. Phase 11 provenance-safe historical intelligence storage/comparison: **COMPLETE**.
5. Phase 11 Evidence Receipt / Proof Score integration and capability boundary: **COMPLETE**.

### Next accepted-milestone candidates — NOT YET ACTIVE

6. Define a new public-service/Scout-reliance contract before exposing Phase 11 intelligence primitives as callable services or automatic downstream inputs.
7. Define explicit inference and classification contracts before whale, insider, bot, accumulator, distributor, market-maker, or wallet-behavior labels are introduced.
8. Add wallet relationship evidence only after relationship scope, identity, provenance, and non-ownership semantics are formally accepted.
9. Add alert rules only when their underlying evidence fields have explicit scope, freshness, threshold, and persistence semantics.
10. Expand historical retention only where the source can support the claimed archival/continuous coverage; otherwise preserve sparse-sample semantics.

### Cross-chain expansion candidates

11. Mature Solana coverage field-by-field rather than treating Phase 10 as full Solana parity with X1.
12. Add direct Solana venue evidence only where scope/non-overlap semantics are defensible.
13. Begin chain-neutral capital-flow primitives after cross-chain identity/provenance contracts are stable.
14. Add Ethereum provider/verification work only after an explicit Ethereum capability table and acceptance plan exist.

### Productization candidates

15. Investigation mode and evidence export.
16. Premium authentication/quotas.
17. Streaming/webhook alerts.
18. Institutional audit/retention/access controls and service commitments.

None of these candidates is an active execution milestone merely by appearing in this roadmap. Each requires an explicit accepted scope before implementation begins.

---

## 7. Data and model governance principles

1. **Facts before interpretation.** Deterministic facts remain separate from Roberta/LLM interpretation.
2. **Providers are candidates.** Important claims should be checked against authoritative chain evidence where possible.
3. **Unknown remains unknown.** Missing evidence is not filled with model guesses.
4. **Inference is labeled.** Wallet relationships, risk similarity, and forecasts identify themselves as inference/probability.
5. **Evidence is reproducible.** Important conclusions retain enough provenance to reproduce/audit them.
6. **Freshness is explicit.** Live and historical observations preserve time/slot/block provenance where available.
7. **Cross-chain normalization does not erase chain differences.** Canonical fields preserve original chain/source provenance.
8. **Risk and proof are separate.** Risk level and evidence strength are different dimensions.
9. **No autonomous execution by implication.** Intelligence, monitoring, simulation, and pre-trade analysis do not authorize signing or execution.
10. **Premium does not change truth.** Paid access expands capability, not factual standards.

---

## 8. Strategic positioning

Liquidity Scout can remain the public-facing product identity.

CMIS can remain invisible infrastructure for basic users while becoming a direct premium product for advanced users, developers, agents, and institutions.

Suggested positioning:

> **CMIS is a blockchain evidence and intelligence service that converts raw market and chain activity into verified, explainable, machine-consumable intelligence.**

Short differentiator:

> **CMIS does not just report what a market source says happened. It attempts to determine what can actually be proven, records the evidence, and makes that verified intelligence reusable by agents and applications.**

---

## 9. Relationship to Roberta

CMIS supplies verified facts, historical features, evidence receipts, proof strength, confidence, and deterministic risk signals.

Roberta may use CMIS for broader market interpretation, historical-pattern reasoning, risk probability assessment, macro/crypto regime reasoning, cross-chain synthesis, final user explanations, and coordination of specialist agents.

Roberta must not silently promote an inference into a CMIS-verified fact, recompute proof strength, or collapse risk and evidence quality into one synthetic grade.

Conceptually:

```text
CMIS remembers and proves what happened.
Roberta reasons about what those patterns may mean.
```

---

## 10. Success criterion

CMIS should answer four different questions clearly:

1. **What was reported?**
2. **What can be independently verified?**
3. **How strong and complete is the evidence?**
4. **What remains unknown or unavailable under the accepted evidence contract?**

Historical-pattern and probabilistic interpretation can then be layered on top by CMIS intelligence features and Roberta without erasing the distinction between fact, proof quality, risk, and inference.
