# Persistent Concentration Warning Evidence Contract

Status: CMIS Issue #396 first Early Warning foundation slice — internal, read-only, non-promoted.

## Purpose

This contract defines the first persistent Early Warning evidence primitive after CMIS 1.17 field-scoped freshness. It evaluates whether an explicit concentration-threshold condition is satisfied by **two distinct compatible CMIS-owned concentration-change intelligence observations**.

This contract does not create a public CMIS alert service, Scout reliance, ROBERTA planner behavior, delivery authority, risk severity, behavioral/ownership inference, or execution authority.

## Trust root

The warning builder accepts only canonical CMIS-owned `top_account_concentration_change` intelligence evidence identified by exact `ie_<64 hex>` ids and resolved through the trusted internal intelligence-evidence resolver.

Each evidence object must be deterministically rebuilt through the already-accepted `concentration_change_intelligence/v1` path. The warning layer does not accept caller-supplied:

- concentration-change bundles;
- Evidence Receipts;
- Proof Scores;
- provider assertions;
- freshness labels;
- behavioral/ownership/risk labels;
- replacement threshold results.

The accepted concentration intelligence service remains authoritative for canonical fact validation, exact subject identity, evidence lineage, freshness state, unresolved fields, and threshold-policy assessment.

## First-slice subject and compatibility

Version 1 is X1-only and requires exactly two evidence ids.

Both resolved observations must have identical:

- chain;
- asset id;
- source;
- scope;
- requested account limit;
- observed account count.

The caller supplies one exact expected chain and asset id. Both resolved observations must match those bindings exactly.

The warning layer does not merge different sources, scopes, top-N definitions, account cardinalities, or assets.

## Distinctness and replay protection

The two intelligence evidence ids must be distinct.

Duplicate evidence is rejected before evaluation and can never inflate persistence counts. The same two accepted evidence ids, policy, times, and compatibility state deterministically rebuild the same warning id.

Version 1 uses:

```text
persistence_mode = two_distinct_compatible_observations
required_observations = 2
```

No hidden repetition rule exists.

## Ordering

The caller-supplied evidence-id order is material and is not silently sorted.

The canonical `after_observed_at` of the first observation must be strictly earlier than the second observation.

Equal or decreasing fact times fail closed.

## Persistence window

The contract requires an explicit non-negative `max_persistence_window_seconds`.

The persistence span is:

```text
second.after_observed_at - first.after_observed_at
```

The equality boundary is accepted. A span greater than the configured maximum fails closed.

No implicit calendar window, interpolation, or missing-observation assumption is used.

## Latest-evidence freshness

The contract requires:

- canonical UTC `evaluated_at` ending in `Z`;
- explicit non-negative `max_latest_age_seconds`.

`evaluated_at` may not precede the second observation.

The latest age is:

```text
evaluated_at - second.after_observed_at
```

The equality boundary is accepted. A larger age fails closed.

In addition, each accepted `concentration_change_intelligence/v1` response must already report:

```text
evidence.freshness_verified = true
evidence.unresolved_fields = []
```

A timestamp alone cannot override an unverified Evidence Receipt freshness state.

## Threshold policy

The accepted metric and unit are exactly:

```text
metric = absolute_delta_bps
unit = basis_points
```

The threshold policy must contain exactly:

- `policy_id`;
- `policy_version`;
- `absolute_delta_threshold_bps`.

Version 1 supports explicit comparators:

```text
GT
GTE
```

The existing CMIS threshold evaluator remains authoritative for `EXCEEDS_THRESHOLD`, `AT_THRESHOLD`, and `WITHIN_THRESHOLD`.

The warning condition maps those states deterministically:

- `GT`: satisfied only by `EXCEEDS_THRESHOLD`;
- `GTE`: satisfied by `EXCEEDS_THRESHOLD` or `AT_THRESHOLD`;
- `WITHIN_THRESHOLD`: never satisfied.

## Persistent warning state

Each of the two compatible observations is evaluated independently under the same explicit threshold policy and comparator.

The persistent warning is active only when **both** observations satisfy the threshold condition.

Version 1 exposes exactly:

```text
WATCH = both observations satisfy the condition
CLEAR = persistence condition is not proven
```

`WATCH` and `CLEAR` are deterministic warning-state vocabulary. They are not market facts, risk levels, safety grades, manipulation labels, or predictions.

## Evidence lineage

For each resolved observation, the warning preserves exactly the accepted concentration-intelligence evidence summary:

- intelligence evidence id;
- Evidence Receipt ids;
- Proof Score records;
- freshness state;
- canonical concentration fact;
- deterministic threshold assessment.

The warning must not synthesize a new Evidence Receipt or Proof Score merely to fill a missing field.

Proof Score remains separate from warning state and risk.

## Deterministic identity

The warning id is SHA-256 over canonical JSON of all material warning content except the warning id itself:

```text
cw_<64 lowercase hex>
```

Material content includes subject binding, evaluation time, policy, comparator, persistence/freshness policy, observation identities, canonical fact times, threshold states, Receipt/Proof lineage, and resulting warning state.

Changing material evidence or policy changes the id or causes fail-closed rejection.

## Fail-closed behavior

Version 1 rejects or remains unavailable for:

- anything other than exactly two evidence ids;
- malformed or duplicate evidence ids;
- unavailable trusted evidence resolver;
- missing or invalid CMIS-owned evidence;
- deterministic evidence revalidation failure;
- wrong chain or asset;
- incompatible source, scope, requested account limit, or observed account count;
- equal/out-of-order observation times;
- persistence-window overflow;
- evaluation before the latest observation;
- stale latest observation;
- Evidence Receipt freshness not verified;
- unresolved evidence fields;
- malformed or hidden threshold policy;
- threshold unit other than `basis_points`;
- unsupported comparator;
- unsupported threshold status;
- caller-supplied proof/evidence/behavior/ownership/risk material.

Missing evidence remains unknown/unavailable. It is never converted into zero, false, an estimate, interpolation, or LLM-authored completion.

## Authority and non-goals

The result must preserve:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
delivery_authorized = false
risk_interpretation_verified = false
behavioral_interpretation_verified = false
ownership_interpretation_verified = false
proof_strength_separate_from_risk = true
execution_authorized = false
```

A `WATCH` result does not establish or imply:

- whale, insider, bot, accumulator, distributor, or market maker identity;
- common owner, beneficial owner, or coordinated control;
- manipulation, fraud, scam, or malicious intent;
- causality;
- imminent price movement;
- risk severity;
- safety;
- complete holder/account history;
- transaction preparation or execution permission.

## Promotion boundary

This is foundation-only work. A later separately accepted issue is required before any:

- public CMIS Early Warning service;
- capability-manifest promotion;
- X1 Scout reliance;
- ROBERTA `/alert` or warning workflow;
- delivery/notification transport;
- risk mapping;
- execution-related use.

`execution_authorized=false`
