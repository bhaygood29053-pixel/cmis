# Solana Jupiter Current-Price Freshness Governance

Status: accepted CMIS source-specific freshness policy for Issue #311.

Policy id:

```text
cmis.solana.jupiter.current_price_freshness.v1
```

## Accepted policy

```text
max_age_seconds = 60
max_future_skew_seconds = 5
```

Machine-readable policy:
`liquidity_scout/providers/solana/jupiter_freshness_policy.json`

Runtime normalization/classification:
`liquidity_scout/providers/solana/jupiter_freshness_policy.py`

## What the provider evidence establishes

Jupiter Price V3 documents `blockId` as the Solana block reference for the
computed price and states that it can be compared with the current block to
judge recency.

Provider evidence reviewed:

- https://developers.jup.ag/docs/guides/how-to-get-token-price
- https://developers.jup.ag/blog/how-jupiter-prices-a-token

Canonical Solana RPC `getBlockTime` maps an exact slot to estimated block
production time as a Unix timestamp:

- https://solana.com/docs/rpc/http/getblocktime

These sources establish the fact-time mechanism. They do **not** publish a
Jupiter stale-after-N-seconds service guarantee.

## Governance rationale

### max_age_seconds = 60

This is a CMIS current-price evidence contract, not a Jupiter or Solana SLA.

A Jupiter price whose verified block-time fact is more than one minute older
than the post-read CMIS collection clock is not considered current by this
source-specific policy.

The one-minute horizon is selected independently of observed Jupiter ages and
matches the already accepted CMIS current-price horizon for X1 Oracle V2. That
cross-chain consistency is intentional: "current" has the same operator meaning
for these two bounded market-evidence contracts unless a source-specific reason
requires otherwise.

The value is not derived from Solana slot duration, transaction blockhash
expiration, observed price ages, or a passing live sample.

### max_future_skew_seconds = 5

This is the CMIS clock-reference contract.

A verified provider fact time may be at most five seconds ahead of the
post-read CMIS collection clock. Larger positive offsets fail closed as FUTURE.

This is an operator clock-skew tolerance, not a Jupiter or Solana SLA and not a
claim about Solana slot duration. The value matches the accepted CMIS
cross-chain clock-reference bound used for X1 Oracle V2.

## Deterministic classifications

```text
FRESH
STALE
FUTURE
INVALID
UNAVAILABLE
POLICY_UNVERIFIED
```

Rules:

- FRESH: effective age <= 60 seconds and positive future skew <= 5 seconds.
- STALE: effective age > 60 seconds.
- FUTURE: provider fact time is > 5 seconds ahead of CMIS reference time.
- INVALID: malformed or internally inconsistent verified evidence.
- UNAVAILABLE: exact Jupiter provider fact time cannot be verified.
- POLICY_UNVERIFIED: required numerical policy/provenance is incomplete.

Boundary semantics are inclusive:

- age exactly 60.000 seconds => FRESH;
- age greater than 60.000 seconds => STALE;
- future offset exactly 5.000 seconds => FRESH;
- future offset greater than 5.000 seconds => FUTURE.

## Verification semantics

`jupiter_freshness_verified=true` means CMIS successfully applied the
accepted policy to verified Jupiter fact-time evidence and produced a
deterministic FRESH/STALE/FUTURE classification.

It does **not** mean the price is fresh. Freshness status is represented by the
classification and `jupiter_current_price_eligible`.

For example:

```text
classification = STALE
jupiter_freshness_verified = true
jupiter_current_price_eligible = false
```

is valid and expected.

## Cross-source boundary

Even if Jupiter is FRESH:

```text
dexscreener_freshness_verified = false
cross_source_time_identity_verified = false
freshness_verified = false
current_price_promotable = false
source_independence_verified = false
execution_authorized = false
```

The accepted DEX Screener token-pairs schema still provides no verified
price/liquidity/volume market-update timestamp. Jupiter source-specific
freshness therefore cannot become shared cross-source current-price authority.

## Next gate

Identify and verify a secondary Solana price source with:

- exact mint/subject identity;
- exact price unit semantics;
- provider-owned timestamp/block/slot semantics;
- deterministic fact-time mapping;
- compatible current-price freshness policy;
- independent source/provenance analysis.

Only a separate accepted gate may consider Solana current-price promotion.
