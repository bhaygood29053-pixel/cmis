# CMIS 1.8.x X1 Provider Proof Map

## Purpose

CMIS contract `1.8.0` already exists. This document defines the X1 provider/evidence hardening strategy for the `1.8.x` line without changing the existing truth standard.

The goal is not to find one provider that answers every question. The goal is to assign specialist sources to narrow evidence roles, verify each exact source contract before promotion, and keep unsupported facts explicitly unavailable or unknown.

Core rule:

> Different provider names are not proof of source independence.

CMIS may record same-fact agreement before source independence is established. Positive independence credit requires explicit accepted evidence that the compared observations are produced by sufficiently distinct upstream collection paths for the exact fact under review.

## Architecture boundary

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider boundary
        -> specialist source
```

Roberta and X1 Scout do not call specialist providers directly. Provider-specific transport, parsing, provenance, and evidence contracts remain beneath CMIS.

## X1 provider roles

| Source | Candidate CMIS role | Current status | What it may help prove | What is not assumed |
| --- | --- | --- | --- | --- |
| Official X1 RPC (`https://rpc.mainnet.x1.xyz`) | canonical direct-chain verifier | ACTIVE / bounded by accepted RPC contracts | transaction existence/success, slot/time metadata where available, program/account state, token-account state, exact on-chain observations | independence from another provider merely because the interface differs |
| Official X1 Explorer (`https://explorer.mainnet.x1.xyz/`) | manual/discovery corroboration for direct-chain facts | CANDIDATE for machine use | transaction/account/program lookup and operator-visible reproduction | stable machine-readable API, complete indexing, independent upstream |
| FortiBlox (`https://explorer.fortiblox.com/`) | general secondary explorer/indexer candidate | CANDIDATE | transactions, accounts, programs/tokens/NFT discovery, indexed cross-checks if exact API contracts are verified | current API paths, completeness, retention, freshness, finality equivalence, source independence |
| X1 Validator HQ (`https://x1valhq.xyz/`) | validator/staking specialist candidate | CANDIDATE | validator/staking observations after exact machine contract and semantics are verified | chain-wide market facts, source independence, unverified ranking semantics |
| X1 Prism (`https://x1prism.com/`) | network/bridge analytics specialist candidate | CANDIDATE | rankings/maps/bridge-flow observations after exact backend, metric semantics, freshness, and provenance are verified | official bridge status, route usability, capacity, fee semantics, source independence |
| X1SCR (`https://x1scr.xyz/`) | token analytics specialist candidate | CANDIDATE | token charts, early-buyer observations, holder/token-account distribution, LP observations after exact contracts are verified | beneficial-owner identity, wallet-holder equivalence, complete holder coverage, independent upstream |
| X1 Space (`https://x1space.xyz/`) | wallet/alert specialist candidate | CANDIDATE | wallet monitoring and alert-oriented observations after exact source/API contracts are verified | whale/insider/intent labels, complete wallet history, source independence |
| X1 Ninja (`https://x1.ninja/`) | market/trade specialist | ACTIVE / bounded field-by-field | pools, trades, OHLCV, wallet/trade utilities and other fields only where existing CMIS evidence contracts explicitly accept them | provider claims as verified chain facts, complete history, source independence, universal amount/price/timestamp semantics |

`ACTIVE` does not mean every field from a provider is verified. Promotion is field-, scope-, and evidence-contract-specific.

## Proof routing by fact type

### 1. Transaction / account / program proof

Preferred evidence path:

```text
provider observation
  -> exact transaction/account/program identity
  -> official X1 RPC direct-chain verification
  -> optional independently verified secondary indexer corroboration
```

Primary candidates:

- Official X1 RPC: direct-chain verification.
- FortiBlox: secondary indexed corroboration candidate.
- Official X1 Explorer: manual reproduction/discovery support unless a stable machine contract is separately accepted.

A second explorer view is not independent proof until its upstream collection lineage is verified.

### 2. Market / pool / trade proof

Preferred evidence path:

```text
X1 Ninja / XDEX observation
  -> exact asset + pool + transaction identity
  -> official X1 RPC pool/program/vault verification
  -> exact transaction-to-pool membership proof where applicable
  -> optional accepted secondary indexer corroboration
```

CMIS must preserve the difference between:

- provider-reported market facts;
- direct on-chain observations;
- same-fact agreement;
- source independence;
- asset-wide versus individual-pool scope.

Public pool count remains `#LPs`.

### 3. Holder / concentration proof

Preferred evidence path:

```text
X1SCR candidate observation
  -> official X1 RPC token-account evidence
  -> optional FortiBlox indexed cross-check
```

Required semantic boundary:

- token accounts are not automatically unique wallets;
- unique wallets are not automatically beneficial owners;
- top token-account concentration is not automatically holder concentration;
- missing holder coverage is not zero concentration.

Until exact X1SCR contracts and semantics are verified, it remains a candidate source only.

### 4. Validator / staking proof

Preferred evidence path:

```text
X1 Validator HQ candidate observation
  -> official X1 RPC validator/stake evidence
  -> exact metric/ranking semantic verification
```

CMIS must not promote a displayed ranking until the ranking inputs, denominator/scope, freshness, and ordering semantics are accepted.

### 5. Bridge / network-flow proof

Preferred evidence path:

```text
X1 Prism candidate observation
  -> discover exact machine-readable backend
  -> identify upstream bridge/on-chain lineage
  -> verify metric semantics + freshness
  -> cross-check against official bridge/on-chain evidence where available
```

