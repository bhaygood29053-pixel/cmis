# Tokenized Equity Market Activity v1

Issue: #670
Parent: #660

Contract:

```text
tokenized_equity_market_activity/v1
```

This is a bounded, non-promoted market-observation foundation for tokenized-equity representations. It binds exact tokenized-equity provenance to an exact chain-scoped observation scope and keeps each market metric semantically separate.

## Required metrics

The contract carries exactly these independent metrics:

- `liquidity_usd` — `liquidity_snapshot`
- `trade_volume_usd` — `executed_trade_volume`
- `trade_count` — `executed_trade_count`
- `transfer_count` — `token_transfer_count`
- `holder_count` — `holder_snapshot`
- `price_usd` — one of executed, quoted, reference, or derived price semantics
- `bridge_inflow_units` — `bridge_inflow`
- `bridge_outflow_units` — `bridge_outflow`

A caller cannot relabel one metric as another. In particular, transfers are not trades, liquidity is not volume, and bridge flow is not exchange volume.

## Scope and zero semantics

Scopes are explicit `asset`, `venue`, or `pool` identities. Venue/pool observations require an exact program identity. Symbol, ticker, name, and label values are not accepted as exact scope identifiers.

A zero value can be recorded as a bounded zero only when the supplied observation scope declares complete coverage for that exact scope. Even then:

```text
bounded_zero_equals_global_zero = false
global_market_coverage_verified = false
```

The foundation does not independently verify a provider's completeness declaration. That belongs to the later evidence/freshness/confidence acceptance layer.

## Time and freshness

Snapshot metrics carry explicit fact time. Window metrics carry explicit start/end times and computed duration. Freshness is evaluated from metric fact time/window end, never from retrieval time alone.

The contract preserves `FRESH`, `STALE`, or `UNKNOWN` freshness state. Retrieval of old data does not make the underlying fact current.

## Price semantics

`price_usd` must be explicitly classified as one of:

- `executed_trade_price`
- `quoted_price`
- `reference_price`
- `derived_price`

Only `executed_trade_price` requires transaction-bound on-chain/indexer evidence. A quote, reference, or derived value is never relabeled as an executed trade price.

## Evidence/source boundary

Observed metrics require provider/source identity, HTTPS source URL, observation id, retrieval time, content SHA-256, and optional transaction identity. This proves structural provenance, not provider truth or global completeness.

## Hard boundaries

The contract does not establish:

- global market coverage;
- tokenized-equity deployment on X1;
- a Robinhood Chain → X1 route;
- adoption from bridge movement;
- beneficial ownership from holder count;
- shareholder rights from market activity;
- manipulation, insider, whale, or causality conclusions;
- automatic risk or investment conclusions;
- trade execution authority.

Promotion remains locked:

```text
read_only=true
public_service_promoted=false
scout_reliance_promoted=false
execution_authorized=false
```
