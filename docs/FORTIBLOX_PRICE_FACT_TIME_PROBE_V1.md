# FortiBlox Price Fact-Time Probe v1

Issues: #567, #646

Contract:

`fortiblox_price_fact_time_probe/v1`

## Purpose

This is an evidence gate, not a freshness promotion.

CMIS may observe repeated public FortiBlox `/api/tokens` responses and ask a narrow question: does the evidence prove that top-level `updatedAt` is the exact fact time for each token's `priceUsd` field?

The only allowed conclusions are:

- `PROVEN`
- `DISPROVEN`
- `EVIDENCE_INCOMPLETE`

## Fail-closed rule

Repeated numerical agreement or a visually plausible millisecond timestamp is not enough to prove field-level timestamp semantics.

A direct contradiction is decisive: if an exact mint's `priceUsd` changes while top-level `updatedAt` remains unchanged, the claimed binding is `DISPROVEN` for the observed contract.

If price changes remain coupled to `updatedAt` changes, the result is still `EVIDENCE_INCOMPLETE` unless independent provider-owned semantic evidence explicitly establishes that `updatedAt` timestamps the token price field.

Only that combination may produce `PROVEN`.

## Timestamp boundary

The probe may report observational diagnostics such as:

- `updated_at_millisecond_shape_observed`
- `updated_at_clock_near_collection_observed`

These are not semantic verification. The probe keeps:

```text
timestamp_unit_verified=false
clock_semantics_verified=false
```

unless a later separately accepted proof establishes them.

## Authority boundary

This probe does not establish:

- source independence;
- CMIS verification of FortiBlox;
- 24h volume freshness or semantics;
- risk;
- Proof Score;
- public-service promotion;
- X1 Scout or ROBERTA reliance;
- transaction, payment, signing, broadcast, or execution authority.

The live workflow uses no authentication, payment, wallet, or transaction action and retains only bounded selected public fields needed for the semantic test. Raw response bodies are not uploaded.

`execution_authorized=false`

## Promotion rule

Do not create or advertise `fortiblox_price_freshness/v1` from this probe unless the result is `PROVEN` and the exact supporting live evidence is accepted under #567.

If the live evidence remains inconclusive, close #567 as `EVIDENCE_INCOMPLETE` and keep cross-source `current_fact_corroboration=false`.
