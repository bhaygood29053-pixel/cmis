# CMIS Product & Premium Service Roadmap

## Purpose

**CMIS — Cross-Chain Market Intelligence Service** is the deterministic evidence, verification, normalization, historical-intelligence, risk, and bounded pre-trade layer beneath chain-specific Scouts.

Canonical architecture:

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

The repository originally began as Liquidity Scout. The `liquidity_scout` Python namespace remains a compatibility implementation detail during incremental migration; it is not a separate current authority layer.

Core principle:

> Premium users may receive more depth, history, speed, automation, analytics, and access, but never a weaker or different definition of truth.

---

## Roadmap status — 2026-08-20

The original product-sequence numbering predates later GitHub execution-phase numbering. CMIS and Roberta phase numbers are separate and must not be treated as one shared sequence.

Accepted milestones:

- **CMIS Phase 10 — Solana read-only provider foundation: COMPLETE.**
- **Evidence Receipts + Proof Score: COMPLETE.**
- **Remaining X1 evidence gaps: CLASSIFIED at an explicit fail-closed capability boundary.**
- **Deterministic pre-trade trade-size analysis: COMPLETE.**
- **CMIS Phase 11 — read-only Verified Intelligence foundation: COMPLETE.**
- **First Phase 11 public-service / Scout-reliance promotion: COMPLETE for one narrow X1 service.**
- **CMIS capability contract: 1.9.0.**
- **XDEX quote/history semantics: materially advanced with field-by-field bounded verification.**
- **Pinned XENCAT/native-XNT historical execution-fee model: 2800 ppm STRONGLY CORROBORATED / BOUNDED.**
- **Fail-closed route-scoped pre-trade evidence seam: COMPLETE.**
- **Deterministic explicit-policy concentration-threshold evaluation: COMPLETE.**

The core Phase 11 `intelligence_foundation` remains read-only and non-promoted as a group:

```text
public_service_promoted = false
scout_reliance_promoted = false
```

