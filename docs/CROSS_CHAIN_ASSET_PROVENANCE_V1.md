# Cross-Chain Asset Provenance v1

Status: **foundation / read-only / non-promoted**

Tracking issue: #402

## Purpose

`cross_chain_asset_provenance/v1` is the first CMIS primitive for preserving
canonical cross-chain asset lineage. It is intentionally narrower than Bridge
Intelligence. It validates ordered chain-scoped identity continuity and refuses
symbol/name equivalence as identity evidence.

## Authority boundary

This primitive does **not** verify:

- live bridge route state;
- bridge backing or reserve sufficiency;
- custody claims;
- bridge supply;
- inflows/outflows;
- XDEX liquidity;
- provider source independence.

Those require separate provider evidence and promotion gates.

## Required structure

Each endpoint contains:

- `chain`
- `asset_id`
- `asset_id_kind`

Each hop contains:

- source endpoint
- destination endpoint
- bridge
- representation type
- optional custody model
- optional backing asset id
- optional route id

The first hop must start at the declared origin, every intermediate hop must be
continuous, and the final hop must end at the declared current representation.

## Hard rules

1. Symbol, ticker, name, and label are never accepted as identity roots.
2. Every hop preserves source and destination chain identity.
3. Same-chain transformations are outside this contract.
4. Duplicate hops fail closed.
5. Missing or discontinuous lineage fails closed.
6. Structural validation never becomes live bridge verification.
7. The primitive remains read-only, non-promoted, and
   `execution_authorized=false`.

## Roadmap

After this foundation is accepted, follow-on work may add:

1. verified bridge-route/provider evidence;
2. bridge supply and 24h/7d/30d flow history;
3. XDEX pool discovery for bridged representations;
4. Bridge-to-DEX utilization intelligence;
5. ROBERTA/X1 Scout consumption after a separate promotion gate.
