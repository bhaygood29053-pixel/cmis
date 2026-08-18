# CMIS Product & Premium Service Roadmap

## Purpose

**CMIS — Cross-Chain Market Intelligence Service** is the deterministic evidence, verification, normalization, historical-intelligence, risk, and bounded pre-trade layer beneath chain-specific Scouts.

The canonical project architecture is:

```text
User / transport
      ↓
Roberta — coordinator and user-facing voice
      ↓
Chain Scout
      ↓
CMIS — deterministic intelligence authority
      ↓
Chain Provider / verified source
```

The repository was originally created as **Liquidity Scout**. That name is retained only for historical context and the compatibility Python namespace `liquidity_scout`; it is not a second current user-facing product beside Roberta.

The long-term goal is to make CMIS a premium blockchain-intelligence service that converts raw market and on-chain activity into **verified, explainable, auditable, and machine-consumable intelligence**.

Core principle:

> Premium users may receive more depth, history, speed, automation, analytics, and access, but never a weaker or different definition of truth.

Verification standards remain consistent across every service tier.

---

## Roadmap status — 2026-08-18

The original product-sequence numbering in this document predates later GitHub execution-phase numbering. They are not a one-to-one mapping.

Accepted milestones:

- **CMIS Phase 10 — Solana read-only provider foundation: COMPLETE.**
- **Evidence Receipts + Proof Score: COMPLETE.**
- **Remaining X1 evidence gaps: CLASSIFIED at an explicit fail-closed capability boundary.**
- **Deterministic pre-trade trade-size analysis: COMPLETE.**
- **CMIS Phase 11 — read-only Verified Intelligence foundation: COMPLETE.**
- **XDEX quote/history semantics: materially advanced with field-by-field bounded verification.**
- **Pinned XENCAT/native-XNT historical execution-fee model: 2800 ppm STRONGLY CORROBORATED / BOUNDED.**
- **Fail-closed route-scoped pre-trade evidence seam: COMPLETE.**
- **Deterministic explicit-policy concentration-threshold evaluation: COMPLETE.**

Phase 10 completion is recorded in [`PHASE_10_COMPLETION.md`](./PHASE_10_COMPLETION.md). Phase 11 completion is recorded in [`PHASE_11_COMPLETION.md`](./PHASE_11_COMPLETION.md).

CMIS contract `1.8.0` exposes Evidence Receipt / Proof Score requirements and a discoverable read-only `intelligence_foundation`. Phase 11 intelligence primitives remain outside `supported_services`, with `public_service_promoted = false` and `scout_reliance_promoted = false` until a separately accepted service contract authorizes promotion.

Recent accepted post-foundation work also established:

- XDEX 1-minute history timestamp/OHLC semantics for tested verified scope while keeping unverified volume semantics bounded;
- verified XDEX quote route/config identity and independently reproducible route-scoped price-impact semantics;
- verified quote-side slippage parameter percent units and current default behavior, while keeping quote tolerance distinct from expected execution slippage;
- a bounded 23-swap state-contiguous historical execution reconstruction strongly supporting 2800-ppm execution for the pinned XENCAT/native-XNT config and strongly rejecting 3000-ppm execution for that tested sequence;
- a hardened internal route-evidence seam that may expose only exact, fresh, scope-matched, accepted-proof price-impact and fee evidence to pre-trade analysis;
- deterministic explicit-policy threshold evaluation over canonical top-account concentration changes without creating whale/insider/behavioral or risk labels.

No controlled-execution milestone is active in CMIS. Transaction construction, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, and autonomous value movement remain unauthorized.

---

## 1. Stable architecture and ownership

```text
Users / channels
      ↓
Roberta
      ↓
X1 Scout / Solana Scout
      ↓
CMIS
      ↓
X1 / XDEX / Solana providers and verified sources
```

Authority flows downward:

```text
Roberta → Chain Scout → CMIS → Chain Provider
```

Verified information flows upward:

```text
Chain Provider → CMIS → Chain Scout → Roberta
```

### CMIS owns

- deterministic collection and normalization;
- blockchain/provider verification where accepted;
- source comparison and conflict handling;
- explicit confidence, proof, freshness, scope, and verification state;
- historical evidence storage;
- deterministic risk features;
- Evidence Receipts and Proof Scores;
- cross-chain canonical schemas;
- capability eligibility contracts;
- bounded analysis-only pre-trade calculations;
- future premium intelligence APIs and alerts when separately accepted.