CMIS 1.9.0 separately promotes exactly one wrapper service for X1:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
read_only = true
execution_authorized = false
```

This promotion does not make the foundation generally callable, does not establish holder-total or beneficial-owner semantics, and does not authorize behavioral labels or execution.

Roberta has adopted this exact service through X1 Scout with a service-specific CMIS `>=1.9.0` fail-closed promotion gate and readiness coverage. Solana remains unavailable/non-promoted for this service.

No controlled-execution milestone is active in CMIS. Transaction construction, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, and autonomous value movement remain unauthorized.

---

## 1. Stable architecture and ownership

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
- accepted read-only intelligence services.

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

## 2. Verified-data foundation

### X1 / XDEX — COMPLETE / ACTIVE foundation

Accepted capabilities include, where exact evidence contracts permit:

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

Program-, pool-, route-, provider-, or sample-scoped completeness remains distinct from asset-wide/global X1 completeness.

### X1 evidence capability boundary — COMPLETE / ACTIVE

CMIS records evidence as verified, bounded, partial, unavailable, conflicting, or insufficient rather than treating provider gaps as implicit promises.

Current provider-gap observations reinforce this boundary:

- the accepted bounded X1.Ninja `/v1/stream/trades` handshake probe returned HTTP `403` / `access_denied` for the current repository credential; no SSE event body was consumed and no stream schema/order/finality/reconnect/backfill/freshness semantics were inferred;
- a same-run XENCAT holder-looking comparison observed X1.Ninja candidate `116`, RPC token-account candidate `180`, and unique token-account-authority candidate `174`; the result remains `INSUFFICIENT_EVIDENCE` because enumeration completeness, holder semantics, wallet identity, and beneficial ownership are unverified;
- Warp Bridge machine-readable operational facts remain unavailable until an exact provenance-approved read URL and deterministic response contract are verified.

### XDEX semantic and execution-evidence progress — ACTIVE / BOUNDED

Accepted distinctions include:

- quote route and AMM-config identity can be verified for exact tested routes;
- route-scoped price impact can be independently reproduced where pool/reserve/config evidence is accepted;
- quote `slippage` uses percent units in tested scope;
- quote tolerance/minimum-received semantics are not expected execution slippage;
- selected history timestamp/OHLC semantics have bounded corroboration;
- the pinned XENCAT/native-XNT 2800-ppm historical execution model is strongly corroborated for its tested sequence;
- the separate 3000-ppm zero-slippage quote baseline is localized to the quote layer for tested scope;
- the private backend reason for that quote behavior remains unavailable;
- global route optimality, fill quality, route quality, generic execution quality, and universal XDEX execution semantics remain unproven.

### Solana Phase 10 read-only foundation — COMPLETE / BOUNDED

Solana remains beneath the same shared CMIS contract rather than forming a duplicate intelligence stack.

Accepted components include:

- exact-mint identity through canonical Solana RPC;
- SPL Token and Token-2022 handling;
- canonical token supply and mint/freeze authority evidence;
- RPC slot/context provenance;
- optional largest-token-account concentration evidence that is not holder-total coverage;
- Jupiter evidence where configured;
- Helius indexed evidence where configured;
- DEX Screener pair-scoped market evidence;
- deterministic cross-source price/supply gates;
- provenance-safe observation history;
- bounded/partial `asset_lookup`, `tokenomics`, `market_report`, `risk_check`, and narrow `historical_compare` services;
- environment-owned production composition and read-only live acceptance.

Recent Solana readiness work accepts a PYUSD Token-2022 fixture contract while keeping largest-account evidence gated by the dedicated RPC/readiness proof. Solana ranking, pre-trade execution modeling, trade verification, verified asset-wide activity, signing, broadcasting, and custody remain unavailable until separately implemented and promoted.

---

## 3. Evidence quality and Verified Intelligence

### Evidence Receipts and Proof Score — COMPLETE / ACTIVE

Evidence Receipts preserve available provenance, verification state, scope, freshness, disagreements, limitations, unresolved fields, and content-addressed identity.

Proof Score remains separate from risk. Missing evidence remains unknown rather than becoming fabricated false or zero.

### CMIS Phase 11 read-only Verified Intelligence foundation — COMPLETE

Accepted foundations include:

- exact top-account concentration observations with rational evidence;
- compatible-scope numeric concentration-change comparison;
- neutral verified wallet-activity facts without behavioral labels;
- bounded activity windows and verified-volume facts with explicit units where supported;
- sanitized sparse historical storage and compatible-series comparison;
- no interpolation or zero-filled missing history;
- evidence-bound conclusions using exact Evidence Receipts and recomputed Proof Scores;
- content-addressed observation, receipt, conclusion, and evidence-bundle identities;
- explicit provider-reported versus verifier-observed evidence separation.

Phase 11 does **not** promote whale, insider, bot, market-maker, accumulator, distributor, ownership, relationship, scam, manipulation, or behavioral-intent claims.

### First promoted intelligence service — COMPLETE / BOUNDED X1 ONLY

`concentration_change_intelligence/v1` is the first separately accepted public/Scout-reliance service built on the Phase 11 foundation.

Promotion requirements include:

- exact X1 asset identity;
- exact canonical CMIS-owned intelligence evidence id;
- trusted internal evidence resolution;
- deterministic bundle revalidation;
- exact content-addressed Evidence Receipts and recomputed Proof Scores;
- conclusion type limited to `top_account_concentration_change`;
- no caller-supplied intelligence bundle or proof replacement;
- no behavioral/ownership labels;
- no execution authorization.

The underlying foundation records remain non-promoted. Solana remains unavailable for this service.

### Explicit-policy concentration threshold — COMPLETE / INTERNAL FOUNDATION

CMIS can compare a canonical concentration change with an explicit versioned threshold and report only:

- `WITHIN_THRESHOLD`;
- `AT_THRESHOLD`;
- `EXCEEDS_THRESHOLD`.

This is policy evaluation, not a market fact and not behavioral/risk interpretation. There is no hidden default threshold and no automatic promotion beyond an explicitly accepted service contract.

---

## 4. Pre-trade analysis — COMPLETE foundation / bounded route evidence

`pre_trade_check` remains analysis only.

Accepted behavior includes requested notional evaluation, verified notional-to-liquidity ratio where verified liquidity exists, versioned trade-size policy, fail-closed missing/conflicting liquidity behavior, explicit freshness policy, and exact route-scoped internal evidence for selected advanced facts.

Current distinctions:

- route-scoped price impact may be available when exact accepted proof gates pass;
- bounded AMM/execution-model fee evidence may be available for exactly matched accepted scope;
- quote slippage tolerance is not expected execution slippage;
- expected execution slippage remains unavailable without a separately accepted observation contract;
- route quality, bridge dependency, transaction simulation, fill quality, and generic execution quality remain unavailable unless separately proven.

Every result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission or advice to execute a trade.

---

## 5. Product direction

### Layer A — Verified Data

Established substantially on X1 and as a bounded read-only foundation on Solana: identity, market/liquidity evidence, tokenomics/authorities, transaction/trade verification where supported, historical comparison, deterministic risk, bounded pre-trade analysis, Evidence Receipts, and Proof Score.

### Layer B — Verified Intelligence

Foundation complete; first narrow X1 public-service promotion complete. Future interpretation layers still require separate accepted deterministic contracts before broader public/automatic Scout use:

- inference/classification contracts;
- wallet behavior profiles;
- wallet relationship evidence;
- verified whale-like classifications only where formally defined and proven;
- liquidity deterioration classifications;
- abnormal mint/burn/authority behavior;
- historical-pattern interpretation;
- broader cross-source disagreement intelligence.

### Layer C — Early Warning

Potential future monitoring includes explicit evidence-backed thresholds, liquidity removal, verified deployer-linked activity, issuance/authority changes, market-structure changes, source disagreement/staleness, and configurable alerts/webhooks.

No alert may imply ownership, intent, manipulation, or fraud beyond an accepted evidence/classification contract.

### Layer D — Cross-Chain Intelligence

- X1: active mature foundation;
- Solana: read-only Phase 10 foundation complete and maturing field-by-field;
- Ethereum: future explicit provider/verification milestone;
- future bridge/stablecoin/capital-flow evidence only after source semantics are accepted.

---

## 6. Premium capability candidates

These are product candidates, not active implementation authority:

1. deterministic inference/classification contracts;
2. deeper wallet intelligence after classification contracts are accepted;
3. wallet relationship evidence with explicit non-ownership semantics;
4. historical risk-pattern similarity without unsupported accusations;
5. evidence-backed real-time alerting;
6. investigation mode and evidence export;
7. developer/agent API access, quotas, subscriptions, and webhooks;
8. longer retention only where archival/continuous coverage is proven;
9. chain-neutral capital-flow primitives;
10. Ethereum provider/verification foundation;
11. institutional audit/retention/access-control capabilities.

Premium tiers never change the verification standard.

---

## 7. Recommended implementation sequence from the current boundary

### Completed immediate work

1. deterministic pre-trade trade-size policy — **COMPLETE**;
2. CMIS Phase 11 concentration/wallet/history/evidence foundation — **COMPLETE**;
3. XDEX quote/history semantic verification — **BOUNDED FIELD-BY-FIELD PROGRESS ACCEPTED**;
4. pinned XDEX historical executed-fee reconstruction — **COMPLETE / STRONGLY CORROBORATED BOUNDED RESULT**;
5. route-scoped pre-trade evidence seam — **COMPLETE**;
6. explicit concentration-threshold evaluator — **COMPLETE**;
7. first public-service / Scout-reliance contract — **COMPLETE for X1 `concentration_change_intelligence/v1`**, with Roberta adoption/readiness complete.

### Next accepted-milestone candidates — NOT YET ACTIVE

8. define deterministic inference/classification contracts before whale, insider, bot, accumulator, distributor, market-maker, or behavioral labels;
9. add wallet relationship evidence only after scope, identity, provenance, and non-ownership semantics are formally accepted;
10. add alert rules only when underlying fields have explicit scope, freshness, threshold, persistence, and evidence semantics;
11. deepen XDEX route/execution evidence field-by-field without transaction preparation as a shortcut to proof;
12. mature Solana coverage field-by-field rather than treating Phase 10 as full parity;
13. begin Ethereum only under an explicit capability table and acceptance plan;
14. productize investigation/evidence export and premium access only after deterministic services are stable.

Parallel provider-gap work remains read-only and fail-closed: exact Warp Bridge source discovery, historical redundancy/source-independence evidence, holder-semantics evidence, and authenticated alternative-provider verification may advance without becoming facts merely because a probe exists.

None of these candidates is an execution milestone merely because it appears here.

---

## 8. Governance principles

1. **Facts before interpretation.**
2. **Providers are candidates until accepted verification exists.**
3. **Unknown remains unknown.**
4. **Inference is labeled and separately contracted.**
5. **Evidence is reproducible and content-addressable where material.**
6. **Freshness is explicit.**
7. **Cross-chain normalization preserves chain provenance.**
8. **Risk and proof are separate.**
9. **Route/pool/provider scope is not asset-wide scope.**
10. **No autonomous execution by implication.**
11. **Premium does not change truth.**

---

## 9. Relationship to Roberta

CMIS supplies verified facts, historical features, Evidence Receipts, Proof Score, confidence, deterministic risk signals, and accepted bounded pre-trade/intelligence services.

Roberta may synthesize those results for broader interpretation, cross-chain context, user policy, and normal human explanation. Roberta must not silently promote inference into a CMIS-verified fact, recalculate market/proof truth, or collapse risk and evidence quality into one synthetic grade.

```text
CMIS verifies what the evidence supports.
Chain Scouts investigate and interpret within their chain.
Roberta coordinates and explains.
```

---

## 10. Success criterion

CMIS should answer four questions clearly:

1. **What was reported?**
2. **What can be independently verified?**
3. **How strong and complete is the evidence?**
4. **What remains unknown or unavailable under the accepted evidence contract?**

Historical-pattern and probabilistic interpretation may be layered on top only without erasing the distinction between fact, proof quality, risk, and inference.
