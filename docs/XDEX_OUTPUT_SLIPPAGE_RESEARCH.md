# XDEX `outputAmount` / slippage semantic follow-up

This follow-up begins after PR #180 / Issue #28 established the field-level XDEX evidence boundary.

## Goal

Determine, read-only and fail-closed, where the remaining XDEX quote-output adjustment enters and which `outputAmount` / slippage semantics can now be defended independently.

## Accepted starting point

PR #180 established:

- pinned XENCAT/native-XNT pool and AMM-config identities;
- classic SPL Token mints on both sides, ruling out Token-2022 transfer fees for the test pair;
- pinned config trade-fee rate `2800 / 1_000_000 = 0.28%`;
- route-scoped `priceImpactPct` independently reproducible from active reserves and the verified constant-product curve; and
- default XDEX `outputAmount` roughly 0.52% below the independently reconstructed 0.28%-fee curve output, with the cause deliberately unnamed.

## Evidence result 1 — Oracle sell quote is a no-trade-fee curve reference

For exact-in XENCAT -> native-XNT test sizes `1`, `2`, `1000`, and `10000` XENCAT, XDEX Oracle `/api/v1/token/sell-quote` `amount_out_quote` matched the independently reconstructed **no-fee** constant-product curve output exactly at output-token raw precision.

This establishes a useful provider boundary for the tested route:

```text
Oracle amount_out_quote ~= no-fee CP curve output
```

It does **not** make the Oracle quote fee-complete, slippage-adjusted, or executable.

## Evidence result 2 — `slippage` request parameter is verified

The live GET `/api/xendex/swap/quote` contract recognizes the query parameter:

```text
slippage
```

Controlled values establish that the parameter is expressed in **percent**, not basis points:

| Request | Meaning observed |
|---|---:|
| `slippage=0` | 0% |
| `slippage=0.01` | 0.01% = 1 bp |
| `slippage=0.1` | 0.1% = 10 bps |
| `slippage=0.5` | 0.5% = 50 bps |
| `slippage=1.0` | 1.0% = 100 bps |

For whole-basis-point values, the returned output follows the raw-unit relationship:

```text
output_raw(slippage=s)
  = floor(output_raw(slippage=0) * (1 - s / 100))
```

within at most one raw output unit where response serialization/rounding requires it.

Alternate candidate names tested without an observable quote effect:

- `slippage_bps`
- `slippageBps`
- `slippage_tolerance`
- `slippageTolerance`

They must not be treated as accepted request semantics.

## Evidence result 3 — default slippage is 0.5%

Omitting the `slippage` parameter produced the same output as explicitly supplying:

```text
slippage=0.5
```

Therefore, for the tested current live quote contract:

```text
XDEX default quote slippage = 0.5%
```

This is independently reproduced live rather than inferred from UI wording.

`priceImpactPct` did not change when slippage changed across the controlled request set. Price impact and slippage are therefore separate quote semantics.

## Evidence result 4 — the old ~0.52% discrepancy is mathematically decomposed

The previous default-output discrepancy is no longer a single unexplained haircut.

For the pinned XENCAT/native-XNT route under AMM config:

```text
2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c
```

the on-chain config decodes:

```text
trade_fee_rate = 2800 ppm = 0.28%
```

However, with `slippage=0`, the live XDEX quote reproduced a constant-product output calculated with an **effective 3000-ppm / 0.30% input deduction** exactly at raw precision across six bidirectional cases.

Examples covered:

- XENCAT -> XNT: 100, 1000, 10000 XENCAT
- XNT -> XENCAT: 0.01, 0.1, 1 XNT

For these cases:

```text
CP output @ 2800 ppm != XDEX slippage=0 output
CP output @ 3000 ppm == XDEX slippage=0 output
```

The normal/default quote then applies the verified 0.5% slippage transform to that zero-slippage output.

Thus the old approximate ~0.52% difference can be separated mathematically into:

1. a quote curve output behaving as if the effective deduction were 0.30% rather than the pinned config's 0.28%; then
2. the verified default 0.5% slippage adjustment.

The first item is an **observed quote-math rule**, not yet a business/fee label.

