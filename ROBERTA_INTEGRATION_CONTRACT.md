# Roberta ↔ Chain Scout ↔ CMIS Integration Contract

## Purpose

This document is the source-of-truth authority boundary between **Roberta**, the chain-specific **Scouts**, and **CMIS** (the Cross-Chain Market Intelligence Service evolved from Liquidity Scout).

```text
Roberta
  ↓
Chain Scout
  ↓
CMIS
  ↓
Chain Provider
```

Authority flows downward:

**Roberta → Chain Scout → CMIS → Chain Provider**

Verified information flows upward:

**Chain Provider → CMIS → Chain Scout → Roberta**

CMIS supplies deterministic facts, evidence, risk analysis, and explicit uncertainty. Roberta owns user intent, policy, coordination, broader reasoning, approval boundaries, and final synthesis.

**Phase 10 is complete. Phase 11 controlled execution is locked/not started.**

---

## 1. Authority boundary

### Roberta owns

- user interaction and user intent;
- user policy and stable user context;
- specialist selection and coordination;
- cross-chain/higher-level reasoning;
- final user-facing synthesis;
- human-review/approval workflow boundaries.

Roberta does **not** own provider calculations, live market reconstruction, CMIS verification rules, or transaction execution.

### Chain Scouts own

- chain-specific planning and interpretation;
- choosing allowed CMIS investigations for the user objective;
- preserving exact CMIS status, provenance, limitations, and uncertainty;
- reporting structured specialist findings to Roberta.

Chain Scouts do **not** manufacture provider facts or silently upgrade partial CMIS evidence.

### CMIS owns

- asset discovery/resolution;
- deterministic live market collection and normalization;
- asset/pool aggregation where scope is proven;
- rankings and historical comparisons where supported;
- tokenomics/authority evidence;
- burn/mint intelligence where verified;
- evidence/provenance storage and exact verification lookup;
- independent-source comparison and data-quality rules;
- deterministic risk calculations;
- bounded analysis-only pre-trade calculations;
- source timestamps, confidence, warnings, errors, and explicit unavailable states;
- the machine-readable chain/service capability manifest.

### Providers own

Chain-specific transport/parsing beneath CMIS, including X1.Ninja/XDEX, X1 RPC, Solana RPC, Jupiter, Helius, DEX/pool/indexer adapters, scanners, and verification plumbing.

Roberta and Chain Scouts must not reproduce provider or CMIS calculations to manufacture a second market fact.

---

## 2. Source-of-truth rule

For live market, liquidity, tokenomics, verification, and risk facts:

**Fresh verified CMIS/provider evidence overrides remembered, checkpointed, or conversational values.**

Never invent or substitute unavailable values for:

- prices;
- liquidity;
- volume;
- holders;
- supply;
- rankings;
- burn/mint totals;
- token/mint addresses;
- pool addresses;
- `#LPs`;
- authority status;
- verification outcomes;
- risk/safety metrics;
- slippage;
- price impact;
- routes;
- execution fees;
- transaction simulation.

If a fact cannot be verified, CMIS represents it as unavailable, ambiguous, partial, unverified, insufficient evidence, conflict, or error according to the accepted service contract.

Roberta preserves that state.

---

## 3. Capability handshake — authoritative runtime eligibility

CMIS publishes the deployed chain/service contract at:

```text
GET /v1/cmis/capabilities
```

The accepted Phase 10 contract uses capability schema `1` and a versioned CMIS contract. Every known chain/service combination is explicitly classified with:

- `state`: `supported`, `bounded`, `partial`, or `unavailable`;
- `callable`;
- `requirements`;
- `limitations`.

The shared Scout-side CMIS client performs a lazy capability handshake before service POSTs and caches a successfully validated manifest for that client instance.

Current guard rules:

- unsupported/malformed capability schema → fail closed;
- CMIS contract older than the Scout's minimum accepted contract → fail closed;
- malformed/unclassified chain/service records → fail closed;
- explicitly non-callable capability → fail before the service POST;
- `bounded`/`partial` capability may be callable, but its limitations remain material;
- unknown chains never fall back to X1 or another chain.

Roberta does **not** call `/v1/cmis/capabilities` directly. The handshake belongs to the **Chain Scout ↔ CMIS** boundary.

Documentation describes intended behavior; the live capability manifest is authoritative for what a deployed CMIS instance can actually serve.

