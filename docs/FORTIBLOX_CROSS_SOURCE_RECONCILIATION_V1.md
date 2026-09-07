# FortiBlox Cross-Source Reconciliation v1

Issue: #563

Contract:

`fortiblox_cross_source_reconciliation/v1`

## Purpose

CMIS may compare one normalized FortiBlox token observation against bounded XDEX, X1.Ninja, and accepted CMIS reference evidence for the exact same mint.

The result is a reconciliation record, not a new truth authority. Numerical agreement can strengthen corroboration, while disagreement is surfaced explicitly. Agreement never proves source independence and never upgrades FortiBlox into CMIS-verified evidence.

## Field states

Each comparable field produces one of:

- `AGREE` — values are within the explicit tolerance;
- `DISAGREE` — a material numerical conflict exists;
- `EVIDENCE_INCOMPLETE` — value/semantic evidence is insufficient;
- `SCOPE_MISMATCH` — nominally similar values describe different scopes/windows;
- `NOT_COMPARABLE` — the reference explicitly says the field should not be compared.

No disagreement is averaged away and the reconciler does not choose a provider winner.

## Price policy

The default price tolerance is the accepted Instant X1 Scan current-price tolerance:

- relative tolerance: 0.5%;
- absolute floor: 1e-12 USD.

The accepted FortiBlox token-field boundary treats `priceUsd` as a provider-labeled USD price observation. This is sufficient for bounded numerical comparison when the reference price semantics are verified.

FortiBlox `updatedAt` is not promoted to exact per-field price fact time. Therefore ordinary price agreement is not current-fact corroboration unless a separate FortiBlox price-freshness proof is supplied.

## 24h volume policy

FortiBlox `volume24hUsd` remains provider-labeled data whose exact rolling-window and contributing-market scope have not yet been proven.

Volume comparison therefore fails closed by default. It becomes comparable only when separate evidence proves:

- FortiBlox volume semantics;
- exact 86,400-second rolling window;
- exact scope identifier;
- matching reference scope;
- reference volume semantics;
- and, for current-fact corroboration, freshness on both sides.

Default numeric tolerance after those semantic gates pass is 1% relative with a $0.01 absolute floor, matching the accepted X1 rolling-24h market-activity tolerance family.

## XDEX overlap

FortiBlox token rows may themselves list XDEX among their provider sources. The reconciler preserves this as `upstream_overlap_with_fortiblox=true`.

A FortiBlox↔XDEX match may therefore be useful same-fact corroboration but must not be described as independent-source confirmation.

## CMIS authority

When a supplied `cmis` reference has `cmis_verified=true`, that reference remains authoritative even if FortiBlox disagrees.

The reconciliation output preserves:

`cmis_reference_authoritative=true`

while also preserving:

`fortiblox_cmis_verified=false`
`cmis_verification_promoted_from_agreement=false`

A FortiBlox disagreement does not erase accepted CMIS truth, and a FortiBlox agreement does not inherit CMIS authority.

## Promotion boundary

This contract is internal provider reconciliation only.

It does not authorize:

- CMIS verification from provider agreement;
- Proof Score changes by itself;
- deterministic risk conclusions;
- recommendations;
- public-service exposure;
- X1 Scout or ROBERTA reliance;
- signing, transaction construction, broadcast, swaps, payments, or any other execution.

Every result preserves `execution_authorized=false`.
