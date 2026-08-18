# XDEX historical execution fee semantics

Status date: **2026-08-18**

This document records the bounded read-only result for Issue #189: whether completed XDEX swaps on the pinned XENCAT/native-XNT pool execute according to the on-chain AMM config's **2800 ppm / 0.28%** trade-fee rate or the XDEX backend quote service's observed **3000 ppm / 0.30%** zero-slippage quote baseline.

## Scope

Pinned identities:

- XDEX X1 mainnet program: `sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN`
- XENCAT mint: `DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb`
- native/wrapped-XNT market identity: `So11111111111111111111111111111111111111112`
- pool: `6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry`
- AMM config: `2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c`
- decoded config trade-fee rate: `2800 / 1_000_000 = 0.28%`
- decoded protocol fee rate: `250000`
- decoded fund fee rate: `50000`

The result is historical and route-scoped. It must not be generalized to other pools, assets, AMM configs, route types, or future XDEX versions without re-verification.

## Why a single historical transaction is insufficient

X1 RPC `preTokenBalances` / `postTokenBalances` expose the gross token balances of the pool vault accounts. Reference Raydium CP-Swap accounting computes curve reserves from vault balances **after subtracting accrued protocol/fund/creator fee counters**.

Therefore a single completed transaction's gross pre-swap vault balances are not enough to reconstruct the active constant-product reserves safely.

The sampled XDEX mainnet transactions also exposed no compatible direct `trade_fee` diagnostic log, no compatible SwapEvent carrying a direct trade-fee field, and no useful transaction return data. Gross-vault-only 2800/3000 comparisons are therefore diagnostic only.

## State-contiguous sequence method

The historical transaction metadata exposes something stronger: a long sequence where the post-swap gross vault state of one completed swap is exactly the pre-swap gross vault state of the next.

The live probe found a **23-swap state-contiguous sequence** spanning slots `66,617,613` through `72,301,970`, with swaps in both directions.

For each candidate trade-fee rate (2800 ppm and 3000 ppm), the reconstruction:

1. uses the XDEX/Raydium-derived fee-accounting model;
2. computes trade fee with ceiling division in `10^-6` units;
3. treats protocol and fund fees as portions within the trade fee;
4. infers the two initial accrued fee-counter values from the first opposite-direction swap pair using exact rational arithmetic;
5. searches only a small nearby integer range to account for discrete raw-token rounding; and
6. propagates those counters through the remaining state-contiguous swaps and predicts each completed output.

The first two opposite-direction swaps therefore determine the initial hidden counter state. The remaining swaps act as holdout validation of the candidate fee-rate model.

## Result

### 2800-ppm candidate

Across the 23-swap contiguous sequence:

- maximum absolute output error: **406 raw units**
- sum absolute output error: **1,115 raw units**
- many swaps match exactly or differ by only 1–13 raw units

Representative larger-output cases remain within only hundreds of raw units despite outputs in the hundreds of billions of raw units.

### 3000-ppm candidate

Across the same sequence:

- maximum absolute output error: **1,557,603,301 raw units**
- sum absolute output error: **2,513,561,183 raw units**
- material misses include tens of millions, hundreds of millions, and more than 1.5 billion raw units

The live CI gate additionally requires the 3000-ppm maximum error to be more than **1,000×** the 2800-ppm maximum error. The observed ratio is far larger than that threshold.

## Classification

**STRONGLY CORROBORATED / CMIS bounded:** completed historical XENCAT/native-XNT swaps on the pinned 2800-ppm XDEX config execute consistently with a **2800-ppm / 0.28%** Raydium-derived fee/counter model and are strongly inconsistent with a 3000-ppm execution model.

This is independent historical execution evidence because it uses completed X1 transaction vault-state transitions and actual outputs, not XDEX quote arithmetic.

The state remains bounded rather than globally verified because:

- the fee-counter accounting implementation is corroborated from the XDEX IDL/config plus Raydium reference source rather than authoritative current XDEX contract source;
- the two initial historical fee counters are inferred rather than read from an archival pool-state snapshot;
- the proof covers one pinned pool/config and one historical contiguous sequence; and
- it does not prove all XDEX route types or future program versions.

## Consequence for the 2800 -> 3000 discrepancy

For the tested scope, the evidence strongly localizes the 3000-ppm behavior to the **quote layer rather than completed AMM execution**.

Safe statement:

```text
Pinned on-chain AMM config:          2800 ppm / 0.28%
Historical execution reconstruction: strongly supports 2800 ppm
XDEX slippage=0 backend quote:       behaves as 3000 ppm / 0.30%
```

Unsafe statements remain:

- XDEX executes a hidden extra 0.02% fee;
- the extra 20 ppm is collected by a router, platform, affiliate, or protocol account;
- the private backend implementation is known;
- the quote service necessarily implements `max(config_fee, 3000)`.

The exact private XDEX backend reason for using the 3000-ppm quote baseline remains **UNAVAILABLE**.

## Safety boundary

Read-only X1.Ninja history, completed X1 RPC transaction metadata, public reference-source inspection, and deterministic arithmetic only. `/swap/prepare` was not invoked. No transaction was constructed, signed, broadcast, simulated for execution, or used to move value.
