# Solana Pyth Timestamped Secondary Price Evidence

Status: bounded implementation for issue #313.

Observed/reviewed: 2026-08-28.

## Purpose

CMIS needs a second Solana price source with provider-owned fact-time semantics
before it can consider a future same-time Jupiter cross-source current-price
gate.

This implementation adds Pyth Core as read-only **secondary evidence** only.

It does not authorize a current CMIS price.

## Current Pyth Core upgrade state

Provider-owned Pyth documentation states that the Pyth Core upgrade completed
on August 26, 2026.

The upgrade documentation also states:

- existing "current" Core contracts were upgraded in place and keep their
  addresses;
- the same Core feed IDs continue to apply;
- Pyth recommends new integrations use the alternate upgraded addresses;
- Core and Pyth Pro remain distinct products.

References:

- https://docs.pyth.network/price-feeds/core/upgrade/contracts
- https://docs.pyth.network/price-feeds/core/contract-addresses/solana

The initial CMIS tracer bullet deliberately reads the provider-listed **current
Core sponsored account path**, which remains valid after the in-place upgrade:

```text
receiver program = rec5EKMGg6MxZYaMdyBfgwp4d5rB9T1VQH5pJv5LtFJ
price-feed / push-oracle program = pythWSnswVUd12oZpeFP8e9CVaEqJg25g1Vtc2biRsT
```

Pyth also lists the alternate upgraded Core programs:

```text
upgraded receiver = rec2HHDDnjLfj4kE7VyEtFA1HPGQLK33259532cRyHp
upgraded price-feed program = pyt2F414BA6dPttK6RddPZUdHfapoBN24GL5wbrPCou
```

CMIS does not silently mix account/program generations. A future migration to
the alternate upgraded account path requires its own exact fixture/evidence
update.

## Exact initial fixture

The first and only repository-approved mapping is:

```text
Solana mint:
EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

CMIS canonical asset:
USDC

Pyth feed:
USDC/USD

Pyth feed id:
eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a

Pyth sponsored shard-0 current account:
Dpw1EAVrSB1ibxiDQyTAW6Zip3J4Btk2x4SgApQCeFbX
```

Provider source:

- https://docs.pyth.network/price-feeds/core/push-feeds/solana
- Pyth repository source commit
  `ea35ae4718ccfe7abb31a1817f92a9dd548af1f2`
- source data:
  `apps/developer-hub/content/docs/price-feeds/core/push-feeds/data/svm/solana-mainnet.json`

No symbol/name discovery exists. Every other mint is currently unavailable
unless a new exact provenance-bearing fixture is accepted.

## Read-only architecture

```text
Roberta
  -> Solana Scout
    -> CMIS
      -> Solana Provider
        -> canonical Solana RPC
          -> exact Pyth sponsored price-feed account
```

Hermes is not used.

This matters because Pyth documents that Hermes requires an API key after the
August 26, 2026 upgrade. CMIS therefore gains this secondary evidence without a
new credential dependency.

## Account ownership and layout

The Pyth push-oracle program derives a fixed price-feed account from shard ID
and price feed ID, then invokes the Pyth Solana Receiver to populate a
`PriceUpdateV2` account.

Current Pyth source establishes:

```text
PriceUpdateV2:
  Anchor discriminator
  write_authority
  verification_level
  PriceFeedMessage
  posted_slot
```

For push-feed accounts, the push-oracle program passes the price-feed PDA itself
as write authority. CMIS therefore verifies:

- exact account address;
- exact receiver-program owner;
- non-executable account;
- exact `PriceUpdateV2` discriminator;
- write authority equals the exact feed account;
- exact feed ID;
- full verification level for price-integrity eligibility.

Provider source:

- `target_chains/solana/programs/pyth-push-oracle/src/lib.rs`
- `target_chains/solana/pyth_solana_receiver_sdk/src/price_update.rs`
- `pythnet/pythnet_sdk/src/messages.rs`

at Pyth source commit
`ea35ae4718ccfe7abb31a1817f92a9dd548af1f2`.

## Price semantics

Pyth's current source defines the actual price as:

```text
(price ± conf) * 10^exponent
```

CMIS preserves:

- signed integer price;
- unsigned confidence;
- signed exponent;
- exact decimal price;
- exact decimal confidence;
- EMA values separately;
- posted Solana slot.

No floating-point conversion is required for price construction.

## Fact-time semantics

Pyth's `PriceFeedMessage` source explicitly defines `publish_time` as the
timestamp of the price update in **seconds**.

CMIS therefore accepts:

```text
publish_time_unix -> provider fact time
```

after exact account/feed/integrity verification.

CMIS does not substitute:

- RPC fetch time;
- posted slot;
- token metadata time;
- Pyth account creation time;

for provider price fact time.

## Source-specific freshness

A separate Pyth policy is recorded in:

`liquidity_scout/providers/solana/pyth_freshness_policy.json`

Accepted CMIS operator bounds:

```text
max_age_seconds = 60
max_future_skew_seconds = 5
```

The sponsored USDC/USD feed is documented with a one-minute heartbeat and 0.5%
price-deviation update parameter. That is source context, not a provider
freshness SLA.

The 60-second current-price horizon remains a CMIS operator definition selected
independently of observed live ages.

## Jupiter comparison

CMIS may compare:

```text
exact USDC mint
Jupiter USD price
Pyth USDC/USD price
configured numerical relative-difference tolerance
Jupiter provider fact time
Pyth publish_time
```

The comparison exposes the exact absolute fact-time delta.

However, #313 intentionally defines **no cross-source maximum fact-time delta**.

Therefore even numerical agreement with both sources individually FRESH remains:

```text
time_identity_policy_complete = false
time_identity_verified = false
source_independence_verified = false
current_price_promotable = false
execution_authorized = false
```

## Independence boundary

Pyth and Jupiter are distinct provider paths, but two provider names do not
prove independent market-price formation.

CMIS does not yet claim:

- upstream publisher/source independence;
- no market-input overlap;
- equivalent price-construction semantics;
- current-price authority.

Those require separate evidence.

## Live acceptance

The Solana live gate reads the exact sponsored USDC/USD account through the
configured read-only Solana RPC and requires:

- exact mint/feed mapping;
- exact account owner;
- exact feed ID;
- exact write authority;
- full verification;
- positive price;
- valid `publish_time`;
- source-specific deterministic freshness classification.

The live test does not require the observed feed to be FRESH. STALE or FUTURE
are valid deterministic evidence outcomes and must not be rewritten.

## Safety

No:

- Hermes API call;
- Pyth price update submission;
- Wormhole VAA submission;
- Solana transaction construction;
- signing;
- broadcast;
- custody;
- trading;
- public/Scout current-price promotion;
- execution authority.
