# X1 Evidence Capability Boundary

Status date: **2026-08-18**

This document records the accepted CMIS decision for the remaining X1 evidence gaps. The machine-readable source of truth is `liquidity_scout/cmis/x1_evidence_capabilities.py` and the same records are exposed under `GET /v1/cmis/capabilities` → `chains.x1.evidence_capabilities`.

The rule is deliberately fail-closed:

- **verified** — usable as a verified fact only for the exact named scope;
- **bounded** — a deterministic evidence primitive exists, but broader semantics/coverage remain unproven;
- **unavailable** — current accepted provider contracts do not prove the fact, so CMIS must not promote it.

An unavailable capability may be reconsidered only after a new accepted evidence contract and tests. UI text, provider advertising, or plausible interpretation is not enough.

## Holder / concentration

| Capability | State | Boundary |
|---|---|---|
| Wallet / beneficial-owner holder total | unavailable | Provider counted-entity semantics and total coverage are not proven; token accounts are not equivalent to wallets or beneficial owners. |
| Token-account concentration | bounded | May describe the observed largest token accounts as a share of mint supply; must not be called holder/wallet concentration or a total holder count. |

## Historical / archival

| Capability | State | Boundary |
|---|---|---|
| Explicit requested-slot same-fact comparison | bounded | Deterministic comparison exists when source independence is explicitly established. |
| Archival history completeness | unavailable | Sparse samples do not prove continuous coverage, retention depth, finality equivalence, reconnect, or backfill. |
| Provider trade-range exhaustiveness | unavailable | Provider pagination/range completeness and full ordering/staleness semantics remain unproven. |

## XDEX history / quote

| Capability | State | Boundary |
|---|---|---|
| Direct XDEX history semantics | unavailable | Pair direction, timestamps, quote units, range, and gap semantics are not proven for CMIS history promotion. |
| Direct XDEX quote semantics | unavailable | Amount/rate, route, fees, expiry/freshness, and price-impact semantics are not proven for pre-trade evidence. |

## Native XNT

| Capability | State | Boundary |
|---|---|---|
| Canonical native-XNT translation | verified | CMIS may distinguish canonical native XNT identity from wrapped market representation and use the accepted native network-supply path. |
| Native-XNT direct-XDEX quote translation | unavailable | The verified canonical translation does not prove the blocked direct-XDEX quote transport semantics. |

## SSE / live-event evidence

| Capability | State | Boundary |
|---|---|---|
| X1.Ninja SSE access handshake | bounded | The read-only classifier may report handshake/access observations only. |
| X1.Ninja live-event evidence | unavailable | Event schema, ordering, duplicate handling, reconnect/backfill, dropped-event detection, and freshness semantics are not accepted CMIS facts. |

## Warp Bridge

| Capability | State | Boundary |
|---|---|---|
| Exact candidate URL provenance gate | bounded | Can decide whether a candidate read URL has acceptable provenance; it does not discover an endpoint or validate semantics. |
| Operational state | unavailable | No provenance-approved, contract-tested machine-readable read source is accepted. |
| Supported asset/route state | unavailable | Canonical representation modeling is not proof of current bridge route support. |
| Fee/capacity | unavailable | No accepted machine-readable fee/capacity contract. |
| Transfer lifecycle/history | unavailable | No authoritative contract-tested lifecycle source. |
| Guardian state | unavailable | UI observation is not accepted machine-readable guardian/quorum/health evidence. |

## Safety boundary

This work is read-only evidence classification. It adds no transaction construction, signing, broadcasting, custody, bridge transfer, trading, autonomous execution, or value movement.
