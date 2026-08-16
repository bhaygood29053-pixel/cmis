# CMIS Product & Premium Service Roadmap

## Purpose

CMIS (Cross-Chain Market Intelligence Service) is the deterministic evidence, verification, normalization, historical-intelligence, and risk layer beneath Liquidity Scout and future specialist agents.

Liquidity Scout remains the market-intelligence agent people interact with. Roberta remains the higher-level reasoning and coordination agent. CMIS supplies trusted, machine-readable evidence to both.

The long-term goal is to make CMIS more than a market-data backend. CMIS should become a premium blockchain intelligence service that converts raw market and on-chain activity into **verified, explainable, auditable, and machine-consumable intelligence**.

Core principle:

> Premium users may receive more depth, history, speed, automation, analytics, and access, but never a weaker or different definition of truth.

Verification standards must remain consistent across every service tier.

---

## 1. Stable architecture

```text
Users / Agents
      |
      +--> Liquidity Scout
      |
      +--> Roberta
      |
      +--> Future chain Scouts / external agents
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
- premium intelligence APIs and alerts.

CMIS does **not** own:

- final user recommendations;
- unsupported predictions presented as facts;
- model-invented market values;
- autonomous trade authorization;
- claims about intent that cannot be proven from evidence.

Roberta and Liquidity Scout may explain and reason over CMIS results, but must not rewrite deterministic facts.

---

## 2. Current foundation

### Phase 1 — Trade verification foundation — COMPLETE

The current X1 trade-verification path can independently verify provider trade candidates against X1 RPC evidence.

Proven capabilities include:

- successful transaction confirmation;
- chain slot and timestamp identity checks;
- XDEX program detection;
- token-account delta analysis;
- multi-leg transaction handling;
- exact pool-leg matching;
- deterministic BUY/SELL verification;
- explicit evidence basis such as `EXACT_POOL_LEG_AMOUNTS`;
- promotion to `PROVIDER_SIDE_ONCHAIN_CONFIRMED` only when evidence supports it;
- gated semantics for unresolved LP event types;
- fail-closed behavior when evidence is incomplete or contradictory.

This establishes the CMIS trust model: provider observations are candidates, not canonical truth.

### Phase 2 — Runtime trade-verification integration — NEXT

Immediate work remains:

1. expose `trade_verification` through the normal CMIS HTTP runtime;
2. add service capability discovery and HTTP contract tests;
3. automate provider-event ingestion into CMIS verification;
4. return verified trade envelopes without requiring manual probe commands;
5. keep Signal/Ollama/Roberta integration downstream until runtime tests pass;
6. preserve gated LP semantics until independently verified.

Target flow:

```text
Market event candidate
        |
        v
CMIS trade_verification
        |
        v
Direct chain verification
        |
        v
Verified CMIS envelope
        |
        v
Liquidity Scout / Roberta
```

---

## 3. Product direction

CMIS should progress through four capability layers.

### Layer A — Verified Data

- asset identity;
- market reports;
- liquidity;
- trade verification;
- tokenomics;
- authority status;
- historical comparisons;
- deterministic risk checks;
- pre-trade analysis.

### Layer B — Verified Intelligence

- wallet behavior profiles;
- wallet relationship graphs;
- verified whale activity;
- liquidity deterioration analysis;
- token-distribution changes;
- abnormal mint/burn/authority behavior;
- historical pattern comparison;
- cross-source disagreement detection.

### Layer C — Early Warning

- real-time risk thresholds;
- suspicious wallet-cluster movement;
- rapid liquidity removal;
- insider-linked selling;
- unusual minting or authority changes;
- abnormal market-structure changes;
- historical scam-pattern similarity acceleration;
- configurable alerts and webhooks.

### Layer D — Cross-Chain Intelligence

- X1 first;
- Solana next;
- Ethereum groundwork and later integration;
- chain-neutral canonical schemas;
- cross-chain wallet/entity relationships when defensible;
- bridge and stablecoin-flow analysis;
- cross-chain capital-flow intelligence;
- chain-by-chain source and proof provenance.

---

## 4. Premium capability roadmap

### 4.1 CMIS Evidence Receipts

Every material CMIS conclusion should be able to produce a structured evidence package containing, where applicable:

- transaction signature/hash;
- chain;
- block/slot;
- observed timestamp;
- provider candidate observations;
- relevant program/contract IDs;
- relevant token accounts or addresses;
- exact token movements;
- source timestamps;
- verification method;
- verification level;
- confidence/completeness;
- warnings and unresolved fields.

Example concept:

```text
CMIS EVIDENCE RECEIPT
Trade direction: SELL
Identity: verified
Pool leg: exact match
Verification basis: EXACT_POOL_LEG_AMOUNTS
Evidence strength: STRONG
```

This should become a defining CMIS premium feature: **do not merely return an answer; return the evidence behind it.**

---

### 4.2 CMIS Proof Score

Develop an evidence-quality score that reflects what CMIS can actually prove.

Example:

```text
Transaction identity      100/100
Trade direction           100/100
Token amounts             100/100
Pool identity             100/100
Wallet attribution         65/100
Human intent               N/A

