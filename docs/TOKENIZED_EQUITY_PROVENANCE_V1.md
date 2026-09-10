# Tokenized Equity Provenance v1

`tokenized_equity_provenance/v1` is the first CMIS foundation for keeping a
blockchain token representation separate from the underlying security it may
reference.

It is intentionally structural and non-promoted. It does **not** prove that a
token is legally the underlying share, that its issuer/backing/custody claims
are true, that a bridge is live, or that the holder receives shareholder
rights.

## Contract

```text
tokenized_equity_provenance/v1
```

The record binds four distinct layers:

1. **Token identity** — exact chain-scoped token/mint/contract identifier.
2. **Underlying security identity** — an exact security identifier such as
   ISIN/CUSIP/SEDOL/FIGI, never a ticker/name alone.
3. **Representation structure** — a controlled representation class plus
   descriptive issuer, backing, custody, and wrapper-layer claims.
4. **Optional cross-chain structural lineage** — an accepted
   `cross_chain_asset_provenance/v1` object whose current endpoint must exactly
   equal the tokenized-equity token.

## Evidence boundary

The builder proves schema and structural identity continuity only.

The following remain unverified until later evidence-bearing contracts prove
them independently:

- representation classification;
- issuer identity;
- direct ownership of the underlying equity;
- backing/collateral;
- custody;
- voting, dividend, redemption, or other holder rights;
- live deployment;
- live bridge-route availability;
- source independence.

Attaching `cross_chain_asset_provenance/v1` proves only the structural lineage
already expressed by that object. It does not upgrade bridge availability,
backing, custody, or legal/economic equivalence.

## Required negative authority

The contract explicitly keeps all of these unauthorized:

- token == underlying share;
- direct or beneficial shareholder ownership;
- voting/dividend/redemption rights;
- issuer guarantee;
- backing sufficiency;
- custody safety;
- legal/economic equivalence between similarly named representations;
- live bridge availability;
- live X1 support;
- automatic risk conclusion;
- legal advice;
- trade recommendation;
- execution.

## Relationship to #660

This is the first accepted-building-block target in CMIS #660:

```text
Tokenized Equity Provenance
  -> tokenized_equity_rights/v1
  -> Robinhood Chain Discovery
  -> Cross-Chain Equity Provenance
  -> Equity Liquidity / Activity Intelligence
  -> ROBERTA Human/Machine explanations
```

The existing Robinhood→X1 structural extension remains useful input to future
cross-chain work, but it does not itself establish that tokenized equities or a
Robinhood→X1 bridge are live.

## Promotion state

This foundation is intentionally:

- `read_only=true`
- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`
