# Concentration Threshold Alert Evidence Contract

Status: CMIS Issue #263 first slice — internal, read-only, non-promoted.

## Purpose

This contract defines the first evidence-backed CMIS alert primitive: a deterministic concentration-threshold alert built only from canonical `cmis_top_account_concentration_change.v1` evidence and the existing `evaluate_concentration_threshold()` policy evaluator.

It does not create a public CMIS service, Scout-reliance contract, Roberta behavior, risk score, behavioral/ownership inference, or execution authority.

## First-slice scope

The accepted first slice supports:

- one canonical CMIS concentration-change observation;
- explicit expected chain and asset/subject identity;
- explicit policy identity and version;
- explicit absolute-delta threshold with fixed `basis_points` unit;
- explicit `GT` (`>`) or `GTE` (`>=`) comparator semantics;
- freshness measured from canonical `after_observed_at` to canonical `evaluated_at`;
- single-observation persistence only;
- a content-addressed triggering evidence identifier;
- a content-addressed alert identifier;
- explicit non-promotion and execution-denial fields.

Multi-observation persistence, duration windows, repetition rules, alert delivery, public service promotion, and Scout/Roberta adoption are out of scope for this slice.

## Canonical input and subject authority

The alert builder accepts exactly the canonical v1 concentration-change field set. Extra fields are rejected so caller-supplied ownership, behavior, risk, fraud, manipulation, intent, or replacement verification labels cannot ride alongside otherwise valid evidence.

The caller must also supply normalized `expected_chain` and `expected_asset_id` policy bindings. The canonical concentration change must match both exactly before alert evaluation continues. A canonical observation for a different chain or asset is valid evidence for that other subject, but is unavailable for the requested alert subject and therefore fails closed here.

The threshold unit is also explicit. Version 1 accepts only:

```text
threshold_unit = basis_points
metric = absolute_delta_bps
```

No implicit unit conversion is performed. Percent, ratio, token amount, fiat amount, or other units are rejected.

The existing concentration-threshold evaluator remains authoritative for:

- concentration-change schema validation;
- exact-ratio consistency;
- chain/asset/source/scope identity inside the canonical evidence;
- requested/observed account bounds;
- canonical observation timestamps;
- direction consistency;
- explicit threshold normalization;
- non-promotable behavioral/risk boundaries.

The alert layer wraps that evaluator; it does not reproduce or replace its concentration truth logic. The returned evaluator subject must still match the independently supplied expected chain and asset.

## Comparator semantics

Version 1 supports exactly:

```text
GT   -> absolute_delta_bps > threshold
GTE  -> absolute_delta_bps >= threshold
```

The existing evaluator distinguishes `EXCEEDS_THRESHOLD`, `AT_THRESHOLD`, and `WITHIN_THRESHOLD`. The alert layer maps those deterministic states to `ABOVE_THRESHOLD`, `AT_THRESHOLD`, and `BELOW_THRESHOLD`, then applies the explicit comparator.

Equality therefore does not trigger `GT` and does trigger `GTE`.

## Freshness

`evaluated_at` and the concentration change's `after_observed_at` must be canonical UTC timestamps ending in `Z`.

`evaluated_at` may not precede the observation. Evidence is accepted only when:

```text
evaluated_at - after_observed_at <= max_evidence_age_seconds
```

The equality boundary is fresh. Stale evidence fails closed with no alert object.

## Persistence and duplicate protection

This first slice supports only:

```text
mode = single_observation
required_observations = 1
```

The builder accepts one concentration-change object rather than an observation list. One canonical content-addressed evidence ID is evaluated exactly once, so duplicate evidence cannot inflate persistence counts in this slice.

A future multi-observation persistence contract must separately define deduplication, ordering, compatible scope, duration/window boundaries, and repetition semantics.

## Deterministic identity

The triggering evidence ID is SHA-256 over canonical JSON for the validated canonical concentration-change object:

```text
ce_<64 lowercase hex>
```

The alert ID is SHA-256 over canonical JSON for all material alert content except the alert ID itself:

```text
ca_<64 lowercase hex>
```

Canonical JSON uses sorted keys and compact separators. Rebuilding the same accepted alert from the same evidence and policy produces the same IDs. Changing material evidence, expected subject identity, policy, comparator, freshness, threshold, unit, or evaluation content changes the applicable ID or causes fail-closed rejection.

## Evidence, proof, risk, and authority separation

The alert is deterministic policy evaluation over accepted evidence. It is not a risk score or severity score.

The first slice does not bind an Evidence Receipt or Proof Score identity because the accepted concentration-change primitive does not expose those identities at this seam. Those fields remain `null`; they are not guessed or synthesized.

The result explicitly preserves:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
behavioral_interpretation_verified = false
risk_interpretation_verified = false
execution_authorized = false
```

## Prohibited implications

A triggered alert does not establish or imply whale, insider, bot, accumulator, distributor, market maker, common owner, beneficial owner, coordinated control, manipulation, fraud, scam, malicious intent, causality, imminent price movement, safety, risk severity, complete holder history, transaction preparation, or execution permission.

## Fail-closed behavior

The first slice rejects or fails closed for:

- non-canonical or extra concentration-change fields;
- invalid canonical concentration evidence rejected by the existing evaluator;
- canonical evidence whose chain does not match `expected_chain`;
- canonical evidence whose asset/subject does not match `expected_asset_id`;
- a threshold unit other than `basis_points`;
- unsupported or ambiguous comparator values;
- missing/hidden threshold values;
- non-canonical timestamps;
- evaluation before the observation;
- stale evidence;
- invalid freshness policy;
- caller-supplied extra behavioral/ownership/risk labels through the evidence object;
- any future multi-observation persistence shape not separately accepted.

Missing evidence remains unavailable; it is never converted into zero, false, an estimate, or LLM-authored completion.

## Promotion boundary

This is foundation-only CMIS work. A later separately accepted issue is required before any public-service promotion, Scout reliance, Roberta planner behavior, alert transport/delivery, risk mapping, or execution-related use.
