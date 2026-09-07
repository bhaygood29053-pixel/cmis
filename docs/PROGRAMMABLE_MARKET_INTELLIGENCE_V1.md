# Programmable Market Intelligence v1

Status: **implementation foundation / pending acceptance**

Tracking issue: #552

## Purpose

This workstream adds deterministic CMIS primitives for programmable-market
mechanics discovered through current Robinhood Chain / Uniswap v4 research.
The discovery material is a lead source only. It is not promoted to verified
market truth.

The foundation contains:

1. `uniswap_v4_hook_intelligence/v1`
2. `reflection_flow_intelligence/v1`
3. `yield_provenance/v1`
4. `cross_chain_asset_provenance_robinhood_x1/v1`, an additive companion to
   the accepted `cross_chain_asset_provenance/v1` primitive.

All four remain read-only, internal, non-promoted, and
`execution_authorized=false`.

## 1. Uniswap v4 hook intelligence

`uniswap_v4_hook_intelligence/v1` validates an exact supplied EVM PoolKey
scope and deterministically decodes the fourteen Uniswap v4 hook permission
bits embedded in the low bits of the exact hook address.

The contract can establish facts such as:

- exact pool id;
- exact PoolManager;
- exact currencies;
- fee and tick spacing;
- exact hook address;
- hook-present vs zero-hook;
- permission mask;
- active permission-bit names;
- supplied code hash and evidence lineage.

### Critical boundary

Permission bits prove only what callbacks the address is shaped to request.
They do **not** prove:

- deployed bytecode;
- source-code equivalence;
- reflection behavior;
- tax rate;
- destination of value;
- current liquidity;
- economic safety;
- risk.

A `0x0088` mask can therefore be described as
`before_swap + before_swap_returns_delta`, but CMIS cannot call it a
reflection hook until separate flow/code evidence supports that claim.

## 2. Reflection-flow intelligence

`reflection_flow_intelligence/v1` consumes one accepted hook-intelligence
object plus exact verified transfer/attribution observations for the same pool
and hook.

The contract:

- rejects pool/hook/asset mismatches;
- rejects duplicate transaction ids;
- rejects unverified transfers;
- rejects unverified hook attribution;
- enforces an exact observation window;
- aggregates reflection amount only in one exact asset unit;
- keeps holder-distribution semantics separate from mere transfer presence.

It does not infer reflection from hook permissions, token marketing, names, or
the existence of transfers.

The aggregate is bounded to the supplied observation set. It is not a lifetime
total and does not claim complete window coverage unless a later provider gate
proves that separately.

## 3. Yield provenance

`yield_provenance/v1` separates:

- organic pool-fee return; and
- externally subsidized incentive return.

The contract requires a verified liquidity-value basis and verified base-fee
value. Incentive value is optional, but missing incentive evidence stays
`unavailable`; it is never zero-filled.

When incentive evidence is present, CMIS exposes three separate views:

- organic fee return;
- subsidized incentive return;
- combined trailing-window return.

Annualization is simple trailing-window extrapolation. It is not a forecast,
promise, sustainability conclusion, or guaranteed APY.

A website-reported APY may be preserved separately as a reported observation,
but it is never treated as CMIS's verified calculation.

## 4. Robinhood → X1 provenance extension

`cross_chain_asset_provenance_robinhood_x1/v1` composes the already-accepted
`cross_chain_asset_provenance/v1` builder.

It intentionally does **not** modify the accepted v1 output or its public
promotion semantics.

The extension requires:

- a Robinhood-origin chain-scoped exact asset identity;
- a current X1 exact asset identity;
- continuous cross-chain hop structure;
- a descriptive source-asset class.

It may retain descriptive custody dependency and route-evidence selectors, but
those do not prove:

- a live Robinhood → X1 route;
- Warp availability;
- bridge backing;
- custody safety;
- tokenized-equity entitlement/ownership;
- redemption;
- solvency;
- risk.

Any future live promotion must resolve accepted CMIS-owned provider evidence
rather than accepting these descriptive fields as truth.

## Discovery-to-verification architecture

```text
CMIS Web Discovery
  -> candidate pool / hook / route / incentive
  -> chain/provider evidence capture
  -> deterministic CMIS validation
  -> accepted evidence object
  -> Chain Scout
  -> ROBERTA
```

Discovery is subordinate to verification at every step.

## Initial 69ELEVEN proof case

The research that motivated #552 can be used as a future bounded proof case for:

- exact Robinhood Chain token contract identity;
- exact Uniswap v4 PoolKey reconstruction;
- zero-hook vs nonzero-hook pool separation;
- `0x0088` permission-mask decoding;
- deployed-code corroboration;
- exact reflection transfer attribution;
- base-fee vs booster-reward separation;
- candidate Robinhood → X1 provenance.

Those facts must be re-collected from authoritative/current evidence before
CMIS may report them as current.

## Promotion state

This issue does **not** change the public CMIS capability manifest.

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
automatic_risk_conclusion_authorized = false
trade_recommendation_authorized = false
execution_authorized = false
```

A separate issue/PR is required for provider adapters, live evidence capture,
freshness, protected-core storage/resolution, public service promotion, and
Scout reliance.