Overall evidence: STRONG
```

Rules:

- scores must be deterministic or reproducibly derived;
- missing evidence must not be converted to high confidence;
- intent must remain distinct from observable behavior;
- confidence and risk must not be conflated;
- a risky token can still have strongly verified facts.

---

### 4.3 Wallet Intelligence

Build behavioral wallet profiles using verified activity rather than unsupported labels.

Potential classifications:

- whale;
- early buyer;
- repeated accumulator;
- repeated distributor;
- LP provider;
- high-frequency trader;
- bot-like behavior;
- deployer-linked;
- market-maker-like;
- newly funded;
- historically profitable when sufficient history exists;
- insider-risk candidate when evidence supports the relationship.

Every label should include:

- supporting evidence;
- confidence;
- observation window;
- reason for classification;
- distinction between fact, heuristic, and inference.

---

### 4.4 Wallet Relationship Graphs

CMIS should eventually detect defensible relationships among apparently independent wallets.

Possible evidence:

- common funding source;
- deployer-to-wallet distributions;
- repeated synchronized activity;
- common LP participation;
- shared counterparties;
- bridge or exchange-flow relationships;
- recurring transaction sequences.

Graph conclusions must preserve uncertainty. A shared funding source may be evidence of association, not proof of common ownership.

---

### 4.5 Historical Scam & Manipulation Pattern Intelligence

Build a cross-chain historical pattern library using older blockchain events.

Candidate event classes:

- liquidity rugs;
- insider exits;
- pump-and-dumps;
- wash trading;
- Sybil activity;
- suspicious token distribution;
- mint abuse;
- freeze/authority abuse;
- slow rugs;
- liquidity manipulation;
- bot-driven artificial activity;
- coordinated wallet dumping.

CMIS should extract verified features from historical cases. Roberta may compare a current project against those patterns and produce probabilistic risk interpretation.

Target result:

```text
Historical similarity
Liquidity-exit patterns       84%
Insider-distribution patterns 71%
Normal-launch patterns        26%