### Chain Scouts own

- chain-specific investigation planning;
- choosing allowed CMIS services for the user objective;
- preserving exact CMIS status, provenance, limitations, and uncertainty;
- chain-specific interpretation without manufacturing provider facts.

### Roberta owns

- user intent and conversational coordination;
- specialist selection;
- broader/cross-chain synthesis;
- user-facing explanation and policy framing;
- human-review boundaries.

Roberta and Chain Scouts must not rewrite deterministic CMIS facts, recompute CMIS proof into a second source of truth, or promote unavailable evidence.

---

## 2. Completed verified-data foundation

### X1 / XDEX — COMPLETE / ACTIVE foundation

Accepted capabilities include, where their exact evidence contracts permit:

- exact asset/pool identity;
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
- deterministic trade-size analysis;
- bounded route-scoped price-impact and fee evidence where exact route/proof/freshness gates pass;
- fail-closed behavior for incomplete, stale, incompatible, or contradictory evidence.

Program-, pool-, route-, or sample-scoped completeness remains distinct from asset-wide/global X1 completeness.

### X1 evidence capability boundary — COMPLETE / ACTIVE

The capability registry records facts as `verified`, `bounded`, or `unavailable` instead of treating provider gaps as implicit promises.

Examples that remain bounded/unavailable include holder/beneficial-owner semantics, archival completeness, live-event semantics, and bridge operational/route/fee/capacity/lifecycle facts unless a newer accepted evidence contract explicitly promotes them.

XDEX semantics have advanced since the original boundary was created. Current accepted evidence is field- and scope-specific rather than a blanket statement that all XDEX quote/history semantics are either verified or unavailable.

### XDEX semantic and execution-evidence progress — ACTIVE / BOUNDED

Accepted current distinctions include:

- quote route and AMM-config identity can be verified for exact tested routes;
- route-scoped `priceImpactPct` can be independently reproduced where pool/reserve/config evidence is accepted;
- quote `slippage` uses percent units and current omitted-slippage behavior has been verified for tested scope;
- quote slippage tolerance / minimum-received behavior is **not** an expected execution-slippage estimate;
- XDEX history `t` and tested OHLC behavior have bounded corroboration; unverified history fields remain unpromoted;
- the pinned XENCAT/native-XNT 2800-ppm historical execution model is strongly corroborated by a state-contiguous completed-swap sequence;
- the observed 3000-ppm zero-slippage quote baseline is localized to the quote layer for that tested scope, not proven as a hidden executed fee;
- the private backend reason for the 2800→3000 quote behavior remains unavailable;
- global route optimality, fill quality, route quality, generic execution quality, and universal XDEX execution semantics remain unproven.

### Solana Phase 10 read-only foundation — COMPLETE

Solana is implemented beneath the same CMIS contract rather than as a separate intelligence stack.

Accepted components include:

- exact-mint identity through canonical Solana RPC;
- SPL Token and Token-2022 identity handling;
- canonical token supply and mint/freeze authority evidence;
- RPC slot/context provenance;
- optional largest-token-account concentration evidence that is not holder-total coverage;
- Jupiter read-only evidence when configured;
- Helius indexed evidence when configured;
- DEX Screener pair-scoped market evidence;
- deterministic cross-source price/supply gates;
- provenance-safe observation history;
- bounded/partial `asset_lookup`, `tokenomics`, `market_report`, `risk_check`, and narrow `historical_compare` services;
- environment-owned production composition and read-only live acceptance.

Solana ranking, pre-trade execution modeling, trade verification, verified asset-wide activity, signing, broadcasting, and custody remain unavailable until separately implemented and promoted.

---

## 3. Evidence quality and Verified Intelligence

### Evidence Receipts and Proof Score — COMPLETE / ACTIVE

CMIS produces deterministic evidence receipts and proof scores without rewriting the underlying service result.

Evidence receipts preserve available provenance, verification state, evidence scope, freshness indicators, disagreements, limitations, unresolved fields, and content-addressed identity.

Proof scores keep proof strength separate from risk. Missing evidence remains missing/unknown rather than becoming a fabricated false or zero value.

### CMIS Phase 11 read-only Verified Intelligence foundation — COMPLETE

Accepted foundations include:

- exact top-account concentration observations with raw rational evidence;
- compatible-scope numeric concentration-change comparison;
- neutral verified wallet activity facts without behavioral labels;
- bounded activity windows, first/last observed activity, transaction counts, and verified volume with explicit units;
- sanitized sparse historical storage for concentration, wallet activity, liquidity, supply, price, and activity;
- compatible-series comparison ordered by canonical observation time;
- no interpolation or zero-filled missing history;
- evidence-bound conclusions using exact Evidence Receipts and recomputed Proof Scores;
- content-addressed observation, receipt, conclusion, and evidence-bundle identities;
- explicit provider-reported versus verifier-observed evidence separation.

Phase 11 does **not** promote whale, insider, bot, market-maker, accumulator, distributor, ownership, relationship, scam, manipulation, or behavioral-intent claims.

### Explicit-policy concentration threshold — COMPLETE / INTERNAL FOUNDATION

CMIS can deterministically compare a canonical concentration change with an explicit caller-supplied versioned threshold and report only:

- `WITHIN_THRESHOLD`;
- `AT_THRESHOLD`;
- `EXCEEDS_THRESHOLD`.

This is policy evaluation, not a market fact and not behavioral/risk interpretation. There is no hidden default threshold, no public-service promotion, and no automatic Scout reliance.

---

## 4. Pre-trade analysis — COMPLETE foundation / bounded route evidence

`pre_trade_check` remains analysis only.

Accepted deterministic behavior includes:

- requested notional evaluation;
- verified notional-to-liquidity ratio where verified liquidity exists;
- versioned trade-size policy;
- fail-closed missing/conflicting liquidity behavior;
- explicit risk-evidence freshness policy;
- exact route-scoped internal evidence seam for selected advanced fields.

The route-evidence seam requires exact token-in/token-out/pool/AMM-config identity, an accepted CMIS evidence producer, explicit freshness, exact semantic/unit contracts, and accepted proof-basis labels. It does not accept arbitrary caller assertions.

Currently:

- route-scoped **price impact** may be available when the exact accepted proof gates pass;
- bounded **AMM/execution-model fee evidence** may be available for an exactly matched accepted route/evidence scope;
- XDEX quote slippage tolerance is explicitly rejected as an **expected execution slippage** estimate;
- expected execution slippage remains unavailable without a separately accepted execution-slippage observation contract;
- route quality, bridge dependency, transaction simulation, fill quality, and execution quality remain unavailable unless separately proven.

Every current result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission or advice to execute a trade.

---

## 5. Product direction

CMIS progresses through four capability layers.

### Layer A — Verified Data

Established substantially on X1 and as a bounded read-only foundation on Solana:

- identity;
- market/liquidity evidence;
- tokenomics and authorities;
- transaction/trade verification where supported;
- historical comparisons;
- deterministic risk;
- bounded pre-trade analysis;
- evidence receipts and proof scoring.

### Layer B — Verified Intelligence

Read-only deterministic foundations now exist for:

- top-account concentration and numeric changes;
- neutral wallet activity;
- sparse provenance-safe intelligence history;
- evidence-bound conclusions;
- explicit-policy concentration-threshold evaluation.

Future interpretation layers require separate accepted contracts before public/automatic Scout use:

- wallet behavior profiles;
- wallet relationship graphs;
- verified whale classifications;
- liquidity deterioration classifications;
- abnormal mint/burn/authority behavior;
- historical-pattern interpretation;
- broader cross-source disagreement intelligence.

### Layer C — Early Warning

Potential future monitoring includes:

- explicit evidence-backed risk thresholds;
- rapid liquidity removal;
- verified deployer-linked activity;
- unusual issuance/authority changes;
- market-structure changes;
- source disagreement/staleness;
- configurable alerts/webhooks.

No alert should imply ownership, intent, manipulation, or fraud beyond the accepted evidence/classification contract.

### Layer D — Cross-Chain Intelligence

- X1: active mature foundation;
- Solana: read-only Phase 10 foundation complete;
- Ethereum: future explicit provider/verification milestone;
- future chain-neutral identity/provenance schemas;
- future bridge/stablecoin/capital-flow evidence only after source semantics are accepted.

---

## 6. Premium capability candidates

These are product candidates, not active implementation authority:

1. deeper wallet intelligence after classification contracts are accepted;
2. wallet relationship evidence with explicit non-ownership semantics;
3. historical manipulation/risk-pattern similarity without unsupported accusations;
4. evidence-backed real-time alerting;
5. investigation mode and evidence export;
6. developer/agent API access, quotas, subscriptions, and webhooks;
7. longer retention only where archival/continuous coverage is actually proven;
8. chain-neutral capital-flow primitives;
9. Ethereum provider/verification foundation;
10. institutional audit/retention/access-control capabilities.