## Evidence result 5 — not a universal extra 2-bps fee

A second XDEX market, XNT/USDC.X, was independently discovered from X1 RPC. The selected live pool under the same `2eFP...` 2800-ppm config again reproduced a 3000-ppm effective zero-slippage curve output exactly in both directions.

A second live AMM config was also discovered:

```text
ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x
```

Its decoded on-chain trade-fee rate is already:

```text
3000 ppm = 0.30%
```

For live routes selecting this config, `slippage=0` matched the config's own 3000-ppm curve output at raw precision (or within one raw unit in one observed case). Applying another 200 ppm was wrong.

Therefore the evidence does **not** support saying:

```text
XDEX adds a universal 0.02% fee on top of every AMM fee.
```

The safer observed rule is:

```text
The tested XDEX exact-in quote routes use an effective 3000-ppm
(0.30%) curve deduction before the slippage transform.
```

For the 2800-ppm config, the reason XDEX quote math uses 3000 ppm remains unlabelled.

## Current config inventory boundary

A read-only X1 RPC inventory observed approximately 1,204 current 637-byte XDEX pool-state candidates and only two distinct AMM configs in that layout family:

| AMM config | Decoded trade-fee rate |
|---|---:|
| `2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c` | 2800 ppm / 0.28% |
| `ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x` | 3000 ppm / 0.30% |

No currently observed config above 3000 ppm exists in this inventory, so the evidence cannot distinguish whether the quote service:

- always uses 3000 ppm for this route family; or
- applies a 3000-ppm minimum/floor while preserving higher future configs.

Do not generalize beyond the observed config set.

## Minimum received boundary

The quote `outputAmount` is now proven to be **slippage-adjusted** according to the accepted `slippage` parameter and its 0.5% default.

That makes it strongly consistent with a minimum-received style value. However, no accepted production backend/frontend source has yet bound the field name `outputAmount` to XDEX's user-facing label **Minimum Received**, nor has this work invoked or decoded a transaction-preparation path to prove the eventual on-chain `minimum_amount_out` argument.

Therefore:

- slippage parameter semantics: **VERIFIED**;
- default 0.5% slippage: **VERIFIED**;
- `outputAmount` slippage transform: **VERIFIED for tested exact-in routes**;
- `outputAmount` = user-facing Minimum Received: **BOUNDED / not fully verified**;
- eventual on-chain minimum-output instruction binding: **UNAVAILABLE**;
- fill quality: **UNAVAILABLE**.

## Fee/decomposition boundary

The following statements remain unsafe:

- the 2800 -> 3000 quote-math difference is a router fee;
- it is a platform fee;
- it is a protocol fee;
- it is a fund fee;
- it is an affiliate/referral fee;
- it is a safety fee;
- it is a hidden 0.02% fee charged on every XDEX swap.

The arithmetic behavior is reproducible; the business/source label is not.

## CMIS promotion recommendation

Safe field-level capabilities from this follow-up:

```text
xdex quote slippage parameter name/percent units         VERIFIED
xdex current default slippage = 0.5%                     VERIFIED
outputAmount raw-unit slippage transform                 VERIFIED, tested scope
priceImpactPct independence from slippage                VERIFIED, tested scope
Oracle amount_out_quote as no-fee CP curve reference     VERIFIED, tested scope
3000-ppm effective zero-slippage curve behavior          VERIFIED, tested configs/routes
outputAmount full business/fee decomposition              BOUNDED
outputAmount == user-facing Minimum Received              BOUNDED
all-in fee decomposition                                  UNAVAILABLE
on-chain minimum_amount_out binding                       UNAVAILABLE
route optimality/multi-hop semantics                      UNAVAILABLE
fill quality                                               UNAVAILABLE
```

These route/config proofs must not leak into generic pre-trade analysis for an unrelated asset such as AGI until that asset's exact route, pool, config, reserves, and quote contract are independently resolved and re-verified.

## Safety boundary

Read-only only: GET requests and X1 RPC reads. `/swap/prepare` was not invoked. No transaction construction, signing, broadcasting, custody, execution, or value movement was performed.