Current risk interpretation: HIGH
Confidence: MODERATE
```

Important rule:

CMIS/Roberta must not say a project is definitively a scam solely because it resembles historical cases. The system should identify **risk patterns, similarity, and evidence**, not make unsupported accusations.

---

### 4.6 Real-Time Early Warning Service

Premium users should eventually be able to monitor assets, pools, wallets, or ecosystems continuously.

Examples:

- liquidity drops beyond a configured threshold;
- deployer-linked wallet begins distributing tokens;
- cluster of related wallets starts selling;
- LP removal accelerates;
- mint authority becomes active or changes;
- unusual issuance occurs;
- verified whale accumulation or distribution begins;
- historical scam-pattern similarity crosses a risk threshold;
- source disagreement or stale-data condition appears.

Alert output should include:

- what changed;
- when it changed;
- why the alert fired;
- supporting evidence;
- confidence;
- risk impact;
- whether the condition is continuing, worsening, or resolved.

---

### 4.7 Verified Whale Intelligence

A whale alert should answer more than “large transaction detected.”

CMIS should attempt to determine:

- trade vs transfer vs LP action vs bridge movement;
- BUY/SELL direction when provable;
- size relative to pool liquidity;
- size relative to recent volume;
- wallet historical behavior;
- deployer or cluster relationships;
- whether the activity is accumulation or distribution over time;
- whether similar actions preceded prior market moves.

This can become a standalone premium feed.

---

### 4.8 Macro & Market-Regime Intelligence

Add a future CMIS macro data layer to support Roberta's crypto forecasts and probability assessments.

Potential verified inputs:

- policy-rate direction;
- Treasury-yield trends;
- yield-curve measures;
- inflation trends;
- labor-market indicators;
- central-bank balance-sheet/liquidity measures;
- money-supply trends;
- dollar strength;
- credit spreads;
- equity-market conditions;
- BTC/ETH market conditions;
- stablecoin supply and flows;
- DEX volume and liquidity;
- chain-specific activity.

CMIS should normalize and timestamp these facts. Roberta can then classify regimes and compare historical periods.

Example:

```text
Policy trend:             EASING
Liquidity trend:          IMPROVING
Dollar pressure:          DECLINING
Stablecoin liquidity:     EXPANDING
Crypto risk appetite:     RISING
Historical similarity:    78%
Confidence:               MODERATE-HIGH
```

This is a forecasting-support tool, not a guarantee of future prices.

---

### 4.9 Cross-Chain Capital-Flow Intelligence

When Solana and Ethereum support mature, CMIS should answer questions such as:

- where liquidity is increasing or leaving;
- where stablecoins are moving;
- which chain is gaining trading activity;
- whether bridge flows are increasing;
- whether an asset's liquidity is migrating between chains;
- whether whale activity is moving from one ecosystem into another.

Target concept:

```text
Ethereum -> Solana -> X1
       verified flow evidence
```

This service should distinguish direct observed flows from inferred capital rotation.

---

### 4.10 CMIS Investigation Mode

Allow a user or agent to submit a token, wallet, transaction, pool, or project for a structured investigation.

Possible investigation package:

```text
TOKEN INVESTIGATION
|- identity
|- creator/deployer
|- authority state
|- supply history
|- liquidity history
|- LP behavior
|- related-wallet graph
|- verified whale activity
|- suspicious transaction sequences
|- mint/burn events
|- historical pattern matches
|- risk findings
|- evidence receipts
`- unresolved questions
```

Roberta can transform the evidence package into a human-readable forensic report while preserving CMIS evidence references.

---

### 4.11 Developer & Agent Intelligence API

CMIS should eventually support third-party applications and autonomous agents, not only Liquidity Scout and Roberta.

Potential future services:

```text
/v1/cmis/trade-verify
/v1/cmis/token-risk
/v1/cmis/wallet-profile
/v1/cmis/wallet-graph
/v1/cmis/liquidity-risk
/v1/cmis/scam-pattern
/v1/cmis/market-regime
/v1/cmis/capital-flow
/v1/cmis/investigation
```

The existing `/v1/cmis` service envelope should remain the architectural foundation unless there is a compelling reason to expose dedicated convenience endpoints later.

Potential premium access patterns:

- API keys;
- usage quotas;
- pay-per-call;
- subscription tiers;
- webhooks;
- streaming feeds;
- agent/MCP access;
- bulk screening;
- evidence export.

---

## 5. Proposed service tiers

### CMIS Public

- basic asset/market information;
- basic deterministic verification;
- limited history;
- limited query volume;
- standard freshness.

### CMIS Pro

- verified trade intelligence;
- advanced tokenomics/risk;
- whale intelligence;
- wallet behavior profiles;
- longer historical windows;
- macro market-regime intelligence;
- configurable alerts;
- higher usage limits.

### CMIS Intelligence

