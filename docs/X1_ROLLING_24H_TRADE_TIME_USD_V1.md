# X1 Rolling 24h Trade-Time USD Evidence v1

Issue: #504

## Purpose

Finish the nonzero USD-volume leg of `x1_rolling_24h_market_activity/v1`
without using a current X1.Ninja price, the provider's USD volume as its own
proof, or a token-name assumption that USDC/USDC.X equals exactly one dollar.

## Accepted valuation chain

For each exact-pool swap classified by the #502/#503 chain reconstruction:

1. The swap signature, slot, block time, exact quote mint, and exact quote
   amount come from X1 RPC and exact pool-vault deltas.
2. For wrapped-XNT quote volume, CMIS reconstructs the XNT/USDC.X reserve ratio
   at that transaction slot from the accepted XNT/USDC.X reference pool
   `CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR`.
3. Each reference vault is independently anchored by its latest successful
   vault-account transaction at or before the swap slot. The anchor
   transaction's exact post-token balance is used. A complete bounded X1 RPC
   address-history scan is required.
4. Historical USDC.X equivalence is reconstructed from exact current Warp USDC
   source reserve and X1 USDC.X supply observations. A separate
   `warp_message_interval_retention/v1` proof covers only the interval from the
   oldest exact swap fact in this market window through the current backing
   observation. Every retained, paired, settled USDC-route bridge action inside
   that interval is reversed on the chain where that action actually occurred.
5. An unresolved destination-side Warp record may be bounded only when its
   source-side action is independently fixed by the exact route mint, expected
   native/non-native operation topology, and verified outgoing-account creation
   coverage. For a post-fact X1 -> Solana USDC.X outflow, CMIS adds the verified
   X1 burn amount back to current USDC.X supply but does **not** assume the
   missing Solana release occurred. Current Solana reserve therefore remains a
   conservative lower bound and reconstructed historical USDC.X supply is a
   conservative upper bound.
6. The conservative reconstructed historical Solana USDC reserve must cover the
   conservative reconstructed historical X1 USDC.X supply at equal six-decimal
   units.
7. Canonical USDC/USD is observed from Kraken's public `USDC/USD` PostTrade
   feed. The accepted policy is the last exact-pair trade at or before the swap
   fact time with maximum age 120 seconds.
8. Decimal arithmetic composes:
   `XNT amount × (USDC.X / XNT) × (USD / USDC)`.
9. The resulting exact-swap values are summed and compared with the provider
   rolling 24h USD volume under the already accepted tolerance policy.
## Provider surface-divergence evidence

Two exact live #504 workflow captures now preserve the same two exact X1
swap signatures while X1.Ninja's trade-history USD fields changed materially
and the pool-level `volume24h` aggregate did not.

The retained classifier is
`x1_ninja_rolling_volume_snapshot_semantics/v1`.

It may establish only these bounded observations:

- the exact trade identity set is unchanged across the two captures;
- within each capture, the returned trade rows share one common implied
  XNT/USD conversion basis;
- that common trade-row USD conversion basis changed between captures;
- the sum of the returned trade-row `amountUsd` values therefore changed;
- the pool-level `volume24h` value remained unchanged.

This proves that the current trade-history USD display and the stored rolling
pool aggregate are not the same mutable value surface. It does **not** prove
the provider's internal aggregation query, stored database columns, event-time
valuation formula, or provider fact-time semantics.

The provider release notes independently describe pool volume/transaction stats
as aggregate queries over the 24h trade database and separately document
historical trade repricing. Those statements are corroborating provider
documentation only; they are not a substitute for the exact X1/RPC evidence
required by CMIS.

Accordingly:

- current trade-row `amountUsd` must never be summed and treated as proof of
  the current `volume24h` field;
- current catalog `xntPriceUsd` must never be substituted into historical
  swaps to force agreement;
- the rolling USD field remains fail-closed until its own stored-aggregate
  valuation basis can be independently reproduced.

## Fail-closed rules

The nonzero USD field stays unverified if any swap lacks any required leg,
including:

- incomplete X1 RPC vault history;
- a missing or ambiguous vault anchor;
- exact-mint or unit/direction mismatch;
- an unresolved Warp USDC route event whose source-side effect cannot be
  conservatively and independently bounded;
- incomplete bounded Warp interval-retention coverage;
- reconstructed USDC reserve below reconstructed USDC.X supply;
- no Kraken USDC/USD trade within the 120-second last-observation policy;
- current-price substitution;
- provider USD-price reuse;
- stable-name-equals-$1 assumption.

Transaction-count freshness remains independently eligible when its #502/#503
chain proof succeeds.

## Explicit boundaries

- Provider collection time is not provider fact time.
- `warp_message_interval_retention/v1` cannot satisfy or replace #441's
  accepted 60-day Bridge Flow retention gate; that minimum remains unchanged.
- Source independence remains separately unverified.
- This work does not promote the public CMIS service or authorize Scout reliance.
- Read-only evidence only.
- No transaction construction, signing, broadcast, custody, mint, burn, swap,
  or value movement is authorized.