These remain separate facts:

```text
X1 network operational
!= bridge operational
!= asset bridgeable
!= capacity/route usable
!= XDEX liquidity available
!= quote/routing available
```

Prism UI values such as bridge inflow/outflow/net/TVL are not promoted until their machine source, upstream lineage, metric definitions, and freshness contract are verified.

### 6. Wallet / alert proof

Preferred evidence path:

```text
X1 Space or X1 Ninja candidate observation
  -> exact wallet + transaction identity
  -> official X1 RPC verification
  -> bounded history/coverage contract
```

CMIS may emit neutral verified activity facts. It must not infer whale, insider, bot, market-maker, accumulation, distribution, manipulation, ownership, or intent without a separately accepted deterministic classification contract.

## Source-independence contract

CMIS must evaluate these dimensions separately:

```json
{
  "same_fact_agreement_verified": true,
  "source_independence_verified": null,
  "independent_agreement_verified": false
}
```

The example above is valid when two sources agree but their upstream independence has not been proven.

Positive source-independence credit requires all of the following for the exact fact/scope:

1. explicit accepted independence evidence;
2. a reported observation and verifier observation with distinct source identities;
3. no evidence that one source merely republishes the other observation;
4. provenance sufficient to identify the upstream collection path relevant to the fact;
5. no unrelated third source may rescue a same-source reported/verifier pair.

Unknown independence remains `null`; explicit disproof remains `false`.

## Provider promotion gates

A specialist source may move from `CANDIDATE` toward bounded/active CMIS use only when the relevant evidence contract establishes, as applicable:

- exact endpoint/method contract;
- authentication contract without credential leakage;
- deterministic response parsing;
- stable identity fields;
- metric and unit semantics;
- pagination/range/order semantics where history is claimed;
- freshness and observation-time semantics;
- finality semantics where required;
- failure/empty/partial behavior;
- direct-chain cross-checks where possible;
- upstream provenance/source-independence status;
- deterministic tests;
- explicit scope limitations;
- no execution/value-moving behavior.

A provider does not need to be globally promoted. Individual fields may be accepted while other fields remain unavailable.

## CMIS 1.8.x accepted baseline and next handoff

### Accepted evidence-hardening baseline

The dependency-safe evidence/history stack is integrated into `main`:

`#231 -> #233 -> #235 -> #230 -> #228 -> #236`

This establishes the current 1.8.x baseline for:

- explicit tri-state source-independence evidence;
- Proof Score / Evidence Receipt preservation of that tri-state;
- historical comparison preservation of unknown versus explicitly failed independence;
- exact fail-closed transaction-to-pool membership proof;
- bounded X1.Ninja trade-history evidence;
- composition of sampled history rows with exact pool-membership evidence.

The integrated baseline does not promote unsupported provider facts. Source independence, pagination/range exhaustiveness, retention/finality, provider amount/price/timestamp semantics, beneficial ownership, and behavioral intent remain unavailable unless separately proven.

### Provider-gap work remains under #30

1. FortiBlox remains a secondary-indexer candidate until exact machine contract and provenance are verified.
2. X1SCR remains a bounded token/holder-distribution candidate; no wallet/beneficial-owner promotion by inference.
3. X1 Prism bridge metrics require backend/provenance discovery; UI values do not prove bridge operational state.
4. X1 Validator HQ requires exact validator metric/ranking semantics before promotion.
5. X1 Space remains a wallet/alert candidate only if a reproducible machine-readable source is accepted.
6. X1Scroll/archive RPC and X1 Ninja SSE/live-event access remain separate credential/access gaps where applicable.

External provider uncertainty does not block the `1.8.x` hardening line when CMIS represents it accurately as `partial`, `unavailable`, `ambiguous`, or unverified.

### Phase 12 read-only intelligence handoff

Issue #237 is the next explicit roadmap/contract gate: promote exactly one public read-only Verified Intelligence service for Chain Scout reliance without bypassing CMIS evidence, proof, freshness, provenance, scope, or unknown-state rules.

Draft PR #238 is an implementation candidate for that gate and must be reviewed against #237 before any public capability advertisement or Scout reliance is accepted. In particular:

- promotion must be explicit and versioned;
- X1-only scope must remain explicit unless another chain is separately accepted;
- nested Phase 11 evidence must not be silently reclassified or strengthened;
- Evidence Receipt IDs, Proof Score records, freshness, limitations, unresolved fields, and proof/risk separation must be preserved;
- facts, deterministic policy outputs, and unsupported interpretations must remain distinguishable;
- behavioral, ownership, relationship, and intent labels remain unavailable;
- capability-manifest exposure and Scout reliance must fail closed until accepted;
- no provider access may bypass CMIS.

The Phase 12 gate does not reopen Controlled Execution and does not authorize transaction preparation, simulation as an execution precursor, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement.

## Completion condition for provider/evidence hardening

The hardening milestone is satisfied when CMIS can reliably distinguish and preserve:

- verified direct-chain facts;
- provider-reported observations;
- same-fact agreement;
- proven source independence;
- unknown versus explicitly failed evidence;
- exact scope and freshness;
- unsupported provider capabilities.

It is not necessary to solve every external provider gap before closing the hardening milestone. It is necessary that no unresolved gap is silently converted into a verified fact.

## Safety

This proof map authorizes read-only evidence collection, verification, normalization, and deterministic analysis only.

It does not authorize transaction preparation, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement.