---

## 4. Current shared service surface

The current Roberta/Scout contract includes:

- `asset_lookup`;
- `market_report`;
- `rank`;
- `historical_compare`;
- `tokenomics`;
- `risk_check`;
- `pre_trade_check`;
- `verification_evidence`.

Additional internal/chain-specific services can exist inside CMIS, but Roberta must use only tested callable contracts through the appropriate Chain Scout.

Common service statuses are:

- `ok`;
- `partial`;
- `unavailable`;
- `ambiguous`;
- `error`.

Evidence outcomes such as `AGREEMENT`, `CONFLICT`, and `INSUFFICIENT_EVIDENCE` remain evidence state inside the CMIS result. They must not be silently rewritten into a stronger fact.

---

## 5. Chain-specific boundary

### X1

X1 is the mature CMIS surface. The accepted architecture includes market reporting, rankings/history, tokenomics, deterministic risk, evidence lookup, trade/activity verification tooling, and bounded analysis-only pre-trade behavior where the live manifest permits them.

X1 evidence-completeness gaps remain explicit and may be independently blocked by provider semantics/live-source availability. A later architectural phase being complete does not permit those gaps to be guessed away.

### Solana

Phase 10 added a separate Solana provider path beneath the same CMIS contracts rather than duplicating CMIS.

Accepted read-only foundation includes exact-mint identity, canonical RPC tokenomics, SPL Token/Token-2022 handling, bounded market/risk evidence, source cross-checks, provenance-safe observation history, and narrow historical comparison.

Solana rules include:

- exact mint identity where the capability requires it;
- no symbol/name substitution when identity is not proven;
- no Solana → X1 fallback;
- pair-scoped DEX values are not asset-wide totals;
- indexed/provider labels remain source evidence, not Roberta's final safety decision;
- optional provider/runtime configuration fails closed when absent;
- service availability is capability-specific rather than a blanket chain enablement claim.

---

## 6. Common response envelope

CMIS responses preserve a structured envelope such as:

```json
{
  "service": "market_report",
  "chain": "x1",
  "status": "ok",
  "asset": {},
  "data": {},
  "risk": null,
  "confidence": {},
  "sources": [],
  "observed_at": null,
  "warnings": [],
  "errors": []
}
```

Service-specific fields may extend `data`, `risk`, and `confidence`, but these properties remain mandatory design goals:

- deterministic facts;
- source traceability;
- timestamps/block/slot provenance where available;
- verification state;
- confidence/data quality;
- uncertainty;
- warnings;
- explicit errors/unavailability.

---

## 7. Market aggregation and scope

When sufficient evidence exists, CMIS may report asset-wide market information rather than silently presenting one pool as the whole asset.

Responses must distinguish:

- asset-wide metrics;
- program-scoped metrics;
- selected-pool metrics;
- individual-pool/pair metrics;
- partial coverage;
- unavailable coverage.

One venue/pair's liquidity or volume must not be relabeled as chain-wide/asset-wide truth without a proven aggregation/coverage contract.

---

## 8. `verification_evidence`

**Status: accepted and runtime-callable where the capability manifest permits it.**

Trust path:

```text
fact-specific verifier
  ↓
sanitized verification envelope
  ↓
content-addressed evidence ledger
  ↓
exact lookup
  ↓
CMIS
  ↓
Chain Scout / Roberta
```

Roberta may request evidence only through accepted exact selectors. Roberta must not submit raw verifier/provider objects, choose persistence paths, or reconstruct verification state.

Important behavior:

- only CMIS-promotable verified agreement may expose a promoted fact value/unit;
- stale/non-promotable agreement remains non-promoted;
- conflicts/insufficient evidence remain explicit;
- persisted evidence is sanitized/content-addressed;
- source identity, role, timestamps, quality, and verification state are preserved.

---

## 9. `risk_check`

**Status: implemented, deterministic, and runtime-callable where advertised.**

Risk outcomes are:

- `PASS`;
- `WARN`;
- `BLOCK`.

Risk findings must remain explainable/reproducible. Roberta may interpret a CMIS risk result in broader context but must not recalculate live market facts, invent a score, or strengthen incomplete evidence.

A service-level `ok` may legitimately contain risk `WARN` or `BLOCK`; service completeness and risk severity are separate concepts.

---

## 10. `pre_trade_check` — bounded analysis-only contract

