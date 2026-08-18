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

Current execution milestone:

> **CMIS Phase 10 — Solana Provider read-only foundation: COMPLETE.**

Phase 10 completion is recorded in [`PHASE_10_COMPLETION.md`](./PHASE_10_COMPLETION.md) and GitHub Issue #78. The final production-composition change was merged in PR #158.

The accepted system now has:

- a mature X1/XDEX deterministic market and verification foundation;
- normal CMIS runtime service composition;
- versioned Scout ↔ CMIS capability discovery;
- persisted verification evidence;
- deterministic X1 trade verification and bounded verified-activity coverage;
- deterministic risk and bounded pre-trade analysis;
- a read-only Solana provider/runtime foundation beneath the same CMIS contract;
- read-only Solana live acceptance in GitHub Actions.

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
- cross-chain canonical schemas;
- capability eligibility contracts;
- future premium intelligence APIs and alerts.

CMIS does **not** own:

- unsupported predictions presented as facts;
- model-invented market values;
- autonomous trade authorization;
- claims about intent that cannot be proven from evidence.

Roberta and Liquidity Scout may explain and reason over CMIS results, but must not rewrite deterministic facts.

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

### CMIS capability/runtime contract — COMPLETE / ACTIVE

The CMIS runtime exposes a versioned machine-readable capability contract. Chain/service combinations are explicitly classified as supported, bounded, partial, or unavailable.

This prevents downstream Scouts from assuming that a service exists merely because another chain supports it.

See [`CMIS_CAPABILITY_CONTRACT.md`](./CMIS_CAPABILITY_CONTRACT.md).

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
- bounded pre-trade analysis.

### Layer B — Verified Intelligence

Future/expanding capabilities:

- wallet behavior profiles;
- wallet relationship graphs;
- verified whale activity;
- liquidity deterioration analysis;
- token-distribution changes;
- abnormal mint/burn/authority behavior;
- historical pattern comparison;
- cross-source disagreement detection.

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

### 4.1 Evidence Receipts and Proof Metadata

Every material CMIS conclusion should eventually be exportable as a structured evidence package containing the applicable transaction/block identity, source observations, program/contract identities, token movements, verification method, evidence level, confidence/completeness, warnings, and unresolved fields.

CMIS should not merely return an answer; it should make the supporting evidence auditable.

### 4.2 CMIS Proof Score

Develop a deterministic/reproducible evidence-quality score that measures what CMIS can actually prove.

Rules:

- missing evidence never becomes high confidence;
- intent remains distinct from observable behavior;
- proof strength and risk are separate dimensions;
- a risky asset can have strongly verified facts.

### 4.3 Wallet Intelligence

Build behavior profiles based on verified history rather than unsupported labels, such as:

- whale/large participant;
- early buyer;
- accumulator/distributor;
- LP provider;
- high-frequency or bot-like behavior;
- deployer-linked candidate;
- market-maker-like behavior;
- newly funded wallet;
- historically profitable behavior when sufficient history exists.

Every classification should state the evidence, observation window, confidence, and whether it is fact, heuristic, or inference.

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

## 6. Recommended implementation sequence from the Phase 10 boundary

Do not build premium analytics faster than the evidence foundation can support them.

### Next execution work — define in a new tracker before coding

1. Choose and document the Phase 11 scope rather than silently expanding Phase 10.
2. Preserve X1 and Solana regression/live acceptance as mandatory gates.
3. Prioritize evidence-receipt/proof metadata and richer persisted history before high-level probabilistic labels.
4. Add wallet activity primitives before wallet relationship/insider inference.
5. Add alert rules only when their underlying evidence fields have explicit scope and freshness semantics.

### Cross-chain expansion

6. Mature Solana coverage field-by-field rather than treating Phase 10 as full Solana parity with X1.
7. Add direct Solana venue evidence only where scope/non-overlap semantics are defensible.
8. Begin chain-neutral capital-flow primitives after cross-chain identity/provenance contracts are stable.
9. Add Ethereum provider/verification work only after an explicit Ethereum capability table and acceptance plan exist.

### Productization

10. Investigation mode and evidence export.
11. Premium authentication/quotas.
12. Streaming/webhook alerts.
13. Institutional audit/retention/access controls and service commitments.

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

CMIS supplies verified facts, historical features, evidence, confidence, and deterministic risk signals.

Roberta may use CMIS for broader market interpretation, historical-pattern reasoning, risk probability assessment, macro/crypto regime reasoning, cross-chain synthesis, final user explanations, and coordination of specialist agents.

Roberta must not silently promote an inference into a CMIS-verified fact.

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
3. **What historical patterns does it resemble?**
4. **What probabilistic interpretation follows from those verified facts?**

Keeping those layers separate is the foundation for a credible premium intelligence service rather than another crypto-data API.
