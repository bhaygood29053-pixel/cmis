# Solana Jupiter-Pyth Cross-Source Time-Identity Governance

Status: accepted CMIS comparison policy for issue #315.

Observed/reviewed: 2026-08-28.

## Purpose

CMIS now has two timestamped Solana price-evidence paths for the exact accepted
USDC fixture:

```text
Jupiter Price V3
  -> blockId
  -> canonical Solana getBlockTime
  -> provider fact time
  -> source-specific FRESH / STALE / FUTURE

Pyth Core USDC/USD
  -> exact sponsored PriceUpdateV2 account
  -> publish_time
  -> source-specific FRESH / STALE / FUTURE
```

Issue #315 defines when those two independently source-fresh observations are
close enough in provider fact time to qualify as a **same-time comparison
candidate**.

It does not promote a CMIS current price.

## Accepted policy

```text
policy_id = cmis.solana.jupiter_pyth.same_time.v1
max_fact_time_delta_seconds = 5
```

Machine-readable policy:

`liquidity_scout/providers/solana/jupiter_pyth_time_identity_policy.json`

Runtime classifier:

`liquidity_scout/providers/solana/jupiter_pyth_time_identity.py`

There is no hidden fallback/default.

## Provider evidence

### Jupiter

Current Jupiter Price V3 documentation states:

- `blockId` is the Solana block when the price was computed;
- `blockId` can be used to verify price recency;
- Price V3 is derived from the last qualifying swap price;
- for popular tokens, qualifying price updates occur every few seconds;
- the Price API is a lagging/reference price, not an execution quote.

References:

- https://developers.jup.ag/docs/guides/how-to-get-token-price
- https://developers.jup.ag/docs/price
- https://developers.jup.ag/blog/how-jupiter-prices-a-token

### Pyth

Pyth documents the sponsored Solana USDC/USD push feed with:

```text
heartbeat = 1 minute
price deviation trigger = 0.5%
```

Push feeds may also experience update delays, so the heartbeat is not a
synchronization or freshness SLA.

References:

- https://docs.pyth.network/price-feeds/core/push-feeds/solana
- https://docs.pyth.network/price-feeds/core/push-feeds

### Solana time mapping

Solana `getBlockTime` returns the **estimated** production time of a slot as a
Unix timestamp. Pyth `publish_time` is also represented in Unix seconds.

Reference:

- https://solana.com/docs/rpc/http/getblocktime
- Pyth source contract recorded in
  `SOLANA_PYTH_SECONDARY_PRICE_EVIDENCE.md`

## Why five seconds

Five seconds is a **CMIS operator comparison window**, not a Jupiter, Pyth, or
Solana guarantee.

The policy is intentionally distinct from the 60-second source-freshness
horizon.

### Why not 60 seconds

A 60-second cross-source delta would collapse two different questions:

1. is each source observation still current enough for its own source policy?
2. do the two observations describe nearly the same market moment?

Pyth USDC/USD can legitimately remain source-fresh while waiting for its
one-minute heartbeat. Such an observation should not automatically be treated
as simultaneous with a Jupiter last-swap observation near the end of that
minute.

### Why not zero seconds

The accepted fact times are whole-second observations, and Jupiter's block time
is an estimated production timestamp. Requiring exact second equality would
turn timestamp quantization into an artificial mismatch rule.

### Why five seconds

For the exact current tracer-bullet scope:

- Jupiter describes popular-token qualifying prices as updating every few
  seconds;
- both fact times are Unix-second observations;
- five seconds permits a small near-synchronous comparison window;
- five seconds remains much tighter than the 60-second current-price horizon;
- Pyth heartbeat-only observations that are materially older fail closed as
  `TIME_MISMATCH`;
- the value was selected from the semantic contract before any live
  Jupiter/Pyth passing sample was used.

The number is therefore a governance definition of **same-time**, not an
empirical claim that providers always update within five seconds.

## Eligibility prerequisites

CMIS evaluates the delta only after all of the following pass:

- exact Solana chain identity;
- exact same mint;
- exact same price subject;
- compatible USD-per-token unit semantics;
- verified Jupiter provider fact time;
- verified Pyth `publish_time`;
- Jupiter source-specific classification = `FRESH`;
- `jupiter_current_price_eligible=true`;
- Pyth source-specific classification = `FRESH`;
- `pyth_current_price_eligible=true`;
- existing Jupiter/Pyth identity and price-semantics gates pass.

A source that is merely `STALE`, `FUTURE`, unavailable, malformed, or
policy-unverified is never upgraded into same-time evidence.

## Deterministic classifications

```text
SAME_TIME
TIME_MISMATCH
SOURCE_STALE
SOURCE_FUTURE
INVALID
UNAVAILABLE
POLICY_UNVERIFIED
```

Boundary semantics are inclusive:

```text
fact-time delta == 5.000 seconds  -> SAME_TIME
fact-time delta >  5.000 seconds  -> TIME_MISMATCH
```

The classifier independently recomputes:

```text
abs(jupiter_fact_time_unix - pyth_fact_time_unix)
```

and rejects a crosscheck record if its reported delta does not match the exact
fact times.

## Numerical agreement is separate

Time identity and price agreement answer different questions.

The following is valid:

```text
classification = SAME_TIME
cross_source_time_identity_verified = true
numerical_price_agreement = false
```

Likewise, numerical agreement with `TIME_MISMATCH` does not create same-time
evidence.

## Authority boundary

Even when both source-specific freshness gates are FRESH, prices agree within
the configured numerical tolerance, and the time classification is SAME_TIME:

```text
cross_source_time_identity_verified = true
same_time_candidate = true

source_independence_verified = false
price_construction_equivalence_verified = false
current_price_promotable = false
execution_authorized = false
```

Jupiter and Pyth use different price-construction systems. A separate gate must
investigate provider/source independence and methodology compatibility before
CMIS may consider any current-price promotion.

## DEX Screener boundary

DEX Screener still has no accepted market-fact update timestamp under the
current token-pairs schema.

Nothing in this policy changes:

```text
dexscreener_freshness_verified = false
```

## Live evidence boundary

The mandatory Solana live gate already verifies the real sponsored Pyth USDC/USD
account and its timestamp semantics through canonical Solana RPC.

PR CI does not require a live Jupiter API credential and therefore does not
manufacture a passing live Jupiter/Pyth SAME_TIME sample.

The five-second policy is tested deterministically at exact boundaries. A future
live Jupiter/Pyth evidence probe may observe SAME_TIME or TIME_MISMATCH without
changing the accepted policy.

## Safety

No:

- source-independence promotion;
- generic Pyth feed expansion;
- DEX Screener timestamp inference;
- current-price promotion;
- Scout/public-service/risk authority;
- transaction construction;
- signing;
- broadcast;
- custody;
- trading;
- execution.
