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
5. The reconstructed historical Solana USDC reserve must cover the reconstructed
   historical X1 USDC.X supply at equal six-decimal units.
6. Canonical USDC/USD is observed from Kraken's public `USDC/USD` PostTrade
   feed. The accepted policy is the last exact-pair trade at or before the swap
   fact time with maximum age 120 seconds.
7. Decimal arithmetic composes:
   `XNT amount × (USDC.X / XNT) × (USD / USDC)`.
8. The resulting exact-swap values are summed and compared with the provider
   rolling 24h USD volume under the already accepted tolerance policy.

## Fail-closed rules

The nonzero USD field stays unverified if any swap lacks any required leg,
including:

- incomplete X1 RPC vault history;
- a missing or ambiguous vault anchor;
- exact-mint or unit/direction mismatch;
- unresolved Warp USDC route events;
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
