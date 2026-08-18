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

The current deployed XDEX frontend independently supports this contract: it sends the user's stored `slippage` value to the quote service and falls back to `0.5` when no value is stored. The frontend consumes the backend-returned `outputAmount`; it does not apply the observed 3000-ppm curve deduction locally at the displayed quote call site.

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

The first item is an **observed quote-math rule**, not a business/fee label.

## Evidence result 5 — not a universal extra 2-bps fee

A second XDEX market, XNT/USDC.X, was independently discovered from X1 RPC. The selected live pool under the same `2eFP...` 2800-ppm config again reproduced a 3000-ppm effective zero-slippage curve output in both directions within the live-probe raw-unit tolerance.

A second live AMM config was also discovered:

```text
ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x
```

Its decoded on-chain trade-fee rate is already:

```text
3000 ppm = 0.30%
```

For live routes selecting this config, `slippage=0` matched the config's own 3000-ppm curve output at raw precision (or within the bounded live-probe tolerance). Applying another 200 ppm was wrong.

Therefore the evidence does **not** support saying:

```text
XDEX adds a universal 0.02% fee on top of every AMM fee.
```

A read-only historical transfer probe also inspected five completed XENCAT/XNT swaps and found no separate parsed SPL-token transfer approximately equal to 2 bps of the observed asset amount. This does not prove that no separate fee mechanism can ever exist, but it further prevents promotion of the fixed-2-bps integrator-fee label.

The safer observed rule is:

```text
The tested XDEX exact-in quote routes use an effective 3000-ppm
(0.30%) curve deduction before the slippage transform.
```

For the 2800-ppm config, the reason XDEX quote math uses 3000 ppm remains unavailable.

## Current config inventory boundary

A read-only X1 RPC inventory observed approximately 1,204 current 637-byte XDEX pool-state candidates and only two distinct AMM configs in that layout family:

| AMM config | Decoded trade-fee rate |
|---|---:|
| `2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c` | 2800 ppm / 0.28% |
| `ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x` | 3000 ppm / 0.30% |

No currently observed config above 3000 ppm exists in this inventory, so the evidence cannot distinguish whether the quote service:

- always uses 3000 ppm for this route family; or
- applies a 3000-ppm minimum/floor while preserving higher future configs; or
- implements another backend convention that happens to reproduce the same observed arithmetic.

Do not generalize beyond the observed config set.

## XDEX CP-Swap program-family boundary

The supplied XDEX IDL identifies `raydium_cp_swap` version `0.1.0`. It documents:

- configurable `tradeFeeRate` in `10^-6` units;
- `protocolFeeRate` and `fundFeeRate` as rates within the trade fee;
- `swapBaseInput(amountIn, minimumAmountOut)`;
- `minimum_amount_out` as the minimum output token amount that prevents excessive slippage; and
- an `ExceededSlippage` program error.

Its metadata address is:

```text
7EEuq61z9VKdkUzj7G36xGd7ncyz8KBtUwAWVjypYQHf
```

Independent X1Pays xDEX integration code maps that address to **X1 testnet** and maps:

```text
sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN
```

to **X1 mainnet**. Historical completed XDEX swaps on mainnet contain the matching Anchor `swap_base_input` discriminator under `sEsYH...`.

Therefore the IDL is used as strong structural/program-family corroboration, not as proof that the testnet metadata address is the active mainnet program address.

The older IDL `SwapEvent` layout contains pool/vault/input/output/transfer-fee fields but no explicit AMM `trade_fee` field. Failure to extract an executed 2800-vs-3000 AMM fee directly from those historical events therefore cannot be treated as evidence that the quote-side 3000-ppm behavior is executed on-chain.

## Minimum received / prepare boundary

The quote `outputAmount` is proven to be **slippage-adjusted** according to the accepted `slippage` parameter and its current 0.5% default.

XDEX user documentation defines **Minimum Received** as the minimum token amount a user receives for slippage protection. The deployed frontend sends the same user slippage value to both quote and `/api/xdex/swap/prepare`, and the XDEX CP-Swap IDL defines `swapBaseInput(amountIn, minimumAmountOut)` with the minimum-output argument explicitly serving as the excessive-slippage boundary.

Read-only historical mainnet transactions further decode the 24-byte `swap_base_input` instruction as:

- 8-byte Anchor discriminator;
- first `u64`: `amount_in`;
- second `u64`: transaction-specific minimum-output threshold.

Across sampled successful swaps, the observed actual output was greater than or equal to that second `u64`. Historical gaps varied materially, showing that the current 0.5% UI/API default is not a universal historical/on-chain slippage rule.

Therefore:

- slippage parameter semantics: **VERIFIED**;
- current default 0.5% slippage: **VERIFIED**;
- `outputAmount` slippage transform: **VERIFIED for tested exact-in routes**;
- `outputAmount` as minimum-received-style quote floor: **STRONGLY CORROBORATED**;
- `swap_base_input` second `u64` as transaction-specific on-chain minimum-output boundary: **STRONGLY CORROBORATED**;
- exact server-side `/swap/prepare` formula mapping the supplied `slippage`/quote state into that `minimum_amount_out`: **UNAVAILABLE** because prepare was not invoked;
- quote-to-execution fill quality: **UNAVAILABLE**.

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

A numerical hypothesis such as `max(config_trade_fee_rate, 3000 ppm)` fits the currently observed 2800/3000 config set, but it remains an inference only. The public evidence cannot distinguish that hypothesis from a hard-coded 3000 baseline, legacy compatibility rule, conservative quote convention, or other backend behavior.

## CMIS promotion recommendation

Safe field-level capabilities from this follow-up:

```text
xdex quote slippage parameter name/percent units         VERIFIED
xdex current default slippage = 0.5%                     VERIFIED
outputAmount raw-unit slippage transform                 VERIFIED, tested scope
priceImpactPct independence from slippage                VERIFIED, tested scope
Oracle amount_out_quote as no-fee CP curve reference     VERIFIED, tested scope
3000-ppm effective zero-slippage curve behavior          VERIFIED, tested configs/routes
native AMM config trade fee 2800 ppm / 0.28%             VERIFIED/DOCUMENTED, pinned scope
outputAmount minimum-received-style semantics            STRONGLY CORROBORATED
on-chain transaction-specific minimum_amount_out         STRONGLY CORROBORATED
quote -> prepare minimum-output formula                  UNAVAILABLE
all-in fee/business decomposition                        UNAVAILABLE
route optimality/multi-hop semantics                     UNAVAILABLE
fill quality                                             UNAVAILABLE
```

These route/config proofs must not leak into generic pre-trade analysis for an unrelated asset such as AGI until that asset's exact route, pool, config, reserves, and quote contract are independently resolved and re-verified.

## Safety boundary

Read-only public frontend inspection, GET requests, historical transaction inspection, and X1 RPC reads only. `/swap/prepare` was not invoked. No transaction construction, signing, broadcasting, custody, execution, or value movement was performed.
