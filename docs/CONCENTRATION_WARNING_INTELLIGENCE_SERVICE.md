# Concentration Warning Intelligence v1

Status: CMIS Issue #399 public-service promotion contract.

## Service identity

```text
service = concentration_warning_intelligence
service_contract = concentration_warning_intelligence/v1
chain = x1
delivery_mode = pull_only
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
push_delivery_authorized = false
execution_authorized = false
```

CMIS capability contract target: `1.18.0`.

## Purpose

This service exposes the already-accepted persistent concentration warning
foundation from Issue #396 as a bounded X1 request/response intelligence service.

The service does not calculate concentration, rebuild historical observations,
invent persistence, infer freshness from timestamps, or recompute Proof Scores.
Those facts remain owned by the accepted CMIS evidence/intelligence foundation
and protected persistent-warning builder.

## Request boundary

The runtime accepts exactly these params:

- `asset_id`;
- `intelligence_evidence_ids` — exactly two canonical CMIS-owned `ie_...` ids;
- `threshold_policy` with exactly:
  - `policy_id`;
  - `policy_version`;
  - `absolute_delta_threshold_bps`;
- `threshold_unit = basis_points`;
- `comparator = GT | GTE`;
- `evaluated_at` canonical UTC;
- `max_latest_age_seconds`;
- `max_persistence_window_seconds`.

The trusted intelligence-evidence resolver is runtime-owned and is never caller supplied.

Caller-supplied evidence bundles, Evidence Receipts, Proof Scores, concentration
facts, persistent warning objects, provider assertions, behavioral labels,
ownership labels, risk labels, or delivery state are rejected.

## Accepted protected input

The public response builder accepts only one canonical
`cmis_persistent_concentration_warning.v1` object produced by the accepted
Issue #396 implementation.

It verifies the warning contract and deterministic `cw_...` identity before
exposure. This integrity validation does not recompute the underlying market fact.

## Response

A successful response preserves:

- exact `warning_id`;
- `WATCH` / `CLEAR`;
- exact threshold policy/comparator;
- exact persistence state;
- exact freshness policy;
- exact observation fact times;
- exact CMIS intelligence evidence ids;
- exact Evidence Receipt ids;
- exact Proof Score records;
- limitations;
- original canonical protected warning object.

The service adds only promotion/delivery metadata:

```text
delivery_mode = pull_only
push_delivery_authorized = false
public_service_promoted = true
scout_reliance_promoted = true
```

The nested canonical warning remains unchanged and retains its original internal
non-promotion flags.

## Status

Both `WATCH` and `CLEAR` are valid successful service results.

`WATCH` means only that the accepted two-observation deterministic threshold
persistence condition passed.

`CLEAR` means that persistent condition was not proven by both accepted
observations.

Neither is a risk level.

## Evidence and authority

The service must preserve:

```text
warning_level_is_risk_severity = false
risk_interpretation = null
risk_interpretation_verified = false
behavioral_interpretation_verified = false
ownership_interpretation_verified = false
proof_strength_separate_from_risk = true
push_delivery_authorized = false
execution_authorized = false
```

No whale, insider, bot, beneficial-owner, manipulation, fraud, intent,
causality, or imminent-price inference is added.

## Solana

Solana is explicitly unavailable for v1.

```text
state = unavailable
callable = false
public_service_promoted = false
scout_reliance_promoted = false
```

## Delivery boundary

This service is pull-only. Public-service promotion does not authorize:

- watchlist schedulers;
- webhooks;
- Telegram push;
- background polling;
- subscriptions;
- retry/delivery queues;
- notification acknowledgement;
- autonomous monitoring.

Those require a separate accepted delivery contract.

## ROBERTA boundary

Scout-reliance promotion means X1 Scout may adopt this CMIS service after its
own contract validation. ROBERTA runtime/Decision Object adoption is not part
of Issue #399 and requires a separate downstream acceptance gate.

`execution_authorized=false`