- wallet relationship graphs;
- historical scam-pattern engine;
- cross-chain capital flows;
- investigation mode;
- advanced evidence receipts;
- evidence exports;
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
- custom integrations and models.

Tier boundaries are product-planning concepts only and should not affect the underlying verification standard.

---

## 6. Recommended implementation sequence

Do not build premium analytics before the evidence foundation is reliable.

### Near term

1. Complete CMIS Trade Phase 2 runtime integration.
2. Add automated trade-candidate ingestion.
3. Persist verified trade evidence in a clean audit-friendly schema.
4. Finish current deterministic market/tokenomics/risk foundations.
5. Keep Liquidity Scout and Roberta consuming only structured CMIS results.

### Next

6. Build evidence receipts and proof metadata.
7. Add wallet activity history.
8. Add wallet relationship primitives.
9. Add verified whale intelligence.
10. Add early-warning rules.

### Expansion

11. Add Solana provider/verification support behind the same CMIS contract.
12. Begin cross-chain canonical schemas and capital-flow primitives.
13. Build historical scam/manipulation dataset and feature extraction.
14. Add Roberta probabilistic pattern interpretation.
15. Add macro/market-regime data ingestion and historical regime analysis.

### Productization

16. Investigation mode.
17. Premium API quotas and authentication tiers.
18. Streaming/webhook alerts.
19. Evidence exports and audit retention.
20. Institutional controls and service commitments.
21. Ethereum provider and verification expansion when X1/Solana architecture is stable.

---

## 7. Data and model governance principles

CMIS premium value depends on trust. Preserve these rules:

1. **Facts before interpretation.** Deterministic facts are stored separately from Roberta/LLM interpretation.
2. **Providers are candidates.** Important claims can be verified against authoritative chain evidence when possible.
3. **Unknown remains unknown.** Missing evidence is not filled with model guesses.
4. **Inference is labeled.** Wallet relationships, scam similarity, and forecasts must identify themselves as inference/probability where appropriate.
5. **Evidence is reproducible.** Important conclusions should carry enough metadata to reproduce or audit the decision.
6. **Freshness is explicit.** Live and historical observations retain timestamps.
7. **Cross-chain normalization does not erase chain differences.** Every canonical field must preserve its original chain/source provenance.
8. **Risk and proof are separate.** A high-risk finding can be strongly evidenced; a low-risk finding can still have incomplete evidence.
9. **No autonomous execution by implication.** Intelligence, monitoring, simulation, and pre-trade analysis do not authorize signing or execution.
10. **Premium does not change truth.** Paid access expands capability, not factual standards.

---

## 8. Strategic positioning

Publicly, Liquidity Scout can remain the product identity users recognize.

CMIS can remain invisible infrastructure for basic users while becoming a direct premium product for advanced users, developers, agents, and institutions.

Suggested positioning:

> **CMIS is a blockchain evidence and intelligence service that converts raw market and chain activity into verified, explainable, machine-consumable intelligence.**

A shorter differentiator:

> **CMIS does not just report what a market source says happened. It attempts to determine what can actually be proven, records the evidence, and makes that verified intelligence reusable by agents and applications.**

---

## 9. Relationship to Roberta

CMIS supplies verified facts, historical features, evidence, confidence, and deterministic risk signals.

Roberta may use CMIS for:

- broader market interpretation;
- historical-pattern reasoning;
- scam-risk probability assessment;
- macro/crypto regime reasoning;
- cross-chain synthesis;
- final user explanations;
- coordinated use of multiple specialist agents.

Roberta must not silently promote an inference into a CMIS-verified fact.

Conceptually:

```text
CMIS remembers and proves what happened.
Roberta reasons about what those patterns may mean.
```

---

## 10. Success criterion

CMIS should eventually answer four different questions clearly:

1. **What was reported?**
2. **What can be independently verified?**
3. **What historical patterns does it resemble?**
4. **What probabilistic interpretation follows from those verified facts?**

Keeping those four layers separate is the foundation for making CMIS a credible premium intelligence service rather than another crypto-data API.