**Status: implemented on the accepted X1 path where the capability manifest permits it.**

CMIS can calculate from already-verified evidence:

- proposed trade notional;
- verified asset-wide liquidity used by the risk result;
- `notional_to_liquidity_ratio`;
- deterministic warning/block notional thresholds when explicit policy ratios are configured;
- risk-evidence age when temporal evidence is valid.

CMIS does **not** invent default trade-size/freshness thresholds.

Advanced execution estimates remain unavailable unless/until a verified producer is implemented:

- slippage;
- price impact;
- route quality;
- bridge dependency;
- fees;
- transaction simulation.

Unavailable capability values remain `null` with explicit reason/evidence requirements. CMIS must not substitute zero, a heuristic percentage, guessed route, or assumed fee.

If an explicitly required capability is unavailable, the bounded analysis fails closed according to the accepted pre-trade contract.

Every current pre-trade result preserves the equivalent of:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` means only that the deterministic checks actually performed did not produce a warning/block. It is **not** permission to trade.

Roberta must not reinterpret a PASS, size ratio, risk result, or human review as authorization to prepare, sign, broadcast, or autonomously execute a transaction.

---

## 11. Confidence, provenance, and evidence rules

CMIS confidence/data quality can reflect:

- identity verification;
- source availability/freshness;
- units/semantics verification;
- LP/pair/program coverage;
- RPC verification;
- independent-source agreement/conflict;
- historical/scanner coverage;
- calculation completeness;
- pre-trade size/freshness completeness;
- availability of explicitly required capabilities.

Where available, preserve:

- source name/role;
- chain;
- asset/pool/pair identity;
- observation time;
- block/slot;
- fact identity;
- calculation/service version;
- verification result;
- warnings/errors.

Two observations are not independent merely because they carry different provider labels. Independence is a deterministic CMIS determination.

Roberta may explain confidence; it must not turn low/incomplete evidence into a verified fact.

---

## 12. Failure rules

CMIS, Chain Scouts, and Roberta must fail safely.

They must not:

- substitute remembered values for unavailable live facts;
- invent LPs, supply, holders, rankings, burns, mints, or authorities;
- infer circulating supply from total supply without verification;
- average conflicting facts unless a documented deterministic rule permits it;
- promote a fact when required identity, units, semantics, freshness, scope, or independence is unproven;
- invent slippage, price impact, routes, fees, or simulation results;
- treat unavailable advanced pre-trade capability as zero risk;
- silently route an unsupported chain to another chain;
- bypass the capability manifest to force a non-callable service.

---

## 13. Roberta consumption rules

When Roberta needs market/chain intelligence:

1. Roberta preserves user intent and policy.
2. Roberta selects the relevant Chain Scout.
3. The Scout plans only allowed chain-specific CMIS work.
4. The shared CMIS client validates live capability eligibility.
5. CMIS/provider code collects/calculates deterministic facts.
6. CMIS returns structured evidence with provenance/uncertainty.
7. The Scout interprets chain-specific meaning without inventing facts.
8. Roberta synthesizes the specialist result for the user.

For `pre_trade_check`, Roberta may phrase/explain CMIS output but must not calculate replacement size ratios, slippage, price impact, routes, fees, simulations, or deterministic risk results.

If an execution estimate is unavailable, Roberta says it is unavailable.

---

## 14. Human approval and execution boundary

Roberta Phase 9 human approval is a resumable **review boundary** over one exact proposal/scope. It is not a signing credential or reusable future authority.

No current CMIS/Scout result or Phase 9 approval by itself authorizes:

- transaction preparation for execution;
- wallet signing;
- broadcasting;
- custody;
- autonomous live trading;
- autonomous bridge transfer;
- value movement.

**Phase 11 — Controlled Execution remains planned/locked and has not started.**

Any future execution milestone must separately define simulation, transaction preparation, exact approval consumption/revalidation, current-precondition checks, signing/broadcast scope, replay protection, and failure behavior. None of that authority is implied by Phase 10 completion.

---

## 15. Core integration principle

**CMIS determines what its verified evidence supports now.**

**Chain Scouts determine what those verified facts mean within their chains.**

**Roberta determines what the specialist findings mean in the larger user/cross-chain context.**

```text
Memory remembers what matters.
CMIS verifies what is happening now.
```

The system becomes more capable by proving more—not by guessing more.