Potential service tiers may include Public, Pro, Intelligence, and Institutional offerings, but tier boundaries never change the verification standard.

---

## 7. Recommended implementation sequence from the current boundary

### Completed immediate work

1. deterministic pre-trade trade-size policy — **COMPLETE**;
2. CMIS Phase 11 concentration/wallet/history/evidence foundation — **COMPLETE**;
3. XDEX quote/history semantic verification — **BOUNDED FIELD-BY-FIELD PROGRESS ACCEPTED**;
4. pinned XDEX historical executed-fee reconstruction — **COMPLETE / STRONGLY CORROBORATED BOUNDED RESULT**;
5. route-scoped pre-trade evidence seam — **COMPLETE**;
6. explicit concentration-threshold evaluator — **COMPLETE**.

### Next accepted-milestone candidates — NOT YET ACTIVE

7. define a new public-service/Scout-reliance contract before exposing Phase 11 intelligence primitives as callable services;
8. define deterministic inference/classification contracts before whale, insider, bot, accumulator, distributor, market-maker, or behavioral labels;
9. add wallet relationship evidence only after scope, identity, provenance, and non-ownership semantics are formally accepted;
10. add alert rules only when underlying fields have explicit scope, freshness, threshold, persistence, and evidence semantics;
11. deepen XDEX route/execution evidence field-by-field without invoking transaction preparation as a shortcut to proof;
12. mature Solana coverage field-by-field rather than treating Phase 10 as full parity;
13. begin Ethereum only under an explicit capability table and acceptance plan;
14. productize investigation/evidence export and premium access only after the underlying deterministic services are stable.

None of these candidates is an active execution milestone merely because it appears here.

---

## 8. Governance principles

1. **Facts before interpretation.** Deterministic facts remain separate from Roberta/LLM interpretation.
2. **Providers are candidates.** Important claims are checked against authoritative chain evidence where possible.
3. **Unknown remains unknown.** Missing evidence is never filled with model guesses.
4. **Inference is labeled.** Relationship, behavior, risk-similarity, and forecast outputs identify their evidentiary status.
5. **Evidence is reproducible.** Material conclusions retain sufficient provenance for audit/reproduction.
6. **Freshness is explicit.** Live/historical observations preserve time/slot/block provenance where available.
7. **Cross-chain normalization preserves chain provenance.** Canonical fields do not erase source/chain differences.
8. **Risk and proof are separate.** Evidence strength is not risk severity.
9. **Route scope is not asset-wide scope.** One pool/config/route cannot silently become a global claim.
10. **No autonomous execution by implication.** Intelligence, monitoring, pre-trade analysis, and human review do not authorize signing or execution.
11. **Premium does not change truth.** Paid access expands capability, not factual standards.

---

## 9. Strategic positioning

CMIS is the canonical project/service identity for this repository. Roberta is the normal user-facing conversational coordinator in the accepted project architecture.

Suggested positioning:

> **CMIS is a blockchain evidence and intelligence service that converts raw market and chain activity into verified, explainable, machine-consumable intelligence.**

Short differentiator:

> **CMIS does not just report what a market source says happened. It attempts to determine what can actually be proven, records the evidence, and makes that verified intelligence reusable by agents and applications.**

---

## 10. Relationship to Roberta

CMIS supplies verified facts, historical features, evidence receipts, proof strength, confidence, deterministic risk signals, and accepted bounded pre-trade evidence.

Roberta may synthesize those results for broader market interpretation, cross-chain context, user policy, and normal human explanations. Roberta must not silently promote inference into a CMIS-verified fact, recalculate market/proof truth, or collapse risk and evidence quality into one synthetic grade.

Conceptually:

```text
CMIS verifies what the evidence supports.
Chain Scouts investigate within their chain.
Roberta coordinates and explains.
```

---

## 11. Success criterion

CMIS should answer four questions clearly:

1. **What was reported?**
2. **What can be independently verified?**
3. **How strong and complete is the evidence?**
4. **What remains unknown or unavailable under the accepted evidence contract?**

Historical-pattern and probabilistic interpretation may be layered on top only without erasing the distinction between fact, proof quality, risk, and inference.
