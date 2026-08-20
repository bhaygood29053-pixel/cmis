# CMIS Product & Premium Service Roadmap

Last reconciled: 2026-08-20

## Canonical architecture

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

The repository originally began as Liquidity Scout. The `liquidity_scout` Python namespace remains a compatibility implementation detail during incremental migration; it is not a separate current authority layer.

Roberta owns orchestration and final synthesis. Chain Scouts plan and interpret chain-specific work without manufacturing facts. CMIS owns deterministic verified facts, evidence, risk, capability eligibility, historical intelligence, and bounded analysis-only pre-trade calculations. Providers remain beneath CMIS.

Fresh accepted CMIS/provider facts override remembered live values. Missing evidence remains unknown/unavailable, never zero-filled. Risk remains separate from Proof Score.

## Roadmap status

Accepted milestones:

- **CMIS Phase 10 — Solana read-only provider foundation: COMPLETE.**
- **Evidence Receipts + Proof Score: COMPLETE.**
- **X1 evidence gaps: explicitly classified/fail-closed.**
- **Deterministic pre-trade trade-size analysis: COMPLETE.**
- **CMIS Phase 11 — read-only Verified Intelligence foundation: COMPLETE.**
- **CMIS Phase 12 — first narrow public-service / Scout-reliance promotion: COMPLETE for X1 `concentration_change_intelligence/v1`.**
- **CMIS capability contract: 1.9.0.**
- **Roberta adoption/readiness of that exact X1 service: COMPLETE.**
- **Controlled transaction execution: unauthorized / not an active CMIS milestone.**

CMIS and Roberta phase numbering are separate. CMIS Phase 12 does not mean Roberta Controlled Execution has started.

## Phase 11 foundation

The core Phase 11 `intelligence_foundation` remains read-only and non-promoted as a group:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
```

Accepted foundation primitives include top-account concentration observations/compatible numeric changes, neutral wallet-activity facts, sanitized sparse history/comparison, and evidence-bound conclusions.

These primitives do not automatically become public Scout services and do not authorize behavioral/ownership labels.

## Phase 12 first promoted intelligence service

CMIS `1.9.0` separately promotes exactly one narrow X1 wrapper:

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

The wrapper resolves canonical CMIS-owned intelligence evidence internally and revalidates deterministic evidence before returning facts/proof. Caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, provider assertions, behavioral labels, or replacement verification state are rejected as trust shortcuts.

The service does not establish unique-holder totals or beneficial owners. Token-account concentration remains token-account concentration. Optional threshold output is deterministic policy evaluation, not risk. Proof Score is not risk.

## Verified-data foundation

### X1 / XDEX

X1 is the mature CMIS surface. Accepted capabilities include, where exact evidence contracts permit, asset/pool identity, market reporting/ranking, tokenomics/authority evidence, transaction/trade verification tooling, persisted verification evidence, deterministic risk, historical comparison, bounded activity, trade-size analysis, and selected exact-route price-impact/fee facts.

Program-, pool-, route-, provider-, token-account-, or sample-scoped evidence remains distinct from asset-wide/global truth.

Current provider gaps remain fail-closed. Recent bounded observations show X1.Ninja SSE access denied for the current tested credential and disagreement among holder-looking provider/RPC/account-authority counts. Those observations do not establish stream semantics, holder totals, wallet identity, beneficial ownership, or provider completeness.

Warp Bridge machine-readable operational state remains unavailable until an exact provenance-approved read contract is accepted.

### Solana

Solana Phase 10 remains a bounded read-only provider/runtime foundation beneath the same CMIS architecture. Exact-mint identity, SPL Token / Token-2022 handling, canonical supply/authority evidence, configured Jupiter/Helius/DEX Screener evidence, cross-source checks, provenance-safe history, and bounded/partial market/tokenomics/risk/history services remain capability-specific.

Solana does not inherit X1 capabilities and is not assumed to have X1 parity.

## Evidence quality

Evidence Receipts preserve provenance, verification state, scope, freshness, disagreements, limitations, unresolved fields, and content-addressed identity.

Proof Score remains separate from risk. Missing evidence remains unknown rather than fabricated false/zero.

No CMIS phase currently promotes whale, insider, bot, accumulator, distributor, market-maker, common-owner, manipulation, relationship, fraud, or behavioral-intent claims without a separately accepted deterministic classification contract.

## Pre-trade analysis

`pre_trade_check` remains analysis only.

Accepted behavior may include requested notional, verified liquidity context, notional-to-liquidity ratio, explicit versioned trade-size policy, freshness handling, and selected route-scoped facts only where exact identity/source/freshness/semantic/unit/proof requirements pass.

Quote tolerance is not expected execution slippage. Missing route quality, bridge dependency, fill quality, transaction simulation, generic execution quality, or other advanced evidence remains unavailable.

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Product direction

### Verified Data

Continue deepening field-level X1 and Solana verification without weakening truth standards.

### Verified Intelligence

Phase 11 foundation complete; first Phase 12 narrow X1 public-service promotion complete. Future interpretation layers require separate deterministic contracts before broader Scout use.

### Early Warning

Future alerts require explicit scope, freshness, threshold, persistence, and evidence semantics and may not imply ownership, intent, manipulation, or fraud beyond accepted contracts.

### Cross-Chain Intelligence

- X1: mature active foundation;
- Solana: Phase 10 read-only foundation complete and maturing field-by-field;
- Ethereum: future explicit provider/verification milestone only;
- bridge/stablecoin/capital-flow evidence: future, only after exact source semantics are accepted.

## Recommended implementation sequence

Completed:

1. deterministic pre-trade trade-size policy;
2. Phase 11 concentration/wallet/history/evidence foundation;
3. bounded XDEX quote/history semantic work;
4. pinned historical executed-fee reconstruction;
5. route-scoped pre-trade evidence seam;
6. explicit concentration-threshold evaluator;
7. **Phase 12** first public-service / Scout-reliance contract for X1 `concentration_change_intelligence/v1`, with Roberta adoption/readiness complete.

Next read-only candidates:

8. deterministic inference/classification contracts before behavioral/ownership labels;
9. wallet relationship evidence with explicit non-ownership semantics;
10. evidence-backed alert contracts;
11. deeper XDEX route/execution evidence without transaction preparation as a proof shortcut;
12. field-by-field Solana maturity;
13. Ethereum only under an explicit capability/acceptance plan;
14. investigation/evidence export and premium access after deterministic services stabilize.

Parallel provider-gap work remains read-only and fail-closed: Warp Bridge source discovery, historical redundancy/source-independence, holder-semantics evidence, and alternate-provider verification.

None of these items authorizes execution.

## Governance

1. Facts before interpretation.
2. Providers are candidates until accepted verification exists.
3. Unknown remains unknown.
4. Inference is separately labeled/contracted.
5. Evidence remains reproducible.
6. Freshness is explicit.
7. Cross-chain normalization preserves chain provenance.
8. Risk and proof are separate.
9. Route/pool/provider scope is not asset-wide scope.
10. No autonomous execution by implication.
11. Premium access never changes the definition of truth.

## Relationship to Roberta

```text
CMIS verifies what the evidence supports.
Chain Scouts investigate and interpret within their chain.
Roberta coordinates and explains.
```

Roberta may synthesize accepted results but must not recalculate CMIS truth/proof, silently upgrade inference to fact, or collapse risk and evidence quality into one score.
