# Solana Market Freshness Evidence

Status: bounded evidence contract implemented for issue #308.

Observed/reviewed: 2026-08-28.

## Purpose

CMIS must distinguish:

- CMIS collection time;
- provider market-fact time;
- Solana block/slot identity;
- provider transport latency;
- underlying market-fact freshness.

None of those concepts is interchangeable by implication.

## Jupiter Price V3

Provider-owned documentation reviewed:

- https://developers.jup.ag/docs/guides/how-to-get-token-price
- https://developers.jup.ag/docs/price
- https://developers.jup.ag/blog/how-jupiter-prices-a-token

Accepted semantics:

- Price V3 createdAt is token creation metadata. It is not a price observation
  timestamp and must never be used as freshness evidence.
- Price V3 blockId is documented as the Solana block when the price was
  computed and as a field that can be used to verify price recency.
- Jupiter describes Price V3 as a last-trade/reference price rather than an
  execution quote.

CMIS therefore accepts blockId as a provider-owned block-reference semantic
for bounded freshness evidence. It does not by itself establish a wall-clock
time or a freshness PASS.

## Canonical Solana RPC mapping

Canonical Solana RPC documentation reviewed:

- https://solana.com/docs/rpc/http/getblocktime

getBlockTime accepts a block number identified by slot and returns the
estimated block production time as Unix seconds when available.

CMIS may therefore map an exact Jupiter blockId to getBlockTime and preserve:

- exact block/slot identity;
- estimated Unix production time;
- whether the RPC returned a usable time.

getBlockTime does not itself prove a separate finality class for the referenced
slot. CMIS therefore keeps finality_verified=false. A separate getSlot
observation may preserve the provider's explicit reference commitment and
whether the Jupiter block is at or before that observed reference slot, but it
does not silently upgrade finality.

## DEX Screener token-pairs v1

Provider-owned documentation reviewed:

- https://docs.dexscreener.com/api/reference

The accepted token-pairs schema exposes pairCreatedAt but no documented
price/liquidity/volume market-update or observation timestamp.

CMIS therefore keeps:

    pair_created_at_used_for_freshness = false
    market_fact_timestamp_semantics_verified = false
    provider_fact_time_verified = false

Collection time is preserved separately and is not substituted for provider
market-fact time.

## Policy boundary

Issue #311 / the Solana Jupiter current-price freshness governance now selects
explicit CMIS operator thresholds:

    max_age_seconds = 60
    max_future_skew_seconds = 5
    freshness_policy_complete = true

These are CMIS governance bounds, not Jupiter or Solana SLAs and not values
derived from observed live ages.

CMIS may therefore produce a deterministic Jupiter source-specific freshness
classification. A computed fact age becomes policy-qualified evidence, but
shared Solana market freshness remains separately gated:

    dexscreener_freshness_verified = false
    cross_source_time_identity_verified = false
    freshness_verified = false
    current_price_promotable = false

See `SOLANA_JUPITER_CURRENT_PRICE_FRESHNESS_GOVERNANCE.md`.

## Cross-source boundary

Even when:

- Jupiter block time is resolved; and
- Jupiter and DEX Screener prices numerically agree;

DEX Screener still lacks a verified market-fact timestamp under the accepted
schema. Therefore:

    cross_source_time_identity_verified = false
    price_freshness_verified = false

Numerical agreement does not create time identity, source independence, public
service authority, Scout reliance, risk authority, or execution authority.
