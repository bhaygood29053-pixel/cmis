# Cross-Chain Asset Provenance v1

Status: **accepted foundation + CMIS 1.20 public promotion / read-only**

Tracking issues: #402 foundation; #491 public/Scout promotion

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
7. The internal primitive remains read-only and non-promoted; CMIS 1.20 exposes
   only a separately validated public wrapper resolved from CMIS-owned
   content-addressed evidence.
8. The public wrapper preserves `execution_authorized=false` and does not
   promote backing, solvency, safety, adoption, causality, custody truth, live
   bridge state, or risk.

## Roadmap

After this foundation is accepted, follow-on work may add:

1. verified bridge-route/provider evidence;
2. bridge supply and 24h/7d/30d flow history;
3. XDEX pool discovery for bridged representations;
4. Bridge-to-DEX utilization intelligence;
5. ROBERTA/X1 Scout consumption after a separate promotion gate.


## CMIS 1.20 public promotion — Issue #491

The accepted foundation is now exposed to X1 Scout only through the public
`cross_chain_asset_provenance` service. The protected runtime resolves a
CMIS-owned canonical provenance record by exact `evidence_sha256`. Callers
supply only that selector plus the exact current X1 `asset_id` and
`asset_id_kind`.

The wrapper revalidates the content hash and deterministically rebuilds the
accepted v1 structure before returning the canonical ordered lineage and
representation depth. Caller-supplied hops, bridge/custody fields, dependencies,
verification claims, risk, or precomputed provenance are not accepted.

```text
service = cross_chain_asset_provenance
service_contract_version = cross_chain_asset_provenance/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

This promotion authorizes structural lineage consumption only. Symbol/name
equality remains invalid identity evidence. Bridge/custody dependency remains
descriptive rather than a risk conclusion. Missing lineage remains unknown.
