# XDEX outputAmount / slippage semantic follow-up

This follow-up begins after PR #180 / Issue #28 established the field-level XDEX evidence boundary.

## Goal

Determine, read-only and fail-closed, where the remaining XDEX quote-output adjustment enters and whether any accepted evidence can identify `outputAmount`, slippage tolerance, or minimum-received semantics.

## Already accepted

- pinned XENCAT/native-XNT pool and AMM config identities
- classic SPL Token mints on both sides (Token-2022 transfer fee not applicable)
- AMM trade fee rate 2800 ppm = 0.28%
- route-scoped `priceImpactPct` independently reproducible from active reserves and the verified CP curve
- `outputAmount` remains provider-reported because the verified curve output is larger by roughly 0.52%

## New evidence question

Compare the same exact-in XENCAT -> XNT amounts across:

1. XDEX `/api/xendex/swap/quote` `outputAmount`
2. XDEX Oracle `/api/v1/token/sell-quote` `amount_out_quote`
3. independently reconstructed CP-swap output from X1 RPC active reserves and AMM config

The comparison is intended to localize the unexplained adjustment:

- Oracle ~= CP but swap quote lower: adjustment likely enters above/common AMM math, in the swap quote/router surface.
- Oracle ~= swap quote and both are lower than CP: adjustment likely exists in a shared XDEX quoting rule or on-chain Oracle sell-quote calculation.
- all three differ: preserve all decompositions as unresolved and investigate each path independently.

These are localization hypotheses, not semantic labels.

## 0.5% hypothesis

Official XDEX user documentation distinguishes Price Impact, Minimum Received, and configurable Slippage Tolerance. The observed roughly 0.52% output shortfall is numerically close to a 0.5% protection haircut, but numerical proximity is not proof.

The live probe therefore reports ratios against an exact 0.5% haircut while deliberately making no assertion that the haircut is slippage or minimum received.

## Safety boundary

Read-only only: GET requests and X1 RPC reads. Do not call `/swap/prepare`; do not construct, sign, simulate for execution, broadcast, custody, or move value.
